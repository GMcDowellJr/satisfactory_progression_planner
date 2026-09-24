"""Tier unlock resolution, and the completeness it is required to report.

The rule under test (formulation record section 18): a recipe is granted at tier N
when a Milestone, Tutorial or Custom schematic with tech_tier <= N unlocks it and
recipes.csv does not flag it as an alternate.

`test_tier_zero_can_smelt_iron` is the reason Custom is in that list, and is the
first test that should be run if the rule is ever changed.
"""
import pathlib

import pytest

from production_adapter import OutputTarget, SolveRequest, load
from production_adapter.lp_backend import Infeasible, LpBackend, PowerStatistic
from progression import TierUnlocks, at_tier
from progression.unlocks import PROGRESSION_TYPES

REPO = pathlib.Path(__file__).resolve().parents[1]

IRON_BASICS = {"Recipe_IngotIron_C", "Recipe_IronPlate_C", "Recipe_IronRod_C"}
SMART_PLATING = "Desc_SpaceElevatorPart_1_C"


@pytest.fixture(scope="module")
def data():
    return load(REPO)


@pytest.fixture(scope="module")
def backend():
    return LpBackend(power_statistic=PowerStatistic.MEAN)


def tier(n, declared=()):
    return at_tier(REPO, n, declared)


# --- the trap ------------------------------------------------------------

def test_tier_zero_can_smelt_iron():
    """`Recipe_IngotIron_C` and friends come from "Starting Blueprints", EST_Custom.

    A Milestone-and-Tutorial-only rule looks obviously right and returns a recipe set
    that cannot make an iron plate. That mistake was made and caught by measurement;
    this test is what keeps it caught.
    """
    assert IRON_BASICS <= set(tier(0).recipe_ids)


def test_custom_is_in_the_progression_types():
    assert PROGRESSION_TYPES == {"EST_Milestone", "EST_Tutorial", "EST_Custom"}


# --- the tier ladder behaves like a ladder -------------------------------

def test_steel_yes_plastic_no_at_tier_three():
    """Greg's framing: on steel you do not yet have oil and plastic."""
    enabled = set(tier(3).recipe_ids)
    assert "Recipe_IngotSteel_C" in enabled
    assert "Recipe_SteelBeam_C" in enabled
    assert "Recipe_Plastic_C" not in enabled
    assert "Recipe_Rubber_C" not in enabled
    assert "Recipe_Motor_C" not in enabled


def test_plastic_arrives_at_tier_five():
    assert "Recipe_Plastic_C" not in set(tier(4).recipe_ids)
    assert "Recipe_Plastic_C" in set(tier(5).recipe_ids)


def test_matter_conversion_is_a_tier_nine_thing():
    """The SAM-and-Quartz-to-Copper route that looked like a valuation problem.

    "Matter Conversion" is a Tier 9 milestone, so the Converter recipes are late-game
    and their appearance in an unconstrained early solve was a progression artefact,
    not a scarcity one. Formulation record section 17.2.
    """
    assert "Recipe_Bauxite_Copper_C" not in set(tier(8).recipe_ids)
    assert "Recipe_Bauxite_Copper_C" in set(tier(9).recipe_ids)


@pytest.mark.parametrize("n", range(0, 9))
def test_tiers_are_monotonic(n):
    assert set(tier(n).recipe_ids) <= set(tier(n + 1).recipe_ids)


def test_no_alternate_is_ever_granted_by_a_tier(data):
    """A tech tier never implies a hard drive. Checked against the adapter's own view."""
    for n in (0, 3, 5, 9):
        for recipe_id in tier(n).recipe_ids:
            assert not data.recipes[recipe_id].is_alternate


# --- the completeness report ---------------------------------------------

def test_every_report_names_what_it_withheld():
    for n in (0, 3, 5, 9):
        report = tier(n).report()
        assert "withheld" in report
        assert "MAM research" in report
        assert "does not model progression" in report


def test_withheld_research_is_substantial_and_shrinks_with_tier():
    """46 of 181 base recipes are MAM-only at tier 9. Silence about that would lie."""
    assert len(tier(9).withheld_research) == 46
    assert len(tier(0).withheld_research) > len(tier(9).withheld_research)
    assert len(tier(9).withheld_alternates) == 110


