"""Put this package and the adapter on sys.path for these tests.

`tests/conftest.py` at the repo root is scoped to `tests/` and does not apply
here. `tools/production_adapter/tests` needs no conftest because that package
is pip-installed editable into `.venv` — the `satisfactory_production_adapter.egg-info`
under its `src/` is the evidence. Relying on the same for `realization` would
make the suite green or red depending on whether someone remembered to run
`uv pip install -e tools/realization`, which is a policy, not a mechanism.

So the path is set here. The install still works if it is done; this makes it
unnecessary.
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]

for p in (
    HERE.parent / "src",
    REPO / "tools" / "production_adapter" / "src",
):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    return REPO


@pytest.fixture(scope="session")
def reference(repo_root):
    """Canonical reference data, 1x.

    The bodies written on 2026-09-21 join recipe -> producer_class -> producer,
    so the tests exercise the real join rather than a stub that cannot drift.
    """
    from production_adapter import gamedata

    return gamedata.load(repo_root)


@pytest.fixture(scope="session")
def logistics(repo_root):
    """`(capabilities, extraction_rates)` from `gamedata.load_logistics`."""
    from production_adapter import gamedata

    return gamedata.load_logistics(repo_root)
