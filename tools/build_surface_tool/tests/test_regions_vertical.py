import numpy as np
from build_surface_tool.regions import label_regions_by_elevation_band


def test_aligned_vertical_spans_progressively_merge():
    usable = np.ones((1, 8), dtype=bool)
    z = np.array([[0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5]], dtype=np.float32)
    labels2, regions2 = label_regions_by_elevation_band(usable, z, 2.0, 0.0)
    labels4, regions4 = label_regions_by_elevation_band(usable, z, 4.0, 0.0)
    labels8, regions8 = label_regions_by_elevation_band(usable, z, 8.0, 0.0)
    assert len(regions2) == 4
    assert len(regions4) == 2
    assert len(regions8) == 1
    assert labels2.shape == labels4.shape == labels8.shape
