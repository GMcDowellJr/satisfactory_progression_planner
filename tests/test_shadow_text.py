"""tools/shadow_text.py: shadow prices in plain language (Greg, 2026-10-19:
"per unit, marginal"). Wording only; each phrase is pinned once."""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("shadow_text", REPO / "tools" / "shadow_text.py")
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)


@pytest.mark.parametrize("args, kw, text", [
    ((2 / 3, "Iron Ore", "Iron Plate/min"), {},
     "+1/min Iron Ore -> +0.6667 Iron Plate/min at the margin"),
    ((0.0, "Iron Ore", "Iron Plate/min"), {}, "+1/min Iron Ore -> no gain at the margin"),
    ((None, "Iron Ore", "Iron Plate/min"), {}, "+1/min Iron Ore -> not priced"),
    ((0.2, "Coal", "Steel Ingot/min"), {"high": 0.25},
     "+1/min Coal -> +0.2 to +0.25 Steel Ingot/min at the margin, by which socket gives it"),
])
def test_per_unit(args, kw, text):
    assert st.per_unit(*args, **kw) == text


def test_per_mw_quotes_the_declared_step():
    assert st.MW_STEP == 10.0
    assert st.per_mw(0.005, "Motor/min") == "+10 MW -> +0.05 Motor/min at the margin"
    assert st.per_mw(0.0, "Motor/min") == "+10 MW -> no gain at the margin"


def test_horizon_reads_minutes_to_cover_the_bill():
    # scale 1/200 per min; +10 MW at 1e-4 scale per MW -> 1/0.006 = 166.7 min
    assert st.horizon(1.0e-4, 0.005, 10.0, "+10 MW") == \
        "+10 MW -> horizon 200.0 -> 166.7 min at the margin"
    assert st.horizon(1.0e-4, 0.0, 10.0, "+10 MW") == \
        "+10 MW -> bill scale 0 -> 0.001/min (horizon 1000.0 min) at the margin"
    assert st.horizon(0.0, 0.005, 1.0, "+1/min Coal") == "+1/min Coal -> no gain at the margin"
    assert st.horizon(1.0e-4, 0.005, 10.0, "+10 MW", high=2.0e-4) == \
        "+10 MW -> horizon 200.0 -> 166.7 to 142.9 min at the margin, by which socket gives it"
