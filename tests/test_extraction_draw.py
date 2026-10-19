"""Extraction charged by the draw, and pumped Water (site_planner_reframe.md
Amendment 4, decided by Greg 2026-10-19).

    charges    each segment's draw * mw_per_unit on the shared grid row; an
               idle socket costs nothing; nameplate reported beside the draw
    pumps      Water at a site declared able to pump it: uncapped, charged as
               Water Extractors (20 MW per 120 m3/min); a transfer of it does
               not escape the charge
    composes   progression.district.extraction_segments: the same caps as
               resource_caps, MW per unit = base MW / nominal rate; a clock
               above 100 % refused
    refuses    a pumped raw with a cap, caps that are not their segments' sum,
               a free uncapped segment, segments with no grid or beside a
               constant nameplate charge

Real reference data, canonical scenario, small explicit recipe sets. Expected
figures derived by hand in each docstring, then run.
"""
from __future__ import annotations

import pathlib

import pytest

from production_adapter import (
    AllowedRecipes, ExtractionSegment, PortfolioRequest, PortfolioSite, PowerBalance, RecipeMode,
    ResourceCap, load,
)
from production_adapter.gamedata import load_generators, load_logistics
from production_adapter.lp_backend import LpBackend, PowerStatistic
from progression import (
    DistrictDefinition, DistrictError, NodeCount, extraction_segments, pumped_water, resource_caps,
    resources_in_reference_order,
)
from progression.power import load_power_tables

REPO = pathlib.Path(__file__).resolve().parents[1]
IRON, COAL, WATER, PLATE = "Desc_OreIron_C", "Desc_Coal_C", "Desc_Water_C", "Desc_IronPlate_C"
PLATES = AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=("Recipe_IngotIron_C", "Recipe_IronPlate_C"))
MK1 = 5.0 / 60.0          # Miner Mk.1, normal node: 5 MW for 60/min
PUMP = 20.0 / 120.0       # Water Extractor: 20 MW for 120 m3/min


@pytest.fixture(scope="module")
def data():
    return load(REPO)


@pytest.fixture(scope="module")
def backend():
    return LpBackend(power_statistic=PowerStatistic.MEAN)


def _coal_power(**kw) -> PowerBalance:
    rows = tuple(g for g in load_generators(REPO)
                 if g.generator_class == "Build_GeneratorCoal_C" and g.fuel_item_id == COAL)
    return PowerBalance(generators=rows, **kw)


def _caps(data, **rates):
    return tuple(ResourceCap(i, rates[i] if i in rates else 0.0)
                 for i in data.items if i in data.resource_items)


def _seg(item, cap, mw):
    return ExtractionSegment(item, cap, mw, None if cap is None else cap * mw)


def test_the_draw_is_charged_and_the_idle_rest_is_not(backend, data):
    """Plate costs 1.5 ore and 0.4 MW of machines (Smelter and Constructor at
    4 MW). One Coal generator: 75 MW on 15 Coal + 45 Water. Charged by the
    draw: Coal 15 * 5/60 = 1.25 MW, Water 45 * 20/120 = 7.5 MW, ore 1.5 *
    5/60 = 0.125 MW per Plate. Scale = (75 - 1.25 - 7.5) / 0.525 = 126.19;
    ore 189.3 of 300, so the idle ore is not charged."""
    site = PortfolioSite(
        "s", _caps(data, **{IRON: 300.0, COAL: 15.0, WATER: None}),
        (_seg(IRON, 300.0, MK1), _seg(COAL, 15.0, MK1), _seg(WATER, None, PUMP)),
    )
    r = backend.solve_portfolio(PortfolioRequest((site,), ((PLATE, 1.0),), PLATES,
                                                 power=_coal_power()), data)
    assert r.scale == pytest.approx(66.25 / 0.525, rel=1e-6)
    plan = r.sites[0]
    assert plan.pumped == ((WATER, pytest.approx(45.0, rel=1e-6)),)
    assert plan.extraction_mw == pytest.approx(1.25 + 7.5 + 1.5 * r.scale * MK1, rel=1e-6)
    assert plan.extraction_nameplate_mw == pytest.approx(25.0 + 1.25, rel=1e-9)  # pumped: none
    assert r.power.extraction_mw == pytest.approx(plan.extraction_mw, rel=1e-9)
    assert r.power.extraction_nameplate_mw == pytest.approx(26.25, rel=1e-9)
    assert r.power.binding and r.power.shadow_price > 0.0


