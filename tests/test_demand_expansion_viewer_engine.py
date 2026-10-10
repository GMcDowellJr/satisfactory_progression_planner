"""The page's JavaScript engine against the Python engine, under Node.

The page runs this same comparison at every load (`Engine.selfCheck`) and
shows a banner on a difference; this test runs it here, plus a case the page
does not: an alternate declared on both sides. Node is not a repository
dependency, so the test is skipped where it is absent and the page's own
check stands in; that is an environment skip, not a way to get green.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed; the page self-checks at load")


def _page(tmp_path):
    spec = importlib.util.spec_from_file_location("demand_expansion_cli", REPO / "tools" / "demand_expansion_cli.py")
    cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
    out = tmp_path / "page.html"
    assert cli.main(["viewer", "--out", str(out)]) == 0
    html = out.read_text(encoding="utf-8")
    engine = html[html.index('<script id="engine">') + len('<script id="engine">'): html.index("</script>", html.index('<script id="engine">'))]
    start = html.index('id="payload"')
    payload = html[html.index(">", start) + 1: html.index("</script>", start)].replace("<\\/", "</")
    return engine, payload


def _run(engine: str, payload: str, harness: str, tmp_path) -> dict:
    (tmp_path / "engine.js").write_text(engine, encoding="utf-8", newline="\n")
    (tmp_path / "payload.json").write_text(payload, encoding="utf-8", newline="\n")
    (tmp_path / "run.js").write_text(
        "const Engine = require('./engine.js'); const D = require('./payload.json');\n" + harness,
        encoding="utf-8", newline="\n",
    )
    res = subprocess.run([NODE, "run.js"], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_the_page_engine_matches_the_python_engine(tmp_path):
    engine, payload = _page(tmp_path)
    r = _run(engine, payload, "console.log(JSON.stringify(Engine.selfCheck(D)));", tmp_path)
    assert r["problems"] == []
    assert r["checked"] > 4000


def test_an_alternate_agrees_on_both_sides(tmp_path):
    """Steeled Frame on Modular Frame at 1x: 13 Iron Ore, 5 Coal (VALIDATION
    table 5), from the page's engine with the alternate declared."""
    engine, payload = _page(tmp_path)
    r = _run(engine, payload, """
      const routes = {...D.routes, alternates: [['Desc_ModularFrame_C', 'Recipe_Alternate_ModularFrame_C']]};
      const G = Engine.build(D, routes); const e = Engine.expand(G, 'Desc_ModularFrame_C', 1, D.fluid_rounding_unit);
      const a = Engine.aggregate(G, D.deliveries, 1.25, 2, D.fluid_rounding_unit);
      console.log(JSON.stringify({ore: e.emb.get('Desc_OreIron_C'), coal: e.emb.get('Desc_Coal_C'),
        motor: a.cells.get('Desc_Motor_C').map(c => c.q), complete5: a.complete[5]}));
    """, tmp_path)
    assert r["ore"] == 13 and r["coal"] == 5
    assert r["motor"] == [0, 0, 3000, 8250, 6600]
    assert r["complete5"] is False
