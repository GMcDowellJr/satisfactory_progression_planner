from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

RESOURCE_MAP = {
    "Desc_OreIron_C": "iron",
    "Desc_OreCopper_C": "copper",
    "Desc_Stone_C": "limestone",
    "Desc_Coal_C": "coal",
    "Desc_OreGold_C": "caterium",
    "Desc_RawQuartz_C": "raw_quartz",
    "Desc_Sulfur_C": "sulfur",
    "Desc_SAM_C": "sam",
    "Desc_OreBauxite_C": "bauxite",
    "Desc_OreUranium_C": "uranium",
    "Desc_LiquidOil_C": "crude_oil",
    "Desc_NitrogenGas_C": "nitrogen_gas",
    "Desc_Water_C": "water",
}
KIND_MAP = {
    "BP_ResourceNode_C": "resource_node",
    "BP_ResourceNodeGeyser_C": "geothermal_geyser",
    "BP_FrackingCore_C": "fracking_core",
    "BP_FrackingSatellite_C": "fracking_satellite",
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Project first-party world-resource extraction into planner v2 tables.")
    ap.add_argument("source_json", type=Path)
    ap.add_argument("--planner-data", type=Path, default=Path("planning_data"))
    ap.add_argument("--world-config-id", default=None)
    args = ap.parse_args()

    raw = args.source_json.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw)
    nodes = payload["nodes"]
    meta = payload["_meta"]
    if len(nodes) != meta["count"]:
        raise SystemExit("resource-node count does not match metadata")

    build_text = meta["game_version_pinned"]
    build = build_text.split("buildVersion ", 1)[1].split(" ", 1)[0]
    config_id = args.world_config_id or f"default_{build}"
    build_label = f"CL-{build}"

    canonical = args.planner_data / "world" / "canonical"
    configuration = args.planner_data / "world" / "configurations" / config_id
    qa = args.planner_data / "analysis" / "qa"
    canonical.mkdir(parents=True, exist_ok=True)
    configuration.mkdir(parents=True, exist_ok=True)
    qa.mkdir(parents=True, exist_ok=True)

    ids = {n["id"] for n in nodes}
    sockets = canonical / "world_resource_sockets.csv"
    with sockets.open("w", newline="", encoding="utf-8") as f:
        fields = ["socket_id","source_object_id","source_class","source_kind","east_m","north_m","elevation_m","core_socket_id","source_game_build","source_sha256"]
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n"); w.writeheader()
        for n in nodes:
            core = n.get("core", "")
            if core and core not in ids:
                raise SystemExit(f"unknown fracking core: {core}")
            w.writerow({
                "socket_id": n["id"],
                "source_object_id": "Persistent_Level:PersistentLevel." + n["id"],
                "source_class": n["class"],
                "source_kind": KIND_MAP[n["class"]],
                "east_m": round(n["x"] / 100.0, 6),
                "north_m": round(-n["y"] / 100.0, 6),
                "elevation_m": round(n["z"] / 100.0, 6),
                "core_socket_id": core,
                "source_game_build": build_label,
                "source_sha256": sha,
            })

    assignments = configuration / "resource_assignments.csv"
    with assignments.open("w", newline="", encoding="utf-8") as f:
        fields = ["world_config_id","socket_id","resource_id","resource_descriptor","purity","assignment_source","source_game_build","source_sha256"]
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n"); w.writeheader()
        for n in nodes:
            desc = n.get("resource")
            rid = "geothermal_geyser" if not desc else RESOURCE_MAP[desc]
            w.writerow({
                "world_config_id": config_id,
                "socket_id": n["id"],
                "resource_id": rid,
                "resource_descriptor": desc or "",
                "purity": n.get("purity", ""),
                "assignment_source": "installed_world_default",
                "source_game_build": build_label,
                "source_sha256": sha,
            })

    print(f"wrote {len(nodes)} sockets and {len(nodes)} assignments for {config_id}")

if __name__ == "__main__":
    main()
