from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd

from .io import load_world_raster
from .save_fixture import edge_mask


def compare_foundation_fixture(repo_root: Path, world_manifest: Path, fixture_csv: Path, output_dir: Path,
                               ground_provenance_codes=(1,3), overhead_provenance_codes=(4,5)) -> dict:
    manifest,raster=load_world_raster(repo_root,world_manifest)
    df=pd.read_csv(fixture_csv).copy()
    east=df['east_m'].to_numpy(float); north=df['north_m'].to_numpy(float)
    col=np.rint((east-raster.east0_m)/raster.source_spacing_m).astype(int)
    row=np.rint((raster.north0_m-north)/raster.source_spacing_m).astype(int)
    inside=(row>=0)&(row<raster.height_m.shape[0])&(col>=0)&(col<raster.height_m.shape[1])
    terrain=np.full(len(df),np.nan,float); prov=np.full(len(df),-1,int)
    terrain[inside]=raster.height_m[row[inside],col[inside]]; prov[inside]=raster.provenance[row[inside],col[inside]]
    top=df['top_elevation_m'].to_numpy(float)
    clearance=top-terrain
    is_edge=edge_mask(df)
    ground=np.isin(prov,list(ground_provenance_codes)) & np.isfinite(terrain)
    overhead=np.isin(prov,list(overhead_provenance_codes)) & np.isfinite(terrain)
    df['terrain_elevation_m']=terrain
    df['terrain_provenance_code']=prov
    names={int(k):v.get('name') for k,v in raster.meta.get('provenance',{}).items()}
    df['terrain_provenance_name']=[names.get(int(x),'unknown') for x in prov]
    df['top_clearance_m']=clearance
    df['is_component_edge']=is_edge
    df['is_ground_surface_sample']=ground
    df['is_cliff_or_overhead_top_surface']=overhead
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    df.to_csv(output_dir/'terrain_comparison.csv',index=False, lineterminator="\n")

    def pct(a,p): return float(np.nanpercentile(a,p)) if len(a) else None
    g=clearance[ground]; eg=clearance[ground & is_edge]
    summary={
      'fixture_id':Path(fixture_csv).parent.name,
      'world_extract_id':manifest.get('world_extract_id'),'game_build':int(raster.build),
      'foundation_count':int(len(df)),
      'flat_origin_elevation_m':float(df['origin_elevation_m'].median()),
      'flat_top_elevation_m':float(df['top_elevation_m'].median()),
      'foundation_height_m':float(df['foundation_height_m'].median()),
      'center_span_m':{'east':float(df['east_m'].max()-df['east_m'].min()),'north':float(df['north_m'].max()-df['north_m'].min())},
      'outer_footprint_span_m':{'east':float(df['east_m'].max()-df['east_m'].min()+8.0),'north':float(df['north_m'].max()-df['north_m'].min()+8.0)},
      'edge_foundation_count':int(is_edge.sum()),
      'ground_surface_center_count':int(ground.sum()),
      'cliff_or_overhead_top_surface_center_count':int(overhead.sum()),
      'unknown_center_count':int((~ground & ~overhead).sum()),
      'ground_surface_relief_m':float(np.max(terrain[ground])-np.min(terrain[ground])) if np.any(ground) else None,
      'ground_top_clearance_m':{
        'mean':float(np.mean(g)) if len(g) else None,'median':pct(g,50),'p90':pct(g,90),'p95':pct(g,95),'max':float(np.max(g)) if len(g) else None,
        'fraction_within_4m':float(np.mean((g>=0)&(g<=4.0))) if len(g) else None,
        'terrain_above_top_count':int(np.sum(g<0)),
      },
      'ground_edge_top_clearance_m':{
        'mean':float(np.mean(eg)) if len(eg) else None,'median':pct(eg,50),'p90':pct(eg,90),'p95':pct(eg,95),'max':float(np.max(eg)) if len(eg) else None,
        'fraction_within_4m':float(np.mean((eg>=0)&(eg<=4.0))) if len(eg) else None,
      },
      'interpretation':[
        'Landscape/fill provenance is treated as the ground-support surface for calibration.',
        'Cliff provenance can represent an overhead rock/bridge in the 2.5D heightfield and is reported separately rather than interpreted as floor penetration.',
        'This fixture is empirical calibration evidence from an existing flat 4 m foundation deck, not a universal placement rule.'
      ]
    }
    (output_dir/'calibration_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8', newline="\n")
    return summary


def validate_calibration_summary(summary: dict, expected: dict) -> dict:
    known_fraction = summary["ground_surface_center_count"] / max(summary["foundation_count"], 1)
    checks = {
        "foundation_count": int(summary["foundation_count"]) == int(expected["foundation_count"]),
        "flat_origin_elevation_m": abs(float(summary["flat_origin_elevation_m"]) - float(expected["flat_origin_elevation_m"])) < 1e-6,
        "flat_top_elevation_m": abs(float(summary["flat_top_elevation_m"]) - float(expected["flat_top_elevation_m"])) < 1e-6,
        "known_ground_fraction": known_fraction >= float(expected["minimum_known_ground_fraction"]),
        "known_ground_relief": float(summary["ground_surface_relief_m"]) <= float(expected["known_ground_relief_m_max"]),
        "known_ground_p95_top_clearance": float(summary["ground_top_clearance_m"]["p95"]) <= float(expected["known_ground_p95_top_clearance_m_max"]),
        "known_edge_p95_top_clearance": float(summary["ground_edge_top_clearance_m"]["p95"]) <= float(expected["known_edge_p95_top_clearance_m_max"]),
        "known_ground_no_top_penetration": int(summary["ground_top_clearance_m"]["terrain_above_top_count"]) == 0,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "known_ground_fraction": known_fraction, "checks": checks}
