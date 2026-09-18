from world_viewer.vtk_view import _add_overlay_actor


class RendererWithViewProp:
    def __init__(self):
        self.added = []

    def AddViewProp(self, actor):
        self.added.append(actor)


class RendererWithActor2D(RendererWithViewProp):
    def AddActor2D(self, actor):
        self.added.append(("2d", actor))


def test_overlay_actor_falls_back_to_add_view_prop():
    renderer = RendererWithViewProp()
    actor = object()
    _add_overlay_actor(renderer, actor)
    assert renderer.added == [actor]


def test_overlay_actor_prefers_add_actor_2d_when_available():
    renderer = RendererWithActor2D()
    actor = object()
    _add_overlay_actor(renderer, actor)
    assert renderer.added == [("2d", actor)]
