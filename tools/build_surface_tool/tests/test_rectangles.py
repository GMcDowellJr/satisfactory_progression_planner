import numpy as np
from build_surface_tool.rectangles import largest_rectangle


def test_largest_rectangle():
    a=np.array([[1,1,0,1],[1,1,0,1],[1,1,1,1]],dtype=bool)
    r=largest_rectangle(a)
    assert r.area_cells == 6
