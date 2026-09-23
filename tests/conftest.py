import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "production_adapter" / "src"))
sys.path.insert(0, str(REPO / "tools" / "progression" / "src"))
#: `progression.stock` imports `realization.contracts` for the bill types, so
#: tests/ needs that src tree too. Without it `tests/test_progression_stock.py`
#: collects only when some OTHER package's conftest has already run and put it
#: on the path — which makes a green run depend on collection order rather than
#: on a mechanism. That is the same failure both conftest docstrings in this
#: repo already reject, arriving as an ordering dependency instead of as a
#: forgotten editable install.
sys.path.insert(0, str(REPO / "tools" / "realization" / "src"))
#: `busmodel`, for `test_oracle_against_realization.py` — the oracle's second
#: job, which needs the oracle AND the bodies it checks. It lives here because
#: this directory is above both packages: neither import boundary is weakened,
#: since each boundary test scans its own `src/` and nothing else.
sys.path.insert(0, str(REPO / "tools" / "busmodel" / "src"))
