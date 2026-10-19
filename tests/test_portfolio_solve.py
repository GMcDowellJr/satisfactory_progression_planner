"""`LpBackend.solve_portfolio`: several sites, one bill, free transfers.

Site-planner reframe Amendment 1 (adopted by Greg, 2026-10-19): bill demand
(P1), power outside (P2), free transfers (P3), raws may move (P6), one item =
one m3 in the volume tie-break (P5), bill counted wherever made (P7).

    reconciles   a one-site portfolio IS the district bill solve (spec §10 I)
    pools        with free transfers the scale equals one merged site's
    places       among plans of equal scale, the least volume moved: two
                 self-sufficient sites trade nothing; Fused Wire ships the
                 smaller Caterium Ingot stream, not the Copper one
    conserves    per site and item: made + drawn + in = used + out + delivered
                 + leftover
    refuses      uncapped raws, repeated labels, a repeated bill item, sites
                 that cap different raws

Real reference data, canonical scenario, small explicit recipe sets.
"""
from __future__ import annotations

import pathlib

import pytest

from production_adapter import (
    AllowedRecipes, DistrictRequest, DistrictTarget, PortfolioRequest, PortfolioSite,
    RecipeMode, ResourceCap, load,
)
from production_adapter.lp_backend import LpBackend, PowerStatistic

REPO = pathlib.Path(__file__).resolve().parents[1]
IRON, COPPER, CATERIUM = "Desc_OreIron_C", "Desc_OreCopper_C", "Desc_OreGold_C"
PLATE, WIRE = "Desc_IronPlate_C", "Desc_Wire_C"
CU_INGOT, CAT_INGOT = "Desc_CopperIngot_C", "Desc_GoldIngot_C"
BASIC = AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=(
    "Recipe_IngotIron_C", "Recipe_IronPlate_C", "Recipe_IngotCopper_C", "Recipe_Wire_C",
))
#: Fused Wire 12 Copper Ingot + 3 Caterium Ingot -> 90 Wire; the only Wire here
FUSED = AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=(
    "Recipe_IngotCopper_C", "Recipe_IngotCaterium_C", "Recipe_Alternate_FusedWire_C",
))
BILL = ((PLATE, 2.0), (WIRE, 3.0))


@pytest.fixture(scope="module")
def data():
    return load(REPO)


@pytest.fixture(scope="module")
def backend():
    return LpBackend(power_statistic=PowerStatistic.MEAN)


def _caps(data, **rates):
    return tuple(ResourceCap(i, float(rates.get(i, 0.0))) for i in data.items if i in data.resource_items)


def _site(data, label, **rates):
    return PortfolioSite(label, _caps(data, **rates))


def test_one_site_is_the_district_bill_solve(backend, data):
    caps = _caps(data, **{IRON: 60.0, COPPER: 30.0})
    portfolio = backend.solve_portfolio(PortfolioRequest((PortfolioSite("all", caps),), BILL, BASIC), data)
    district = backend.solve_district(DistrictRequest(
        tuple(DistrictTarget(i, bill_units=u) for i, u in BILL), BASIC, caps,
    ), data)
    assert portfolio.scale == pytest.approx(district.scale, rel=1e-9)
    assert portfolio.scale == pytest.approx(20.0, rel=1e-9)
    assert portfolio.transfers == ()


def test_free_transfers_pool_the_sites_and_self_sufficient_sites_trade_nothing(backend, data):
    two = backend.solve_portfolio(PortfolioRequest(
        (_site(data, "iron", **{IRON: 60.0}), _site(data, "copper", **{COPPER: 30.0})), BILL, BASIC,
    ), data)
    assert two.scale == pytest.approx(20.0, rel=1e-9)
    assert two.transfers == () and two.transfer_volume_per_min == 0.0
    made = {s.label: dict(s.delivered) for s in two.sites}
    assert made == {"iron": pytest.approx({PLATE: 40.0}), "copper": pytest.approx({WIRE: 60.0})}
    assert [b.item_id for b in two.sites[0].binding] == [IRON]


