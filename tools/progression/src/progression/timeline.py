"""Project Assembly duration from modelled rates, with storage-priority banks.

Site-planner reframe A15.2, decided by Greg 2026-11-17. Reconciliation R8.

B3, the practice this models (Greg's 50x and 100x elevator-part runs):

- A smart splitter on a shared feed lane sends ALL of it to a dedicated bank of
  machines making a part for storage (his example: 4 underclocked
  constructors, 73 Iron Plate/min).
- When storage fills, backpressure flips the splitter to overflow, which
  feeds the Project Assembly lanes.
- As stock is drawn down, the splitter sends feed to refill storage first.
- A standard splitter works as a bootstrap. Round-robin, skipping a blocked
  output: backpressure record §2, cited as evidence.

Q6: the container decides how long filling takes. Its type is gated by
unlocks, and capacity is slots x stack (crossover A7.3; slots stated by Greg:
24 Storage Container, 48 Industrial Storage Container). So the report gives
fill time per container option the playthrough owns (`container_options`).
Withdrawals are NOT declared in this version (Q6), so a phase is two segments
per bank: FILLING, then FULL.

The model, stated so it can be argued with:

    filling   the bank takes b = min(intake, offered) of the feed. "offered"
              is the whole feed for a smart splitter (priority) and the
              declared round-robin share for a standard one. Whatever the
              bank does not take goes to the PA lanes. Storage fills at
              bank_output x b / intake.
    full      the bank backs up; the PA lanes get the whole feed.
    PA lane   a PA part's rate scales linearly with the share of its feed lane
              that reaches it. That holds while the feed is the lane's
              bottleneck, which is the case the practice exists for. It is an
              assumption, not a read.
    duration  for each PA part, the time its cumulative output reaches the
              E-scaled bill. The phase takes the longest of them. The baseline
              is the same without banks, and the delay is the difference.

Time segments, not a minute-by-minute simulation. It chooses nothing: banks,
splitters, shares and containers are declared, and a PA part fed by more
than one bank is refused (composition is not modelled).
"""
from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass

from production_adapter.contracts import ItemId

from .playthrough import PlaythroughState
from .unlocks import buildings_unlocked

SMART = "smart"
STANDARD = "standard"
SPLITTERS = (SMART, STANDARD)

#: Crossover A7.3 (Greg's statement, brought forward by reframe A15.4): slots
#: per container, keyed by building class as building_recipes.csv names them.
CONTAINER_SLOTS = {
    "Desc_StorageContainerMk1_C": 24,
    "Desc_StorageContainerMk2_C": 48,
}

_EPS = 1e-9


class TimelineError(ValueError):
    """A timeline that cannot be computed without guessing; refused by name."""


@dataclass(frozen=True)
class ContainerOption:
    building_class: str
    slots: int
    count: int
    capacity_units: float


def container_options(
    repo_root: str | pathlib.Path,
    state: PlaythroughState,
    stack_size: int,
    count: int,
) -> tuple[ContainerOption, ...]:
    """Q6: every container type the playthrough can build, `count` of them,
    holding an item of `stack_size`. Smallest first. Nothing is chosen."""
    if count < 1 or stack_size < 1:
        raise TimelineError("container count and stack size must be at least 1")
    owned = state.owned_schematics
    open_buildings, _ = buildings_unlocked(repo_root, lambda s: s.schematic_id in owned)
    out = [ContainerOption(cls, slots, count, float(slots * stack_size * count))
           for cls, slots in CONTAINER_SLOTS.items() if cls in open_buildings]
    if not out:
        raise TimelineError("no storage container is unlocked in this playthrough state")
    return tuple(sorted(out, key=lambda o: o.capacity_units))


@dataclass(frozen=True)
class StorageBank:
    """A dedicated storage-priority bank on a shared feed lane. DECLARED."""

    name: str
    storage_item: ItemId          # what the bank makes into storage
    feed_per_min: float           # the shared feed lane, total
    bank_intake_per_min: float    # feed the bank's machines take when running
    bank_output_per_min: float    # storage_item they make at that intake
    capacity_units: float         # storage capacity, in storage_item units
    pa_items: tuple[ItemId, ...]  # PA parts whose lanes get the rest of the feed
    splitter: str                 # SMART | STANDARD
    standard_share: float | None = None   # round-robin share offered the bank

    def __post_init__(self) -> None:
        if self.splitter not in SPLITTERS:
            raise TimelineError(f"{self.name}: splitter {self.splitter!r}; known {SPLITTERS}")
        if (self.splitter == STANDARD) != (self.standard_share is not None):
            raise TimelineError(f"{self.name}: standard_share is declared with a standard "
                                "splitter and only then")
        if self.standard_share is not None and not 0 < self.standard_share < 1:
            raise TimelineError(f"{self.name}: standard_share must be in (0, 1)")
        for field in ("feed_per_min", "bank_intake_per_min", "bank_output_per_min",
                      "capacity_units"):
            if not getattr(self, field) > 0:
                raise TimelineError(f"{self.name}: {field} must be positive")
        if not self.pa_items:
            raise TimelineError(f"{self.name}: name the PA parts its feed lane serves")

    @property
    def bank_take_per_min(self) -> float:
        offered = self.feed_per_min if self.splitter == SMART else \
            self.feed_per_min * self.standard_share
        return min(self.bank_intake_per_min, offered)

    @property
    def pa_share_filling(self) -> float:
        """Share of the feed reaching the PA lanes while storage fills."""
        return (self.feed_per_min - self.bank_take_per_min) / self.feed_per_min

    @property
    def fill_rate_per_min(self) -> float:
        return self.bank_output_per_min * self.bank_take_per_min / self.bank_intake_per_min

    @property
    def fill_min(self) -> float:
        return self.capacity_units / self.fill_rate_per_min


