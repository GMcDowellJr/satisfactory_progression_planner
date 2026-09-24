"""P2: extraction wiring. Extractor buildings, extraction rates, and the
resource -> extractor map, derived from the sha256-pinned game Docs.

Power note: extractor power is NOT uniformly on the extractor. Resource Well
Extractors draw 0 MW; the Resource Well Pressurizer (FGBuildableFrackingActivator)
carries the 150 MW for the whole well. Same shape as the variable-power case:
the number is not where the naive lookup expects it.
"""
import json, re, csv, hashlib, os

DOCS = "/mnt/user-data/uploads/Docs/en-US.json"
REF_IN = "/mnt/user-data/uploads/satisfactory_progression_planner/planning_data/game/reference"
OUT = "/mnt/user-data/outputs/planning_data/game/reference"
os.makedirs(OUT, exist_ok=True)

raw = open(DOCS, "rb").read()
BUILD_ID = "docs_" + hashlib.sha256(raw).hexdigest()[:12]
SOURCE_ID, VERIFIED = "local_game_docs_en_us", "2026-09-18"
d = json.loads(raw.decode("utf-16"))

def classes(sfx):
    for e in d:
        if e["NativeClass"].endswith(sfx):
            for c in e["Classes"]:
                yield e["NativeClass"], c

EXTRACTORS = ["FGBuildableResourceExtractor'", "FGBuildableWaterPump'", "FGBuildableFrackingExtractor'"]
ACTIVATORS = ["FGBuildableFrackingActivator'"]
CLS = re.compile(r"\.(\w+_C)'")
# Node purity multipliers. Not present in Docs; corroborated independently by
# miner_extraction_rates.csv (wiki) and reproduced exactly by base * multiplier.
PURITY = {"impure": 0.5, "normal": 1.0, "pure": 2.0}
OVERCLOCK_MAX = 2.5  # 250%

buildings, rates, resmap = [], [], []
extractors = {}

for sfx in EXTRACTORS + ACTIVATORS:
    for nc, c in classes(sfx):
        role = "activator" if sfx in ACTIVATORS else "extractor"
        rec = {
            "extractor_class": c["ClassName"], "display_name": c["mDisplayName"],
            "native_class": sfx.rstrip("'"), "role": role,
            "base_power_mw": f'{float(c["mPowerConsumption"]):g}',
            "power_exponent": f'{float(c["mPowerConsumptionExponent"]):.6f}',
            "game_build_id": BUILD_ID, "source_id": SOURCE_ID, "verified_on": VERIFIED,
        }
        buildings.append(rec)
        if role == "extractor":
            extractors[c["ClassName"]] = c

for ec, c in sorted(extractors.items()):
    per_cycle = int(c["mItemsPerCycle"])
    cycle = float(c["mExtractCycleTime"])
    forms = [f.strip() for f in c["mAllowedResourceForms"].strip("()").split(",") if f.strip()]
    fluid = any(f in ("RF_LIQUID", "RF_GAS") for f in forms)
    unit = "m3/min" if fluid else "items/min"
    base = (per_cycle / 1000.0 if fluid else per_cycle) * 60.0 / cycle
    # Water Extractors are placed on water surfaces, not on graded nodes, so node
    # purity does not apply. Corroborated by the world layer: resource_totals.csv
    # grades solid nodes, oil nodes and resource wells, and lists no water nodes.
    purities = {"none": 1.0} if ec == "Build_WaterPump_C" else PURITY
    for purity, mult in purities.items():
        nominal = base * mult
        rates.append({
            "extractor_class": ec, "purity": purity, "clock_percent": "100",
            "items_per_cycle_raw": per_cycle, "extract_cycle_time_sec": f"{cycle:g}",
            "purity_multiplier": f"{mult:g}",
            "nominal_rate_min": f"{nominal:g}", "max_250_rate_min": f"{nominal * OVERCLOCK_MAX:g}",
            "unit": unit, "game_build_id": BUILD_ID, "source_id": SOURCE_ID, "verified_on": VERIFIED,
        })
    only = c["mOnlyAllowCertainResources"] == "True"
    allowed = CLS.findall(c.get("mAllowedResources", "") or "")
    for r in csv.DictReader(open(os.path.join(REF_IN, "items.csv"), encoding="utf-8")):
        if r["category"] != "resource":
            continue
        form = {"solid": "RF_SOLID", "liquid": "RF_LIQUID", "gas": "RF_GAS"}[r["form"]]
        if form not in forms:
            continue
        if only and r["item_id"] not in allowed:
            continue
        resmap.append({
            "item_id": r["item_id"], "display_name": r["display_name"], "form": r["form"],
            "extractor_class": ec, "extractor_name": extractors[ec]["mDisplayName"],
            "requires_activator": "Build_FrackingSmasher_C" if "Fracking" in ec else "",
            "game_build_id": BUILD_ID, "source_id": SOURCE_ID, "verified_on": VERIFIED,
        })

def write(name, rows, fields, key):
    rows = sorted(rows, key=key)
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n"); w.writeheader(); w.writerows(rows)
    print(f"wrote {name}: {len(rows)} rows")

write("extraction_buildings.csv", buildings,
      ["extractor_class","display_name","native_class","role","base_power_mw","power_exponent",
       "game_build_id","source_id","verified_on"], lambda r: (r["role"], r["extractor_class"]))
write("extraction_rates.csv", rates,
      ["extractor_class","purity","clock_percent","items_per_cycle_raw","extract_cycle_time_sec",
       "purity_multiplier","nominal_rate_min","max_250_rate_min","unit","game_build_id","source_id",
       "verified_on"], lambda r: (r["extractor_class"], (list(PURITY) + ["none"]).index(r["purity"])))
write("resource_extraction_map.csv", resmap,
      ["item_id","display_name","form","extractor_class","extractor_name","requires_activator",
       "game_build_id","source_id","verified_on"], lambda r: (r["item_id"], r["extractor_class"]))

# --- reconcile against the existing wiki-sourced miner table ---------------
MARK = {"Mk.1": "Build_MinerMk1_C", "Mk.2": "Build_MinerMk2_C", "Mk.3": "Build_MinerMk3_C"}
idx = {(r["extractor_class"], r["purity"]): r for r in rates}
bad = 0
for r in csv.DictReader(open(os.path.join(REF_IN, "miner_extraction_rates.csv"), encoding="utf-8")):
    mine = idx[(MARK[r["miner_mark"]], r["purity"])]
    for a, b in (("nominal_rate_min", "nominal_rate_min"), ("max_250_rate_min", "max_250_rate_min")):
        if abs(float(r[a]) - float(mine[b])) > 1e-6:
            bad += 1
            print(f"  MISMATCH {r['miner_mark']} {r['purity']} {a}: wiki={r[a]} docs={mine[b]}")
print(f"miner_extraction_rates.csv reconciliation: {bad} mismatches across 9 rows x 2 columns")
