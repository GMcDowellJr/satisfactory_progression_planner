"""The Phase 2 reference district (tools/phases/district_phase2.py), pinned.

Crossover A26.1 C2: the v5.5 Stage 0 fixture lives here as a declaration,
composed by tools/district_run.py. Both extraction-clock cases are inputs
(A27.1 K1), so both are pinned; the caps and the plan scale by exactly 4
between them, which is the linearity the LP owes and the test states rather
than assumes.

Measured in the agent container 2026-10-08, scenario 1.25x recipe / 5x
machine power, LpBackend MEAN, goal "balanced" as the tie-break. The bill
(A31): Project Assembly phase 2 + schematic costs of tiers 3, 4, 5 -> VF
1000, Motor 200, EIB 600 among the three products made here (18 items in
all). The solve holds that 1000 : 200 : 600 proportion in every case and
reports the scale (bill per minute) and the horizon (minutes to cover it).

Caps only (power outside the solve, --no-power):

    shipped (100 %)   scale 0.004571  horizon 218.75 min
                      VF 4.5714  Motor 0.9143  EIB 2.7429; coal binds;
                      LP power 1181.72 MW
    readme  (25 %)    scale 0.001143  horizon 875.0 min: exactly a quarter
    baseline          v5.4.4's shipped portfolio as demands, uncapped: coal
                      262.75 (cap 240), limestone 150.4 (cap 120), copper
                      20.58 (cap 0: the district has none); ONE Solid Steel
                      Ingot flow of 4.379 foundries where the PWA built five

Power in the solve (A29; 900 MW grid, 30 MW spare, 7 miners + 2 water
extractors at nameplate = 75 MW, coal generators may be built):

    shipped (100 %)   scale 0.003829  horizon 261.15 min
                      VF 3.8292  Motor 0.7658  EIB 2.2975; lanes 989.84 MW;
                      2.598 coal generators burning 38.97 coal + 116.91
                      water; the row binds; coal binds
    readme  (25 %)    identical to caps-only: the grid covers 295.43 MW of
                      lanes with 499.57 MW to spare, no generator built

Under the bill the Rotor is made ONE way in every case (the A30 mix was a
product of equal weights); A30's ruling is still needed for the general
case, but the fixture no longer exercises it.
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
    """Caps only: power outside the solve, with the baseline row."""
    return district_run.run(DECL, case="shipped", baseline=True, power=False)


@pytest.fixture(scope="module")
def readme():
    return district_run.run(DECL, case="readme", power=False)


@pytest.fixture(scope="module")
def shipped_power():
    return district_run.run(DECL, case="shipped")


@pytest.fixture(scope="module")
def readme_power():
    return district_run.run(DECL, case="readme")


def _rates(dr):
    return {t.item_id: t.rate_per_min for t in dr.response.targets}


def _raw(response):
    return {r.item_id: r.rate_per_min for r in response.raw_inputs}


# --- the declaration composes -------------------------------------------

def test_caps_compose_from_extraction_rates_both_cases(shipped, readme):
    declared = {c.item_id: c.rate_per_min for c in shipped.caps[:5]}
    assert declared == {I["ORE"]: 360.0, I["COAL"]: 240.0, I["STONE"]: 120.0, I["GOLD"]: 60.0,
                        I["WATER"]: 240.0}
    assert [c.item_id for c in shipped.caps[:5]] == [I["ORE"], I["COAL"], I["STONE"], I["GOLD"], I["WATER"]]
    declared = {c.item_id: c.rate_per_min for c in readme.caps[:5]}
    assert declared == {I["ORE"]: 90.0, I["COAL"]: 60.0, I["STONE"]: 30.0, I["GOLD"]: 15.0,
                        I["WATER"]: 60.0}


def test_the_district_is_closed(shipped):
    """Every raw resource not declared is capped at 0: 13 resources, 5 declared."""
    assert len(shipped.caps) == 13
    assert all(c.rate_per_min == 0.0 for c in shipped.caps[5:])
    assert "Desc_OreCopper_C" in {c.item_id for c in shipped.caps[5:]}


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


# --- the bill (A31) ----------------------------------------------------------

def test_the_bill_is_composed_from_phase_2_and_tiers_3_to_5(shipped):
    assert len(shipped.bill) == 18
    assert shipped.bill[I["VF"]] == 1000.0
    assert shipped.bill[I["MOTOR"]] == 200.0
    assert shipped.bill[I["EIB"]] == 600.0
    assert shipped.bill["Desc_SpaceElevatorPart_1_C"] == 1000.0   # in the bill, not made here
    assert [(t.item_id, t.bill_units) for t in shipped.request.targets] == [
        (I["VF"], 1000.0), (I["MOTOR"], 200.0), (I["EIB"], 600.0),
    ]


# --- discovery (A31 O34; v5.5 Stage 2) ---------------------------------------

def test_discovery_lists_what_the_site_can_make_of_the_bill(shipped):
    """15 of 18 at tier 4 on iron, coal, limestone, caterium and water: Copper
    Sheet needs a copper node; Plastic and Rubber have no enabled recipe
    (refinery, tier 5). Independent of rates: discovery is not allocation."""
    reach = {x.item_id: x for x in shipped.reach}
    assert len(reach) == 18 and sum(1 for x in reach.values() if x.makeable) == 15
    assert reach["Desc_CopperSheet_C"].missing_raws == ("Desc_OreCopper_C",)
    assert reach["Desc_Plastic_C"].no_recipe and reach["Desc_Rubber_C"].no_recipe
    assert all(reach[i].makeable for i in (I["VF"], I["MOTOR"], I["EIB"], "Desc_SpaceElevatorPart_1_C"))
    assert [x.item_id for x in shipped.reach] == list(shipped.bill)   # bill order


def test_a_bill_target_the_site_cannot_make_is_refused_by_discovery():
    import types
    decl = types.SimpleNamespace(**{k: getattr(DECL, k) for k in dir(DECL) if not k.startswith("__")})
    decl.BILL_TARGETS = DECL.BILL_TARGETS + (("Desc_CopperSheet_C", 1.0),)
    with pytest.raises(district_run.DistrictRunError, match="cannot be made here at all") as e:
        district_run.run(decl, case="shipped", power=False, realization=False)
    assert "Desc_OreCopper_C" in str(e.value)


# --- the plan, shipped case ------------------------------------------------

def test_every_bill_product_gets_its_proportion(shipped):
    """v5.5 acceptance "positive rates", now by need: 1000 : 200 : 600, each
    at the same scale, nothing at zero because a competitor was "worth more"
    (the v5.4.4 defect, Stator 0 / Motor 0)."""
    r = shipped.response
    assert r.scale == pytest.approx(0.004571, abs=1e-6)
    assert r.horizon_min == pytest.approx(218.75, abs=1e-2)
    assert _rates(shipped) == pytest.approx(
        {I["VF"]: 4.571428, I["MOTOR"]: 0.914286, I["EIB"]: 2.742859}, abs=1e-4,
    )
    assert [t.share for t in r.targets] == pytest.approx([r.scale] * 3, abs=1e-6)
    assert r.weighted_output == pytest.approx(3.555556, abs=1e-4)


def test_the_built_factorys_alternates_are_the_ones_in_use(shipped):
    """Four of the five: under the bill the Rotor is made one way, with the
    base recipe, so Steel Rotor is enabled but idle."""
    used = {u.recipe_id for u in shipped.response.plan.recipes}
    assert ALTERNATES - {"Recipe_Alternate_Rotor_C"} <= used
    assert "Recipe_Alternate_Rotor_C" not in used
    assert "Recipe_IngotSteel_C" not in used   # Solid Steel replaced the base recipe
    assert len(used) == 18


def test_shared_intermediates_are_one_flow_each(shipped):
    """v5.5 acceptance "shared intermediates": one RecipeUse per recipe, and
    the steel for pipes, beams, rotors and frames comes from ONE Solid Steel
    Ingot activity of exactly 4 foundry-equivalents (coal cap 240 / 60 per
    foundry at 1.25x)."""
    uses = {u.recipe_id: u.machine_equivalents for u in shipped.response.plan.recipes}
    assert uses[STEEL_SOLID] == pytest.approx(4.0, abs=1e-6)
    assert len(uses) == len(shipped.response.plan.recipes)


def test_coal_binds_and_is_priced_in_scale(shipped):
    """Coal is the one cap that stops the scale: 1.905e-5 scale per coal/min,
    i.e. 240 coal buys 0.004571. Iron sits at its cap with no price (the
    spare-capacity stage used it), copper at 0 with no price."""
    binding = {b.item_id: b for b in shipped.response.binding}
    assert I["COAL"] in binding
    assert binding[I["COAL"]].shadow_price == pytest.approx(1.905e-5, rel=1e-2)
    assert binding[I["COAL"]].shadow_price * 240.0 == pytest.approx(shipped.response.scale, rel=1e-3)
    assert _raw(shipped.response.plan) == pytest.approx(
        {I["ORE"]: 359.872991, I["COAL"]: 240.0, I["STONE"]: 87.77149, I["GOLD"]: 20.84571}, abs=1e-3,
    )


def test_conservation_holds_on_every_item(shipped):
    """v5.5 acceptance "conservation": production + raw draw = consumption +
    the target's output, within 1e-6, for every item in the ledger."""
    rates = _rates(shipped)
    for flow in shipped.response.plan.items:
        assert flow.net_per_min == pytest.approx(rates.get(flow.item_id, 0.0), abs=1e-6), flow


