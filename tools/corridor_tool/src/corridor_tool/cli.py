from __future__ import annotations
import argparse,json
from pathlib import Path
from .field import load_field
from .derive import derive
from .io import write_result

def main(argv=None):
    p=argparse.ArgumentParser(description="Derive terrain corridor/connectivity geometry from a versioned world extraction.")
    p.add_argument("--repo",default=".")
    p.add_argument("--manifest",default="planning_data/world/manifests/world_502094.json")
    p.add_argument("--policy",default="planning_data/analysis/policies/corridors_v1.json")
    p.add_argument("--step-m",type=float)
    p.add_argument("--output")
    a=p.parse_args(argv)
    repo=Path(a.repo).resolve(); manifest_path=(repo/a.manifest).resolve(); policy_path=(repo/a.policy).resolve()
    policy=json.loads(policy_path.read_text(encoding="utf-8")); step=a.step_m or float(policy["analysis_step_m"])
    field,manifest=load_field(repo,manifest_path,step)
    result=derive(field,policy)
    out=Path(a.output).resolve() if a.output else repo/"planning_data"/"analysis"/"derived"/"corridors"/f"build_{manifest['game']['build']}"/policy["policy_id"]
    write_result(result,out,policy,manifest)
    print(json.dumps({**result.summary,"output":str(out)},indent=2))
    return 0
