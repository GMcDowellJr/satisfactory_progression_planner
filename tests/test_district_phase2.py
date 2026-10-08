"""The Phase 2 reference district (tools/phases/district_phase2.py), pinned.

Crossover A26.1 C2: the v5.5 Stage 0 fixture lives here as a declaration,
composed by tools/district_run.py. Both extraction-clock cases are inputs
(A27.1 K1), so both are pinned; the caps and the plan scale by exactly 4
between them, which is the linearity the LP owes and the test states rather
than assumes.

Measured in the agent container 2026-10-08, scenario 1.25x recipe / 5x
machine power, LpBackend MEAN, goal "balanced" as the tie-break:

    shipped (100 %)   VF 2.6572  Motor 2.6316  EIB 3.7500   weighted 9.0387
                      every declared cap binds; LP power 1337.88 MW
    readme  (25 %)    VF 0.6643  Motor 0.6579  EIB 0.9375   weighted 2.2597
    baseline          v5.4.4's shipped portfolio as demands, uncapped: coal
                      262.75 (cap 240), limestone 150.4 (cap 120), copper
                      20.58 (cap 0: the district has none); ONE Solid Steel
                      Ingot flow of 4.379 foundries where the PWA built five

The shadow prices are the same in both cases: the LP is homogeneous in the
caps, so the marginal value of a unit of each resource does not depend on
the clock.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("district_run", REPO / "tools" / "district_run.py")
district_run = sys.modules.get("district_run") or importlib.util.module_from_spec(_spec)
if "district_run" not in sys.modules:
    sys.modules["district_run"] = district_run
    _spec.loader.exec_module(district_run)

from production_adapter import load  # noqa: E402

DECL = district_run.declaration("district_phase2")
I = DECL.I
STEEL_SOLID = "Recipe_Alternate_IngotSteel_1_C"
ALTERNATES = {
    "Recipe_Alternate_Wire_1_C",                 # Iron Wire
    "Recipe_Alternate_ReinforcedIronPlate_2_C",  # Stitched Iron Plate
    STEEL_SOLID,                                 # Solid Steel Ingot
    "Recipe_Alternate_Stator_C",                 # Quickwire Stator
    "Recipe_Alternate_Rotor_C",                  # Steel Rotor
}


@pytest.fixture(scope="module")
def shipped():
    return district_run.run(DECL, case="shipped", baseline=True)


@pytest.fixture(scope="module")
def readme():
    return district_run.run(DECL, case="readme")


def _rates(dr):
    return {t.item_id: t.rate_per_min for t in dr.response.targets}


def _raw(response):
    return {r.item_id: r.rate_per_min for r in response.raw_inputs}


# --- the declaration composes -------------------------------------------

def test_caps_compose_from_extraction_rates_both_cases(shipped, readme):
    declared = {c.item_id: c.rate_per_min for c in shipped.caps[:4]}
    assert declared == {I["ORE"]: 360.0, I["COAL"]: 240.0, I["STONE"]: 120.0, I["GOLD"]: 60.0}
    assert [c.item_id for c in shipped.caps[:4]] == [I["ORE"], I["COAL"], I["STONE"], I["GOLD"]]
    declared = {c.item_id: c.rate_per_min for c in readme.caps[:4]}
    assert declared == {I["ORE"]: 90.0, I["COAL"]: 60.0, I["STONE"]: 30.0, I["GOLD"]: 15.0}


def test_the_district_is_closed(shipped):
    """Every raw resource not declared is capped at 0: 13 resources, 4 declared."""
    assert len(shipped.caps) == 13
    assert all(c.rate_per_min == 0.0 for c in shipped.caps[4:])
    assert "Desc_OreCopper_C" in {c.item_id for c in shipped.caps[4:]}


def test_the_declared_recipe_names_resolve_to_the_built_factory(shipped):
    data = load(REPO)
    from progression import recipe_ids_by_name
    ids = set(recipe_ids_by_name(data, DECL.DECLARED_RECIPE_NAMES))
    assert ALTERNATES <= ids
    assert {"Recipe_IngotCaterium_C", "Recipe_Quickwire_C"} <= ids
    assert ALTERNATES <= set(shipped.recipe_ids)
    assert len(shipped.recipe_ids) == 35


def test_an_unknown_case_is_refused_by_name():
    with pytest.raises(district_run.DistrictRunError, match="no extraction clock case 'mk2'"):
        district_run.run(DECL, case="mk2")


# --- the plan, shipped case ------------------------------------------------

def test_every_target_gets_a_positive_rate_above_its_floor(shipped):
    """v5.5 acceptance "positive rates": nothing is zero because a competitor
    had the higher marginal value (the v5.4.4 defect, Stator 0 / Motor 0)."""
    rates = _rates(shipped)
    assert rates == pytest.approx(
        {I["VF"]: 2.657162, I["MOTOR"]: 2.631579, I["EIB"]: 3.75}, abs=1e-4,
    )
    assert not any(t.at_floor for t in shipped.response.targets)
    assert shipped.response.weighted_output == pytest.approx(9.038741, abs=1e-4)


def test_the_built_factorys_alternates_are_the_ones_in_use(shipped):
    used = {u.recipe_id for u in shipped.response.plan.recipes}
    assert ALTERNATES <= used
    assert "Recipe_IngotSteel_C" not in used   # Solid Steel replaced the base recipe
    assert len(used) == 19


def test_shared_intermediates_are_one_flow_each(shipped):
    """v5.5 acceptance "shared intermediates": one RecipeUse per recipe, and
    the steel for pipes, beams, rotors and frames comes from ONE Solid Steel
    Ingot activity of exactly 4 foundry-equivalents (coal cap 240 / 60 per
    foundry at 1.25x)."""
    uses = {u.recipe_id: u.machine_equivalents for u in shipped.response.plan.recipes}
    assert uses[STEEL_SOLID] == pytest.approx(4.0, abs=1e-6)
    assert len(uses) == len(shipped.response.plan.recipes)


def test_every_declared_cap_binds_and_copper_is_priced(shipped):
    binding = {b.item_id: b for b in shipped.response.binding}
    assert set(binding) == {I["ORE"], I["COAL"], I["STONE"], I["GOLD"], "Desc_OreCopper_C"}
    assert binding[I["STONE"]].shadow_price == pytest.approx(0.018827, abs=1e-5)
    assert binding["Desc_OreCopper_C"].cap_per_min == 0.0
    assert binding["Desc_OreCopper_C"].shadow_price == pytest.approx(0.018892, abs=1e-5)
    assert _raw(shipped.response.plan) == pytest.approx(
        {I["ORE"]: 360.0, I["COAL"]: 240.0, I["STONE"]: 120.0, I["GOLD"]: 60.0}, abs=1e-4,
    )


def test_conservation_holds_on_every_item(shipped):
    """v5.5 acceptance "conservation": production + raw draw = consumption +
    the target's output, within 1e-6, for every item in the ledger."""
    rates = _rates(shipped)
    for flow in shipped.response.plan.items:
        assert flow.net_per_min == pytest.approx(rates.get(flow.item_id, 0.0), abs=1e-6), flow


