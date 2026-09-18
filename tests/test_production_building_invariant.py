"""P1 validation invariant (plan section 6, as revised for variable power).

    every recipe producer
        -> exactly one canonical production-building record
        -> either a fixed base power, or a declared variable-power producer
        -> for variable-power producers, every recipe under that producer
           carries const + factor, and effective power is a (producer, recipe)
           function, not a producer constant

Source of truth for all three tables is the sha256-pinned game Docs build
recorded in game_builds.csv. These tests do not read Docs.json; they check that
the committed reference layer is internally consistent and complete.
"""
import csv
import pathlib

import pytest

REF = pathlib.Path(__file__).resolve().parents[1] / "planning_data" / "game" / "reference"

VARIABLE_POWER_NATIVE_CLASS = "FGBuildableManufacturerVariablePower"


def _rows(name):
    with open(REF / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def producers():
    return {r["producer_class"]: r for r in _rows("production_buildings.csv")}


@pytest.fixture(scope="module")
def recipe_producers():
    return _rows("recipe_producers.csv")


@pytest.fixture(scope="module")
def variable_power():
    return _rows("recipe_variable_power.csv")


def test_every_recipe_producer_has_exactly_one_building_record(producers, recipe_producers):
    missing = sorted({r["producer_class"] for r in recipe_producers} - set(producers))
    assert not missing, f"producer classes with no production_buildings record: {missing}"


def test_production_building_keys_are_unique(producers):
    raw = _rows("production_buildings.csv")
    assert len(raw) == len(producers), "duplicate producer_class in production_buildings.csv"


def test_no_orphan_building_records(producers, recipe_producers):
    used = {r["producer_class"] for r in recipe_producers}
    orphans = sorted(set(producers) - used)
    assert not orphans, f"production_buildings rows no recipe produces in: {orphans}"


def test_every_producer_declares_a_power_model_and_identity(producers):
    for pc, r in sorted(producers.items()):
        assert r["power_model"] in ("fixed", "variable"), pc
        assert r["display_name"].strip(), f"{pc} has no machine identity"
        assert r["base_power_mw"].strip() != "", f"{pc} has no base power"
        float(r["base_power_mw"])
        float(r["power_exponent"])


def test_fixed_power_producers_have_nonzero_base_power(producers):
    zero = sorted(pc for pc, r in producers.items()
                  if r["power_model"] == "fixed" and float(r["base_power_mw"]) == 0.0)
    assert not zero, f"fixed-power producers recording 0 MW: {zero}"


def test_variable_power_producers_declare_zero_base_power(producers):
    """Base power is meaningless for these; the recipe carries the draw."""
    bad = sorted(pc for pc, r in producers.items()
                 if r["power_model"] == "variable" and float(r["base_power_mw"]) != 0.0)
    assert not bad, f"variable-power producers with a nonzero base power: {bad}"


def test_variable_power_producers_use_the_variable_native_class(producers):
    for pc, r in sorted(producers.items()):
        is_var = r["native_class"].endswith(VARIABLE_POWER_NATIVE_CLASS)
        assert is_var == (r["power_model"] == "variable"), (
            f"{pc}: power_model={r['power_model']} disagrees with native_class={r['native_class']}"
        )


def test_every_variable_producer_recipe_has_a_power_row(producers, recipe_producers, variable_power):
    var_producers = {pc for pc, r in producers.items() if r["power_model"] == "variable"}
    expected = {r["recipe_id"] for r in recipe_producers if r["producer_class"] in var_producers}
    actual = {r["recipe_id"] for r in variable_power}
    assert expected == actual, (
        f"missing power rows: {sorted(expected - actual)}; "
        f"unexpected power rows: {sorted(actual - expected)}"
    )


def test_no_variable_power_rows_for_fixed_producers(producers, variable_power):
    """The trap. Variable power is keyed off the PRODUCER's native class, never
    off a recipe happening to carry mVariablePowerConsumption* fields. Three
    recipes on fixed-power producers carry them in the shipped Docs and the game
    ignores them; honouring those fields overstates Ballistic Warp Drive by ~20x.
    """
    bad = sorted(r["recipe_id"] for r in variable_power
                 if producers[r["producer_class"]]["power_model"] != "variable")
    assert not bad, f"variable-power rows attached to fixed-power producers: {bad}"


def test_variable_power_ranges_are_well_formed(variable_power):
    for r in variable_power:
        lo, hi = float(r["power_min_mw"]), float(r["power_max_mw"])
        assert lo >= 0.0, r["recipe_id"]
        assert hi >= lo, r["recipe_id"]
        assert hi > 0.0, f"{r['recipe_id']} draws no power at all"
        assert abs(float(r["power_mean_mw"]) - (lo + hi) / 2) < 1e-6, r["recipe_id"]
        assert abs(float(r["vp_const_mw"]) - lo) < 1e-6, r["recipe_id"]
        assert abs(float(r["vp_factor_mw"]) - (hi - lo)) < 1e-6, r["recipe_id"]


def test_provenance_is_single_and_consistent(producers, variable_power):
    builds = {r["game_build_id"] for r in producers.values()}
    builds |= {r["game_build_id"] for r in variable_power}
    builds |= {r["game_build_id"] for r in _rows("extraction_buildings.csv")}
    assert len(builds) == 1, f"tables span multiple game builds: {sorted(builds)}"
    known = {r["game_build_id"] for r in _rows("game_builds.csv")}
    assert builds <= known, f"game_build_id not registered in game_builds.csv: {sorted(builds - known)}"
