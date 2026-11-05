# --------------------------------------------------------------------------
# "Chọn điểm hạt giống (3D)" and the shared 3D picker (05/11/2026).
#
# Real VTK render window / interactor / InVesalius-like interactor style,
# off-screen, with real LeftButtonPress events. Covers the defects found:
#   * a click that hits nothing was reported as a point (VTK returns a point
#     on the camera focal plane), giving a meaningless seed;
#   * a one-shot callback removing itself skipped the next callback;
#   * re-attaching the picker (project reload) cleared every callback, so
#     the permanent "Chọn điểm trong 3D" callback stopped for good;
# and the end-to-end seed paths through the real ROIViewerPanel: 3D pick on
# a surface, a miss (stays armed, explains), and the new seed at 2D cursor.
# A real-application run (InVesalius main window, 0543, wx mouse events into
# the 3D view) was also done - see docs/CT3D_SEED_PICK_REVIEW.md.
# --------------------------------------------------------------------------
import types

import numpy as np
import pytest

from plugins.roi_viewer.core.picker_3d import PointPicker3D

_SHAPE = (10, 20, 30)


@pytest.fixture
def scene():
    import importlib

    importlib.import_module("vtkmodules.vtkInteractionStyle")
    importlib.import_module("vtkmodules.vtkRenderingOpenGL2")  # registers the render window
    from vtkmodules.vtkFiltersSources import vtkSphereSource
    from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
    from vtkmodules.vtkRenderingCore import (vtkActor, vtkPolyDataMapper, vtkRenderer, vtkRenderWindow,
                                             vtkRenderWindowInteractor)

    ren = vtkRenderer()
    win = vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(200, 200)
    win.AddRenderer(ren)
    iren = vtkRenderWindowInteractor()
    iren.SetRenderWindow(win)

    class Style(vtkInteractorStyleTrackballCamera):  # InVesalius styles add their own observers
        def __init__(self):
            self.AddObserver("LeftButtonPressEvent", lambda o, e: None)

    iren.SetInteractorStyle(Style())
    sphere = vtkSphereSource()
    sphere.SetRadius(3)
    sphere.SetCenter(15, -10, 5)  # 3D view frame (y negated), inside the volume
    sphere.SetThetaResolution(32)
    sphere.SetPhiResolution(32)
    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(sphere.GetOutputPort())
    actor = vtkActor()
    actor.SetMapper(mapper)
    ren.AddActor(actor)
    ren.ResetCamera()
    win.Render()

    def click(x, y):
        iren.SetEventInformation(x, y)
        iren.LeftButtonPressEvent()
        iren.LeftButtonReleaseEvent()

    return types.SimpleNamespace(ren=ren, iren=iren, win=win, click=click)


def test_hit_reports_a_point_on_the_surface(scene):
    p = PointPicker3D()
    p.initialize_picker(scene.ren, scene.iren)
    got = []
    p.add_callback(got.append)
    scene.click(100, 100)
    assert len(got) == 1
    x, y, z = got[0]
    assert np.hypot(np.hypot(x - 15, y + 10), z - 5) == pytest.approx(3.0, abs=0.05)  # on the sphere


def test_miss_is_not_reported_as_a_point(scene):
    p = PointPicker3D()
    p.initialize_picker(scene.ren, scene.iren)
    got, missed = [], []
    p.add_callback(got.append)
    p.add_miss_callback(lambda: missed.append(True))
    scene.click(3, 3)  # background
    assert got == [] and missed == [True]
    assert p.pick(3, 3) is None and p.pick(100, 100) is not None


def test_self_removing_callback_does_not_skip_the_next(scene):
    p = PointPicker3D()
    p.initialize_picker(scene.ren, scene.iren)
    order = []

    def one_shot(point):
        order.append("one_shot")
        p.remove_callback(one_shot)

    p.add_callback(one_shot)
    p.add_callback(lambda point: order.append("permanent"))
    scene.click(100, 100)
    scene.click(100, 100)
    assert order == ["one_shot", "permanent", "permanent"]


def test_failing_callback_does_not_stop_others(scene):
    p = PointPicker3D()
    p.initialize_picker(scene.ren, scene.iren)
    got = []

    def broken(point):
        raise RuntimeError("boom")

    p.add_callback(broken)
    p.add_callback(got.append)
    scene.click(100, 100)
    assert len(got) == 1


def test_reattach_keeps_callbacks_and_one_observer(scene):
    p = PointPicker3D()
    p.initialize_picker(scene.ren, scene.iren)
    got = []
    p.add_callback(got.append)
    p.initialize_picker(scene.ren, scene.iren)  # what a project reload does
    scene.click(100, 100)
    assert len(got) == 1  # still connected, and not twice
    p.cleanup()  # plugin close: everything goes
    scene.click(100, 100)
    assert len(got) == 1 and p.callbacks == [] and p.miss_callbacks == []


