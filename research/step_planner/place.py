# place.py -- when an alternate becomes obtainable, per phase, in minutes of model3's schedule (scratch).
# Rule (Greg 2026-10-28 19:16: MAM-gated alternates follow the tier/phase of their sub-components):
#   t(alt) = max( HUB dependencies paid (docs-regenerated deps, alt_deps.py),
#                 its building unlocked, every input producible )
#   MAM research dependencies are not scheduled (MAM treated as available, handoff assumption); they bind through the
#   inputs, which is where Greg's rule puts them. Producible = the item's standard recipe and building unlocked and its
#   inputs producible (recursive). Raws: ores free; fluids by extractor milestone; Bauxite/Uranium P4, SAM P5 (scanning).
import json, math
import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))  # EDIT (a): sibling imports under python -I
import model2 as M, run2
DEPS = json.load(open(HERE / 'alt_deps.json'))  # EDIT (a): was cwd-relative 'alt_deps.json'
HUB_PHASE = {t['schematic_id']: t['phase'] for t in run2.tags}
RAW_PHASE = {'Bauxite': 4, 'Uranium': 4, 'SAM': 5}
FLUID_BLDG = {'Water': 'Recipe_WaterPump_C', 'Crude Oil': 'Recipe_OilPump_C', 'Nitrogen Gas': 'Recipe_FrackingExtractor_C'}
ORES = {'Iron Ore', 'Copper Ore', 'Limestone', 'Coal', 'Caterium Ore', 'Raw Quartz', 'Sulfur', 'Bauxite', 'Uranium', 'SAM'}
MANUAL = {'Wood', 'Leaves', 'Mycelia', 'Biomass'}
_std = {}
def std_recipe(item):
    if item in M.RID: return M.RID[item]
    if item in _std: return _std[item]
    c = [rid for rid, x in M.IO.items() if item in x['out'] and M.rec.get(rid, {}).get('is_alternate') == 'false' and M.prodby.get(rid)]
    c = [r for r in c if sorted(M.prodby[r])[0] in M.BLDG] or c
    _std[item] = sorted(c, key=lambda r: (not M.rec[r]['display_name'].startswith(item), r))[0] if c else None
    return _std[item]
class Clock:
    """milestone -> minute paid, for phase k (0 if paid in an earlier phase, inf if later)."""
    def __init__(self, k, sc):
        self.k = k; self.win = {s: w[1] for s, w in sc['win'].items()}
    def paid(self, m):
        if m is None: return 0.0
        if m in self.win: return self.win[m]
        ph = HUB_PHASE.get(m)
        if ph is None:   # EST_Custom / non-HUB: owner() maps sub-schematics; MAM/other treated available
            o = M.owner(m) if m in M.sch else None
            return self.paid(o) if o and o != m else 0.0
        return 0.0 if ph < self.k else math.inf
def item_time(item, clk, memo, depth=0):
    if item in memo: return memo[item]
    memo[item] = math.inf
    if item in MANUAL: t = 0.0
    elif item in FLUID_BLDG: t = clk.paid(M.recipe_needs(FLUID_BLDG[item]))
    elif item in ORES: t = 0.0 if RAW_PHASE.get(item, 1) <= clk.k else math.inf
    else:
        rid = std_recipe(item)
        if rid is None or depth > 25: t = math.inf
        else: t = recipe_time(rid, clk, memo, depth+1)
    memo[item] = t; return t
def recipe_time(rid, clk, memo, depth=0):
    b = sorted(M.prodby[rid])[0] if M.prodby.get(rid) else None
    t = max(clk.paid(M.recipe_needs(rid)) if M.rec[rid]['is_alternate'] == 'false' else 0.0,
            clk.paid(M.recipe_needs(M.BLDG[b])) if b in M.BLDG else (0.0 if b else math.inf))
    for i in M.IO[rid]['in']:
        t = max(t, item_time(i, clk, memo, depth))
    return t
def alt_time(rid, clk, memo):
    d = DEPS.get(rid)
    if d is None: return math.inf, 'no schematic'
    hub = [x for x in d['deps'] if x.startswith('Schematic_') and not x.startswith('Schematic_Alternate')]
    alt_dep = [x for x in d['deps'] if x.startswith('Schematic_Alternate')]   # e.g. Compacted Coal research chain
    t_hub = max([clk.paid(x) for x in hub], default=0.0)
    t = max(t_hub, recipe_time(rid, clk, memo))
    why = 'HUB dep' if t_hub >= t and t_hub > 0 else 'inputs/building'
    return t, why
