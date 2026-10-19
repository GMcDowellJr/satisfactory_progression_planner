"""One power implementation (site_planner_reframe.md Amendment 6, Greg
2026-10-19: "we should have shared modules for stuff like this").

    solver     the extraction columns live in _build_core: a district solve
               and a one-site portfolio with the same segments give the same
               scale (spec §10 I), and a district price reads from segments
    composer   progression.site_extraction / pumped_caps / generators_at_tier
               / extraction_at_share, for every tool
    tripwire   the tools at tools/ root do not assemble extraction or
               generator sets themselves, and none passes a constant
               nameplate charge (A4, A6): a fourth copy would fail here
    refuses    district_run without WATER_PUMPABLE; standing generators fed
               from the district's caps in solve mode; extraction segments
               on a DistrictRequest without a grid
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys
import types

import pytest

from production_adapter import (
    AllowedRecipes, DistrictRequest, DistrictTarget, ExtractionSegment, PortfolioRequest,
    PortfolioSite, PowerBalance, RecipeMode, ResourceCap, load,
)
from production_adapter.gamedata import load_generators
from production_adapter.lp_backend import LpBackend, PowerStatistic
from progression import DistrictError, extraction_at_share, generators_at_tier

REPO = pathlib.Path(__file__).resolve().parents[1]
IRON, COAL, WATER, PLATE = "Desc_OreIron_C", "Desc_Coal_C", "Desc_Water_C", "Desc_IronPlate_C"
PLATES = AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=("Recipe_IngotIron_C", "Recipe_IronPlate_C"))
MK1, PUMP = 5.0 / 60.0, 20.0 / 120.0


@pytest.fixture(scope="module")
def data():
    return load(REPO)


def _caps(data, **rates):
    return tuple(ResourceCap(i, rates[i] if i in rates else 0.0)
                 for i in data.items if i in data.resource_items)


def _seg(item, cap, mw):
    return ExtractionSegment(item, cap, mw, None if cap is None else cap * mw)


def _coal_power():
    rows = tuple(g for g in load_generators(REPO)
                 if g.generator_class == "Build_GeneratorCoal_C" and g.fuel_item_id == COAL)
    return PowerBalance(generators=rows)


def test_district_and_one_site_portfolio_agree_with_extraction(data):
    """Same caps, segments, generator and bill: (75 - 1.25 - 7.5) / 0.525 =
    126.19 Plate/min in both (test_extraction_draw derives it), and the ore
    price from the segment in both."""
    caps = _caps(data, **{IRON: 300.0, COAL: 15.0, WATER: None})
    segs = (_seg(IRON, 300.0, MK1), _seg(COAL, 15.0, MK1), _seg(WATER, None, PUMP))
    backend = LpBackend(power_statistic=PowerStatistic.MEAN)
    d = backend.solve_district(DistrictRequest(
        (DistrictTarget(PLATE, bill_units=1.0),), PLATES, caps, power=_coal_power(), extraction=segs,
    ), data)
    p = backend.solve_portfolio(PortfolioRequest(
        (PortfolioSite("s", caps, segs),), ((PLATE, 1.0),), PLATES, power=_coal_power(),
    ), data)
    assert d.scale == pytest.approx(66.25 / 0.525, rel=1e-6)
    assert d.scale == pytest.approx(p.scale, rel=1e-9)
    assert d.power.extraction_mw == pytest.approx(p.power.extraction_mw, rel=1e-6)
    assert d.power.extraction_nameplate_mw == pytest.approx(26.25, rel=1e-9)
    assert d.power.pumped == ((WATER, pytest.approx(45.0, rel=1e-6)),)


def test_a_district_request_with_segments_needs_a_grid(data):
    with pytest.raises(ValueError, match="power is None"):
        DistrictRequest((DistrictTarget(PLATE, weight=1.0),), PLATES, _caps(data, **{IRON: 60.0}),
                        extraction=(_seg(IRON, 60.0, MK1),))


def test_extraction_at_share_reads_every_socket_alike():
    """Pure 120 at 5/120 and impure 30 at 5/30: 75 of 150 drawn is half of
    each, 2.5 + 2.5 = 5 MW, choosing no socket. Pumped: on the whole draw."""
    segs = (ExtractionSegment(IRON, 120.0, 5.0 / 120.0, 5.0), ExtractionSegment(IRON, 30.0, 5.0 / 30.0, 5.0),
            _seg(WATER, None, PUMP))
    assert extraction_at_share(segs, {IRON: 75.0, WATER: 60.0}) == pytest.approx(5.0 + 10.0)
    with pytest.raises(DistrictError, match="two pumped"):
        extraction_at_share((_seg(WATER, None, PUMP), _seg(WATER, None, PUMP)), {WATER: 1.0})


def test_the_scenario_multiplier_reaches_extractors():
    """A7 (Greg, 2026-10-19): the machine-power multiplier applies to
    extractors and pumps: MW per unit, nameplate and the pumped charge all
    scale by it; caps do not."""
    from production_adapter import Scenario
    from production_adapter.gamedata import load_logistics
    from progression import DistrictDefinition, NodeCount, nameplate_mw, site_extraction
    from progression.power import load_power_tables
    _, rates = load_logistics(REPO)
    base = load_power_tables(REPO).extractors
    d = DistrictDefinition((NodeCount(IRON, "normal", 2),), "Build_MinerMk1_C", 1.0)
    one = site_extraction(d, rates, base, scenario=Scenario(), water=True)
    five = site_extraction(d, rates, base, scenario=Scenario(machine_power_multiplier=5.0), water=True)
    assert [e.cap_per_min for e in five] == [e.cap_per_min for e in one] == [120.0, None]
    assert [e.mw_per_unit for e in five] == pytest.approx([5.0 * e.mw_per_unit for e in one])
    assert nameplate_mw(one) == 10.0 and nameplate_mw(five) == 50.0
    assert five[1].mw_per_unit == pytest.approx(5.0 * PUMP)


def test_generators_at_tier_is_the_a3_join():
    assert generators_at_tier(REPO, 4)[0] == ("Build_GeneratorBiomass_Automated_C", "Build_GeneratorCoal_C")
    classes, rows = generators_at_tier(REPO, 6)
    assert "Build_GeneratorFuel_C" in classes and {g.generator_class for g in rows} == set(classes)


TOOLS = ("site_card", "portfolio_run", "district_run")
#: assembled once, in progression (A6); a tool naming one assembles its own
ASSEMBLERS = {"extraction_segments", "pumped_water", "generators_open_at_tier"}
#: also refused as an import or bare name (A7: nameplate comes from the
#: scaled segments); as an attribute it is a response field of the same name
UNSCALED = {"extraction_nameplate_mw"}


@pytest.mark.parametrize("tool", TOOLS)
def test_the_tools_do_not_assemble_power_themselves(tool):
    tree = ast.parse((REPO / "tools" / f"{tool}.py").read_text(encoding="utf-8"))
    bare = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    bare |= {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    named = bare | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert ASSEMBLERS.isdisjoint(named), ASSEMBLERS & named
    assert UNSCALED.isdisjoint(bare), UNSCALED & bare
    constant = [k for n in ast.walk(tree) if isinstance(n, ast.Call)
                and getattr(n.func, "id", getattr(n.func, "attr", None)) == "PowerBalance"
                for k in n.keywords if k.arg == "extraction_mw"]
    assert constant == [], f"{tool} passes a constant nameplate charge"


# -- district_run refusals --------------------------------------------------------

def _district_run():
    spec = importlib.util.spec_from_file_location("district_run", REPO / "tools" / "district_run.py")
    mod = sys.modules.get("district_run") or importlib.util.module_from_spec(spec)
    if "district_run" not in sys.modules:
        sys.modules["district_run"] = mod
        spec.loader.exec_module(mod)
    return mod


def _decl_with(**changes):
    dr = _district_run()
    base = dr.declaration("district_phase2")
    decl = types.ModuleType("decl_copy")
    decl.__dict__.update({k: v for k, v in vars(base).items() if not k.startswith("__")})
    for k, v in changes.items():
        if v is None:
            delattr(decl, k)
        else:
            setattr(decl, k, v)
    return dr, decl


def test_district_run_needs_water_pumpable_declared():
    dr, decl = _decl_with(WATER_PUMPABLE=None)
    with pytest.raises(dr.DistrictRunError, match="WATER_PUMPABLE"):
        dr.run(decl, case="shipped", realization=False)


def test_standing_fed_from_the_caps_is_refused_in_solve_mode():
    """No standing generators, so caps_less_draws has nothing to refuse and
    the A6 refusal is what answers (the declared 4 Coal generators would be
    refused earlier: their Water has no cap here)."""
    dr, decl = _decl_with(STANDING_FED_FROM_DISTRICT=True, STANDING_GENERATORS=())
    with pytest.raises(dr.DistrictRunError, match="not modelled"):
        dr.run(decl, case="shipped", realization=False)
