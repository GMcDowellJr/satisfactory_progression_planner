from __future__ import annotations

import zlib
import numpy as np

NODATA = -32768


def decode_i16(blob: bytes, height: int, width: int) -> np.ndarray:
    """Decode the repo's row-delta + zlib int16 raster format."""
    delta = np.frombuffer(zlib.decompress(blob), dtype="<i2")
    if delta.size != height * width:
        raise ValueError("raster size does not match meta.json")
    running = np.cumsum(delta.reshape(height, width).astype(np.int32), axis=1)
    return running.astype(np.int16)


def decode_u8(blob: bytes, height: int, width: int) -> np.ndarray:
    """Decode the repo's plain-zlib uint8 raster format."""
    flat = np.frombuffer(zlib.decompress(blob), dtype=np.uint8)
    if flat.size != height * width:
        raise ValueError("raster size does not match meta.json")
    return flat.reshape(height, width)
