from pathlib import Path
import json
import numpy as np
import pandas as pd

from world_viewer.io import analysis_model, available_local_relief_tolerances, load_membership, load_rectangles


def test_local_relief_variant_discovery_and_rectangle_load(tmp_path: Path):
    np.savez_compressed(tmp_path/'build_surface_membership_16m_relief_4m.npz', labels=np.array([[1]],dtype=np.int32))
    np.savez_compressed(tmp_path/'build_surface_membership_16m_relief_8m.npz', labels=np.array([[2]],dtype=np.int32))
    (tmp_path/'build_surface_membership_index.json').write_text(json.dumps({
        'analysis_model':'local_multiscale_relief',
        'variants':[{'resolution_m':16,'local_relief_tolerance_m':4,'file':'build_surface_membership_16m_relief_4m.npz'},
                    {'resolution_m':16,'local_relief_tolerance_m':8,'file':'build_surface_membership_16m_relief_8m.npz'}]
    }))
    pd.DataFrame([{'surface_id':'x','analysis_model':'local_multiscale_relief'}]).to_csv(tmp_path/'build_surfaces.csv',index=False)
    pd.DataFrame([{'rectangle_id':'r','surface_id':'x'}]).to_csv(tmp_path/'build_surface_rectangles.csv',index=False)
    assert analysis_model(tmp_path) == 'local_multiscale_relief'
    assert available_local_relief_tolerances(tmp_path,16) == [4.0,8.0]
    assert int(load_membership(tmp_path,16,local_relief_tolerance_m=8)[0,0]) == 2
    assert load_rectangles(tmp_path).iloc[0]['rectangle_id'] == 'r'
