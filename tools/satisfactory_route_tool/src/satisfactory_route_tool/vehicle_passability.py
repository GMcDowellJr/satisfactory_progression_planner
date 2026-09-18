from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

import numpy as np

from .heightfield import WorkingField, PROV_CLIFF_VALUES


@dataclass
class VehiclePatch:
    path: Path
    known: np.ndarray
    passable: np.ndarray
    floor_z_m: np.ndarray
    roof_hit: np.ndarray
    measured_clearance_m: np.ndarray
    step_m: float
    east0_m: float
    north0_m: float

    @property
    def shape(self):
        return self.known.shape

    def world_to_rc(self, east_m: float, north_m: float):
        c = int(round((east_m - self.east0_m) / self.step_m))
        r = int(round((self.north0_m - north_m) / self.step_m))
        return r, c


def load_vehicle_patch(path: str | Path) -> VehiclePatch:
    path = Path(path)
    with np.load(path) as d:
        required = {
            "known",
            "passable",
            "floor_z_m",
            "roof_hit",
            "measured_clearance_m",
            "step_m",
            "east0_m",
            "north0_m",
        }
        missing = sorted(required - set(d.files))
        if missing:
            raise ValueError(f"{path} missing patch arrays: {missing}")

        known = np.asarray(d["known"], dtype=bool)
        passable = np.asarray(d["passable"], dtype=bool)
        floor = np.asarray(d["floor_z_m"], dtype=np.float32)
        roof = np.asarray(d["roof_hit"], dtype=bool)
        clearance = np.asarray(d["measured_clearance_m"], dtype=np.float32)
        step = float(np.asarray(d["step_m"]).ravel()[0])
        east0 = float(np.asarray(d["east0_m"]).ravel()[0])
        north0 = float(np.asarray(d["north0_m"]).ravel()[0])

    if not (
        known.shape
        == passable.shape
        == floor.shape
        == roof.shape
        == clearance.shape
    ):
        raise ValueError(f"{path} patch raster shapes do not match")
    if step <= 0:
        raise ValueError(f"{path} has invalid step_m={step}")

    return VehiclePatch(
        path=path,
        known=known,
        passable=passable,
        floor_z_m=floor,
        roof_hit=roof,
        measured_clearance_m=clearance,
        step_m=step,
        east0_m=east0,
        north0_m=north0,
    )


def _clone_field(field: WorkingField) -> WorkingField:
    return WorkingField(
        step_m=float(field.step_m),
        east0_m=float(field.east0_m),
        north0_m=float(field.north0_m),
        z_m=np.array(field.z_m, copy=True),
        prov=np.array(field.prov, copy=True),
        water_q=np.array(field.water_q, copy=True),
        water_depth_m=np.array(field.water_depth_m, copy=True),
    )


def apply_vehicle_patch(
    field: WorkingField,
    patch: VehiclePatch,
    *,
    clear_validated_cliff_penalty: bool = True,
):
    """Apply a raw-geometry passability patch to the implicit base field.

    A patch is authoritative only where patch.known=True:
      * known + passable => implicit-base Z becomes raw Landscape floor Z.
      * known + blocked  => implicit-base state is suppressed (Z=NaN).
      * unknown          => original working field is untouched.

    Explicit multi-surface graph nodes remain available to the normal solver.
    This means the patch corrects/validates the implicit lower surface without
    deleting legitimate upper surfaces.

    Returns (patched_field, stats).
    """
    out = _clone_field(field)

    # Determine the WorkingField rectangle intersecting the patch.
    patch_north = patch.north0_m
    patch_south = patch.north0_m - (patch.shape[0] - 1) * patch.step_m
    patch_west = patch.east0_m
    patch_east = patch.east0_m + (patch.shape[1] - 1) * patch.step_m

    r0, c0 = field.world_to_rc(patch_west, patch_north)
    r1, c1 = field.world_to_rc(patch_east, patch_south)

    rmin = max(0, min(r0, r1) - 1)
    rmax = min(field.shape[0], max(r0, r1) + 2)
    cmin = max(0, min(c0, c1) - 1)
    cmax = min(field.shape[1], max(c0, c1) + 2)

    tested = 0
    passable_count = 0
    blocked_count = 0
    z_changed = 0
    cliff_cleared = 0
    water_recomputed = 0

    cliff_values = set(int(x) for x in PROV_CLIFF_VALUES)

    for r in range(rmin, rmax):
        north = field.north0_m - r * field.step_m
        pr = int(round((patch.north0_m - north) / patch.step_m))
        if pr < 0 or pr >= patch.shape[0]:
            continue

        for c in range(cmin, cmax):
            east = field.east0_m + c * field.step_m
            pc = int(round((east - patch.east0_m) / patch.step_m))
            if pc < 0 or pc >= patch.shape[1]:
                continue
            if not patch.known[pr, pc]:
                continue

            tested += 1
            old_z = float(out.z_m[r, c]) if np.isfinite(out.z_m[r, c]) else math.nan

            if not patch.passable[pr, pc]:
                if np.isfinite(out.z_m[r, c]):
                    z_changed += 1
                out.z_m[r, c] = np.nan
                blocked_count += 1
                continue

            new_z = float(patch.floor_z_m[pr, pc])
            if not math.isfinite(new_z):
                # Defensive: passable without a support floor is inconsistent.
                out.z_m[r, c] = np.nan
                blocked_count += 1
                continue

            passable_count += 1
            if not math.isfinite(old_z) or abs(old_z - new_z) > 1e-4:
                z_changed += 1

            # Preserve measured water level while changing the support floor.
            q = int(out.water_q[r, c])
            if q != 0 and np.isfinite(out.water_depth_m[r, c]) and math.isfinite(old_z):
                water_level = old_z + float(out.water_depth_m[r, c])
                out.water_depth_m[r, c] = max(0.0, water_level - new_z)
                water_recomputed += 1

            out.z_m[r, c] = new_z

            # The raw collision test is stronger vehicle evidence than the
            # composed heightfield's cliff provenance inside this tested cell.
            if clear_validated_cliff_penalty and int(out.prov[r, c]) in cliff_values:
                out.prov[r, c] = 0
                cliff_cleared += 1

    stats = {
        "patch": str(patch.path),
        "tested_field_cells": int(tested),
        "passable_field_cells": int(passable_count),
        "blocked_field_cells": int(blocked_count),
        "z_changed_field_cells": int(z_changed),
        "cliff_penalty_cleared_cells": int(cliff_cleared),
        "water_depth_recomputed_cells": int(water_recomputed),
        "field_bounds_rc": {
            "rmin": int(rmin),
            "rmax": int(rmax),
            "cmin": int(cmin),
            "cmax": int(cmax),
        },
        "patch_world_bounds_m": {
            "west": float(patch_west),
            "east": float(patch_east),
            "south": float(patch_south),
            "north": float(patch_north),
        },
    }
    return out, stats
