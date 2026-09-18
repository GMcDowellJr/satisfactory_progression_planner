# PHM steel-deck calibration fixture — build 502094

This fixture was extracted from the supplied `PHM_autosave_0.sav` and is used to calibrate the build-surface analysis against a known in-game flat foundation deck.

Selection: the largest edge-connected component of standard 8×4 foundations whose transform origin is Z = -5 m. It contains 221 foundations on one flat plane. Assuming the standard 4 m foundation transform is centered vertically, the deck top is Z = -3 m.

The fixture intentionally does **not** commit the source `.sav`; it commits only the derived foundation transforms and terrain comparison needed for regression/calibration.

At foundation centers where the 502094 heightfield provenance is landscape/fill, the deck top is about 3.0 m above terrain at the median and 3.8 m at p95. The known-ground relief across those centers is about 2.3 m. 42 centers coincide with cliff provenance; those are treated as vertical-layer ambiguity because the 2.5D heightfield can be showing the natural bridge/overhead rock rather than the floor under it.

Recreate from a local save:

```cmd
python scripts\extract_foundation_fixture.py PHM_autosave_0.sav --z-m -5 --output-dir planning_data\analysis\calibration\PHM_steel_deck_502094
python scripts\calibrate_foundation_fixture.py planning_data\analysis\calibration\PHM_steel_deck_502094\foundations.csv
```