def test_lp_power_is_machine_time_at_mean_power_not_a_realization(shipped):
    power = shipped.response.plan.power
    assert power.scenario_mw == pytest.approx(1181.7167, abs=1e-3)
    assert power.canonical_mw == pytest.approx(power.scenario_mw / 5.0, abs=1e-6)
    assert any("power excludes extraction" in w for w in shipped.response.plan.warnings)


# --- readme case: the same plan at a quarter ------------------------------

def test_the_readme_case_is_the_shipped_plan_scaled_by_a_quarter(shipped, readme):
    s, r = _rates(shipped), _rates(readme)
    assert r == pytest.approx({k: v / 4.0 for k, v in s.items()}, abs=1e-4)
    assert readme.response.scale == pytest.approx(shipped.response.scale / 4.0, abs=1e-7)
    assert readme.response.horizon_min == pytest.approx(875.0, abs=1e-2)
    assert readme.response.power is None
    coal = {b.item_id: b.shadow_price for b in readme.response.binding}[I["COAL"]]
    assert coal == pytest.approx(1.905e-5, rel=1e-2)   # the price per unit does not depend on the clock


def test_floors_too_high_for_the_readme_case_are_refused_with_the_scale():
    """Extras with floors (the A27.2 shape, no bill): 1 / 1 / 0.5 fit
    together only to 0.7555 of their values, coal and caterium binding.
    Measured 2026-10-08 before A31; kept as the extras path's diagnosis."""
    from production_adapter import DistrictRequest, DistrictTarget
    from production_adapter.lp_backend import Infeasible, LpBackend, PowerStatistic
    base = district_run.run(DECL, case="readme", power=False)
    request = DistrictRequest(
        targets=(DistrictTarget(I["VF"], minimum_rate=1.0), DistrictTarget(I["MOTOR"], minimum_rate=1.0),
                 DistrictTarget(I["EIB"], minimum_rate=0.5)),
        allowed_recipes=base.request.allowed_recipes, resource_caps=base.caps,
    )
    with pytest.raises(Infeasible) as e:
        LpBackend(PowerStatistic.MEAN).solve_district(request, load(REPO, DECL.SCENARIO))
    assert "0.7555" in str(e.value)
    assert "Desc_Coal_C" in str(e.value) and "Desc_OreGold_C" in str(e.value)


