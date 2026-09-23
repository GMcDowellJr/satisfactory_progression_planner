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

#: Which unit a fluid amount is rounded in. **UNOBSERVED** — record 3.2.5 adopts
#: the same nearest-integer rule for fluids as for solids but does not say in
#: which unit, and the two disagree materially: 3 m3 x 1.25 rounds to 4 m3 in m3
#: and to 3.75 m3 in mL. The reference layer states both (`amount_per_cycle` in
#: m3, `amount_per_cycle_raw` in mL). "m3" rounds in the displayed unit; "mL"
#: rounds in the game's internal one; None leaves fluids unrounded, which is what
#: the 3.2.2 computation behind the 66,423 figure actually did. Immaterial for
#: Modular Frame (3.2.3, variants A-D identical); material for a fluid-heavy
#: target. Named here rather than compiled into the arithmetic.
FLUID_ROUNDING_UNIT: str | None = FLUID_UNIT

_ML_PER_M3 = 1000


def _round_half_away_from_zero(value: Decimal) -> Decimal:
    """Nearest integer, halves away from zero (record 3.2.5).

    Not `round()`: Python rounds halves to even, which would send 2.5 to 2. The
    tie case is unobserved in game — record 10.3 of the 2026-09-21 storage review
    proposes a two-building read that settles it — so this is the adopted rule
    standing on 3.2.5, not a measurement.
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
    input_amount_floor
        The minimum a positive input may round down to. **Unresolved** (record
        3.2.3): patch 1.2.3.0 fixed the 1.75x setting zeroing liquid costs, which
        establishes that no floor was universal before it, and no floor has been
        observed since. It cannot bind at multipliers >= 1x, so it is required
        only below 1x — where it is declared by the caller rather than assumed,
        and construction refuses without it.
    """

    recipe_input_multiplier: float = 1.0
    machine_power_multiplier: float = 1.0
    project_assembly_requirement_multiplier: float = 1.0
    input_amount_floor: float | None = None

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
        floor = self.input_amount_floor
        if floor is not None:
            if not isinstance(floor, (int, float)) or isinstance(floor, bool):
                raise TypeError("input_amount_floor must be numeric or None")
            if floor < 0:
                raise ValueError(f"input_amount_floor must not be negative, got {floor}")
        elif self.recipe_input_multiplier < 1.0:
            raise ValueError(
                f"recipe_input_multiplier {self.recipe_input_multiplier} is below 1x, "
                "where an input can round to zero. The game's floor rule is "
                "unobserved (record 3.2.3), so it is declared, not assumed: pass "
                "input_amount_floor=1 to hold positive inputs at one unit, or "
                "input_amount_floor=0 to allow zero."
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
            if FLUID_ROUNDING_UNIT is None:
                scaled = amount * factor
            elif FLUID_ROUNDING_UNIT == "mL":
                scaled = _round_half_away_from_zero(
                    amount * _ML_PER_M3 * factor
                ) / _ML_PER_M3
            else:
                scaled = _round_half_away_from_zero(amount * factor)
        else:
            scaled = _round_half_away_from_zero(amount * factor)

        if self.input_amount_floor is not None and amount > 0:
            floor = Decimal(repr(self.input_amount_floor))
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

        `input_amount_floor` is NOT applied here. It is the unresolved sub-1x
        question for recipe INPUTS, and deliveries never reach it — the
        smallest 1x quantity is 50 and the smallest multiplier is 0.25.
        Pinned by test rather than left as a reading.
        """
        multiplier = self.project_assembly_requirement_multiplier
        if multiplier == 1.0:
            return quantity
        return float(_round_half_away_from_zero(
            Decimal(repr(quantity)) * Decimal(repr(multiplier))
        ))

    def canonical(self) -> "Scenario":
        """The unmodified scenario, for computing `PowerReport.canonical_mw`."""
        return Scenario()


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
