"""Put this package, the adapter and the realization contracts on sys.path.

`tests/conftest.py` at the repo root is scoped to `tests/` and does not apply
here. Relying on an editable install would make the suite green or red
depending on whether someone remembered to run `uv pip install -e`, which is a
policy, not a mechanism. So the path is set here; the install still works if it
is done.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]

for _p in (
    HERE.parent / "src",
    REPO / "tools" / "production_adapter" / "src",
    REPO / "tools" / "realization" / "src",
):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    return REPO


@pytest.fixture(scope="session")
def canonical(repo_root):
    """Reference data at 1x. The storage review's own scenario for sections 3,
    6.1 and 7."""
    from production_adapter import gamedata

    return gamedata.load(repo_root)


@pytest.fixture(scope="session")
def scenario_of_record(repo_root):
    """1.25x parts / 2x power, game 1.2.4.0 CL#502094.

    The Space Elevator multiplier is deliberately absent: it scales Project
    Assembly deliveries, which this model does not consume, and carrying a value
    nothing reads would invite it being read later.
    """
    from production_adapter import gamedata
    from production_adapter.scenario import Scenario

    return gamedata.load(
        repo_root, Scenario(recipe_input_multiplier=1.25, machine_power_multiplier=2.0)
    )