# --- power in the solve (A29) ----------------------------------------------

def test_power_is_composed_from_the_declaration(shipped_power):
    pb = shipped_power.request.power
    assert pb.grid_mw == 900.0 and pb.spare_mw == 30.0
    assert pb.extraction_mw == 75.0            # 7 x Mk.1 at 5 MW + 2 water at 20 MW
    assert [(g.generator_class, g.fuel_item_id) for g in pb.generators] == [
        ("Build_GeneratorCoal_C", I["COAL"]),
        ("Build_GeneratorCoal_C", "Desc_CompactedCoal_C"),
        ("Build_GeneratorCoal_C", "Desc_PetroleumCoke_C"),
    ]


def test_shipped_with_power_keeps_the_proportion_and_builds_coal_generators(shipped_power):
    """Power priced, the proportion holds (A31) and the scale drops from
    0.004571 to 0.003829: 2.598 coal generators take coal from steel."""
    r = shipped_power.response
    assert r.scale == pytest.approx(0.003829, abs=1e-6)
    assert r.horizon_min == pytest.approx(261.15, abs=1e-2)
    assert _rates(shipped_power) == pytest.approx(
        {I["VF"]: 3.82917, I["MOTOR"]: 0.765834, I["EIB"]: 2.297505}, abs=1e-4,
    )
    assert [t.share for t in r.targets] == pytest.approx([r.scale] * 3, abs=1e-6)
    pw = r.power
    assert pw.lane_mw == pytest.approx(989.8427, abs=1e-3)
    assert pw.generated_mw == pytest.approx(194.8427, abs=1e-3)
    assert pw.margin_mw == pytest.approx(0.0, abs=1e-6) and pw.binding
    assert pw.shadow_price == pytest.approx(1.919e-6, rel=1e-2)   # scale per MW
    [g] = pw.generators
    assert g.fuel_item_id == I["COAL"]
    assert g.count == pytest.approx(2.597902, abs=1e-4)
    assert g.fuel_per_min == pytest.approx(38.968534, abs=1e-4)
    assert dict(g.supplemental_per_min) == pytest.approx({I["WATER"]: 116.905603}, abs=1e-4)
    # the plan's raw draw carries the generators' coal and water
    assert _raw(r.plan) == pytest.approx({
        I["COAL"]: 240.0, I["STONE"]: 73.520155, I["ORE"]: 301.4408, I["GOLD"]: 17.461013,
        I["WATER"]: 116.905603,
    }, abs=1e-3)
    assert I["COAL"] in {b.item_id for b in r.binding}