@dataclass(frozen=True)
class PartTimeline:
    item_id: ItemId
    bill_units: float
    full_rate_per_min: float
    filling_rate_per_min: float
    bank: str | None
    finish_min: float
    baseline_min: float


@dataclass(frozen=True)
class PhaseTimeline:
    parts: tuple[PartTimeline, ...]
    banks: tuple[StorageBank, ...]
    duration_min: float
    baseline_min: float
    stock_at_finish: tuple[tuple[str, ItemId, float], ...]   # bank, item, units in storage

    @property
    def delay_min(self) -> float:
        return self.duration_min - self.baseline_min

    def report(self) -> str:
        lines = [f"phase: {self.duration_min:.1f} min with banks, {self.baseline_min:.1f} min "
                 f"without (+{self.delay_min:.1f} min)"]
        for b in self.banks:
            lines.append(f"  bank {b.name} ({b.splitter}): fills {b.capacity_units:g} "
                         f"{b.storage_item} in {b.fill_min:.1f} min; PA lanes get "
                         f"{100 * b.pa_share_filling:.0f}% of the feed while it fills")
        for p in self.parts:
            lines.append(f"  {p.item_id}: {p.bill_units:g} by {p.finish_min:.1f} min "
                         f"(alone {p.baseline_min:.1f})")
        for bank, item, units in self.stock_at_finish:
            lines.append(f"  in storage at the end: {units:g} {item} ({bank})")
        lines.append("  not modelled: withdrawals during the phase (Q6), more than one "
                     "bank per PA part; PA rate assumed linear in its feed share")
        return "\n".join(lines)


def _finish(q: float, r1: float, t1: float, r2: float) -> float:
    """Time cumulative output reaches q: rate r1 for t1 minutes, then r2."""
    if r1 > _EPS and r1 * t1 >= q - _EPS:
        return q / r1
    if r2 <= _EPS:
        return math.inf
    return t1 + (q - r1 * t1) / r2


def pa_duration(
    bill: dict[ItemId, float],
    full_rates: dict[ItemId, float],
    banks: tuple[StorageBank, ...] = (),
) -> PhaseTimeline:
    """`bill` is the phase's E-scaled delivery quantities; `full_rates` what the
    PA lanes make of each part with their whole feed (from a solved and realized
    plan). Every bill part needs a positive rate, and is refused by name
    otherwise."""
    if not bill:
        raise TimelineError("an empty bill has no duration")
    missing = sorted(i for i in bill if not full_rates.get(i, 0) > 0)
    if missing:
        raise TimelineError(f"no positive PA rate for {missing}; the phase cannot finish")
    served: dict[ItemId, StorageBank] = {}
    for b in banks:
        for item in b.pa_items:
            if item not in bill:
                raise TimelineError(f"bank {b.name} serves {item}, which the bill does not hold")
            if item in served:
                raise TimelineError(f"{item} is served by banks {served[item].name} and {b.name}; "
                                    "composition is not modelled")
            served[item] = b
    parts = []
    for item, q in bill.items():
        r = full_rates[item]
        b = served.get(item)
        if b is None:
            parts.append(PartTimeline(item, q, r, r, None, q / r, q / r))
        else:
            r1 = r * b.pa_share_filling
            parts.append(PartTimeline(item, q, r, r1, b.name, _finish(q, r1, b.fill_min, r), q / r))
    duration = max(p.finish_min for p in parts)
    stock = tuple((b.name, b.storage_item,
                   min(b.capacity_units, b.fill_rate_per_min * min(duration, b.fill_min)))
                  for b in banks)
    return PhaseTimeline(tuple(parts), tuple(banks), duration,
                         max(p.baseline_min for p in parts), stock)
