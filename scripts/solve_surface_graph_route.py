from __future__ import annotations

import argparse, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'tools'/'satisfactory_route_tool'/'src'
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))

from satisfactory_route_tool.package import PlannerPackage
from satisfactory_route_tool.heightfield import load_working_field
from satisfactory_route_tool.profiles import load_profile
from satisfactory_route_tool.graph_solver import solve_surface_graph, write_result


def main():
    p=argparse.ArgumentParser(description='Solve one route using the hybrid layered surface graph')
    p.add_argument('--planner',default='planning_data')
    p.add_argument('--surface-graph',required=True)
    p.add_argument('--intervals')
    p.add_argument('--roads')
    p.add_argument('--origin',nargs=2,type=float,required=True,metavar=('EAST_M','NORTH_M'))
    p.add_argument('--destination',nargs=2,type=float,required=True,metavar=('EAST_M','NORTH_M'))
    p.add_argument('--mode',choices=['foot','tractor','truck','rail'],default='tractor')
    p.add_argument('--profiles')
    p.add_argument('--build',default='502094')
    p.add_argument('--bridge-policy',choices=['forbid','allow'],default='forbid')
    p.add_argument('--corridor-pad-m',type=float,default=800.0)
    p.add_argument('--endpoint-access-radius-m',type=float,default=200.0)
    p.add_argument('--minimum-clearance-m',type=float)
    p.add_argument('--out',required=True)
    args=p.parse_args()

    meta=json.loads((Path(args.surface_graph)/'meta.json').read_text(encoding='utf-8'))
    step=float(meta['grid']['step_m'])
    pkg=PlannerPackage(args.planner)
    field=load_working_field(pkg,args.build,step)
    profile=dict(load_profile(args.mode,args.profiles)); profile['_mode']=args.mode
    result=solve_surface_graph(
        field,tuple(args.origin),tuple(args.destination),profile,
        surface_graph_dir=args.surface_graph, intervals_path=args.intervals,
        road_prior_path=args.roads, bridge_policy=args.bridge_policy,
        corridor_pad_m=args.corridor_pad_m,
        minimum_clearance_m=args.minimum_clearance_m,
        endpoint_access_radius_m=args.endpoint_access_radius_m,
    )
    write_result(result,args.out)
    print(json.dumps(result.summary,indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