# ------------------------------------------------------------------ real panel
@pytest.fixture
def panel_env(real_slice_and_project_singleton, scene, monkeypatch):
    import wx
    from invesalius.pubsub import pub as Publisher

    from plugins.roi_viewer.gui.roi_panel import ROIViewerPanel
    from plugins.roi_viewer.interface import view_interface
    from plugins.roi_viewer.interface.project_interface import ProjectInterface

    s, proj, Project, Slice = real_slice_and_project_singleton
    Project.instance, Slice.instance = proj, s
    proj.mask_dict, proj.surface_dict = {}, {}
    proj.modality = "CT"
    s.current_mask = None
    vol = np.full(_SHAPE, -800, dtype=np.int16)
    vol[7, 10, 15] = 123
    s.matrix = vol
    s._spacing = (1.0, 1.0, 1.0)
    ProjectInterface()._refresh_project_data()
    Publisher.sendMessage("Create new mask", mask_name="Base", thresh=(-900, 100), colour=(1.0, 0.0, 0.0))
    viewer = types.SimpleNamespace(ren=scene.ren, interactor=scene.iren, view_angle=1)
    monkeypatch.setattr(view_interface.ViewInterface, "get_volume_viewer", lambda self: viewer)
    monkeypatch.setattr(wx, "CallAfter", lambda fn, *a, **k: fn(*a, **k))
    top = wx.Frame(None)
    frame = ROIViewerPanel(top)
    seg = frame.segmentation_panel
    seg.cb_enable_preview.SetValue(True)  # record the seed, do not grow
    yield types.SimpleNamespace(frame=frame, seg=seg, scene=scene, s=s, proj=proj)
    frame.shutdown()
    frame.Destroy()
    top.Destroy()
    proj.mask_dict, proj.surface_dict = {}, {}
    s.current_mask = None


def _arm(e):
    e.seg.btn_pick_seed.SetValue(True)
    e.seg._on_toggle_pick_seed(None)


def test_3d_seed_pick_on_a_surface(panel_env):
    e = panel_env
    _arm(e)
    assert e.seg.rg_status.GetLabel() == "Nhấp chọn điểm hạt giống trong khung 3D…"
    e.scene.click(100, 100)
    # the front of the sphere (camera on +z): z = 5 + 3 = 8, y = 10 (view -10), x = 15
    assert e.seg._preview_seed_voxel == (8, 10, 15)
    assert e.seg.rg_status.GetLabel().startswith("Hạt giống tại voxel")
    assert e.seg.btn_preview_region_growing.IsEnabled() and not e.seg.btn_pick_seed.GetValue()
    assert e.seg._on_seed_picked not in e.frame.picker.callbacks  # one-shot
    assert e.frame.marker_3d.get_position() is not None  # feedback in 3D


def test_3d_miss_explains_and_stays_armed(panel_env):
    e = panel_env
    _arm(e)
    e.scene.click(3, 3)
    assert e.seg._preview_seed_voxel is None
    assert e.seg.rg_status.GetLabel().startswith("Cú nhấp không trúng bề mặt 3D nào")
    assert e.seg._on_seed_picked in e.frame.picker.callbacks  # still armed
    e.scene.click(100, 100)
    assert e.seg._preview_seed_voxel is not None


def test_pressing_twice_registers_once(panel_env):
    e = panel_env
    _arm(e)
    e.seg._on_toggle_pick_seed(None)
    assert e.frame.picker.callbacks.count(e.seg._on_seed_picked) == 1


def test_untoggle_cancels(panel_env):
    e = panel_env
    _arm(e)
    e.seg.btn_pick_seed.SetValue(False)
    e.seg._on_toggle_pick_seed(None)
    assert e.seg._on_seed_picked not in e.frame.picker.callbacks
    assert e.seg._on_seed_missed not in e.frame.picker.miss_callbacks


def test_seed_at_2d_cursor(panel_env):
    e = panel_env
    e.seg._on_seed_from_cursor(None)
    assert e.seg.rg_status.GetLabel().startswith("Chưa có vị trí con trỏ 2D")
    e.frame._last_cross_focal_point = (15.0, 10.0, 7.0)  # slice frame (x, y, z) mm
    e.seg._on_seed_from_cursor(None)
    assert e.seg._preview_seed_voxel == (7, 10, 15)
    assert "HU 123" in e.seg.rg_status.GetLabel()


def test_display_tab_pick_survives_project_reload(panel_env):
    e = panel_env
    inter = e.frame.interaction_panel
    inter._on_pick_point(None)
    e.frame.on_project_close()
    e.frame.ensure_picker_initialized()  # re-attach after the reload
    e.scene.click(100, 100)
    assert inter.txt_coords.GetValue() != "X: -, Y: -, Z: -"


def test_marker_never_intercepts_a_pick(scene):
    """The yellow 3D marker (crosshair / seed feedback) sat in front of the
    surface and was picked instead of it (real application, 05/11/2026)."""
    from plugins.roi_viewer.core.marker_3d import CrosshairMarker3D

    p = PointPicker3D()
    p.initialize_picker(scene.ren, scene.iren)
    got = []
    p.add_callback(got.append)
    scene.click(100, 100)
    marker = CrosshairMarker3D()
    marker.attach(scene.ren)
    marker.update_position(*got[0])  # the marker on the picked point
    scene.win.Render()
    assert marker.actor.GetPickable() == 0
    scene.click(100, 100)
    assert got[1] == pytest.approx(got[0], abs=1e-6)  # still the sphere surface, not the marker
