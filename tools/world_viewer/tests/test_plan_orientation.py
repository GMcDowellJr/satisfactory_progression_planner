from world_viewer import vtk_view


def test_plan_camera_uses_positive_viewer_north():
    # io.py converts raw game -Y into the positive north_m viewer axis.
    src = open(vtk_view.__file__, encoding="utf-8").read()
    assert "camera.SetViewUp(0.0, 1.0, 0.0)" in src
    assert "camera.SetViewUp(0.0, -1.0, 0.0)" not in src


def test_slider_uses_value_in_title_not_separate_value_label():
    src = open(vtk_view.__file__, encoding="utf-8").read()
    assert 'rep.SetLabelFormat("")' in src
    assert 'rep.SetTitleText(f"{title} {float(v):.' in src
