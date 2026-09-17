# --------------------------------------------------------------------------
# Persistent tests for C8 (Sync 2D->3D) and F3 (annotation position
# policy) - CT3D_P11_TEST_AUTOMATION, Sections XIII/XV.
#
# roi_panel.ROIViewerFrame.on_cross_focal_point_changed() and
# .get_current_reference_position() are real bound methods on a wx.Frame
# subclass, but each only reads/writes a small, fully-enumerated set of
# `self` attributes (verified by reading the full method body - see the
# comments below). Rather than constructing a full wx.Frame (heavy,
# requires the whole app bootstrap used by Phase 08/09/10's standalone
# scripts), these tests call the UNBOUND real method against a minimal
# stand-in object carrying exactly those attributes - this exercises the
# real, unmodified production code path (not a reimplementation), just
# without the unrelated wx widget tree around it. core/marker_3d.
# CrosshairMarker3D itself (pure VTK, no wx) is exercised for real with a
# real vtkRenderer - no mocking there.
# --------------------------------------------------------------------------
import inspect
import types
from unittest.mock import patch

import pytest

from plugins.roi_viewer.core.marker_3d import CrosshairMarker3D
from plugins.roi_viewer.core.slice_planes_3d import SlicePlanes3D
from plugins.roi_viewer.core.sync_2d3d import SyncManager2D3D
from plugins.roi_viewer.gui import roi_panel


# ---------------------------------------------------------------------
# CrosshairMarker3D - real VTK, no wx (integration: needs a real VTK
# renderer object, but no GUI/mouse)
# ---------------------------------------------------------------------

pytestmark = pytest.mark.integration


@pytest.fixture
def vtk_renderer():
    from vtkmodules.vtkRenderingCore import vtkRenderer

    return vtkRenderer()


def test_sync_t3_update_position_never_creates_a_second_actor(vtk_renderer):
    marker = CrosshairMarker3D()
    assert marker.attach(vtk_renderer)
    for i in range(20):
        marker.update_position(float(i), float(i) * 2, float(i) * 3)
    assert vtk_renderer.GetActors().GetNumberOfItems() == 1
    assert marker.get_position() == pytest.approx((19.0, 38.0, 57.0))


def test_sync_t4_detach_removes_the_actor(vtk_renderer):
    marker = CrosshairMarker3D()
    marker.attach(vtk_renderer)
    marker.update_position(1.0, 2.0, 3.0)
    assert vtk_renderer.GetActors().GetNumberOfItems() == 1
    marker.detach()
    assert vtk_renderer.GetActors().GetNumberOfItems() == 0
    assert marker.get_position() is None


def test_sync_t4b_detach_is_idempotent(vtk_renderer):
    marker = CrosshairMarker3D()
    marker.attach(vtk_renderer)
    marker.detach()
    marker.detach()  # must not raise


def test_marker_reattach_to_new_renderer_leaves_no_orphan_in_the_old_one():
    from vtkmodules.vtkRenderingCore import vtkRenderer

    renderer_a = vtkRenderer()
    renderer_b = vtkRenderer()
    marker = CrosshairMarker3D()
    marker.attach(renderer_a)
    marker.update_position(1.0, 1.0, 1.0)
    marker.attach(renderer_b)  # simulates closing/reopening the plugin window
    assert renderer_a.GetActors().GetNumberOfItems() == 0  # no orphan left behind
    assert renderer_b.GetActors().GetNumberOfItems() == 1


def test_marker_hide_keeps_actor_but_not_visible(vtk_renderer):
    marker = CrosshairMarker3D()
    marker.attach(vtk_renderer)
    marker.update_position(0.0, 0.0, 0.0)
    assert marker.visible is True
    marker.hide()
    assert marker.visible is False
    assert vtk_renderer.GetActors().GetNumberOfItems() == 1  # actor still exists, just hidden


# ---------------------------------------------------------------------
# on_cross_focal_point_changed - real bound method, minimal fake `self`
# ---------------------------------------------------------------------

