import numpy as np
import pandas as pd
from types import SimpleNamespace

from world_viewer.geometry import regular_surface_mesh, surface_overlay_cells


def world():
    h = np.array([[0,0,0,0],[0,1,1,0],[0,1,1,0],[0,0,0,0]], dtype=np.float32)
    return SimpleNamespace(height_m=h, water_m=np.full_like(h,np.nan), spacing_m=1.0, east0_m=0.0, north0_m=3.0)


def test_regular_surface_mesh_has_faces():
    m = regular_surface_mesh(world(), spacing_m=1.0)
    assert len(m.points) == 16
    assert len(m.faces) == 18


def test_surface_overlay_uses_classified_labels():
    labels = np.array([[1,1],[0,2]], dtype=np.int32)
    df = pd.DataFrame([
        {"surface_id":"bs_1_2m_00001","analysis_resolution_m":2.0,"size_class":"small"},
        {"surface_id":"bs_1_2m_00002","analysis_resolution_m":2.0,"size_class":"medium"},
    ])
    pts, quads, rows, ranks, meta = surface_overlay_cells(world(), labels, df, 2.0, {"medium"})
    assert len(quads) == 1
    assert ranks.tolist() == [2]
