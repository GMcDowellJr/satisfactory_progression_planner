"""The per-phase rate sheet's guardrails (R1-R4), asserted from the source.

Figures over a real run are pinned in `tests/test_phase_two_run.py`, beside
the phase-2 fixture, rather than re-running phase 2 here.
"""
from __future__ import annotations

import ast
import dataclasses
import importlib.util
import inspect
import pathlib
import sys
import typing

REPO = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("rate_sheet", REPO / "tools" / "rate_sheet.py")
rate_sheet = importlib.util.module_from_spec(_spec)
sys.modules["rate_sheet"] = rate_sheet
_spec.loader.exec_module(rate_sheet)
TREE = ast.parse((REPO / "tools" / "rate_sheet.py").read_text(encoding="utf-8"))


def _called() -> set[str]:
    return {
        (n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", ""))
        for n in ast.walk(TREE) if isinstance(n, ast.Call)
    }


def test_r1_calls_no_layer_and_imports_none():
    assert {"realize", "solve", "run", "paced_run", "bill_for", "replace"}.isdisjoint(_called())
    imported = {n.module for n in ast.walk(TREE) if isinstance(n, ast.ImportFrom)}
    for forbidden in ("goal_run", "progression", "production_adapter.lp_backend",
                      "production_adapter.backend", "realization.realize"):
        assert not [m for m in imported if m and m.startswith(forbidden)], forbidden


def test_r2_ranks_and_rounds_nothing():
    assert {"min", "max", "sorted", "sort", "round"}.isdisjoint(_called())


def test_r3_rows_carry_no_verdict():
    for cls in (rate_sheet.RateRow, rate_sheet.RateSheet, rate_sheet.LaneClock):
        assert bool not in typing.get_type_hints(cls).values(), cls
        assert not [f for f in dataclasses.fields(cls) if f.name.startswith("is_")]


def test_r4_takes_no_scale_and_multiplies_nothing():
    """A sheet holds at the rate it was run at; `sheet` rescales nothing. The
    module-level `/` is pathlib, so the check is on the function body."""
    params = set(inspect.signature(rate_sheet.sheet).parameters)
    assert params == {"report", "goals", "phase", "anchor_goal_id", "horizon_min"}
    (fn,) = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "sheet"]
    assert not [n for n in ast.walk(fn) if isinstance(n, (ast.Mult, ast.Div))]
