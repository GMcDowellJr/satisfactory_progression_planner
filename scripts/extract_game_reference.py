#!/usr/bin/env python3
"""Derive reference tables from the pinned game Docs snapshot.

The snapshot README lists nine tables as "Derived from this snapshot" and
`tools/check_game_docs_provenance.py` names the same nine in `DERIVED`, but
neither the README nor the checker regenerates them: the provenance checker
only hashes the snapshot. Before this script the derivation existed nowhere in
the repo, so the README's reproducibility claim -- "the reference layer is
reproducible from the repo, on a machine that has never had the game
installed" -- was not actually true of the repo.

This script does NOT re-derive those nine. It emits four NEW tables that the
reference layer has never carried, and it verifies its own recipe filter
against the existing `recipes.csv` so that the filter recorded here is
demonstrably the filter that produced the committed data.

THE FILTER, recovered and verified
----------------------------------
`FGRecipe` holds 872 classes. The committed `recipes.csv` holds 291. The rule
that reproduces that set exactly, id for id, is:

    keep a recipe when mProducedIn names at least one Build_* class

549 recipes name `BP_BuildGun` instead. No recipe names both, so the two sets
are disjoint and the Build Gun set is precisely what the existing filter drops.
Those 549 are the building construction costs -- the outflow half of the
storage model, and the source for machine/foundation/belt/pole bills.

Emitted tables
--------------
    building_recipes.csv      one row per Build Gun recipe
    building_recipe_io.csv    its ingredients, as TOTALS not rates
    power_buildings.csv       generators, with production and supplemental
    generator_fuels.csv       burn rate, supplemental rate, byproduct rate

Building costs are totals, never rates: a building is built once. `recipe_io.csv`
carries `rate_per_min` because a production recipe runs continuously; the
Build Gun's `mManufactoringDuration` is 1.0 on every row and means nothing, so
no rate column is emitted here. Reading one would be a category error.

Fuel arithmetic, each verified against a known in-game figure
-------------------------------------------------------------
    burn_rate_per_min     = mPowerProduction / energy_mj_per_unit * 60
    supplemental_per_min  = mPowerProduction * mSupplementalToPowerRatio * 60 / 1000
    byproduct_per_min     = burn_rate_per_min * mByproductAmount

`mEnergyValue` is MJ per item for solids and MJ per mL for liquids and gases,
so fluid energy is scaled by 1000 to reach MJ per m3 and the emitted rate is in
m3/min. Checks in --verify.

Usage
    python scripts/extract_game_reference.py --verify
    python scripts/extract_game_reference.py --emit
    python scripts/extract_game_reference.py --emit --out-dir /tmp/staging
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = REPO / "planning_data" / "game" / "source_snapshots"
REFERENCE = REPO / "planning_data" / "game" / "reference"

GAME_BUILD_ID = "docs_a81d250e96aa"
SOURCE_ID = "local_game_docs_en_us"
PINNED_SHA = "a81d250e96aa13db3c0bf8c332c199ad930b2f15323e2c1a069afa4c07f971bb"

#: mProducedIn entries are paths; the class token repeats as `/Name.Name_C`.
PRODUCER_RE = re.compile(r"/([A-Za-z0-9_]+)\.\1_C")

#: mIngredients / mProduct are UE struct literals, not JSON.
INGREDIENT_RE = re.compile(
    r'ItemClass\s*=\s*"[^"]*?/([A-Za-z0-9_]+)\.\1_C[^"]*?"\s*,\s*Amount\s*=\s*(-?\d+)'
)

#: FGItemDescriptor.mForm -> (display unit, divisor from the raw amount)
FORM_UNITS = {
    "RF_SOLID": ("items", 1),
    "RF_LIQUID": ("m3", 1000),
    "RF_GAS": ("m3", 1000),
}

#: Cost inputs that are equipment rather than parts, so they are absent from
#: items.csv by construction. Allowed by the join check and named here rather
#: than silently dropped: the Portable Miner is an ingredient of Miner Mk.1
#: (1), Mk.2 (2), Mk.3 (3) and the Drone (1), so every miner's construction
#: bill is only partly resolvable against the current reference layer. It has
#: its own workshop recipe, which this filter does not keep.
NON_PART_COST_ITEMS = {"BP_ItemDescriptorPortableMiner_C"}

GENERATOR_CLASSES = (
    "FGBuildableGeneratorFuel",
    "FGBuildableGeneratorNuclear",
    "FGBuildableGeneratorGeoThermal",
)

#: (generator, fuel, field, expected) -- in-game figures the arithmetic must hit.
FUEL_CHECKS = [
    ("Build_GeneratorCoal_C", "Desc_Coal_C", "burn", 15.0),
    ("Build_GeneratorCoal_C", "Desc_CompactedCoal_C", "burn", 7.142857),
    ("Build_GeneratorCoal_C", "Desc_PetroleumCoke_C", "burn", 25.0),
    ("Build_GeneratorCoal_C", "Desc_Coal_C", "supplemental", 45.0),
    ("Build_GeneratorBiomass_Automated_C", "Desc_Leaves_C", "burn", 120.0),
    ("Build_GeneratorBiomass_Automated_C", "Desc_Biofuel_C", "burn", 4.0),
    ("Build_GeneratorBiomass_Automated_C", "Desc_GenericBiomass_C", "burn", 10.0),
    ("Build_GeneratorFuel_C", "Desc_LiquidFuel_C", "burn", 20.0),
    ("Build_GeneratorNuclear_C", "Desc_NuclearFuelRod_C", "burn", 0.2),
    ("Build_GeneratorNuclear_C", "Desc_NuclearFuelRod_C", "supplemental", 240.0),
    ("Build_GeneratorNuclear_C", "Desc_NuclearFuelRod_C", "byproduct", 10.0),
]

#: Building costs that must appear verbatim. The three after the Constructor
#: are the inputs section 8.2's geometric overhead rule needs -- foundation,
#: trunk belt, power pole -- so this check also asserts that the rule's data
#: dependency is actually satisfied by what this script emits.
BUILDING_CHECKS = [
    ("Recipe_ConstructorMk1_C", {"Desc_IronPlateReinforced_C": 2, "Desc_Cable_C": 8}),
    # Pinned FROM the snapshot, not an independent figure: an initial
    # expectation of 4 Concrete was recollection and the data says 5, for the
    # 1 m, 2 m and 4 m foundations alike. Kept as a regression pin so a future
    # extraction change that moves it fails loudly.
    ("Recipe_Foundation_Concrete_8x4_C", {"Desc_Cement_C": 5}),
    ("Recipe_ConveyorBeltMk1_C", {"Desc_IronPlate_C": 1}),
    ("Recipe_PowerPoleMk1_C",
     {"Desc_Wire_C": 3, "Desc_IronRod_C": 1, "Desc_Cement_C": 1}),
]


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------

def find_snapshot() -> pathlib.Path:
    path = SNAPSHOT_DIR / GAME_BUILD_ID / "en-US.json"
    if not path.is_file():
        sys.exit(f"snapshot not found: {path}")
    return path


def load_docs(path: pathlib.Path) -> dict[str, list[dict]]:
    """Return {short native class name: [class dicts]}.

    The snapshot is UTF-16 LE with a BOM and must not be re-encoded; the sha256
    is the pin every derived table's `game_build_id` refers to.
    """
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != PINNED_SHA:
        sys.exit(
            f"snapshot sha256 {digest} does not match the pin {PINNED_SHA}.\n"
            "Run tools/check_game_docs_provenance.py before deriving anything."
        )
    docs = json.loads(raw.decode("utf-16"))
    out: dict[str, list[dict]] = {}
    for entry in docs:
        short = entry["NativeClass"].split(".")[-1].rstrip("'")
        out.setdefault(short, []).extend(entry["Classes"])
    return out


def producers(recipe: dict) -> list[str]:
    return PRODUCER_RE.findall(recipe.get("mProducedIn", "") or "")


def machine_producers(recipe: dict) -> list[str]:
    return [p for p in producers(recipe) if p.startswith("Build_")]


def is_build_gun(recipe: dict) -> bool:
    return "BP_BuildGun" in producers(recipe)


def parse_items(field: str) -> list[tuple[str, int]]:
    """(item_id, raw amount) pairs.

    The capture group is the repeated path token, which excludes the trailing
    `_C` because the pattern consumes it as a literal. Item ids in every other
    reference table carry it, so it is restored here -- without it nothing
    joins to items.csv.
    """
    return [
        (f"{m.group(1)}_C", int(m.group(2)))
        for m in INGREDIENT_RE.finditer(field or "")
    ]


def item_index(by: dict[str, list[dict]]) -> dict[str, dict]:
    """Every descriptor family that can name an item, flattened by ClassName."""
    idx: dict[str, dict] = {}
    for classes in by.values():
        for cls in classes:
            name = cls.get("ClassName", "")
            # Parts are Desc_*; equipment that can appear as a build cost
            # (the Portable Miner) is BP_ItemDescriptor* / BP_Equipment*.
            if name.startswith(("Desc_", "BP_ItemDescriptor", "BP_Equipment")):
                idx.setdefault(name, cls)
    return idx


def unit_of(cls: dict | None) -> tuple[str, int]:
    return FORM_UNITS.get((cls or {}).get("mForm", "RF_SOLID"), ("items", 1))


def fnum(cls: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(cls.get(key, default))
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------
# derivation
# --------------------------------------------------------------------------

def building_rows(by, items):
    """Build Gun recipes and their ingredient totals."""
    heads, io = [], []
    for r in by["FGRecipe"]:
        if not is_build_gun(r):
            continue
        product = parse_items(r.get("mProduct", ""))
        target, amount = (product[0] if product else ("", 0))
        heads.append({
            "recipe_id": r["ClassName"],
            "display_name": r.get("mDisplayName", ""),
            "building_class": target,
            "building_display_name": (items.get(target) or {}).get("mDisplayName", ""),
            "produced_amount": amount,
            "ingredient_count": len(parse_items(r.get("mIngredients", ""))),
            "gameplay_tags": r.get("mGameplayTags", ""),
            "full_name": r.get("FullName", ""),
            "game_build_id": GAME_BUILD_ID,
            "source_id": SOURCE_ID,
        })
        for item_id, raw in parse_items(r.get("mIngredients", "")):
            unit, divisor = unit_of(items.get(item_id))
            io.append({
                "recipe_id": r["ClassName"],
                "direction": "input",
                "item_id": item_id,
                "item_name": (items.get(item_id) or {}).get("mDisplayName", ""),
                "amount": raw / divisor,
                "amount_raw": raw,
                "unit": unit,
                "game_build_id": GAME_BUILD_ID,
            })
    heads.sort(key=lambda d: d["recipe_id"])
    io.sort(key=lambda d: (d["recipe_id"], d["item_id"]))
    return heads, io


def generator_rows(by, items, today):
    """Generators and their per-fuel rates."""
    heads, fuels = [], []
    for native in GENERATOR_CLASSES:
        for g in by.get(native, []):
            mw = fnum(g, "mPowerProduction")
            variable = "mVariablePowerProductionFactor" in g and mw == 0.0
            heads.append({
                "generator_class": g["ClassName"],
                "display_name": g.get("mDisplayName", ""),
                "native_class": native,
                "power_model": "variable" if variable else "fixed",
                "power_production_mw": "" if variable else mw,
                "variable_power_factor": (
                    fnum(g, "mVariablePowerProductionFactor") if variable else ""
                ),
                "requires_supplemental": g.get("mRequiresSupplementalResource", "False"),
                "supplemental_to_power_ratio": fnum(g, "mSupplementalToPowerRatio"),
                "fuel_load_amount": g.get("mFuelLoadAmount", ""),
                "game_build_id": GAME_BUILD_ID,
                "source_id": SOURCE_ID,
                "verified_on": today,
            })
            if variable:
                # Geothermal output is a function of node purity, which is a
                # world-placement fact. Emitting a rate here would invent one.
                continue
            for f in (g.get("mFuel") or []):
                fuel_id = f.get("mFuelClass", "")
                fuel_cls = items.get(fuel_id)
                unit, divisor = unit_of(fuel_cls)
                energy_raw = fnum(fuel_cls or {}, "mEnergyValue")
                if energy_raw <= 0:
                    continue
                energy = energy_raw * divisor          # MJ per display unit
                burn = mw / energy * 60.0              # display units per minute

                supp_id = f.get("mSupplementalResourceClass", "") or ""
                supp_unit, _ = unit_of(items.get(supp_id)) if supp_id else ("", 1)
                supp_rate = (
                    mw * fnum(g, "mSupplementalToPowerRatio") * 60.0 / 1000.0
                    if supp_id else ""
                )

                by_id = f.get("mByproduct", "") or ""
                try:
                    by_amt = float(f.get("mByproductAmount") or 0)
                except ValueError:
                    by_amt = 0.0
                fuels.append({
                    "generator_class": g["ClassName"],
                    "fuel_item_id": fuel_id,
                    "fuel_item_name": (fuel_cls or {}).get("mDisplayName", ""),
                    "fuel_unit": unit,
                    "energy_mj_per_unit": round(energy, 6),
                    "burn_rate_per_min": round(burn, 6),
                    "power_production_mw": mw,
                    "supplemental_item_id": supp_id,
                    "supplemental_rate_per_min": (
                        round(supp_rate, 6) if supp_id else ""
                    ),
                    "supplemental_unit": supp_unit,
                    "byproduct_item_id": by_id,
                    "byproduct_amount_per_fuel": by_amt if by_id else "",
                    "byproduct_rate_per_min": (
                        round(burn * by_amt, 6) if by_id else ""
                    ),
                    "game_build_id": GAME_BUILD_ID,
                    "source_id": SOURCE_ID,
                    "verified_on": today,
                })
    heads.sort(key=lambda d: d["generator_class"])
    fuels.sort(key=lambda d: (d["generator_class"], d["fuel_item_id"]))
    return heads, fuels


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

def verify(by, items) -> int:
    failures = []

    kept = {r["ClassName"] for r in by["FGRecipe"] if machine_producers(r)}
    committed_path = REFERENCE / "recipes.csv"
    if committed_path.is_file():
        with committed_path.open(encoding="utf-8-sig", newline="") as fh:
            committed = {row["recipe_id"] for row in csv.DictReader(fh)}
        if kept == committed:
            print(f"OK    recipe filter reproduces recipes.csv exactly ({len(kept)} rows)")
        else:
            failures.append(
                f"recipe filter differs: +{sorted(kept - committed)[:5]} "
                f"-{sorted(committed - kept)[:5]}"
            )
    else:
        print(f"SKIP  {committed_path} absent; filter not cross-checked")

    bg = [r for r in by["FGRecipe"] if is_build_gun(r)]
    overlap = [r["ClassName"] for r in bg if machine_producers(r)]
    print(f"OK    {len(bg)} Build Gun recipes, {len(overlap)} overlapping the kept set")
    if overlap:
        failures.append(f"Build Gun and machine sets overlap: {overlap[:5]}")

    index = {r["ClassName"]: r for r in bg}
    for recipe_id, expected in BUILDING_CHECKS:
        r = index.get(recipe_id)
        if r is None:
            failures.append(f"{recipe_id} missing from the Build Gun set")
            continue
        if expected is None:
            continue
        got = dict(parse_items(r.get("mIngredients", "")))
        if got != expected:
            failures.append(f"{recipe_id} cost {got} != expected {expected}")
        else:
            print(f"OK    {recipe_id} = {got}")

    # Every emitted item id must join to items.csv, or the cost bill is
    # unresolvable against the rest of the reference layer.
    items_path = REFERENCE / "items.csv"
    if items_path.is_file():
        with items_path.open(encoding="utf-8-sig", newline="") as fh:
            known = {row["item_id"] for row in csv.DictReader(fh)}
        _, io = building_rows(by, items)
        orphans = sorted({r["item_id"] for r in io} - known - NON_PART_COST_ITEMS)
        if orphans:
            failures.append(f"{len(orphans)} item ids do not join to items.csv: {orphans[:8]}")
        else:
            total = len({r["item_id"] for r in io})
            print(f"OK    {total - len(NON_PART_COST_ITEMS)} of {total} cost item ids "
                  f"join to items.csv; {len(NON_PART_COST_ITEMS)} allowed non-part")

    _, fuels = generator_rows(by, items, "verify")
    lookup = {(f["generator_class"], f["fuel_item_id"]): f for f in fuels}
    for gen, fuel, field, expected in FUEL_CHECKS:
        row = lookup.get((gen, fuel))
        if row is None:
            failures.append(f"{gen}/{fuel} not derived")
            continue
        key = {
            "burn": "burn_rate_per_min",
            "supplemental": "supplemental_rate_per_min",
            "byproduct": "byproduct_rate_per_min",
        }[field]
        got = float(row[key])
        if abs(got - expected) > 1e-4:
            failures.append(f"{gen}/{fuel} {field} = {got}, expected {expected}")
        else:
            print(f"OK    {gen.removeprefix('Build_Generator'):24} {fuel:24} {field:12} {got:g}")

    if failures:
        print("\nFAILED")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nall checks passed")
    return 0


# --------------------------------------------------------------------------
# emit
# --------------------------------------------------------------------------

def write_csv(path: pathlib.Path, rows: list[dict]) -> None:
    if not rows:
        print(f"SKIP  {path.name}: no rows")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path}  ({len(rows)} rows)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verify", action="store_true",
                    help="check the filter and the fuel arithmetic; write nothing")
    ap.add_argument("--emit", action="store_true", help="write the four new tables")
    ap.add_argument("--out-dir", type=pathlib.Path, default=REFERENCE,
                    help="destination directory (default: the reference layer)")
    args = ap.parse_args()
    if not (args.verify or args.emit):
        ap.error("pass --verify or --emit")

    by = load_docs(find_snapshot())
    items = item_index(by)
    today = datetime.date.today().isoformat()

    if args.verify:
        rc = verify(by, items)
        if rc or not args.emit:
            return rc

    heads, io = building_rows(by, items)
    gens, fuels = generator_rows(by, items, today)
    write_csv(args.out_dir / "building_recipes.csv", heads)
    write_csv(args.out_dir / "building_recipe_io.csv", io)
    write_csv(args.out_dir / "power_buildings.csv", gens)
    write_csv(args.out_dir / "generator_fuels.csv", fuels)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
