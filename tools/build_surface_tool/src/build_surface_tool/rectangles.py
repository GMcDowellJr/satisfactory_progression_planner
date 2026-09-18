from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class Rectangle:
    width_cells: int
    height_cells: int
    area_cells: int
    rotation_deg: float


def largest_rectangle(binary: np.ndarray) -> Rectangle:
    """Largest axis-aligned all-true rectangle in a boolean matrix, O(rows*cols)."""
    if binary.size == 0:
        return Rectangle(0, 0, 0, 0.0)
    heights = np.zeros(binary.shape[1], dtype=np.int32)
    best = Rectangle(0, 0, 0, 0.0)
    for row in binary:
        heights = np.where(row, heights + 1, 0)
        stack: list[tuple[int, int]] = []
        for i in range(len(heights) + 1):
            h = int(heights[i]) if i < len(heights) else 0
            start = i
            while stack and stack[-1][1] > h:
                idx, hh = stack.pop()
                width = i - idx
                area = width * hh
                if area > best.area_cells:
                    best = Rectangle(width, hh, area, 0.0)
                start = idx
            if not stack or stack[-1][1] < h:
                stack.append((start, h))
    return best


def best_rotated_rectangle(binary: np.ndarray, angles_deg: list[float]) -> Rectangle:
    """Approximate rotated-core search by nearest-neighbor mask rotation."""
    best = Rectangle(0, 0, 0, 0.0)
    for angle in angles_deg:
        if angle % 90 == 0:
            rotated = binary
        else:
            rotated = ndimage.rotate(binary.astype(np.uint8), angle, reshape=True, order=0, mode="constant", cval=0, prefilter=False) > 0
        rect = largest_rectangle(rotated)
        if rect.area_cells > best.area_cells:
            best = Rectangle(rect.width_cells, rect.height_cells, rect.area_cells, float(angle))
    return best
