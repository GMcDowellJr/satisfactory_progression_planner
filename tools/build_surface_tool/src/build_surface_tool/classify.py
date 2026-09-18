from __future__ import annotations


def classify_size(short_span_foundations: float, area_m2: float, policy: dict) -> str:
    classes = policy["size_classes"]
    order = ["small", "medium", "large", "very_large"]
    result = "below_small"
    for name in order:
        cfg = classes[name]
        if short_span_foundations >= float(cfg["minimum_short_span_foundations"]) and area_m2 >= float(cfg["reference_core_area_m2"]):
            result = name
    return result


def classify_shape(width: float, height: float, policy: dict) -> tuple[str, float]:
    short = min(width, height)
    long = max(width, height)
    if short <= 0:
        return "none", float("inf")
    ratio = long / short
    shapes = policy["shape_classes"]
    if ratio <= float(shapes["good"]["max_aspect_ratio"]):
        return "good", ratio
    if ratio <= float(shapes["workable"]["max_aspect_ratio"]):
        return "workable", ratio
    if ratio <= float(shapes["linear"]["max_aspect_ratio"]):
        return "linear", ratio
    return "poor", ratio
