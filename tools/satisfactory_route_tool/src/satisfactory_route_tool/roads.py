from __future__ import annotations

import json
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

from .heightfield import WorkingField


def _long_run(mask_1d: np.ndarray, min_count: int):
    idx = np.where(mask_1d >= min_count)[0]
    if len(idx) == 0:
        return None
    # choose longest contiguous run
    runs=[]
    st=prev=idx[0]
    for x in idx[1:]:
        if x == prev+1:
            prev=x
        else:
            runs.append((st,prev))
            st=prev=x
    runs.append((st,prev))
    return max(runs, key=lambda ab: ab[1]-ab[0])


def detect_map_crop(rgb: np.ndarray):
    """Find the large colorful square map panel, excluding gray SCIM UI."""
    chroma = rgb.max(axis=2).astype(int) - rgb.min(axis=2).astype(int)
    dark = rgb.mean(axis=2) < 35
    content = (chroma > 12) | dark
    row_counts = content.sum(axis=1)
    col_counts = content.sum(axis=0)
    rr = _long_run(row_counts, max(80, int(rgb.shape[1]*0.25)))
    cc = _long_run(col_counts, max(80, int(rgb.shape[0]*0.25)))
    if rr is None or cc is None:
        raise ValueError("could not automatically detect map crop; pass --crop")
    y0,y1 = rr
    x0,x1 = cc
    return x0,y0,x1+1,y1+1


def purple_mask(rgb: np.ndarray):
    r=rgb[:,:,0].astype(np.int16)
    g=rgb[:,:,1].astype(np.int16)
    b=rgb[:,:,2].astype(np.int16)
    return (r>105)&(b>100)&(g<115)&((r+b-2*g)>115)


def dilate(mask: np.ndarray, radius_cells: int):
    if radius_cells <= 0:
        return mask.copy()
    out=mask.copy()
    for _ in range(radius_cells):
        p=np.pad(out,1)
        acc=np.zeros_like(out,dtype=bool)
        for dr in range(3):
            for dc in range(3):
                acc |= p[dr:dr+out.shape[0], dc:dc+out.shape[1]]
        out=acc
    return out


def extract_road_prior(image_path: str, field: WorkingField, out_dir: str, crop=None, band_m=25.0):
    img=np.asarray(Image.open(image_path).convert("RGB"))
    if crop is None:
        crop=detect_map_crop(img)
    x0,y0,x1,y1=map(int,crop)
    map_img=img[y0:y1,x0:x1]
    pm=purple_mask(map_img)

    # Resize screenshot mask directly to the working field shape. Both represent the full,
    # north-up square map extent. Nearest-neighbor preserves the coarse line topology.
    pil=Image.fromarray((pm*255).astype(np.uint8))
    resized=np.asarray(pil.resize((field.shape[1],field.shape[0]),resample=Image.Resampling.NEAREST))>0
    band=dilate(resized,max(1,int(round(band_m/field.step_m))))

    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(
        out/"scim_road_prior_5m.npz",
        road=resized.astype(np.uint8),
        road_band=band.astype(np.uint8),
        step_m=np.array([field.step_m],dtype=np.float32),
        east0_m=np.array([field.east0_m],dtype=np.float64),
        north0_m=np.array([field.north0_m],dtype=np.float64),
    )
    meta={
        "image":str(image_path),
        "crop_px":[x0,y0,x1,y1],
        "source":"visible SCIM Roads overlay screenshot",
        "interpretation":"coarse cartographic road prior; not underlying SCIM source geometry",
        "working_step_m":field.step_m,
        "road_band_m":band_m,
        "road_cells":int(resized.sum()),
        "road_band_cells":int(band.sum()),
    }
    (out/"scim_road_prior_meta.json").write_text(json.dumps(meta,indent=2),encoding="utf-8", newline="\n")

    plt.figure(figsize=(9,9))
    plt.imshow(map_img)
    plt.imshow(pm, alpha=0.35)
    plt.axis("off")
    plt.title("SCIM visible-road segmentation")
    plt.tight_layout()
    plt.savefig(out/"scim_road_segmentation.png",dpi=160)
    plt.close()
    return meta


def load_road_prior(path: str, expected_shape=None):
    d=np.load(path)
    road=d["road"].astype(bool)
    band=d["road_band"].astype(bool)
    if expected_shape is not None and road.shape != tuple(expected_shape):
        raise ValueError(f"road prior shape {road.shape} != terrain working shape {expected_shape}")
    return road,band
