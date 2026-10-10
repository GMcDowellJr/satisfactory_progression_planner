"""`demand_expansion`'s structural tripwire, written with the package.

    PERMITTED   production_adapter.contracts, .gamedata, .scenario
    FORBIDDEN   production_adapter.backend, .lp_backend, .analysis
                progression, realization, busmodel, scipy, at any depth
                csv, and any call to open(): this package reads no file.
                Reference data arrives through gamedata.load, the one loader.

And from the other side: nothing in the adapter imports this package. LP record
§11.1 runs the dependency downward only; a rule checked in one direction is
checked in half.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "src" / "demand_expansion"
ADAPTER = (
    pathlib.Path(__file__).resolve().parents[3]
    / "tools" / "production_adapter" / "src" / "production_adapter"
)

PERMITTED_ADAPTER_MODULES = frozenset({
    "production_adapter.contracts",
    "production_adapter.gamedata",
    "production_adapter.scenario",
})
FORBIDDEN_ROOTS = frozenset({"scipy", "progression", "realization", "busmodel", "csv"})


def _module_files(package: pathlib.Path) -> list[pathlib.Path]:
    files = sorted(package.glob("*.py"))
    assert files, f"no modules found under {package} — the scan's frame is wrong"
    return files


def _imported_modules(path: pathlib.Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
    return found


def test_the_scan_sees_every_module():
    assert {p.name for p in _module_files(PACKAGE)} == {
        "__init__.py", "contracts.py", "declarations.py", "graph.py", "expand.py",
        "aggregate.py",   # PR 4, 2026-10-10
        "report.py",      # PR 5, 2026-10-10
    }


@pytest.mark.parametrize("path", _module_files(PACKAGE), ids=lambda p: p.name)
def test_no_module_reaches_past_the_boundary(path):
    for module in _imported_modules(path):
        root = module.split(".")[0]
        assert root not in FORBIDDEN_ROOTS, f"{path.name} imports {module}"
        if root == "production_adapter":
            assert module in PERMITTED_ADAPTER_MODULES, f"{path.name} imports {module}"


@pytest.mark.parametrize("path", _module_files(PACKAGE), ids=lambda p: p.name)
def test_the_package_opens_no_file(path):
    source = path.read_text(encoding="utf-8")
    assert "planning_data" not in source, f"{path.name} names the data directory"
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "open", f"{path.name} calls open()"


def test_nothing_in_the_adapter_imports_this_package():
    for path in _module_files(ADAPTER):
        for module in _imported_modules(path):
            assert module.split(".")[0] != "demand_expansion", (
                f"{path.name} imports {module}, which reverses the dependency"
            )
