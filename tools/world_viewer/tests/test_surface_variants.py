from pathlib import Path
import numpy as np

from world_viewer.io import available_surface_variants, available_surface_resolutions, available_region_spans, load_membership


def test_variant_discovery_and_load(tmp_path: Path):
    np.savez_compressed(tmp_path / 'build_surface_membership_16m_z2m.npz', labels=np.array([[1]], dtype=np.int32))
    np.savez_compressed(tmp_path / 'build_surface_membership_16m_z8m.npz', labels=np.array([[2]], dtype=np.int32))
    np.savez_compressed(tmp_path / 'build_surface_membership_8m_z4m.npz', labels=np.array([[3]], dtype=np.int32))
    assert available_surface_variants(tmp_path) == [(8.0, 4.0), (16.0, 2.0), (16.0, 8.0)]
    assert available_surface_resolutions(tmp_path) == [8.0, 16.0]
    assert available_region_spans(tmp_path, 16.0) == [2.0, 8.0]
    assert int(load_membership(tmp_path, 16.0, 2.0)[0,0]) == 1
    # Without an explicit span, v2 defaults to the largest available span.
    assert int(load_membership(tmp_path, 16.0)[0,0]) == 2
