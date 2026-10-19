"""The manifests hash content as git stores it, so line endings cannot drift them.

A checkout made before `.gitattributes` existed keeps CRLF text on disk: git sees
the content as unchanged and never rewrites it. When the manifests hashed working-
copy bytes, every regeneration on such a checkout recorded hashes no clone had
(2026-09-24, and again 2026-10-19 at a74cb38). Hashing git's form of the content
removes the dependency instead of policing it.
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "regenerate_manifests", REPO / "tools" / "regenerate_manifests.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)

LF = b"a,b\n1,2\n3,4\n"
CRLF = LF.replace(b"\n", b"\r\n")


def _expected(data: bytes) -> tuple[int, str]:
    return len(data), hashlib.sha256(data).hexdigest()


def test_crlf_and_lf_text_hash_the_same(tmp_path):
    lf, crlf = tmp_path / "lf.csv", tmp_path / "crlf.csv"
    lf.write_bytes(LF)
    crlf.write_bytes(CRLF)
    assert rm.digest(lf, "x/lf.csv") == rm.digest(crlf, "x/crlf.csv") == _expected(LF)


def test_a_crlf_split_across_chunks_is_still_one_newline(tmp_path, monkeypatch):
    monkeypatch.setattr(rm, "CHUNK", 4)  # b"a,b\r" | b"\n1,2" ... splits every CRLF
    p = tmp_path / "split.csv"
    p.write_bytes(CRLF)
    assert rm.digest(p, "x/split.csv") == _expected(LF)


def test_a_lone_cr_is_kept_as_git_keeps_it(tmp_path):
    p = tmp_path / "cr.txt"
    p.write_bytes(b"a\rb\r")
    assert rm.digest(p, "x/cr.txt") == _expected(b"a\rb\r")


def test_a_raw_path_is_hashed_byte_for_byte(tmp_path):
    p = tmp_path / "manifest.csv"
    p.write_bytes(CRLF)
    assert rm.digest(p, "planning_data/manifest.csv") == _expected(CRLF)


def test_a_nul_makes_a_file_binary(tmp_path):
    data = b"\x00\x01\r\n\x02"
    p = tmp_path / "blob.bin"
    p.write_bytes(data)
    assert rm.digest(p, "x/blob.bin") == _expected(data)


def test_raw_patterns_come_from_gitattributes():
    pats = rm.RAW_PATTERNS
    assert {"REPO_MANIFEST.csv", "planning_data/manifest.csv", "*.z"} <= set(pats)
    assert rm.is_raw("REPO_MANIFEST.csv")
    assert rm.is_raw("planning_data/manifest.csv")
    assert rm.is_raw("planning_data/terrain/tile.z")
    assert rm.is_raw("planning_data/game/source_snapshots/502094/en-US.json")
    assert not rm.is_raw("planning_data/game/reference/items.csv")
    assert not rm.is_raw("docs/manifest.csv")  # anchored pattern, not a name match
