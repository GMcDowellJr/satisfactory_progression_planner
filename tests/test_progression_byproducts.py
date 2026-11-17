"""By-product ledger (reframe A16, decided by Greg 2026-11-17): by-products
feed production where the solve finds that useful, and what is left goes to
the AWESOME Sink by default. Solids only; fluids are named, not sunk."""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

from production_adapter import load
from production_adapter.contracts import ItemFlow
from progression import playthrough
from progression.byproducts import (
    FLUID_NO_SINK, SINK, SINK_NOT_UNLOCKED, ledger, sink_unlocked,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
RESIN = "Desc_PolymerResin_C"      # solid, 12 sink points
HOR = "Desc_HeavyOilResidue_C"     # liquid
PLASTIC = "Desc_Plastic_C"


@pytest.fixture(scope="module")
def data():
    return load(REPO)


def test_the_sink_opens_with_its_milestone():
    assert not sink_unlocked(REPO, playthrough(REPO, through_tier=1))
    assert sink_unlocked(REPO, playthrough(REPO, through_tier=2))


def test_each_leftover_gets_its_disposition(data):
    flows = (ItemFlow(RESIN, 30.0, 10.0), ItemFlow(HOR, 20.0, 5.0),
             ItemFlow(PLASTIC, 40.0, 0.0))
    late = ledger(REPO, data, playthrough(REPO, through_tier=5), flows, {PLASTIC: 40.0})
    assert [(b.item_id, b.rate_per_min, b.disposition) for b in late] == [
        (HOR, 15.0, FLUID_NO_SINK), (RESIN, 20.0, SINK)]
    resin = next(b for b in late if b.item_id == RESIN)
    assert resin.sink_points_per_min == pytest.approx(20.0 * 12)
    early = ledger(REPO, data, playthrough(REPO, through_tier=1), flows[:1], {})
    assert early[0].disposition == SINK_NOT_UNLOCKED and early[0].sink_points_per_min is None


def test_what_is_consumed_or_delivered_is_not_a_by_product(data):
    flows = (ItemFlow(RESIN, 10.0, 10.0), ItemFlow(PLASTIC, 40.0, 0.0))
    assert ledger(REPO, data, playthrough(REPO, through_tier=5), flows, {PLASTIC: 40.0}) == ()


def test_the_factory_track_reports_its_by_products():
    spec = importlib.util.spec_from_file_location("factory_run", REPO / "tools" / "factory_run.py")
    F = sys.modules.get("factory_run") or importlib.util.module_from_spec(spec)
    if "factory_run" not in sys.modules:
        sys.modules["factory_run"] = F
        spec.loader.exec_module(F)
    doc = {
        "schema": "factory-inputs/1", "world_config_id": "default_502094",
        "playthrough": {"through_tier": 5, "milestones": [], "research": [], "alternates": []},
        "scenario": {"recipe_input_multiplier": 1.0, "machine_power_multiplier": 1.0,
                     "project_assembly_requirement_multiplier": 1.0, "fluid_input_floor": None,
                     "fluid_rounding_unit": "mL"},
        "site": {"label": "oil", "socket_ids": ["BP_ResourceNode100", "BP_ResourceNode14_609"],
                 "supply": [], "pumps_water": False},
        "goal_mix": [{"item_id": PLASTIC, "units": 1}], "goal": "balanced",
        "power_mode": "report_need", "grid_mw": 0.0, "spare_mw": 0.0, "target_scale": None,
        "infrastructure_policy": "highest_then_step_down",
    }
    run = F.run_inputs(doc)
    assert [(b.item_id, b.disposition) for b in run.byproducts] == [(HOR, FLUID_NO_SINK)]
    assert F.record(run)["byproducts"][0]["disposition"] == FLUID_NO_SINK
