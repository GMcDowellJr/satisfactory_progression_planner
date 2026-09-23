"""The driver. `python -m busmodel --repo . <declaration>`.

The scratch model this replaces had none: every published figure was produced by
an ad-hoc call and the call was not kept, which is why A3.5 is not reproducible
from the code that produced it.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from production_adapter import gamedata
from production_adapter.scenario import Scenario
from realization.contracts import Disposition

from . import declarations as decls
from .model import SizingBasis, solve
from .report import out_of_scope_draw, render, render_out_of_scope

#: The scenario of record: 1.25x parts, 2x power, game 1.2.4.0 CL#502094.
#: `MARGINAL_PEAK_DEBOTTLENECK` carries a 2x Space Elevator multiplier, which
#: this model does not consume -- it scales Project Assembly deliveries, not
#: recipes -- so it is named rather than defaulted.
SCENARIO_OF_RECORD = Scenario(recipe_input_multiplier=1.25, machine_power_multiplier=2.0)

CASES = (
    "storage_review_T1-2",
    "storage_review_T3-4",
    "storage_review_T1-2_base_rip",
    "worked_case_A4",
    "worked_case_A4_full_rate_plate",
    "crossover_A",
    "crossover_B",
)


def build(case: str, data):
    if case == "storage_review_T1-2":
        return decls.storage_review_t1_2(data)
    if case == "storage_review_T3-4":
        return decls.storage_review_t3_4(data)
    if case == "storage_review_T1-2_base_rip":
        return decls.storage_review_t1_2_base_rip(data)
    if case == "worked_case_A4":
        return decls.worked_case_a4(data)
    if case == "worked_case_A4_full_rate_plate":
        return decls.worked_case_a4(data, build_plate_disposition=Disposition.BACK_UP)
    if case == "crossover_A":
        return decls.crossover_regime(data, stitched=False)
    if case == "crossover_B":
        return decls.crossover_regime(data, stitched=True)
    raise SystemExit(f"unknown case {case!r}; one of {', '.join(CASES)}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("case", choices=CASES)
    p.add_argument("--repo", default=".", help="repo root holding planning_data/")
    p.add_argument("--multiplier", type=float, default=1.25,
                   help="recipe input multiplier; 1.0 is canonical")
    # `peak` stays in the choices so that asking for it reaches `solve`'s
    # refusal, which says why it is not a basis any more and where the peak is
    # reported instead. Dropping it from `choices` would answer with argparse's
    # "invalid choice", which explains nothing.
    p.add_argument("--basis", choices=[b.value for b in SizingBasis],
                   default=SizingBasis.AVERAGE.value)
    p.add_argument("--machine-floor", type=int, default=1)
    args = p.parse_args(argv)

    scenario = (
        Scenario() if args.multiplier == 1.0
        else Scenario(recipe_input_multiplier=args.multiplier, machine_power_multiplier=2.0)
    )
    data = gamedata.load(pathlib.Path(args.repo), scenario)
    decl = build(args.case, data)
    solution = solve(decl, data, sizing_basis=SizingBasis(args.basis),
                     machine_floor=args.machine_floor)
    print(render(solution, title=f"{decl.name}  @ {args.multiplier}x  "
                                 f"[{data.game_build_id}]"))
    print(render_out_of_scope(out_of_scope_draw(decl, data, solution), data))
    print(f"  provenance: {decl.provenance}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
