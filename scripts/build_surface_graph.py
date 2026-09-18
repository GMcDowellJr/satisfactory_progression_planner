"""Build a sparse layered-surface adjacency graph from generated spatial products.

The generator deliberately keeps ordinary Landscape/base movement implicit in the existing
heightfield. ``vertical_intervals.npz`` contains the exceptional, vertically layered XY
columns. This tool turns those exception-floor intervals into explicit graph nodes and
builds:

* explicit surface-to-surface candidate edges between neighboring exception columns;
* portal edges between an exception surface node and an ordinary implicit base-grid cell.

Ordinary base-grid-to-base-grid adjacency is NOT duplicated into this graph. A routing
consumer combines the ordinary heightfield with this overlay.

Node IDs are stable and zero-copy: node id N is interval N in ``vertical_intervals.npz``.
The graph therefore does not rewrite the node table. Edges are sharded by map direction and
chunk so the builder never needs tens of millions of Python edge objects in RAM.

This is intentionally a candidate *geometric* graph, not yet the final vehicle graph.
Edges retain distance/dz/grade and node clearance; tractor/truck/foot/rail policy belongs
downstream. Interval schema 3 carries event-level connected component identity. The graph uses it
to reject vertically-near but topologically unrelated surface transitions.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import time
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

NODATA = -32768

DIRECTIONS = (
    ("east",       0,  1, 1.0),
    ("south",      1,  0, 1.0),
    ("southeast",  1,  1, math.sqrt(2.0)),
    ("southwest",  1, -1, math.sqrt(2.0)),
)

PORTAL_DIRECTIONS = (
    ("north",     -1,  0, 1.0),
    ("northeast",-1,  1, math.sqrt(2.0)),
    ("east",       0,  1, 1.0),
    ("southeast",  1,  1, math.sqrt(2.0)),
    ("south",      1,  0, 1.0),
    ("southwest",  1, -1, math.sqrt(2.0)),
    ("west",       0, -1, 1.0),
    ("northwest", -1, -1, math.sqrt(2.0)),
)


def decode_i16(path: Path, height: int, width: int) -> np.ndarray:
    raw = zlib.decompress(path.read_bytes())
    delta = np.frombuffer(raw, dtype="<i2")
    if delta.size != height * width:
        raise ValueError(
            f"{path}: decoded {delta.size} cells; expected {height * width}"
        )
    running = np.cumsum(
        delta.reshape(height, width).astype(np.int32), axis=1
    )
    return running.astype(np.int16)


def load_base_at_interval_resolution(
    height_dir: Path,
    *,
    interval_step_m: float,
    interval_east0_m: float,
    interval_north0_m: float,
    interval_height: int,
    interval_width: int,
) -> np.ndarray:
    meta = json.loads((height_dir / "meta.json").read_text(encoding="utf-8"))
    g = meta["grid"]
    h = int(g["height"])
    w = int(g["width"])
    native_step_m = float(g["spacing_cm"]) / 100.0
    east0_m = float(g["x0_cm"]) / 100.0
    north0_m = -float(g["y0_cm"]) / 100.0

    if abs(east0_m - interval_east0_m) > 1e-4 or abs(north0_m - interval_north0_m) > 1e-4:
        raise ValueError(
            "heightmap and interval grid origins differ: "
            f"height=({east0_m},{north0_m}), interval="
            f"({interval_east0_m},{interval_north0_m})"
        )

    ratio = interval_step_m / native_step_m
    stride = int(round(ratio))
    if stride < 1 or abs(stride * native_step_m - interval_step_m) > 1e-6:
        raise ValueError(
            f"interval step {interval_step_m} m is not a whole multiple of "
            f"heightmap step {native_step_m} m"
        )

    height_dm = decode_i16(height_dir / "height.i16.z", h, w)
    sampled = height_dm[::stride, ::stride]
    sampled = sampled[:interval_height, :interval_width]

    if sampled.shape != (interval_height, interval_width):
        raise ValueError(
            f"sampled heightmap shape {sampled.shape} != interval grid "
            f"{(interval_height, interval_width)}"
        )

    base = sampled.astype(np.float32) / 10.0
    base[sampled == NODATA] = np.nan
    return base


def component_candidate_pairs(
    z_a: np.ndarray,
    z_b: np.ndarray,
    comp_a: np.ndarray,
    comp_b: np.ndarray,
    *,
    distance_m: float,
    max_dz_m: float,
    base_seam_max_grade: float,
    cross_component_seam_max_grade: float,
    ambiguous_seam_max_grade: float,
    max_neighbors: int,
):
    """Return candidate pairs using component identity as evidence, not a hard wall.

    Relation codes:
      0 same connected component
      1 base (component 0) <-> placed connected component seam
      2 different positive connected components, geometrically continuous seam
      3 mixed/ambiguous contributor seam

    The connected-component pass is intentionally conservative and may fail to union
    separately placed meshes that nevertheless form one continuous traversable surface.
    Therefore cross-component edges are retained only when their local dz satisfies a
    strict geometric seam-grade limit. The route solver can then penalize relation 2/3
    rather than making the world artificially disconnected.
    """
    if len(z_a) == 0 or len(z_b) == 0:
        return []

    dz = np.abs(z_a[:, None] - z_b[None, :])
    relation = np.full(dz.shape, 3, np.uint8)

    aa = comp_a[:, None]
    bb = comp_b[None, :]

    same = aa == bb
    relation[same] = 0

    base_switch = ((aa == 0) & (bb > 0)) | ((bb == 0) & (aa > 0))
    relation[base_switch] = 1

    cross_pos = (aa > 0) & (bb > 0) & (aa != bb)
    relation[cross_pos] = 2

    ambiguous = (aa < 0) | (bb < 0)
    relation[ambiguous] = 3

    allowed = dz <= max_dz_m
    allowed &= (
        (relation == 0)
        | ((relation == 1) & (dz <= base_seam_max_grade * distance_m + 1e-6))
        | ((relation == 2) & (dz <= cross_component_seam_max_grade * distance_m + 1e-6))
        | ((relation == 3) & (dz <= ambiguous_seam_max_grade * distance_m + 1e-6))
    )

    chosen: set[tuple[int, int]] = set()
    for ia in range(len(z_a)):
        valid = np.flatnonzero(allowed[ia])
        if len(valid):
            order = valid[np.argsort(dz[ia, valid], kind="stable")[:max_neighbors]]
            chosen.update((ia, int(ib)) for ib in order)
    for ib in range(len(z_b)):
        valid = np.flatnonzero(allowed[:, ib])
        if len(valid):
            order = valid[np.argsort(dz[valid, ib], kind="stable")[:max_neighbors]]
            chosen.update((int(ia), ib) for ia in order)

    return [(ia, ib, int(relation[ia, ib])) for ia, ib in sorted(chosen)]


class ShardWriter:
    def __init__(self, out_dir: Path, kind: str, direction: str):
        self.out_dir = out_dir
        self.kind = kind
        self.direction = direction
        self.index = 0
        self.files: list[dict] = []
        self.total = 0

    def write(self, *, bbox=None, **arrays):
        if not arrays:
            return
        n = len(next(iter(arrays.values())))
        if n == 0:
            return

        name = f"{self.kind}_{self.direction}_{self.index:04d}.npz"
        path = self.out_dir / name
        np.savez_compressed(path, **arrays)
        rec={
            "file": name,
            "records": int(n),
            "bytes": int(path.stat().st_size),
        }
        if bbox is not None:
            rec["bbox_rc"]=[int(x) for x in bbox]
        self.files.append(rec)
        self.total += int(n)
        self.index += 1


def _bbox_from_cells(cells: np.ndarray, width: int):
    if len(cells)==0:
        return None
    rr=cells//width; cc=cells%width
    return (int(rr.min()),int(rr.max()),int(cc.min()),int(cc.max()))


def build_direction(
    *,
    direction: str,
    dr: int,
    dc: int,
    distance_factor: float,
    cells: np.ndarray,
    offsets: np.ndarray,
    floor_z: np.ndarray,
    floor_component: np.ndarray,
    clearance: np.ndarray,
    base_z: np.ndarray,
    grid_height: int,
    grid_width: int,
    step_m: float,
    max_dz_m: float,
    base_seam_max_grade: float,
    cross_component_seam_max_grade: float,
    ambiguous_seam_max_grade: float,
    max_neighbors: int,
    chunk_pairs: int,
    out_dir: Path,
    emit_explicit: bool = True,
    emit_portals: bool = True,
):
    """Build one undirected map direction using only positive dr/dc directions."""
    rows = cells // grid_width
    cols = cells % grid_width

    target_rows = rows + dr
    target_cols = cols + dc
    in_bounds = (
        (target_rows >= 0) & (target_rows < grid_height) &
        (target_cols >= 0) & (target_cols < grid_width)
    )

    src_pos = np.flatnonzero(in_bounds)
    src_cells = cells[src_pos]
    target_cells = (
        target_rows[in_bounds] * grid_width + target_cols[in_bounds]
    ).astype(np.int64)

    # Which target columns are themselves exception columns?
    where = np.searchsorted(cells, target_cells)
    target_is_exception = where < len(cells)
    safe = np.minimum(where, max(len(cells) - 1, 0))
    if len(cells):
        target_is_exception &= cells[safe] == target_cells
    else:
        target_is_exception[:] = False

    explicit_writer = ShardWriter(out_dir, "edges", direction)
    portal_writer = ShardWriter(out_dir, "portals", direction)

    distance_m = float(step_m * distance_factor)

    # Explicit exception-column pairs.
    ex_idx = np.flatnonzero(target_is_exception) if emit_explicit else np.empty(0,dtype=np.int64)
    for chunk_start in range(0, len(ex_idx), chunk_pairs):
        batch = ex_idx[chunk_start:chunk_start + chunk_pairs]

        u_list = []
        v_list = []
        dz_list = []
        grade_list = []
        min_clear_list = []
        relation_list = []

        for j in batch:
            a_pos = int(src_pos[j])
            b_pos = int(where[j])

            a0, a1 = int(offsets[a_pos]), int(offsets[a_pos + 1])
            b0, b1 = int(offsets[b_pos]), int(offsets[b_pos + 1])
            za = floor_z[a0:a1]
            zb = floor_z[b0:b1]
            ca = floor_component[a0:a1]
            cb = floor_component[b0:b1]

            for ia, ib, relation in component_candidate_pairs(
                za, zb, ca, cb,
                distance_m=distance_m,
                max_dz_m=max_dz_m,
                base_seam_max_grade=base_seam_max_grade,
                cross_component_seam_max_grade=cross_component_seam_max_grade,
                ambiguous_seam_max_grade=ambiguous_seam_max_grade,
                max_neighbors=max_neighbors,
            ):
                u = a0 + ia
                v = b0 + ib
                signed_dz = float(floor_z[v] - floor_z[u])
                u_list.append(u)
                v_list.append(v)
                dz_list.append(signed_dz)
                grade_list.append(abs(signed_dz) / distance_m)
                relation_list.append(relation)

                cu = float(clearance[u])
                cv = float(clearance[v])
                if math.isfinite(cu) and math.isfinite(cv):
                    mc = min(cu, cv)
                elif math.isfinite(cu):
                    mc = cu
                elif math.isfinite(cv):
                    mc = cv
                else:
                    mc = math.nan
                min_clear_list.append(mc)

        if u_list:
            batch_cells=np.concatenate([src_cells[batch], target_cells[batch]])
            explicit_writer.write(
                bbox=_bbox_from_cells(batch_cells, grid_width),
                u=np.asarray(u_list, np.int64),
                v=np.asarray(v_list, np.int64),
                distance_m=np.full(len(u_list), distance_m, np.float32),
                dz_m=np.asarray(dz_list, np.float32),
                grade=np.asarray(grade_list, np.float32),
                min_known_clearance_m=np.asarray(min_clear_list, np.float32),
                component_relation=np.asarray(relation_list, np.uint8),
            )

    # Exception -> ordinary implicit-base portals.
    portal_idx = np.flatnonzero(~target_is_exception) if emit_portals else np.empty(0,dtype=np.int64)
    flat_base = base_z.reshape(-1)

    for chunk_start in range(0, len(portal_idx), chunk_pairs):
        batch = portal_idx[chunk_start:chunk_start + chunk_pairs]

        node_list = []
        cell_list = []
        target_z_list = []
        dz_list = []
        grade_list = []
        relation_list = []

        for j in batch:
            a_pos = int(src_pos[j])
            target_cell = int(target_cells[j])
            bz = float(flat_base[target_cell])
            if not math.isfinite(bz):
                continue

            a0, a1 = int(offsets[a_pos]), int(offsets[a_pos + 1])
            za = floor_z[a0:a1]
            ca = floor_component[a0:a1]
            if len(za) == 0:
                continue

            dz = np.abs(za - bz)
            # Ordinary implicit terrain is component 0. Positive placed components may
            # join it only at a tight seam; mixed/ambiguous events use the tighter limit.
            limits = np.where(
                ca == 0,
                max_dz_m,
                np.where(
                    ca > 0,
                    base_seam_max_grade * distance_m,
                    ambiguous_seam_max_grade * distance_m,
                ),
            )
            valid = np.flatnonzero(dz <= limits)
            if not len(valid):
                continue

            order = valid[np.argsort(dz[valid], kind="stable")[:max_neighbors]]
            for ia in order:
                node_id = a0 + int(ia)
                signed_dz = bz - float(floor_z[node_id])
                node_list.append(node_id)
                cell_list.append(target_cell)
                target_z_list.append(bz)
                dz_list.append(signed_dz)
                grade_list.append(abs(signed_dz) / distance_m)
                relation_list.append(0 if int(ca[int(ia)]) == 0 else (1 if int(ca[int(ia)]) > 0 else 3))

        if node_list:
            batch_cells=np.concatenate([src_cells[batch], target_cells[batch]])
            portal_writer.write(
                bbox=_bbox_from_cells(batch_cells, grid_width),
                node=np.asarray(node_list, np.int64),
                implicit_cell_index=np.asarray(cell_list, np.int32),
                implicit_z_m=np.asarray(target_z_list, np.float32),
                distance_m=np.full(len(node_list), distance_m, np.float32),
                dz_m=np.asarray(dz_list, np.float32),
                grade=np.asarray(grade_list, np.float32),
                component_relation=np.asarray(relation_list, np.uint8),
            )

    return {
        "direction": direction,
        "explicit_edges": explicit_writer.total,
        "portal_edges": portal_writer.total,
        "edge_shards": explicit_writer.files,
        "portal_shards": portal_writer.files,
    }



def _resolve_workers(requested: int, task_count: int) -> int:
    if requested < 0:
        raise SystemExit("--workers must be >= 0")
    if requested == 1:
        return 1
    if requested > 1:
        return min(requested, task_count)
    cpu = os.cpu_count() or 2
    # Each process opens the interval arrays and a 2 m base-height grid, so keep auto modest.
    return min(task_count, max(1, min(4, cpu // 2 if cpu > 1 else 1)))


def _worker_build(task: dict) -> dict:
    """Load read-only source products locally and build one independent direction."""
    spatial_root = Path(task["spatial_root"])
    interval_path = spatial_root / "multisurface" / "vertical_intervals.npz"
    height_dir = spatial_root / "heightmap"
    out_dir = Path(task["out_dir"])

    started = time.time()
    with np.load(interval_path, mmap_mode="r") as iv:
        step_m = float(iv["step_m"][0])
        east0_m = float(iv["east0_m"][0])
        north0_m = float(iv["north0_m"][0])
        width = int(iv["width"][0])
        height = int(iv["height"][0])

        cells = np.asarray(iv["cell_index"], dtype=np.int64)
        offsets = np.asarray(iv["interval_offsets"], dtype=np.int64)
        schema = int(iv["schema_version"][0])
        if schema < 3 or "floor_component_id" not in iv:
            raise ValueError(
                f"vertical_intervals.npz schema {schema} lacks event-level component identity; "
                "regenerate with gen_world_spatial.py v11+"
            )
        floor_z = np.asarray(iv["floor_z_m"], dtype=np.float32)
        floor_component = np.asarray(iv["floor_component_id"], dtype=np.int32)
        clearance = np.asarray(iv["clearance_m"], dtype=np.float32)

        base_z = load_base_at_interval_resolution(
            height_dir,
            interval_step_m=step_m,
            interval_east0_m=east0_m,
            interval_north0_m=north0_m,
            interval_height=height,
            interval_width=width,
        )

        result = build_direction(
            direction=task["direction"],
            dr=task["dr"],
            dc=task["dc"],
            distance_factor=task["distance_factor"],
            cells=cells,
            offsets=offsets,
            floor_z=floor_z,
            floor_component=floor_component,
            clearance=clearance,
            base_z=base_z,
            grid_height=height,
            grid_width=width,
            step_m=step_m,
            max_dz_m=task["max_dz_m"],
            base_seam_max_grade=task["base_seam_max_grade"],
            cross_component_seam_max_grade=task["cross_component_seam_max_grade"],
            ambiguous_seam_max_grade=task["ambiguous_seam_max_grade"],
            max_neighbors=task["max_neighbors"],
            chunk_pairs=task["chunk_pairs"],
            out_dir=out_dir,
            emit_explicit=task["emit_explicit"],
            emit_portals=task["emit_portals"],
        )
    result["seconds"] = round(time.time() - started, 1)
    result["task_kind"] = task["task_kind"]
    return result



def parse_args():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--spatial-root",
        type=Path,
        default=Path("data/local/spatial"),
        help="root containing heightmap/ and multisurface/",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output directory; default <spatial-root>/surface_graph",
    )
    p.add_argument(
        "--max-dz-m",
        type=float,
        default=8.0,
        help=(
            "broad geometric candidate limit between neighboring 2 m columns. "
            "8 m preserves the current foot hard-grade envelope; movement modes filter later"
        ),
    )
    p.add_argument(
        "--base-seam-max-grade",
        type=float,
        default=1.0,
        help=(
            "maximum geometric grade for component-0 base to/from placed-surface seams; "
            "default 1.0 = 100%%. Route-mode grade limits still apply downstream."
        ),
    )
    p.add_argument(
        "--cross-component-seam-max-grade",
        type=float,
        default=1.0,
        help=(
            "maximum geometric grade for a seam between two different positive "
            "placed-surface components; default 1.0 = 100%%. Such edges remain "
            "distinguishable and are penalized by the route solver."
        ),
    )
    p.add_argument(
        "--ambiguous-seam-max-grade",
        type=float,
        default=1.0,
        help=(
            "maximum geometric grade when either event has mixed/ambiguous component identity; "
            "route-mode grade limits still apply downstream"
        ),
    )
    p.add_argument(
        "--max-neighbors-per-node",
        type=int,
        default=2,
        help="retain up to this many nearest-Z candidates in each adjacent exception column",
    )
    p.add_argument(
        "--chunk-pairs",
        type=int,
        default=100_000,
        help="neighbor column-pairs processed per output shard batch",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=0,
        help=(
            "parallel worker processes. 0=auto (up to 4); 1=serial/debug. "
            "Each worker loads its own read-only spatial arrays."
        ),
    )
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    spatial_root = args.spatial_root.resolve()
    interval_path = spatial_root / "multisurface" / "vertical_intervals.npz"
    height_dir = spatial_root / "heightmap"
    out_dir = (args.out or (spatial_root / "surface_graph")).resolve()

    if not interval_path.exists():
        raise SystemExit(f"missing {interval_path}")
    if not (height_dir / "height.i16.z").exists():
        raise SystemExit(f"missing {height_dir / 'height.i16.z'}")

    if out_dir.exists():
        if not args.force:
            raise SystemExit(f"{out_dir} exists; pass --force to replace it")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    started = time.time()
    with np.load(interval_path, mmap_mode="r") as iv:
        schema = int(iv["schema_version"][0])
        if schema < 2:
            raise SystemExit(
                f"vertical interval schema {schema} is older than the sparse exception format; "
                "regenerate with gen_world_spatial.py v9+"
            )

        step_m = float(iv["step_m"][0])
        east0_m = float(iv["east0_m"][0])
        north0_m = float(iv["north0_m"][0])
        width = int(iv["width"][0])
        height = int(iv["height"][0])

        cells = iv["cell_index"].astype(np.int64, copy=False)
        offsets = iv["interval_offsets"].astype(np.int64, copy=False)
        floor_z = iv["floor_z_m"].astype(np.float32, copy=False)
        clearance = iv["clearance_m"].astype(np.float32, copy=False)

        if len(offsets) != len(cells) + 1:
            raise SystemExit("interval_offsets length does not equal cell_index + 1")
        if int(offsets[-1]) != len(floor_z):
            raise SystemExit("interval_offsets[-1] does not equal node/floor count")
        if np.any(cells[1:] <= cells[:-1]):
            raise SystemExit("cell_index must be strictly increasing")

        print(
            f"loading base terrain at {step_m:g} m for {height}x{width} grid; "
            f"{len(cells):,} exception columns, {len(floor_z):,} surface nodes"
        )
        base_z = load_base_at_interval_resolution(
            height_dir,
            interval_step_m=step_m,
            interval_east0_m=east0_m,
            interval_north0_m=north0_m,
            interval_height=height,
            interval_width=width,
        )

        tasks = []
        for name, dr, dc, factor in DIRECTIONS:
            tasks.append({
                "task_kind": "explicit",
                "direction": name,
                "dr": dr,
                "dc": dc,
                "distance_factor": factor,
                "emit_explicit": True,
                "emit_portals": False,
            })
        for name, dr, dc, factor in PORTAL_DIRECTIONS:
            tasks.append({
                "task_kind": "portal",
                "direction": name,
                "dr": dr,
                "dc": dc,
                "distance_factor": factor,
                "emit_explicit": False,
                "emit_portals": True,
            })

        workers = _resolve_workers(args.workers, len(tasks))
        common = {
            "spatial_root": str(spatial_root),
            "out_dir": str(out_dir),
            "max_dz_m": args.max_dz_m,
            "base_seam_max_grade": args.base_seam_max_grade,
            "cross_component_seam_max_grade": args.cross_component_seam_max_grade,
            "ambiguous_seam_max_grade": args.ambiguous_seam_max_grade,
            "max_neighbors": args.max_neighbors_per_node,
            "chunk_pairs": args.chunk_pairs,
        }
        tasks = [{**common, **t} for t in tasks]

        print(
            f"building {len(DIRECTIONS)} explicit directions + "
            f"{len(PORTAL_DIRECTIONS)} portal directions with {workers} worker(s)..."
        )

        completed = []
        if workers == 1:
            for task in tasks:
                label = f"{task['task_kind']}:{task['direction']}"
                print(f"  {label} ...", flush=True)
                r = _worker_build(task)
                completed.append(r)
                count = r["explicit_edges"] if r["task_kind"] == "explicit" else r["portal_edges"]
                print(f"    {count:,} records in {r['seconds']:.1f}s", flush=True)
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_worker_build, task): task for task in tasks}
                for fut in as_completed(futures):
                    task = futures[fut]
                    r = fut.result()
                    completed.append(r)
                    count = r["explicit_edges"] if r["task_kind"] == "explicit" else r["portal_edges"]
                    print(
                        f"  {r['task_kind']}:{r['direction']} "
                        f"{count:,} records in {r['seconds']:.1f}s",
                        flush=True,
                    )

        results = sorted(
            (r for r in completed if r["task_kind"] == "explicit"),
            key=lambda r: [d[0] for d in DIRECTIONS].index(r["direction"]),
        )
        portal_results = sorted(
            (r for r in completed if r["task_kind"] == "portal"),
            key=lambda r: [d[0] for d in PORTAL_DIRECTIONS].index(r["direction"]),
        )

        meta = {
            "schema_version": 3,
            "representation": (
                "hybrid layered-surface graph overlay: vertical interval floor candidates "
                "are explicit nodes; ordinary base-grid adjacency remains implicit"
            ),
            "source_intervals": str(interval_path),
            "source_heightmap": str(height_dir),
            "node_id_semantics": (
                "node id equals floor interval index in vertical_intervals.npz"
            ),
            "grid": {
                "step_m": step_m,
                "width": width,
                "height": height,
                "east0_m": east0_m,
                "north0_m": north0_m,
            },
            "node_count": int(len(floor_z)),
            "exception_column_count": int(len(cells)),
            "ordinary_base_graph": (
                "implicit 8-neighbor heightfield; not duplicated in edge shards"
            ),
            "candidate_edge_policy": {
                "max_neighbor_dz_m": args.max_dz_m,
                "base_seam_max_grade": args.base_seam_max_grade,
                "cross_component_seam_max_grade": args.cross_component_seam_max_grade,
                "ambiguous_seam_max_grade": args.ambiguous_seam_max_grade,
                "different_positive_components": (
                    "allowed only across a local geometric seam; route solver penalizes "
                    "relation 2 so same-component continuity is preferred"
                ),
                "max_neighbors_per_node_each_direction": args.max_neighbors_per_node,
                "component_relation_codes": {
                    "0": "same component",
                    "1": "component-0 base to/from placed component seam",
                    "2": "different positive connected components across an allowed geometric seam",
                    "3": "mixed/ambiguous component seam",
                },
                "directions_stored_once_undirected": [d[0] for d in DIRECTIONS],
                "portal_directions": [d[0] for d in PORTAL_DIRECTIONS],
                "warning": (
                    "candidate geometry only. Movement-mode grade/clearance policy and "
                    "lateral solid-volume validation are downstream."
                ),
            },
            "directions": results,
            "portal_directions": portal_results,
            "totals": {
                "explicit_edges": int(sum(r["explicit_edges"] for r in results)),
                "portal_edges": int(sum(r["portal_edges"] for r in portal_results)),
                "edge_shards": int(sum(len(r["edge_shards"]) for r in results)),
                "portal_shards": int(sum(len(r["portal_shards"]) for r in portal_results)),
            },
            "workers": workers,
            "parallel_strategy": "independent direction builds use worker processes; each worker loads read-only spatial arrays locally",
            "seconds": round(time.time() - started, 1),
            "known_limitations": [
                "mixed same-Z event contributors are represented as component -1 and use a tighter seam tolerance",
                "lateral solid-volume/vehicle-envelope collision is not yet validated",
                "ordinary terrain edges are implicit and must be combined by the route consumer",
            ],
        }
        (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(
        f"surface graph complete: {meta['node_count']:,} explicit surface nodes, "
        f"{meta['totals']['explicit_edges']:,} explicit edges, "
        f"{meta['totals']['portal_edges']:,} portals in {meta['seconds']:.1f}s"
    )
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
