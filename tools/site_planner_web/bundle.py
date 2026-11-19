#!/usr/bin/env python3
"""The repo files the in-browser runtime needs: traced, not listed by hand.

The picker's Web Worker (worker.js) runs this repo's Python in Pyodide
(decided by Greg 2026-10-19 16:10; precomputed exports plus in-browser
recompute decided 2026-10-23 15:36, reframe A10). Pyodide sees only the
files the worker copies into its file system, so the worker fetches exactly
the paths in bundle_files.json.

That list is produced by RUNNING the worker's entry points natively in a
fresh interpreter, with an audit hook recording every file opened and every
module imported under the repo:

    neighborhoods.export_for     (recompute, with the v0.20 policy)
    portfolio_run.run_inputs + record   (three runs: a starter site, a
                                 site that pumps Water at tier 6, so the
                                 generator, Water and alternate paths load,
                                 and the starter under report_need, A11)
    planner_catalog.catalog, tier_milestones, generators_owned, horizons
                                 (the planner page's choices, reframe A20/A21)
    run_plan.storage_timeline    (a storage-priority bank, A21)
    run_plan.run_inputs + record + report (a phase that plans and one that is blocked)
    run_plan.handoff             (that phase to factory-inputs/1)
    factory_run.run_inputs + record + report (the hand-off's document; a declared
                                 power site at tier 4, so the supply check
                                 loads; and the same site in grid mode)

A file a code path reads only under inputs these runs do not reach would be
missing in the browser; the worker then reports the missing path by name
rather than guessing. tests/test_site_planner_web.py re-traces and compares,
so the list cannot drift from the code.

    uv run python tools/site_planner_web/bundle.py           # --check
    uv run python tools/site_planner_web/bundle.py --write
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
LIST = HERE / "bundle_files.json"
POLICY = HERE / "precomputed" / "policy_v020.json"
#: top-level repo directories a bundled file may come from
BUNDLED_ROOTS = ("tools", "planning_data")

#: the runs traced (module docstring): a starter, a Water-pumping tier-6 site, and the
#: starter again under report_need (A11)
_SCENARIO = {"recipe_input_multiplier": 1.0, "machine_power_multiplier": 1.0,
             "project_assembly_requirement_multiplier": 1.0, "input_amount_floor": None,
             "fluid_rounding_unit": "mL"}
_EXTRACTORS = [{"source_kind": "resource_node", "item_id": None, "extractor_class": "Build_MinerMk1_C"},
               {"source_kind": "resource_node", "item_id": "Desc_LiquidOil_C", "extractor_class": "Build_OilPump_C"}]
TRACE_RUNS = (
    {"schema": "portfolio-inputs/2", "world_config_id": "default_502094", "tier": 2, "declared_recipes": [],
     "scenario": _SCENARIO, "goal": "balanced", "bill": {"phases": [1], "tiers": [1, 2]},
     "extraction_clock": 1.0, "extractors": _EXTRACTORS[:1], "power_mode": "grid", "grid_mw": 60.0, "spare_mw": 0.0,
     "sites": [{"label": "starter", "socket_ids": ["BP_ResourceNode103", "BP_ResourceNode106"],
                "pumps_water": False, "supply": []}]},
    {"schema": "portfolio-inputs/2", "world_config_id": "default_502094", "tier": 6, "declared_recipes": [],
     "scenario": _SCENARIO, "goal": "balanced", "bill": {"phases": [3], "tiers": [5, 6]},
     "extraction_clock": 1.0, "extractors": _EXTRACTORS, "power_mode": "grid", "grid_mw": 0.0, "spare_mw": 0.0,
     "sites": [{"label": "oil", "socket_ids": ["BP_ResourceNode98"], "pumps_water": True, "supply": []}]},
    # A11: the report_need path (fuel join reads the unlock tables)
    {"schema": "portfolio-inputs/2", "world_config_id": "default_502094", "tier": 2, "declared_recipes": [],
     "scenario": _SCENARIO, "goal": "balanced", "bill": {"phases": [1], "tiers": [1, 2]},
     "extraction_clock": 1.0, "extractors": _EXTRACTORS[:1], "power_mode": "report_need", "grid_mw": 0.0,
     "spare_mw": 0.0, "sites": [{"label": "starter", "socket_ids": ["BP_ResourceNode103", "BP_ResourceNode106"],
                                "pumps_water": False, "supply": []}]},
)

#: the planner page's runs (reframe A20); sockets are Rocky Desert district A,
#: the tests' declaration (tests/test_factory_run.py), not Greg's
_ROCKY_A = ["BP_ResourceNode153", "BP_ResourceNode109", "BP_ResourceNode108", "BP_ResourceNode105_2463",
            "BP_ResourceNode107", "BP_ResourceNode106", "BP_ResourceNode112", "BP_ResourceNode111_3367",
            "BP_ResourceNode103", "BP_ResourceNode102_2068", "BP_ResourceNode104"]
_FSCENARIO = {"recipe_input_multiplier": 1.0, "machine_power_multiplier": 1.0,
              "project_assembly_requirement_multiplier": 1.0, "fluid_input_floor": None,
              "fluid_rounding_unit": "mL"}
_PT = {"through_tier": 2, "milestones": [], "research": [], "alternates": []}
RUN_TRACES = (
    {"schema": "run-inputs/1", "playthrough": _PT, "scenario": _FSCENARIO, "phase": 1,
     "horizon_min": None, "horizon_fraction": 1.0, "power_statistic": "mean",
     "fuel_byproducts": "power", "standing_generators": {}, "generation_mix": None},
    {"schema": "run-inputs/1", "playthrough": {**_PT, "through_tier": 3}, "scenario": _FSCENARIO,
     "phase": 2, "horizon_min": None, "horizon_fraction": 0.25, "power_statistic": "mean",
     "fuel_byproducts": "power", "standing_generators": {}, "generation_mix": None},
)
BANK_TRACE = {"name": "plates", "storage_item": "Desc_IronPlate_C", "feed_per_min": 120.0,
              "bank_intake_per_min": 60.0, "bank_output_per_min": 40.0,
              "container_class": "Desc_StorageContainerMk1_C", "container_count": 1,
              "pa_items": ["Desc_SpaceElevatorPart_1_C"], "splitter": "smart", "standard_share": None}
HANDOFF_TRACE = {"world_config_id": "default_502094", "label": "rocky", "socket_ids": _ROCKY_A,
                 "supply": [], "pumps_water": False, "power_mode": "report_need",
                 "power_statistic": "mean", "fuel_byproducts": "power", "power_from_site": False,
                 "goal": "balanced", "grid_mw": 0.0, "spare_mw": 0.0,
                 "infrastructure_policy": "highest_then_step_down", "fixed_rate": True}
_FACTORY = {"schema": "factory-inputs/1", "world_config_id": "default_502094",
            "playthrough": {**_PT, "through_tier": 4}, "scenario": _FSCENARIO,
            "site": {"label": "rocky", "socket_ids": _ROCKY_A,
                     "supply": [{"item_id": "Desc_Coal_C", "rate_per_min": 1000.0}], "pumps_water": False},
            "goal_mix": [{"item_id": "Desc_IronPlateReinforced_C", "units": 1},
                         {"item_id": "Desc_Rotor_C", "units": 1}],
            "goal": "balanced", "power_mode": "report_need", "power_statistic": "mean",
            "grid_mw": 0.0, "spare_mw": 0.0, "target_scale": None,
            "infrastructure_policy": "highest_then_step_down", "fuel_byproducts": "power",
            "standing_generators": {}, "generation_mix": None, "power_from_site": True}
FACTORY_TRACES = (_FACTORY, {**_FACTORY, "power_mode": "grid", "grid_mw": 10000.0,
                             "power_from_site": False})


def _trace() -> list[str]:
    """Run in THIS interpreter (call it fresh): hook first, imports after."""
    seen: set[str] = set()
    root = str(REPO) + os.sep

    def hook(event, args):
        if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
            p = os.path.abspath(os.fsdecode(args[0]))
            if p.startswith(root) and os.path.isfile(p):
                seen.add(p)

    sys.addaudithook(hook)
    sys.path[:0] = [str(REPO / "tools")] + [str(REPO / "tools" / s / "src")
                                             for s in ("production_adapter", "progression", "realization")]
    import factory_run  # noqa: E402
    import neighborhoods  # noqa: E402
    import planner_catalog  # noqa: E402
    import portfolio_run  # noqa: E402
    import run_plan  # noqa: E402
    from production_adapter import load  # noqa: E402

    with open(POLICY, encoding="utf-8") as f:
        neighborhoods.export_for(json.load(f), "default_502094", REPO)
    for doc in TRACE_RUNS:
        pr, scenario = portfolio_run.run_inputs(doc, REPO)
        portfolio_run.record(pr, load(REPO, scenario), None, doc)
    planner_catalog.catalog(REPO)
    planner_catalog.tier_milestones(REPO, 2)
    planner_catalog.generators_owned(REPO, _FACTORY["playthrough"])
    planner_catalog.horizons(REPO, _FSCENARIO)
    run_plan.storage_timeline(run_plan.run_inputs(RUN_TRACES[0], REPO), [BANK_TRACE], REPO)
    for doc in RUN_TRACES:
        plan = run_plan.run_inputs(doc, REPO)
        run_plan.record(plan), run_plan.report(plan)
    for doc in (run_plan.handoff(RUN_TRACES[0], HANDOFF_TRACE, REPO),) + FACTORY_TRACES:
        run = factory_run.run_inputs(doc, REPO)
        factory_run.record(run), factory_run.report(run)
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if f and os.path.abspath(f).startswith(root):
            seen.add(os.path.abspath(f))
    seen.discard(str(POLICY))  # the policy is the worker's input, not a bundle file
    seen.discard(str(pathlib.Path(__file__).resolve()))  # this tracer, run as __main__
    rel = {pathlib.Path(p).relative_to(REPO).as_posix() for p in seen}
    # repo content only: a uv .venv inside the repo holds numpy/scipy, which
    # Pyodide supplies itself; compiled caches are the interpreter's
    return sorted(r for r in rel if r.split("/")[0] in BUNDLED_ROOTS
                  and "__pycache__" not in r and not r.endswith(".pyc"))


def traced() -> list[str]:
    """The list, traced in a fresh interpreter (imports already done here
    would not show as opens)."""
    out = subprocess.run([sys.executable, str(pathlib.Path(__file__)), "--emit"],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--emit"]:
        print(json.dumps(_trace()))
        return 0
    files = traced()
    if argv == ["--write"]:
        with open(LIST, "w", encoding="utf-8", newline="\n") as f:
            json.dump(files, f, indent=1)
            f.write("\n")
        print(f"wrote {LIST.relative_to(REPO).as_posix()}: {len(files)} files")
        return 0
    if argv not in ([], ["--check"]):
        print("usage: bundle.py [--check | --write]", file=sys.stderr)
        return 2
    with open(LIST, encoding="utf-8") as f:
        committed = json.load(f)
    if committed != files:
        print(f"bundle_files.json is stale: +{sorted(set(files) - set(committed))} "
              f"-{sorted(set(committed) - set(files))}", file=sys.stderr)
        return 1
    print(f"bundle_files.json in sync: {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
