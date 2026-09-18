import numpy as np
from corridor_tool.field import TerrainField
from corridor_tool.derive import derive

def policy():
 return {"policy_id":"t","terrain":{"grade_neighborhood_m":10,"grade_hard_block":2,"unknown_terrain_block":True,"cliff_provenance_block":False},"water":{"block_any_water":True,"block_deep_or_unknown_depth":True,"deep_water_depth_m":3},"corridor":{"maximum_constrained_half_width_m":50,"chokepoint_half_width_m":20,"minimum_branch_length_m":0,"simplify_tolerance_m":0}}

def test_corridor_graph_nonempty():
 z=np.zeros((30,30),np.float32); z[:,0:5]=np.nan; z[:,25:]=np.nan
 # block most of middle row except 3-cell gate, making a chokepoint
 z[14:16,5:13]=np.nan; z[14:16,16:25]=np.nan
 f=TerrainField(10,0,0,z,np.zeros((30,30),np.uint8),np.zeros((30,30),np.uint8),np.full((30,30),np.nan,np.float32))
 r=derive(f,policy())
 assert len(r.nodes)>0 and len(r.edges)>0
 assert "corridor_class" in r.edges
