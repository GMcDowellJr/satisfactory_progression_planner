from __future__ import annotations

from pathlib import Path
import numpy as np

try:
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk
except ImportError as exc:  # pragma: no cover
    vtk = None
    numpy_to_vtk = None
    _VTK_IMPORT_ERROR = exc
else:
    _VTK_IMPORT_ERROR = None

from .geometry import regular_surface_mesh, surface_overlay_cells, representative_height
from .io import load_membership, load_rectangles

SIZE_COLORS = {
    1: (0.45, 0.78, 0.52),
    2: (0.93, 0.79, 0.34),
    3: (0.95, 0.48, 0.25),
    4: (0.67, 0.45, 0.88),
}



def _require_vtk():
    if vtk is None:
        raise RuntimeError("VTK is required for interactive viewing; install the world_viewer package dependencies") from _VTK_IMPORT_ERROR



def _add_overlay_actor(renderer, actor):
    """Add a 2D/overlay prop across VTK versions.

    Some VTK Python builds no longer expose vtkRenderer.AddActor2D even
    though vtkTextActor remains a valid vtkProp. AddViewProp is the stable
    base-class API and works for both 2D text actors and ordinary props.
    """
    add_actor_2d = getattr(renderer, "AddActor2D", None)
    if callable(add_actor_2d):
        add_actor_2d(actor)
        return
    add_view_prop = getattr(renderer, "AddViewProp", None)
    if callable(add_view_prop):
        add_view_prop(actor)
        return
    add_actor = getattr(renderer, "AddActor", None)
    if callable(add_actor):
        add_actor(actor)
        return
    raise RuntimeError("This VTK renderer exposes no supported actor-add API")



