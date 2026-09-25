from pathlib import Path
import argparse, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/build_surface_tool/src'))
from build_surface_tool.calibration import compare_foundation_fixture, validate_calibration_summary

p=argparse.ArgumentParser(description='Compare a foundation calibration fixture against the versioned terrain heightfield.')
p.add_argument('fixture_csv',type=Path)
p.add_argument('--world-manifest',type=Path,default=ROOT/'planning_data/world/manifests/world_502094.json')
p.add_argument('--output-dir',type=Path,default=None)
args=p.parse_args(); out=args.output_dir or args.fixture_csv.parent
s=compare_foundation_fixture(ROOT,args.world_manifest,args.fixture_csv,out)
expected_path=args.fixture_csv.parent/'expected.json'
if expected_path.exists():
    import json
    expected=json.loads(expected_path.read_text(encoding='utf-8'))
    validation=validate_calibration_summary(s,expected)
    (Path(out)/'validation.json').write_text(json.dumps(validation,indent=2)+'\n',encoding='utf-8', newline="\n")
    print(f"calibration {validation['status']}; ground p95 top clearance: {s['ground_top_clearance_m']['p95']:.2f} m; cliff/overhead centers: {s['cliff_or_overhead_top_surface_center_count']}")
    raise SystemExit(0 if validation['status']=='PASS' else 2)
print(f"ground p95 top clearance: {s['ground_top_clearance_m']['p95']:.2f} m; cliff/overhead centers: {s['cliff_or_overhead_top_surface_center_count']}")