def test_readme_with_power_is_the_caps_only_plan_on_the_grid(readme, readme_power):
    assert _rates(readme_power) == pytest.approx(_rates(readme), abs=1e-6)
    pw = readme_power.response.power
    assert pw.generators == () and not pw.binding
    assert pw.lane_mw == pytest.approx(295.4291, abs=1e-3)
    assert pw.margin_mw == pytest.approx(499.5709, abs=1e-3)


# --- realization over the plan (A32; v5.5 Stage 5 and "factory parity") -----

def _lanes(dr, bus_id):
    [bus] = [b for b in dr.realization.buses if b.bus_id == bus_id]
    return bus.lanes


def test_realization_reproduces_the_plans_rates_bus_by_bus(shipped_power):
    """Every target's realized output equals the solve's rate, and every
    intermediate lane's output equals its consumers' draw (A32.2 Z2):
    stores=False clocks the line to its consumers. The residual realization
    reports is nameplate minus draw, the idle headroom of whole machines
    backing up (Disposition.BACK_UP), not stored overflow; on a terminal bus
    the draw is out of scope, so the whole nameplate is reported there
    (buses.py `_demand`), and the export is the lane's clocked output."""
    rz = shipped_power.realization
    assert rz is not None and len(rz.buses) == 18
    targets = {t.item_id: t.rate_per_min for t in shipped_power.response.targets}
    for bus in rz.buses:
        out = sum(l.output_rate_per_min for l in bus.lanes)
        # 1e-4: realization's clock percentages carry their own rounding
        if bus.item_id in targets:
            assert out == pytest.approx(targets[bus.item_id], abs=1e-4)
        else:
            assert out == pytest.approx(bus.automated_demand_per_min, abs=1e-4), bus.bus_id
        assert bus.residual.disposition.name == "BACK_UP"
        assert bus.residual.rate_per_min == pytest.approx(
            bus.supply_per_min - bus.automated_demand_per_min, abs=1e-4,
        ), bus.bus_id


def test_realization_sizes_whole_machines_at_explicit_clocks(shipped_power):
    rz = shipped_power.realization
    counts: dict[str, int] = {}
    for bus in rz.buses:
        for lane in bus.lanes:
            counts[lane.producer_class] = counts.get(lane.producer_class, 0) + lane.machines
    assert counts == {"Build_AssemblerMk1_C": 7, "Build_ConstructorMk1_C": 16,
                      "Build_FoundryMk1_C": 4, "Build_SmelterMk1_C": 12}
    [vf] = _lanes(shipped_power, "versatile_framework")
    assert (vf.machines, vf.clock_percent) == (1, pytest.approx(76.5834, abs=1e-3))
    [steel] = _lanes(shipped_power, "steel_ingot")
    assert steel.machines == 4 and steel.recipe_id == "Recipe_Alternate_IngotSteel_1_C"
    # the iron ingot bus splits into two lanes on a Mk.3 belt at tier 4
    assert [l.machines for l in _lanes(shipped_power, "iron_ingot")] == [6, 5]


