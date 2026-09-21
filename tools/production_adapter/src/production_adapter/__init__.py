"""Narrow interface between the progression planner and a production solver.

    from production_adapter import Scenario, SolveRequest, OutputTarget, load

    data = load(repo_root, Scenario(recipe_input_multiplier=1.25))
    request = SolveRequest(outputs=(OutputTarget("Desc_SpaceElevatorPart_1_C", 1.0),))
    response = get_backend().solve(request, data)

Progression code imports from here and nowhere deeper.
"""
from .contracts import (
    AllowedRecipes, ItemFlow, MachineCount, OutputTarget, PowerReport, RawInput,
    RecipeMode, RecipeUse, ResourceCap, SolveRequest, SolveResponse, Weights,
)
from .backend import Backend, BackendNotSelected, get as get_backend, register, registered
from .gamedata import (
    Item, PowerRange, Producer, Recipe, ReferenceData, ReferenceDataError, load,
)
from .scenario import (
    CHALLENGE_1_25X_2X, FLUID_UNIT, ITEM_UNIT, MARGINAL_PEAK_DEBOTTLENECK, Scenario,
)

__all__ = [
    "AllowedRecipes", "Backend", "BackendNotSelected", "CHALLENGE_1_25X_2X", "FLUID_UNIT",
    "ITEM_UNIT", "Item", "ItemFlow", "MARGINAL_PEAK_DEBOTTLENECK",
    "MachineCount", "OutputTarget", "PowerRange", "PowerReport", "Producer",
    "RawInput", "Recipe", "RecipeMode", "RecipeUse", "ReferenceData", "ReferenceDataError",
    "ResourceCap", "Scenario", "SolveRequest", "SolveResponse", "Weights",
    "get_backend", "load", "register", "registered",
]
__version__ = "0.1.0"
