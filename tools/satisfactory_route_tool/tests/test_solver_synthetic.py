import numpy as np
from satisfactory_route_tool.heightfield import WorkingField
from satisfactory_route_tool.solver import solve


def field():
    z=np.zeros((30,30),dtype=np.float32)
    prov=np.ones((30,30),dtype=np.uint8)
    wq=np.zeros((30,30),dtype=np.uint8)
    wd=np.full((30,30),np.nan,dtype=np.float32)
    return WorkingField(5.0,0.0,145.0,z,prov,wq,wd)


PROFILE={
    "road_factor":0.3,"road_band_factor":0.6,
    "grade_soft_start":0.3,"grade_hard_block":1.0,"grade_penalty":10.0,
    "shallow_water_penalty":10.0,"deep_water_depth_m":3.0,"deep_water_penalty":100.0,
    "cliff_penalty":10.0,"unknown_penalty":5.0
}


def test_deep_water_blocked():
    f=field()
    f.water_q[:,15]=1
    f.water_depth_m[:,15]=10
    try:
        solve(f,(5,100),(140,100),PROFILE,bridge_policy="forbid",corridor_pad_m=200)
    except RuntimeError:
        pass
    else:
        raise AssertionError("deep continuous water barrier should block route")


def test_bridge_allows_water():
    f=field()
    f.water_q[:,15]=1
    f.water_depth_m[:,15]=10
    r=solve(f,(5,100),(140,100),PROFILE,bridge_policy="allow",corridor_pad_m=200)
    assert len(r.route)>0


def test_grade_wall_blocked():
    f=field()
    f.z_m[:,15:]=100.0
    try:
        solve(f,(5,100),(140,100),PROFILE,bridge_policy="forbid",corridor_pad_m=200)
    except RuntimeError:
        pass
    else:
        raise AssertionError("vertical wall should block route")
