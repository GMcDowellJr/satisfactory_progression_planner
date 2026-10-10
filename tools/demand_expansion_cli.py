"""Demand expansion: reference outputs and inspection (plan package 05).

A joint above `production_adapter` and `demand_expansion`, at tools/ root like
`goal_run.py`. The package produces rows and text and opens no file; this
CLI loads the reference layer, runs one configuration, and writes:

    dependency_coefficients.csv   dataset A: source x target, per unit, depth
    phase_demand.csv              dataset B: item x phase, incremental and views
    unresolved.csv                refused targets and deliveries, by name
    provenance.json               build, route table hash, scenario, counts
    dataset.json                  the three tables and the provenance, in one
    report.md                     compact Markdown

    python tools/demand_expansion_cli.py generate
    python tools/demand_expansion_cli.py generate --recipe-multiplier 1.25 --project-assembly-multiplier 2
    python tools/demand_expansion_cli.py item Motor
    python tools/demand_expansion_cli.py target "Thermal Propulsion Rocket" --recipe-multiplier 1.25

Outputs go under planning_data/analysis/derived/demand_expansion/<config>/,
which is gitignored and outside the manifests: a recomputable product of a
named script over canonical inputs. Every writer pins LF
(tests/test_writers_emit_lf.py).
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _src in ("production_adapter", "demand_expansion"):
    _path = str(REPO / "tools" / _src / "src")
    if _path not in sys.path:
        sys.path.insert(0, _path)

from production_adapter import Scenario, load, load_game_build, load_project_assembly  # noqa: E402
from production_adapter.scenario import FLUID_ROUNDING_VARIANTS  # noqa: E402
import demand_expansion as de  # noqa: E402

DERIVED = REPO / "planning_data" / "analysis" / "derived" / "demand_expansion"
_FLUID_CHOICES = {"mL": "mL", "m3": "m3", "none": None}


def _scenario_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--recipe-multiplier", type=float, default=1.0,
                   help="recipe cost multiplier, applied per cycle and rounded (record 3.2.5)")
    p.add_argument("--project-assembly-multiplier", type=float, default=1.0,
                   help="Space Elevator delivery multiplier, applied in phase aggregation")
    p.add_argument("--fluid-rounding", choices=sorted(_FLUID_CHOICES), default="mL",
                   help='fluid rounding variant; "mL" is the observed rule (A2), '
                        '"m3" reproduces pre-2026-10-10 figures')
    p.add_argument("--repo", type=pathlib.Path, default=REPO, help=argparse.SUPPRESS)


def _scenario(args) -> tuple[Scenario, str | None]:
    unit = _FLUID_CHOICES[args.fluid_rounding]
    assert unit in FLUID_ROUNDING_VARIANTS
    return Scenario(
        recipe_input_multiplier=args.recipe_multiplier,
        project_assembly_requirement_multiplier=args.project_assembly_multiplier,
        fluid_rounding_unit=unit,
    ), unit


def _resolve(data, text: str) -> str:
    """An item id, or a display name matching exactly one item. Refuses
    otherwise, by name (the storage review's display-name warning)."""
    if text in data.items:
        return text
    hits = [i for i, item in data.items.items() if item.display_name == text]
    if len(hits) == 1:
        return hits[0]
    raise SystemExit(
        f"{text!r} matches {len(hits)} items; give an item id (Desc_*_C) or an "
        "exact, unique display name."
    )


def _repo_head(repo: pathlib.Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _write_csv(path: pathlib.Path, rows, columns) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(columns), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _load_all(args):
    data = load(args.repo)
    graph = de.build(data, de.DEFAULT_ROUTES)
    deliveries = load_project_assembly(args.repo, data)
    build = load_game_build(args.repo)
    return data, graph, deliveries, build


def cmd_generate(args) -> int:
    data, graph, deliveries, build = _load_all(args)
    scenario, unit = _scenario(args)
    ds = de.build_dataset(
        graph, deliveries, build, scenario, unit,
        generated_at=_dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
        repo_head=_repo_head(args.repo),
    )
    out = args.out or (DERIVED / ds.config_id.replace("/", "_"))
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "dependency_coefficients.csv", ds.coefficients, de.COEFFICIENT_COLUMNS)
    _write_csv(out / "phase_demand.csv", ds.phases, de.PHASE_COLUMNS)
    _write_csv(out / "unresolved.csv", ds.unresolved, de.UNRESOLVED_COLUMNS)
    (out / "provenance.json").write_text(
        json.dumps(ds.provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (out / "dataset.json").write_text(
        json.dumps({
            "provenance": ds.provenance,
            "dependency_coefficients": list(ds.coefficients),
            "phase_demand": list(ds.phases),
            "unresolved": list(ds.unresolved),
        }, indent=1, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    (out / "report.md").write_text(de.markdown_report(ds, graph), encoding="utf-8", newline="\n")
    c = ds.provenance["counts"]
    print(f"{ds.config_id}: {c['targets']} targets, {c['coefficient_rows']} coefficient rows, "
          f"{c['phase_rows']} phase rows, {c['unresolved']} unresolved -> {out}")
    return 0


def cmd_item(args) -> int:
    """A source part: where it ends up, how much per unit, and its phases."""
    data, graph, deliveries, build = _load_all(args)
    scenario, unit = _scenario(args)
    item = _resolve(data, args.item)
    ds = de.build_dataset(graph, deliveries, build, scenario, unit)
    name = data.items[item].display_name
    print(f"{name} ({item}) under {ds.config_id}\n")
    rows = [r for r in ds.coefficients if r["source_item_id"] == item]
    print(f"Embedded in {len(rows)} targets (per unit of target, depth):")
    for r in rows:
        print(f"  {r['per_target_exact']:>10}  d{r['depth']}  {r['target_name']}"
              + (f"  (direct {r['direct_per_target_exact']})" if r["direct_per_target"] else ""))
    cells = ds.phase_demand.item(item)
    if cells:
        print("\nPhase demand (incremental / cumulative / remaining; + = incomplete phase):")
        for c in cells:
            g = f"{float(c.growth.ratio):.3g}x" if c.growth.kind == "ratio" else c.growth.kind
            print(f"  phase {c.phase}: {str(c.quantity):>10}{'' if c.complete else '+'}"
                  f"  cum {str(c.cumulative):>10}  rem {str(c.remaining):>10}  growth {g}")
    else:
        print("\nNo Project Assembly delivery requires it.")
    if ds.unresolved:
        print(f"\n{len(ds.unresolved)} unresolved (see `generate`): "
              + ", ".join(sorted({u['item_name'] for u in ds.unresolved})))
    return 0


def cmd_target(args) -> int:
    """One target expanded: every item below it, per unit."""
    data, graph, deliveries, build = _load_all(args)
    scenario, unit = _scenario(args)
    target = _resolve(data, args.target)
    try:
        e = de.expand(graph, target, scenario, unit)
    except de.DemandExpansionError as err:
        print(f"refused: {type(err).__name__}: {err}")
        return 2
    print(f"{data.items[target].display_name} ({target}), per unit, "
          f"recipe {scenario.recipe_input_multiplier:g}x, fluid {e.fluid_rounding_unit or 'none'}\n")
    for item_id, q in e.embedded.items():
        nm = data.items[item_id].display_name if item_id in data.items else item_id
        kind = "resource" if graph.is_resource(item_id) else ""
        print(f"  {str(q):>12}  d{e.depth[item_id]}  {nm} {kind}")
    if e.coproducts:
        print("\nCoproducts (reported, not netted):")
        for item_id, q in e.coproducts.items():
            print(f"  {str(q):>12}  {data.items[item_id].display_name}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="demand_expansion_cli.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate", help="write the reference outputs for one configuration")
    g.add_argument("--out", type=pathlib.Path, default=None, help="output directory")
    _scenario_args(g)
    g.set_defaults(fn=cmd_generate)
    i = sub.add_parser("item", help="a source part: destinations and phases")
    i.add_argument("item")
    _scenario_args(i)
    i.set_defaults(fn=cmd_item)
    t = sub.add_parser("target", help="one target, fully expanded per unit")
    t.add_argument("target")
    _scenario_args(t)
    t.set_defaults(fn=cmd_target)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
