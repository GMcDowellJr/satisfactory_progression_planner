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
