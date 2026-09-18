from pathlib import Path
from types import SimpleNamespace

import world_viewer.vtk_view as vv


class FakeStyle:
    def __init__(self):
        self.motion = None
        self.wheel = None
        self.observers = []
    def SetMotionFactor(self, value): self.motion = value
    def SetMouseWheelMotionFactor(self, value): self.wheel = value
    def AddObserver(self, event, callback, priority=0.0): self.observers.append((event, callback, priority))


class FakeInteractor:
    def __init__(self):
        self.style = None
        self.shift = 0
        self.observers = []
    def SetInteractorStyle(self, style): self.style = style
    def GetShiftKey(self): return self.shift
    def AddObserver(self, event, callback, priority=0.0): self.observers.append((event, callback, priority))


def test_interactor_style_live_navigation_controls(monkeypatch):
    fake_vtk = SimpleNamespace(vtkInteractorStyleTrackballCamera=FakeStyle)
    monkeypatch.setattr(vv, "vtk", fake_vtk)
    interactor = FakeInteractor()
    style = vv._configure_interactor_style(interactor)
    assert interactor.style is style
    assert style.motion == 8.0
    assert style.wheel == 0.5
    style._satisfactory_set_motion(12.0)
    assert style.motion == 12.0
    style._satisfactory_set_wheel(0.8)
    assert style.wheel == 0.8
    style._satisfactory_set_fine(0.1)
    interactor.shift = 1
    style._satisfactory_set_motion(10.0)
    assert style.motion == 1.0
    assert abs(style.wheel - 0.08) < 1e-9
    assert not any(event == "MouseMoveEvent" for event, _, _ in style.observers)
    assert any(event == "KeyPressEvent" for event, _, _ in interactor.observers)
    assert any(event == "KeyReleaseEvent" for event, _, _ in interactor.observers)


def test_write_png_creates_parent_and_verifies_file(monkeypatch, tmp_path):
    class W2I:
        def SetInput(self, window): pass
        def Update(self): pass
        def GetOutputPort(self): return object()
    class Writer:
        def __init__(self): self.path = None
        def SetFileName(self, path): self.path = Path(path)
        def SetInputConnection(self, port): pass
        def Write(self): self.path.write_bytes(b"png")
    fake_vtk = SimpleNamespace(vtkWindowToImageFilter=W2I, vtkPNGWriter=Writer)
    monkeypatch.setattr(vv, "vtk", fake_vtk)
    out = tmp_path / "missing" / "nested" / "shot.png"
    result = vv._write_png(object(), out)
    assert result == out
    assert out.read_bytes() == b"png"


def test_plan_camera_uses_positive_transformed_north_as_screen_up():
    class Camera:
        def __init__(self): self.focal=None; self.position=None; self.up=None; self.parallel=False
        def SetFocalPoint(self,*v): self.focal=v
        def SetPosition(self,*v): self.position=v
        def SetViewUp(self,*v): self.up=v
        def ParallelProjectionOn(self): self.parallel=True
    class Terrain:
        def GetBounds(self): return (0.0, 100.0, -200.0, 0.0, 10.0, 30.0)
    class Renderer:
        def __init__(self): self.camera=Camera(); self.bounds=None; self.clipped=False
        def GetActiveCamera(self): return self.camera
        def ResetCamera(self, bounds=None): self.bounds=bounds
        def ResetCameraClippingRange(self): self.clipped=True
    renderer=Renderer()
    cam=vv._reset_plan_camera(renderer, Terrain())
    assert cam.up == (0.0, 1.0, 0.0)
    assert cam.parallel is True
    assert cam.position[2] > cam.focal[2]
    assert renderer.bounds == (0.0, 100.0, -200.0, 0.0, 10.0, 30.0)


def test_rectangle_dimensions_use_foundation_units_not_analysis_resolution():
    row=SimpleNamespace(width_foundations=8.0,length_foundations=8.0,foundation_size_m=8.0)
    assert vv._rectangle_dimensions_m(row) == (64.0,64.0)
    legacy=SimpleNamespace(width_foundations=12.0,length_foundations=26.0)
    assert vv._rectangle_dimensions_m(legacy) == (96.0,208.0)
