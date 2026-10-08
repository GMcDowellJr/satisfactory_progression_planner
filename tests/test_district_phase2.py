"""The Phase 2 reference district (tools/phases/district_phase2.py), pinned.

Crossover A26.1 C2: the v5.5 Stage 0 fixture lives here as a declaration,
composed by tools/district_run.py. Rulings in force: A27 (both clocks are
inputs), A31 (the bill supplies the proportions), A34 (every makeable bill
item is a target unless excluded; one recipe per bus, the solve's recipe
set read from the partition), A35 (the question is what fits on the 300 MW
of the 4 standing coal generators, whose coal and water are OUTSIDE the
district's materials; power in the solve by default, no new generators).

Measured in the agent container 2026-10-08, scenario 1.25x recipe / 5x
machine power, LpBackend MEAN, goal "balanced" as the tie-break. Bill =
Project Assembly phase 2 + schematic costs of tiers 3, 4, 5: 18 items, 15
makeable here, all targets.

    on 300 MW (default)   lanes held to 235 MW (300 - 35 extraction - 30
                          spare): scale 0.000386 /min, horizon 2589.7 min;
                          iron 68 of 360; 24 whole machines (9 Asm, 10 Con,
                          1 Fdy, 4 Sml), 174.41 MW realized. The 25 % case
                          gives the SAME plan: power binds, no cap does, so
                          the miners' clock does not enter
    --power report        the unconstrained draw: scale 0.002031, horizon
                          492.4 min; iron binds; 54 machines; 1140.20 MW
                          realized + 35 extraction against 300 MW standing:
                          SHORT by 875.20 MW
    baseline              v5.4.4's shipped portfolio as demands under the
                          partition's recipes, uncapped: coal 238.75,
                          limestone 150.4 (cap 120), caterium 48; ONE Solid
                          Steel Ingot flow of 3.979

Concrete takes spare limestone beyond its share only when caps bind
(report mode: A34.3 O41); on 300 MW every item sits at the scale.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import pathlib
import sys
import types

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
ALTERNATES_IN_PARTITION = {
    "Recipe_Alternate_Wire_1_C",                 # Iron Wire
    "Recipe_Alternate_ReinforcedIronPlate_2_C",  # Stitched Iron Plate
    STEEL_SOLID,                                 # Solid Steel Ingot
    "Recipe_Alternate_Stator_C",                 # Quickwire Stator
}
COPPER = "Desc_OreCopper_C"


def _decl(**over):
    ns = types.SimpleNamespace(**{k: getattr(DECL, k) for k in dir(DECL) if not k.startswith("__")})
    for k, v in over.items():
        setattr(ns, k, v)
    return ns


@pytest.fixture(scope="module")
def shipped():
    """The default: what fits on 300 MW."""
    return district_run.run(DECL, case="shipped")


@pytest.fixture(scope="module")
def readme():
    return district_run.run(DECL, case="readme")


@pytest.fixture(scope="module")
def shipped_report():
    """The unconstrained draw, stated against the standing supply."""
    return district_run.run(DECL, case="shipped", power="report", baseline=True)


def _rates(dr):
    return {t.item_id: t.rate_per_min for t in dr.response.targets}


def _raw(response):
    return {r.item_id: r.rate_per_min for r in response.raw_inputs}


def _machines(dr):
    counts: dict[str, int] = {}
    for bus in dr.realization.buses:
        for lane in bus.lanes:
            counts[lane.producer_class] = counts.get(lane.producer_class, 0) + lane.machines
    return counts


def _lanes(dr, bus_id):
    [bus] = [b for b in dr.realization.buses if b.bus_id == bus_id]
    return bus.lanes


# --- the declaration composes -------------------------------------------

def test_caps_compose_from_extraction_rates_both_cases(shipped, readme):
    caps = {c.item_id: c.rate_per_min for c in shipped.caps[:4]}
    assert caps == {I["ORE"]: 360.0, I["COAL"]: 240.0, I["STONE"]: 120.0, I["GOLD"]: 60.0}
    caps = {c.item_id: c.rate_per_min for c in readme.caps[:4]}
    assert caps == {I["ORE"]: 90.0, I["COAL"]: 60.0, I["STONE"]: 30.0, I["GOLD"]: 15.0}


def test_the_power_plant_is_outside_the_districts_materials(shipped):
    """A35 G2: 4 coal generators, 300 MW; their 60 coal + 180 water are not
    off the caps (STANDING_FED_FROM_DISTRICT False), the water extractors are
    not district nodes, extraction at nameplate is the 7 miners' 35 MW."""
    st = shipped.standing
    assert st.mw == 300.0 and dict(st.draws) == {I["COAL"]: 60.0, I["WATER"]: 180.0}
    assert DECL.STANDING_FED_FROM_DISTRICT is False
    assert shipped.caps == shipped.gross_caps
    assert len(DECL.NODES) == 4 and shipped.extraction_mw == 35.0


