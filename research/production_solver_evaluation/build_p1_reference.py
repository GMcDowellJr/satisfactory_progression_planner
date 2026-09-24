"""P1: canonical production-building reference + variable-power extension.

Primary source: the game's shipped Docs (en-US.json), sha256-pinned in game_builds.csv.
Emits solver-safe tables keyed by the SAME producer_class that recipe_producers.csv uses.
Does not modify any existing reference file.
"""
import json, re, csv, hashlib, os

DOCS = "/mnt/user-data/uploads/Docs/en-US.json"
OUT  = "/mnt/user-data/outputs/planning_data/game/reference"
os.makedirs(OUT, exist_ok=True)

raw = open(DOCS, "rb").read()
SHA = hashlib.sha256(raw).hexdigest()
BUILD_ID = "docs_" + SHA[:12]
SOURCE_ID = "local_game_docs_en_us"
VERIFIED = "2026-09-18"
d = json.loads(raw.decode("utf-16"))

def classes(suffix):
    for e in d:
        if e["NativeClass"].endswith(suffix):
            for c in e["Classes"]:
                yield c

FIXED_NC = "FGBuildableManufacturer'"
VAR_NC   = "FGBuildableManufacturerVariablePower'"
EXTRACT  = ["FGBuildableResourceExtractor'", "FGBuildableWaterPump'", "FGBuildableFrackingExtractor'"]

producers = {}
for model, suffix in (("fixed", FIXED_NC), ("variable", VAR_NC)):
    for c in classes(suffix):
        producers[c["ClassName"]] = {
            "producer_class": c["ClassName"],
            "display_name": c["mDisplayName"],
            "native_class": suffix.rstrip("'"),
            "power_model": model,
            "base_power_mw": f'{float(c["mPowerConsumption"]):g}',
            "power_exponent": f'{float(c["mPowerConsumptionExponent"]):.6f}',
            "game_build_id": BUILD_ID, "source_id": SOURCE_ID, "verified_on": VERIFIED,
        }

CLS = re.compile(r"\.(\w+_C)")
vp_rows, recipe_producer = [], {}
for c in classes("FGRecipe'"):
    hit = [p for p in CLS.findall(c.get("mProducedIn", "") or "") if p in producers]
    if not hit:
        continue
    assert len(hit) == 1, (c["ClassName"], hit)
    pc = hit[0]
    recipe_producer[c["ClassName"]] = pc
    # Variable power is a property of the PRODUCER's native class, not of the recipe
    # carrying the fields. Fixed-power producers ignore them; see NOTES.
    if producers[pc]["power_model"] != "variable":
        continue
    const = float(c.get("mVariablePowerConsumptionConstant", 0) or 0)
    factor = float(c.get("mVariablePowerConsumptionFactor", 0) or 0)
    vp_rows.append({
        "recipe_id": c["ClassName"], "producer_class": pc,
        "vp_const_mw": f"{const:g}", "vp_factor_mw": f"{factor:g}",
        "power_min_mw": f"{const:g}", "power_max_mw": f"{const + factor:g}",
        "power_mean_mw": f"{const + factor / 2:g}",
        "game_build_id": BUILD_ID, "source_id": SOURCE_ID, "verified_on": VERIFIED,
    })

extraction = []
for suffix in EXTRACT:
    for c in classes(suffix):
        extraction.append({
            "extractor_class": c["ClassName"], "display_name": c["mDisplayName"],
            "native_class": suffix.rstrip("'"),
            "base_power_mw": f'{float(c["mPowerConsumption"]):g}',
            "power_exponent": f'{float(c["mPowerConsumptionExponent"]):.6f}',
            "game_build_id": BUILD_ID, "source_id": SOURCE_ID, "verified_on": VERIFIED,
        })

def write(name, rows, fields):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n"); w.writeheader(); w.writerows(rows)
    print(f"wrote {name}: {len(rows)} rows")

write("production_buildings.csv", sorted(producers.values(), key=lambda r: r["producer_class"]),
      ["producer_class","display_name","native_class","power_model","base_power_mw",
       "power_exponent","game_build_id","source_id","verified_on"])
write("recipe_variable_power.csv", sorted(vp_rows, key=lambda r: r["recipe_id"]),
      ["recipe_id","producer_class","vp_const_mw","vp_factor_mw","power_min_mw","power_max_mw",
       "power_mean_mw","game_build_id","source_id","verified_on"])
write("extraction_buildings.csv", sorted(extraction, key=lambda r: r["extractor_class"]),
      ["extractor_class","display_name","native_class","base_power_mw","power_exponent",
       "game_build_id","source_id","verified_on"])
print("game_build_id:", BUILD_ID, "| sha256:", SHA)