def test_the_volume_tie_break_ships_the_smaller_stream(backend, data):
    """Wire needs both ingots at one machine. 30 Copper Ore -> 30 ingots, 45
    Caterium Ore -> 15 ingots: the binding stream is copper at 12:3, so 7.5
    Caterium Ingot/min travels to the copper site rather than 30 Copper the
    other way. Same scale either way; the tie-break (P5) decides."""
    r = backend.solve_portfolio(PortfolioRequest(
        (_site(data, "copper", **{COPPER: 30.0}), _site(data, "caterium", **{CATERIUM: 45.0})),
        ((WIRE, 1.0),), FUSED,
    ), data)
    assert r.scale == pytest.approx(225.0, rel=1e-9)
    assert [(t.source, t.destination, t.item_id) for t in r.transfers] == [("caterium", "copper", CAT_INGOT)]
    assert r.transfer_volume_per_min == pytest.approx(7.5, rel=1e-6)
    assert dict(r.sites[0].delivered) == pytest.approx({WIRE: 225.0})


def test_raws_may_move(backend, data):
    """P6: a site with no smelting advantage still lets ore travel when that
    is the least volume. Here every recipe is at both sites, so moving 7.5
    ingots beats moving 22.5 ore: the ingot is made where its ore is."""
    r = backend.solve_portfolio(PortfolioRequest(
        (_site(data, "copper", **{COPPER: 30.0}), _site(data, "caterium", **{CATERIUM: 45.0})),
        ((WIRE, 1.0),), FUSED,
    ), data)
    assert not [t for t in r.transfers if t.item_id in data.resource_items]


def test_every_site_conserves(backend, data):
    r = backend.solve_portfolio(PortfolioRequest(
        (_site(data, "copper", **{COPPER: 30.0}), _site(data, "caterium", **{CATERIUM: 45.0})),
        ((WIRE, 1.0),), FUSED,
    ), data)
    for site in r.sites:
        flows = {f.item_id: f.net_per_min for f in site.plan.items}
        out = {}
        for t in r.transfers:
            if t.source == site.label:
                out[t.item_id] = out.get(t.item_id, 0.0) + t.rate_per_min
            if t.destination == site.label:
                out[t.item_id] = out.get(t.item_id, 0.0) - t.rate_per_min
        delivered = dict(site.delivered)
        for item, net in flows.items():
            assert net == pytest.approx(out.get(item, 0.0) + delivered.get(item, 0.0), abs=1e-6), (site.label, item)


def test_a_bill_no_site_can_cover_scales_to_zero(backend, data):
    r = backend.solve_portfolio(PortfolioRequest(
        (_site(data, "iron", **{IRON: 60.0}),), ((WIRE, 1.0),), BASIC,
    ), data)
    assert r.scale == 0.0 and r.horizon_min is None


@pytest.mark.parametrize("build, match", [
    (lambda d: PortfolioSite("s", (ResourceCap(IRON, None),)), "uncapped"),
    (lambda d: PortfolioRequest((_site(d, "a"), _site(d, "a")), BILL, BASIC), "repeat"),
    (lambda d: PortfolioRequest((_site(d, "a"),), ((PLATE, 1.0), (PLATE, 2.0)), BASIC), "twice"),
    (lambda d: PortfolioRequest((_site(d, "a"),), ((PLATE, 0.0),), BASIC), "positive"),
    (lambda d: PortfolioRequest(
        (_site(d, "a"), PortfolioSite("b", (ResourceCap(IRON, 1.0),))), BILL, BASIC), "same raw"),
    (lambda d: PortfolioRequest((), BILL, BASIC), "at least one site"),
])
def test_requests_it_cannot_use_refuse(data, build, match):
    with pytest.raises(ValueError, match=match):
        build(data)


def test_locality_comes_before_a_cheaper_recipe_mix(backend, data):
    """A1.2's stage order. Iron caps the scale at 20 (Plate 1:1 with Wire), so
    Wire has slack. Base Wire at the copper site needs 10 Copper Ore and no
    transfer; Fused Wire needs ~4.7 ore but Caterium Ingot shipped in. A
    resources-only goal prefers Fused; the volume stage runs first and keeps
    Wire local. (Mutation-checked: without stage 2, Caterium Ingot moves.)"""
    from production_adapter import Weights
    both = AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=BASIC.recipe_ids + FUSED.recipe_ids[1:])
    r = backend.solve_portfolio(PortfolioRequest(
        (_site(data, "home", **{IRON: 30.0, COPPER: 30.0}), _site(data, "caterium", **{CATERIUM: 45.0})),
        ((PLATE, 1.0), (WIRE, 1.0)), both, Weights(resources=1.0, power=0.0, buildings=0.0),
    ), data)
    assert r.scale == pytest.approx(20.0, rel=1e-6)
    assert r.transfers == ()
    assert "Recipe_Alternate_FusedWire_C" not in {u.recipe_id for u in r.sites[0].plan.recipes}
