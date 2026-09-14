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


def _fake_frame(project_loaded=True, sync_enabled=True, marker=None):
    fake = types.SimpleNamespace()
    fake.project_loaded = project_loaded
    fake._last_cross_focal_point = None
    fake.sync_mgr = SyncManager2D3D()
    fake.sync_mgr.sync_2d_3d = sync_enabled
    fake.marker_3d = marker if marker is not None else _FakeMarker()
    return fake


def test_sync_t1_disabled_does_not_touch_the_marker():
    fake = _fake_frame(sync_enabled=False)
    roi_panel.ROIViewerFrame.on_cross_focal_point_changed(fake, (1.0, 2.0, 3.0))
    assert fake.marker_3d.attach_calls == []
    assert fake.marker_3d.update_calls == []


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