def test_an_unpowered_site_with_segments_scales_to_zero_not_infeasible(backend, data):
    """Under P2's constant (test_portfolio_solve) this site had no plan. By
    the draw, an idle site draws nothing: scale 0.0, a plan."""
    site = PortfolioSite("s", _caps(data, **{IRON: 60.0}), (_seg(IRON, 60.0, MK1),))
    r = backend.solve_portfolio(PortfolioRequest((site,), ((PLATE, 1.0),), PLATES,
                                                 power=_coal_power()), data)
    assert r.scale == 0.0 and r.sites[0].extraction_mw == pytest.approx(0.0, abs=1e-9)


def test_pumped_water_moved_to_another_site_is_still_charged(backend, data):
    """The plant has Coal and no Water; the well pumps. With free transfers
    (A1 P3) the volume stage (P5) moves the 15 Coal to the water rather than
    45 Water to the coal, and burns it there; the pump is charged where it
    stands. Same arithmetic as above with the ore at the plant."""
    plant = PortfolioSite(
        "plant", _caps(data, **{IRON: 300.0, COAL: 15.0, WATER: 0.0}),
        (_seg(IRON, 300.0, MK1), _seg(COAL, 15.0, MK1)),
    )
    well = PortfolioSite("well", _caps(data, **{IRON: 0.0, COAL: 0.0, WATER: None}),
                         (_seg(WATER, None, PUMP),))
    r = backend.solve_portfolio(PortfolioRequest((plant, well), ((PLATE, 1.0),), PLATES,
                                                 power=_coal_power()), data)
    assert r.scale == pytest.approx(66.25 / 0.525, rel=1e-6)
    assert [(t.source, t.item_id) for t in r.transfers] == [("plant", COAL)]
    assert r.transfer_volume_per_min == pytest.approx(15.0, rel=1e-6)
    plant_plan, well_plan = r.sites
    assert well_plan.generators and not plant_plan.generators
    assert well_plan.pumped == ((WATER, pytest.approx(45.0, rel=1e-6)),)
    assert well_plan.extraction_mw == pytest.approx(7.5, rel=1e-6)


def test_the_power_goal_prices_the_draw(backend, data):
    """Two Iron segments, the cheaper MW per unit first: Mk.1 on a pure node
    is 5 MW for 120/min, on an impure one 5 MW for 30/min. A grid without
    limit and the power goal: the 30/min of ore comes from the pure node."""
    from production_adapter import Weights
    pure, impure = ExtractionSegment(IRON, 120.0, 5.0 / 120.0, 5.0), ExtractionSegment(IRON, 30.0, 5.0 / 30.0, 5.0)
    site = PortfolioSite("s", _caps(data, **{IRON: 150.0}), (pure, impure))
    r = backend.solve_portfolio(PortfolioRequest(
        (site,), ((PLATE, 20.0),), PLATES, Weights(resources=0.0, power=1.0, buildings=0.0),
        power=PowerBalance(grid_mw=1.0e4),
    ), data)
    # scale is ore-bound: 150 ore -> 100 Plate -> scale 5; then every unit is drawn
    assert r.scale == pytest.approx(5.0, rel=1e-6)
    assert r.sites[0].extraction_mw == pytest.approx(10.0, rel=1e-6)
    # at half the bill the pure node alone is drawn
    r2 = backend.solve_portfolio(PortfolioRequest(
        (PortfolioSite("s", _caps(data, **{IRON: 150.0}), (pure, impure)),), ((PLATE, 20.0),), PLATES,
        Weights(resources=0.0, power=1.0, buildings=0.0), power=PowerBalance(grid_mw=8.0 * 2.5 + 2.5),
    ), data)
    # grid 22.5 MW: Plate costs 0.4 MW + ore 1.5 * 5/120 = 0.0625 MW, so
    # 22.5 / 0.4625 = 48.6 Plate (73 ore, all pure); scale 2.43
    assert r2.scale == pytest.approx(22.5 / 0.4625 / 20.0, rel=1e-6)
    assert r2.sites[0].extraction_mw == pytest.approx(22.5 / 0.4625 * 1.5 * 5.0 / 120.0, rel=1e-6)


