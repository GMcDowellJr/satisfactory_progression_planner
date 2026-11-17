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


# --- the committed manifests are well formed (R0, 2026-11-17) ----------------
# A manifest's sync with the tree is NOT tested: the convention puts the
# regeneration in a separate commit after each content commit, so the content
# commit itself is expected to drift. Its shape is always testable.

def test_the_committed_manifests_are_well_formed():
    for m in rm.MANIFESTS:
        assert rm.read_existing(m.out), m.out  # raises ManifestFormatError if not


def test_a_header_sorted_into_the_body_is_refused_by_name(tmp_path):
    p = tmp_path / "REPO_MANIFEST.csv"
    p.write_bytes(b"a.txt,1,x\r\npath,bytes,sha256\r\nz.txt,1,y\r\n")
    import pytest
    with pytest.raises(rm.ManifestFormatError, match="first row"):
        rm.read_existing(p)


def test_an_unsorted_manifest_is_refused(tmp_path):
    p = tmp_path / "m.csv"
    p.write_bytes(b"path,bytes,sha256\r\nz.txt,1,y\r\na.txt,1,x\r\n")
    import pytest
    with pytest.raises(rm.ManifestFormatError, match="sorted"):
        rm.read_existing(p)
