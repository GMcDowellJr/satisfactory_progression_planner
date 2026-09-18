"""Runtime scenario modifiers (implementation plan section 8).

Canonical game facts are never mutated. A Scenario is applied when the reference
layer is transformed into a solver's game data, so the same CSVs serve every
scenario in the same process.

Proven in the Phase 0 harness: applying these at transform time reproduced correct
multi-stage compounding with zero changes to the solver.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    """The three configurable game modifiers.

    recipe_input_multiplier
        Scales every recipe's *inputs*. Outputs are unchanged — the game setting
        raises the cost of a recipe, not its yield. Compounds across stages,
        which is intended: a 1.25x setting raises Smart Plating's raw ore demand
        by considerably more than 1.25x.
    machine_power_multiplier
        Scales machine power draw. Applies to fixed base power and to the
        per-recipe variable-power range alike.
    project_assembly_requirement_multiplier
        Scales Project Assembly delivery quantities. Consumed by the Phase 2
        scheduler, not by the production solver, so it is carried here but not
        applied by `apply_*` below.
    """

    recipe_input_multiplier: float = 1.0
    machine_power_multiplier: float = 1.0
    project_assembly_requirement_multiplier: float = 1.0

    def __post_init__(self) -> None:
        for name in (
            "recipe_input_multiplier",
            "machine_power_multiplier",
            "project_assembly_requirement_multiplier",
        ):
            v = getattr(self, name)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise TypeError(f"{name} must be numeric")
            if v <= 0:
                raise ValueError(f"{name} must be positive, got {v}")

    @property
    def is_canonical(self) -> bool:
        """True when this scenario leaves canonical values untouched."""
        return (
            self.recipe_input_multiplier == 1.0
            and self.machine_power_multiplier == 1.0
            and self.project_assembly_requirement_multiplier == 1.0
        )

    def apply_input_rate(self, rate_per_min: float) -> float:
        return rate_per_min * self.recipe_input_multiplier

    def apply_output_rate(self, rate_per_min: float) -> float:
        """Identity. Present so callers never have to remember the asymmetry."""
        return rate_per_min

    def apply_power(self, mw: float) -> float:
        return mw * self.machine_power_multiplier

    def apply_project_assembly_quantity(self, quantity: float) -> float:
        return quantity * self.project_assembly_requirement_multiplier

    def canonical(self) -> "Scenario":
        """The unmodified scenario, for computing `PowerReport.canonical_mw`."""
        return Scenario()


CHALLENGE_1_25X_2X = Scenario(
    recipe_input_multiplier=1.25,
    machine_power_multiplier=2.0,
    project_assembly_requirement_multiplier=1.0,
)
