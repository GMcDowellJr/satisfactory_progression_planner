"""The hard-drive pool: what is obtainable at a tier, not what is held.

Formulation record section 19. Two things are load-bearing here and both are
asserted rather than trusted:

    the P4 join       slug -> Recipe_*_C by normalised display name, all 79 rows
    the scope line    automatic pool entry only; MAM-gated entry is reported, never
                      modelled, because researching it widens the pool and that is a
                      cost this layer cannot see
"""
import pathlib

import pytest

from production_adapter import OutputTarget, SolveRequest, load
from production_adapter.lp_backend import LpBackend, PowerStatistic
from progression import PoolDataError, at_tier, available_at, resolve_slugs
from progression.pool import AUTOMATIC_ELIGIBILITY, _band_max_tier, resolve_clusters

REPO = pathlib.Path(__file__).resolve().parents[1]

CAST_SCREWS = "Recipe_Alternate_Screw_C"
IRON_WIRE = "Recipe_Alternate_Wire_1_C"
STITCHED = "Recipe_Alternate_ReinforcedIronPlate_2_C"
SMART_PLATING = "Desc_SpaceElevatorPart_1_C"


@pytest.fixture(scope="module")
def data():
    return load(REPO)


@pytest.fixture(scope="module")
def backend():
    return LpBackend(power_statistic=PowerStatistic.MEAN)


# --- the P4 join ---------------------------------------------------------

def test_every_slug_resolves_to_a_recipe_id():
    """P4, open since the session handoff recorded it. All 79, none ambiguous."""
    resolved = resolve_slugs(REPO)
    assert len(resolved) == 79
    assert resolved["cast_screws"] == CAST_SCREWS
    assert resolved["iron_wire"] == IRON_WIRE
    assert resolved["stitched_iron_plate"] == STITCHED
    assert len(set(resolved.values())) == len(resolved)


def test_the_join_raises_rather_than_dropping_a_row(tmp_path):
    """A future game build that breaks the match must fail loudly, not shrink the pool."""
    ref = tmp_path / "planning_data" / "game" / "reference"
    ref.mkdir(parents=True)
    (ref / "recipes.csv").write_text(
        "recipe_id,display_name,is_alternate\nRecipe_X_C,Alternate: Something Else,true\n",
        encoding="utf-8",
    )
    (ref / "alternate_recipe_unlocks.csv").write_text(
        "recipe_id,recipe_name,progression_cluster_id,eligibility_type\n"
        "cast_screws,Cast Screws,pre_tier_1_2,automatic_hub\n",
        encoding="utf-8",
    )
    with pytest.raises(PoolDataError, match="matched 0 recipes"):
        resolve_slugs(tmp_path)


# --- tier bands ----------------------------------------------------------

def test_band_max_tier_reads_the_cluster_id():
    assert _band_max_tier("pre_tier_1_2") == 0
    assert _band_max_tier("tier_1_2") == 2
    assert _band_max_tier("tier_3_4") == 4
    assert _band_max_tier("tier_9") == 9


def test_bands_are_monotonic_in_sort_order():
    """The guard that keeps reading a tier off an identifier from being a guess."""
    bands = resolve_clusters(REPO)
    assert bands == {
        "pre_tier_1_2": 0, "tier_1_2": 2, "tier_3_4": 4,
        "tier_5_6": 6, "tier_7_8": 8, "tier_9": 9,
    }


def test_an_unreadable_cluster_id_raises():
    with pytest.raises(PoolDataError, match="cannot read a tier band"):
        _band_max_tier("some_band")


# --- the pool ------------------------------------------------------------

def test_cast_screws_and_iron_wire_are_in_the_pool_from_the_start():
    """Both are pre_tier_1_2 — obtainable before any milestone."""
    pool = available_at(REPO, 0)
    assert set(pool.recipe_ids) == {CAST_SCREWS, IRON_WIRE}
    assert pool.by_cluster["pre_tier_1_2"] == tuple(sorted((CAST_SCREWS, IRON_WIRE)))


def test_the_tier_two_pool_is_the_early_six():
    pool = available_at(REPO, 2)
    assert set(pool.recipe_ids) == {
        CAST_SCREWS, IRON_WIRE, STITCHED,
        "Recipe_Alternate_BoltedFrame_C",
        "Recipe_Alternate_CopperRotor_C",
        "Recipe_Alternate_ReinforcedIronPlate_1_C",
    }


@pytest.mark.parametrize("n", range(0, 9))
def test_the_pool_only_grows(n):
    assert set(available_at(REPO, n).recipe_ids) <= set(available_at(REPO, n + 1).recipe_ids)


