"""Provenance reconciliation: re-derive solver-relevant reference tables from the
pinned game Docs and diff against the repo's committed CSVs. Read-only."""
import json, re, csv, os, hashlib, collections

DOCS="/mnt/user-data/uploads/Docs/en-US.json"
REF="/mnt/user-data/uploads/satisfactory_progression_planner/planning_data/game/reference"
raw=open(DOCS,'rb').read(); d=json.loads(raw.decode('utf-16'))
def rd(n): return list(csv.DictReader(open(os.path.join(REF,n),encoding='utf-8')))
def classes(sfx):
    for e in d:
        if e['NativeClass'].endswith(sfx):
            for c in e['Classes']: yield c

FIXED="FGBuildableManufacturer'"; VAR="FGBuildableManufacturerVariablePower'"
producers={c['ClassName'] for s in (FIXED,VAR) for c in classes(s)}
CLS=re.compile(r"\.(\w+_C)")
ITEM=re.compile(r'ItemClass="[^"]*?\.(\w+_C)\'",Amount=(\d+)')

# item forms, to convert fluid amounts (cm3 -> m3)
form={}
for sfx in ["FGItemDescriptor'","FGResourceDescriptor'","FGItemDescriptorBiomass'",
            "FGItemDescriptorNuclearFuel'","FGConsumableDescriptor'","FGEquipmentDescriptor'",
            "FGAmmoTypeProjectile'","FGAmmoTypeInstantHit'","FGAmmoTypeSpreadshot'",
            "FGPowerShardDescriptor'","FGItemDescriptorPowerBoosterFuel'"]:
    for c in classes(sfx): form[c['ClassName']]=c.get('mForm','RF_SOLID')

docs_rec={}
for c in classes("FGRecipe'"):
    hit=[p for p in CLS.findall(c.get('mProducedIn','') or '') if p in producers]
    if not hit: continue
    dur=float(c['mManufactoringDuration'])
    io=[]
    for direction,key in (('input','mIngredients'),('output','mProduct')):
        for iid,amt in ITEM.findall(c.get(key,'') or ''):
            a=float(amt)
            fluid = form.get(iid,'RF_SOLID') in ('RF_LIQUID','RF_GAS')
            per_cycle = a/1000.0 if fluid else a
            io.append((direction,iid,round(per_cycle,6),round(per_cycle*60.0/dur,6)))
    docs_rec[c['ClassName']]={'producer':hit[0],'name':c['mDisplayName'],'dur':dur,
                              'alt':'Alternate' in c['ClassName'] or 'Recipe_Alternate' in c['ClassName'],'io':io}

def hdr(t): print('\n'+'='*4,t)

# --- recipe_producers ----------------------------------------------------
hdr('recipe_producers.csv')
repo={r['recipe_id']:r['producer_class'] for r in rd('recipe_producers.csv')}
docs={k:v['producer'] for k,v in docs_rec.items()}
print(f'  repo {len(repo)} rows | docs {len(docs)} rows')
print(f'  only in repo: {sorted(set(repo)-set(docs))[:5]}  ({len(set(repo)-set(docs))})')
print(f'  only in docs: {sorted(set(docs)-set(repo))[:5]}  ({len(set(docs)-set(repo))})')
mis=[(k,repo[k],docs[k]) for k in set(repo)&set(docs) if repo[k]!=docs[k]]
print(f'  producer mismatches: {len(mis)} {mis[:3]}')

# --- recipes -------------------------------------------------------------
hdr('recipes.csv')
rr={r['recipe_id']:r for r in rd('recipes.csv')}
dur_mis=[(k,rr[k]['manufacturing_duration_sec'],docs_rec[k]['dur']) for k in set(rr)&set(docs_rec)
         if abs(float(rr[k]['manufacturing_duration_sec'])-docs_rec[k]['dur'])>1e-6]
name_mis=[(k,rr[k]['display_name'],docs_rec[k]['name']) for k in set(rr)&set(docs_rec)
          if rr[k]['display_name']!=docs_rec[k]['name']]
alt_mis=[(k,rr[k]['is_alternate'],docs_rec[k]['alt']) for k in set(rr)&set(docs_rec)
         if (rr[k]['is_alternate']=='true')!=docs_rec[k]['alt']]
print(f'  rows repo {len(rr)} / docs {len(docs_rec)}')
print(f'  duration mismatches: {len(dur_mis)} {dur_mis[:3]}')
print(f'  display_name mismatches: {len(name_mis)} {name_mis[:3]}')
print(f'  is_alternate mismatches: {len(alt_mis)} {alt_mis[:3]}')

# --- recipe_io -----------------------------------------------------------
hdr('recipe_io.csv')
repo_io=collections.defaultdict(set)
for r in rd('recipe_io.csv'):
    repo_io[r['recipe_id']].add((r['direction'],r['item_id'],round(float(r['amount_per_cycle']),6),
                                 round(float(r['rate_per_min']),6)))
docs_io={k:set(v['io']) for k,v in docs_rec.items()}
tot=sum(len(v) for v in repo_io.values()); dtot=sum(len(v) for v in docs_io.values())
print(f'  rows repo {tot} / docs {dtot}')
bad=[]
for k in set(repo_io)&set(docs_io):
    if repo_io[k]!=docs_io[k]: bad.append(k)
print(f'  recipes whose io set differs: {len(bad)}')
for k in bad[:3]:
    print(f'    {k}\n      repo-only {sorted(repo_io[k]-docs_io[k])}\n      docs-only {sorted(docs_io[k]-repo_io[k])}')

# --- items ---------------------------------------------------------------
hdr('items.csv')
ri={r['item_id']:r for r in rd('items.csv')}
di={}
for sfx,c in ((s,c) for s in form for c in []): pass
allitems={}
for sfx in ["FGItemDescriptor'","FGResourceDescriptor'","FGItemDescriptorBiomass'",
            "FGItemDescriptorNuclearFuel'","FGConsumableDescriptor'","FGEquipmentDescriptor'",
            "FGAmmoTypeProjectile'","FGAmmoTypeInstantHit'","FGAmmoTypeSpreadshot'",
            "FGPowerShardDescriptor'","FGItemDescriptorPowerBoosterFuel'"]:
    for c in classes(sfx): allitems[c['ClassName']]=c
print(f'  repo {len(ri)} rows | docs item descriptors (all kinds) {len(allitems)}')
print(f'  repo items missing from docs: {sorted(set(ri)-set(allitems))[:5]} ({len(set(ri)-set(allitems))})')
sp=[(k,ri[k]["sink_points"],allitems[k].get("mResourceSinkPoints")) for k in set(ri)&set(allitems)
    if str(int(float(ri[k]["sink_points"] or 0)))!=str(allitems[k].get("mResourceSinkPoints"))]
print(f'  sink_points mismatches: {len(sp)} {sp[:3]}')
