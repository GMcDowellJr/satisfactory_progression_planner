"""Put this package and the adapter on sys.path.

`tests/conftest.py` at the repo root is scoped to `tests/` and does not apply
here; this conftest must not rely on it having run. The path is set here so
the suite is green whether or not an editable install was done.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]

for _p in (HERE.parent / "src", REPO / "tools" / "production_adapter" / "src"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    return REPO


@pytest.fixture(scope="session")
def canonical(repo_root):
    from production_adapter import gamedata

    return gamedata.load(repo_root)


@pytest.fixture(scope="session")
def default_graph(canonical):
    from demand_expansion import DEFAULT_ROUTES, build

    return build(canonical, DEFAULT_ROUTES)
