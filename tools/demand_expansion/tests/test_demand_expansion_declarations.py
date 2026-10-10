"""A route table is a recorded choice, and a stale one is refused."""
from __future__ import annotations

import pytest

from demand_expansion import (
    DEFAULT_ROUTES, DeclarationError, Exclusion, RoutePin, RouteTable, build,
)


def test_the_default_table_builds(canonical):
    g = build(canonical, DEFAULT_ROUTES)
    assert g.producers["Desc_Plastic_C"] == ("Recipe_Plastic_C",)
    assert g.producers["Desc_Rubber_C"] == ("Recipe_Rubber_C",)
    assert "Recipe_UnpackageWater_C" not in g.enabled
    assert "Recipe_Alternate_Turbofuel_C" not in g.enabled
    assert "Recipe_Coal_Iron_C" not in g.enabled          # resource primary
    assert "Recipe_FicsiteIngot_Iron_C" in g.enabled      # Converter, not ore


def test_every_entry_carries_a_reason():
    assert all(e.reason.strip() for e in DEFAULT_ROUTES.exclusions)
    assert all(p.reason.strip() for p in DEFAULT_ROUTES.pins)
    with pytest.raises(DeclarationError):
        RouteTable("x", exclusions=(Exclusion("Recipe_UnpackageWater_C", " "),))


def test_an_exclusion_of_a_missing_recipe_is_stale(canonical):
    t = RouteTable("x", exclusions=(Exclusion("Recipe_Nope_C", "gone"),))
    with pytest.raises(DeclarationError, match="not in the reference layer"):
        build(canonical, t)


def test_an_exclusion_of_an_alternate_is_stale(canonical):
    """When the data fixes an is_alternate defect, the exclusion must go."""
    t = RouteTable("x", exclusions=(Exclusion("Recipe_Alternate_Wire_1_C", "defect"),))
    with pytest.raises(DeclarationError, match="flags as an alternate"):
        build(canonical, t)


def test_a_pin_that_resolves_nothing_is_stale(canonical):
    """Silica: one enabled producer under the primary-output rule, so the pin
    Amendment 1 proposed would be a choice nobody needs to make."""
    t = RouteTable("x", pins=(RoutePin("Desc_Silica_C", "Recipe_Silica_C", "proposed"),))
    with pytest.raises(DeclarationError, match="resolves nothing"):
        build(canonical, t)


def test_a_pin_cannot_enable_an_alternate(canonical):
    t = RouteTable("x", pins=(
        RoutePin("Desc_Plastic_C", "Recipe_Alternate_Plastic_1_C", "recycled"),
    ))
    with pytest.raises(DeclarationError, match="may only select"):
        build(canonical, t)


def test_duplicates_are_refused():
    with pytest.raises(DeclarationError):
        RouteTable("x", exclusions=(Exclusion("a", "r"), Exclusion("a", "r")))
    with pytest.raises(DeclarationError):
        RouteTable("x", pins=(RoutePin("i", "a", "r"), RoutePin("i", "b", "r")))