@pytest.mark.parametrize("build, match", [
    (lambda d: ExtractionSegment(WATER, None, 0.0, None), "must cost power"),
    (lambda d: ExtractionSegment(IRON, 60.0, MK1, None), "exactly when"),
    (lambda d: PortfolioSite("s", _caps(d, **{WATER: 45.0}), (_seg(WATER, None, PUMP),)), "pumped"),
    (lambda d: PortfolioSite("s", _caps(d, **{IRON: 90.0}), (_seg(IRON, 60.0, MK1),)), "sum"),
    (lambda d: PortfolioSite("s", _caps(d, **{IRON: None})), "uncapped"),
    (lambda d: PortfolioRequest(
        (PortfolioSite("s", _caps(d, **{IRON: 60.0}), (_seg(IRON, 60.0, MK1),)),),
        ((PLATE, 1.0),), PLATES), "power is None"),
    (lambda d: PortfolioRequest(
        (PortfolioSite("s", _caps(d, **{IRON: 60.0}), (_seg(IRON, 60.0, MK1),)),),
        ((PLATE, 1.0),), PLATES, power=_coal_power(extraction_mw=5.0)), "twice"),
])
def test_requests_it_cannot_use_refuse(data, build, match):
    with pytest.raises(ValueError, match=match):
        build(data)


# -- the composer --------------------------------------------------------------

def _definition(clock=1.0, reserve=0.0):
    return DistrictDefinition(
        nodes=(NodeCount(IRON, "normal", 2), NodeCount(IRON, "pure", 1),
               NodeCount("Desc_LiquidOil_C", "normal", 1, extractor_class="Build_OilPump_C")),
        extractor_class="Build_MinerMk1_C", extraction_clock=clock, reserve_fraction=reserve,
    )


def test_segments_carry_the_caps_resource_caps_composes(data):
    _, rates = load_logistics(REPO)
    base = load_power_tables(REPO).extractors
    d = _definition(clock=0.5, reserve=0.1)
    segs = extraction_segments(d, rates, base)
    caps = {c.item_id: c.rate_per_min for c in resource_caps(d, rates, resources_in_reference_order(data))}
    for item in (IRON, "Desc_LiquidOil_C"):
        assert sum(s.cap_per_min for s in segs if s.item_id == item) == pytest.approx(caps[item], rel=1e-12)
    assert [s.mw_per_unit for s in segs[:2]] == [pytest.approx(5.0 / 60.0), pytest.approx(5.0 / 120.0)]
    assert [s.nameplate_mw for s in segs] == [10.0, 5.0, 40.0]


def test_an_overclock_is_refused_by_the_composer():
    _, rates = load_logistics(REPO)
    with pytest.raises(DistrictError, match="above 100 %"):
        extraction_segments(_definition(clock=1.5), rates, load_power_tables(REPO).extractors)


def test_pumped_water_is_a_water_extractor_by_the_draw():
    _, rates = load_logistics(REPO)
    seg = pumped_water(rates, load_power_tables(REPO).extractors)
    assert (seg.item_id, seg.cap_per_min, seg.nameplate_mw) == (WATER, None, None)
    assert seg.mw_per_unit == pytest.approx(PUMP, rel=1e-12)
