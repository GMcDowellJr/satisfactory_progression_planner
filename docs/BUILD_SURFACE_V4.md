# Build Surface V4 — Local Multi-Scale Relief

## Purpose

V4 makes the primary build-surface question local rather than global:

> Where can a factory-sized footprint sit while the terrain inside that footprint remains within an allowed vertical relief?

This separates three independent judgments: horizontal analysis resolution, factory footprint scale, and tolerated terrain relief.

## Size-scale windows

The current calibration anchors are unchanged:

| Class | Reference footprint |
|---|---|
| Small | 8×8 foundations / 64×64 m |
| Medium | 24×32 / 192×256 m |
| Large | 48×64 / 384×512 m |
| Very Large | 80×80 / 640×640 m |

For each candidate center and class, the terrain high-to-low difference across that whole reference footprint is measured. A center qualifies when the difference is less than or equal to the active local-relief tolerance.

## What the region means

The irregular output polygon/raster is a **placement-center zone**. It answers: "if the center of this class-sized factory footprint is here, does the whole footprint satisfy the relief policy?"

It does not mean the irregular shape itself is the factory footprint. `build_surface_rectangles.csv` supplies the concrete rectangles that demonstrate qualification.

Each region retains up to three low-relief, mostly non-overlapping rectangle candidates. The viewer shows the primary rectangle for all visible regions and all retained candidates for the selected region.

## Independent parameters

- Smaller horizontal resolution gives finer boundaries and more small branches/offshoots.
- Smaller relief tolerance fragments suitability into fewer/smaller placement zones.
- Larger relief tolerance expands and merges suitability.
- Larger footprint class makes qualification harder because relief is evaluated over a larger physical area.

These effects are intentionally independent.

## Build 502094 calibration evidence

At 16 m horizontal resolution, the first default run produced:

| Relief tolerance | Small regions | Medium | Large | Very Large |
|---:|---:|---:|---:|---:|
| 2 m | 96 | 0 | 0 | 0 |
| 4 m | 213 | 0 | 0 | 0 |
| 8 m | 423 | 0 | 0 | 0 |
| 16 m | 436 | 12 | 0 | 0 |
| 32 m | 355 | 25 | 5 | 0 |
| 64 m | 235 | 49 | 9 | 5 |

These are calibration results, not final claims about ideal thresholds. The important structural behavior is that broader footprint classes appear as the allowed local relief increases.

## Relationship to V3

V3 remains useful for a different question: "at what absolute elevation can a flat platform clear terrain?" It is intentionally retained as an alternate analysis, not deleted or folded into V4.
