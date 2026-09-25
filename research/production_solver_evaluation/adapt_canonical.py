"""Adapter: canonical progression-planner CSVs -> Candidate A (YAFP) GameData shape.
Pure data transform. No solver logic. Scenario multipliers applied at transform time.
"""
import csv, json, sys, collections, os

REF = "/mnt/user-data/uploads/satisfactory_progression_planner/planning_data/game/reference"
def rd(n): return list(csv.DictReader(open(os.path.join(REF,n), encoding="utf-8")))

recipe_input_multiplier = float(sys.argv[1]) if len(sys.argv)>1 else 1.0
machine_power_multiplier = float(sys.argv[2]) if len(sys.argv)>2 else 1.0
out = sys.argv[3] if len(sys.argv)>3 else "gameData.json"

recipes_csv = rd("recipes.csv"); io_csv = rd("recipe_io.csv")
prod_csv = rd("recipe_producers.csv"); bldg_csv = rd("buildings.csv"); items_csv = rd("items.csv")

producer_of = {r["recipe_id"]: r["producer_class"] for r in prod_csv}
producer_name = {r["producer_class"]: r["producer_name"] for r in prod_csv}
# buildings.csv is keyed by Desc_*; recipes reference Build_*. Bridge on the machine noun.
power_by_name = {b["name"].strip().lower(): b["power_mw"] for b in bldg_csv}

buildings, missing_power = {}, []
for pc, nm in sorted(producer_name.items()):
    raw = power_by_name.get(nm.strip().lower(), "")
    if raw in ("", None):
        missing_power.append((pc, nm)); power = 0.0
    else:
        power = float(raw)
    buildings[pc] = {"slug": pc, "name": nm, "power": power*machine_power_multiplier,
                     "area": 0, "buildCost": [], "isFicsmas": False}

ing = collections.defaultdict(list); pro = collections.defaultdict(list)
for r in io_csv:
    rate = float(r["rate_per_min"])
    entry = {"itemClass": r["item_id"], "perMinute": rate}
    if r["direction"] == "input":
        entry["perMinute"] = rate*recipe_input_multiplier; ing[r["recipe_id"]].append(entry)
    else:
        pro[r["recipe_id"]].append(entry)

recipes = {}
for r in recipes_csv:
    rid = r["recipe_id"]
    recipes[rid] = {"slug": rid, "name": r["display_name"],
                    "isAlternate": r["is_alternate"] == "true",
                    "ingredients": ing[rid], "products": pro[rid],
                    "producedIn": producer_of[rid], "isFicsmas": False}

items, resources = {}, {}
for it in items_csv:
    iid = it["item_id"]
    items[iid] = {"slug": iid, "name": it["display_name"],
                  "sinkPoints": int(float(it["sink_points"] or 0)),
                  "usedInRecipes": [k for k,v in ing.items() if any(x["itemClass"]==iid for x in v)],
                  "producedFromRecipes": [k for k,v in pro.items() if any(x["itemClass"]==iid for x in v)],
                  "isFicsmas": False}
    if it["category"] == "resource":
        resources[iid] = {"itemClass": iid, "maxExtraction": None, "relativeValue": 1}

# Candidate A hardcodes these three extraction building keys in its report pass.
EXTRACTION_KEYS = {"Desc_MinerMk3_C": "miner_mk3", "Desc_WaterPump_C": None, "Desc_OilPump_C": None}
power_by_id = {b["building_id"]: b["power_mw"] for b in bldg_csv}
missing_extraction = []
for k, bid in EXTRACTION_KEYS.items():
    raw = power_by_id.get(bid, "") if bid else ""
    if raw in ("", None):
        missing_extraction.append(k); pw = 0.0
    else:
        pw = float(raw)
    buildings[k] = {"slug": k, "name": k, "power": pw*machine_power_multiplier,
                    "area": 0, "buildCost": [], "isFicsmas": False}

json.dump({"buildings": buildings, "recipes": recipes, "resources": resources,
           "items": items, "handGatheredItems": {}}, open(out,"w", newline="\n"))
print(json.dumps({"recipes": len(recipes), "items": len(items), "resources": len(resources),
                  "buildings": len(buildings),
                  "producers_without_power": missing_power,
                  "extraction_buildings_missing_from_repo": missing_extraction,
                  "recipes_without_power": sum(1 for r in recipes.values()
                       if buildings[r["producedIn"]]["power"] == 0)}, indent=1))