def test_lp_power_is_machine_time_at_mean_power_not_a_realization(shipped):
    power = shipped.response.plan.power
    assert power.scenario_mw == pytest.approx(1337.8834, abs=1e-3)
    assert power.canonical_mw == pytest.approx(power.scenario_mw / 5.0, abs=1e-6)
    assert any("power excludes extraction" in w for w in shipped.response.plan.warnings)


# --- readme case: the same plan at a quarter ------------------------------

def test_the_readme_case_is_the_shipped_plan_scaled_by_a_quarter(shipped, readme):
    s, r = _rates(shipped), _rates(readme)
    assert r == pytest.approx({k: v / 4.0 for k, v in s.items()}, abs=1e-4)
    assert readme.response.weighted_output == pytest.approx(9.038741 / 4.0, abs=1e-4)
    assert not any(t.at_floor for t in readme.response.targets)
    assert {b.item_id: b.shadow_price for b in readme.response.binding} == pytest.approx(
        {b.item_id: b.shadow_price for b in shipped.response.binding}, abs=1e-6,
    )


def test_floors_too_high_for_the_readme_case_are_refused_with_the_scale():
    """Measured on the way to the declared floors: 1 / 1 / 0.5 fit together
    only to 0.7555 of their values, coal and caterium binding."""
    from production_adapter import DistrictRequest, DistrictTarget
    from production_adapter.lp_backend import Infeasible, LpBackend, PowerStatistic
    base = district_run.run(DECL, case="readme")
    request = DistrictRequest(
        targets=(DistrictTarget(I["VF"], minimum_rate=1.0), DistrictTarget(I["MOTOR"], minimum_rate=1.0),
                 DistrictTarget(I["EIB"], minimum_rate=0.5)),
        allowed_recipes=base.request.allowed_recipes, resource_caps=base.caps,
    )
    with pytest.raises(Infeasible) as e:
        LpBackend(PowerStatistic.MEAN).solve_district(request, load(REPO, DECL.SCENARIO))
    assert "0.7555" in str(e.value)
    assert "Desc_Coal_C" in str(e.value) and "Desc_OreGold_C" in str(e.value)


