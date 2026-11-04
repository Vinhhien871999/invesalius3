# --------------------------------------------------------------------------
# The REAL "Phân tích ROI" panel on a real Slice()/Project(): statistics
# equal the existing Measure Volume result, staleness (edit, deletion),
# the 2D overlay never replaces the segmentation preview and leaves the
# ROI untouched, the 3D class preview is cleaned on source change /
# project close / plugin close, report data carries recorded provenance.
# --------------------------------------------------------------------------
import types

import numpy as np
import pytest

from plugins.roi_viewer.core import native_mask
from plugins.roi_viewer.core.analysis.hu_classes import HUClass
from plugins.roi_viewer.gui.analysis_panel import ANALYSIS_AUX_KEY

_SHAPE = (6, 12, 14)
_SPACING = (0.5, 0.75, 2.0)
CLASSES = [HUClass(1, "Inflated", -950, -750, (0.2, 0.6, 1.0)), HUClass(2, "Dense", 0, 100, (1.0, 0.3, 0.0))]


@pytest.fixture
def env(real_slice_and_project_singleton, monkeypatch):
    import wx
    from invesalius.pubsub import pub as Publisher
    from vtkmodules.vtkRenderingCore import vtkRenderer

    from plugins.roi_viewer.gui.roi_panel import ROIViewerPanel
    from plugins.roi_viewer.interface import view_interface
    from plugins.roi_viewer.interface.project_interface import ProjectInterface

    s, proj, Project, Slice = real_slice_and_project_singleton
    Project.instance, Slice.instance = proj, s
    proj.mask_dict, proj.surface_dict, proj.image_versions = {}, {}, []
    proj.modality = "CT"
    s.current_mask = None
    volume = np.full(_SHAPE, -1000, dtype=np.int16)
    volume[1:5, 2:10, 2:7] = -850
    volume[1:5, 2:10, 7:12] = 40
    volume[2, 3, 3] = -600  # in the ROI, in no class
    s.matrix = volume
    s._spacing = _SPACING
    ProjectInterface()._refresh_project_data()
    s.to_show_aux = ""
    for buffer in s.buffer_slices.values():
        buffer.index = -1
        buffer.discard_mask()
        buffer.discard_vtk_mask()
    Publisher.sendMessage("Create new mask", mask_name="ROI A", thresh=(-900, 100), colour=(1.0, 0.0, 0.0))
    base = s.current_mask
    renderer = vtkRenderer()
    monkeypatch.setattr(view_interface.ViewInterface, "get_volume_viewer",
                        lambda self: types.SimpleNamespace(ren=renderer, view_angle=1))
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: wx.YES)
    top = wx.Frame(None)
    frame = ROIViewerPanel(top)
    panel = frame.analysis_panel
    panel.background = False
    e = types.SimpleNamespace(s=s, proj=proj, frame=frame, panel=panel, base=base, volume=volume, renderer=renderer)
    yield e
    frame.shutdown()
    frame.Destroy()
    top.Destroy()
    s.to_show_aux = ""
    s.aux_matrices.pop(ANALYSIS_AUX_KEY, None)
    # Leave the shared singletons as found: later modules build frames that
    # show the current mask's name.
    proj.mask_dict, proj.surface_dict = {}, {}
    s.current_mask = None


def _compute(e, classes=CLASSES):
    e.panel.classes = list(classes)
    e.panel._refresh_class_list()
    e.panel._on_compute(None)
    assert e.panel.session is not None and not e.panel.session.stale


def test_statistics_equal_measure_volume(env):
    _compute(env)
    st = env.panel.session.statistics
    assert st.voxel_count == 4 * 8 * 10
    measured = env.frame.measure_mgr
    measured.set_spacing(_SPACING)
    vm = measured.add_volume_measurement("", env.base.index, native_mask.logical_foreground(env.s, env.base))
    assert vm.volume == pytest.approx(st.volume_mm3, rel=0, abs=1e-9)  # both voxel-based
    assert env.panel.lbl_status.GetLabel() == "Đã phân tích 'ROI A'."
    assert "Số voxel: 320" in env.panel.lbl_stats.GetLabel()


