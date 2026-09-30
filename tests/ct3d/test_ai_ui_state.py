# --------------------------------------------------------------------------
# E6 UI state on the REAL ROIViewerPanel: AI is off by default and loads
# nothing while off; with no provider the UI says so and cannot run; the
# classic controls are untouched.
# --------------------------------------------------------------------------
import threading

import pytest

from ai_stub_provider import StubAIProvider
from plugins.roi_viewer.core.ai.types import DeviceKind


@pytest.fixture
def frame(real_slice_and_project_singleton):
    import wx

    from plugins.roi_viewer.gui.roi_panel import ROIViewerPanel

    s, proj, Project, Slice = real_slice_and_project_singleton
    Slice.instance, Project.instance = s, proj
    top = wx.Frame(None)
    f = ROIViewerPanel(top)
    yield f
    f.Destroy()
    top.Destroy()


def _ai_widgets(panel):
    return (panel.choice_ai_model, panel.choice_ai_device, panel.rb_ai_positive, panel.rb_ai_negative,
            panel.btn_ai_pick_point, panel.btn_ai_cursor_point, panel.btn_ai_corner1, panel.btn_ai_corner2,
            panel.btn_ai_clear, panel.btn_ai_run, panel.btn_ai_cancel)


def _enable(panel, on=True):
    panel.cb_enable_ai.SetValue(on)
    panel._on_enable_ai_toggle(None)


def _section(panel):
    import wx

    parent = panel.cb_enable_ai.GetParent()
    while parent is not None and not isinstance(parent, wx.CollapsiblePane):
        parent = parent.GetParent()
    return parent


def test_ai_off_by_default_and_nothing_loaded(frame):
    panel = frame.segmentation_panel
    assert panel.cb_enable_ai.GetValue() is False
    assert panel._ai_registry is None and panel._ai_jobs is None  # no provider module imported, no controller
    assert all(not w.IsEnabled() for w in _ai_widgets(panel))
    assert panel.lbl_ai_status.GetLabel() == "Tắt"
    assert panel.lbl_ai_prompts.GetLabel() == ""
    assert not any(t.name.startswith("roi-viewer-ai") for t in threading.enumerate())


def test_ai_section_collapsed_and_vietnamese(frame):
    panel = frame.segmentation_panel
    section = _section(panel)
    assert section.GetLabel() == "Phân đoạn AI (thử nghiệm)" and section.IsCollapsed()
    assert panel.cb_enable_ai.GetLabel() == "Bật phân đoạn AI (thử nghiệm)"
    labels = [panel.btn_ai_pick_point, panel.btn_ai_cursor_point, panel.btn_ai_corner1, panel.btn_ai_corner2,
              panel.btn_ai_clear, panel.btn_ai_run, panel.btn_ai_cancel, panel.rb_ai_positive, panel.rb_ai_negative]
    assert [w.GetLabel() for w in labels] == [
        "Chọn điểm (3D)", "Điểm tại con trỏ 2D", "Chọn góc 1", "Chọn góc 2", "Xóa điểm AI",
        "Xem trước bằng AI", "Hủy xử lý AI", "Thuộc vùng", "Loại trừ"]


def test_no_provider_state(frame):
    """An empty registry (independent of what this machine has installed)."""
    from plugins.roi_viewer.core.ai.registry import AIProviderRegistry

    panel = frame.segmentation_panel
    _enable(panel)
    panel._ai_registry = AIProviderRegistry()
    panel._refresh_ai_models()
    panel._update_ai_controls()
    assert panel.lbl_ai_status.GetLabel() == "Chưa có mô hình AI tương thích."
    assert panel.choice_ai_model.GetStrings() == ["(chưa có)"]
    assert panel.choice_ai_device.GetStrings() == ["Tự động"]
    assert not panel.btn_ai_run.IsEnabled() and not panel.btn_ai_cancel.IsEnabled()
    # UI review (30/09/2026): without a model only what helps is shown -
    # no point/box/structure/mode rows, but the install hint.
    sizer = panel._ai_sizer
    assert not sizer.IsShown(panel._ai_prompt_sizer)
    assert not sizer.IsShown(panel._ai_structure_row) and not sizer.IsShown(panel._ai_mode_row)
    assert sizer.IsShown(panel.lbl_ai_help)
    assert panel.lbl_ai_help.GetLabel().startswith("Plugin không kèm mô hình AI.")


def test_prompt_rows_shown_for_a_prompt_model(frame):
    from plugins.roi_viewer.core.ai.registry import AIProviderRegistry

    panel = frame.segmentation_panel
    _enable(panel)
    panel._ai_registry = AIProviderRegistry()
    panel._ai_registry.register(StubAIProvider())
    panel._ai_registry.probe_all()
    panel._refresh_ai_models()
    panel._update_ai_controls()
    sizer = panel._ai_sizer
    assert sizer.IsShown(panel._ai_prompt_sizer) and not sizer.IsShown(panel.lbl_ai_help)
    assert not sizer.IsShown(panel._ai_structure_row)  # the stub declares no structures
    assert panel.lbl_ai_prompts.GetLabel() == "Điểm: 0 thuộc vùng, 0 loại trừ · Hộp: chưa có"


def test_model_not_installed_state(frame):
    panel = frame.segmentation_panel
    _enable(panel)
    from plugins.roi_viewer.core.ai.registry import AIProviderRegistry

    panel._ai_registry = AIProviderRegistry()
    panel._ai_registry.register(StubAIProvider(available=False, requires_weights=True,
                                               reason="weights_missing: no weights"))
    panel._ai_registry.probe_all()
    panel._refresh_ai_models()
    panel._update_ai_controls()
    assert panel.lbl_ai_status.GetLabel() == "Mô hình Stub stub chưa sẵn sàng."
    assert panel.choice_ai_model.GetStrings() == ["(chưa có)"]
    assert not panel.btn_ai_run.IsEnabled()


def test_available_provider_state_and_devices(frame):
    panel = frame.segmentation_panel
    _enable(panel)
    panel._ai_registry.register(StubAIProvider(devices=(DeviceKind.CPU, DeviceKind.CUDA)))
    panel._ai_registry.probe_all()
    panel._refresh_ai_models()
    panel._update_ai_controls()
    assert panel.choice_ai_model.GetStrings() == ["Stub stub"]
    assert panel.choice_ai_device.GetStrings() == ["Tự động", "CPU", "CUDA"]
    assert panel.btn_ai_run.IsEnabled() and not panel.btn_ai_cancel.IsEnabled()
    panel.choice_ai_device.SetSelection(2)
    assert panel._selected_ai_device() == DeviceKind.CUDA
    assert panel.lbl_ai_status.GetLabel() == "Sẵn sàng."


def test_disabling_ai_disables_controls_again(frame):
    panel = frame.segmentation_panel
    _enable(panel)
    _enable(panel, False)
    assert all(not w.IsEnabled() for w in _ai_widgets(panel))
    assert panel.lbl_ai_status.GetLabel() == "Tắt" and panel.lbl_ai_prompts.GetLabel() == ""


def test_classic_controls_unchanged_with_ai_off(frame):
    panel = frame.segmentation_panel
    for button in (panel.btn_apply_thresh, panel.btn_pick_seed, panel.btn_undo, panel.btn_redo,
                   panel.btn_checkpoint, panel.btn_toggle_brush):
        assert button.IsEnabled()
    for button in (panel.btn_preview_otsu, panel.btn_preview_region_growing, panel.btn_preview_accept,
                   panel.btn_preview_cancel):
        assert not button.IsEnabled()
    assert panel.cb_enable_preview.GetValue() is False
