"""The structural tripwire, asserted rather than asked for.

The realization layer may not become a second solver. The property that makes
that impossible is an import restriction, and an import restriction that lives
only in a docstring is a policy. The repo has already learned what policies are
worth: `reference_tables.csv` replaced three hand-maintained lists with one
declaration and seven assertions, and caught two errors on its first run, after
the policy version of the same rule had failed three times.

So this is the test, not the note.

    PERMITTED   production_adapter.contracts    types only
                production_adapter.gamedata     reference data, read-only
    FORBIDDEN   production_adapter.backend
                production_adapter.lp_backend
                production_adapter.analysis
                scipy, at any depth

Supersedes the inclusion form in output-contract-respec-2026-09-21.md §1
("imports `contracts` and nothing else from the adapter"), which was
incompatible with `gamedata.py`'s locked claim to be the only place that knows
CSV column names: honouring it literally would have required a second loader.
The exclusion form preserves the property that was actually wanted — a layer
that reads `effective_count` and cannot reach `linprog` cannot become a second
solver — because both permitted modules are data and contract, and neither can
solve.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "src" / "realization"

PERMITTED_ADAPTER_MODULES = frozenset({
    "production_adapter.contracts",
    "production_adapter.gamedata",
})
FORBIDDEN_ROOTS = frozenset({"scipy"})


def _module_files() -> list[pathlib.Path]:
    files = sorted(PACKAGE.glob("*.py"))
    assert files, f"no modules found under {PACKAGE} — the scan's frame is wrong"
    return files


def _imported_modules(path: pathlib.Path) -> set[str]:
    """Every module name this file imports, absolute form only.

    Relative imports (`from .contracts import ...`) are intra-package and carry
    no boundary meaning, so they are skipped rather than resolved.
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
    offenders = {
        m for m in _imported_modules(path) if m.split(".")[0] in FORBIDDEN_ROOTS
    }
    assert not offenders, f"{path.name} imports {sorted(offenders)}"


@pytest.mark.parametrize("path", _module_files(), ids=lambda p: p.name)
def test_adapter_imports_are_permitted(path: pathlib.Path) -> None:
    adapter = {
        m for m in _imported_modules(path) if m.split(".")[0] == "production_adapter"
    }
    assert adapter <= PERMITTED_ADAPTER_MODULES, (
        f"{path.name} imports {sorted(adapter - PERMITTED_ADAPTER_MODULES)} — "
        "the realization layer may reach the adapter's contract and reference "
        "data, and nothing that solves"
    )


def test_package_declares_no_solver_dependency() -> None:
    """The install cannot pull scipy in, so the restriction survives a refactor.

    The AST scan above is defeated by an indirection; this is not. A package
    whose dependency closure cannot reach a solver cannot become one by
    accident.

    Parsed, not grepped. The first version of this test was a substring scan
    for "scipy" over the whole file and it failed on the COMMENT that explains
    why scipy is excluded — a check whose population included its own
    documentation. The failure was the test working: it named a frame error
    before the frame error could name a false pass. The declared dependencies
    are the population; prose about them is not.

    `production_adapter` carries scipy under its `lp` extra. Depending on the
    base distribution therefore does not pull a solver in, and requesting the
    extra would. Both are asserted.
    """
    import tomllib

    pyproject = (PACKAGE.parents[1] / "pyproject.toml").read_bytes()
    project = tomllib.loads(pyproject.decode("utf-8"))["project"]

    declared: list[str] = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        declared.extend(extra)

    offenders = [d for d in declared if "scipy" in d or "[lp]" in d]
    assert not offenders, (
        f"realization must not depend on a solver, directly or via an extra: {offenders}"
    )


def test_scan_covers_every_module() -> None:
    """The frame, checked.

    A scan is only as good as its population. The manifest's own completeness
    test failed on its first run because it globbed a partially staged
    directory and declared exactly what it could see — a measurement of the
    wrong set, which reads as a confident, complete-looking, wrong answer.
    This asserts the population rather than assuming it.
    """
    expected = {
        "__init__.py", "contracts.py", "capabilities.py", "buses.py",
        "residual.py", "realize.py",
    }
    actual = {p.name for p in _module_files()}
    assert actual == expected, (
        f"module set drifted: missing {sorted(expected - actual)}, "
        f"undeclared {sorted(actual - expected)}"
    )
