"""Narrow interface between the progression planner and a production solver.

    from production_adapter import Scenario, SolveRequest, OutputTarget, load

    data = load(repo_root, Scenario(recipe_input_multiplier=1.25))
    request = SolveRequest(outputs=(OutputTarget("Desc_SpaceElevatorPart_1_C", 1.0),))
    response = get_backend().solve(request, data)

Progression code imports from here and nowhere deeper.
"""
from .contracts import (
    AllowedRecipes, BindingCap, DistrictPower, DistrictRequest, DistrictResponse,
    DistrictTarget, GeneratorFuel, GeneratorUse, ItemFlow, MachineCount, OutputTarget,
    PortfolioRequest, PortfolioResponse, PortfolioSite, PowerBalance, PowerReport, RawInput,
    RecipeMode, RecipeUse, ResourceCap, SitePlan, SolveRequest, SolveResponse, TargetRate,
    Transfer, Weights,
)
from .backend import Backend, BackendNotSelected, get as get_backend, register, registered
from .gamedata import (
    GameBuild, Item, PowerRange, Producer, ProjectAssemblyRequirement, Recipe,
    RecipeUnlock, ReferenceData, ReferenceDataError, load, load_game_build,
    load_project_assembly, load_recipe_unlocks,
)
from .scenario import (
    CHALLENGE_1_25X_2X, FLUID_ROUNDING_VARIANTS, FLUID_UNIT, ITEM_UNIT,
    MARGINAL_PEAK_DEBOTTLENECK, Scenario,
)

__all__ = [
    "AllowedRecipes", "Backend", "BackendNotSelected", "BindingCap", "CHALLENGE_1_25X_2X",
    "DistrictPower", "DistrictRequest", "DistrictResponse", "DistrictTarget",
    "FLUID_ROUNDING_VARIANTS", "FLUID_UNIT", "GameBuild", "GeneratorFuel", "GeneratorUse",
    "ITEM_UNIT", "Item", "ItemFlow", "MARGINAL_PEAK_DEBOTTLENECK",
    "MachineCount", "OutputTarget", "PortfolioRequest", "PortfolioResponse", "PortfolioSite",
    "PowerBalance", "PowerRange", "PowerReport", "Producer",
    "ProjectAssemblyRequirement", "RecipeUnlock",
    "RawInput", "Recipe", "RecipeMode", "RecipeUse", "ReferenceData", "ReferenceDataError",
    "ResourceCap", "Scenario", "SitePlan", "SolveRequest", "SolveResponse", "TargetRate",
    "Transfer", "Weights",
    "get_backend", "load", "load_game_build", "load_project_assembly",
    "load_recipe_unlocks", "register", "registered",
]
__version__ = "0.1.0"
