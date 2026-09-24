"""Every text writer in the repo pins its line ending to LF, asserted from source.

The manifests hash working-copy bytes. `.gitattributes` stores text as LF and
checks it out as LF, but git does not rewrite a file a script has just written:
a CRLF file on disk stays CRLF, `git status` shows it clean, and a manifest
regenerated then records bytes no clone will have. That is how thirteen data
files drifted before 2026-09-24. The CRLF came from two defaults:

    csv.writer / csv.DictWriter   lineterminator defaults to "\\r\\n", on every OS
    pandas DataFrame.to_csv       lineterminator defaults to os.linesep
    open(.., "w"), write_text     text mode translates "\\n" to os.linesep

So every such call must say what it writes. A policy that lives in AGENTS.md
is a docstring; this is the test.

    csv writer     lineterminator="\\n"
    to_csv         lineterminator="\\n"
    write_text     newline="\\n"
    open, text w/a newline="\\n", or newline="" (no translation; what csv wants)

One exception, by name: `tools/regenerate_manifests.py` writes the manifests
CRLF, which is their format, and stores them with write_bytes.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
SCANNED = ("scripts", "tools", "research")
#: path -> the one call it may make with a non-LF terminator, and why
CRLF_BY_FORMAT = {"tools/regenerate_manifests.py": "manifests are CRLF by format"}

LF = "\n"


def _sources():
    for top in SCANNED:
        for path in sorted((REPO / top).rglob("*.py")):
            rel = path.relative_to(REPO).as_posix()
            if "/tests/" in rel or "__pycache__" in rel:
                continue
            yield rel, path


def _kw(call: ast.Call, name: str):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def _const(node):
    return node.value if isinstance(node, ast.Constant) else None


def _open_mode(call: ast.Call):
    """The mode string of an open() / Path.open() call, or None if not literal."""
    mode = _kw(call, "mode")
    if mode is None:
        func = call.func
        pos = 1 if isinstance(func, ast.Name) else 0
        mode = call.args[pos] if len(call.args) > pos else None
    return "r" if mode is None else _const(mode)


def violations(tree: ast.AST):
    """(line, message) for every text write that does not pin LF."""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name in ("writer", "DictWriter") and isinstance(func, ast.Attribute) \
                and getattr(func.value, "id", None) == "csv":
            if _const(_kw(node, "lineterminator")) != LF:
                out.append((node.lineno, f"csv.{name} without lineterminator='\\n'"))
        elif name == "to_csv":
            if _const(_kw(node, "lineterminator")) != LF:
                out.append((node.lineno, "to_csv without lineterminator='\\n'"))
        elif name == "write_text":
            if _const(_kw(node, "newline")) != LF:
                out.append((node.lineno, "write_text without newline='\\n'"))
        elif name == "open":
            mode = _open_mode(node)
            if isinstance(mode, str) and "b" not in mode and any(c in mode for c in "wax"):
                if _const(_kw(node, "newline")) not in (LF, ""):
                    out.append((node.lineno, f"open(mode={mode!r}) without newline"))
    return out


def test_every_text_writer_pins_lf():
    found = []
    for rel, path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for line, msg in violations(tree):
            if rel in CRLF_BY_FORMAT:
                continue
            found.append(f"{rel}:{line}: {msg}")
    assert not found, "writers that can emit CRLF:\n" + "\n".join(found)


def test_scan_reaches_the_writers_it_governs():
    """A scan that finds no files is not a check. Pin that it sees the two
    writers of the data that drifted on 2026-09-24."""
    seen = {rel for rel, _ in _sources()}
    assert "scripts/materialize_world_resources.py" in seen
    assert "research/production_solver_evaluation/build_p2_extraction.py" in seen


def test_the_manifest_exception_is_still_the_crlf_writer():
    """The exemption names a file; if that file stops writing CRLF, the
    exemption is stale and must go."""
    src = (REPO / "tools/regenerate_manifests.py").read_text(encoding="utf-8")
    assert 'lineterminator="\\r\\n"' in src


@pytest.mark.parametrize("snippet", [
    "import csv\ncsv.writer(f)",
    "import csv\ncsv.DictWriter(f, fieldnames=x, lineterminator='\\r\\n')",
    "df.to_csv(p, index=False)",
    "p.write_text(s, encoding='utf-8')",
    "open(p, 'w', encoding='utf-8')",
    "p.open('w', encoding='utf-8')",
    "open(p, mode='a')",
])
def test_the_scan_rejects(snippet):
    assert violations(ast.parse(snippet))


@pytest.mark.parametrize("snippet", [
    "import csv\ncsv.DictWriter(f, fieldnames=x, lineterminator='\\n')",
    "df.to_csv(p, index=False, lineterminator='\\n')",
    "p.write_text(s, encoding='utf-8', newline='\\n')",
    "open(p, 'w', newline='')",
    "p.open('w', newline='\\n')",
    "open(p)",
    "open(p, 'rb')",
    "p.open('wb')",
])
def test_the_scan_accepts(snippet):
    assert not violations(ast.parse(snippet))