def test_realized_power_is_at_the_clock_and_at_the_scenario_multiplier(shipped_power):
    """908.12 MW realized against the LP's 989.84 MW machine-time: the clock
    exponent saves power the LP cannot see, so the solve's balance is
    floor-safe (A25.3 P2, confirmed). Both figures carry the 5x multiplier
    (A32.1): one Assembler at 100 % would be 75 MW."""
    rz = shipped_power.realization
    assert rz.total_power_mw == pytest.approx(908.1155, abs=1e-3)
    assert rz.total_power_mw < shipped_power.response.plan.power.scenario_mw
    [vf] = _lanes(shipped_power, "versatile_framework")
    assert vf.power_mw == pytest.approx(75.0 * (vf.clock_percent / 100.0) ** 1.321929, rel=1e-6)


def test_realization_of_the_readme_case(readme_power):
    rz = readme_power.realization
    counts: dict[str, int] = {}
    for bus in rz.buses:
        for lane in bus.lanes:
            counts[lane.producer_class] = counts.get(lane.producer_class, 0) + lane.machines
    assert sum(counts.values()) == 20
    assert rz.total_power_mw == pytest.approx(247.5206, abs=1e-3)
    [steel] = _lanes(readme_power, "steel_ingot")
    assert (steel.machines, steel.clock_percent) == (1, pytest.approx(100.0, abs=1e-6))


def test_realization_can_be_skipped(shipped):
    assert district_run.run(DECL, case="shipped", power=False, realization=False).realization is None


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

def test_export_carries_the_power_balance(shipped_power, tmp_path):
    data = load(REPO, DECL.SCENARIO)
    path = tmp_path / "district_power.json"
    district_run.export(shipped_power, data, path)
    doc = json.loads(path.read_bytes())
    assert doc["power"]["binding"] is True
    assert doc["power"]["generators"][0]["generator_class"] == "Build_GeneratorCoal_C"
    assert doc["power"]["grid_mw"] == 900.0


def test_export_is_one_lf_json_document_with_the_plan_and_its_inputs(shipped, tmp_path):
    data = load(REPO, DECL.SCENARIO)
    path = tmp_path / "district.json"
    district_run.export(shipped, data, path)
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    doc = json.loads(raw)
    assert doc["schema"] == district_run.EXPORT_SCHEMA
    assert doc["case"] == "shipped"
    assert doc["power"] is None   # this fixture ran caps-only
    assert doc["scenario"]["recipe_input_multiplier"] == 1.25
    assert doc["scenario"]["machine_power_multiplier"] == 5.0
    assert [n["item_id"] for n in doc["district"]["nodes"]] == [I["ORE"], I["COAL"], I["STONE"], I["GOLD"], I["WATER"]]
    assert len(doc["district"]["caps"]) == 13
    assert doc["goal"] == {"name": "balanced", "resources": 1.0, "power": 1.0, "buildings": 1.0, "complexity": 0.0}
    assert doc["bill"]["phases"] == [2] and doc["bill"]["tiers"] == [3, 4, 5]
    assert doc["bill"]["units"][I["MOTOR"]] == 200.0
    assert doc["bill"]["scale"] == pytest.approx(0.004571, abs=1e-6)
    assert [t["item_id"] for t in doc["targets"]] == [I["VF"], I["MOTOR"], I["EIB"]]
    assert doc["weighted_output"] == pytest.approx(3.555556, abs=1e-4)
    assert {b["item_id"] for b in doc["binding"]} >= {I["COAL"], I["ORE"]}
    assert len(doc["plan"]["recipes"]) == 18
    assert doc["baseline"] is not None and len(doc["baseline"]["recipes"]) == 16
    assert len(doc["realization"]["buses"]) == 18 and doc["realization"]["design_tier"] == 4
    assert sum(1 for x in doc["discovery"] if x["makeable"]) == 15
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
    assert _called_names(tree) <= {"dict", "NodeCount", "DistrictTarget", "Scenario", "B", "S"}
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