class _FakeMarker:
    """Records calls instead of touching real VTK - used only for the
    disabled-sync test (SYNC11-T1), where the real method must return
    before ever touching the marker."""

    def __init__(self):
        self.attach_calls = []
        self.update_calls = []

    def attach(self, renderer):
        self.attach_calls.append(renderer)
        return True

    def update_position(self, x, y, z):
        self.update_calls.append((x, y, z))


class _FakePlanes:
    """Records calls instead of touching real VTK - used for the
    disabled-sync test, where the real method must return before ever
    touching the planes."""

    def __init__(self):
        self.attach_calls = []
        self.set_bounds_calls = []
        self.update_calls = []
        self.set_visible_calls = []

    def attach(self, renderer):
        self.attach_calls.append(renderer)
        return True

    def set_bounds(self, bounds):
        self.set_bounds_calls.append(bounds)

    def update_position(self, world_position):
        self.update_calls.append(world_position)

    def set_visible(self, visible):
        self.set_visible_calls.append(visible)


def _fake_frame(project_loaded=True, sync_enabled=True, marker=None, planes=None,
                 show_slice_planes=True):
    fake = types.SimpleNamespace()
    fake.project_loaded = project_loaded
    fake._last_cross_focal_point = None
    fake.sync_mgr = SyncManager2D3D()
    fake.sync_mgr.sync_2d_3d = sync_enabled
    fake.marker_3d = marker if marker is not None else _FakeMarker()
    fake.slice_planes_3d = planes if planes is not None else _FakePlanes()
    fake.show_slice_planes = show_slice_planes
    # Bind the REAL _compute_volume_bounds method - it only reads
    # ProjectInterface() (patched per-test below where real bounds
    # matter), no other `self` state.
    fake._compute_volume_bounds = roi_panel.ROIViewerFrame._compute_volume_bounds.__get__(fake)
    return fake


def _fake_project_interface(shape, spacing):
    """A minimal stand-in for interface/project_interface.ProjectInterface
    exposing exactly what _compute_volume_bounds() calls - get_shape()
    and voxel_to_world() - using the SAME real mapping the real
    ProjectInterface.voxel_to_world() implements (x=sagital*spacing[2],
    y=coronal*spacing[1], z=axial*spacing[0]), so the test's expected
    bounds are computed via that same real, documented convention, not
    a reimplementation with different semantics."""

    def voxel_to_world(axial, coronal, sagital):
        return (sagital * spacing[2], coronal * spacing[1], axial * spacing[0])

    return types.SimpleNamespace(get_shape=lambda: shape, voxel_to_world=voxel_to_world)


def test_sync_t1_disabled_does_not_touch_the_marker():
    fake = _fake_frame(sync_enabled=False)
    roi_panel.ROIViewerFrame.on_cross_focal_point_changed(fake, (1.0, 2.0, 3.0))
    assert fake.marker_3d.attach_calls == []
    assert fake.marker_3d.update_calls == []


def test_sync3d_t1_disabled_does_not_touch_the_slice_planes():
    """Phase 13.5: sync OFF -> event -> slice planes unchanged either
    (same guard as the marker, same event)."""
    fake = _fake_frame(sync_enabled=False)
    roi_panel.ROIViewerFrame.on_cross_focal_point_changed(fake, (1.0, 2.0, 3.0))
    assert fake.slice_planes_3d.attach_calls == []
    assert fake.slice_planes_3d.set_bounds_calls == []
    assert fake.slice_planes_3d.update_calls == []


def test_sync_t1b_disabled_still_tracks_last_cross_focal_point_for_f3():
    """Tracking "where is the crosshair" (used by F3/get_current_reference_position)
    is independent of the Sync 2D->3D checkbox - see the method's own
    docstring."""
    fake = _fake_frame(sync_enabled=False)
    roi_panel.ROIViewerFrame.on_cross_focal_point_changed(fake, (1.0, 2.0, 3.0))
    assert fake._last_cross_focal_point == (1.0, 2.0, 3.0)


