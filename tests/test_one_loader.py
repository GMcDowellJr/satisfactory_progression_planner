"""One loader: only `production_adapter/gamedata.py` knows the game-reference
tables' filenames and columns (AGENTS.md, "One loader").

Until 2026-11-17 the rule was a sentence. Six modules opened
`planning_data/game/reference/*.csv` themselves (progression.unlocks, .pool,
.power, .stock, production_cli, storage_view), and nothing failed. R1 of the
architecture reconciliation moved them onto typed `gamedata` loaders; this test
keeps them there.

The signal is a path INTO the reference directory: the bare segment
"reference" (how `Path(...) / "game" / "reference"` is built) or a
"game/reference/..." path literal. Prose that merely names a table
("absent from schematics.csv") is not a path and is not flagged.

Approved exceptions, each with its reason:

- `check_game_docs_provenance.py` audits the raw table files themselves
  (hashes and the build stamp), as `regenerate_manifests` does for the repo.
- `satisfactory_route_tool/poi.py` belongs to a standalone spatial engine
  that reads through its own versioned planner package (pandas); it scores
  crash-site POIs and does no production arithmetic.

Scope is `tools/`. `tests/` are deliberately excluded: a test reading a table
raw is an independent oracle (`tests/_balance_check.py`), which is the point.
`research/` is self-declared scratch that breaks this rule on purpose.
"""
from __future__ import annotations

import ast
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"

LOADER = "tools/production_adapter/src/production_adapter/gamedata.py"
EXCEPTIONS = {
    "tools/check_game_docs_provenance.py",
    "tools/satisfactory_route_tool/src/satisfactory_route_tool/poi.py",
}

_PATH = re.compile(r"(^|/)game/reference(/|$)")


def reference_paths(source: str) -> list[tuple[int, str]]:
    """Line and literal of every string that builds a path into game/reference."""
    hits = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if v == "reference" or (" " not in v and _PATH.search(v)):
                hits.append((node.lineno, v))
    return hits


def _modules():
    for path in sorted(TOOLS.rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        yield path.relative_to(REPO).as_posix(), path


def test_only_gamedata_builds_a_path_into_the_reference_layer():
    offenders = {
        rel: hits
        for rel, path in _modules()
        if rel != LOADER and rel not in EXCEPTIONS
        and (hits := reference_paths(path.read_text(encoding="utf-8")))
    }
    assert not offenders, (
        "read game/reference through production_adapter.gamedata, not directly: "
        f"{offenders}"
    )


def test_the_exceptions_still_exist_and_still_need_to_be_exceptions():
    """An exception that no longer reads the layer is a stale allowance; drop it."""
    for rel in EXCEPTIONS:
        path = REPO / rel
        assert path.is_file(), rel
        assert reference_paths(path.read_text(encoding="utf-8")), rel


def test_the_signal_catches_the_shapes_that_were_removed():
    """Mutation check, kept as a test: the R1 shapes are caught; prose is not."""
    assert reference_paths('REF = pathlib.Path("planning_data") / "game" / "reference"\n')
    assert reference_paths('REFERENCE = ("planning_data", "game", "reference")\n')
    assert reference_paths('p = "planning_data/game/reference/recipes.csv"\n')
    assert not reference_paths('raise E(f"{x}: absent from schematics.csv")\n')
    assert not reference_paths(
        'raise E("D1 disposal is blocked on P5: planning_data/game/reference/ carries no")\n'
    )
