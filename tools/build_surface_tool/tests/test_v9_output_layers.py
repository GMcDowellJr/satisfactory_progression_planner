from pathlib import Path
import numpy as np

from build_surface_tool import plane_fit


def test_safe_nan_stats_do_not_warn_or_raise():
    vals=np.array([np.nan,np.nan])
    assert np.isnan(plane_fit._safe_nanmean(vals))
    assert np.isnan(plane_fit._safe_nanpercentile(vals,90))
