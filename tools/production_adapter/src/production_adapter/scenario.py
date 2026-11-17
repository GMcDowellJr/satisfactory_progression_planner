"""Runtime scenario modifiers (implementation plan section 8).

Canonical game facts are never mutated. A Scenario is applied when the reference
layer is transformed into a solver's game data, so the same CSVs serve every
scenario in the same process.

Proven in the Phase 0 harness: applying these at transform time reproduced correct
multi-stage compounding with zero changes to the solver.

**Scenarios round.** `docs/decisions/demand_expansion_scope_and_site_capacity.md`
section 3.2.5: the recipe-cost multiplier applies to a recipe's per-cycle integer
part counts and the result is rounded to the nearest whole number, per input.
Confirmed in game at 1.25x in both directions (3.2.4). Rounding is not expressible
on a rate, which is why `apply_input_rate` was removed rather than adjusted: a
rate-shaped input transform cannot model the game and must not be available to
call.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

#: `recipe_io.csv.unit` values. Solids are counted; fluids are measured.
ITEM_UNIT = "items"
FLUID_UNIT = "m3"

#: Which unit a fluid amount is rounded in. **OBSERVED 2026-10-10** (demand-
#: expansion record Amendment 2): on a 1.25x save, game 1.2.4.0 CL#502094, the
#: Plastic recipe shows 3.75 Crude Oil per cycle (3 at 1x), with its outputs
#: unchanged at 20 Plastic and 10 Heavy Oil Residue per minute. So fluids are
#: NOT rounded to whole m3; "m3" is ruled out. "mL" rounds in the game's
#: internal unit and None leaves fluids unrounded, and on this build the two
#: cannot differ: every per-cycle fluid count is a multiple of 0.5 m3 and every
#: selectable multiplier a multiple of 0.25, so a scaled fluid is always a whole
#: number of millilitres. "mL" is carried as the rule because it is the one
#: consistent with 3.2.3's finding that the code does scale fluids. Until
#: 2026-10-10 this constant was "m3", which overstated Crude Oil per Thermal
#: Propulsion Rocket at 1.25x by 6.7% (880.5 against 825.47).
FLUID_ROUNDING_UNIT: str | None = "mL"

#: The three admissible values of `Scenario.fluid_rounding_unit`.
FLUID_ROUNDING_VARIANTS: tuple[str | None, ...] = (FLUID_UNIT, "mL", None)

_ML_PER_M3 = 1000

#: The floor on a positive SOLID input below 1x. **OBSERVED 2026-10-26**
#: (demand-expansion record A5.1, Greg on a 0.25x save, 1.2.4.0 CL#502094):
#: Iron Rod's 1 Iron Ingot reads 1 at 0.25x, where rounding alone gives 0. Not a
#: field: the game fixes it, so no scenario may declare another (reframe A15.2
#: B4, decided by Greg 2026-11-17; the code default since reconciliation R4).
SOLID_INPUT_FLOOR = 1


class FluidFloorUndeclared(ValueError):
    """Below 1x the fluid floor's unit is unobserved (demand A5.2), so it is declared."""


