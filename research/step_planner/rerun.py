import csv, sys
from collections import defaultdict
import pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))  # EDIT (a): sibling imports under python -I
import p5_walkback as W
D=str(HERE.parents[1]/'planning_data/game/reference')+'/'  # EDIT (a): was '/mnt/user-data/uploads/satisfactory_progression_planner/planning_data/game/reference/'
rec={r['recipe_id']:r for r in csv.DictReader(open(D+'recipes.csv'))}
io=defaultdict(lambda:{'in':{},'out':{}})
nm=lambda s:'Screw' if s=='Screws' else s
for r in csv.DictReader(open(D+'recipe_io.csv')):
    io[r['recipe_id']]['in' if r['direction']=='input' else 'out'][nm(r['item_name'])]=float(r['amount_per_cycle'])
pick={'Ficsite Ingot':sys.argv[1] if len(sys.argv)>1 else 'Recipe_FicsiteIngot_AL_C'}
R={}
for p in W.R:
    if p in pick: rid=pick[p]
    else:
        c=[rid for rid,x in io.items() if p in x['out'] and rec.get(rid,{}).get('is_alternate')=='false' and (p=='Excited Photonic Matter' or x['in'])]
        if len(c)>1: c=[r for r in c if rec[r]["display_name"].startswith(p)]
        assert len(c)==1,(p,c); rid=c[0]
        if p=='Excited Photonic Matter': pass
    x=io[rid]; o=x['out'][p]; by={k:v for k,v in x['out'].items() if k!=p}
    R[p]=(o,dict(x['in']),by)
W.R.clear(); W.R.update(R)
import numpy as np
W.A[:]=0
for j,p in enumerate(W.items):
    o,ins,by=R[p]; W.A[W.idx[p],j]+=o
    for k,v in list(ins.items())+[(k,-v) for k,v in by.items()]:
        if k in W.idx: W.A[W.idx[k],j]-=v
for tag,dem in [("ALL",{f:1 for f in W.FINAL})]+[(f,{f:1}) for f in W.FINAL]:
    prod,raw=W.solve(dem)
    print(tag, {k:round(float(v),1) for k,v in sorted(raw.items(),key=lambda t:-t[1])})
prod,raw=W.solve({f:1 for f in W.FINAL})
for k in ["Nuclear Pasta","Superposition Oscillator","Dark Matter Crystal","Diamonds","Time Crystal","Dark Matter Residue","Reanimated SAM","Ficsite Ingot","Ficsite Trigon","Copper Powder","Excited Photonic Matter","Aluminum Ingot"]: print(k, round(prod.get(k,0),2))
