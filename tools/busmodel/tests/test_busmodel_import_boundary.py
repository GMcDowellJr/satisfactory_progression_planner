"""The oracle's structural tripwire, asserted rather than asked for.

An oracle that can reach the solver, or the bodies it validates, is not an
oracle. The property that makes that impossible is an import restriction, and an
import restriction that lives only in a docstring is a policy.

    PERMITTED   production_adapter.contracts    types only
                production_adapter.gamedata     reference data, read-only
                production_adapter.scenario     the multiplier and its rounding
                realization.contracts           `Disposition` ONLY
    FORBIDDEN   production_adapter.backend, .lp_backend, .analysis
                realization.buses, .residual, .realize, .capabilities
                scipy, at any depth

The second forbidden line is the one this package exists for. The realization
layer's bodies are checked against these figures; if the figures could be
produced by the bodies, the check is circular and nothing would catch it.

`realization.contracts` is permitted, and deliberately: the four steady-state
names live in one place or they drift into two. That module is types and
docstrings and cannot compute anything, and it is the only module of that
package this one may see.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "src" / "busmodel"

PERMITTED_ADAPTER_MODULES = frozenset({
    "production_adapter",            # the package itself, for `from production_adapter import gamedata`
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
    """Every module name this file imports, absolute form only.

    Relative imports are intra-package and carry no boundary meaning.
    """
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
    return found


@pytest.mark.parametrize("path", _module_files(), ids=lambda p: p.name)
def test_imports_no_forbidden_root(path: pathlib.Path) -> None:
    offenders = {m for m in _imported_modules(path) if m.split(".")[0] in FORBIDDEN_ROOTS}
    assert not offenders, f"{path.name} imports {sorted(offenders)}"


@pytest.mark.parametrize("path", _module_files(), ids=lambda p: p.name)
def test_adapter_imports_are_permitted(path: pathlib.Path) -> None:
    adapter = {m for m in _imported_modules(path) if m.split(".")[0] == "production_adapter"}
    assert adapter <= PERMITTED_ADAPTER_MODULES, (
        f"{path.name} imports {sorted(adapter - PERMITTED_ADAPTER_MODULES)} — "
        "the oracle may reach the adapter's contract, scenario and reference "
        "data, and nothing that solves"
    )


@pytest.mark.parametrize("path", _module_files(), ids=lambda p: p.name)
def test_realization_imports_are_contract_only(path: pathlib.Path) -> None:
    seen = {m for m in _imported_modules(path) if m.split(".")[0] == "realization"}
    assert seen <= PERMITTED_REALIZATION_MODULES, (
        f"{path.name} imports {sorted(seen - PERMITTED_REALIZATION_MODULES)} — "
        "the oracle may share the realization layer's TYPES and may not reach "
        "the code it is the check on"
    )


def test_package_declares_no_solver_dependency() -> None:
    """The install cannot pull scipy in, so the restriction survives a refactor.

    The AST scan above is defeated by an indirection; this is not. Parsed, not
    grepped: `production_adapter` carries scipy under its `lp` extra, so
    depending on the base distribution does not pull a solver in and requesting
    the extra would. Both are asserted.
    """
    import tomllib

    project = tomllib.loads(
        (PACKAGE.parents[1] / "pyproject.toml").read_bytes().decode("utf-8")
    )["project"]
    declared: list[str] = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        declared.extend(extra)
    offenders = [d for d in declared if "scipy" in d or "[lp]" in d]
    assert not offenders, (
        f"busmodel must not depend on a solver, directly or via an extra: {offenders}"
    )


def test_no_module_opens_a_file() -> None:
    """The locked claim this package exists to honour.

    `gamedata.py` is the only place in the repo that knows the reference CSVs'
    filenames and column names. The scratch model this replaces could not be
    committed precisely because it opened them itself, and a second loader is
    what that lock exists to prevent.

    `cli.py` is exempt for `pathlib` alone — it takes a repo root on the command
    line and hands it to `gamedata.load`, which is the permitted route.
    """
    offenders = []
    for path in _module_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "open":
                    offenders.append(f"{path.name}: open()")
            if isinstance(node, ast.Attribute) and node.attr in {"read_text", "read_bytes", "open"}:
                offenders.append(f"{path.name}: .{node.attr}()")
        for module in _imported_modules(path):
            if module.split(".")[0] == "csv":
                offenders.append(f"{path.name}: imports csv")
    assert not offenders, (
        "the oracle must read reference data only through production_adapter."
        f"gamedata: {sorted(set(offenders))}"
    )


def test_scan_covers_every_module() -> None:
    """The frame, checked. A scan is only as good as its population."""
    expected = {
        "__init__.py", "__main__.py", "cli.py", "declarations.py",
        "model.py", "report.py",
    }
    actual = {p.name for p in _module_files()}
    assert actual == expected, (
        f"module set drifted: missing {sorted(expected - actual)}, "
        f"undeclared {sorted(actual - expected)}"
    )