def _round_half_away_from_zero(value: Decimal) -> Decimal:
    """Nearest integer, halves away from zero (record 3.2.5).

    Not `round()`: Python rounds halves to even, which would send 2.5 to 2. The
    tie case was adopted on 3.2.5 before any tie had been observed; it has since
    been read in game (crossover record Amendment 1, 2026-09-21: Cable 2.5 -> 3,
    Reinforced Iron Plate 7.5 -> 8, on 1.2.4.0 CL#502094), so this is now a
    measured rule, not an assumption.
    """
    return value.quantize(Decimal(1), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Scenario:
    """The three configurable game modifiers.

    recipe_input_multiplier
        Scales every recipe's *inputs*. Outputs are unchanged — the game setting
        raises the cost of a recipe, not its yield. Applied to per-cycle amounts
        and rounded per input, then compounded across stages, which is intended:
        a 1.25x setting raises Smart Plating's raw ore demand by considerably
        more than 1.25x, and not by a constant factor.
    machine_power_multiplier
        Scales machine power draw. Applies to fixed base power and to the
        per-recipe variable-power range alike.
    project_assembly_requirement_multiplier
        Scales Project Assembly delivery quantities. Consumed by the Phase 2
        scheduler, not by the production solver, so it is carried here but not
        applied by `apply_input_amount` below.
    fluid_rounding_unit
        Which unit a fluid input is rounded in: "mL" (observed, the default),
        None (identical on this build), or "m3" (ruled out by the 2026-10-10
        read; selectable only to reproduce figures computed under it before
        then). Demand-expansion record Amendments 1 and 2.
    fluid_input_floor
        The minimum, in m3, a positive FLUID input may round down to below 1x.
        **Unobserved** (demand A5.2): if the game's floor is one internal unit
        (1 mL) it never binds on this build (the smallest scaled fluid is
        250 mL), and 0 states that; if it is one stated unit, 1 holds 0.75 m3 of
        Plastic's Crude Oil at 1. The two disagree on 31 fluid inputs at 0.25x
        and 6 at 0.50x/0.75x, so below 1x it is REQUIRED and construction
        refuses without it. The discriminating read is Plastic's Crude Oil on a
        0.25x save. Solids need no declaration: their floor is observed
        (`SOLID_INPUT_FLOOR`, A5.1).
    input_amount_floor
        LEGACY (portfolio-inputs/2 and earlier callers), kept so a /2 document
        keeps its meaning. It used to floor solids and fluids alike. Since R4
        (2026-11-17) solids are floored at 1 by observation, so only 1 still
        means what it meant: it sets `fluid_input_floor` to 1 m3 and every
        figure computed under it is unchanged. 0 (solids allowed to reach zero)
        contradicts A5.1 and any other value never had a reading; both are
        refused by name. New callers declare `fluid_input_floor`.
    """

    recipe_input_multiplier: float = 1.0
    machine_power_multiplier: float = 1.0
    project_assembly_requirement_multiplier: float = 1.0
    input_amount_floor: float | None = None
    fluid_rounding_unit: str | None = FLUID_ROUNDING_UNIT
    fluid_input_floor: float | None = None

    def __post_init__(self) -> None:
        if self.fluid_rounding_unit not in FLUID_ROUNDING_VARIANTS:
            raise ValueError(
                f"fluid_rounding_unit must be one of {FLUID_ROUNDING_VARIANTS}, "
                f"got {self.fluid_rounding_unit!r}"
            )
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
        for name in ("input_amount_floor", "fluid_input_floor"):
            v = getattr(self, name)
            if v is None:
                continue
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise TypeError(f"{name} must be numeric or None")
            if v < 0:
                raise ValueError(f"{name} must not be negative, got {v}")
        legacy = self.input_amount_floor
        if legacy is not None:
            if legacy != SOLID_INPUT_FLOOR:
                raise ValueError(
                    f"input_amount_floor={legacy:g} would floor solid inputs at "
                    f"{legacy:g}, but the solid floor is observed to be "
                    f"{SOLID_INPUT_FLOOR} (demand record A5.1). Declare the fluid "
                    "floor alone with fluid_input_floor (0 or 1, in m3)."
                )
            if self.fluid_input_floor is None:
                object.__setattr__(self, "fluid_input_floor", float(legacy))
            elif self.fluid_input_floor != legacy:
                raise ValueError(
                    f"input_amount_floor={legacy:g} (legacy: fluids at 1 m3) "
                    f"contradicts fluid_input_floor={self.fluid_input_floor:g}; "
                    "declare one of them"
                )
        if self.recipe_input_multiplier < 1.0 and self.fluid_input_floor is None:
            raise FluidFloorUndeclared(
                f"recipe_input_multiplier {self.recipe_input_multiplier} is below 1x. "
                f"Solid inputs are floored at {SOLID_INPUT_FLOOR} (observed, demand "
                "A5.1); the FLUID floor's unit is unobserved (A5.2), so declare "
                "fluid_input_floor: 0 if the game floors at one internal unit "
                "(never binds here), 1 if at one m3. The read that decides it: "
                "Plastic's Crude Oil on a 0.25x save (0.75 or 1)."
            )

    @property
    def is_canonical(self) -> bool:
        """True when this scenario leaves canonical values untouched."""
        return (
            self.recipe_input_multiplier == 1.0
            and self.machine_power_multiplier == 1.0
            and self.project_assembly_requirement_multiplier == 1.0
        )

    def apply_input_amount(self, amount_per_cycle: float, unit: str = ITEM_UNIT) -> float:
        """Scale one input's per-cycle amount and round it, per record 3.2.5.

        At 1x this is the identity, including for the one fractional fluid amount
        in the reference layer (Recipe_Battery_C draws 2.5 m3 of Sulfuric Acid):
        the game states canonical costs when no multiplier is set, so rounding
        them would invent a cost.
        """
        multiplier = self.recipe_input_multiplier
        if multiplier == 1.0:
            return amount_per_cycle

        amount = Decimal(repr(amount_per_cycle))
        factor = Decimal(repr(multiplier))
        if unit == FLUID_UNIT:
            if self.fluid_rounding_unit is None:
                scaled = amount * factor
            elif self.fluid_rounding_unit == "mL":
                scaled = _round_half_away_from_zero(
                    amount * _ML_PER_M3 * factor
                ) / _ML_PER_M3
            else:
                scaled = _round_half_away_from_zero(amount * factor)
        else:
            scaled = _round_half_away_from_zero(amount * factor)

        if amount > 0 and multiplier < 1.0:
            # Floors exist only below 1x: at or above it no positive input can
            # round below its own canonical unit. Solids by observation (A5.1),
            # fluids by declaration (A5.2); construction refuses the latter
            # undeclared, so it is set here.
            floor = Decimal(SOLID_INPUT_FLOOR) if unit != FLUID_UNIT else \
                Decimal(repr(self.fluid_input_floor))
            if scaled < floor:
                scaled = floor
        return float(scaled)

    def apply_output_rate(self, rate_per_min: float) -> float:
        """Identity. Present so callers never have to remember the asymmetry."""
        return rate_per_min

    def apply_power(self, mw: float) -> float:
        return mw * self.machine_power_multiplier

    def apply_project_assembly_quantity(self, quantity: float) -> float:
        """Scale one delivery quantity and round it, per record 3.2.5.

        The SAME rule as recipe inputs, observed separately rather than
        assumed to carry over: read in game 2026-09-22, the 0.25x elevator-
        parts setting turns phase 1's 50 Smart Plating into 13. 12.5 -> 13
        rules out half-down and half-to-even in one read.

        Ceil is NOT ruled out and cannot be: no selectable multiplier
        produces a non-half fraction on any of the fifteen delivery rows, so
        ceil and nearest-half-away agree on every reachable cell. A1.2's
        shape — the distinction cannot arise in this domain.

        1x is the identity, for the reason `apply_input_amount` has one: the
        game states canonical quantities when no multiplier is set.

        No input floor is applied here: the floors (`SOLID_INPUT_FLOOR`,
        `fluid_input_floor`) are about recipe INPUTS, and deliveries never
        reach one — the smallest 1x quantity is 50 and the smallest
        multiplier is 0.25. Pinned by test rather than left as a reading.
        """
        multiplier = self.project_assembly_requirement_multiplier
        if multiplier == 1.0:
            return quantity
        return float(_round_half_away_from_zero(
            Decimal(repr(quantity)) * Decimal(repr(multiplier))
        ))

    def canonical(self) -> "Scenario":
        """The unmodified scenario, for computing `PowerReport.canonical_mw`."""
        return Scenario(fluid_rounding_unit=self.fluid_rounding_unit)


CHALLENGE_1_25X_2X = Scenario(
    recipe_input_multiplier=1.25,
    machine_power_multiplier=2.0,
    project_assembly_requirement_multiplier=1.0,
)

#: The scenario of record for every worked example in the 2026-09-19 decision
#: record: Marginal - Peak Demand - Debottleneck (3.3.1), on game 1.2.4.0
#: CL#502094, single-player. Distinct from CHALLENGE_1_25X_2X, which carries a
#: 1.0 Project Assembly multiplier and is therefore a different save.
MARGINAL_PEAK_DEBOTTLENECK = Scenario(
    recipe_input_multiplier=1.25,
    machine_power_multiplier=2.0,
    project_assembly_requirement_multiplier=2.0,
)