def test_accounting_shown_and_exact(env):
    _compute(env)
    c = env.panel.session.classification
    assert [r.voxel_count for r in c.classes] == [159, 160] and c.unclassified.voxel_count == 1
    assert c.accounted_voxels == env.panel.session.statistics.voxel_count
    assert "Chưa phân lớp" in env.panel.lbl_classes.GetLabel()


def test_analysis_and_previews_never_change_the_roi(env):
    # Reading the ROI completes InVesalius's lazy threshold first (what
    # native code does before any whole-volume use); after that, no byte
    # of the mask may change.
    logical = native_mask.logical_foreground(env.s, env.base)
    before = env.base.matrix.copy()
    _compute(env)
    env.panel.cb_show_2d.SetValue(True)
    env.panel._on_toggle_2d(None)
    env.panel.cb_show_3d.SetValue(True)
    env.panel._on_toggle_3d(None)
    env.panel._on_redraw_histogram(None)
    env.panel._hide_previews()
    assert np.array_equal(env.base.matrix, before)
    assert np.array_equal(native_mask.logical_foreground(env.s, env.base), logical)
    assert len(env.proj.mask_dict) == 1 and env.proj.surface_dict == {}


def test_2d_overlay_is_its_own_layer(env):
    _compute(env)
    env.panel.cb_show_2d.SetValue(True)
    env.panel._on_toggle_2d(None)
    assert env.s.to_show_aux == ANALYSIS_AUX_KEY
    assert np.array_equal(env.s.aux_matrices[ANALYSIS_AUX_KEY], env.panel.session.labels)
    assert env.s.aux_matrices_colours[ANALYSIS_AUX_KEY][1][3] == 0.5
    env.panel.cb_show_2d.SetValue(False)
    env.panel._on_toggle_2d(None)
    assert env.s.to_show_aux == "" and ANALYSIS_AUX_KEY not in env.s.aux_matrices


def test_segmentation_preview_keeps_the_overlay_slot(env):
    from plugins.roi_viewer.gui.segmentation_panel import PREVIEW_AUX_KEY

    _compute(env)
    env.s.to_show_aux = PREVIEW_AUX_KEY  # an E2 preview is on screen
    env.panel.cb_show_2d.SetValue(True)
    env.panel._on_toggle_2d(None)
    assert env.s.to_show_aux == PREVIEW_AUX_KEY and env.panel.cb_show_2d.GetValue() is False
    assert env.panel.lbl_status.GetLabel().startswith("Đang hiển thị bản xem trước phân đoạn")
    env.panel._hide_2d()
    assert env.s.to_show_aux == PREVIEW_AUX_KEY  # never cleared by analysis


def test_3d_preview_transient_and_non_pickable(env):
    _compute(env)
    env.panel.cb_show_3d.SetValue(True)
    env.panel._on_toggle_3d(None)
    actors = env.panel.preview_3d.actors
    assert set(actors) == {1, 2} and env.renderer.GetActors().GetNumberOfItems() == 2
    assert all(a.GetPickable() == 0 for a in actors.values()) and env.proj.surface_dict == {}


def test_source_edit_makes_analysis_stale_and_clears_previews(env):
    _compute(env)
    env.panel.cb_show_2d.SetValue(True)
    env.panel._on_toggle_2d(None)
    env.panel.cb_show_3d.SetValue(True)
    env.panel._on_toggle_3d(None)
    edited = native_mask.logical_foreground(env.s, env.base)
    edited[1, 2, 2] = False
    native_mask.write_logical_region(env.s, env.base, edited)  # plugin edit: no modified() callback
    assert env.panel.ensure_current() is False
    assert env.panel.lbl_status.GetLabel() == "ROI đã thay đổi. Hãy tính lại phân tích."
    assert env.s.to_show_aux == "" and env.renderer.GetActors().GetNumberOfItems() == 0
    assert not env.panel.btn_csv.IsEnabled() and not env.panel.btn_convert.IsEnabled()


def test_native_modified_callback_marks_stale(env):
    _compute(env)
    env.base.modified()  # what the native brush does after a stroke
    assert env.panel.session.stale


