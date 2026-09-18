"""Fixed-recipe power and machine-count expectations.

Plan section 11's validation set, the half the demand oracle does not cover.
`test_demand_oracle.py` already pins multipliers and raw inputs; this module pins
what those multipliers imply for power and machines, so a production backend has
an independent reference to be checked against before it is trusted.

Every case here is fixed-recipe. None of them depends on D1 (unconsumed output),
D2 (power statistic), D3 (tie-breaking) or D4 (cycles), which is why they can be
written while those decisions are open — see
docs/decisions/production_lp_formulation.md.
"""
import pytest

from _demand_oracle import demand
from _fixed_recipe_expectations import expectations

IRON_PLATE = "Desc_IronPlate_C"
SMART_PLATING = "Desc_SpaceElevatorPart_1_C"
IRON_ORE = "Desc_OreIron_C"

# Candidate A's hardcoded extraction path, reproduced only to reconstruct the
# Phase 0 figures. Not a model of extraction — see D5, extraction is outside the LP.
_YAFP_MINER_MK3_MW = 45.0
_YAFP_MINER_MK3_DIVISOR = 240.0


def _yafp_extraction_mw(ore_per_min: float) -> float:
    return ore_per_min / _YAFP_MINER_MK3_DIVISOR * _YAFP_MINER_MK3_MW


# --- Iron Plate 20/min ----------------------------------------------------

def test_iron_plate_power_and_machines():
    e = expectations(demand(IRON_PLATE, 20.0).recipe_multipliers)
    assert e.power.mean_mw == pytest.approx(8.0)
    assert e.machines_by_display_name == pytest.approx({"Smelter": 1.0, "Constructor": 1.0})


def test_iron_plate_power_is_unambiguous():
    """Every producer in this chain is fixed-power, so D2 cannot change the answer."""
    e = expectations(demand(IRON_PLATE, 20.0).recipe_multipliers)
    assert e.power.is_degenerate
    assert e.power.min_mw == pytest.approx(8.0)
    assert e.power.max_mw == pytest.approx(8.0)


# --- Smart Plating 1/min --------------------------------------------------

def test_smart_plating_power_and_machines():
    e = expectations(demand(SMART_PLATING, 1.0).recipe_multipliers)
    assert e.power.mean_mw == pytest.approx(26.05)
    assert e.machines_by_display_name == pytest.approx(
        {"Smelter": 0.775, "Constructor": 2.175, "Assembler": 0.95}
    )


def test_smart_plating_power_is_unambiguous():
    e = expectations(demand(SMART_PLATING, 1.0).recipe_multipliers)
    assert e.power.is_degenerate


# --- scope guards ---------------------------------------------------------

def test_power_excludes_extraction():
    """D5. No extractor class may appear; raw ore enters at the boundary."""
    for item, rate in ((IRON_PLATE, 20.0), (SMART_PLATING, 1.0)):
        e = expectations(demand(item, rate).recipe_multipliers)
        for producer_class in e.machines_by_producer_class:
            assert "Miner" not in producer_class
            assert "Pump" not in producer_class
            assert "Fracking" not in producer_class


def test_expectations_cannot_choose_recipes():
    """The structural guard, mirroring the oracle's. It takes multipliers, never picks."""
    import inspect

    import _fixed_recipe_expectations as mod

    params = list(inspect.signature(mod.expectations).parameters)
    assert params == ["recipe_multipliers"]

    code = [
        ln for ln in open(mod.__file__, encoding="utf-8").read().splitlines()
        if not ln.lstrip().startswith("#")
    ]
    assert not [ln for ln in code if ln.startswith("if __name__")]
    assert not hasattr(mod, "main")


# --- the Phase 0 power figures, reconstructed -----------------------------
#
# Section 3.2 of docs/decisions/production_solver_selection.md reports 9.63 MW for
# Iron Plate and 27.31 MW for Smart Plating. The session handoff records those power
# columns as unusable. These two tests show why, exactly: each figure is reproducible
# only by reintroducing both defects — the missing Smelter (P1) and Candidate A's
# hardcoded Miner Mk3 extraction. They are here so the caveat is arithmetic rather
# than an assertion someone has to take on trust.
#
# The exact values are 9.625 and 27.309375. Section 3.2 displays them as 9.63 and
# 27.31 because JavaScript's toFixed(2) rounds 9.625 up where Python's round() gives
# 9.62. The assertions below pin the exact arithmetic, not either language's
# formatting.

_SMELTER = "Smelter"


def _power_with_p1_gap(item: str, rate: float) -> float:
    """Total power with the Smelter contributing nothing, as it did before P1."""
    result = demand(item, rate)
    e = expectations(result.recipe_multipliers)
    smelter_mw = 4.0 * e.machines_by_display_name.get(_SMELTER, 0.0)
    return e.power.mean_mw - smelter_mw


def test_reconstructs_phase_0_iron_plate_figure():
    """4 MW Constructor + 0 MW Smelter + 5.625 MW extraction = 9.625, reported as 9.63."""
    ore = demand(IRON_PLATE, 20.0).raw_inputs[IRON_ORE]
    reconstructed = _power_with_p1_gap(IRON_PLATE, 20.0) + _yafp_extraction_mw(ore)
    assert reconstructed == pytest.approx(9.625)


def test_reconstructs_phase_0_smart_plating_figure():
    """22.95 MW production without the Smelter + 4.359375 MW extraction, reported as 27.31."""
    ore = demand(SMART_PLATING, 1.0).raw_inputs[IRON_ORE]
    reconstructed = _power_with_p1_gap(SMART_PLATING, 1.0) + _yafp_extraction_mw(ore)
    assert reconstructed == pytest.approx(27.309375)
