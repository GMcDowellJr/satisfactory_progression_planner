"""Picker base map: a small hillshade PNG cut from the committed terrain raster.

Greg 2026-10-23 16:14/16:21: the picker plots sockets on a map drawn from game
data (the terrain raster from lukszi/SatisfactoryMCP's generator, kept in the
repo at planning_data/world/spatial/heightmap_build_<build>/), and a small
image (about 1024 px) is fine in the repo. This replaces the plain grid and the
fitted SCIM registration: the raster is georeferenced in meta.json, so the
image is placed exactly, with no fitted transform.

What the image says, and what it doesn't
    land      grey hillshade (NW light) of the 1 m field, sampled at every
              STRIDE-th vertex (vertex-aligned, meta.json `grid.alignment`:
              a pixel IS that vertex, so nothing is averaged or invented)
    water     transparent: every texel waterq marks as water (1 measured,
              2 level-only). The level-only class is the ocean volume boxes,
              whose rectangular edges meet no-data; drawing both transparent
              over the page's sea colour hides that seam
    no-data   transparent (open ocean past the landscape edge, plus the two
              cave-mouth blobs meta.json lists under known_defects: those show
              as sea, a known defect, not a claim that they are water)
Grey levels are quantised to LEVELS steps so the PNG stays small.

The image is grey + alpha so one file serves both themes (the page dims it in
dark mode with a CSS filter). The sidecar JSON gives its placement in the
picker's frame: x = game X = east_m, y = game Y = -north_m, metres.

No new dependency: the PNG is written with zlib + struct (the root dev group is
pytest, numpy, scipy). The raster decode repeats satisfactory_route_tool's
heightfield.decode_i16/decode_u8 (row-delta int16, plain u8), because that
tool is not on the suite's path; the format is meta.json's `files`.

    uv run python tools/site_planner_web/basemap.py            # --check (default)
    uv run python tools/site_planner_web/basemap.py --write
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys
import zlib

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = REPO / "tools" / "site_planner_web" / "precomputed"
BUILD = "502094"
STRIDE = 7          # 7500 vertices -> 1072 px, about 1 px per 7 m
LEVELS = 32         # grey steps on land
NODATA = -32768


def _raster(build: str) -> pathlib.Path:
    return REPO / "planning_data" / "world" / "spatial" / f"heightmap_build_{build}"


def _i16(path: pathlib.Path, h: int, w: int) -> np.ndarray:
    delta = np.frombuffer(zlib.decompress(path.read_bytes()), dtype="<i2")
    if delta.size != h * w:
        raise ValueError(f"{path.name}: raster size does not match meta.json")
    return np.cumsum(delta.reshape(h, w).astype(np.int32), axis=1).astype(np.int16)


def _u8(path: pathlib.Path, h: int, w: int) -> np.ndarray:
    flat = np.frombuffer(zlib.decompress(path.read_bytes()), dtype=np.uint8)
    if flat.size != h * w:
        raise ValueError(f"{path.name}: raster size does not match meta.json")
    return flat.reshape(h, w)


def render(build: str = BUILD, stride: int = STRIDE) -> tuple[np.ndarray, dict]:
    """(grey+alpha pixels, uint8 HxWx2; placement sidecar)."""
    base = _raster(build)
    meta = json.loads((base / "meta.json").read_text(encoding="utf-8"))
    g = meta["grid"]
    h, w, step_m = int(g["height"]), int(g["width"]), float(g["spacing_cm"]) / 100.0
    z = _i16(base / "height.i16.z", h, w)[::stride, ::stride]
    wq = _u8(base / "waterq.u8.z", h, w)[::stride, ::stride]
    land = (z != NODATA) & (wq == 0)

    zm = z.astype(np.float64) / 10.0
    zm[z == NODATA] = 0.0
    px = stride * step_m
    dzdy, dzdx = np.gradient(zm, px)
    # NW light at 45 deg; y grows south in the grid (meta.json `grid.axes`)
    az, alt = np.radians(315.0), np.radians(45.0)
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(-dzdx, dzdy)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    lo, hi = np.percentile(zm[land], [2, 98])
    rel = np.clip((zm - lo) / (hi - lo), 0.0, 1.0)
    tone = np.clip(0.6 * np.clip(shade, 0.0, 1.0) + 0.4 * rel, 0.0, 1.0)
    q = np.round(tone * (LEVELS - 1)) / (LEVELS - 1)
    grey = (90 + q * 150).astype(np.uint8)

    px_img = np.zeros(z.shape + (2,), np.uint8)
    px_img[..., 0] = np.where(land, grey, 0)
    px_img[..., 1] = np.where(land, 255, 0)

    x0 = float(g["x0_cm"]) / 100.0
    y0 = float(g["y0_cm"]) / 100.0
    rows, cols = z.shape
    side = {
        "schema": "basemap/1",
        "image": f"basemap_{build}.png",
        "source": f"planning_data/world/spatial/heightmap_build_{build}",
        "generator": "tools/site_planner_web/basemap.py",
        "stride_vertices": stride, "pixel_m": px, "levels": LEVELS,
        "frame": "x = game X = east_m; y = game Y = -north_m (metres)",
        # a pixel is the vertex at its centre, so the image's edge is half a
        # pixel outside the first and last vertex sampled
        "x_m": x0 - px / 2, "y_m": y0 - px / 2,
        "width_m": cols * px, "height_m": rows * px,
        "width_px": cols, "height_px": rows,
        "transparent": "water (waterq 1 and 2) and no-data (incl. two cave-mouth blobs, a known defect)",
    }
    return px_img, side


def png_bytes(px_img: np.ndarray) -> bytes:
    """Grey+alpha 8-bit PNG, filter 0 on every row."""
    h, w, _ = px_img.shape
    raw = b"".join(b"\x00" + px_img[r].tobytes() for r in range(h))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 4, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def png_pixels(data: bytes) -> np.ndarray:
    """Decode a PNG written by png_bytes (grey+alpha, filter 0 only): the test
    compares pixels, not bytes, because zlib's output may differ by version."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, w, h = 8, b"", 0, 0
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
            if (depth, ctype) != (8, 4):
                raise ValueError("only 8-bit grey+alpha is read here")
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    rows = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, 1 + 2 * w)
    if rows[:, 0].any():
        raise ValueError("only filter 0 is read here")
    return rows[:, 1:].reshape(h, w, 2)


def same(a: np.ndarray, b: np.ndarray) -> bool:
    """Alpha exactly equal; grey within one quantisation step. Floating point
    in the hillshade can differ by an ulp between numpy builds, and that can
    tip a pixel across a step boundary; it cannot move land or water."""
    if a.shape != b.shape or not np.array_equal(a[..., 1], b[..., 1]):
        return False
    step = 150.0 / (LEVELS - 1)
    return bool(np.abs(a[..., 0].astype(int) - b[..., 0].astype(int)).max() <= np.ceil(step))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="write the PNG and sidecar")
    args = ap.parse_args(argv)
    px_img, side = render()
    png, js = OUT / side["image"], OUT / f"basemap_{BUILD}.json"
    text = json.dumps(side, indent=2) + "\n"
    if args.write:
        png.write_bytes(png_bytes(px_img))
        js.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {png.name} ({png.stat().st_size} bytes) and {js.name}")
        return 0
    ok = png.exists() and js.exists() and js.read_text(encoding="utf-8") == text \
        and same(png_pixels(png.read_bytes()), px_img)
    print("basemap in sync" if ok else "basemap drift: re-run with --write")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