def test_every_automatic_alternate_is_in_the_pool_by_tier_nine():
    pool = available_at(REPO, 9)
    assert len(pool.recipe_ids) == 79
    assert pool.not_yet == ()


def test_the_research_gated_remainder_is_constant_and_named():
    """31 alternates never enter automatically. That does not change with tier."""
    for n in (0, 2, 5, 9):
        assert len(available_at(REPO, n).research_gated) == 31


def test_the_report_states_what_it_does_not_model():
    report = available_at(REPO, 2).report()
    assert "31 alternates enter the pool only through MAM research" in report
    assert "widens the pool" in report
    assert "not modelled here" in report


def test_only_automatic_eligibility_is_modelled():
    assert AUTOMATIC_ELIGIBILITY == "automatic_hub"


def test_a_negative_tier_raises():
    with pytest.raises(ValueError, match="non-negative"):
        available_at(REPO, -1)


# --- composition with the tier filter ------------------------------------

def test_include_pool_defaults_off_and_changes_nothing(data):
    """No existing caller asked for a wider set, so the default must not widen it."""
    without = at_tier(REPO, 2)
    assert without.pool is None
    for recipe_id in without.recipe_ids:
        assert not data.recipes[recipe_id].is_alternate


def test_include_pool_adds_exactly_the_pool(data):
    base = set(at_tier(REPO, 2).recipe_ids)
    wide = at_tier(REPO, 2, include_pool=True)
    assert set(wide.recipe_ids) - base == set(available_at(REPO, 2).recipe_ids)
    assert wide.pool is not None
    assert "pool at tier 2" in wide.report()


def test_pool_alternates_leave_the_withheld_list():
    assert CAST_SCREWS in at_tier(REPO, 2).withheld_alternates
    assert CAST_SCREWS not in at_tier(REPO, 2, include_pool=True).withheld_alternates


# --- the payoff ----------------------------------------------------------

def test_the_tier_two_pool_beats_the_base_chain_substantially(backend, data):
    """Smart Plating 1/min, tier 2, reaching for what the pool offers.

        held only   23.2500 iron                      26.0500 MW
        pool         9.3333 iron + 7.3333 copper      17.4644 MW

    The solver takes Cast Screws, Stitched Iron Plate and Copper Rotor — and does
    NOT take Iron Wire, which was worth 3.30 ore/min when paired with Stitched alone
    (section 16). Once Copper Rotor puts copper in the chain anyway, Iron Wire's
    whole argument — getting the copper back out — evaporates.

    That is section 16.2's point arriving a second time from a different direction:
    an alternate's value is a property of the set, not of the recipe.
    """
    def solve(include_pool):
        return backend.solve(
            SolveRequest(outputs=(OutputTarget(SMART_PLATING, 1.0),),
                         allowed_recipes=at_tier(REPO, 2, include_pool=include_pool).allowed_recipes),
            data,
        )

    held, wide = solve(False), solve(True)
    held_raw = {r.item_id: r.rate_per_min for r in held.raw_inputs}
    wide_raw = {r.item_id: r.rate_per_min for r in wide.raw_inputs}

    assert held_raw == pytest.approx({"Desc_OreIron_C": 23.25}, abs=1e-4)
    assert wide_raw == pytest.approx(
        {"Desc_OreIron_C": 9.333333, "Desc_OreCopper_C": 7.333333}, abs=1e-4
    )
    assert held.power.scenario_mw == pytest.approx(26.05, abs=1e-4)
    assert wide.power.scenario_mw == pytest.approx(17.464444, abs=1e-4)

    chosen = {u.recipe_id for u in wide.recipes}
    assert CAST_SCREWS in chosen
    assert STITCHED in chosen
    assert "Recipe_Alternate_CopperRotor_C" in chosen
    assert IRON_WIRE not in chosen


# --- the structural guard ------------------------------------------------

def test_the_corrupt_table_is_not_read():
    """`alternate_choices.csv` joins cleanly on ids and its progression columns are
    unusable — 98 of 107 recipe rows carry truncated dependency fragments. Section
    19.3. Reading it would look like an upgrade and would silently be wrong."""
    import ast

    import progression.pool as mod

    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    docstrings = {
        id(n.body[0].value) for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
        and getattr(n, "body", None) and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant) and isinstance(n.body[0].value.value, str)
    }
    literals = " ".join(
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
    )
    assert "alternate_choices" not in literals
    assert not hasattr(mod, "main")
