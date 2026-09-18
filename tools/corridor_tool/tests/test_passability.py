import numpy as np
from corridor_tool.field import TerrainField
from corridor_tool.derive import build_passability

def test_steep_step_blocks():
    z=np.zeros((9,9),np.float32); z[:,5:]=100
    f=TerrainField(10,0,0,z,np.zeros_like(z,dtype=np.uint8),np.zeros_like(z,dtype=np.uint8),np.full_like(z,np.nan))
    p={"terrain":{"grade_neighborhood_m":10,"grade_hard_block":1.0,"unknown_terrain_block":True,"cliff_provenance_block":False},"water":{"block_any_water":False,"block_deep_or_unknown_depth":True,"deep_water_depth_m":3}}
    m,g=build_passability(f,p)
    assert not m[:,4:6].all()
