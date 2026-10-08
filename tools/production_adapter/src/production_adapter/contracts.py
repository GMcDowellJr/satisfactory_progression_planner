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


# --------------------------------------------------------------------------
# the district solve (crossover A27.1 K2, A27.2)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DistrictTarget:
    """One selected output of a supply-side solve: a weight and an optional floor.

    The district question is "what can this site make", with no bill (A27.1
    K2). Rates are therefore VARIABLES, not inputs: the solve maximises the
    weighted sum of the selected outputs within the caps, after every declared
    floor is met. Both numbers are printed with the result (LP record 21 R2).

        weight         0 excludes the item from the objective; the PWA's
                       Trickle / Normal / Prioritize are three values of it
        minimum_rate   a declared floor, in items per minute. A trickle is a
                       small floor, never a clock (v5.5 rule 2). None: no floor
    """

    item_id: ItemId
    weight: float = 1.0
    minimum_rate: float | None = None

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ValueError(f"{self.item_id}: weight must be non-negative")
        if self.minimum_rate is not None and self.minimum_rate <= 0:
            raise ValueError(f"{self.item_id}: minimum_rate must be positive when given")

    @property
    def is_active(self) -> bool:
        """In the solve at all: weighted, or held above a floor."""
        return self.weight > 0 or self.minimum_rate is not None


@dataclass(frozen=True)
class GeneratorFuel:
    """One generator_fuels.csv row as the solver sees it: a generator burning
    one fuel. Rates are per generator per minute at 100 %; `power_mw` is the
    generator's gross output and is NOT scaled by the scenario's machine-power
    multiplier (the 5x run multiplies consumers, not generators). Loaded by
    `gamedata.load_generators`, never constructed from a note."""

    generator_class: ProducerClass
    fuel_item_id: ItemId
    burn_rate_per_min: float
    power_mw: float
    supplemental: tuple[tuple[ItemId, float], ...] = ()   # (item, rate): water
    byproduct: tuple[tuple[ItemId, float], ...] = ()      # (item, rate): waste

    def __post_init__(self) -> None:
        if self.burn_rate_per_min <= 0 or self.power_mw <= 0:
            raise ValueError(f"{self.generator_class}/{self.fuel_item_id}: rates must be positive")


@dataclass(frozen=True)
class PowerBalance:
    """Power inside the solve (crossover A25.3 P1, mechanics A29).

        generators      the (generator, fuel) pairs the district may build;
                        each becomes a column consuming fuel and water
        grid_mw         standing supply declared outside the district: an
                        existing or imported grid, A25.3 P3 "base + fed"
        spare_mw        the required margin, held above the draw
        extraction_mw   the declared extractors at NAMEPLATE (P2), a constant

    The balance row: generated + grid >= lane MW + extraction + spare. Lane
    MW is the LP's machine-time at the chosen power statistic, which the
    scenario multiplier scales; generator MW is not scaled.
    """

    generators: tuple[GeneratorFuel, ...] = ()
    grid_mw: float = 0.0
    spare_mw: float = 0.0
    extraction_mw: float = 0.0

    def __post_init__(self) -> None:
        for name in ("grid_mw", "spare_mw", "extraction_mw"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        seen = [(g.generator_class, g.fuel_item_id) for g in self.generators]
        if len(seen) != len(set(seen)):
            raise ValueError("duplicate (generator, fuel) pair")


@dataclass(frozen=True)
class DistrictRequest:
    """A supply-side solve: selected outputs, a recipe set, caps, and the goal
    that breaks ties among plans of equal weighted output.

    `weights` is the SECONDARY objective: among the plans that reach the
    maximum weighted output, the one cheapest under these weights is chosen.
    It is the same `Weights` the demand-driven solve uses, so a named goal
    (balanced, resources, power, buildings) means the same thing in both.
    """

    targets: tuple[DistrictTarget, ...]
    allowed_recipes: AllowedRecipes = AllowedRecipes()
    resource_caps: tuple[ResourceCap, ...] = ()
    weights: Weights = Weights()
    #: None: power stays outside the solve, as `solve` leaves it (D5)
    power: PowerBalance | None = None

    def __post_init__(self) -> None:
        if not self.targets:
            raise ValueError("a district solve needs at least one target")
        seen = [t.item_id for t in self.targets]
        dupes = {i for i in seen if seen.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate district targets: {sorted(dupes)}")
        if not any(t.is_active for t in self.targets):
            raise ValueError(
                "every target has weight 0 and no floor: nothing to maximise and "
                "nothing to hold. Exclusion is a per-target setting, not a request"
            )
        capped = {c.item_id for c in self.resource_caps}
        both = capped & set(seen)
        if both:
            raise ValueError(f"item is both a target and a capped input: {sorted(both)}")


@dataclass(frozen=True)
class TargetRate:
    """What one target got. `at_floor` says the floor is all it got."""

    item_id: ItemId
    rate_per_min: float
    weight: float
    minimum_rate: float | None
    at_floor: bool
    excluded: bool


@dataclass(frozen=True)
class BindingCap:
    """A resource cap the solve pressed against, with its shadow price.

    `shadow_price` is d(weighted output) / d(cap), read from the LP's dual on
    the cap's bound. It can be 0.0 at a degenerate optimum; the cap is still
    reported as binding because the draw sits on it.
    """

    item_id: ItemId
    cap_per_min: float
    shadow_price: float


@dataclass(frozen=True)
class GeneratorUse:
    generator_class: ProducerClass
    fuel_item_id: ItemId
    count: float               # fractional generator-equivalents
    mw: float
    fuel_per_min: float
    supplemental_per_min: tuple[tuple[ItemId, float], ...] = ()


@dataclass(frozen=True)
class DistrictPower:
    """The balance as solved. `margin_mw` is generated + grid - lane -
    extraction - spare, which the row holds at >= 0; `binding` says the row
    was tight and `shadow_price` what one more MW of supply would buy in
    weighted output. Reported; nothing here judges it."""

    lane_mw: float
    extraction_mw: float
    grid_mw: float
    spare_mw: float
    generated_mw: float
    margin_mw: float
    generators: tuple[GeneratorUse, ...]
    binding: bool
    shadow_price: float


@dataclass(frozen=True)
class DistrictResponse:
    """The district plan: a `SolveResponse` plus what each target got and why.

    `plan.items` carries each target's output as that item's net flow, which is
    the material ledger v5.5 Stage 1 asks for. `targets` keeps request order;
    nothing here is ranked.
    """

    plan: SolveResponse
    targets: tuple[TargetRate, ...]
    weighted_output: float
    goal: Weights
    binding: tuple[BindingCap, ...]
    #: None when the request carried no PowerBalance
    power: DistrictPower | None = None
