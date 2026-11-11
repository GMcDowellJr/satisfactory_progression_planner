# alt_deps.py -- regenerate alternate-schematic dependencies from the game-docs snapshot (scratch; repo untouched).
# alternate_choices.csv's dependency column is truncated (formulation record s19.3: ids split on '-', e.g. 'Schematic_4-1_C' -> '1_C').
import json, re, csv
import pathlib; HERE = pathlib.Path(__file__).resolve().parent; REPO = HERE.parents[1]  # EDIT (a): repo root = two levels up
SNAP = str(REPO / 'planning_data/game/source_snapshots/docs_a81d250e96aa/en-US.json')  # EDIT (a): was '/home/claude/gmcdowelljr/satisfactory_progression_planner/planning_data/...'
D = json.loads(open(SNAP, 'rb').read().decode('utf-16'))
ids = lambda s: re.findall(r"\.([A-Za-z0-9_\-]+_C)'", s or '')
out = {}
for blk in D:
    for c in blk['Classes']:
        if c.get('mType') != 'EST_Alternate': continue
        recs = [r for u in c.get('mUnlocks', []) for r in ids(u.get('mRecipes', ''))]
        deps = []; req_all = True
        for d in c.get('mSchematicDependencies', []):
            deps += ids(d.get('mSchematics', '')); req_all = req_all and d.get('mRequireAllSchematicsToBePurchased', 'True') == 'True'
        for r in recs: out[r] = dict(schematic=c['ClassName'], tier=int(c.get('mTechTier', 0)), deps=deps, require_all=req_all)
json.dump(out, open(HERE / 'alt_deps.json', 'w', newline="\n"), indent=1)  # EDIT (b)(d): LF; was cwd
if __name__ == '__main__':
    print(len(out), 'alternate recipes with a schematic')
    print(sum(1 for v in out.values() if not v['require_all']), 'any-of dependency sets')
    from collections import Counter
    print(Counter(len(v['deps']) for v in out.values()))
    # compare with the truncated CSV
    rows = list(csv.DictReader(open(str(REPO / 'planning_data/game/reference/alternate_choices.csv'))))  # EDIT (a): was '/home/claude/gmcdowelljr/satisfactory_progression_planner/planning_data/...'
    bad = 0
    for r in rows:
        for rid in r['recipe_ids'].split(';'):
            if rid in out:
                full = ';'.join(out[rid]['deps'])
                if full != r['dependency_schematic_ids']: bad += 1
    print('rows where CSV != docs:', bad, 'of', len(rows))
    for rid in ['Recipe_Alternate_Stator_C', 'Recipe_Alternate_CircuitBoard_2_C', 'Recipe_Alternate_Wire_1_C']:
        print(rid, out.get(rid))