def test_sync_t0_not_project_loaded_is_a_full_noop():
    fake = _fake_frame(project_loaded=False, sync_enabled=True)
    roi_panel.ROIViewerFrame.on_cross_focal_point_changed(fake, (1.0, 2.0, 3.0))
    assert fake._last_cross_focal_point is None  # not even tracked
    assert fake.marker_3d.attach_calls == []


def test_sync_t2_enabled_marker_moves_to_the_real_world_position(vtk_renderer):
    """End-to-end through the real method, with a real CrosshairMarker3D
    and real vtkRenderer - only ViewInterface (which needs a real
    top-level wx.Frame's widget tree, out of scope for this test's
    weight) is faked."""
    real_marker = CrosshairMarker3D()
    fake = _fake_frame(sync_enabled=True, marker=real_marker)

    fake_viewer = types.SimpleNamespace(ren=vtk_renderer)
    fake_view_interface_cls = lambda: types.SimpleNamespace(get_volume_viewer=lambda: fake_viewer)

    with patch("plugins.roi_viewer.interface.view_interface.ViewInterface", fake_view_interface_cls):
        with patch("invesalius.pubsub.pub.sendMessage"):  # don't touch real pubsub subscribers
            roi_panel.ROIViewerFrame.on_cross_focal_point_changed(fake, (5.0, 6.0, 7.0))

    assert real_marker.get_position() == pytest.approx((5.0, 6.0, 7.0))
    assert vtk_renderer.GetActors().GetNumberOfItems() == 1  # exactly one actor, no duplicates


# ---------------------------------------------------------------------
# SYNC3D-T2..T9: Phase 13.5 - real SlicePlanes3D driven through the same
# real on_cross_focal_point_changed() event as the marker above.
# ---------------------------------------------------------------------

_TEST_SHAPE = (50, 80, 60)  # (axial, coronal, sagital) voxel counts
_TEST_SPACING = (1.5, 1.0, 0.8)  # (axial, coronal, sagital) mm/voxel


def _attach_real_viewer_and_project(vtk_renderer, shape=_TEST_SHAPE, spacing=_TEST_SPACING):
    """Context data shared by the SYNC3D tests below - a real viewer
    stand-in (just needs .ren) and a real-convention ProjectInterface
    stand-in with a fixed, known shape/spacing."""
    fake_viewer = types.SimpleNamespace(ren=vtk_renderer)
    fake_view_interface_cls = lambda: types.SimpleNamespace(get_volume_viewer=lambda: fake_viewer)
    fake_pi = _fake_project_interface(shape, spacing)
    fake_project_interface_cls = lambda: fake_pi
    return fake_view_interface_cls, fake_project_interface_cls


def test_sync3d_t2_enabled_planes_intersect_event_a(vtk_renderer):
    real_planes = SlicePlanes3D()
    fake = _fake_frame(sync_enabled=True, planes=real_planes)
    view_cls, pi_cls = _attach_real_viewer_and_project(vtk_renderer)

    with patch("plugins.roi_viewer.interface.view_interface.ViewInterface", view_cls):
        with patch("plugins.roi_viewer.interface.project_interface.ProjectInterface", pi_cls):
            with patch("invesalius.pubsub.pub.sendMessage"):
                roi_panel.ROIViewerFrame.on_cross_focal_point_changed(fake, (10.0, 20.0, 30.0))

    assert real_planes.actor_count == 3
    assert real_planes.get_position() == pytest.approx((10.0, 20.0, 30.0))
    axial = real_planes._planes["AXIAL"]["source"]
    coronal = real_planes._planes["CORONAL"]["source"]
    sagital = real_planes._planes["SAGITAL"]["source"]
    assert axial.GetOrigin()[2] == pytest.approx(30.0)
    assert coronal.GetOrigin()[1] == pytest.approx(20.0)
    assert sagital.GetOrigin()[0] == pytest.approx(10.0)


