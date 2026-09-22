"""`progression`'s structural tripwire. It did not have one until 2026-09-22.

The package docstring has said "Sits above `production_adapter` and imports
downward" since it was written, and a docstring is a policy. `busmodel` and
`realization` each assert their boundary; this package did not, and the module
that made that matter is `stock`.

    PERMITTED   production_adapter, .contracts, .gamedata, .scenario
                realization.contracts    the bill TYPES only
    FORBIDDEN   production_adapter.backend, .lp_backend, .analysis
                realization.buses, .residual, .realize, .capabilities
                scipy, at any depth

WHY `stock` IS THE MODULE THAT NEEDS THIS. It holds per-building costs, settled
machine counts and — once UNLOCK_COST unblocks — tier unlocks, at once. That is
enough to plausibly answer "what should I build next", which is a broader and
more authoritative question than "what does this bill come to". The drift would
not announce itself; it would arrive as one convenient extra return value.

`realization.contracts` is permitted for the reason `busmodel` is allowed
`Disposition`: `WithdrawalBill`, `BillTerm` and `WithdrawalBasis` live in one
place or they drift into two. That module is types and docstrings and cannot
compute anything, and it is the only module of that package this one may see.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

PACKAGE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "tools" / "progression" / "src" / "progression"
)

PERMITTED_ADAPTER_MODULES = frozenset({
    "production_adapter",
    "production_adapter.contracts",
    "production_adapter.gamedata",
    "production_adapter.scenario",
})
PERMITTED_REALIZATION_MODULES = frozenset({"realization.contracts"})
FORBIDDEN_ROOTS = frozenset({"scipy"})


def _module_files() -> list[pathlib.Path]:
    files = sorted(PACKAGE.glob("*.py"))
    assert files, f"no modules found under {PACKAGE} — the scan's frame is wrong"
    return files


def _imported_modules(path: pathlib.Path) -> set[str]:
    """Every module this file imports, absolute form only. Relative imports are
    intra-package and carry no boundary meaning."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
    return found


def test_the_scan_sees_every_module():
    """The frame is the thing that goes wrong silently. A scan of a directory
    that is missing files produces a confident, complete-looking pass —
    observed on 2026-09-21 against a partially staged reference directory."""
    assert {p.name for p in _module_files()} == {
        "__init__.py", "pool.py", "unlocks.py", "stock.py",
    }


@pytest.mark.parametrize("path", _module_files(), ids=lambda p: p.name)
def test_no_module_reaches_past_the_boundary(path):
    for module in _imported_modules(path):
        root = module.split(".")[0]
        if root in FORBIDDEN_ROOTS:
            pytest.fail(f"{path.name} imports {module}")
        if root == "production_adapter":
            assert module in PERMITTED_ADAPTER_MODULES, f"{path.name} imports {module}"
        if root == "realization":
            assert module in PERMITTED_REALIZATION_MODULES, f"{path.name} imports {module}"


def test_only_stock_touches_the_realization_contracts():
    """The permission is narrow by module as well as by name. If a second module
    here starts needing realization types, that is a design change and should
    arrive as one, not as an import."""
    touching = {
        p.name for p in _module_files()
        if any(m.split(".")[0] == "realization" for m in _imported_modules(p))
    }
    assert touching == {"stock.py"}


def test_the_package_imports_without_the_realization_layer(monkeypatch):
    """`progression/__init__.py` must not eagerly import `stock`, or the whole
    package becomes unusable wherever `realization` is not on the path. The
    submodule is imported on demand."""
    init = PACKAGE / "__init__.py"
    assert "realization" not in _imported_modules(init)
    assert "from .stock" not in init.read_text(encoding="utf-8")


def test_nothing_in_the_adapter_imports_this_package():
    """The direction is the whole point of the boundary — production_lp_formulation
    §11.1. Asserted from the other side, because a one-way rule checked in one
    direction is checked in half."""
    adapter = (
        pathlib.Path(__file__).resolve().parents[1]
        / "tools" / "production_adapter" / "src" / "production_adapter"
    )
    files = sorted(adapter.glob("*.py"))
    assert files, f"no modules found under {adapter} — the scan's frame is wrong"
    for path in files:
        for module in _imported_modules(path):
            assert module.split(".")[0] not in {"progression", "realization"}, (
                f"{path.name} imports {module}, which reverses the dependency"
            )
