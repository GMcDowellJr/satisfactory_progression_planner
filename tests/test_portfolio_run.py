"""tools/portfolio_run.py: spec v1.0 (proposed) §10 C on the default world.

Oil site: 16 sockets within 500 m of BP_ResourceNode98 (5 Oil nodes, 1 impure
Copper). Copper site: 19 sockets within 500 m of BP_ResourceNode213 (Iron,
Copper, Coal, Limestone, Sulfur; no Oil). Tier 6, canonical scenario, Miner
Mk.1 / Oil Extractor at 100 %. Bill: Project Assembly phase 3 + milestones of
tiers 5 and 6 (A31 composition). Measured 2026-10-19, container, py3.13,
extraction by the draw (A4; no site pumps Water):

    together      0.003499 bill/min      oil alone 0.000704
    copper alone  0.0: it cannot make Plastic, Rubber, Computer, Modular
                  Engine or Adaptive Control Unit without Oil (under A25.3
                  P2's constant it was "infeasible", which hid this)
    oil site      makes Plastic, Rubber, Computer, Adaptive Control Unit;
                  builds 5.515 Fuel generators (1379 MW) on ~110 Fuel/min
    copper site   makes Motor, Copper Sheet; ships Motor and Automated
                  Wiring to the oil site; receives nothing; no generators
    power         one shared grid (A3): tight but not limiting (shadow 0);
                  extractors 141.9 MW drawn of 380 MW nameplate; Coal binds
                  at both sites; oil draws ~234 of 1020/min

Scenario D (spec §10 D, Coal to steel vs Coal to power): the copper site
alone, tier 4, bill phase 2 + tiers 3-4, measured the same day:

    Water declared pumpable   0.003770/min; 72.4 of 180 Coal/min burned in
                              4.82 Coal generators, 217 m3/min pumped; power
                              LIMITING; the alternative is labelled
                              CONDITIONAL on the Water declaration
    no Water, no grid         0.0: no power source
    no Water, 5000 MW grid    0.006305/min: every Coal to steel

No three-role partition is declared anywhere: the placement is the solve's.
"""
from __future__ import annotations

import ast
import dataclasses
import importlib.util
import inspect
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


