"""tools/portfolio_run.py record (--export): the portfolio-plan/1 document.

Scenario C as in tests/test_portfolio_run.py (oil site r 500 m around
BP_ResourceNode98 + copper site r 500 m around BP_ResourceNode213, tier 6,
bill phase 3 + tiers 5-6, recipe x1). Measured 2026-10-19, container,
py3.13 (site_planner_reframe.md A8.2):

    no Water          the only leftover is Polymer Resin, 53.33/min at the
                      oil site (Fuel refinery by-product, unconsumed=FREE)
    oil pumps Water   no leftover: the resin goes to Residual Plastic

The ledger is the record's reason to exist: the portfolio solve drops the
sites' local D1 warnings, so this is the only place a leftover shows.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


def _module(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


site_card = _module("site_card")
portfolio_run = _module("portfolio_run")

from production_adapter import Scenario, load  # noqa: E402

OIL = "Desc_LiquidOil_C"
RESIN = "Desc_PolymerResin_C"
MINERS = (
    (("resource_node", None), "Build_MinerMk1_C"),
    (("resource_node", OIL), "Build_OilPump_C"),
)
#: below this a ledger residue is solver noise (lp_backend REPORT_EPSILON)
NOISE = 1.0e-4


def _spec(sockets, label, centre_id):
    c = next(s for s in sockets if s.socket_id == centre_id)
    return site_card.SiteSpec(
        label=label, socket_ids=site_card.sockets_within(sockets, c.east_m, c.north_m, 500.0),
        extractors=MINERS, extraction_clock=1.0,
    )


@pytest.fixture(scope="module")
def specs():
    sockets = site_card.load_sockets(REPO, "default_502094")
    return (_spec(sockets, "oil", "BP_ResourceNode98"), _spec(sockets, "copper", "BP_ResourceNode213"))


@pytest.fixture(scope="module")
def data():
    return load(REPO, Scenario())


def _run(specs, water=()):
    return portfolio_run.run(specs, tier=6, scenario=Scenario(), goal="balanced",
                             bill_phases=(3,), bill_tiers=(5, 6), water_sites=water)


@pytest.fixture(scope="module")
def rec_c(specs, data):
    return portfolio_run.record(_run(specs), data)


def _leftovers(rec):
    return [(s["label"], x["item_id"], x["left"]) for s in rec["sites"] for x in s["ledger"]
            if abs(x["left"]) > NOISE]


def test_export_is_one_lf_json_document(specs, data, tmp_path):
    path = tmp_path / "c.json"
    portfolio_run.export(_run(specs), data, path)
    raw = path.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"}\n")
    doc = json.loads(raw)
    assert doc["schema"] == portfolio_run.RECORD_SCHEMA == "portfolio-plan/1"
    assert [s["label"] for s in doc["sites"]] == ["oil", "copper"]


def test_c_the_only_leftover_is_the_fuel_refineries_resin(rec_c):
    left = _leftovers(rec_c)
    assert [(label, item) for label, item, _ in left] == [("oil", RESIN)]
    assert left[0][2] == pytest.approx(53.33, abs=0.01)


def test_c_with_water_the_resin_is_used(specs, data):
    assert _leftovers(portfolio_run.record(_run(specs, water=("oil",)), data)) == []


def test_ledger_rows_balance(rec_c):
    for s in rec_c["sites"]:
        for x in s["ledger"]:
            assert x["left"] == pytest.approx(
                x["produced"] + x["received"] - x["consumed"] - x["burned"] - x["shipped"]
                - x["to_bill"], abs=1e-12)


def test_shipped_matches_received_across_sites(rec_c):
    out = {}
    for s in rec_c["sites"]:
        for x in s["ledger"]:
            out[x["item_id"]] = out.get(x["item_id"], 0.0) + x["shipped"] - x["received"]
    assert all(abs(v) < 1e-9 for v in out.values())


def test_to_bill_sums_to_scale_times_units(rec_c):
    scale = rec_c["bill"]["scale"]
    for item, units in rec_c["bill"]["units"].items():
        made = sum(x["to_bill"] for s in rec_c["sites"] for x in s["ledger"] if x["item_id"] == item)
        assert made >= scale * units * (1.0 - 1e-6), item


def test_caps_carry_the_draw_and_fuel_is_burned(rec_c):
    oil = rec_c["sites"][0]
    crude = next(c for c in oil["caps"] if c["item_id"] == OIL)
    assert crude["cap_per_min"] == 1020.0
    assert 220.0 < crude["drawn_per_min"] < 250.0
    fuel = next(x for x in oil["ledger"] if x["item_id"] == "Desc_LiquidFuel_C")
    assert fuel["burned"] == pytest.approx(fuel["produced"], rel=1e-9)


def test_names_cover_every_id_the_document_mentions(rec_c):
    items = set(rec_c["bill"]["units"])
    recipes = set()
    for s in rec_c["sites"]:
        items |= {c["item_id"] for c in s["caps"]} | {x["item_id"] for x in s["ledger"]}
        recipes |= {u["recipe_id"] for u in s["recipes"]}
    assert items <= set(rec_c["names"]["items"])
    assert recipes <= set(rec_c["names"]["recipes"])


# -- additions 2026-10-23 (handoff action 1, "Step 1") -------------------------

def test_margin_text_is_the_reports_wording(specs, data):
    """Each binding cap's margin_text appears verbatim in the text report:
    one helper words both, so a client cannot drift from the CLI."""
    pr = _run(specs)
    rec = portfolio_run.record(pr, data)
    text = portfolio_run.report(pr, data)
    phrases = [b["margin_text"] for s in rec["sites"] for b in s["binding"]]
    assert phrases and all(f"BINDING ({p})" in text for p in phrases)
    coal = next(b for b in rec["sites"][0]["binding"] if b["item_id"] == "Desc_Coal_C")
    assert coal["margin_text"] == "+1/min Coal -> horizon 285.8 -> 285.2 min at the margin"
    assert rec["assumptions"]["margin"] == portfolio_run.shadow_text.MARGIN_NOTE


def test_grid_margin_text_when_binding(rec_c):
    pw = rec_c["power"]
    # C: generators built to the draw, so the grid row binds with dual 0
    assert pw["binding"] and pw["margin_text"] == "+10 MW -> no gain at the margin"


def test_items_cover_every_mentioned_item_with_form_and_solid_stack(rec_c, data):
    assert set(rec_c["items"]) == set(rec_c["names"]["items"])
    for i, f in rec_c["items"].items():
        assert f["form"] == data.items[i].form
        assert f["stack_size"] == (data.items[i].stack_size if f["form"] == "solid" else None), i
    assert rec_c["items"][RESIN] == {"form": "solid", "stack_size": 200}
    assert rec_c["items"]["Desc_LiquidFuel_C"] == {"form": "liquid", "stack_size": None}


def test_record_is_deterministic_and_provenance_is_only_in_export(specs, data, tmp_path):
    """record() leaves provenance null, so a native and a Pyodide record can
    be compared byte for byte; export() always states it."""
    pr = _run(specs)
    a, b = portfolio_run.record(pr, data), portfolio_run.record(pr, data)
    assert a["provenance"] is None and json.dumps(a) == json.dumps(b)
    path = tmp_path / "c.json"
    portfolio_run.export(pr, data, path)
    prov = json.loads(path.read_text(encoding="utf-8"))["provenance"]
    assert set(prov) == {"generated_utc", "python", "implementation", "numpy", "scipy",
                         "commit", "worktree_dirty", "commit_unavailable"}
    # a commit, or the reason there is none: never both, never neither
    assert (prov["commit"] is None) != (prov["commit_unavailable"] is None)


def test_provenance_without_git_names_the_reason(tmp_path):
    prov = portfolio_run.provenance(tmp_path)  # not a checkout
    assert prov["commit"] is None and prov["worktree_dirty"] is None
    assert prov["commit_unavailable"]
