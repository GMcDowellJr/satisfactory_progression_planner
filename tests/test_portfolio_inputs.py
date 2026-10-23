"""tools/portfolio_run.py inputs: the portfolio-inputs/1 document.

The picker (handoff 2026-10-23 14:48, action 2) hands a run to portfolio_run
as sites by socket id plus every other input, all declared. The CLI flags
build the same document, so there is one path into run() and every record
echoes the inputs that made it.

First pick (Greg, 2026-10-23: "use the starting area of the Rocky Desert"):
district A of planning/plans/rocky_desert ("Western Coast Starter Works /
Home Base", resource_assignments.csv), whose 11 legacy source ids
(planning/legacy/rocky_desert/resource_sources.csv) each sit within 6 mm of
one world socket of the same resource and purity (container 2026-10-23,
d029aa7). Those 11 sockets are exactly the v0.20-policy neighborhood seeded
at BP_ResourceNode103 (tools/neighborhoods.py).
"""
from __future__ import annotations

import copy
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

#: Rocky Desert district A, as world sockets (module docstring)
ROCKY_A = ("BP_ResourceNode153", "BP_ResourceNode109", "BP_ResourceNode108", "BP_ResourceNode105_2463",
           "BP_ResourceNode107", "BP_ResourceNode106", "BP_ResourceNode112", "BP_ResourceNode111_3367",
           "BP_ResourceNode103", "BP_ResourceNode102_2068", "BP_ResourceNode104")
MINER = [{"source_kind": "resource_node", "item_id": None, "extractor_class": "Build_MinerMk1_C"}]


def _rocky(grid_mw: float) -> dict:
    """A starter run of district A. Tier 2, bill PA phase 1 + milestones of
    tiers 1-2 are the TEST's declarations (placeholders, not Greg's)."""
    return {
        "schema": "portfolio-inputs/1", "world_config_id": "default_502094", "tier": 2,
        "declared_recipes": [], "scenario": {
            "recipe_input_multiplier": 1.0, "machine_power_multiplier": 1.0,
            "project_assembly_requirement_multiplier": 1.0, "input_amount_floor": None,
            "fluid_rounding_unit": "mL"},
        "goal": "balanced", "bill": {"phases": [1], "tiers": [1, 2]}, "extraction_clock": 1.0,
        "extractors": copy.deepcopy(MINER), "grid_mw": grid_mw, "spare_mw": 0.0,
        "sites": [{"label": "rocky_start", "socket_ids": list(ROCKY_A), "pumps_water": False,
                   "supply": []}],
    }


def test_rocky_a_is_the_neighborhood_seeded_at_node_103():
    nb = _module("neighborhoods")
    include = tuple(
        [("resource_node", f"Desc_{i}_C") for i in ("OreIron", "Stone", "Coal", "OreCopper", "LiquidOil",
                                                   "SAM", "OreGold", "RawQuartz", "OreBauxite", "Sulfur")]
        + [(k, i) for k in ("fracking_satellite", "fracking_core")
           for i in ("Desc_LiquidOil_C", "Desc_NitrogenGas_C")])
    found = nb.discover(site_card.load_sockets(REPO, "default_502094"),
                        nb.Policy(include, 350.0, 2, nb.Dedupe(0.78, 175.0, "most_types_first")),
                        nb.purity_weights(REPO))
    seed = next(n for n in found if n.seed_socket_id == "BP_ResourceNode103")
    assert set(seed.socket_ids) == set(ROCKY_A)


def test_rocky_a_alone_has_no_power_source():
    """Tier 2 opens only the Biomass Burner, and no socket supplies biomass:
    the grid binds at 0 MW and the bill scale is 0 (measured 2026-10-23)."""
    pr, _ = portfolio_run.run_inputs(_rocky(0.0))
    assert pr.response.scale == 0.0
    assert pr.response.power.binding and pr.response.power.shadow_price > 0.0


def test_rocky_a_with_a_declared_standing_grid():
    pr, _ = portfolio_run.run_inputs(_rocky(60.0))
    assert pr.response.scale == pytest.approx(0.012147, abs=1e-6)
    assert pr.response.power.binding  # still power-bound at 60 MW
    assert [b.item_id for b in pr.blocked] == ["Desc_ResourceSinkCoupon_C"]


