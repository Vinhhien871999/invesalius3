# --------------------------------------------------------------------------
# E5A visibility orchestration - regression for a real manual-QA bug
# (E5-A FAIL): with "Show CT texture on slice planes" ON, the coloured C8
# planes stayed visible on top of the textures, because every crosshair
# update called slice_planes_3d.set_visible(show_slice_planes) without
# looking at texture mode.
#
# Runs the REAL ROIViewerFrame.on_cross_focal_point_changed() /
# update_textured_slice_planes() / apply_slice_plane_visibility() and the
# REAL InteractionPanel checkbox handlers, bound onto SimpleNamespace fakes
# (same technique as test_preview_surface_integration.py), with real
# SlicePlanes3D / TexturedSlicePlanes3D / CrosshairMarker3D in a real
# vtkRenderer. Only the volume-viewer lookup and Slice().GetSlices() are
# substituted (real renderer, real converters.to_vtk() images).
# --------------------------------------------------------------------------
import types

import numpy as np
import pytest

from plugins.roi_viewer.core.marker_3d import CrosshairMarker3D
from plugins.roi_viewer.core.slice_planes_3d import SlicePlanes3D
from plugins.roi_viewer.core.surface_clipping_3d import SurfaceClipping3D
from plugins.roi_viewer.core.textured_slice_planes_3d import TexturedSlicePlanes3D
from plugins.roi_viewer.gui.interaction_panel import InteractionPanel
from plugins.roi_viewer.gui.roi_panel import ROIViewerFrame


@pytest.fixture
def env(monkeypatch, real_slice_and_project_singleton):
    from vtkmodules.vtkRenderingCore import vtkRenderer

    from invesalius.data import converters
    from plugins.roi_viewer.interface import project_interface, view_interface

    s, proj, Project, Slice = real_slice_and_project_singleton
    Slice.instance = s
    Project.instance = proj

    renderer = vtkRenderer()
    monkeypatch.setattr(
        view_interface.ViewInterface, "get_volume_viewer",
        lambda self: types.SimpleNamespace(ren=renderer),
    )
    monkeypatch.setattr(
        project_interface.ProjectInterface, "world_to_voxel",
        lambda self, x, y, z: (int(z), int(y), int(x)),
    )
    image = np.full((11, 11), 100, dtype=np.uint8)
    monkeypatch.setattr(
        s, "GetSlices",
        lambda orientation, index, *a: converters.to_vtk(image, (1.0, 1.0, 1.0), index, orientation),
    )
    return renderer


def _make_frame():
    frame = types.SimpleNamespace(
        project_loaded=True,
        sync_mgr=types.SimpleNamespace(sync_2d_3d=True),
        marker_3d=CrosshairMarker3D(),
        slice_planes_3d=SlicePlanes3D(),
        textured_slice_planes_3d=TexturedSlicePlanes3D(),
        surface_clipping_3d=SurfaceClipping3D(),
        show_slice_planes=True,
        show_texture_planes=False,
        _last_cross_focal_point=None,
        _texture_planes_position=None,
        _compute_volume_bounds=lambda: (0.0, 10.0, 0.0, 10.0, 0.0, 10.0),
        request_render=lambda: None,
    )
    for name in ("on_cross_focal_point_changed", "update_textured_slice_planes", "apply_slice_plane_visibility"):
        setattr(frame, name, getattr(ROIViewerFrame, name).__get__(frame))
    return frame


def _make_panel(frame):
    panel = types.SimpleNamespace(controller=frame, texture_checked=False)
    panel.cb_texture_planes = types.SimpleNamespace(GetValue=lambda: panel.texture_checked)
    toggle = InteractionPanel._on_texture_planes_toggle.__get__(panel)
    master = InteractionPanel._on_show_slice_planes_changed.__get__(panel)

    def set_texture(on):
        panel.texture_checked = on
        toggle(None)

    def set_master(on):
        master(types.SimpleNamespace(IsChecked=lambda: on))

    panel.set_texture = set_texture
    panel.set_master = set_master
    return panel


def _visible(planes):
    return sum(entry["actor"].GetVisibility() for entry in planes._planes.values())


