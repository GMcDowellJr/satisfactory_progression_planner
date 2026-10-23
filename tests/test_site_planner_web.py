"""tools/site_planner_web/index.html: the portfolio-plan/1 renderer.

The page is static JS that cannot import Python, so the constants it shares
with the solve side are pinned here: the schema tag it accepts, the dual it
treats as zero, and the residue it treats as solver noise. Change one side
without the other and this fails. Rendering itself is checked in a browser
(handoff test ladder), not here.
"""
from __future__ import annotations

import importlib.util
import json
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


# -- picker.html (handoff 2026-10-23 14:48 action 2, first half) ---------------------

PICKER = REPO / "tools" / "site_planner_web" / "picker.html"


def _picker(name: str):
    found = re.findall(rf"^const {name} = ([^;]+);", PICKER.read_text(encoding="utf-8"), re.M)
    assert len(found) == 1, f"{name}: expected one declaration, found {found}"
    return json.loads(found[0])


def test_picker_schemas_are_the_tools():
    assert _picker("NB_SCHEMA") == _module("neighborhoods").EXPORT_SCHEMA
    assert _picker("INPUTS_SCHEMA") == _module("portfolio_run").INPUTS_SCHEMA


def test_picker_goals_are_site_cards():
    assert _picker("GOALS") == list(_module("site_card").GOALS)


def test_picker_extractors_are_the_rate_tables():
    from production_adapter.gamedata import load_logistics

    _, rates = load_logistics(REPO)
    assert sorted(_picker("EXTRACTORS")) == sorted({r.extractor_class for r in rates})


def test_picker_scenario_fields_and_fluid_rounding():
    import dataclasses

    from production_adapter import FLUID_ROUNDING_VARIANTS, Scenario

    assert _picker("SCENARIO_KEYS") == [f.name for f in dataclasses.fields(Scenario)]
    assert _picker("FLUID_ROUNDING") == list(FLUID_ROUNDING_VARIANTS)


def test_picker_reads_no_world_files():
    text = PICKER.read_text(encoding="utf-8")
    assert ".csv" not in text and "planning_data" not in text


# -- in-browser runtime (Greg 2026-10-23 15:36: precomputed defaults + recompute, A10) ---

WEB = REPO / "tools" / "site_planner_web"


def test_picker_orders_are_neighborhoods():
    assert _picker("ORDERS") == list(_module("neighborhoods").ORDERS)


def test_precomputed_export_regenerates_byte_for_byte(tmp_path):
    """The shipped default is derived data: from its policy file, today's
    code and world must reproduce it exactly, or it is stale."""
    nb = _module("neighborhoods")
    default = _picker("DEFAULT_EXPORT")
    shipped = WEB / default["path"]
    policy = json.loads((WEB / "precomputed" / "policy_v020.json").read_text(encoding="utf-8"))
    out = tmp_path / "nb.json"
    nb.write_export(nb.export_for(policy, "default_502094", REPO), out)
    assert out.read_bytes() == shipped.read_bytes()
    assert json.loads(shipped.read_text(encoding="utf-8"))["policy"] == policy


def test_bundle_list_matches_a_fresh_trace():
    import subprocess

    r = subprocess.run([sys.executable, str(WEB / "bundle.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    files = json.loads((WEB / "bundle_files.json").read_text(encoding="utf-8"))
    assert all(f.split("/")[0] in ("tools", "planning_data") for f in files)
    assert "planning_data/game/reference/recipes.csv" in files and "tools/portfolio_run.py" in files


def test_worker_pins_pyodide_0_27_7():
    """Greg 2026-10-19 18:23: Pyodide from the CDN, pinned, as measured."""
    text = (WEB / "worker.js").read_text(encoding="utf-8")
    assert re.findall(r"pyodide/v([\d.]+)/", text) == ["0.27.7"]