def test_the_district_is_closed(shipped):
    assert len(shipped.caps) == 13
    assert all(c.rate_per_min == 0.0 for c in shipped.caps[4:])
    assert COPPER in {c.item_id for c in shipped.caps[4:]}
    assert I["WATER"] in {c.item_id for c in shipped.caps[4:]}


def test_the_recipe_set_is_the_partitions_one_per_item(shipped):
    """A34 E3: 21 buses, 21 recipes, each granted by tier 4 plus the declared
    unlocks; the built factory's alternates among them; Steel Rotor absent."""
    assert len(DECL.BUSES) == 21 and len(shipped.recipe_ids) == 21
    assert set(shipped.recipe_ids) == {b.recipe_id for b in DECL.BUSES}
    assert ALTERNATES_IN_PARTITION <= set(shipped.recipe_ids)
    assert "Recipe_Alternate_Rotor_C" not in shipped.recipe_ids
    assert shipped.request.allowed_recipes.recipe_ids == shipped.recipe_ids


def test_a_partition_recipe_the_tier_does_not_grant_is_refused():
    with pytest.raises(district_run.DistrictRunError, match="do not grant") as e:
        district_run.run(_decl(DECLARED_RECIPE_NAMES=()), case="shipped", realization=False)
    assert STEEL_SOLID in str(e.value)


def test_an_unknown_case_is_refused_by_name():
    with pytest.raises(district_run.DistrictRunError, match="no extraction clock case 'mk2'"):
        district_run.run(DECL, case="mk2")


# --- the bill and discovery (A31, A33, A34) -------------------------------------

def test_the_bill_is_composed_from_phase_2_and_tiers_3_to_5(shipped):
    assert len(shipped.bill) == 18
    assert shipped.bill[I["VF"]] == 1000.0
    assert shipped.bill[I["MOTOR"]] == 200.0
    assert shipped.bill[I["EIB"]] == 600.0
    assert shipped.bill[I["SP"]] == 1000.0


def test_discovery_lists_what_the_site_can_make_of_the_bill(shipped, readme):
    """15 of 18 on iron, coal, limestone and caterium: Copper Sheet, Plastic
    and Rubber have no recipe in the partition. Independent of the clock."""
    reach = {x.item_id: x for x in shipped.reach}
    assert len(reach) == 18 and sum(1 for x in reach.values() if x.makeable) == 15
    assert all(reach[i].no_recipe for i in ("Desc_CopperSheet_C", "Desc_Plastic_C", "Desc_Rubber_C"))
    assert [x.item_id for x in shipped.reach] == list(shipped.bill)   # bill order
    assert sum(1 for x in readme.reach if x.makeable) == 15


def test_every_makeable_bill_item_is_a_target_unless_excluded(shipped):
    """A34 E1: 15 targets, bill order, weight 1, their bill units; none excluded."""
    targets = shipped.request.targets
    assert len(targets) == 15 and all(t.is_bill and t.weight == 1.0 for t in targets)
    assert [t.item_id for t in targets][:3] == [I["SP"], I["VF"], I["AW"]]
    assert targets[-1].item_id == I["MOTOR"] and targets[-1].bill_units == 200.0


def test_an_exclusion_removes_a_target_and_a_stray_exclusion_is_refused():
    dr = district_run.run(_decl(BILL_EXCLUDED=(I["MOTOR"],)), case="shipped", realization=False)
    assert I["MOTOR"] not in {t.item_id for t in dr.request.targets}
    assert len(dr.request.targets) == 14
    with pytest.raises(district_run.DistrictRunError, match="not in the bill"):
        district_run.run(_decl(BILL_EXCLUDED=("Desc_Plastic_C", "Desc_Nope_C")), case="shipped", realization=False)


# --- the plan on 300 MW (A35, the default) ------------------------------------

