from __future__ import annotations

import json
from pathlib import Path
from importlib.resources import files


def default_profiles():
    # Package source tree fallback.
    p = Path(__file__).resolve().parents[2] / "movement_profiles.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    # Installed wheel fallback: embedded defaults.
    return {
        "foot":{"road_factor":1.0,"road_band_factor":1.0,"grade_soft_start":0.75,"grade_hard_block":4.0,"grade_penalty":1.5,"shallow_water_penalty":5.0,"deep_water_depth_m":4.0,"deep_water_penalty":20.0,"cliff_penalty":2.0,"unknown_penalty":3.0},
        "tractor":{"road_factor":0.38,"road_band_factor":0.62,"grade_soft_start":0.35,"grade_hard_block":1.0,"grade_penalty":14.0,"shallow_water_penalty":10.0,"deep_water_depth_m":3.0,"deep_water_penalty":90.0,"cliff_penalty":15.0,"unknown_penalty":8.0},
        "truck":{"road_factor":0.34,"road_band_factor":0.58,"grade_soft_start":0.30,"grade_hard_block":1.0,"grade_penalty":16.0,"shallow_water_penalty":12.0,"deep_water_depth_m":3.0,"deep_water_penalty":100.0,"cliff_penalty":18.0,"unknown_penalty":10.0},
        "rail":{"road_factor":0.78,"road_band_factor":0.86,"grade_soft_start":0.02,"grade_hard_block":0.08,"grade_penalty":80.0,"shallow_water_penalty":35.0,"deep_water_depth_m":0.5,"deep_water_penalty":120.0,"cliff_penalty":35.0,"unknown_penalty":20.0},
    }


def load_profile(mode: str, path: str | None = None):
    data = json.loads(Path(path).read_text(encoding="utf-8")) if path else default_profiles()
    if mode not in data:
        raise KeyError(f"unknown mode {mode!r}; choose from {sorted(data)}")
    return data[mode]