# --- Stage 0 baseline row ---------------------------------------------------

def test_baseline_v544_portfolio_overdraws_three_resources(shipped):
    """The PWA's own shipped portfolio, as demands under the built factory's
    recipe set: coal and limestone exceed the caps and it draws copper the
    district does not have. The PWA reported it feasible because each product
    was costed alone and copper was never capped."""
    assert shipped.baseline_error is None
    raw = _raw(shipped.baseline)
    assert raw == pytest.approx({
        I["COAL"]: 262.75, I["STONE"]: 150.4, "Desc_OreCopper_C": 20.583333,
        I["ORE"]: 276.408334, I["GOLD"]: 48.0,
    }, abs=1e-4)
    over = [c.item_id for c in shipped.caps if raw.get(c.item_id, 0.0) > c.rate_per_min + 1e-6]
    assert over == [I["COAL"], I["STONE"], "Desc_OreCopper_C"]


def test_baseline_makes_steel_once(shipped):
    """Five Solid Steel Ingot banks in the PWA (one per product, measured
    2026-10-08, 124 machines in all); one activity here."""
    uses = {u.recipe_id: u.machine_equivalents for u in shipped.baseline.recipes}
    assert uses[STEEL_SOLID] == pytest.approx(4.379167, abs=1e-5)
    assert len(uses) == 16
    assert shipped.baseline.power.scenario_mw == pytest.approx(921.1306, abs=1e-3)


# --- export (A27.3) ----------------------------------------------------------

def test_export_is_one_lf_json_document_with_the_plan_and_its_inputs(shipped, tmp_path):
    data = load(REPO, DECL.SCENARIO)
    path = tmp_path / "district.json"
    district_run.export(shipped, data, path)
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    doc = json.loads(raw)
    assert doc["schema"] == district_run.EXPORT_SCHEMA
    assert doc["case"] == "shipped"
    assert doc["scenario"]["recipe_input_multiplier"] == 1.25
    assert doc["scenario"]["machine_power_multiplier"] == 5.0
    assert [n["item_id"] for n in doc["district"]["nodes"]] == [I["ORE"], I["COAL"], I["STONE"], I["GOLD"]]
    assert len(doc["district"]["caps"]) == 13
    assert doc["goal"] == {"name": "balanced", "resources": 1.0, "power": 1.0, "buildings": 1.0, "complexity": 0.0}
    assert [t["item_id"] for t in doc["targets"]] == [I["VF"], I["MOTOR"], I["EIB"]]
    assert doc["weighted_output"] == pytest.approx(9.038741, abs=1e-4)
    assert {b["item_id"] for b in doc["binding"]} >= {I["COAL"], I["ORE"]}
    assert len(doc["plan"]["recipes"]) == 19
    assert doc["baseline"] is not None and len(doc["baseline"]["recipes"]) == 16
    assert doc["unverified"] == list(district_run.UNVERIFIED)


# --- guardrails ------------------------------------------------------------

def _called_names(tree):
    return {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def test_the_joint_cannot_choose():
    """No min, max or sort in district_run: targets print in request order,
    caps in declaration order, and the goal is a named argument whose weights
    are printed (LP record 21 R2)."""
    tree = ast.parse(inspect.getsource(district_run))
    assert {"min", "max", "sorted", "sort"}.isdisjoint(_called_names(tree))


def test_the_declaration_is_data():
    """No function definitions and no calls other than constructors: a phase
    declaration computes nothing (A22)."""
    tree = ast.parse(pathlib.Path(DECL.__file__).read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    assert _called_names(tree) <= {"dict", "NodeCount", "DistrictTarget", "Scenario"}
