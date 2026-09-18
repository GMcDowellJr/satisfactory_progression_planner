from pathlib import Path
import numpy as np
import pandas as pd
from types import SimpleNamespace

from world_viewer.io import available_platform_elevations, load_membership
from world_viewer.geometry import surface_overlay_cells


def test_plane_membership_discovery_and_load(tmp_path):
    np.savez_compressed(tmp_path/'build_surface_membership_16m_plane_neg16m.npz', labels=np.array([[1]],dtype=np.int32))
    np.savez_compressed(tmp_path/'build_surface_membership_16m_plane_pos0m.npz', labels=np.array([[2]],dtype=np.int32))
    assert available_platform_elevations(tmp_path,16) == [-16.0,0.0]
    assert load_membership(tmp_path,16,-16)[0,0] == 1


def test_sweep_overlay_is_flat_at_platform_elevation():
    world=SimpleNamespace(height_m=np.array([[1,2],[3,4]],dtype=np.float32), water_m=np.full((2,2),np.nan,dtype=np.float32), spacing_m=1.0,east0_m=0.0,north0_m=1.0)
    labels=np.array([[1]],dtype=np.int32)
    df=pd.DataFrame([{'surface_id':'bs_1_2m_ppos10m_00001','analysis_resolution_m':2.0,'platform_elevation_m':10.0,'size_class':'small'}])
    pts,quads,rows,ranks,meta=surface_overlay_cells(world,labels,df,2.0,platform_elevation_m=10.0,z_offset_m=2.0)
    assert len(quads)==1
    assert np.allclose(pts[:,2],12.0)
