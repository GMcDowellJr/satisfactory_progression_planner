"""The command line: that it runs, and that it declines what it cannot represent.

Thin glue over `production_adapter` and `progression`, so these tests check wiring
and refusals rather than arithmetic — the arithmetic has its own suites. The
refusal tests are the ones that matter: a command line answering production
questions will be asked progression questions, and the failure mode to prevent is
answering them approximately.
"""
import importlib.util
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
CLI_PATH = REPO / "tools" / "production_cli.py"

_spec = importlib.util.spec_from_file_location("production_cli", CLI_PATH)
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)

SMART_PLATING = "Desc_SpaceElevatorPart_1_C"
TARGET = f"--target={SMART_PLATING}=1.0"


def run(argv):
    return cli.main(argv)


# --- refusals ------------------------------------------------------------

@pytest.mark.parametrize("flag,phase", [
    ("--by=240", "Phase 2"),
    ("--deadline=240", "Phase 2"),
    ("--inventory=Desc_IronPlate_C=100", "Phase 4"),
    ("--what-next=yes", "Phase 4"),
])
def test_out_of_scope_flags_are_declined_by_name(capsys, flag, phase):
    with pytest.raises(SystemExit) as exc:
        run(["solve", "--tier", "2", TARGET, flag])
    assert phase in str(exc.value)
    assert "not supported" in str(exc.value)


def test_every_refusal_names_the_phase_that_owns_it():
    for reason in cli.REFUSALS.values():
        assert "Phase" in reason


def test_a_negative_tier_is_refused():
    with pytest.raises(SystemExit, match="non-negative"):
        run(["solve", "--tier", "-1", TARGET])


def test_a_malformed_target_is_refused():
    with pytest.raises(SystemExit, match="ID=VALUE"):
        run(["solve", "--tier", "2", "--target", SMART_PLATING])


def test_a_non_numeric_rate_is_refused():
    with pytest.raises(SystemExit, match="not a number"):
        run(["solve", "--tier", "2", f"--target={SMART_PLATING}=lots"])


def test_an_unknown_vary_axis_is_refused():
    with pytest.raises(SystemExit, match="unknown axis"):
        run(["compare", "--tier", "2", TARGET, "--vary", "colour:red,blue"])


def test_vary_needs_two_values():
    with pytest.raises(SystemExit, match="at least two values"):
        run(["compare", "--tier", "2", TARGET, "--vary", "pool:on"])


# --- tiers ---------------------------------------------------------------

def test_tiers_reports_and_lists(capsys):
    assert run(["tiers", "--tier", "2"]) == 0
    out = capsys.readouterr().out
    assert "tier 2:" in out
    assert "withheld" in out
    assert "Recipe_IngotIron_C" in out


def test_tiers_pool_widens_and_says_so(capsys):
    run(["tiers", "--tier", "2", "--pool"])
    out = capsys.readouterr().out
    assert "pool at tier 2" in out
    assert "Recipe_Alternate_Screw_C" in out


def test_tiers_find_resolves_a_display_name(capsys):
    run(["tiers", "--tier", "2", "--find", "cast screws"])
    out = capsys.readouterr().out
    assert "Recipe_Alternate_Screw_C" in out
    assert "Alternate: Cast Screws" in out


def test_tiers_find_reports_a_miss(capsys):
    run(["tiers", "--tier", "2", "--find", "zzzz no such recipe"])
    assert "no recipe display name contains" in capsys.readouterr().out


