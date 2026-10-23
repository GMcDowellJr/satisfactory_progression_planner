"""tools/neighborhoods.py: resource neighborhoods under a declared policy.

The anchor is v0.20's saved output (research/v020_site_mapper/
resource_first_clusters.json, 276 neighborhoods over 522 sockets): with
v0.20's policy DECLARED, the repo tool regenerates the same socket sets in
the same order (handoff 2026-10-19 18:28 action 2). The rest pins what
"declared, never defaulted" means here (decided by Greg, 2026-10-23).

Measured 2026-10-23, container, d029aa7: one choice changed at a time from
v0.20's policy, the share of the 276 kept as identical sets was: order
seed_id 249, no seed-distance gate 238, jaccard 0.6 237, radius 300 86,
radius 400 60, min nodes 3 263, fracking cores excluded 250.
"""
from __future__ import annotations

import importlib.util
import json
import math
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
nb = _module("neighborhoods")

#: v0.20's INCLUDE, as (kind, item) pairs over this repo's sockets
V020_INCLUDE = tuple(
    [("resource_node", f"Desc_{i}_C") for i in ("OreIron", "Stone", "Coal", "OreCopper", "LiquidOil",
                                               "SAM", "OreGold", "RawQuartz", "OreBauxite", "Sulfur")]
    + [(k, i) for k in ("fracking_satellite", "fracking_core")
       for i in ("Desc_LiquidOil_C", "Desc_NitrogenGas_C")]
)
V020 = nb.Policy(V020_INCLUDE, 350.0, 2, nb.Dedupe(0.78, 175.0, "most_types_first"))
SAVED = REPO / "research" / "v020_site_mapper" / "resource_first_clusters.json"


@pytest.fixture(scope="module")
def sockets():
    return site_card.load_sockets(REPO, "default_502094")


@pytest.fixture(scope="module")
def weights():
    return nb.purity_weights(REPO)


@pytest.fixture(scope="module")
def v020(sockets, weights):
    return nb.discover(sockets, V020, weights)


def test_regenerates_v020s_276_in_order(v020):
    saved = [set(c["socket_ids"]) for c in json.loads(SAVED.read_text(encoding="utf-8"))["clusters"]]
    assert len(saved) == 276
    assert [set(n.socket_ids) for n in v020] == saved
    assert [n.seed_socket_id for n in v020] == [
        c["seed_socket_id"] for c in json.loads(SAVED.read_text(encoding="utf-8"))["clusters"]]


def test_purity_weights_come_from_extraction_rates(weights):
    assert {p: weights[p] for p in ("impure", "normal", "pure")} == {"impure": 0.5, "normal": 1.0, "pure": 2.0}


def test_the_order_is_policy(sockets, weights):
    """Same thresholds, another declared order: another set of survivors."""
    other = nb.discover(sockets, nb.Policy(V020_INCLUDE, 350.0, 2, nb.Dedupe(0.78, 175.0, "seed_id")),
                        weights)
    assert len(other) == 275
    saved = {frozenset(n.socket_ids) for n in nb.discover(sockets, V020, weights)}
    assert sum(frozenset(n.socket_ids) in saved for n in other) == 249


def test_without_dedupe_every_seed_is_reported_in_file_order(sockets):
    found = nb.discover(sockets, nb.Policy(V020_INCLUDE, 350.0, 2, None))
    assert len(found) == 522
    # the world file is already in id order, so feed it reversed: the
    # output must follow the input, not an id sort (no ranking without dedupe)
    flipped = tuple(reversed(sockets))
    seeds = [n.seed_socket_id for n in nb.discover(flipped, nb.Policy(V020_INCLUDE, 350.0, 2, None))]
    pool = [s.socket_id for s in flipped if (s.source_kind, s.item_id) in V020_INCLUDE]
    assert seeds == [s for s in pool if s in set(seeds)] and seeds != sorted(seeds)


def test_weights_refuse_a_purity_with_two_multipliers():
    from production_adapter.gamedata import ExtractionRate

    rows = (ExtractionRate("Build_A_C", "pure", 2.0, 120.0, 300.0, "items/min"),
            ExtractionRate("Build_B_C", "pure", 3.0, 120.0, 300.0, "items/min"))
    with pytest.raises(nb.NeighborhoodError, match="pure"):
        nb.weights_from_rates(rows)
    assert nb.weights_from_rates(rows[:1]) == {"pure": 2.0}


