"""tools/site_planner_web/index.html: the portfolio-plan/1 renderer.

The page is static JS that cannot import Python, so the constants it shares
with the solve side are pinned here: the schema tag it accepts, the dual it
treats as zero, and the residue it treats as solver noise. Change one side
without the other and this fails. Rendering itself is checked in a browser
(handoff test ladder), not here.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
PAGE = REPO / "tools" / "site_planner_web" / "index.html"


def _module(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _const(name: str) -> str:
    found = re.findall(rf"^const {name} = ([^;]+);", PAGE.read_text(encoding="utf-8"), re.M)
    assert len(found) == 1, f"{name}: expected one declaration, found {found}"
    return found[0].strip()


def test_schema_is_the_records():
    portfolio_run = _module("portfolio_run")
    assert _const("SCHEMA") == f'"{portfolio_run.RECORD_SCHEMA}"'


def test_zero_dual_is_shadow_texts():
    shadow_text = _module("shadow_text")
    assert float(_const("ZERO")) == shadow_text.ZERO


def test_noise_is_the_report_epsilon():
    from production_adapter.lp_backend import REPORT_EPSILON

    assert float(_const("NOISE")) == REPORT_EPSILON


def test_page_reads_no_reference_csv():
    """One loader (AGENTS.md): the page gets names, forms and stack sizes
    from the record, never from planning_data."""
    text = PAGE.read_text(encoding="utf-8")
    assert ".csv" not in text and "planning_data" not in text