def test_sync3d_t3_event_b_same_actor_ids_new_position(vtk_renderer):
    real_planes = SlicePlanes3D()
    fake = _fake_frame(sync_enabled=True, planes=real_planes)
    view_cls, pi_cls = _attach_real_viewer_and_project(vtk_renderer)

    with patch("plugins.roi_viewer.interface.view_interface.ViewInterface", view_cls):
        with patch("plugins.roi_viewer.interface.project_interface.ProjectInterface", pi_cls):
            with patch("invesalius.pubsub.pub.sendMessage"):
                roi_panel.ROIViewerFrame.on_cross_focal_point_changed(fake, (10.0, 20.0, 30.0))
                actors_a = {name: e["actor"] for name, e in real_planes._planes.items()}
                roi_panel.ROIViewerFrame.on_cross_focal_point_changed(fake, (15.0, 25.0, 35.0))
                actors_b = {name: e["actor"] for name, e in real_planes._planes.items()}

    for name in actors_a:
        assert actors_a[name] is actors_b[name]  # same VTK objects
    assert real_planes.get_position() == pytest.approx((15.0, 25.0, 35.0))


def test_sync3d_t4_many_updates_actor_count_stable(vtk_renderer):
    real_marker = CrosshairMarker3D()
    real_planes = SlicePlanes3D()
    fake = _fake_frame(sync_enabled=True, marker=real_marker, planes=real_planes)
    view_cls, pi_cls = _attach_real_viewer_and_project(vtk_renderer)

    with patch("plugins.roi_viewer.interface.view_interface.ViewInterface", view_cls):
        with patch("plugins.roi_viewer.interface.project_interface.ProjectInterface", pi_cls):
            with patch("invesalius.pubsub.pub.sendMessage"):
                for i in range(60):
                    roi_panel.ROIViewerFrame.on_cross_focal_point_changed(
                        fake, (float(i % 30), float(i % 40), float(i % 20))
                    )

    # 1 marker + 3 planes = 4 actors total, stable regardless of update count.
    assert vtk_renderer.GetActors().GetNumberOfItems() == 4


def test_sync3d_t5_show_planes_off_marker_continues_planes_invisible(vtk_renderer):
    real_marker = CrosshairMarker3D()
    real_planes = SlicePlanes3D()
    fake = _fake_frame(sync_enabled=True, marker=real_marker, planes=real_planes,
                        show_slice_planes=False)
    view_cls, pi_cls = _attach_real_viewer_and_project(vtk_renderer)

    with patch("plugins.roi_viewer.interface.view_interface.ViewInterface", view_cls):
        with patch("plugins.roi_viewer.interface.project_interface.ProjectInterface", pi_cls):
            with patch("invesalius.pubsub.pub.sendMessage"):
                roi_panel.ROIViewerFrame.on_cross_focal_point_changed(fake, (10.0, 20.0, 30.0))

    assert real_marker.get_position() == pytest.approx((10.0, 20.0, 30.0))  # marker still updates
    for entry in real_planes._planes.values():
        assert entry["actor"].GetVisibility() == 0  # planes hidden
    # Geometry still tracks the real position underneath, even hidden:
    assert real_planes.get_position() == pytest.approx((10.0, 20.0, 30.0))


def test_sync3d_t6_show_planes_on_visible_at_current_position(vtk_renderer):
    real_planes = SlicePlanes3D()
    fake = _fake_frame(sync_enabled=True, planes=real_planes, show_slice_planes=True)
    view_cls, pi_cls = _attach_real_viewer_and_project(vtk_renderer)

    with patch("plugins.roi_viewer.interface.view_interface.ViewInterface", view_cls):
        with patch("plugins.roi_viewer.interface.project_interface.ProjectInterface", pi_cls):
            with patch("invesalius.pubsub.pub.sendMessage"):
                roi_panel.ROIViewerFrame.on_cross_focal_point_changed(fake, (12.0, 22.0, 32.0))

    for entry in real_planes._planes.values():
        assert entry["actor"].GetVisibility() == 1
    assert real_planes.get_position() == pytest.approx((12.0, 22.0, 32.0))