def test_tiers_json_carries_the_withheld_counts(capsys):
    run(["tiers", "--tier", "2", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["tier"] == 2
    assert payload["pool"] is None
    assert len(payload["withheld_alternates"]) == 110


def test_declared_file_is_read(capsys, tmp_path):
    path = tmp_path / "held.txt"
    path.write_text("# what I have\nRecipe_Alternate_Screw_C\n\n", encoding="utf-8")
    run(["tiers", "--tier", "2", "--declared-file", str(path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["declared"] == ["Recipe_Alternate_Screw_C"]


# --- solve ---------------------------------------------------------------

def test_solve_prints_a_plan(capsys):
    assert run(["solve", "--tier", "2", "--pool", TARGET]) == 0
    out = capsys.readouterr().out
    assert "raw inputs" in out
    assert "Desc_OreIron_C" in out
    assert "power   scenario" in out
    assert "excludes extraction" in out


def test_solve_json_matches_the_known_pool_answer(capsys):
    run(["solve", "--tier", "2", "--pool", TARGET, "--json"])
    payload = json.loads(capsys.readouterr().out)
    raw = {r["item_id"]: r["rate_per_min"] for r in payload["raw_inputs"]}
    assert raw["Desc_OreIron_C"] == pytest.approx(9.333333, abs=1e-4)
    assert raw["Desc_OreCopper_C"] == pytest.approx(7.333333, abs=1e-4)
    assert payload["power"]["scenario_mw"] == pytest.approx(17.464444, abs=1e-4)


def test_solve_without_the_pool_is_the_base_chain(capsys):
    run(["solve", "--tier", "2", TARGET, "--json"])
    payload = json.loads(capsys.readouterr().out)
    raw = {r["item_id"]: r["rate_per_min"] for r in payload["raw_inputs"]}
    assert raw == pytest.approx({"Desc_OreIron_C": 23.25}, abs=1e-4)


def test_an_unreachable_target_exits_with_the_reason():
    with pytest.raises(SystemExit, match="infeasible"):
        run(["solve", "--tier", "2", "--target=Desc_Plastic_C=100"])


def test_a_cap_is_applied(capsys):
    run(["solve", "--tier", "2", TARGET, "--cap=Desc_OreIron_C=23.25", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert any("resource cap binds" in w for w in payload["warnings"])


def test_the_challenge_scenario_separates_canonical_from_scenario_power(capsys):
    run(["solve", "--tier", "2", TARGET, "--scenario", "challenge", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["power"]["scenario_mw"] == pytest.approx(
        payload["power"]["canonical_mw"] * 2.0, abs=1e-4
    )


# --- compare -------------------------------------------------------------

def test_compare_weights_produces_a_regret_table(capsys):
    assert run(["compare", "--tier", "2", "--pool", TARGET,
                "--vary", "weights:balanced,resources"]) == 0
    out = capsys.readouterr().out
    assert "regret" in out
    assert "balanced" in out and "resources" in out


def test_compare_pool_refuses_to_cross_price(capsys):
    """Different recipe sets are different feasible sets. n/a is the feature."""
    run(["compare", "--tier", "2", TARGET, "--vary", "pool:off,on"])
    out = capsys.readouterr().out
    assert "n/a" in out
    assert "different enabled recipe sets" in out


def test_compare_tier_axis_also_refuses(capsys):
    run(["compare", "--tier", "2", TARGET, "--vary", "tier:2,5"])
    out = capsys.readouterr().out
    assert "not comparable" in out


def test_compare_power_statistic_is_comparable(capsys):
    """Same feasible set, different metric — this one has real numbers in it."""
    run(["compare", "--tier", "2", "--pool", TARGET,
         "--vary", "power-statistic:min,mean,max", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["incomparable"] == {}
    assert all(v is not None for v in payload["regret"].values())


def test_an_unknown_weights_preset_is_refused():
    with pytest.raises(SystemExit, match="unknown weights preset"):
        run(["compare", "--tier", "2", TARGET, "--vary", "weights:balanced,cheapest"])


# --- the entry point itself ----------------------------------------------

def test_it_sets_up_sys_path_rather_than_needing_an_install():
    """The repo is not installed; conftest is what puts src trees on the path for
    tests. A user running this script has no conftest, so it must do it itself."""
    source = CLI_PATH.read_text(encoding="utf-8")
    assert "sys.path.insert" in source


def test_a_subcommand_is_required():
    with pytest.raises(SystemExit):
        run([])