def test_uncertain_surfaces_the_mis_flagged_turbofuel_recipes():
    """Three recipes are is_alternate=false but reachable only through research.

    `Recipe_Alternate_Turbofuel_C` comes from MAM and an "Alternate:" Custom
    schematic; `Recipe_PackagedTurboFuel_C` and `Recipe_UnpackageTurboFuel_C` come
    from hard-drive schematics. The tier filter grants them because the flag says
    base, and says it is unsure. Section 18.4.
    """
    uncertain = set(tier(9).uncertain)
    assert {
        "Recipe_Alternate_Turbofuel_C",
        "Recipe_PackagedTurboFuel_C",
        "Recipe_UnpackageTurboFuel_C",
    } <= uncertain


# --- declared is an input, never an inference ----------------------------

def test_declared_is_added_verbatim():
    without = set(tier(3).recipe_ids)
    with_silica = set(tier(3, declared=("Recipe_Silica_C",)).recipe_ids)
    assert with_silica - without == {"Recipe_Silica_C"}


def test_declaring_removes_it_from_withheld():
    assert "Recipe_Silica_C" in tier(3).withheld_research
    assert "Recipe_Silica_C" not in tier(3, declared=("Recipe_Silica_C",)).withheld_research


def test_declared_ids_are_validated():
    with pytest.raises(ValueError, match="not in recipes.csv"):
        tier(3, declared=("Recipe_NotAThing_C",))


def test_a_negative_tier_raises():
    with pytest.raises(ValueError, match="non-negative"):
        tier(-1)


# --- the structural guard ------------------------------------------------

def _non_docstring_strings(path):
    """Every string literal in a module except the docstrings."""
    import ast

    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    return [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
    ]


def test_it_does_not_walk_schematic_dependencies():
    """A filter, not a progression model. The moment it needs the dependency graph
    it has become Phase 3's unlocked-recipe candidate generation.

    Checked against string literals in code rather than the file text, because the
    module docstring names those tables in order to say it does not read them.
    """
    import progression.unlocks as mod

    literals = " ".join(_non_docstring_strings(mod.__file__))
    assert "schematic_dependencies" not in literals
    assert "alternate_recipe_unlocks" not in literals
    assert not hasattr(mod, "main")


def test_the_adapter_does_not_import_progression():
    """Dependency runs one way, downward. Section 11.1.

    Inspects import statements, not file text: the adapter's docstrings talk about
    "the progression planner" and always have.
    """
    import ast

    import production_adapter
    import production_adapter.gamedata as gamedata
    import production_adapter.lp_backend as lp_backend
    import production_adapter.analysis as analysis

    for module in (production_adapter, gamedata, lp_backend, analysis):
        tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all("progression" not in a.name for a in node.names), module.__name__
            elif isinstance(node, ast.ImportFrom):
                assert "progression" not in (node.module or ""), module.__name__


# --- end to end ----------------------------------------------------------

def test_smart_plating_at_tier_three_matches_the_canonical_answer(backend, data):
    """The tier set is a drop-in for `allowed_recipes` and changes no arithmetic."""
    response = backend.solve(
        SolveRequest(outputs=(OutputTarget(SMART_PLATING, 1.0),),
                     allowed_recipes=tier(3).allowed_recipes),
        data,
    )
    raw = {r.item_id: r.rate_per_min for r in response.raw_inputs}
    assert raw == pytest.approx({"Desc_OreIron_C": 23.25}, abs=1e-4)
    assert response.power.scenario_mw == pytest.approx(26.05, abs=1e-4)


def test_plastic_at_tier_three_is_infeasible_rather_than_wrong(backend, data):
    with pytest.raises(Infeasible, match="no enabled recipe produces"):
        backend.solve(
            SolveRequest(outputs=(OutputTarget("Desc_Plastic_C", 100.0),),
                         allowed_recipes=tier(3).allowed_recipes),
            data,
        )


def test_allowed_recipes_is_explicit_never_a_mode():
    """A mode would let the tier set drift back to base_only or all silently."""
    allowed = tier(3).allowed_recipes
    assert allowed.mode.value == "explicit"
    assert allowed.recipe_ids == tier(3).recipe_ids
    assert isinstance(tier(3), TierUnlocks)


# --------------------------------------------------------------------------
# tier -> schematics, and what they cost. Added 2026-09-22 for the stock pass.
# --------------------------------------------------------------------------

def test_the_tier_filter_resolves_schematics_and_recipes_from_one_predicate():
    """Extracted so the filter exists ONCE. Two copies of a filter is how the
    provenance work's three-lists defect started, and the fix there was to make
    the lists one list."""
    from progression import unlocks as U

    assert U._reached_at_tier({"schematic_type": "EST_Milestone", "tech_tier": "3"}, 3)
    assert U._reached_at_tier({"schematic_type": "EST_Milestone", "tech_tier": "1"}, 3)
    assert not U._reached_at_tier({"schematic_type": "EST_Milestone", "tech_tier": "4"}, 3)
    assert not U._reached_at_tier({"schematic_type": "EST_MAM", "tech_tier": "1"}, 3)
    assert not U._reached_at_tier({"schematic_type": "EST_Alternate", "tech_tier": "1"}, 3)


