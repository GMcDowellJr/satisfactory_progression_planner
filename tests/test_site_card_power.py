"""tools/site_card.py: the self-powered column beside the material one
(Greg, 2026-10-19: "add power to site card", "both, side by side").

Site: 19 sockets within 500 m of BP_ResourceNode213 (Iron, Copper, Coal,
Limestone, Sulfur; no Oil), Miner Mk.1 at 100 %, tier 4 (Biomass and Coal
generators open), canonical scenario. Measured 2026-10-19, container, py3.13:

    Water pumpable     Iron Plate 400 = 400 material (ore-bound; +1/min ore
                       -> +2/3 Plate both columns); Steel Ingot 162.34 of
                       180 (Coal burns for power: +1/min Coal -> +0.9019,
                       grid LIMITING); Motor 9.907 of 19.05
    no Water, no grid  every self-powered ceiling 0: no power source
    5000 MW grid       self-powered = material for all three
"""
from __future__ import annotations

import dataclasses
import importlib.util
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
# one module object per process, shared with tests/test_site_card.py
_spec = importlib.util.spec_from_file_location("site_card", REPO / "tools" / "site_card.py")
site_card = sys.modules.get("site_card") or importlib.util.module_from_spec(_spec)
if "site_card" not in sys.modules:
    sys.modules["site_card"] = site_card
    _spec.loader.exec_module(site_card)

from production_adapter import Scenario  # noqa: E402
from production_adapter.lp_backend import PowerStatistic  # noqa: E402

PLATE, STEEL, MOTOR = "Desc_IronPlate_C", "Desc_SteelIngot_C", "Desc_Motor_C"
IRON, COAL = "Desc_OreIron_C", "Desc_Coal_C"
MINERS = ((("resource_node", None), "Build_MinerMk1_C"),)


@pytest.fixture(scope="module")
def spec():
    sockets = site_card.load_sockets(REPO, "default_502094")
    c = next(s for s in sockets if s.socket_id == "BP_ResourceNode213")
    return site_card.SiteSpec("coal", site_card.sockets_within(sockets, c.east_m, c.north_m, 500.0),
                              MINERS, 1.0)


def _card(spec, **kw):
    return site_card.build_card(
        spec, tier=4, scenario=Scenario(), goal="balanced", power_statistic=PowerStatistic.MEAN,
        products=(PLATE, STEEL, MOTOR), **kw,
    )


@pytest.fixture(scope="module")
def wet(spec):
    return _card(spec, water=True)


def _opp(card, item):
    return next(o for o in card.opportunities if o.item_id == item)


def test_an_ore_bound_product_loses_nothing_to_power(wet):
    o = _opp(wet, PLATE)
    assert o.powered.ceiling_per_min == pytest.approx(o.ceiling_per_min, rel=1e-6) == pytest.approx(400.0)
    [iron] = [u for u in o.powered.caps if u.binding]
    assert iron.item_id == IRON and iron.shadow_price == pytest.approx(2.0 / 3.0, rel=1e-6)
    assert [g.generator_class for g in o.powered.generators] == ["Build_GeneratorCoal_C"]
    assert dict(o.powered.pumped)["Desc_Water_C"] > 0.0


def test_steel_pays_for_its_power_in_coal(wet):
    """Coal feeds the Foundry and the generators: the self-powered ceiling is
    under the material one and the grid limits it."""
    o = _opp(wet, STEEL)
    assert o.ceiling_per_min == pytest.approx(180.0, rel=1e-6)
    assert o.powered.ceiling_per_min == pytest.approx(162.337, rel=1e-4)
    [coal] = [u for u in o.powered.caps if u.binding]
    assert coal.item_id == COAL and coal.shadow_price == pytest.approx(0.9019, rel=1e-3)
    assert o.powered.grid.binding and o.powered.grid.shadow_price > 0.0
    assert _opp(wet, MOTOR).powered.ceiling_per_min == pytest.approx(9.907, rel=1e-3)


def test_without_water_or_grid_nothing_is_self_powered(spec):
    card = _card(spec)
    for o in card.opportunities:
        assert o.ceiling_per_min > 0.0 and o.powered.ceiling_per_min == 0.0, o.item_id
    text = site_card.report(card, site_card.load(REPO))
    assert "no power source here (+10 MW -> +" in text
    assert "no Water (none declared pumpable)" in text


def test_a_standing_grid_closes_the_gap(spec):
    for o in _card(spec, grid_mw=5000.0).opportunities:
        assert o.powered.ceiling_per_min == pytest.approx(o.ceiling_per_min, rel=1e-6), o.item_id


def test_the_report_reads_in_plain_language(wet):
    text = site_card.report(wet, site_card.load(REPO))
    assert "+1/min Coal -> +0.9019 Steel Ingot/min at the margin" in text
    assert "power LIMITS it (+10 MW -> +2.042 Steel Ingot/min at the margin)" in text
    assert "Water pumped here, CONDITIONAL on the declaration" in text
    assert "'at the margin'" in text and "shadow " not in text


def test_a_free_water_supply_is_refused(spec):
    wet_supply = dataclasses.replace(spec, supply=(("Desc_Water_C", 240.0),))
    with pytest.raises(site_card.SiteCardError, match="never free"):
        _card(wet_supply)


def test_an_overclock_keeps_the_material_column_and_says_why_not_the_other(spec):
    card = _card(dataclasses.replace(spec, extraction_clock=1.5))
    assert card.powered_error is not None and "above 100 %" in card.powered_error
    assert all(o.powered is None and o.ceiling_per_min > 0.0 for o in card.opportunities)