def test_sync3d_t7_detach_removes_both_marker_and_planes(vtk_renderer):
    real_marker = CrosshairMarker3D()
    real_planes = SlicePlanes3D()
    real_marker.attach(vtk_renderer)
    real_marker.update_position(1.0, 2.0, 3.0)
    real_planes.attach(vtk_renderer)
    real_planes.set_bounds((0, 10, 0, 10, 0, 10))
    real_planes.update_position((5.0, 5.0, 5.0))
    assert vtk_renderer.GetActors().GetNumberOfItems() == 4  # 1 + 3

    real_marker.detach()
    real_planes.detach()
    assert vtk_renderer.GetActors().GetNumberOfItems() == 0


def test_sync3d_t8_reattach_exactly_3_planes_not_6(vtk_renderer):
    real_planes = SlicePlanes3D()
    real_planes.attach(vtk_renderer)
    real_planes.detach()
    real_planes.attach(vtk_renderer)  # simulates plugin close + reopen
    assert vtk_renderer.GetActors().GetNumberOfItems() == 3
    assert real_planes.actor_count == 3


def test_sync3d_t9_slice_planes_do_not_intercept_3d_picking(vtk_renderer):
    """Regression: the 3 plane actors must never be pickable - a real
    3D pick (Region Growing seed, Distance 3D endpoint, etc.) must be
    able to hit the real surface/data behind them."""
    real_planes = SlicePlanes3D()
    fake = _fake_frame(sync_enabled=True, planes=real_planes)
    view_cls, pi_cls = _attach_real_viewer_and_project(vtk_renderer)

    with patch("plugins.roi_viewer.interface.view_interface.ViewInterface", view_cls):
        with patch("plugins.roi_viewer.interface.project_interface.ProjectInterface", pi_cls):
            with patch("invesalius.pubsub.pub.sendMessage"):
                roi_panel.ROIViewerFrame.on_cross_focal_point_changed(fake, (1.0, 1.0, 1.0))

    assert real_planes.actor_count == 3
    for entry in real_planes._planes.values():
        assert entry["actor"].GetPickable() == 0


def test_sync_t5_never_republishes_set_cross_focal_point():
    """
    No event-loop risk by construction: on_cross_focal_point_changed
    must never call Publisher.sendMessage("Set cross focal point", ...)
    itself (the topic it CONSUMES) - only a one-way consumer. Checked by
    reading the real method's source (not a mock-call-count trick, which
    only proves it didn't happen in one specific test run).
    """
    source = inspect.getsource(roi_panel.ROIViewerFrame.on_cross_focal_point_changed)
    assert '"Set cross focal point"' not in source
    assert "'Set cross focal point'" not in source


# ---------------------------------------------------------------------
# F3 - get_current_reference_position priority policy
# ---------------------------------------------------------------------

class _FakePicker:
    def __init__(self, last_point):
        self._last_point = last_point

    def get_last_point(self):
        return self._last_point


def _fake_frame_for_f3(picked_point, crosshair_point):
    fake = types.SimpleNamespace()
    fake.picker = _FakePicker(picked_point)
    fake._last_cross_focal_point = crosshair_point
    return fake


def test_f3_priority_a_pick_3d_wins_when_present():
    fake = _fake_frame_for_f3(picked_point=(1.0, 2.0, 3.0), crosshair_point=(9.0, 9.0, 9.0))
    result = roi_panel.ROIViewerFrame.get_current_reference_position(fake)
    assert result == (1.0, 2.0, 3.0)


def test_f3_priority_b_crosshair_used_when_no_pick():
    fake = _fake_frame_for_f3(picked_point=None, crosshair_point=(4.0, 5.0, 6.0))
    result = roi_panel.ROIViewerFrame.get_current_reference_position(fake)
    assert result == (4.0, 5.0, 6.0)


def test_f3_priority_c_none_when_neither_available():
    fake = _fake_frame_for_f3(picked_point=None, crosshair_point=None)
    result = roi_panel.ROIViewerFrame.get_current_reference_position(fake)
    assert result is None