def _setup(env):
    frame = _make_frame()
    panel = _make_panel(frame)
    frame.on_cross_focal_point_changed((5.0, 5.0, 5.0))
    return frame, panel


def test_texture_off_geometric_on(env):
    frame, panel = _setup(env)
    assert _visible(frame.slice_planes_3d) == 3
    assert _visible(frame.textured_slice_planes_3d) == 0


def test_texture_on_hides_geometric_planes(env):
    frame, panel = _setup(env)
    panel.set_texture(True)
    assert _visible(frame.slice_planes_3d) == 0


def test_texture_on_shows_textured_planes(env):
    frame, panel = _setup(env)
    panel.set_texture(True)
    assert frame.textured_slice_planes_3d.actor_count == 3
    assert _visible(frame.textured_slice_planes_3d) == 3


def test_texture_off_restores_geometric_planes(env):
    frame, panel = _setup(env)
    panel.set_texture(True)
    panel.set_texture(False)
    assert _visible(frame.slice_planes_3d) == 3
    assert _visible(frame.textured_slice_planes_3d) == 0


def test_crosshair_update_does_not_reshow_geometric_planes_in_texture_mode(env):
    """The exact operator-observed bug."""
    frame, panel = _setup(env)
    panel.set_texture(True)
    for pos in ((2.0, 3.0, 4.0), (7.0, 1.0, 9.0), (5.0, 5.0, 5.0)):
        frame.on_cross_focal_point_changed(pos)
        assert _visible(frame.slice_planes_3d) == 0
        assert _visible(frame.textured_slice_planes_3d) == 3


def test_master_slice_plane_visibility_off_hides_both_modes(env):
    """Case D: master OFF + texture ON -> nothing drawn; texture mode
    never bypasses "Show slice planes in 3D"."""
    frame, panel = _setup(env)
    panel.set_master(False)
    assert (_visible(frame.slice_planes_3d), _visible(frame.textured_slice_planes_3d)) == (0, 0)

    panel.set_texture(True)
    assert (_visible(frame.slice_planes_3d), _visible(frame.textured_slice_planes_3d)) == (0, 0)

    frame.on_cross_focal_point_changed((3.0, 3.0, 3.0))
    assert (_visible(frame.slice_planes_3d), _visible(frame.textured_slice_planes_3d)) == (0, 0)

    panel.set_master(True)
    assert (_visible(frame.slice_planes_3d), _visible(frame.textured_slice_planes_3d)) == (0, 3)


def test_master_on_with_texture_on_does_not_show_geometric(env):
    frame, panel = _setup(env)
    panel.set_texture(True)
    panel.set_master(False)
    panel.set_master(True)
    assert _visible(frame.slice_planes_3d) == 0
    assert _visible(frame.textured_slice_planes_3d) == 3


def test_repeated_texture_toggle_no_duplicate_actor(env):
    frame, panel = _setup(env)
    for _ in range(4):
        panel.set_texture(True)
        frame.on_cross_focal_point_changed((4.0, 6.0, 2.0))
        assert (_visible(frame.slice_planes_3d), _visible(frame.textured_slice_planes_3d)) == (0, 3)
        panel.set_texture(False)
        assert (_visible(frame.slice_planes_3d), _visible(frame.textured_slice_planes_3d)) == (3, 0)
    # 3 geometric + 3 textured + 1 marker, never more.
    assert env.GetActors().GetNumberOfItems() == 7


def test_plugin_close_reopen_visibility_clean(env):
    frame, panel = _setup(env)
    panel.set_texture(True)
    # Close: the real _on_close() detaches every renderer-attached object.
    frame.marker_3d.detach()
    frame.slice_planes_3d.detach()
    frame.textured_slice_planes_3d.detach()
    assert env.GetActors().GetNumberOfItems() == 0

    # Reopen: a fresh frame starts with texture mode OFF.
    frame2, panel2 = _setup(env)
    assert (_visible(frame2.slice_planes_3d), _visible(frame2.textured_slice_planes_3d)) == (3, 0)
    assert env.GetActors().GetNumberOfItems() == 4  # 3 geometric + 1 marker
