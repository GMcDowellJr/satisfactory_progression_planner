// The site planner's Python runtime: this repo's own code, in Pyodide, in a Web Worker.
// Used by picker.html (portfolio track) and planner.html (run and factory
// tracks, reframe A20): every figure either page shows comes from here.
//
// Decided by Greg: the HTML layer runs the repo's Python in the browser
// (2026-10-19 16:10); precomputed exports are the starting point and the
// policy can be recomputed in the browser (2026-10-23 15:36, reframe A10).
// Pyodide 0.27.7 from the CDN, pinned (Greg 2026-10-19 18:23).
//
// Files: exactly bundle_files.json (traced by bundle.py from the runs this
// worker makes), fetched relative to the repo root, so the page must be
// served from the repo root over http (file:// cannot fetch). A missing file
// is reported by its path, never skipped.
//
// Messages in:  {id, op, arg}; op is
//   picker:  "boot" | "pairs" | "neighborhoods" | "run" (portfolio-inputs/2)
//   planner: "catalog" | "tier" (milestones through tier N) | "generators"
//            (classes a playthrough owns) | "run_plan" (run-inputs/1) |
//            "handoff" ({run, decl} -> factory-inputs/1) | "factory" (factory-inputs/1)
// A Python refusal is passed back as Python worded it (its last line).
// Messages out: {id, ok: true, result, ms} | {id, ok: false, error}
//               {status: "..."} while booting
"use strict";
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/";
importScripts(PYODIDE + "pyodide.js");
const ROOT = new URL("../../", self.location.href);  // tools/site_planner_web/ -> repo root

// planner.html's ops: each answers with the Python's JSON text, parsed by the page
const PLANNER_OPS = new Set(["catalog", "tier", "generators", "run_plan", "handoff", "factory"]);

let ready = null;
function boot() {
  if (ready) return ready;
  ready = (async () => {
    const t0 = performance.now();
    postMessage({ status: "loading Python" });
    const py = await loadPyodide({ indexURL: PYODIDE });
    postMessage({ status: "loading numpy, scipy" });
    await py.loadPackage(["numpy", "scipy"]);
    const list = await (await fetch(new URL("bundle_files.json", self.location.href))).json();
    postMessage({ status: `fetching ${list.length} repo files` });
    const bodies = await Promise.all(list.map(async path => {
      const r = await fetch(new URL(path, ROOT));
      if (!r.ok) throw new Error(`bundle file missing: ${path} (HTTP ${r.status}); serve the page from the repo root`);
      return [path, new Uint8Array(await r.arrayBuffer())];
    }));
    for (const [path, bytes] of bodies) {
      const full = "/repo/" + path;
      py.FS.mkdirTree(full.slice(0, full.lastIndexOf("/")));
      py.FS.writeFile(full, bytes);
    }
    py.runPython(`
import json, os, sys
os.chdir("/repo")
sys.path[:0] = ["/repo/tools", "/repo/tools/production_adapter/src", "/repo/tools/progression/src",
                "/repo/tools/realization/src"]
import neighborhoods, portfolio_run, site_card
import factory_run, planner_catalog, run_plan
REPO = portfolio_run.REPO
from production_adapter import load

def _pairs(world):
    seen = {}
    for s in site_card.load_sockets(portfolio_run.REPO, world):
        seen[(s.source_kind, s.item_id)] = seen.get((s.source_kind, s.item_id), 0) + 1
    data = load(portfolio_run.REPO)
    return json.dumps([{"source_kind": k, "item_id": i, "count": n,
                        "name": data.items[i].display_name if i in data.items else None}
                       for (k, i), n in seen.items()])

def _neighborhoods(arg):
    a = json.loads(arg)
    return json.dumps(neighborhoods.export_for(a["policy"], a["world_config_id"]))

def _run(arg):
    doc = json.loads(arg)
    pr, scenario = portfolio_run.run_inputs(doc)
    data = load(portfolio_run.REPO, scenario)
    # the same text portfolio_run.export writes (indent 1, LF)
    return json.dumps(portfolio_run.record(pr, data, portfolio_run.provenance(), doc), indent=1) + "\\n"

# planner.html (reframe A20); records as their CLIs' --export writes them (indent 1, LF)
def _catalog(arg):
    return json.dumps(planner_catalog.catalog(REPO))

def _tier(arg):
    return json.dumps(planner_catalog.tier_milestones(REPO, json.loads(arg)))

def _generators(arg):
    return json.dumps(planner_catalog.generators_owned(REPO, json.loads(arg)))

# record: the --export text, byte for byte; report: the CLI's printed report, which
# carries the figures the record leaves to properties (the stack's headroom)
def _run_plan(arg):
    plan = run_plan.run_inputs(json.loads(arg), REPO)
    return json.dumps({"record": json.dumps(run_plan.record(plan), indent=1, default=str) + "\\n",
                       "report": run_plan.report(plan)})

def _handoff(arg):
    a = json.loads(arg)
    return json.dumps(run_plan.handoff(a["run"], a["decl"], REPO), indent=1) + "\\n"

def _factory(arg):
    run = factory_run.run_inputs(json.loads(arg), REPO)
    return json.dumps({"record": json.dumps(factory_run.record(run), indent=1, default=str) + "\\n",
                       "report": factory_run.report(run)})
`);
    postMessage({ status: `ready (${Math.round(performance.now() - t0)} ms to start)` });
    return py;
  })();
  ready.catch(() => { ready = null; });  // let a later message retry
  return ready;
}

function pyError(e) {
  // a Python exception's message ends with "ErrorName: message"; keep that line
  const lines = String(e && e.message || e).trim().split("\n");
  return lines[lines.length - 1];
}

onmessage = async ev => {
  const { id, op, arg } = ev.data;
  const t0 = performance.now();
  try {
    const py = await boot();
    let result = null;
    if (op === "pairs") result = JSON.parse(py.globals.get("_pairs")(arg));
    else if (op === "neighborhoods") result = JSON.parse(py.globals.get("_neighborhoods")(JSON.stringify(arg)));
    // the record's own Python JSON text, unparsed: JSON.stringify would rewrite
    // 60.0 as 60, and the record should match a native export byte for byte
    else if (op === "run") result = { text: py.globals.get("_run")(JSON.stringify(arg)) };
    else if (PLANNER_OPS.has(op)) result = { text: py.globals.get("_" + op)(JSON.stringify(arg ?? null)) };
    else if (op !== "boot") throw new Error(`no op ${op}`);
    postMessage({ id, ok: true, result, ms: Math.round(performance.now() - t0) });
  } catch (e) {
    postMessage({ id, ok: false, error: pyError(e) });
  }
};
