"""One bill composition (reconciliation R2, 2026-11-17).

portfolio_run.compose_bill was a copy of district_run's block ("as
district_run.py composes them"). Both now call
`progression.district.compose_bill`. This fails if either tool scales Project
Assembly rows or reads schematic costs itself again, the way
tests/test_shared_power.py guards power assembly.
"""
from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("tool", ["portfolio_run.py", "district_run.py"])
def test_the_tools_do_not_compose_a_bill_themselves(tool):
    src = (REPO / "tools" / tool).read_text(encoding="utf-8")
    for owned in ("apply_project_assembly_quantity", "schematic_costs(", "bill_units("):
        assert owned not in src, f"{tool} composes the bill itself ({owned})"
    assert "compose_bill(" in src


def test_compose_bill_refuses_an_unknown_phase():
    from production_adapter import load
    from progression.district import DistrictError, compose_bill

    with pytest.raises(DistrictError, match="no Project Assembly phase"):
        compose_bill(REPO, load(REPO), (9,), ())
