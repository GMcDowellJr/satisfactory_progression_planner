"""tools/run_plan.py: the demand-side run track (reconciliation R9).

Reframe A15.2 B1 (Greg, 2026-11-17): demand side estimates what's next and what
reaching a target takes; the reference is the deployed prototype's target
determination (rate = E-scaled bill / horizon, horizon bounded by one machine
of the slowest part), with the repo's own arithmetic.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

from production_adapter import Scenario, load
from progression import playthrough

REPO = pathlib.Path(__file__).resolve().parents[1]
SP = "Desc_SpaceElevatorPart_1_C"
AW = "Desc_SpaceElevatorPart_3_C"
ROCKY_A = ("BP_ResourceNode153", "BP_ResourceNode109", "BP_ResourceNode108", "BP_ResourceNode105_2463",
           "BP_ResourceNode107", "BP_ResourceNode106", "BP_ResourceNode112", "BP_ResourceNode111_3367",
           "BP_ResourceNode103", "BP_ResourceNode102_2068", "BP_ResourceNode104")


def _module(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


R = _module("run_plan")


def _plan(phase=1, tier=2, milestones=(), scenario=Scenario(), **horizon):
    state = playthrough(REPO, through_tier=tier, milestones=list(milestones))
    from production_adapter.lp_backend import PowerStatistic
    return R.plan_phase(REPO, state=state, scenario=scenario, phase=phase,
                        power_statistic=PowerStatistic.MEAN, **horizon)


# --- the prototype's target determination, with the repo's arithmetic --------

def test_the_one_machine_ceiling_is_the_prototype_bound():
    """Phase 1: 50 Smart Plating on one Assembler at 2/min is 25 min."""
    plan = _plan(horizon_fraction=1.0)
    assert plan.ceiling_min == pytest.approx(25.0)
    assert plan.horizon_min == pytest.approx(25.0)
    (part,) = plan.parts
    assert (part.item_id, part.bill_units, part.rate_per_min) == (SP, 50.0, pytest.approx(2.0))


def test_the_ceiling_is_the_slowest_part():
    """Phase 2: Smart Plating 1000 at 2/min (500 min), Versatile Framework 1000
    at 5/min (200), Automated Wiring 100 at 2.5/min (40). The bound is 500."""
    plan = _plan(phase=2, tier=4, horizon_fraction=1.0)
    assert plan.ceiling_min == pytest.approx(500.0)
    assert sorted(round(p.one_machine_min) for p in plan.parts) == [40, 200, 500]


def test_a_fraction_of_the_ceiling_scales_the_rate():
    """The prototype's 25 % preset: a quarter of the time, four times the rate."""
    plan = _plan(horizon_fraction=0.25)
    assert plan.horizon_min == pytest.approx(6.25)
    assert plan.parts[0].rate_per_min == pytest.approx(8.0)


def test_a_declared_horizon_in_minutes():
    plan = _plan(horizon_min=50.0)
    assert plan.horizon_fraction == pytest.approx(2.0)   # longer than one machine: allowed
    assert plan.parts[0].rate_per_min == pytest.approx(1.0)


def test_e_scales_the_bill_and_the_ceiling():
    plan = _plan(scenario=Scenario(project_assembly_requirement_multiplier=2.0),
                 horizon_fraction=1.0)
    assert plan.parts[0].bill_units == 100.0
    assert plan.ceiling_min == pytest.approx(50.0)


def test_r_is_the_in_game_rule_not_the_prototype_ceil():
    """At 1.25x Smart Plating's 1 Reinforced Iron Plate stays 1 (demand
    §3.2.4); the prototype's ceil would make it 2."""
    data = load(REPO, Scenario(recipe_input_multiplier=1.25))
    amounts = {i: a for i, a, _ in data.recipes["Recipe_SpaceElevatorPart_1_C"].input_amounts}
    assert set(amounts.values()) == {1.0}
    plan = _plan(scenario=Scenario(recipe_input_multiplier=1.25), horizon_fraction=1.0)
    assert plan.response is not None


# --- what's next ----------------------------------------------------------------

def test_a_blocked_part_names_the_unlock_it_waits_on():
    """Phase 2 at tier 3: Automated Wiring's recipe comes with Advanced Steel
    Production (tier 4). No solve is attempted; the block is the answer."""
    plan = _plan(phase=2, tier=3, horizon_fraction=0.25)
    assert plan.response is None
    (blocked,) = plan.blocked
    assert blocked.item_id == AW
    base = dict((rid, (st, via)) for rid, st, via in blocked.producers)["Recipe_SpaceElevatorPart_3_C"]
    assert base == ("locked", ("Advanced Steel Production",))


def test_buying_the_milestone_unblocks_it():
    plan = _plan(phase=2, tier=3, milestones=["Schematic_4-1_C"], horizon_fraction=0.25)
    assert not plan.blocked and plan.response is not None
    assert plan.power_options   # a labelled diagnostic, one row per open (generator, fuel)


# --- the hand-off to the factory track (A1) ------------------------------------

def test_a_run_step_becomes_factory_inputs():
    F = _module("factory_run")
    plan = _plan(horizon_fraction=1.0)          # 2 Smart Plating/min
    doc = R.to_factory_inputs(plan, world_config_id="default_502094", label="rocky",
                              socket_ids=ROCKY_A, power_mode="report_need",
                              power_statistic="mean")
    assert max(m["units"] for m in doc["goal_mix"]) == 1.0      # proportions
    run = F.run_inputs(doc)
    assert run.scale == pytest.approx(50.0 / plan.horizon_min)
    assert dict(run.delivered)[SP] == pytest.approx(2.0)
    free = F.run_inputs({**doc, "target_scale": None})
    assert free.scale >= run.scale     # the site's maximum, and the horizon it implies


# --- the record and refusals ----------------------------------------------------

def test_the_record_and_the_cli(tmp_path):
    rec = json.loads(json.dumps(R.record(_plan(horizon_fraction=0.5)), default=str))
    assert rec["schema"] == "run-plan/1" and rec["parts"][0]["item_id"] == SP
    out = tmp_path / "plan.json"
    assert R.main(["--phase", "1", "--through-tier", "2", "--horizon-fraction", "0.5",
                   "--power-statistic", "mean", "--export", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["horizon_fraction"] == pytest.approx(0.5)


def test_the_power_statistic_has_no_default():
    """AGENTS.md: no default for power_statistic (LP D2). Codex on PR #15."""
    import inspect
    sig = inspect.signature(R.plan_phase).parameters["power_statistic"]
    assert sig.default is inspect.Parameter.empty
    with pytest.raises(SystemExit):
        R.main(["--phase", "1", "--through-tier", "2", "--horizon-fraction", "0.5"])


@pytest.mark.parametrize("kw, match", [
    ({}, "exactly one"),
    ({"horizon_min": 1.0, "horizon_fraction": 0.5}, "exactly one"),
    ({"horizon_fraction": 1.5}, r"\(0, 1\]"),
    ({"horizon_min": 0.0}, "positive"),
    ({"phase": 9, "horizon_fraction": 1.0}, "no Project Assembly phase"),
])
def test_a_bad_target_is_refused(kw, match):
    with pytest.raises(R.RunPlanError, match=match):
        _plan(**kw)
