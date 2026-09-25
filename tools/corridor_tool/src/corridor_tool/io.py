from __future__ import annotations
import json, zlib
from pathlib import Path
import numpy as np
from .derive import CorridorResult

def _write_array(path: Path,a: np.ndarray):
    hdr={"dtype":str(a.dtype),"shape":list(a.shape),"encoding":"zlib_raw_c_order"}
    path.with_suffix(path.suffix+".json").write_text(json.dumps(hdr,indent=2),encoding="utf-8", newline="\n")
    path.write_bytes(zlib.compress(a.tobytes(order="C"),9))

def write_result(result: CorridorResult,out: Path,policy:dict,manifest:dict):
    out.mkdir(parents=True,exist_ok=True)
    result.nodes.to_csv(out/"corridor_nodes.csv",index=False, lineterminator="\n")
    result.edges.to_csv(out/"corridor_edges.csv",index=False, lineterminator="\n")
    point_rows=[]
    if not result.edges.empty:
        for _,e in result.edges.iterrows():
            for order,token in enumerate(str(e["path_rc"]).split(";")):
                r,c=map(int,token.split(":"))
                point_rows.append({"edge_id":e["edge_id"],"point_order":order,"row":r,"col":c})
    import pandas as pd
    pd.DataFrame(point_rows,columns=["edge_id","point_order","row","col"]).to_csv(out/"corridor_edge_points.csv",index=False, lineterminator="\n")
    _write_array(out/"passable.u8.z",result.passable.astype(np.uint8))
    _write_array(out/"clearance.f32.z",result.clearance_m.astype("<f4"))
    _write_array(out/"skeleton.u8.z",result.skeleton.astype(np.uint8))
    summary={**result.summary,"policy_id":policy["policy_id"],"world_extract_id":manifest["world_extract_id"],"game_build":manifest["game"]["build"]}
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8", newline="\n")
    qa={"status":"PASS" if len(result.nodes)>0 and len(result.edges)>0 else "FAIL","checks":{"nonempty_graph":len(result.nodes)>0 and len(result.edges)>0,"finite_clearance_on_skeleton":bool(np.isfinite(result.clearance_m[result.skeleton]).all())}}
    (out/"qa.json").write_text(json.dumps(qa,indent=2),encoding="utf-8", newline="\n")