def test_flags_and_inputs_give_the_same_record():
    """inputs_doc is how the CLI flags enter run_inputs; a circle site is
    written as the socket ids it caught."""
    sockets = site_card.load_sockets(REPO, "default_502094")
    extractors = ((("resource_node", None), "Build_MinerMk1_C"),)
    spec = site_card.SiteSpec("rocky_start", site_card.sockets_within(sockets, -2650.3, 370.01, 200.0),
                              extractors, 1.0)
    kw = dict(tier=2, scenario=Scenario(), goal="balanced", bill_phases=(1,), bill_tiers=(1, 2),
              grid_mw=60.0, spare_mw=0.0, water_sites=())
    direct = portfolio_run.run((spec,), **kw)
    doc = portfolio_run.inputs_doc((spec,), world_config_id="default_502094", declared_recipes=(), **kw)
    via, scenario = portfolio_run.run_inputs(json.loads(json.dumps(doc)))
    data = load(REPO, scenario)
    assert json.dumps(portfolio_run.record(via, data)) == json.dumps(portfolio_run.record(direct, data))


@pytest.mark.parametrize("key", portfolio_run.INPUT_KEYS)
def test_every_input_key_is_required(key):
    doc = _rocky(60.0)
    del doc[key]
    with pytest.raises(portfolio_run.PortfolioRunError, match=f"missing \\['{key}'\\]"):
        portfolio_run.run_inputs(doc)


@pytest.mark.parametrize("path, key", [
    (("sites", 0), "pumps_water"), (("extractors", 0), "item_id"), (("bill",), "tiers"),
    (("scenario",), "input_amount_floor"),
])
def test_nested_keys_are_required(path, key):
    doc = _rocky(60.0)
    obj = doc
    for p in path:
        obj = obj[p]
    del obj[key]
    with pytest.raises(portfolio_run.PortfolioRunError, match=key):
        portfolio_run.run_inputs(doc)


def test_unknown_keys_and_schema_are_refused():
    doc = _rocky(60.0)
    doc["sites"][0]["radius_m"] = 500
    with pytest.raises(portfolio_run.PortfolioRunError, match="not known \\['radius_m'\\]"):
        portfolio_run.run_inputs(doc)
    doc = _rocky(60.0)
    doc["schema"] = "portfolio-inputs/2"
    with pytest.raises(portfolio_run.PortfolioRunError, match="schema"):
        portfolio_run.run_inputs(doc)


def test_pumps_water_reaches_the_run():
    doc = _rocky(60.0)
    doc["sites"][0]["pumps_water"] = True
    pr, _ = portfolio_run.run_inputs(doc)
    assert pr.sites[0].pumps_water
    assert next(c for c in pr.sites[0].caps if c.item_id == "Desc_Water_C").rate_per_min is None


def test_an_empty_bill_is_refused():
    doc = _rocky(60.0)
    doc["bill"] = {"phases": [], "tiers": []}
    with pytest.raises(portfolio_run.PortfolioRunError, match="declare phases and/or tiers"):
        portfolio_run.run_inputs(doc)


def test_export_echoes_the_inputs(tmp_path):
    doc = _rocky(60.0)
    path, src = tmp_path / "r.json", tmp_path / "in.json"
    src.write_text(json.dumps(doc), encoding="utf-8", newline="\n")
    assert portfolio_run.main(["--inputs", str(src), "--export", str(path)]) == 0
    assert json.loads(path.read_text(encoding="utf-8"))["inputs"] == doc


def test_cli_refuses_inputs_mixed_with_flags(tmp_path, capsys):
    src = tmp_path / "in.json"
    src.write_text(json.dumps(_rocky(60.0)), encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit):
        portfolio_run.main(["--inputs", str(src), "--grid-mw", "0"])
    assert "--grid-mw" in capsys.readouterr().err


def test_cli_refuses_a_missing_or_broken_inputs_file(tmp_path, capsys):
    """Greg, 2026-10-23 15:19: an unexpanded $HOME gave a traceback."""
    with pytest.raises(SystemExit):
        portfolio_run.main(["--inputs", "$HOME\\Downloads\\portfolio_inputs.json"])
    assert "no file at $HOME" in capsys.readouterr().err
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit):
        portfolio_run.main(["--inputs", str(bad)])
    assert "is not JSON" in capsys.readouterr().err


def test_cli_without_inputs_still_requires_the_flags(capsys):
    with pytest.raises(SystemExit):
        portfolio_run.main(["--tier", "2", "--bill-tier", "1"])
    err = capsys.readouterr().err
    assert "--site" in err and "--extractor" in err and "--clock" in err