def test_every_socket_is_within_the_radius_of_its_seed(sockets, v020):
    by = {s.socket_id: s for s in sockets}
    for n in v020:
        assert n.seed_socket_id in n.socket_ids and len(n.socket_ids) >= 2
        for sid in n.socket_ids:
            assert math.hypot(by[sid].east_m - n.east_m, by[sid].north_m - n.north_m) <= 350.0
            assert (by[sid].source_kind, by[sid].item_id) in V020_INCLUDE


def test_kind_wildcard_includes_every_item_of_that_kind(sockets):
    # fracking cores carry three items (Water, Nitrogen Gas, Crude Oil)
    found = nb.discover(sockets, nb.Policy((("fracking_core", None),), 350.0, 1, None))
    got = {s for n in found for s in n.socket_ids}
    want = {s.socket_id for s in sockets if s.source_kind == "fracking_core"}
    assert got == want
    assert len({s.item_id for s in sockets if s.socket_id in got}) == 3


@pytest.mark.parametrize("policy, match", [
    (nb.Policy(V020_INCLUDE, 0.0, 2, None), "radius"),
    (nb.Policy(V020_INCLUDE, 350.0, 0, None), "min_nodes"),
    (nb.Policy((), 350.0, 2, None), "nothing is included by default"),
    (nb.Policy((("resource_node", "Desc_Nope_C"),), 350.0, 2, None), "match no socket"),
    (nb.Policy(V020_INCLUDE + (V020_INCLUDE[0],), 350.0, 2, None), "included twice"),
    (nb.Policy(V020_INCLUDE, 350.0, 2, nb.Dedupe(1.5, 175.0, "seed_id")), "jaccard"),
    (nb.Policy(V020_INCLUDE, 350.0, 2, nb.Dedupe(0.78, -1.0, "seed_id")), "seed distance"),
    (nb.Policy(V020_INCLUDE, 350.0, 2, nb.Dedupe(0.78, 175.0, "biggest")), "no dedupe order"),
])
def test_refused_by_name(sockets, policy, match):
    with pytest.raises(nb.NeighborhoodError, match=match):
        nb.discover(sockets, policy, {"impure": 0.5, "normal": 1.0, "pure": 2.0})


def test_purity_order_without_weights_is_refused(sockets):
    with pytest.raises(nb.NeighborhoodError, match="pass purity_weights"):
        nb.discover(sockets, V020, None)


def test_cli_refuses_half_a_dedupe(capsys):
    with pytest.raises(SystemExit):
        nb.main(["--radius", "350", "--min-nodes", "2", "--include", "resource_node",
                 "--dedupe-jaccard", "0.78"])
    assert "all three" in capsys.readouterr().err


def test_cli_requires_the_policy(capsys):
    for missing in (["--min-nodes", "2", "--include", "resource_node"],
                    ["--radius", "350", "--include", "resource_node"],
                    ["--radius", "350", "--min-nodes", "2"]):
        with pytest.raises(SystemExit):
            nb.main(missing)


def test_export_is_lf_and_self_contained(sockets, tmp_path):
    path = tmp_path / "nb.json"
    args = ["--radius", "350", "--min-nodes", "2", "--dedupe-jaccard", "0.78", "--dedupe-seed-m", "175",
            "--dedupe-order", "most_types_first", "--export", str(path)]
    for kind, item in V020_INCLUDE:
        args += ["--include", f"{kind}:{item}"]
    assert nb.main(args) == 0
    raw = path.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"}\n")
    doc = json.loads(raw)
    assert doc["schema"] == nb.EXPORT_SCHEMA == "neighborhoods/1"
    assert doc["policy"]["dedupe"] == {"jaccard": 0.78, "seed_distance_m": 175.0, "order": "most_types_first"}
    assert len(doc["neighborhoods"]) == 276
    carried = {s["socket_id"] for s in doc["sockets"]}
    assert {sid for n in doc["neighborhoods"] for sid in n["socket_ids"]} == carried
    assert {s["item_id"] for s in doc["sockets"]} <= set(doc["names"]["items"])