def test_what_fits_on_300_mw(shipped):
    """Lanes held to 235 MW; every bill product at the scale; no cap binds."""
    r = shipped.response
    assert shipped.power_mode == "solve"
    assert r.scale == pytest.approx(0.00038615, abs=1e-7)
    assert r.horizon_min == pytest.approx(2589.686, abs=1e-2)
    rates = _rates(shipped)
    assert rates[I["SP"]] == pytest.approx(0.386146, abs=1e-5)
    assert rates[I["VF"]] == pytest.approx(0.386146, abs=1e-5)
    assert rates[I["MOTOR"]] == pytest.approx(0.077229, abs=1e-5)
    # at the scale within a part in a thousand: the spare-capacity stage lifts
    # one share by 1e-7 where a lane has a sliver of room
    assert [t.share for t in r.targets] == pytest.approx([r.scale] * 15, rel=1e-3)
    assert r.weighted_output == pytest.approx(0.81684, abs=1e-4)
    assert r.binding == ()
    pw = r.power
    assert pw.grid_mw == 300.0 and pw.spare_mw == 30.0 and pw.extraction_mw == 35.0
    assert pw.generators == () and pw.binding
    assert pw.lane_mw == pytest.approx(235.0, abs=1e-6)
    assert _raw(r.plan) == pytest.approx(
        {I["ORE"]: 68.4506, I["COAL"]: 23.0529, I["STONE"]: 10.5032, I["GOLD"]: 2.0543}, abs=1e-3,
    )


def test_on_300_mw_the_miners_clock_does_not_enter(shipped, readme):
    """Power binds and no cap does, so the 25 % case gives the same plan."""
    assert _rates(readme) == pytest.approx(_rates(shipped), abs=1e-6)
    assert readme.response.scale == pytest.approx(shipped.response.scale, abs=1e-9)
    assert _machines(readme) == _machines(shipped)


def test_conservation_holds_on_every_item(shipped):
    rates = _rates(shipped)
    for flow in shipped.response.plan.items:
        assert flow.net_per_min == pytest.approx(rates.get(flow.item_id, 0.0), abs=1e-6), flow


# --- the unconstrained draw (--power report) ------------------------------------

def test_the_unconstrained_draw_is_stated_against_the_standing_supply(shipped_report):
    r = shipped_report.response
    assert shipped_report.power_mode == "report" and r.power is None
    assert r.scale == pytest.approx(0.00203085, abs=1e-7)
    assert r.horizon_min == pytest.approx(492.404, abs=1e-2)
    binding = {b.item_id: b for b in r.binding}
    assert I["ORE"] in binding and binding[I["ORE"]].shadow_price == pytest.approx(5.641e-6, rel=1e-2)
    assert _raw(r.plan) == pytest.approx(
        {I["ORE"]: 360.0, I["COAL"]: 121.242, I["STONE"]: 120.0, I["GOLD"]: 10.8041}, abs=1e-3,
    )
    # concrete takes the spare limestone beyond its share (O41)
    [concrete] = [t for t in r.targets if t.item_id == I["CON"]]
    assert concrete.share == pytest.approx(0.0101260, abs=1e-6)
    lp = r.plan.power.scenario_mw
    rz = shipped_report.realization.total_power_mw
    assert lp == pytest.approx(1257.5163, abs=1e-3)
    assert rz == pytest.approx(1140.2006, abs=1e-3)
    assert sum(_machines(shipped_report).values()) == 54
    text = district_run.report(shipped_report, load(REPO, DECL.SCENARIO))
    assert "SHORT by 875.20 MW" in text


# --- realization (A32) ---------------------------------------------------------

def test_realization_reproduces_the_plans_rates_bus_by_bus(shipped):
    """Lane output equals the solve's rate for a target, the consumers' draw
    for an intermediate; the residual is idle headroom (BACK_UP)."""
    rz = shipped.realization
    assert len(rz.buses) == 21
    targets = _rates(shipped)
    for bus in rz.buses:
        out = sum(l.output_rate_per_min for l in bus.lanes)
        if bus.item_id in targets:
            # a bill product that is also an intermediate exports its rate on
            # top of what its consumers draw
            assert out == pytest.approx(targets[bus.item_id] + bus.automated_demand_per_min, abs=1e-4), bus.bus_id
        else:
            assert out == pytest.approx(bus.automated_demand_per_min, abs=1e-4), bus.bus_id
        assert bus.residual.disposition.name == "BACK_UP"


