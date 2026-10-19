"""tools/portfolio_run.py: spec v1.0 (proposed) §10 C on the default world.

Oil site: 16 sockets within 500 m of BP_ResourceNode98 (5 Oil nodes, 1 impure
Copper). Copper site: 19 sockets within 500 m of BP_ResourceNode213 (Iron,
Copper, Coal, Limestone, Sulfur; no Oil). Tier 6, canonical scenario, Miner
Mk.1 / Oil Extractor at 100 %. Bill: Project Assembly phase 3 + milestones of
tiers 5 and 6 (A31 composition). Measured 2026-10-19, container, py3.13:

    together      0.003499 bill/min      oil alone 0.000704
    copper alone  infeasible: no oil, and Coal generators need Water nobody
                  declared, so its 95 MW of miners cannot run
    oil site      makes Plastic, Rubber, Computer, Adaptive Control Unit;
                  builds 6.528 Fuel generators (1632 MW) on ~131 Fuel/min
    copper site   makes Motor, Copper Sheet; ships Motor and Automated
                  Wiring to the oil site; receives nothing; no generators
    power         one shared grid (A3): tight but not limiting (shadow 0);
                  Coal binds at both sites; oil draws ~265 of 1020/min

No three-role partition is declared anywhere: the placement is the solve's.
"""
from __future__ import annotations

import ast
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
    assert alone["copper"].startswith("infeasible: cannot power its own extractors")


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
    assert 250.0 < draw[OIL] < 300.0


def test_c_idle_oil_powers_both_sites(run_c):
    assert run_c.generators_open == (
        "Build_GeneratorBiomass_Automated_C", "Build_GeneratorCoal_C", "Build_GeneratorFuel_C")
    oil, copper = run_c.response.sites
    assert [(u.generator_class, u.fuel_item_id) for u in oil.generators] == [
        ("Build_GeneratorFuel_C", "Desc_LiquidFuel_C")]
    assert oil.generators[0].count == pytest.approx(6.528, rel=1e-3)
    assert copper.generators == ()
    pw = run_c.response.power
    assert pw.generated_mw == pytest.approx(pw.lane_mw + pw.extraction_mw, rel=1e-6)
    assert pw.extraction_mw == pytest.approx(380.0, rel=1e-9)
    assert pw.shadow_price == pytest.approx(0.0, abs=1e-12)


def test_c_report_states_power_and_the_volume_assumption(run_c):
    from production_adapter import load
    text = portfolio_run.report(run_c, load(REPO))
    assert "one shared grid (A3)" in text and "one item as one m3" in text
    assert "tight, not limiting" in text and "copper alone: infeasible" in text


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
