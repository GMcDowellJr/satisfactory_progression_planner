"""tools/site_planner_web/publish.py and the two hosts (reframe A20.7, Greg 2026-11-18).

Netlify publishes dist/ built by publish.py; GitHub Pages serves the repo root
and needs .nojekyll. Either way the worker fetches bundle_files.json's paths
relative to the repo root, so the published tree must hold every one of them
at its repo path.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
WEB = REPO / "tools" / "site_planner_web"


def _publish():
    spec = importlib.util.spec_from_file_location("site_planner_publish", WEB / "publish.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_site_holds_the_pages_and_every_bundle_file(tmp_path):
    P = _publish()
    P.publish(tmp_path)
    for page in ("planner.html", "picker.html", "index.html", "worker.js", "bundle_files.json",
                 "precomputed/neighborhoods_v020.json", "precomputed/basemap_502094.png"):
        assert (tmp_path / "tools" / "site_planner_web" / page).is_file(), page
    bundle = json.loads((WEB / "bundle_files.json").read_text(encoding="utf-8"))
    for rel in bundle:
        assert (tmp_path / rel).read_bytes() == (REPO / rel).read_bytes(), rel
    # nothing beyond the pages and the bundle: no tracer, no tests, no other data
    published = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert published == set(P.site_files())
    assert "tools/site_planner_web/bundle.py" not in published


def test_a_missing_file_is_refused_by_name(tmp_path, monkeypatch):
    P = _publish()
    monkeypatch.setattr(P, "site_files", lambda: ["tools/no_such_file.py"])
    with pytest.raises(P.PublishError, match="tools/no_such_file.py"):
        P.publish(tmp_path)


def test_netlify_builds_the_viewer_then_publishes_the_pages():
    toml = (REPO / "netlify.toml").read_text(encoding="utf-8")
    assert 'publish = "dist"' in toml
    assert "demand_expansion_cli.py viewer --out dist/index.html" in toml
    assert "tools/site_planner_web/publish.py --out dist" in toml


def test_pages_serves_underscore_files():
    """Without .nojekyll, GitHub Pages' Jekyll drops __init__.py and the worker fails."""
    assert (REPO / ".nojekyll").is_file()
    assert any(pathlib.PurePosixPath(p).name.startswith("_")
               for p in json.loads((WEB / "bundle_files.json").read_text(encoding="utf-8")))
