from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'tools'/'corridor_tool'/'src'
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
from corridor_tool.field import load_field
from corridor_tool.query import shortest_corridor, corridor_alternatives
import pandas as pd


def main(argv=None):
    p=argparse.ArgumentParser(description='Query the reusable terrain corridor graph between arbitrary endpoints.')
    p.add_argument('--repo',default='.')
    p.add_argument('--manifest',default='planning_data/world/manifests/world_502094.json')
    p.add_argument('--policy',default='planning_data/analysis/policies/corridors_v1.json')
    p.add_argument('--corridors',default='planning_data/analysis/derived/corridors/build_502094/corridors_v1')
    p.add_argument('--origin',nargs=2,type=float,required=True,metavar=('EAST_M','NORTH_M'))
    p.add_argument('--destination',nargs=2,type=float,required=True,metavar=('EAST_M','NORTH_M'))
    p.add_argument('--out',required=True)
    p.add_argument('--alternatives',type=int,default=1,help='number of materially distinct physical corridor candidates')
    p.add_argument('--separation-m',type=float,default=128.0,help='avoidance band around earlier candidates')
    p.add_argument('--avoidance-penalty',type=float,default=3.0,help='cost multiplier strength inside the avoidance band')
    a=p.parse_args(argv)
    repo=Path(a.repo).resolve(); policy=json.loads((repo/a.policy).read_text())
    field,_=load_field(repo,(repo/a.manifest).resolve(),float(policy['analysis_step_m']))
    cdir=(repo/a.corridors).resolve()
    nodes=pd.read_csv(cdir/'corridor_nodes.csv'); edges=pd.read_csv(cdir/'corridor_edges.csv')
    out=Path(a.out).resolve(); out.mkdir(parents=True,exist_ok=True)
    if a.alternatives <= 1:
        result=shortest_corridor(nodes,edges,tuple(a.origin),tuple(a.destination),field.east0_m,field.north0_m,field.step_m)
        result.points.to_csv(out/'corridor_route_points.csv',index=False)
        result.edges.to_csv(out/'corridor_route_edges.csv',index=False)
        (out/'corridor_route_summary.json').write_text(json.dumps(result.summary,indent=2),encoding='utf-8')
        print(json.dumps(result.summary,indent=2)); return 0
    results=corridor_alternatives(nodes,edges,tuple(a.origin),tuple(a.destination),field.east0_m,field.north0_m,field.step_m,
                                  count=a.alternatives,separation_m=a.separation_m,avoidance_penalty=a.avoidance_penalty)
    summaries=[]
    for i,result in enumerate(results,1):
        sub=out/f'alt_{i}'; sub.mkdir(parents=True,exist_ok=True)
        result.points.to_csv(sub/'corridor_route_points.csv',index=False)
        result.edges.to_csv(sub/'corridor_route_edges.csv',index=False)
        (sub/'corridor_route_summary.json').write_text(json.dumps(result.summary,indent=2),encoding='utf-8')
        summaries.append(result.summary)
    (out/'corridor_alternatives_summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
    print(json.dumps(summaries,indent=2)); return 0

if __name__=='__main__': raise SystemExit(main())