def test_schematics_at_tier_is_cumulative():
    """`tech_tier <= tier`, so this is everything bought on the way and not the
    tier's own row. The wrong shape for "what do I still owe" — the difference
    is what the player has already bought, which is state this layer does not
    hold."""
    from progression.unlocks import schematics_at_tier

    low = set(schematics_at_tier(REPO, 1))
    high = set(schematics_at_tier(REPO, 3))
    assert low < high, "a higher tier must strictly contain a lower one"
    assert "Schematic_1-1_C" in low and "Schematic_3-4_C" not in low
    assert "Schematic_3-4_C" in high


def test_schematics_at_tier_withholds_research_and_hard_drive_schematics():
    """A tier does not imply MAM research or hard-drive loot, so their COSTS are
    not in a tier's bill either — the same rule `at_tier` applies to recipes."""
    import csv

    from progression.unlocks import PROGRESSION_TYPES, schematics_at_tier

    path = REPO / "planning_data" / "game" / "reference" / "schematics.csv"
    with path.open(encoding="utf-8") as fh:
        kinds = {r["schematic_id"]: r["schematic_type"] for r in csv.DictReader(fh)}
    for schematic_id in schematics_at_tier(REPO, 9):
        assert kinds[schematic_id] in PROGRESSION_TYPES


def test_every_milestone_and_tutorial_carries_a_cost():
    """THE MEASUREMENT THAT MAKES "ABSENT MEANS FREE" SAFE.

    `unlock_cost` treats a schematic missing from the cost table as costing
    nothing. That is only honest because all 42 Milestones and all 6 Tutorials
    are costed, and the uncosted progression-type schematics are Custom —
    starting blueprints, cosmetics, FICSMAS. If a future extraction drops
    milestone costs, this fails instead of every bill quietly shrinking.
    """
    import csv

    from progression.unlocks import schematic_costs

    path = REPO / "planning_data" / "game" / "reference" / "schematics.csv"
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    costs = schematic_costs(REPO)

    for kind, expected in (("EST_Milestone", 42), ("EST_Tutorial", 6)):
        ids = [r["schematic_id"] for r in rows if r["schematic_type"] == kind]
        assert len(ids) == expected
        assert all(s in costs for s in ids), f"an uncosted {kind}"


def test_schematic_costs_reads_real_amounts():
    """Base Building, tier 1: 200 Concrete, 100 Iron Plate, 100 Iron Rod. Three
    distinct amounts, read from schematic_costs.csv."""
    from progression.unlocks import schematic_costs

    assert dict(schematic_costs(REPO)["Schematic_1-1_C"]) == {
        "Desc_Cement_C": 200.0,
        "Desc_IronPlate_C": 100.0,
        "Desc_IronRod_C": 100.0,
    }


# --------------------------------------------------------------------------
# D3 P6: schematics_in_tiers, an optional helper. The set stays declared
# --------------------------------------------------------------------------

from progression import unlocks as _u  # noqa: E402

def test_schematics_in_tier_2_are_the_five_milestones_a13_declared():
    """The five A13.5 paced, filtered by hand in test_goal_run.py."""
    got = _u.schematics_in_tiers(REPO, (2,))
    assert got == (
        "Schematic_2-1_C", "Schematic_2-2_C", "Schematic_2-3_C",
        "Schematic_2-5_C", "Schematic_3-2_C",
    )


def test_schematics_in_tiers_is_incremental_and_partitions_the_cumulative_set():
    """Tiers {0, 1, 2} together are exactly schematics_at_tier(2)."""
    assert set(_u.schematics_in_tiers(REPO, (0, 1, 2))) == set(_u.schematics_at_tier(REPO, 2))
    assert set(_u.schematics_in_tiers(REPO, (2,))).isdisjoint(_u.schematics_in_tiers(REPO, (1,)))


def test_schematics_in_tiers_returns_ids_and_never_a_quantity():
    got = _u.schematics_in_tiers(REPO, (1, 2))
    assert all(isinstance(s, str) for s in got)


def test_schematics_in_tiers_refuses_a_negative_tier():
    with pytest.raises(ValueError):
        _u.schematics_in_tiers(REPO, (-1,))
