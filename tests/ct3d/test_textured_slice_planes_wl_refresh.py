# --------------------------------------------------------------------------
# E5 finalization: immediate Window/Level refresh of E5A textured planes.
#
# The frame-side methods (on_window_level_changed / _run_scheduled_wl_
# texture_refresh / refresh_slice_textures) are the real, unmodified
# ROIViewerFrame methods, bound onto a SimpleNamespace fake the same way
# test_preview_surface_integration.py's _panel_like() does - so no real
# wx.Frame or running event loop is needed. wx.CallAfter is replaced by a
# recorder so "scheduled" vs "ran" is something the test controls.
# --------------------------------------------------------------------------
import ast
import inspect
import types

import pytest

from plugins.roi_viewer.gui import roi_panel
from plugins.roi_viewer.gui.roi_panel import ROIViewerFrame


@pytest.fixture
def call_after(monkeypatch):
    scheduled = []
    monkeypatch.setattr(roi_panel.wx, "CallAfter", lambda fn, *a, **k: scheduled.append((fn, a, k)))
    return scheduled


def _frame_like(show_texture=True, position=(1.0, 2.0, 3.0)):
    fake = types.SimpleNamespace()
    fake.show_texture_planes = show_texture
    fake._texture_planes_position = position
    fake._wl_texture_refresh_scheduled = False
    fake.built_at = []
    fake.renders = 0
    fake.update_textured_slice_planes = lambda pos: fake.built_at.append(pos)

    def _render():
        fake.renders += 1

    fake.request_render = _render
    for name in ("on_window_level_changed", "_run_scheduled_wl_texture_refresh", "refresh_slice_textures"):
        setattr(fake, name, getattr(ROIViewerFrame, name).__get__(fake))
    return fake


def test_wl_change_ignored_when_texture_mode_off(call_after):
    frame = _frame_like(show_texture=False)
    frame.on_window_level_changed()
    assert call_after == []


def test_wl_change_ignored_before_first_texture_build(call_after):
    frame = _frame_like(position=None)
    frame.on_window_level_changed()
    assert call_after == []


def test_wl_drag_coalesces_to_one_refresh(call_after):
    """Native W/L dragging sends the topic on every mouse-move."""
    frame = _frame_like()
    for _ in range(5):
        frame.on_window_level_changed()
    assert len(call_after) == 1


def test_scheduled_refresh_rebuilds_at_texture_position(call_after):
    frame = _frame_like(position=(4.0, 5.0, 6.0))
    frame.on_window_level_changed()
    fn, args, kwargs = call_after[0]
    fn(*args, **kwargs)
    assert frame.built_at == [(4.0, 5.0, 6.0)]
    assert frame.renders == 1
    assert frame._wl_texture_refresh_scheduled is False


def test_next_change_after_refresh_schedules_again(call_after):
    frame = _frame_like()
    frame.on_window_level_changed()
    fn, args, kwargs = call_after[0]
    fn(*args, **kwargs)
    frame.on_window_level_changed()
    assert len(call_after) == 2


def test_refresh_is_noop_without_position():
    frame = _frame_like(position=None)
    assert frame.refresh_slice_textures() is False
    assert frame.built_at == []


def test_main_subscribes_and_unsubscribes_wl_topic():
    import plugins.roi_viewer.main as main_mod

    sig = inspect.signature(main_mod._on_window_level_changed)
    assert list(sig.parameters) == ["window", "level"]

    tree = ast.parse(inspect.getsource(main_mod))
    pairs = {"subscribe": set(), "unsubscribe": set()}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in pairs
            and len(node.args) == 2
            and isinstance(node.args[0], ast.Name)
            and isinstance(node.args[1], ast.Constant)
        ):
            pairs[node.func.attr].add((node.args[0].id, node.args[1].value))
    entry = ("_on_window_level_changed", "Update window level value")
    assert entry in pairs["subscribe"]
    assert entry in pairs["unsubscribe"]


def test_slice_holds_new_wl_when_update_topic_fires(real_slice_and_project_singleton):
    """The ordering guarantee the subscription relies on, checked against
    the REAL Slice.UpdateWindowLevelBackground subscriber: when "Update
    window level value" fires (sent after "Bright and contrast adjustment
    image" at every real sender), Slice() already stores the new W/L."""
    from invesalius.pubsub import pub as Publisher

    s, proj, Project, Slice = real_slice_and_project_singleton
    Slice.instance = s
    Project.instance = proj
    seen = []
    # Shared session-wide Slice(): restore W/L afterwards so no later test
    # inherits it. Slice.__init__ never creates window_width/window_level -
    # only UpdateWindowLevelBackground() (or a project load) does - so
    # "absent" is a real state to restore, not just a value.
    missing = object()
    original = {name: getattr(s, name, missing) for name in ("window_width", "window_level")}

    def probe(window, level):
        seen.append((Slice().window_width, Slice().window_level))

    Publisher.subscribe(probe, "Update window level value")
    try:
        Publisher.sendMessage("Bright and contrast adjustment image", window=1234, level=-56)
        Publisher.sendMessage("Update window level value", window=1234, level=-56)
    finally:
        Publisher.unsubscribe(probe, "Update window level value")
        for name, value in original.items():
            if value is missing:
                s.__dict__.pop(name, None)
            else:
                setattr(s, name, value)

    assert seen == [(1234, -56)]


def test_enable_texture_uses_c8_plane_position_not_live_crosshair(monkeypatch):
    """With Sync 2D->3D off, C8's planes stay frozen while
    _last_cross_focal_point keeps moving - enabling texture mode must
    build where the planes actually are."""
    from vtkmodules.vtkRenderingCore import vtkRenderer

    from plugins.roi_viewer.core.slice_planes_3d import SlicePlanes3D
    from plugins.roi_viewer.core.textured_slice_planes_3d import TexturedSlicePlanes3D
    from plugins.roi_viewer.gui.interaction_panel import InteractionPanel
    from plugins.roi_viewer.interface import view_interface

    renderer = vtkRenderer()
    monkeypatch.setattr(
        view_interface.ViewInterface, "get_volume_viewer",
        lambda self: types.SimpleNamespace(ren=renderer),
    )

    # C8's planes live in the y-flipped 3D view frame; texture building
    # selects voxels, so the toggle must hand it the SLICE-frame position
    # (2, 2, 2) - see core/coordinates.py (updated 30/09/2026).
    planes = SlicePlanes3D()
    planes.attach(renderer)
    planes.set_bounds((0.0, 10.0, -10.0, 0.0, 0.0, 10.0))
    planes.update_position((2.0, -2.0, 2.0))

    built = []
    controller = types.SimpleNamespace(
        show_texture_planes=False,
        show_slice_planes=True,
        slice_planes_3d=planes,
        textured_slice_planes_3d=TexturedSlicePlanes3D(),
        _last_cross_focal_point=(9.0, 9.0, 9.0),
        update_textured_slice_planes=lambda pos: built.append(tuple(pos)),
        apply_slice_plane_visibility=lambda: None,
        request_render=lambda: None,
    )
    panel = types.SimpleNamespace(
        controller=controller,
        cb_texture_planes=types.SimpleNamespace(GetValue=lambda: True),
    )
    InteractionPanel._on_texture_planes_toggle.__get__(panel)(None)

    assert built == [(2.0, 2.0, 2.0)]
