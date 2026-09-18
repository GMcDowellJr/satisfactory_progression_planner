"""Provenance stamp tests.

The stamp itself is always checked. The live game file is only checked when it is
reachable on this machine, so these stay green on a box without the game installed.
"""
import csv
import hashlib
import os
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
STAMP = REPO / "planning_data" / "provenance" / "game_docs_source.csv"
REF = REPO / "planning_data" / "game" / "reference"

STAMPED_TABLES = [
    "recipes.csv", "recipe_io.csv", "recipe_producers.csv", "items.csv",
    "production_buildings.csv", "recipe_variable_power.csv",
    "extraction_buildings.csv", "extraction_rates.csv", "resource_extraction_map.csv",
]


def _rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def stamp():
    rows = _rows(STAMP)
    assert len(rows) == 1, "expected exactly one pinned game docs source"
    return rows[0]


def test_build_id_derives_from_the_hash(stamp):
    assert stamp["game_build_id"] == "docs_" + stamp["sha256"][:12]


def test_build_id_is_registered(stamp):
    known = {r["game_build_id"] for r in _rows(REF / "game_builds.csv")}
    assert stamp["game_build_id"] in known


def test_stamp_fields_are_populated(stamp):
    for field in ("docs_filename", "source_path", "bytes", "sha256", "encoding", "captured_on"):
        assert stamp[field].strip(), f"{field} is empty"
    assert len(stamp["sha256"]) == 64
    assert int(stamp["bytes"]) > 0


def test_checker_exists(stamp):
    assert (REPO / stamp["checker"]).is_file()


def test_repo_snapshot_is_recorded_and_present(stamp):
    rel = stamp["repo_copy_path"].strip()
    assert rel, "no repo-local snapshot recorded; the layer is not reproducible offline"
    assert (REPO / rel).is_file(), f"snapshot missing at {rel}"


def test_repo_snapshot_matches_the_pin(stamp):
    """The snapshot IS the pin. If this fails the reference layer is unmoored."""
    path = REPO / stamp["repo_copy_path"].strip()
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    assert h.hexdigest() == stamp["sha256"]
    assert path.stat().st_size == int(stamp["bytes"])


def test_repo_snapshot_lives_under_its_build_id(stamp):
    parts = pathlib.PurePosixPath(stamp["repo_copy_path"].strip()).parts
    assert stamp["game_build_id"] in parts, (
        "snapshot path should name the build it pins, so two builds cannot collide"
    )


@pytest.mark.parametrize("table", STAMPED_TABLES)
def test_derived_tables_carry_the_stamped_build(stamp, table):
    path = REF / table
    if not path.is_file():
        pytest.skip(f"{table} not present")
    builds = {r["game_build_id"] for r in _rows(path) if r.get("game_build_id")}
    assert builds, f"{table} carries no game_build_id"
    assert builds == {stamp["game_build_id"]}, (
        f"{table} spans {sorted(builds)}, stamp is {stamp['game_build_id']} — "
        "re-derive after the game patch"
    )


def test_live_game_file_still_matches(stamp):
    """Detects a game patch. Skipped when the game is not installed here."""
    path = pathlib.Path(os.environ.get("SATISFACTORY_DOCS") or stamp["source_path"])
    if not path.is_file():
        pytest.skip(f"game docs not reachable at {path}")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    assert h.hexdigest() == stamp["sha256"], (
        "game docs have changed since the reference layer was derived; "
        "run tools/check_game_docs_provenance.py"
    )
