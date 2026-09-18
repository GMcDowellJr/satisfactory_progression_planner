"""The adapter contract (implementation plan section 7).

Progression code depends on these types and nothing else. Nothing here knows
whether the engine underneath is TypeScript, Python, LP, or graph propagation —
that is the entire point of the boundary.

Rates are per minute throughout. Machine counts are fractional; rounding is a
presentation concern (plan section 15) and is applied by the caller, not here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

ItemId = str      # Desc_*_C
RecipeId = str    # Recipe_*_C
ProducerClass = str  # Build_*_C


class RecipeMode(str, Enum):
    """How `SolveRequest.allowed_recipes` is interpreted."""

    EXPLICIT = "explicit"   # exactly the listed recipe ids
    BASE_ONLY = "base_only"  # every non-alternate recipe
    ALL = "all"             # every known recipe


@dataclass(frozen=True)
class OutputTarget:
    item_id: ItemId
    rate_per_min: float

    def __post_init__(self) -> None:
        if self.rate_per_min <= 0:
            raise ValueError(f"{self.item_id}: target rate must be positive")


@dataclass(frozen=True)
class ResourceCap:
    """An upper bound on a raw input. `rate_per_min = None` means unlimited."""

    item_id: ItemId
    rate_per_min: float | None = None


@dataclass(frozen=True)
class AllowedRecipes:
    mode: RecipeMode = RecipeMode.BASE_ONLY
    recipe_ids: tuple[RecipeId, ...] = ()

    def __post_init__(self) -> None:
        if self.mode is RecipeMode.EXPLICIT and not self.recipe_ids:
            raise ValueError("explicit mode requires at least one recipe id")
        if self.mode is not RecipeMode.EXPLICIT and self.recipe_ids:
            raise ValueError(f"recipe_ids is meaningless in {self.mode.value} mode")


@dataclass(frozen=True)
class Weights:
    """Objective weights. Names follow plan section 12's separate metrics.

    `complexity` is pinned to 0.0 and rejected otherwise: on the vendored
    Candidate A engine it introduces binary variables, and every case in the
    Phase 0 benchmark hit that engine's hardcoded 3-second limit against the
    291-recipe 1.2 dataset. See docs/decisions/production_solver_selection.md,
    fork delta F2. Lift this once F2 is resolved, not before.
    """

    resources: float = 1.0
    power: float = 1.0
    buildings: float = 1.0
    complexity: float = 0.0

    def __post_init__(self) -> None:
        for name in ("resources", "power", "buildings", "complexity"):
            v = getattr(self, name)
            if v < 0:
                raise ValueError(f"weight {name} must be non-negative")
        if self.complexity != 0.0:
            raise NotImplementedError(
                "complexity weight is disabled (fork delta F2: unbounded MIP solve time)"
            )


@dataclass(frozen=True)
class SolveRequest:
    outputs: tuple[OutputTarget, ...]
    allowed_recipes: AllowedRecipes = AllowedRecipes()
    resource_caps: tuple[ResourceCap, ...] = ()
    existing_inventory: tuple[ResourceCap, ...] = ()   # plan section 14 hook
    weights: Weights = Weights()

    def __post_init__(self) -> None:
        if not self.outputs:
            raise ValueError("a solve needs at least one output target")
        seen = [o.item_id for o in self.outputs]
        dupes = {i for i in seen if seen.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate output targets: {sorted(dupes)}")
        capped = {c.item_id for c in self.resource_caps}
        both = capped & set(seen)
        if both:
            raise ValueError(f"item is both an output and an input: {sorted(both)}")


@dataclass(frozen=True)
class RecipeUse:
    recipe_id: RecipeId
    producer_class: ProducerClass
    machine_equivalents: float   # fractional, at 100% clock
    cycles_per_min: float


@dataclass(frozen=True)
class ItemFlow:
    item_id: ItemId
    produced_per_min: float
    consumed_per_min: float

    @property
    def net_per_min(self) -> float:
        return self.produced_per_min - self.consumed_per_min


@dataclass(frozen=True)
class RawInput:
    item_id: ItemId
    rate_per_min: float


@dataclass(frozen=True)
class MachineCount:
    producer_class: ProducerClass
    effective_count: float
    physical_count_if_rounded: int


@dataclass(frozen=True)
class PowerReport:
    """Variable-power producers make a single figure meaningless.

    Particle Accelerator, Converter and Quantum Encoder draw a range that depends
    on the recipe, so the adapter reports the range and lets the caller choose
    which statistic to optimise. See docs/decisions/production_building_power_model.md.
    """

    canonical_mw: float
    scenario_mw: float
    min_mw: float
    max_mw: float

    def __post_init__(self) -> None:
        if self.max_mw < self.min_mw:
            raise ValueError("power max below min")


@dataclass(frozen=True)
class SolveResponse:
    recipes: tuple[RecipeUse, ...]
    items: tuple[ItemFlow, ...]
    raw_inputs: tuple[RawInput, ...]
    power: PowerReport
    machines: tuple[MachineCount, ...]
    backend: str = ""
    warnings: tuple[str, ...] = field(default_factory=tuple)
