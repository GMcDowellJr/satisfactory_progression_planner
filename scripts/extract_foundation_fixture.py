from pathlib import Path
import argparse, json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/build_surface_tool/src'))
from build_surface_tool.save_fixture import foundation_dataframe, select_flat_component

p=argparse.ArgumentParser(description='Extract a connected flat foundation component from a Satisfactory .sav for build-surface calibration.')
p.add_argument('save',type=Path)
p.add_argument('--z-m',type=float,required=True,help='Foundation transform-origin elevation to select, in metres.')
p.add_argument('--output-dir',type=Path,required=True)
p.add_argument('--foundation-height-m',type=float,default=4.0)
p.add_argument('--spacing-m',type=float,default=8.0)
args=p.parse_args()
allf=foundation_dataframe(args.save,foundation_height_m=args.foundation_height_m)
fixture=select_flat_component(allf,args.z_m,spacing_m=args.spacing_m,largest=True)
args.output_dir.mkdir(parents=True,exist_ok=True)
fixture.to_csv(args.output_dir/'foundations.csv',index=False)
meta={'source_save_name':args.save.name,'save_build':int(fixture['save_build'].iloc[0]),'selection':{'class':'Build_Foundation_8x4_01','origin_z_m':args.z_m,'largest_edge_connected_component':True,'spacing_m':args.spacing_m},'foundation_count':int(len(fixture)),'foundation_height_m':args.foundation_height_m}
(args.output_dir/'fixture.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
print(f"wrote {len(fixture)} foundations to {args.output_dir/'foundations.csv'}")