def test_realization_sizes_whole_machines_at_explicit_clocks(shipped):
    assert _machines(shipped) == {"Build_AssemblerMk1_C": 9, "Build_ConstructorMk1_C": 10,
                                  "Build_FoundryMk1_C": 1, "Build_SmelterMk1_C": 4}
    assert shipped.realization.total_power_mw == pytest.approx(174.4063, abs=1e-3)
    [steel] = _lanes(shipped, "steel_ingot")
    assert steel.machines == 1 and steel.recipe_id == STEEL_SOLID
    [vf] = _lanes(shipped, "versatile_framework")
    assert vf.power_mw == pytest.approx(75.0 * (vf.clock_percent / 100.0) ** 1.321929, rel=1e-6)
    assert all(l.clock_percent <= 100.0 + 1e-9 for b in shipped.realization.buses for l in b.lanes)


def test_floors_on_extras_are_refused_with_the_scale_when_too_high():
    """The extras path (A27.2 shape): floors each reachable alone but not
    together are refused with the scale at which they fit and the caps that
    bind there."""
    from production_adapter import DistrictRequest, DistrictTarget
    from production_adapter.lp_backend import Infeasible, LpBackend, PowerStatistic
    base = district_run.run(DECL, case="readme", realization=False)
    request = DistrictRequest(
        targets=(DistrictTarget(I["SP"], minimum_rate=2.0), DistrictTarget(I["RIP"], minimum_rate=3.0)),
        allowed_recipes=base.request.allowed_recipes, resource_caps=base.caps,
    )
    with pytest.raises(Infeasible) as e:
        LpBackend(PowerStatistic.MEAN).solve_district(request, load(REPO, DECL.SCENARIO))
    msg = str(e.value)
    assert "reachable alone but not together" in msg and "fit up to 0." in msg


# --- Stage 0 baseline row ---------------------------------------------------

def test_baseline_v544_portfolio_overdraws_under_the_partitions_recipes(shipped_report):
    assert shipped_report.baseline_error is None
    raw = _raw(shipped_report.baseline)
    assert raw == pytest.approx({I["COAL"]: 238.75, I["STONE"]: 150.4, I["GOLD"]: 48.0,
                                 I["ORE"]: 313.519444}, abs=1e-4)
    over = [c.item_id for c in shipped_report.caps if raw.get(c.item_id, 0.0) > c.rate_per_min + 1e-6]
    assert over == [I["STONE"]]
    uses = {u.recipe_id: u.machine_equivalents for u in shipped_report.baseline.recipes}
    assert uses[STEEL_SOLID] == pytest.approx(3.979167, abs=1e-5)
    assert len(uses) == 16


# --- export (A27.3) ----------------------------------------------------------

def test_export_is_one_lf_json_document_with_the_plan_and_its_inputs(shipped_report, tmp_path):
    data = load(REPO, DECL.SCENARIO)
    path = tmp_path / "district.json"
    district_run.export(shipped_report, data, path)
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    doc = json.loads(raw)
    assert doc["schema"] == district_run.EXPORT_SCHEMA and doc["case"] == "shipped"
    assert doc["power_mode"] == "report" and doc["power"] is None
    assert doc["standing"]["mw"] == 300.0 and doc["extraction_mw"] == 35.0
    assert doc["standing_fed_from_district"] is False
    assert len(doc["gross_caps"]) == 13 and len(doc["district"]["caps"]) == 13
    assert [n["item_id"] for n in doc["district"]["nodes"]] == [I["ORE"], I["COAL"], I["STONE"], I["GOLD"]]
    assert doc["goal"] == {"name": "balanced", "resources": 1.0, "power": 1.0, "buildings": 1.0, "complexity": 0.0}
    assert doc["bill"]["phases"] == [2] and doc["bill"]["tiers"] == [3, 4, 5]
    assert doc["bill"]["scale"] == pytest.approx(0.00203085, abs=1e-7)
    assert len(doc["targets"]) == 15
    assert sum(1 for x in doc["discovery"] if x["makeable"]) == 15
    assert len(doc["plan"]["recipes"]) == 21 and len(doc["recipe_ids"]) == 21
    assert doc["baseline"] is not None and len(doc["baseline"]["recipes"]) == 16
    assert len(doc["realization"]["buses"]) == 21 and doc["realization"]["design_tier"] == 4
    assert doc["unverified"] == list(district_run.UNVERIFIED)


# --- guardrails ------------------------------------------------------------

def _called_names(tree):
    return {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def test_the_joint_cannot_choose():
    tree = ast.parse(inspect.getsource(district_run))
    assert {"min", "max", "sorted", "sort"}.isdisjoint(_called_names(tree))


def test_the_declaration_is_data():
    tree = ast.parse(pathlib.Path(DECL.__file__).read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    assert _called_names(tree) <= {"dict", "NodeCount", "DistrictTarget", "Scenario", "B", "S"}
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
