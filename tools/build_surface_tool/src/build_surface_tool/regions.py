from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class Region:
    label: int
    cells: int
    row0: int
    row1: int
    col0: int
    col1: int
    band_index: int | None = None
    band_low_m: float | None = None
    band_high_m: float | None = None


def _regions_from_labels(labels: np.ndarray, min_cells: int = 1, band_lookup: dict[int, tuple[int, float, float]] | None = None) -> tuple[np.ndarray, list[Region]]:
    count = int(labels.max(initial=0))
    if count == 0:
        return labels.astype(np.int32), []
    objects = ndimage.find_objects(labels)
    counts = np.bincount(labels.ravel())
    regions: list[Region] = []
    for lab in range(1, count + 1):
        if counts[lab] < min_cells:
            labels[labels == lab] = 0
            continue
        sl = objects[lab - 1]
        if sl is None:
            continue
        band_index = band_low = band_high = None
        if band_lookup and lab in band_lookup:
            band_index, band_low, band_high = band_lookup[lab]
        regions.append(Region(lab, int(counts[lab]), sl[0].start, sl[0].stop, sl[1].start, sl[1].stop,
                              band_index, band_low, band_high))
    return labels.astype(np.int32), regions


def label_regions(usable: np.ndarray, min_cells: int = 1) -> tuple[np.ndarray, list[Region]]:
    labels, _ = ndimage.label(usable, structure=np.array([[0,1,0],[1,1,1],[0,1,0]], dtype=np.uint8))
    return _regions_from_labels(labels, min_cells=min_cells)


def label_regions_by_elevation_band(usable: np.ndarray, z_m: np.ndarray, span_m: float, origin_m: float,
                                    min_cells: int = 1) -> tuple[np.ndarray, list[Region]]:
    """Label 4-connected regions constrained to aligned vertical elevation bands.

    Every usable cell is assigned to floor((z-origin)/span). Connected cells only
    join when they occupy the same band. Using one common origin and spans that are
    integer multiples of one another makes small-span regions nest naturally into
    larger-span regions, which is useful for calibration and visualization.
    """
    span = float(span_m)
    if span <= 0:
        raise ValueError("region vertical span must be > 0")
    valid = usable & np.isfinite(z_m)
    if not np.any(valid):
        return np.zeros_like(usable, dtype=np.int32), []

    band = np.full(z_m.shape, np.iinfo(np.int32).min, dtype=np.int32)
    band[valid] = np.floor((z_m[valid] - float(origin_m)) / span).astype(np.int32)
    labels = np.zeros_like(band, dtype=np.int32)
    next_label = 1
    band_lookup: dict[int, tuple[int, float, float]] = {}
    structure = np.array([[0,1,0],[1,1,1],[0,1,0]], dtype=np.uint8)

    for b in np.unique(band[valid]):
        local, n = ndimage.label(valid & (band == b), structure=structure)
        if n == 0:
            continue
        mask = local > 0
        local[mask] += next_label - 1
        labels[mask] = local[mask]
        low = float(origin_m) + int(b) * span
        high = low + span
        for lab in range(next_label, next_label + n):
            band_lookup[lab] = (int(b), low, high)
        next_label += n

    return _regions_from_labels(labels, min_cells=min_cells, band_lookup=band_lookup)


def label_regions_at_plane(domain: np.ndarray, obstruction_m: np.ndarray, platform_elevation_m: float,
                           min_cells: int = 1) -> tuple[np.ndarray, list[Region]]:
    """Label connected platform area available at one horizontal elevation plane.

    A coarse cell is available when it belongs to the analysis domain and its
    maximum obstruction height does not rise above the platform plane.  As the
    plane rises this mask is monotonic: cells can become available but never
    become unavailable.
    """
    usable = domain & np.isfinite(obstruction_m) & (obstruction_m <= float(platform_elevation_m))
    return label_regions(usable, min_cells=min_cells)
