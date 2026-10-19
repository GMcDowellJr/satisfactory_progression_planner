"""tools/site_card.py: what can be made at a site, and what limits it.

Handoff 2026-10-19 12:35, actions 1-2 (status: under consideration). The two
acceptance cases are spec v1.0 (proposed) section 10 A and B, on real sockets
of the default world 502094 (a fixture, not the architecture), canonical
scenario (recipe x1), extraction at 100 %, Miner Mk.1 / Oil Extractor:

    A  Oil site, one impure Copper node: 16 sockets within 500 m of
       BP_ResourceNode98, tier 6. Measured 2026-10-19 (container, py3.13):
       Plastic 680/min on Crude Oil alone; Computer 1.25/min, Copper the
       only cap it draws fully, with Crude Oil left over
    B  Iron / Coal / Limestone / Caterium (+ Sulfur): 13 sockets within 300 m
       of BP_ResourceNode169_UAID_..., tier 4 + Caterium Ingot and Quickwire.
       Measured 2026-10-19: 16 products, each with its own limiting cap;
       Motor not makeable (base Wire needs Copper)

Spec B also asks for competing products "simultaneously" with no double use
of supply. One solve per product cannot do that; the card states that its
ceilings are alternatives, and that is what is pinned here. A portfolio solve
is spec F3, not this slice.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("site_card", REPO / "tools" / "site_card.py")
site_card = sys.modules.get("site_card") or importlib.util.module_from_spec(_spec)
if "site_card" not in sys.modules:
    sys.modules["site_card"] = site_card
    _spec.loader.exec_module(site_card)

from production_adapter import ResourceCap, Scenario  # noqa: E402
from production_adapter.lp_backend import PowerStatistic  # noqa: E402

OIL, COPPER, IRON, STONE, CATERIUM, COAL = (
    "Desc_LiquidOil_C", "Desc_OreCopper_C", "Desc_OreIron_C", "Desc_Stone_C",
    "Desc_OreGold_C", "Desc_Coal_C",
)
MINERS = (
    (("resource_node", None), "Build_MinerMk1_C"),
    (("resource_node", OIL), "Build_OilPump_C"),
)
SITE_A = ("BP_ResourceNode98", 500.0)
SITE_B = ("BP_ResourceNode169_UAID_40B076DF2F7939DE01_2083925623", 300.0)


@pytest.fixture(scope="module")
def sockets():
    return site_card.load_sockets(REPO, "default_502094")


def _spec_around(sockets, centre_id, radius, label):
    centre = next(s for s in sockets if s.socket_id == centre_id)
    ids = site_card.sockets_within(sockets, centre.east_m, centre.north_m, radius)
    return site_card.SiteSpec(label=label, socket_ids=ids, extractors=MINERS, extraction_clock=1.0)


def _card(spec, tier, recipes=()):
    return site_card.build_card(
        spec, tier=tier, scenario=Scenario(), goal="balanced",
        power_statistic=PowerStatistic.MEAN, declared_recipe_names=recipes,
    )


@pytest.fixture(scope="module")
def card_a(sockets):
    return _card(_spec_around(sockets, *SITE_A, "A: oil, one impure copper"), tier=6)


@pytest.fixture(scope="module")
def card_b(sockets):
    return _card(_spec_around(sockets, *SITE_B, "B: iron coal limestone caterium"),
                 tier=4, recipes=("Caterium Ingot", "Quickwire"))


@pytest.fixture(scope="module")
def card_b_pool(sockets):
    return site_card.build_card(
        _spec_around(sockets, *SITE_B, "B"), tier=4, scenario=Scenario(), goal="balanced",
        power_statistic=PowerStatistic.MEAN, declared_recipe_names=("Caterium Ingot", "Quickwire"),
        compare_pool=True,
    )


def _opp(card, item):
    return next(o for o in card.opportunities if o.item_id == item)


def _limits(opp):
    return [u.item_id for u in opp.caps if u.binding]


# -- the world join -------------------------------------------------------------

def _row(sid, kind="resource_node", core=""):
    return {"socket_id": sid, "source_kind": kind, "east_m": "0", "north_m": "0",
            "elevation_m": "0", "core_socket_id": core}


def _assign(sid, item="Desc_OreIron_C", world="w"):
    return {"world_config_id": world, "socket_id": sid, "resource_descriptor": item, "purity": "pure"}


def test_the_default_world_joins_every_socket(sockets):
    assert len(sockets) == 625
    assert len({s.socket_id for s in sockets}) == 625


def test_an_unassigned_socket_refuses():
    with pytest.raises(site_card.SiteCardError, match="no assignment row"):
        site_card.join_sockets([_row("a"), _row("b")], [_assign("a")], "w")


def test_an_assignment_for_an_unknown_socket_refuses():
    with pytest.raises(site_card.SiteCardError, match="unknown sockets"):
        site_card.join_sockets([_row("a")], [_assign("a"), _assign("z")], "w")


def test_a_socket_assigned_twice_refuses():
    with pytest.raises(site_card.SiteCardError, match="assigned twice"):
        site_card.join_sockets([_row("a")], [_assign("a"), _assign("a")], "w")


def test_other_world_configurations_are_not_read():
    joined = site_card.join_sockets([_row("a")], [_assign("a"), _assign("a", world="other")], "w")
    assert [s.item_id for s in joined] == ["Desc_OreIron_C"]


def test_an_unknown_world_configuration_refuses():
    with pytest.raises(site_card.SiteCardError, match="no world configuration"):
        site_card.load_sockets(REPO, "no_such_world")


# -- selecting a site -----------------------------------------------------------

def _socket(sid, east, north, elev=0.0, kind="resource_node", item=IRON):
    return site_card.Socket(sid, kind, item, "pure", east, north, elev, None)


def test_radius_is_horizontal_and_keeps_file_order():
    world = (_socket("far", 300, 0), _socket("high", 0, 99, elev=5000.0), _socket("near", 10, 0))
    assert site_card.sockets_within(world, 0.0, 0.0, 100.0) == ("high", "near")


def test_a_radius_must_be_positive():
    with pytest.raises(site_card.SiteCardError, match="radius"):
        site_card.sockets_within((), 0.0, 0.0, 0.0)


def test_cores_and_geysers_are_listed_not_extracted():
    world = (
        _socket("node", 0, 0),
        _socket("core", 0, 0, kind="fracking_core", item="Desc_Water_C"),
        _socket("geyser", 0, 0, kind="geothermal_geyser", item=None),
    )
    spec = site_card.SiteSpec("s", ("node", "core", "geyser"), MINERS, 1.0)
    chosen, nodes, skipped = site_card.site_nodes(world, spec)
    assert [s.socket_id for s in chosen] == ["node", "core", "geyser"]
    assert [(n.item_id, n.extractor_class) for n in nodes] == [(IRON, "Build_MinerMk1_C")]
    assert [sid for sid, _ in skipped] == ["core", "geyser"]


def test_the_item_specific_extractor_wins_over_the_kind():
    world = (_socket("oil", 0, 0, item=OIL), _socket("iron", 0, 0))
    spec = site_card.SiteSpec("s", ("oil", "iron"), MINERS, 1.0)
    _, nodes, _ = site_card.site_nodes(world, spec)
    assert [n.extractor_class for n in nodes] == ["Build_OilPump_C", "Build_MinerMk1_C"]


def test_an_undeclared_extractor_refuses():
    world = (_socket("sat", 0, 0, kind="fracking_satellite", item="Desc_NitrogenGas_C"),)
    with pytest.raises(site_card.SiteCardError, match="no extractor declared"):
        site_card.site_nodes(world, site_card.SiteSpec("s", ("sat",), MINERS, 1.0))


@pytest.mark.parametrize("ids, match", [
    ((), "at least one socket"),
    (("a", "a"), "listed twice"),
    (("nope",), "unknown sockets"),
    (("g",), "none of its sockets is extracted"),
])
def test_a_site_it_cannot_use_refuses(ids, match):
    world = (_socket("a", 0, 0), _socket("g", 0, 0, kind="geothermal_geyser", item=None))
    with pytest.raises(site_card.SiteCardError, match=match):
        site_card.site_nodes(world, site_card.SiteSpec("s", ids, MINERS, 1.0))


def test_declared_supply_adds_to_its_raw_and_refuses_otherwise():
    caps = (ResourceCap(IRON, 60.0), ResourceCap("Desc_Water_C", 0.0))
    out = site_card.with_supply(caps, (("Desc_Water_C", 240.0),))
    assert [(c.item_id, c.rate_per_min) for c in out] == [(IRON, 60.0), ("Desc_Water_C", 240.0)]
    with pytest.raises(site_card.SiteCardError, match="not a raw resource"):
        site_card.with_supply(caps, (("Desc_IronPlate_C", 1.0),))
    with pytest.raises(site_card.SiteCardError, match="must be positive"):
        site_card.with_supply(caps, (("Desc_Water_C", 0.0),))


# -- acceptance A: an Oil site limited by Copper --------------------------------

def test_a_oil_site_caps(card_a):
    caps = {c.item_id: c.rate_per_min for c in card_a.caps if c.rate_per_min > 0.0}
    assert caps == {OIL: 1020.0, COAL: 240.0, IRON: 360.0, COPPER: 30.0, STONE: 60.0}
    assert [n.item_id for n in card_a.nodes if n.item_id == COPPER] == [COPPER]
    assert card_a.status == "material_bound"


def test_a_plastic_is_strong_on_oil(card_a):
    plastic = _opp(card_a, "Desc_Plastic_C")
    assert plastic.ceiling_per_min == pytest.approx(680.0, abs=1e-4)
    assert _limits(plastic) == [OIL]


def test_a_computers_are_limited_by_copper(card_a):
    computer = _opp(card_a, "Desc_Computer_C")
    assert computer.ceiling_per_min == pytest.approx(1.25, abs=1e-4)
    assert _limits(computer) == [COPPER]
    copper = next(u for u in computer.caps if u.item_id == COPPER)
    assert copper.shadow_price > 0.0
    oil = next(u for u in computer.caps if u.item_id == OIL)
    assert oil.residual_per_min > 900.0


def test_a_final_plan_decides_binding_not_the_first_vertex(card_a):
    """Iron Plate draws no Crude Oil; the first-stage vertex can (FREE leftover)."""
    plate = _opp(card_a, "Desc_IronPlate_C")
    assert _limits(plate) == [IRON]
    assert next(u for u in plate.caps if u.item_id == OIL).draw_per_min == pytest.approx(0.0, abs=1e-6)


# -- acceptance B: a mixed Iron / Coal / Limestone / Caterium site --------------

def test_b_lists_several_products_each_with_its_own_limit(card_b):
    limits = {o.item_id: _limits(o) for o in card_b.opportunities}
    assert limits["Desc_SteelPipe_C"] == [IRON]
    assert limits["Desc_Cement_C"] == [STONE]
    assert limits["Desc_SteelPlateReinforced_C"] == [STONE]
    assert limits["Desc_HighSpeedWire_C"] == [CATERIUM]
    assert len(card_b.opportunities) == 16
    assert not [o for o in card_b.opportunities if o.error is not None]


def test_b_ceilings_are_alternatives_and_none_overdraws(card_b):
    assert card_b.ceilings_are_alternatives
    for o in card_b.opportunities:
        for u in o.caps:
            assert u.draw_per_min <= u.cap_per_min + 1e-6, (o.item_id, u.item_id)


def test_b_motor_needs_copper(card_b):
    motor = next(u for u in card_b.unreachable if u.item_id == "Desc_Motor_C")
    assert motor.missing_raws == (COPPER,)


def test_b_motor_is_opened_by_any_of_three_single_alternates(card_b):
    """Greg, 2026-10-19: Motor is makeable here with wire from an alternate.
    Rigor Motor and Electric Motor still need a Stator (directly or through
    the Electromagnetic Control Rod), so neither opens it alone."""
    motor = next(u for u in card_b.unreachable if u.item_id == "Desc_Motor_C")
    assert motor.opened_by == (
        ("Recipe_Alternate_Wire_2_C", site_card.MAM_RESEARCH),   # Caterium Wire
        ("Recipe_Alternate_Wire_1_C", site_card.POOL_NOW),       # Iron Wire
        ("Recipe_Alternate_Stator_C", site_card.MAM_RESEARCH),   # Quickwire Stator
    )


def test_b_copper_ingot_has_no_alternate_way_in(card_b):
    copper = next(u for u in card_b.unreachable if u.item_id == "Desc_CopperIngot_C")
    assert copper.missing_raws == (COPPER,) and copper.opened_by == ()


def test_b_hints_are_not_computed_from_held_recipes(card_b):
    held = set(card_b.declared_recipes)
    assert not [r for u in card_b.unreachable for r, _ in u.opened_by if r in held]


def test_b_pool_comparison_held_beside_obtainable(card_b, card_b_pool):
    """Measured 2026-10-19 (container): with this tier's 24 automatic pool
    alternates added, Motor goes from not makeable to 25.35/min; Concrete,
    Quickwire and Caterium Ingot are unchanged."""
    assert card_b.pool_opportunities is None
    held = {o.item_id: o.ceiling_per_min for o in card_b_pool.opportunities}
    pool = {o.item_id: o.ceiling_per_min for o in card_b_pool.pool_opportunities}
    assert held == {o.item_id: o.ceiling_per_min for o in card_b.opportunities}
    assert "Desc_Motor_C" not in held
    assert pool["Desc_Motor_C"] == pytest.approx(25.35, abs=1e-3)
    for item in ("Desc_Cement_C", "Desc_HighSpeedWire_C", "Desc_GoldIngot_C"):
        assert pool[item] == pytest.approx(held[item], rel=1e-6), item
    assert len(card_b_pool.pool_added) == 24
    assert not set(card_b_pool.pool_added) & set(card_b_pool.declared_recipes)


def test_b_report_says_the_ceilings_are_not_additive(card_b):
    from production_adapter import load
    text = site_card.report(card_b, load(REPO))
    assert "alternatives, not additive" in text
    assert "not assessed: power" in text


# -- guardrails -----------------------------------------------------------------

def test_a_product_no_recipe_makes_refuses(sockets):
    spec = _spec_around(sockets, *SITE_B, "B")
    with pytest.raises(site_card.SiteCardError, match="no recipe enabled at tier 4"):
        site_card.build_card(
            spec, tier=4, scenario=Scenario(), goal="balanced",
            power_statistic=PowerStatistic.MEAN, products=("Desc_Computer_C",),
        )


def test_the_card_cannot_choose():
    """No min, max or sort: the card lists, it does not rank (AGENTS.md)."""
    tree = ast.parse(inspect.getsource(site_card))
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    called |= {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert {"min", "max", "sorted", "sort"}.isdisjoint(called)
