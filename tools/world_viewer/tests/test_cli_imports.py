import sys

def test_cli_does_not_eagerly_import_trimesh():
    sys.modules.pop("trimesh", None)
    sys.modules.pop("world_viewer.cli", None)
    import world_viewer.cli  # noqa: F401
    assert "trimesh" not in sys.modules
