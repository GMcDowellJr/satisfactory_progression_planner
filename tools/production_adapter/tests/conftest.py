"""Put this package's own `src/` on the path, so these tests collect on their own.

Found 2026-10-08: without this file `uv run pytest tools/production_adapter/tests`
fails to import `production_adapter`, and the full suite passed only because
`tests/conftest.py` had already run. A green run that depends on collection
order is the failure every other conftest in this repo already rejects. The
realization and busmodel packages carry the same file; this one was missing.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
