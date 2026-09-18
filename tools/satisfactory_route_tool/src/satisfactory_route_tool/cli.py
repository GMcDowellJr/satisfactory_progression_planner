from __future__ import annotations

import argparse, json
from pathlib import Path

from .package import PlannerPackage
from .heightfield import load_working_field
from .profiles import load_profile
from .roads import extract_road_prior, load_road_prior
from .solver import solve, write_result
from .poi import score_pois


def _parse_crop(text):
    if text is None: return None
    vals=[int(x) for x in text.split(",")]
    if len(vals)!=4: raise argparse.ArgumentTypeError("crop must be x0,y0,x1,y1")
    return vals


def main(argv=None):
    ap=argparse.ArgumentParser(prog="satisfactory-route")
    sub=ap.add_subparsers(dest="cmd",required=True)

    p=sub.add_parser("extract-scim",help="make aligned coarse road-prior raster from a SCIM screenshot")
    p.add_argument("--planner",required=True)
    p.add_argument("--image",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--build",default="502094")
    p.add_argument("--step-m",type=float,default=5.0)
    p.add_argument("--road-band-m",type=float,default=25.0)
    p.add_argument("--crop",type=_parse_crop)

    p=sub.add_parser("solve",help="solve one mode-aware route")
    p.add_argument("--planner",required=True)
    p.add_argument("--roads")
    p.add_argument("--origin",nargs=2,type=float,required=True,metavar=("EAST_M","NORTH_M"))
    p.add_argument("--destination",nargs=2,type=float,required=True,metavar=("EAST_M","NORTH_M"))
    p.add_argument("--mode",choices=["foot","tractor","truck","rail"],required=True)
    p.add_argument("--bridge-policy",choices=["forbid","allow"],default="forbid")
    p.add_argument("--profiles")
    p.add_argument("--build",default="502094")
    p.add_argument("--step-m",type=float,default=5.0)
    p.add_argument("--corridor-pad-m",type=float,default=800.0)
    p.add_argument("--out",required=True)

    p=sub.add_parser("score-pois",help="rank on-foot exploration detours from a solved route")
    p.add_argument("--planner",required=True)
    p.add_argument("--route",required=True)
    p.add_argument("--trip-type",default="first_trip")
    p.add_argument("--max-offset-m",type=float,default=350.0)
    p.add_argument("--out",required=True)

    args=ap.parse_args(argv)

    if args.cmd=="extract-scim":
        pkg=PlannerPackage(args.planner)
        field=load_working_field(pkg,args.build,args.step_m)
        meta=extract_road_prior(args.image,field,args.out,args.crop,args.road_band_m)
        print(json.dumps(meta,indent=2))
        return 0

    if args.cmd=="solve":
        pkg=PlannerPackage(args.planner)
        field=load_working_field(pkg,args.build,args.step_m)
        roads=band=None
        if args.roads:
            roads,band=load_road_prior(args.roads,field.shape)
        profile=load_profile(args.mode,args.profiles)
        result=solve(
            field,tuple(args.origin),tuple(args.destination),profile,
            roads=roads,road_band=band,bridge_policy=args.bridge_policy,
            corridor_pad_m=args.corridor_pad_m,
        )
        write_result(result,args.out,field,roads)
        print(json.dumps(result.summary,indent=2))
        return 0

    if args.cmd=="score-pois":
        pkg=PlannerPackage(args.planner)
        df=score_pois(pkg,args.route,args.out,args.trip_type,args.max_offset_m)
        print(df["recommendation_class"].value_counts().to_string())
        return 0


if __name__=="__main__":
    raise SystemExit(main())
