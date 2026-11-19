#!/usr/bin/env python3
"""What the planner page may offer as choices, read through the one loader.

Reframe A20 (2026-11-18): the browser planner (tools/site_planner_web/
planner.html) runs the run and factory tracks in Pyodide. A static page cannot
read the reference layer (one loader, AGENTS.md), so the lists it shows come
from here, through the worker:

    catalog(repo)                every milestone (progression-type schematic),
                                 MAM research and alternate recipe, with names
                                 and tiers; item, recipe and building names; the
                                 Project Assembly phases; and the vocabularies
                                 each declared key accepts (power statistic,
                                 fuel route, policy, goal, power mode, fluid
                                 rounding), each from the module that owns it
    tier_milestones(repo, n)     the milestones "through tier N" means: exactly
                                 playthrough(through_tier=n).milestones (Q2), so
                                 the page's tier button ticks what Python means
    generators_owned(repo, pt)   the generator classes a declared state owns, in
                                 the order obtained (power_stack's own reading),
                                 so standing units and the mix are asked only for
                                 classes the stack will accept

Reframe A21 (decided by Greg, 2026-11-19) adds what the page offers and starts
with: the game's option sets for R, P and E (demand record §3.2.1, Greg's
statement of the custom-settings menu), the horizon presets (his Full Factory
Calculator's 5-100 % chips), the storage containers (timeline.CONTAINER_SLOTS),
and PAGE_DEFAULTS, the values the page is pre-filled with. Those defaults are
the PAGE's (Greg chose pre-filled defaults for it, A21); no Python layer takes
a default from them, and every document the page writes still carries every
key. `horizons` gives each phase's ceiling and the minutes of each preset.

It reads and names; it does not order by preference, rank or pick. Lists are in
the reference layer's order unless a reading owns another (the order obtained).
A joint at tools/ root because it spans production_adapter and progression.
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for sub in ("production_adapter", "progression", "realization"):
    p = str(REPO / "tools" / sub / "src")
    if p not in sys.path:
        sys.path.insert(0, p)
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

from production_adapter import FLUID_ROUNDING_VARIANTS, Scenario, load  # noqa: E402
from production_adapter.gamedata import (  # noqa: E402
    load_building_recipe_rows, load_project_assembly, load_recipe_rows, load_schematic_rows,
)
from production_adapter.lp_backend import PowerStatistic  # noqa: E402
from progression import playthrough  # noqa: E402
from progression.byproducts import FUEL_ROUTES  # noqa: E402
from progression.infrastructure import POLICIES  # noqa: E402
from progression.playthrough import RESEARCH_TYPE  # noqa: E402
from progression.power_stack import generators_in_order_obtained  # noqa: E402
from progression.timeline import CONTAINER_SLOTS, SPLITTERS  # noqa: E402
from progression.unlocks import PROGRESSION_TYPES  # noqa: E402

import factory_run  # noqa: E402
import run_plan  # noqa: E402
import site_card  # noqa: E402

CATALOG_SCHEMA = "planner-catalog/1"

#: Demand record §3.2.1 (Greg, 2026-09-19): the game's custom-settings menus.
RECIPE_INPUT_OPTIONS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
MACHINE_POWER_OPTIONS = (0.25, 0.5, 0.75, 1.0, 2.0, 5.0)
PROJECT_ASSEMBLY_OPTIONS = (0.25, 0.5, 0.75, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0)
#: Greg's Full Factory Calculator chips (reframe A21): fractions of the ceiling
HORIZON_PRESETS = (0.05, 0.1, 0.25, 0.5, 1.0)

_SCENARIO = Scenario()
#: Reframe A21, decided by Greg 2026-11-19: the page starts pre-filled. The
#: values listed in the option he chose (1x, phase 1, 100 % horizon, mean,
#: power) are his; the rest are Claude's reading, reversible: the Scenario's
#: own defaults, milestones through tier 2 (what phase 1's parts need), no
#: standing generators, no mix, and the hand-off as the tests declare it.
PAGE_DEFAULTS = {
    "scenario": {"recipe_input_multiplier": _SCENARIO.recipe_input_multiplier,
                 "machine_power_multiplier": _SCENARIO.machine_power_multiplier,
                 "project_assembly_requirement_multiplier":
                     _SCENARIO.project_assembly_requirement_multiplier,
                 "fluid_input_floor": _SCENARIO.fluid_input_floor,
                 "fluid_rounding_unit": _SCENARIO.fluid_rounding_unit},
    "through_tier": 2,
    "standing_units": 0,
    "generation_mix": None,
    "run": {"phase": 1, "horizon_fraction": 1.0, "power_statistic": "mean",
            "fuel_byproducts": "power"},
    "handoff": {"pumps_water": False, "supply": [], "power_mode": "report_need",
                "grid_mw": 0.0, "spare_mw": 0.0, "power_statistic": "mean",
                "fuel_byproducts": "power", "power_from_site": False, "goal": "balanced",
                "infrastructure_policy": "highest_then_step_down", "goal_source": "run",
                "fixed_rate": True},
    "bank": {"splitter": "smart", "container_count": 1},
}


def catalog(repo: pathlib.Path = REPO) -> dict:
    data = load(repo)
    schematics = load_schematic_rows(repo)
    phases: dict[int, str] = {}
    for r in load_project_assembly(repo, data):
        phases.setdefault(r.phase, r.phase_name)
    buildings = {}
    for b in load_building_recipe_rows(repo):
        if b.building_class.startswith("Desc_"):
            buildings["Build_" + b.building_class[len("Desc_"):]] = b.display_name
    return {
        "schema": CATALOG_SCHEMA,
        "game_build_id": data.game_build_id,
        "milestones": [{"schematic_id": s.schematic_id, "name": s.display_name,
                        "tier": s.tech_tier, "type": s.schematic_type}
                       for s in schematics if s.schematic_type in PROGRESSION_TYPES],
        "research": [{"schematic_id": s.schematic_id, "name": s.display_name, "tier": s.tech_tier}
                     for s in schematics if s.schematic_type == RESEARCH_TYPE],
        "alternates": [{"recipe_id": r.recipe_id, "name": r.display_name}
                       for r in load_recipe_rows(repo) if r.is_alternate],
        "items": {i: x.display_name for i, x in data.items.items()},
        "recipes": {i: r.display_name for i, r in data.recipes.items()},
        "producers": {**buildings, **{c: p.display_name for c, p in data.producers.items()}},
        "phases": [{"phase": n, "name": name} for n, name in phases.items()],
        "power_statistics": [s.value for s in PowerStatistic],
        "fuel_routes": list(FUEL_ROUTES),
        "infrastructure_policies": list(POLICIES),
        "goals": list(site_card.GOALS),
        "power_modes": list(factory_run.POWER_MODES),
        "fluid_rounding_units": list(FLUID_ROUNDING_VARIANTS),
        "scenario_options": {"recipe_input_multiplier": list(RECIPE_INPUT_OPTIONS),
                             "machine_power_multiplier": list(MACHINE_POWER_OPTIONS),
                             "project_assembly_requirement_multiplier":
                                 list(PROJECT_ASSEMBLY_OPTIONS)},
        "horizon_presets": list(HORIZON_PRESETS),
        "splitters": list(SPLITTERS),
        "containers": [{"building_class": c, "name": buildings.get("Build_" + c[len("Desc_"):], c),
                        "slots": n} for c, n in CONTAINER_SLOTS.items()],
        "stackable_items": [i for i, x in data.items.items() if x.form == "solid" and x.stack_size],
        "page_defaults": PAGE_DEFAULTS,
    }


def horizons(repo: pathlib.Path, scenario: dict) -> list[dict]:
    """Each phase's one-machine ceiling and the minutes of each preset under the
    declared scenario (a scenario object as in run-inputs/1)."""
    return run_plan.phase_horizons(repo, Scenario(**scenario), HORIZON_PRESETS)


def tier_milestones(repo: pathlib.Path, tier: int) -> list[str]:
    """Q2's shortcut, as the milestone ids it stands for (refusals as playthrough's)."""
    return list(playthrough(repo, through_tier=tier).milestones)


def generators_owned(repo: pathlib.Path, pt: dict) -> list[dict]:
    """`pt` is a playthrough object as in run-inputs/1 and factory-inputs/1."""
    state = playthrough(repo, through_tier=pt["through_tier"], milestones=pt["milestones"],
                        research=pt["research"], alternates=pt["alternates"])
    return [{"generator_class": c, "obtained_with": name, "tier": tier}
            for c, name, tier in generators_in_order_obtained(repo, state)]
