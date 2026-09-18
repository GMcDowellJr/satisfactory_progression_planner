from __future__ import annotations
from pathlib import Path
from .io import load_json
from .local_relief import analyze_local_relief
from .plane_fit import analyze_plane_fit
from .sweep import analyze as analyze_elevation_sweep


def analyze(repo_root: Path, world_manifest: Path, policy_path: Path, output_dir: Path,
            resolutions: list[float] | None = None,
            relief_tolerances_m: list[float] | None = None,
            size_classes: list[str] | None = None,
            vertical_step_m: float | None = None,
            plane_min_m: float | None = None,
            plane_max_m: float | None = None,
            clearance_tolerances_m: list[float] | None = None):
    policy = load_json(policy_path)
    model = policy.get("analysis_model")
    if model == "horizontal_plane_fit":
        return analyze_plane_fit(repo_root, world_manifest, policy_path, output_dir,
                                 resolutions=resolutions,
                                 clearance_tolerances_m=clearance_tolerances_m,
                                 size_classes=size_classes)
    if model == "local_multiscale_relief":
        return analyze_local_relief(repo_root, world_manifest, policy_path, output_dir,
                                    resolutions=resolutions,
                                    relief_tolerances_m=relief_tolerances_m,
                                    size_classes=size_classes)
    if model == "elevation_sweep":
        return analyze_elevation_sweep(repo_root, world_manifest, policy_path, output_dir,
                                       resolutions=resolutions,
                                       vertical_step_m=vertical_step_m,
                                       plane_min_m=plane_min_m,
                                       plane_max_m=plane_max_m)
    raise ValueError(f"unsupported build-surface analysis_model: {model!r}")