def _write_png(window, output: Path) -> Path:
    """Write a PNG snapshot, creating parents and verifying the write."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(window)
    w2i.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(output))
    writer.SetInputConnection(w2i.GetOutputPort())
    writer.Write()
    if not output.is_file() or output.stat().st_size <= 0:
        raise RuntimeError(f"VTK did not create snapshot: {output}")
    return output



def _configure_interactor_style(interactor, motion_factor: float = 8.0, wheel_factor: float = 0.5, fine_factor: float = 0.25):
    """Install tunable trackball controls without intercepting VTK mouse events.

    Important: adding a MouseMoveEvent observer directly to vtkInteractorStyle can
    suppress the style's native OnMouseMove implementation on some VTK builds.
    Fine control is therefore applied from Shift key state changes instead.
    """
    style = vtk.vtkInteractorStyleTrackballCamera()
    state = {"motion": float(motion_factor), "wheel": float(wheel_factor), "fine": float(fine_factor)}

    def apply_effective_sensitivity():
        shift = bool(interactor.GetShiftKey())
        multiplier = state["fine"] if shift else 1.0
        if hasattr(style, "SetMotionFactor"):
            style.SetMotionFactor(max(0.05, state["motion"] * multiplier))
        if hasattr(style, "SetMouseWheelMotionFactor"):
            style.SetMouseWheelMotionFactor(max(0.01, state["wheel"] * multiplier))

    def set_motion(value: float):
        state["motion"] = float(value)
        apply_effective_sensitivity()

    def set_wheel(value: float):
        state["wheel"] = float(value)
        apply_effective_sensitivity()

    def set_fine(value: float):
        state["fine"] = float(value)
        apply_effective_sensitivity()

    def modifier_changed(obj, event):
        apply_effective_sensitivity()

    style._satisfactory_nav_state = state
    style._satisfactory_set_motion = set_motion
    style._satisfactory_set_wheel = set_wheel
    style._satisfactory_set_fine = set_fine
    style._satisfactory_apply_sensitivity = apply_effective_sensitivity
    interactor.SetInteractorStyle(style)
    if hasattr(interactor, "AddObserver"):
        interactor.AddObserver("KeyPressEvent", modifier_changed, 2.0)
        interactor.AddObserver("KeyReleaseEvent", modifier_changed, 2.0)
    apply_effective_sensitivity()
    return style



def _make_slider(interactor, title: str, minimum: float, maximum: float, value: float, y: float, callback, decimals: int = 1):
    """Create a compact live slider in the upper-right corner.

    V8 intentionally uses about one quarter of the old horizontal control span so
    the controls do not obscure the map. Values remain in the title and update live.
    """
    rep = vtk.vtkSliderRepresentation2D()
    rep.SetMinimumValue(float(minimum)); rep.SetMaximumValue(float(maximum)); rep.SetValue(float(value))
    rep.SetLabelFormat("")
    rep.GetPoint1Coordinate().SetCoordinateSystemToNormalizedDisplay(); rep.GetPoint1Coordinate().SetValue(0.958, y)
    rep.GetPoint2Coordinate().SetCoordinateSystemToNormalizedDisplay(); rep.GetPoint2Coordinate().SetValue(0.987, y)
    rep.SetSliderLength(0.006); rep.SetSliderWidth(0.008); rep.SetTubeWidth(0.002); rep.SetEndCapLength(0.004)
    rep.GetTitleProperty().SetColor(0.98, 0.98, 0.98); rep.GetTitleProperty().SetFontSize(8)
    rep.GetLabelProperty().SetOpacity(0.0)

    def update_title(v: float):
        rep.SetTitleText(f"{title} {float(v):.{int(decimals)}f}")

    update_title(value)
    widget = vtk.vtkSliderWidget(); widget.SetInteractor(interactor); widget.SetRepresentation(rep); widget.SetAnimationModeToAnimate()

    def changed(obj, event):
        v = float(rep.GetValue())
        update_title(v)
        callback(v)

    widget.AddObserver("InteractionEvent", changed); widget.EnabledOn()
    return widget, rep


def _wrapped(text: str, width: int = 112) -> str:
    """Wrap overlay prose without breaking existing explicit line boundaries."""
    import textwrap
    return "\n".join(
        textwrap.fill(line, width=width, break_long_words=False, break_on_hyphens=False) if line else ""
        for line in str(text).splitlines()
    )


def _set_camera_pivot(camera, target) -> None:
    """Move the camera focal point to an explicit orbit pivot."""
    if target is None:
        return
    camera.SetFocalPoint(float(target[0]), float(target[1]), float(target[2]))


def _enforce_world_up(renderer) -> None:
    """Prevent camera roll: north-up in plan, world-Z-up in oblique views."""
    camera = renderer.GetActiveCamera()
    pos = np.asarray(camera.GetPosition(), dtype=float)
    focal = np.asarray(camera.GetFocalPoint(), dtype=float)
    d = focal - pos
    norm = float(np.linalg.norm(d))
    if norm <= 1e-9:
        return
    d /= norm
    world_z = np.array([0.0, 0.0, 1.0])
    projected = world_z - float(np.dot(world_z, d)) * d
    plen = float(np.linalg.norm(projected))
    if plen < 1e-4:
        camera.SetViewUp(0.0, 1.0, 0.0)
    else:
        projected /= plen
        camera.SetViewUp(*projected)
    if hasattr(camera, "OrthogonalizeViewUp"):
        camera.OrthogonalizeViewUp()

def _poly_from_triangles(points: np.ndarray, faces: np.ndarray):
    poly = vtk.vtkPolyData()
    pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(points, deep=True))
    poly.SetPoints(pts)
    cells = vtk.vtkCellArray()
    for f in faces:
        tri = vtk.vtkTriangle()
        for i in range(3):
            tri.GetPointIds().SetId(i, int(f[i]))
        cells.InsertNextCell(tri)
    poly.SetPolys(cells)
    return poly



def _poly_from_quads(points: np.ndarray, quads: np.ndarray, row_index: np.ndarray, size_rank: np.ndarray):
    poly = vtk.vtkPolyData()
    pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(points, deep=True)); poly.SetPoints(pts)
    cells = vtk.vtkCellArray()
    for f in quads:
        q = vtk.vtkQuad()
        for i in range(4):
            q.GetPointIds().SetId(i, int(f[i]))
        cells.InsertNextCell(q)
    poly.SetPolys(cells)
    a = numpy_to_vtk(row_index.astype(np.int32), deep=True); a.SetName("surface_row")
    b = numpy_to_vtk(size_rank.astype(np.int32), deep=True); b.SetName("size_rank")
    poly.GetCellData().AddArray(a); poly.GetCellData().SetScalars(b)
    return poly



def _poly_from_lines(points: np.ndarray, segments: np.ndarray, row_index: np.ndarray | None = None):
    poly = vtk.vtkPolyData()
    pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(points, deep=True)); poly.SetPoints(pts)
    cells = vtk.vtkCellArray()
    for s in segments:
        line = vtk.vtkLine()
        line.GetPointIds().SetId(0, int(s[0]))
        line.GetPointIds().SetId(1, int(s[1]))
        cells.InsertNextCell(line)
    poly.SetLines(cells)
    if row_index is not None and len(row_index):
        a = numpy_to_vtk(row_index.astype(np.int32), deep=True); a.SetName("surface_row")
        poly.GetCellData().AddArray(a)
    return poly



def _surface_subset(surfaces, resolution_m: float, size_filter: set[str] | None = None, surface_ids: set[str] | None = None,
                    platform_elevation_m: float | None = None, local_relief_tolerance_m: float | None = None, clearance_tolerance_m: float | None = None):
    df = surfaces[surfaces["analysis_resolution_m"].astype(float) == float(resolution_m)].copy()
    if clearance_tolerance_m is not None and "clearance_tolerance_m" in df.columns:
        df = df[np.isclose(df["clearance_tolerance_m"].astype(float), float(clearance_tolerance_m))]
    elif local_relief_tolerance_m is not None and "local_relief_tolerance_m" in df.columns:
        df = df[np.isclose(df["local_relief_tolerance_m"].astype(float), float(local_relief_tolerance_m))]
    elif platform_elevation_m is not None:
        if "platform_elevation_m" in df.columns:
            df = df[np.isclose(df["platform_elevation_m"].astype(float), float(platform_elevation_m))]
        elif "region_vertical_span_m" in df.columns:
            # v2 compatibility: the viewer's second variant dimension was platform elevation.
            df = df[df["region_vertical_span_m"].astype(float) == float(platform_elevation_m)]
    if size_filter:
        df = df[df["size_class"].isin(size_filter)]
    if surface_ids is not None:
        df = df[df["surface_id"].isin(surface_ids)]
    return df



def _terrain_actor(world, spacing_m: float):
    mesh = regular_surface_mesh(world, spacing_m=spacing_m)
    poly = _poly_from_triangles(mesh.points, mesh.faces)
    if mesh.scalars is not None and len(mesh.scalars) == len(mesh.faces):
        vals = numpy_to_vtk(mesh.scalars.astype(np.float32), deep=True); vals.SetName("elevation_m")
        poly.GetCellData().SetScalars(vals)
    mapper = vtk.vtkPolyDataMapper(); mapper.SetInputData(poly); mapper.ScalarVisibilityOff()
    actor = vtk.vtkActor(); actor.SetMapper(mapper); actor.GetProperty().SetColor(0.58, 0.57, 0.54)
    return actor



def _water_actor(world, spacing_m: float):
    mesh = regular_surface_mesh(world, spacing_m=spacing_m, source="water")
    if len(mesh.faces) == 0:
        return None
    poly = _poly_from_triangles(mesh.points, mesh.faces)
    mapper = vtk.vtkPolyDataMapper(); mapper.SetInputData(poly); mapper.ScalarVisibilityOff()
    actor = vtk.vtkActor(); actor.SetMapper(mapper); actor.GetProperty().SetColor(0.24, 0.55, 0.78); actor.GetProperty().SetOpacity(0.48)
    return actor



def _resource_actor(resources):
    pts = vtk.vtkPoints()
    for r in resources.itertuples(index=False):
        pts.InsertNextPoint(float(r.east_m), float(r.north_m), float(r.elevation_m) + 4.0)
    poly = vtk.vtkPolyData(); poly.SetPoints(pts)
    sphere = vtk.vtkSphereSource(); sphere.SetRadius(7.0); sphere.SetThetaResolution(6); sphere.SetPhiResolution(6)
    glyph = vtk.vtkGlyph3D(); glyph.SetSourceConnection(sphere.GetOutputPort()); glyph.SetInputData(poly); glyph.Update()
    mapper = vtk.vtkPolyDataMapper(); mapper.SetInputConnection(glyph.GetOutputPort())
    actor = vtk.vtkActor(); actor.SetMapper(mapper); actor.GetProperty().SetColor(0.92, 0.92, 0.92)
    return actor



def _coverage_layer_for_sizes(size_filter: set[str] | None) -> str:
    if size_filter and len(size_filter) == 1:
        name = next(iter(size_filter))
        return f"coverage_{name}_labels"
    return "coverage_labels"


def _surface_actor(world, surfaces, surface_dir: Path, resolution_m: float, size_filter: set[str] | None = None, surface_ids: set[str] | None = None,
                   platform_elevation_m: float | None = None, local_relief_tolerance_m: float | None = None, clearance_tolerance_m: float | None = None):
    labels = load_membership(surface_dir, resolution_m, platform_elevation_m, local_relief_tolerance_m, clearance_tolerance_m, layer=_coverage_layer_for_sizes(size_filter))
    df = _surface_subset(surfaces, resolution_m, size_filter=size_filter, surface_ids=surface_ids,
                         platform_elevation_m=platform_elevation_m, local_relief_tolerance_m=local_relief_tolerance_m, clearance_tolerance_m=clearance_tolerance_m)
    points, quads, row_idx, size_rank, rows = surface_overlay_cells(
        world, labels, df, resolution_m, size_filter=None, platform_elevation_m=platform_elevation_m,
        local_relief_tolerance_m=local_relief_tolerance_m, clearance_tolerance_m=clearance_tolerance_m
    )
    poly = _poly_from_quads(points, quads, row_idx, size_rank)
    mapper = vtk.vtkPolyDataMapper(); mapper.SetInputData(poly); mapper.SetScalarModeToUseCellData(); mapper.SetScalarRange(1, 4)
    lut = vtk.vtkLookupTable(); lut.SetNumberOfTableValues(4); lut.Build()
    for rank in range(1, 5):
        c = SIZE_COLORS[rank]; lut.SetTableValue(rank - 1, c[0], c[1], c[2], 0.72)
    mapper.SetLookupTable(lut)
    actor = vtk.vtkActor(); actor.SetMapper(mapper); actor.GetProperty().SetOpacity(0.72)
    return actor, rows



def _surface_outline_actor(world, surfaces, surface_dir: Path, resolution_m: float, size_filter: set[str] | None = None,
                           surface_ids: set[str] | None = None, platform_elevation_m: float | None = None,
                           local_relief_tolerance_m: float | None = None, clearance_tolerance_m: float | None = None, z_offset_m: float = 2.8,
                           color=(0.10, 0.10, 0.10), opacity: float = 0.95, line_width: float = 1.0,
                           layer: str | None = None):
    labels = load_membership(surface_dir, resolution_m, platform_elevation_m, local_relief_tolerance_m, clearance_tolerance_m, layer=(layer or _coverage_layer_for_sizes(size_filter)))
    df = _surface_subset(surfaces, resolution_m, size_filter=size_filter, surface_ids=surface_ids,
                         platform_elevation_m=platform_elevation_m, local_relief_tolerance_m=local_relief_tolerance_m, clearance_tolerance_m=clearance_tolerance_m)
    if df.empty:
        return None, []
    rows = list(df.itertuples(index=False))
    label_to_row = {}
    for i, row in enumerate(rows):
        try:
            label_to_row[int(str(row.surface_id).rsplit("_", 1)[1])] = i
        except Exception:
            continue
    if not label_to_row:
        return None, rows

    terrain_z = representative_height(world, resolution_m)
    h = min(labels.shape[0], terrain_z.shape[0]); w = min(labels.shape[1], terrain_z.shape[1])
    labels = labels[:h, :w]; terrain_z = terrain_z[:h, :w]
    half = resolution_m / 2.0
    segments=[]; points=[]; row_ids=[]

    def emit_segment(x0,y0,x1,y1,zz,row_id):
        base=len(points); points.extend([(x0,y0,zz),(x1,y1,zz)]); segments.append((base,base+1)); row_ids.append(row_id)

    for rr in range(h):
        north = world.north0_m - rr * resolution_m
        for cc in range(w):
            lab=int(labels[rr,cc]); row_id=label_to_row.get(lab)
            if row_id is None:
                continue
            east=world.east0_m + cc*resolution_m
            if platform_elevation_m is not None and "platform_elevation_m" in df.columns:
                zz=float(platform_elevation_m)+float(z_offset_m)
            else:
                if not np.isfinite(terrain_z[rr,cc]):
                    continue
                zz=float(terrain_z[rr,cc])+float(z_offset_m)
            x0,x1=east-half,east+half; y0,y1=north-half,north+half
            if rr==0 or int(labels[rr-1,cc])!=lab: emit_segment(x0,y1,x1,y1,zz,row_id)
            if rr==h-1 or int(labels[rr+1,cc])!=lab: emit_segment(x0,y0,x1,y0,zz,row_id)
            if cc==0 or int(labels[rr,cc-1])!=lab: emit_segment(x0,y0,x0,y1,zz,row_id)
            if cc==w-1 or int(labels[rr,cc+1])!=lab: emit_segment(x1,y0,x1,y1,zz,row_id)

    if not segments:
        return None, rows
    poly=_poly_from_lines(np.asarray(points,dtype=np.float64),np.asarray(segments,dtype=np.int64),np.asarray(row_ids,dtype=np.int32))
    mapper=vtk.vtkPolyDataMapper(); mapper.SetInputData(poly); mapper.ScalarVisibilityOff()
    actor=vtk.vtkActor(); actor.SetMapper(mapper)
    prop=actor.GetProperty(); prop.SetColor(*color); prop.SetOpacity(opacity); prop.SetLineWidth(float(line_width))
    return actor, rows



def _rectangle_dimensions_m(row) -> tuple[float, float]:
    """Return physical rectangle width/length in metres.

    Foundation geometry is a game-space quantity and must not change when the
    analysis raster changes resolution. V7 stores foundation_size_m explicitly;
    older rectangle CSVs fall back to the game's 8 m foundation width.
    """
    foundation_m = float(getattr(row, "foundation_size_m", 8.0))
    return float(row.width_foundations) * foundation_m, float(row.length_foundations) * foundation_m


def _rectangle_actor(surface_dir: Path, resolution_m: float, size_filter: set[str] | None = None,
                     local_relief_tolerance_m: float | None = None, clearance_tolerance_m: float | None = None, surface_ids: set[str] | None = None,
                     candidate_ranks: set[int] | None = None, color=(1.0, 1.0, 1.0), opacity: float = 0.95,
                     line_width: float = 2.0):
    df = load_rectangles(surface_dir)
    if df.empty:
        return None
    df = df[np.isclose(df["analysis_resolution_m"].astype(float), float(resolution_m))]
    if clearance_tolerance_m is not None and "clearance_tolerance_m" in df.columns:
        df = df[np.isclose(df["clearance_tolerance_m"].astype(float), float(clearance_tolerance_m))]
    elif local_relief_tolerance_m is not None and "local_relief_tolerance_m" in df.columns:
        df = df[np.isclose(df["local_relief_tolerance_m"].astype(float), float(local_relief_tolerance_m))]
    if size_filter:
        df = df[df["size_class"].isin(size_filter)]
    if surface_ids is not None:
        df = df[df["surface_id"].isin(surface_ids)]
    if candidate_ranks is not None:
        df = df[df["candidate_rank"].astype(int).isin(candidate_ranks)]
    if df.empty:
        return None
    points=[]; segments=[]
    for row in df.itertuples(index=False):
        cx=float(row.center_east_m); cy=float(row.center_north_m); z=float(row.display_elevation_m)+2.0
        width,length=_rectangle_dimensions_m(row)
        angle=np.deg2rad(float(row.rotation_deg))
        # local x follows rectangle length, local y follows width
        corners=np.array([[-length/2,-width/2],[length/2,-width/2],[length/2,width/2],[-length/2,width/2]],dtype=float)
        rot=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        xy=corners @ rot.T
        base=len(points)
        points.extend([(cx+x,cy+y,z) for x,y in xy])
        segments.extend([(base,base+1),(base+1,base+2),(base+2,base+3),(base+3,base)])
    poly=_poly_from_lines(np.asarray(points,dtype=np.float64),np.asarray(segments,dtype=np.int64))
    mapper=vtk.vtkPolyDataMapper(); mapper.SetInputData(poly); mapper.ScalarVisibilityOff()
    actor=vtk.vtkActor(); actor.SetMapper(mapper)
    prop=actor.GetProperty(); prop.SetColor(*color); prop.SetOpacity(float(opacity)); prop.SetLineWidth(float(line_width))
    return actor


def _reset_plan_camera(renderer, terrain_actor=None):
    """Frame the scene from directly above with planner north at screen top."""
    camera = renderer.GetActiveCamera()
    bounds = terrain_actor.GetBounds() if terrain_actor is not None else renderer.ComputeVisiblePropBounds()
    if bounds is None or len(bounds) != 6 or not np.all(np.isfinite(bounds)):
        renderer.ResetCamera()
        bounds = renderer.ComputeVisiblePropBounds()
    xmin, xmax, ymin, ymax, zmin, zmax = [float(v) for v in bounds]
    cx, cy, cz = (xmin + xmax) * 0.5, (ymin + ymax) * 0.5, (zmin + zmax) * 0.5
    span = max(xmax - xmin, ymax - ymin, 1.0)
    camera.SetFocalPoint(cx, cy, cz)
    camera.SetPosition(cx, cy, cz + span * 2.0)
    camera.SetViewUp(0.0, 1.0, 0.0)
    if hasattr(camera, "ParallelProjectionOn"):
        camera.ParallelProjectionOn()
    renderer.ResetCamera(bounds)
    renderer.ResetCameraClippingRange()
    return camera



def view(world, resources, surfaces, surface_dir: Path, resolution_m: float, terrain_spacing_m: float = 24.0,
         size_filter: set[str] | None = None, show_water: bool = True, show_resources: bool = True,
         vertical_exaggeration: float = 1.0, screenshot: Path | None = None, offscreen: bool = False,
         available_resolutions: list[float] | None = None, platform_elevation_m: float | None = None,
         local_relief_tolerance_m: float | None = None, clearance_tolerance_m: float | None = None,
         available_variants: list[tuple[float, float | None]] | None = None, motion_factor: float = 8.0,
         wheel_factor: float = 0.5, fine_factor: float = 0.25):
    _require_vtk()
    size_filter = size_filter or {"small"}
    size_priority = ["small", "medium", "large", "very_large"]
    active_initial = next((name for name in size_priority if name in size_filter), "small")
    resolutions = sorted(set(float(x) for x in (available_resolutions or [resolution_m])))
    if float(resolution_m) not in resolutions:
        resolutions.append(float(resolution_m)); resolutions.sort()
    resolution_index = [resolutions.index(float(resolution_m))]
    model = str(surfaces.iloc[0].get("analysis_model", "legacy")) if not surfaces.empty else "legacy"
    variants = list(available_variants or [(float(resolution_m), clearance_tolerance_m if model == "horizontal_plane_fit" else (local_relief_tolerance_m if model == "local_multiscale_relief" else platform_elevation_m))])

    def variant_values_for(resolution: float) -> list[float]:
        return sorted(v[1] for v in variants if float(v[0]) == float(resolution) and v[1] is not None)

    initial_values = variant_values_for(float(resolution_m))
    if model == "horizontal_plane_fit":
        if clearance_tolerance_m is None and initial_values:
            clearance_tolerance_m = 4.0 if any(np.isclose(x, 4.0) for x in initial_values) else initial_values[len(initial_values)//2]
        current_clearance_tolerance = [None if clearance_tolerance_m is None else float(clearance_tolerance_m)]
        current_relief_tolerance = [None]
        current_platform_elevation = [None]
    elif model == "local_multiscale_relief":
        current_clearance_tolerance = [None]
        if local_relief_tolerance_m is None and initial_values:
            local_relief_tolerance_m = 8.0 if any(np.isclose(x, 8.0) for x in initial_values) else initial_values[len(initial_values)//2]
        current_relief_tolerance = [None if local_relief_tolerance_m is None else float(local_relief_tolerance_m)]
        current_platform_elevation = [None]
    else:
        current_clearance_tolerance = [None]
        if platform_elevation_m is None and initial_values:
            platform_elevation_m = max(initial_values)
        current_platform_elevation = [None if platform_elevation_m is None else float(platform_elevation_m)]
        current_relief_tolerance = [None]

    renderer = vtk.vtkRenderer(); renderer.SetBackground(0.08, 0.09, 0.10)
    window = vtk.vtkRenderWindow(); window.AddRenderer(renderer); window.SetSize(1500, 950)
    if offscreen:
        window.SetOffScreenRendering(1)
    interactor = vtk.vtkRenderWindowInteractor(); interactor.SetRenderWindow(window)
    interaction_style = _configure_interactor_style(interactor, motion_factor, wheel_factor, fine_factor)

    terrain = _terrain_actor(world, terrain_spacing_m); renderer.AddActor(terrain)
    water = _water_actor(world, terrain_spacing_m)
    if show_water and water is not None:
        renderer.AddActor(water)
    resource_actor = _resource_actor(resources)
    if show_resources:
        renderer.AddActor(resource_actor)

    current_resolution = [float(resolution_m)]
    visible_sizes = {active_initial}
    selected_surface_id = [None]
    selected_world_point = [None]
    isolate_selected = [False]
    zex = [float(vertical_exaggeration)]
    rows_holder = [[]]
    actors = {"base": None, "outline": None, "center_outline": None, "rectangles": None, "selected_fill": None, "selected_outline": None, "selected_rectangles": None}

    title = vtk.vtkTextActor(); title.GetTextProperty().SetFontSize(16); title.GetTextProperty().SetColor(1.0, 1.0, 1.0); title.GetTextProperty().SetBold(True); title.GetTextProperty().SetBackgroundColor(0.03,0.03,0.03); title.GetTextProperty().SetBackgroundOpacity(0.72); title.SetPosition(14, 14); _add_overlay_actor(renderer, title)
    help_text = vtk.vtkTextActor(); help_text.GetTextProperty().SetFontSize(10); help_text.GetTextProperty().SetColor(0.95,0.95,0.95); help_text.GetTextProperty().SetBackgroundColor(0.03,0.03,0.03); help_text.GetTextProperty().SetBackgroundOpacity(0.66); help_text.SetPosition(14, 46); _add_overlay_actor(renderer, help_text)
    selected = vtk.vtkTextActor(); selected.GetTextProperty().SetFontSize(10); selected.GetTextProperty().SetColor(1.0,1.0,1.0); selected.GetTextProperty().SetBackgroundColor(0.03,0.03,0.03); selected.GetTextProperty().SetBackgroundOpacity(0.66); selected.SetPosition(14, 102); _add_overlay_actor(renderer, selected)

    def set_actor_scale(actor):
        if actor is not None:
            actor.SetScale(1.0, 1.0, zex[0])

    def remove_actor(name: str):
        actor = actors.get(name)
        if actor is not None:
            renderer.RemoveActor(actor)
        actors[name] = None

    def remove_all_surface_actors():
        for name in list(actors):
            remove_actor(name)

    def add_actor(name: str, actor):
        if actor is not None:
            set_actor_scale(actor)
            renderer.AddActor(actor)
        actors[name] = actor

    def selected_row():
        sid = selected_surface_id[0]
        if sid is None:
            return None
        for row in rows_holder[0]:
            if str(row.surface_id) == str(sid):
                return row
        return None

    def update_title():
        subset = surfaces[surfaces["analysis_resolution_m"].astype(float) == current_resolution[0]]
        extra = " | isolate selected" if isolate_selected[0] and selected_surface_id[0] is not None else ""
        if model == "horizontal_plane_fit":
            clearance = current_clearance_tolerance[0]
            cv = "?" if clearance is None else f"{clearance:g} m"
            active = subset
            if clearance is not None and "clearance_tolerance_m" in active.columns:
                active = active[np.isclose(active["clearance_tolerance_m"].astype(float), float(clearance))]
            counts = {name: int((active["size_class"] == name).sum()) if not active.empty else 0 for name in ["small", "medium", "large", "very_large"]}
            title.SetInput(f"Build {world.build} | cells {current_resolution[0]:g} m | clearance <= {cv} | showing {next(iter(visible_sizes)).replace('_',' ').title()} | counts S {counts['small']} M {counts['medium']} L {counts['large']} V {counts['very_large']} | Z x{zex[0]:g}{extra}")
        elif model == "local_multiscale_relief":
            relief = current_relief_tolerance[0]
            rv = "?" if relief is None else f"{relief:g} m"
            title.SetInput(f"Build {world.build} | cells {current_resolution[0]:g} m | local relief <= {rv} | Z x{zex[0]:g}{extra}")
        else:
            if current_platform_elevation[0] is not None and "platform_elevation_m" in subset.columns:
                subset = subset[np.isclose(subset["platform_elevation_m"].astype(float), current_platform_elevation[0])]
            step = None if subset.empty else float(subset.iloc[0].get("vertical_step_m", float("nan")))
            st = "?" if step is None or not np.isfinite(step) else f"{step:g}"
            plane = "legacy" if current_platform_elevation[0] is None else f"{current_platform_elevation[0]:g} m"
            title.SetInput(f"Build {world.build} | cells {current_resolution[0]:g} m | platform Z {plane} | sweep step {st} m | Z x{zex[0]:g}{extra}")

    pivot_mode = ["view"]
    show_center_outline = [False]

    def update_help():
        variant_help = ";/' clearance" if model == "horizontal_plane_fit" else (";/' relief" if model == "local_multiscale_relief" else ";/' platform Z")
        line1 = f"Mouse orbit/pan/zoom/pick | Shift fine | Pivot {pivot_mode[0].title()} (P cycles View/Cursor/Selection)"
        line2 = f"[ ] resolution | {variant_help} | S/M/L/V choose one size | B rectangles | D center diagnostic | R/W/T layers | C/Home plan | F focus | I isolate | Esc clear"
        help_text.SetInput(_wrapped(line1, 118) + "\n" + _wrapped(line2, 118))

    def update_selected_text():
        row = selected_row()
        if row is None:
            selected.SetInput(_wrapped("Click a suitability region to inspect it; strong rectangles show concrete reference footprints", 118))
            return
        iso = " | isolated" if isolate_selected[0] else ""
        if model == "horizontal_plane_fit":
            selected.SetInput(_wrapped(
                f"{row.surface_id} | {row.size_class}{iso} | reference {row.core_width_foundations:g} x {row.core_length_foundations:g} foundations | "
                f"placement-zone {row.placement_zone_area_m2:,.0f} m2 | mean clearance min/med/max "
                f"{row.min_mean_clearance_m:.1f}/{row.median_mean_clearance_m:.1f}/{row.max_mean_clearance_m:.1f} m | "
                f"edge mean med {row.median_edge_mean_clearance_m:.1f} m | known {row.median_terrain_known_fraction:.0%} | "
                f"overhead ambiguity {row.median_overhead_ambiguous_fraction:.0%} | rectangles {int(row.rectangle_candidate_count)} | conf {row.mean_terrain_confidence:.2f}", 118))
        elif model == "local_multiscale_relief":
            selected.SetInput(_wrapped(
                f"{row.surface_id} | {row.size_class}{iso} | reference {row.core_width_foundations:g} x {row.core_length_foundations:g} foundations | "
                f"placement-zone {row.placement_zone_area_m2:,.0f} m2 | local relief min/med/max "
                f"{row.min_local_relief_m:.1f}/{row.median_local_relief_m:.1f}/{row.max_local_relief_m:.1f} m | "
                f"rectangle candidates {int(row.rectangle_candidate_count)} | conf {row.mean_terrain_confidence:.2f}", 118))
        elif hasattr(row, "platform_elevation_m"):
            selected.SetInput(_wrapped(
                f"{row.surface_id} | {row.size_class} / {row.shape_class}{iso} | "
                f"core {row.core_width_foundations:g} x {row.core_length_foundations:g} foundations | "
                f"area {row.contiguous_area_m2:,.0f} m2 | platform Z {row.platform_elevation_m:g} m | "
                f"clearance med/p90/max {row.median_platform_clearance_m:.1f}/{row.p90_platform_clearance_m:.1f}/{row.max_platform_clearance_m:.1f} m", 118))
        else:
            selected.SetInput(_wrapped(f"{row.surface_id} | {row.size_class}{iso} | area {row.contiguous_area_m2:,.0f} m2", 118))

    def build_base_surface_layers():
        base_actor, rows = _surface_actor(world, surfaces, Path(surface_dir), current_resolution[0], visible_sizes,
                                          platform_elevation_m=current_platform_elevation[0], local_relief_tolerance_m=current_relief_tolerance[0], clearance_tolerance_m=current_clearance_tolerance[0])
        outline_actor, _ = _surface_outline_actor(world, surfaces, Path(surface_dir), current_resolution[0], visible_sizes,
                                                  platform_elevation_m=current_platform_elevation[0], local_relief_tolerance_m=current_relief_tolerance[0], clearance_tolerance_m=current_clearance_tolerance[0],
                                                  color=(0.07, 0.07, 0.07), opacity=0.75, line_width=0.8)
        rows_holder[0] = rows
        add_actor("base", base_actor)
        if base_actor is not None and model in {"local_multiscale_relief", "horizontal_plane_fit"}:
            base_actor.GetProperty().SetOpacity(0.28)
        add_actor("outline", outline_actor)
        if model in {"local_multiscale_relief", "horizontal_plane_fit"}:
            center_outline, _ = _surface_outline_actor(world, surfaces, Path(surface_dir), current_resolution[0], visible_sizes,
                                                        platform_elevation_m=current_platform_elevation[0], local_relief_tolerance_m=current_relief_tolerance[0], clearance_tolerance_m=current_clearance_tolerance[0],
                                                        color=(0.2, 0.45, 0.2), opacity=0.65, line_width=0.7, layer="labels")
            add_actor("center_outline", center_outline)
            if center_outline is not None: center_outline.SetVisibility(1 if show_center_outline[0] else 0)
            rect_actor = _rectangle_actor(Path(surface_dir), current_resolution[0], visible_sizes,
                                          current_relief_tolerance[0], current_clearance_tolerance[0], candidate_ranks={1},
                                          color=(1.0, 1.0, 1.0), opacity=0.95, line_width=2.0)
            add_actor("rectangles", rect_actor)

    def build_selected_layers():
        remove_actor("selected_fill"); remove_actor("selected_outline"); remove_actor("selected_rectangles")
        row = selected_row()
        if row is None:
            selected_surface_id[0] = None
            return
        sid = {str(row.surface_id)}
        sel_fill, _ = _surface_actor(world, surfaces, Path(surface_dir), current_resolution[0], surface_ids=sid,
                                     platform_elevation_m=current_platform_elevation[0], local_relief_tolerance_m=current_relief_tolerance[0], clearance_tolerance_m=current_clearance_tolerance[0])
        sel_outline, _ = _surface_outline_actor(world, surfaces, Path(surface_dir), current_resolution[0], surface_ids=sid,
                                                platform_elevation_m=current_platform_elevation[0], local_relief_tolerance_m=current_relief_tolerance[0], clearance_tolerance_m=current_clearance_tolerance[0],
                                                color=(1.0, 1.0, 1.0), opacity=1.0, line_width=3.0)
        if sel_fill is not None:
            sel_fill.GetProperty().SetOpacity(0.65 if model in {"local_multiscale_relief", "horizontal_plane_fit"} else 0.95)
            add_actor("selected_fill", sel_fill)
        if sel_outline is not None: add_actor("selected_outline", sel_outline)
        if model in {"local_multiscale_relief", "horizontal_plane_fit"}:
            sel_rect = _rectangle_actor(Path(surface_dir), current_resolution[0], surface_ids=sid,
                                        local_relief_tolerance_m=current_relief_tolerance[0], clearance_tolerance_m=current_clearance_tolerance[0], candidate_ranks={1,2,3},
                                        color=(1.0, 1.0, 1.0), opacity=1.0, line_width=3.5)
            add_actor("selected_rectangles", sel_rect)

    def sync_surface_visibility():
        base = actors.get("base")
        outline = actors.get("outline")
        rectangles = actors.get("rectangles")
        center_outline = actors.get("center_outline")
        sel_fill = actors.get("selected_fill")
        sel_outline = actors.get("selected_outline")
        sel_rectangles = actors.get("selected_rectangles")
        has_sel = selected_row() is not None
        if base is not None:
            base.SetVisibility(0 if isolate_selected[0] and has_sel else 1)
            base.GetProperty().SetOpacity(0.30 if has_sel and not isolate_selected[0] else 0.72)
        if outline is not None:
            outline.SetVisibility(0 if isolate_selected[0] and has_sel else 1)
            outline.GetProperty().SetOpacity(0.55 if has_sel and not isolate_selected[0] else 0.95)
        if rectangles is not None:
            rectangles.SetVisibility(0 if isolate_selected[0] and has_sel else 1)
        if center_outline is not None:
            center_outline.SetVisibility(1 if show_center_outline[0] and not (isolate_selected[0] and has_sel) else 0)
        if sel_fill is not None:
            sel_fill.SetVisibility(1 if has_sel else 0)
        if sel_outline is not None:
            sel_outline.SetVisibility(1 if has_sel else 0)
        if sel_rectangles is not None:
            sel_rectangles.SetVisibility(1 if has_sel else 0)

    def rebuild_surface():
        remove_all_surface_actors()
        build_base_surface_layers()
        if selected_surface_id[0] is not None and selected_row() is None:
            selected_surface_id[0] = None
            selected_world_point[0] = None
            isolate_selected[0] = False
        build_selected_layers()
        sync_surface_visibility()
        update_title(); update_help(); update_selected_text(); window.Render()

    def apply_z(value: float):
        zex[0] = max(0.5, min(8.0, float(value)))
        for actor in [terrain, water, resource_actor, actors.get("base"), actors.get("outline"), actors.get("center_outline"), actors.get("rectangles"), actors.get("selected_fill"), actors.get("selected_outline"), actors.get("selected_rectangles")]:
            set_actor_scale(actor)
        update_title(); renderer.ResetCameraClippingRange(); window.Render()

    slider_widgets = []
    if not offscreen:
        nav_state = interaction_style._satisfactory_nav_state
        specs = [
            ("Motion", 1.0, 20.0, nav_state["motion"], 0.975, interaction_style._satisfactory_set_motion, 1),
            ("Wheel", 0.1, 2.0, nav_state["wheel"], 0.935, interaction_style._satisfactory_set_wheel, 2),
            ("Shift", 0.05, 0.5, nav_state["fine"], 0.895, interaction_style._satisfactory_set_fine, 2),
            ("Z", 0.5, 5.0, zex[0], 0.855, apply_z, 1),
        ]
        for spec in specs:
            slider_widgets.append(_make_slider(interactor, *spec))

    def on_key(obj, event):
        key = obj.GetKeySym().lower()
        if key == "r":
            resource_actor.SetVisibility(not resource_actor.GetVisibility())
        elif key == "w" and water is not None:
            water.SetVisibility(not water.GetVisibility())
        elif key == "t":
            terrain.SetVisibility(not terrain.GetVisibility())
        elif key in {"s", "m", "l", "v"}:
            name = {"s": "small", "m": "medium", "l": "large", "v": "very_large"}[key]
            visible_sizes.clear(); visible_sizes.add(name)
            selected_surface_id[0] = None; selected_world_point[0] = None; isolate_selected[0] = False
            rebuild_surface(); return
        elif key in {"bracketleft", "comma"} and len(resolutions) > 1:
            resolution_index[0] = (resolution_index[0] - 1) % len(resolutions)
            current_resolution[0] = resolutions[resolution_index[0]]
            ss = variant_values_for(current_resolution[0])
            if model == "horizontal_plane_fit": current_clearance_tolerance[0] = (4.0 if any(np.isclose(x,4.0) for x in ss) else (ss[len(ss)//2] if ss else None))
            elif model == "local_multiscale_relief": current_relief_tolerance[0] = (8.0 if any(np.isclose(x,8.0) for x in ss) else (ss[len(ss)//2] if ss else None))
            else: current_platform_elevation[0] = max(ss) if ss else None
            selected_surface_id[0] = None; selected_world_point[0] = None; isolate_selected[0] = False
            rebuild_surface(); return
        elif key in {"bracketright", "period"} and len(resolutions) > 1:
            resolution_index[0] = (resolution_index[0] + 1) % len(resolutions)
            current_resolution[0] = resolutions[resolution_index[0]]
            ss = variant_values_for(current_resolution[0])
            if model == "horizontal_plane_fit": current_clearance_tolerance[0] = (4.0 if any(np.isclose(x,4.0) for x in ss) else (ss[len(ss)//2] if ss else None))
            elif model == "local_multiscale_relief": current_relief_tolerance[0] = (8.0 if any(np.isclose(x,8.0) for x in ss) else (ss[len(ss)//2] if ss else None))
            else: current_platform_elevation[0] = max(ss) if ss else None
            selected_surface_id[0] = None; selected_world_point[0] = None; isolate_selected[0] = False
            rebuild_surface(); return
        elif key in {"semicolon"}:
            ss = variant_values_for(current_resolution[0])
            if ss:
                cur = current_clearance_tolerance[0] if model == "horizontal_plane_fit" else (current_relief_tolerance[0] if model == "local_multiscale_relief" else current_platform_elevation[0])
                i = ss.index(cur) if cur in ss else len(ss) - 1
                if model == "horizontal_plane_fit": current_clearance_tolerance[0] = ss[(i - 1) % len(ss)]
                elif model == "local_multiscale_relief": current_relief_tolerance[0] = ss[(i - 1) % len(ss)]
                else: current_platform_elevation[0] = ss[(i - 1) % len(ss)]
                selected_surface_id[0] = None; selected_world_point[0] = None; isolate_selected[0] = False
                rebuild_surface(); return
        elif key in {"apostrophe", "quotedbl"}:
            ss = variant_values_for(current_resolution[0])
            if ss:
                cur = current_clearance_tolerance[0] if model == "horizontal_plane_fit" else (current_relief_tolerance[0] if model == "local_multiscale_relief" else current_platform_elevation[0])
                i = ss.index(cur) if cur in ss else 0
                if model == "horizontal_plane_fit": current_clearance_tolerance[0] = ss[(i + 1) % len(ss)]
                elif model == "local_multiscale_relief": current_relief_tolerance[0] = ss[(i + 1) % len(ss)]
                else: current_platform_elevation[0] = ss[(i + 1) % len(ss)]
                selected_surface_id[0] = None; selected_world_point[0] = None; isolate_selected[0] = False
                rebuild_surface(); return
        elif key == "d":
            show_center_outline[0] = not show_center_outline[0]
            sync_surface_visibility(); update_help()
        elif key == "p":
            modes = ["view", "cursor", "selection"]
            pivot_mode[0] = modes[(modes.index(pivot_mode[0]) + 1) % len(modes)]
            update_help()
        elif key == "b" and actors.get("rectangles") is not None:
            actors["rectangles"].SetVisibility(not actors["rectangles"].GetVisibility())
        elif key in {"plus", "equal", "kp_add"}:
            apply_z(min(5.0, zex[0] * 2.0))
            if slider_widgets:
                slider_widgets[-1][1].SetValue(zex[0])
        elif key in {"minus", "underscore", "kp_subtract"}:
            apply_z(max(0.5, zex[0] / 2.0))
            if slider_widgets:
                slider_widgets[-1][1].SetValue(zex[0])
        elif key in {"c", "home"}:
            _reset_plan_camera(renderer, terrain)
        elif key == "f" and selected_world_point[0] is not None:
            camera = renderer.GetActiveCamera()
            old_focal = np.array(camera.GetFocalPoint(), dtype=float)
            old_pos = np.array(camera.GetPosition(), dtype=float)
            offset = old_pos - old_focal
            target = np.array(selected_world_point[0], dtype=float)
            camera.SetFocalPoint(*target)
            camera.SetPosition(*(target + offset))
            renderer.ResetCameraClippingRange()
        elif key == "i" and selected_row() is not None:
            isolate_selected[0] = not isolate_selected[0]
            sync_surface_visibility(); update_title(); update_selected_text()
        elif key in {"escape", "delete", "backspace"}:
            selected_surface_id[0] = None
            selected_world_point[0] = None
            isolate_selected[0] = False
            build_selected_layers(); sync_surface_visibility(); update_title(); update_selected_text()
        window.Render()

    picker = vtk.vtkCellPicker(); picker.SetTolerance(0.0005)
    pivot_picker = vtk.vtkCellPicker(); pivot_picker.SetTolerance(0.0005)

    def update_orbit_pivot(obj, event):
        """Choose orbit pivot at interaction start without recentering on whole geometry."""
        mode = pivot_mode[0]
        target = None
        if mode == "selection" and selected_world_point[0] is not None:
            target = selected_world_point[0]
        else:
            if mode == "cursor":
                px, py = interactor.GetEventPosition()
            else:
                w, h = window.GetSize()
                px, py = int(w * 0.5), int(h * 0.5)
            if pivot_picker.Pick(px, py, 0, renderer):
                target = pivot_picker.GetPickPosition()
        if target is not None:
            _set_camera_pivot(renderer.GetActiveCamera(), target)
            renderer.ResetCameraClippingRange()

    def keep_world_up(obj=None, event=None):
        renderer.ResetCameraClippingRange()

    def on_pick(obj, event):
        x, y = interactor.GetEventPosition()
        picked = picker.Pick(x, y, 0, renderer)
        if not picked:
            return
        actor = picker.GetActor()
        if actor not in {actors.get("base"), actors.get("selected_fill"), actors.get("outline"), actors.get("selected_outline")}:
            return
        poly = actor.GetMapper().GetInput()
        arr = poly.GetCellData().GetArray("surface_row")
        cid = picker.GetCellId()
        if arr is None or cid < 0 or cid >= arr.GetNumberOfTuples():
            return
        idx = int(arr.GetTuple1(cid))
        rows = rows_holder[0]
        if 0 <= idx < len(rows):
            r = rows[idx]
            selected_surface_id[0] = str(r.surface_id)
            selected_world_point[0] = (float(r.centroid_east_m), float(r.centroid_north_m), float(getattr(r, "platform_elevation_m", 0.0) if model != "local_multiscale_relief" else 0.0))
            build_selected_layers(); sync_surface_visibility(); update_title(); update_selected_text(); window.Render()

    interactor.AddObserver("KeyPressEvent", on_key)
    interactor.AddObserver("LeftButtonPressEvent", update_orbit_pivot, 1.0)
    interactor.AddObserver("LeftButtonPressEvent", on_pick, 0.5)

    build_base_surface_layers()
    build_selected_layers()
    sync_surface_visibility()
    camera = _reset_plan_camera(renderer, terrain)
    distance = max(float(camera.GetDistance()), 1.0)
    camera.SetClippingRange(max(0.1, distance * 0.002), distance * 8.0)
    update_title(); update_help(); update_selected_text(); window.Render()

    if screenshot:
        _write_png(window, Path(screenshot))
    if not offscreen:
        interactor.Initialize(); interactor.Start()
