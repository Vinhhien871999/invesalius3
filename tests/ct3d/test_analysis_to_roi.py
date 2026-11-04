# --------------------------------------------------------------------------
# "Chuyển lớp đang chọn thành ROI" through the REAL panel, Slice() and
# Project(): no mask before the button, exactly one after it, its logical
# array equals the selected class, the parent is untouched, no surface,
# a locked parent does not block creating a NEW ROI.
#
# Undo semantics (documented in docs/CT3D_ROI_ANALYSIS_REPORT.md): the new
# ROI is a new mask, not an edit of the parent - the parent's undo history
# is unchanged and the new ROI is removed with "Xóa" in the ROI list.
# --------------------------------------------------------------------------
import types

import numpy as np
import pytest

from plugins.roi_viewer.core import native_mask
from plugins.roi_viewer.core.analysis.hu_classes import HUClass

_SHAPE = (6, 12, 14)
_SPACING = (0.5, 0.75, 2.0)
CLASSES = [HUClass(1, "Inflated", -950, -750, (0.2, 0.6, 1.0)), HUClass(2, "Dense", 0, 100, (1.0, 0.3, 0.0))]


@pytest.fixture
def env(real_slice_and_project_singleton, monkeypatch):
    import wx
    from invesalius.pubsub import pub as Publisher

    from plugins.roi_viewer.gui.roi_panel import ROIViewerPanel
    from plugins.roi_viewer.interface.project_interface import ProjectInterface

    s, proj, Project, Slice = real_slice_and_project_singleton
    Project.instance, Slice.instance = proj, s
    proj.mask_dict, proj.surface_dict, proj.image_versions = {}, {}, []
    proj.modality = "CT"
    s.current_mask = None
    volume = np.full(_SHAPE, -1000, dtype=np.int16)
    volume[1:5, 2:10, 2:7] = -850
    volume[1:5, 2:10, 7:12] = 40
    s.matrix = volume
    s._spacing = _SPACING
    ProjectInterface()._refresh_project_data()
    s.to_show_aux = ""
    for buffer in s.buffer_slices.values():
        buffer.index = -1
        buffer.discard_mask()
        buffer.discard_vtk_mask()
    Publisher.sendMessage("Create new mask", mask_name="AI - lung_left", thresh=(-900, 100), colour=(1.0, 0.0, 0.0))
    base = s.current_mask
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: wx.YES)
    top = wx.Frame(None)
    frame = ROIViewerPanel(top)
    panel = frame.analysis_panel
    panel.background = False
    e = types.SimpleNamespace(s=s, proj=proj, frame=frame, panel=panel, base=base, volume=volume)
    yield e
    frame.shutdown()
    frame.Destroy()
    top.Destroy()
    s.to_show_aux = ""
    # Leave the shared singletons as found: later modules build frames that
    # show the current mask's name.
    proj.mask_dict, proj.surface_dict = {}, {}
    s.current_mask = None


def _compute(e, classes=CLASSES):
    e.panel.classes = list(classes)
    e.panel._refresh_class_list()
    e.panel._on_compute(None)
    assert e.panel.session is not None and not e.panel.session.stale


def test_conversion_creates_exactly_one_matching_roi(env):
    _compute(env)
    parent_before = native_mask.logical_foreground(env.s, env.base).copy()
    assert len(env.proj.mask_dict) == 1  # analysis alone created nothing
    labels = env.panel.session.labels.copy()
    name = env.panel.convert_class_to_roi(CLASSES[0])
    assert name == "AI - lung_left - Inflated"
    assert len(env.proj.mask_dict) == 2
    new = env.s.current_mask
    assert new.name == name and new is not env.base
    assert np.array_equal(native_mask.logical_foreground(env.s, new), labels == 1)
    assert np.array_equal(native_mask.logical_foreground(env.s, env.base), parent_before)
    assert env.proj.surface_dict == {}  # no automatic surface


def test_conversion_button_needs_a_selected_class(env):
    _compute(env)
    env.panel.list_classes.Select(0, on=False)
    env.panel._on_convert(None)
    assert len(env.proj.mask_dict) == 1
    assert env.panel.lbl_status.GetLabel() == "Hãy chọn một lớp trong danh sách."
    env.panel.list_classes.Select(1)
    env.panel._on_convert(None)
    assert len(env.proj.mask_dict) == 2 and env.s.current_mask.name == "AI - lung_left - Dense"


def test_empty_class_creates_nothing(env):
    classes = CLASSES + [HUClass(3, "Nothing", 500, 600)]
    _compute(env, classes)
    assert env.panel.convert_class_to_roi(classes[2]) is None
    assert len(env.proj.mask_dict) == 1


def test_locked_parent_does_not_block_a_new_roi(env):
    mgr = env.frame.roi_mgr
    roi_id = next(rid for rid, roi in mgr.rois.items() if roi.mask_index == env.base.index)
    mgr.set_locked(roi_id, True)
    _compute(env)
    assert env.panel.convert_class_to_roi(CLASSES[1]) == "AI - lung_left - Dense"
    assert len(env.proj.mask_dict) == 2
    assert mgr.is_locked_for_mask_index(env.base.index)  # parent still locked


def test_parent_undo_history_unchanged(env):
    _compute(env)
    editor = env.frame.mask_mgr.get_editor(env.base.index)
    before = editor.undo_manager.can_undo() if editor else False
    env.panel.convert_class_to_roi(CLASSES[0])
    editor = env.frame.mask_mgr.get_editor(env.base.index)
    assert (editor.undo_manager.can_undo() if editor else False) == before


def test_stale_analysis_refuses_conversion(env):
    _compute(env)
    edited = native_mask.logical_foreground(env.s, env.base)
    edited[1, 2, 2] = False
    native_mask.write_logical_region(env.s, env.base, edited)
    env.panel.list_classes.Select(0)
    env.panel._on_convert(None)
    assert len(env.proj.mask_dict) == 1
    assert env.panel.session.stale and env.panel.lbl_status.GetLabel() == "ROI đã thay đổi. Hãy tính lại phân tích."