def test_source_deletion_makes_analysis_stale(env):
    _compute(env)
    env.proj.mask_dict.pop(env.base.index)
    env.frame.on_roi_source_changed()
    assert env.panel.session.stale


@pytest.mark.parametrize("how", ["project_close", "project_load", "plugin_close"])
def test_lifecycle_cleans_everything(env, how):
    _compute(env)
    env.panel.cb_show_2d.SetValue(True)
    env.panel._on_toggle_2d(None)
    env.panel.cb_show_3d.SetValue(True)
    env.panel._on_toggle_3d(None)
    {"project_close": env.frame.on_project_close, "project_load": env.frame.on_project_load,
     "plugin_close": env.frame.shutdown}[how]()
    assert env.panel.session is None
    assert env.s.to_show_aux == "" and ANALYSIS_AUX_KEY not in env.s.aux_matrices
    assert env.renderer.GetActors().GetNumberOfItems() == 0


def test_late_worker_result_after_reset_is_dropped(env):
    env.panel.background = True
    calls = []
    env.panel._spawn = lambda fn, name: calls.append(fn)  # hold the worker
    env.panel.classes = list(CLASSES)
    env.panel._on_compute(None)
    env.panel.reset()
    env.panel.background = False
    calls[0]()  # the worker finishes after the reset
    assert env.panel.session is None


def test_colour_change_keeps_results_range_change_drops_them(env):
    _compute(env)
    env.panel.list_classes.Select(0)
    env.panel._on_class_selected(None)
    env.panel.colour_class.SetColour(wx_colour(10, 20, 30))
    env.panel._on_class_apply(None)
    assert env.panel.session.classification is not None
    env.panel.spin_class_max.SetValue(-700)
    env.panel._on_class_apply(None)
    assert env.panel.session.classification is None
    assert env.panel.lbl_status.GetLabel() == "Đã đổi phân lớp. Hãy bấm Tính toán."


def test_overlapping_edit_rejected_and_list_unchanged(env):
    _compute(env)
    env.panel.list_classes.Select(0)
    env.panel._on_class_selected(None)
    env.panel.spin_class_max.SetValue(50)  # into class 2's range
    env.panel._on_class_apply(None)
    assert env.panel.classes[0].max_hu == -750
    assert "chồng lấn" in env.panel.lbl_status.GetLabel()


def test_report_data_uses_recorded_provenance_only(env):
    _compute(env)
    data = env.panel.report_data("2026-11-04 10:00")
    assert data.ai is None and data.roi["source"] == ""
    env.frame.roi_provenance[env.base] = {"source": "AI", "ai": {"provider_name": "TotalSegmentator",
                                                                  "structure": "lung_left", "device": "cuda"}}
    data = env.panel.report_data("2026-11-04 10:00")
    assert data.ai == {"provider_name": "TotalSegmentator", "structure": "lung_left", "device": "cuda"}
    assert data.dataset["shape_zyx"] == _SHAPE and data.dataset["modality"] == "CT"


def test_non_ct_project_disables_hu_parts(env):
    env.proj.modality = "MR"
    _compute(env)
    assert env.panel.session.statistics.hu is None and env.panel.session.classification is None
    assert "Không có thống kê HU" in env.panel.lbl_stats.GetLabel()


def test_comparison_through_the_panel(env):
    from invesalius.pubsub import pub as Publisher

    Publisher.sendMessage("Create new mask", mask_name="ROI B", thresh=(0, 100), colour=(0.0, 1.0, 0.0))
    env.frame.on_roi_source_changed()
    env.panel.classes = list(CLASSES)
    env.panel.combo_roi_a.SetValue("ROI A")
    env.panel.combo_roi_b.SetValue("ROI B")
    env.panel._on_compare(None)
    rows = {r.metric: r for r in env.panel.comparison.rows}
    assert rows["voxel_count"].a == 320 and rows["voxel_count"].b == 160 and rows["voxel_count"].total == 480
    assert env.panel.comparison.overlap_voxels == 160
    assert "Thể tích (ml)" in env.panel.lbl_compare.GetLabel()


def wx_colour(r, g, b):
    import wx

    return wx.Colour(r, g, b)