def _module(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


site_card = _module("site_card")
portfolio_run = _module("portfolio_run")

from production_adapter import Scenario  # noqa: E402

OIL, COAL, CU = "Desc_LiquidOil_C", "Desc_Coal_C", "Desc_OreCopper_C"
MINERS = (
    (("resource_node", None), "Build_MinerMk1_C"),
    (("resource_node", OIL), "Build_OilPump_C"),
)


def _spec(sockets, label, centre_id, radius):
    c = next(s for s in sockets if s.socket_id == centre_id)
    return site_card.SiteSpec(
        label=label, socket_ids=site_card.sockets_within(sockets, c.east_m, c.north_m, radius),
        extractors=MINERS, extraction_clock=1.0,
    )


@pytest.fixture(scope="module")
def specs():
    sockets = site_card.load_sockets(REPO, "default_502094")
    return (
        _spec(sockets, "oil", "BP_ResourceNode98", 500.0),
        _spec(sockets, "copper", "BP_ResourceNode213", 500.0),
    )


@pytest.fixture(scope="module")
def run_c(specs):
    return portfolio_run.run(
        specs, tier=6, scenario=Scenario(), goal="balanced", bill_phases=(3,), bill_tiers=(5, 6),
    )


def _made(run, label):
    return dict(next(s for s in run.response.sites if s.label == label).delivered)


def test_c_together_beats_either_site_alone(run_c):
    assert run_c.response.scale == pytest.approx(0.003499, rel=1e-3)
    alone = dict(run_c.alone)
    assert alone["oil"] == pytest.approx(0.000704, rel=1e-3)
    assert alone["copper"] == 0.0
    assert dict(run_c.alone_blocked)["copper"] == (
        "Desc_SpaceElevatorPart_4_C", "Desc_SpaceElevatorPart_5_C", "Desc_Plastic_C",
        "Desc_Rubber_C", "Desc_Computer_C")
    assert dict(run_c.alone_blocked)["oil"] == ()


def test_c_oil_products_are_made_at_the_oil_site(run_c):
    oil, copper = _made(run_c, "oil"), _made(run_c, "copper")
    for item in ("Desc_Plastic_C", "Desc_Rubber_C", "Desc_Computer_C", "Desc_SpaceElevatorPart_5_C"):
        assert item in run_c.bill, item
        assert item in oil and item not in copper, item


def test_c_the_copper_site_supplies_the_oil_site(run_c):
    sent = {(t.source, t.destination, t.item_id) for t in run_c.response.transfers}
    assert ("copper", "oil", "Desc_Motor_C") in sent
    assert not [t for t in run_c.response.transfers if t.source == "oil"]


def test_c_coal_binds_at_both_and_oil_is_left_over(run_c):
    for site in run_c.response.sites:
        assert COAL in [b.item_id for b in site.binding], site.label
    oil = next(s for s in run_c.response.sites if s.label == "oil")
    draw = {x.item_id: x.rate_per_min for x in oil.plan.raw_inputs}
    assert 220.0 < draw[OIL] < 250.0


def test_c_idle_oil_powers_both_sites(run_c):
    assert run_c.generators_open == (
        "Build_GeneratorBiomass_Automated_C", "Build_GeneratorCoal_C", "Build_GeneratorFuel_C")
    oil, copper = run_c.response.sites
    assert [(u.generator_class, u.fuel_item_id) for u in oil.generators] == [
        ("Build_GeneratorFuel_C", "Desc_LiquidFuel_C")]
    assert oil.generators[0].count == pytest.approx(5.515, rel=1e-3)
    assert copper.generators == ()
    pw = run_c.response.power
    assert pw.generated_mw == pytest.approx(pw.lane_mw + pw.extraction_mw, rel=1e-6)
    assert pw.shadow_price == pytest.approx(0.0, abs=1e-12)


def test_c_extraction_is_charged_by_the_draw_with_nameplate_beside_it(run_c):
    """A4: 19 + 16 sockets, Mk.1 5 MW and Oil Extractor 40 MW, 380 MW at
    nameplate; the plan draws 141.9 of it. Each site's draw is under its own
    nameplate, and the grid's figures are the sites' sums."""
    pw = run_c.response.power
    assert pw.extraction_nameplate_mw == pytest.approx(380.0, rel=1e-9)
    assert pw.extraction_mw == pytest.approx(141.885, rel=1e-3)
    for site in run_c.response.sites:
        assert 0.0 < site.extraction_mw < site.extraction_nameplate_mw, site.label
        assert site.pumped == ()
    assert pw.extraction_mw == pytest.approx(sum(s.extraction_mw for s in run_c.response.sites), rel=1e-9)


def test_c_report_states_power_and_the_volume_assumption(run_c):
    from production_adapter import load
    text = portfolio_run.report(run_c, load(REPO))
    assert "one shared grid (A3)" in text and "one item as one m3" in text
    assert "tight, not limiting" in text and "drawn (nameplate 380.0)" in text
    assert "copper alone: 0.000000/min; cannot make alone: Modular Engine" in text


# -- scenario D: Coal to steel vs Coal to power (spec §10 D) -------------------

@pytest.fixture(scope="module")
def coal_site(specs):
    return dataclasses.replace(specs[1], label="coal")


def _run_d(coal_site, **kw):
    return portfolio_run.run(
        (coal_site,), tier=4, scenario=Scenario(), goal="balanced", bill_phases=(2,),
        bill_tiers=(3, 4), **kw,
    )


@pytest.fixture(scope="module")
def run_d(coal_site):
    return _run_d(coal_site, water_sites=("coal",))


def test_d_coal_splits_between_steel_and_power(run_d):
    """With Water declared pumpable, the only power at tier 4 is Coal: the
    solve burns part of the 180 Coal/min and makes steel with the rest, and
    the grid is the limit (shadow > 0)."""
    r = run_d.response
    assert r.scale == pytest.approx(0.003770, rel=1e-3)
    site = r.sites[0]
    assert COAL in [b.item_id for b in site.binding]
    [gen] = site.generators
    assert (gen.generator_class, gen.fuel_item_id) == ("Build_GeneratorCoal_C", COAL)
    assert 0.0 < gen.fuel_per_min < 180.0
    assert gen.fuel_per_min == pytest.approx(72.36, rel=1e-3)
    pumped = dict(site.pumped)["Desc_Water_C"]
    assert pumped == pytest.approx(3.0 * gen.fuel_per_min, rel=1e-6)   # 45 Water per 15 Coal
    assert r.power.binding and r.power.shadow_price > 0.0


def test_d_without_water_or_grid_nothing_runs(coal_site):
    r = _run_d(coal_site).response
    assert r.scale == 0.0 and r.sites[0].generators == ()


def test_d_a_standing_grid_sends_every_coal_to_steel(coal_site, run_d):
    """The bounded comparison spec D asks for: the same site with power from
    outside makes more of the bill than one that burns its own Coal."""
    r = _run_d(coal_site, grid_mw=5000.0).response
    assert r.sites[0].generators == ()
    assert r.scale == pytest.approx(0.006305, rel=1e-3)
    assert r.scale > run_d.response.scale


def test_d_report_labels_the_water_power_conditional(run_d):
    from production_adapter import load
    text = portfolio_run.report(run_d, load(REPO))
    assert "Water: DECLARED pumpable here, not verified by world data" in text
    assert "CONDITIONAL" in text and "LIMITING" in text and "pumped Water:" in text


def test_d_report_names_power_when_nothing_runs(coal_site):
    from production_adapter import load
    text = portfolio_run.report(_run_d(coal_site), load(REPO))
    assert "the grid holds every machine at 0: no power source" in text


@pytest.mark.parametrize("kw, match", [
    ({"water_sites": ("nowhere",)}, "not declared"),
    ({"water_sites": ("coal", "coal")}, "twice"),
])
def test_water_declarations_it_cannot_use_refuse(coal_site, kw, match):
    with pytest.raises(portfolio_run.PortfolioRunError, match=match):
        _run_d(coal_site, **kw)


def test_a_free_water_supply_is_refused(coal_site):
    """A4: Water is never free; the old --supply route is closed by name."""
    wet = dataclasses.replace(coal_site, supply=(("Desc_Water_C", 240.0),))
    with pytest.raises(portfolio_run.PortfolioRunError, match="never free"):
        _run_d(wet)


def test_a_socket_in_two_sites_refuses(specs):
    twice = site_card.SiteSpec("oil again", specs[0].socket_ids[:1], MINERS, 1.0)
    with pytest.raises(portfolio_run.PortfolioRunError, match="owned once"):
        portfolio_run.run((specs[0], twice), tier=6, scenario=Scenario(), goal="balanced",
                          bill_phases=(3,), bill_tiers=())


def test_an_unknown_phase_refuses(specs):
    with pytest.raises(portfolio_run.PortfolioRunError, match="no Project Assembly phase"):
        portfolio_run.run(specs[:1], tier=6, scenario=Scenario(), goal="balanced",
                          bill_phases=(9,), bill_tiers=())


def test_the_run_cannot_choose():
    """No min, max or sort: sites, bill items and transfers keep their order."""
    tree = ast.parse(inspect.getsource(portfolio_run))
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    called |= {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert {"min", "max", "sorted", "sort"}.isdisjoint(called)
