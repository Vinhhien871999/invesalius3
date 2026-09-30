# --------------------------------------------------------------------------
# ROI Viewer UI: Vietnamese localization + layout regression (30/09/2026).
#
# Static checks run on the plugin source (AST) and the catalog. UI checks
# build the REAL ROIViewerFrame headlessly and walk its actual widget tree -
# labels, tooltips, defaults, sizes - rather than trusting source text. No
# screenshots are produced or compared.
# --------------------------------------------------------------------------
import ast
import pathlib
import re

import pytest

from plugins.roi_viewer import i18n
from plugins.roi_viewer.locale_vi import CATALOG

_PLUGIN = pathlib.Path(__file__).resolve().parents[2] / "plugins" / "roi_viewer"
_NEUTRAL = {"-", "voxel", "x", "X: -, Y: -, Z: -", "2D", "3D", "1", "2", "3", "4", "5"}
_FORMAT = re.compile(r"\(\.\w+(\.\w+)?\)$")  # "NIfTI (.nii.gz)", "PNG (.png)" ...


def _norm(text):
    return " ".join(text.split())


_VI = {_norm(v) for v in CATALOG.values()}


def _msgids():
    found, non_literal = set(), []
    for path in _PLUGIN.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    found.add(arg.value)
                else:
                    non_literal.append(f"{path.name}:{arg.lineno}")
    return found, non_literal


# ------------------------------------------------------------------
# Static: catalog completeness and i18n rules
# ------------------------------------------------------------------

def test_all_msgids_are_literals():
    """_(f"...") can never be translated - the msgid changes every call."""
    _, non_literal = _msgids()
    assert non_literal == []


def test_every_msgid_has_vietnamese_translation():
    found, _ = _msgids()
    missing = sorted(m for m in found if m not in CATALOG)
    assert missing == []


def test_no_unused_catalog_entries():
    found, _ = _msgids()
    assert sorted(k for k in CATALOG if k not in found) == []


def test_placeholders_preserved():
    for msgid, text in CATALOG.items():
        assert set(re.findall(r"\{\w*\}", msgid)) == set(re.findall(r"\{\w*\}", text)), msgid


def test_empty_string_never_translated():
    """gettext("") returns the catalog header - the metadata leak an
    operator once saw on screen."""
    assert i18n._("") == ""
    assert "" not in CATALOG


def test_plugin_does_not_use_upstream_translator():
    for path in _PLUGIN.rglob("*.py"):
        code = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
        assert "from invesalius.i18n import" not in code, path.name


def test_vietnamese_number_format():
    assert i18n.fmt_int(152340) == "152.340"
    assert i18n.fmt_float(0.08, 2) == "0,08"
    assert i18n.fmt_float(1234.5, 2) == "1.234,50"


# ------------------------------------------------------------------
# Real frame
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def _frame_module(real_slice_and_project_singleton):
    import wx

    s, proj, Project, Slice = real_slice_and_project_singleton
    Slice.instance, Project.instance = s, proj  # never construct a second real Slice()
    from plugins.roi_viewer.gui.roi_panel import ROIViewerFrame

    top = wx.Frame(None)
    frame = ROIViewerFrame(top)
    yield frame
    frame.Destroy()
    top.Destroy()


@pytest.fixture
def frame(_frame_module, real_slice_and_project_singleton):
    s, proj, Project, Slice = real_slice_and_project_singleton
    Slice.instance, Project.instance = s, proj
    return _frame_module


def _walk(window):
    for child in window.GetChildren():
        yield child
        yield from _walk(child)


def _layout(frame, width, expanded):
    import wx

    frame.SetSize((width, 700))
    for w in _walk(frame):
        if isinstance(w, wx.CollapsiblePane):
            w.Collapse(not expanded)
    frame.Layout()
    for i in range(frame.notebook.GetPageCount()):
        page = frame.notebook.GetPage(i)
        page.Layout()
        if hasattr(page, "SetupScrolling"):
            page.SetupScrolling(scroll_x=False, scrollToTop=False)


def test_tabs_are_vietnamese_in_workflow_order(frame):
    tabs = [frame.notebook.GetPageText(i) for i in range(frame.notebook.GetPageCount())]
    assert tabs == ["Phân đoạn", "ROI & 3D", "Tương tác & Hiển thị", "Đo lường", "Ghi chú", "Xuất dữ liệu"]
    assert frame.GetTitle() == "ROI Viewer – Trực quan hóa CT 3D"


def test_all_visible_labels_are_vietnamese(frame):
    import wx

    english = []
    for w in _walk(frame):
        if isinstance(w, wx.Choice):
            labels = w.GetStrings()
        elif isinstance(w, (wx.StaticText, wx.Button, wx.ToggleButton, wx.CheckBox, wx.RadioButton,
                            wx.StaticBox, wx.CollapsiblePane)):
            labels = [w.GetLabel()]
        else:
            continue
        for label in labels:
            text = _norm(label)
            if text and text not in _VI and text not in _NEUTRAL and not _FORMAT.search(text):
                english.append(text)
    assert english == []


def test_tooltips_are_vietnamese(frame):
    tips = [_norm(w.GetToolTipText()) for w in _walk(frame) if w.GetToolTipText()]
    assert tips  # the advanced controls do carry tooltips
    assert [t for t in tips if t not in _VI] == []


def test_advanced_sections_collapsed_by_default():
    """Fresh frame (not the shared one other tests expand)."""
    import wx

    from plugins.roi_viewer.gui.roi_panel import ROIViewerFrame

    top = wx.Frame(None)
    fresh = ROIViewerFrame(top)
    try:
        panes = {w.GetLabel(): w.IsCollapsed() for w in _walk(fresh) if isinstance(w, wx.CollapsiblePane)}
        assert panes == {
            "Phân đoạn AI (thử nghiệm)": True,  # E6 (30/09/2026)
            "Hậu xử lý (ROI hiện tại)": True,
            "Chỉnh sửa thủ công (cọ vẽ)": True,
            "Xem trước 3D thời gian thực (thử nghiệm)": True,
            "Hiển thị 3D nâng cao (thử nghiệm)": True,
        }
    finally:
        fresh.Destroy()
        top.Destroy()


def test_feature_defaults(frame):
    seg, inter = frame.segmentation_panel, frame.interaction_panel
    assert seg.cb_enable_preview.GetValue() is False
    assert seg.cb_enable_live_3d_preview.GetValue() is False
    assert inter.cb_texture_planes.GetValue() is False
    assert inter.cb_clip_enabled.GetValue() is False
    assert inter.cb_show_slice_planes.GetValue() is True
    assert inter.cb_sync_2d_3d.GetValue() is True
    for button in (seg.btn_preview_otsu, seg.btn_preview_region_growing, seg.btn_preview_accept,
                   seg.btn_preview_cancel, seg.btn_refresh_3d_preview):
        assert button.IsEnabled() is False


def test_preview_buttons_follow_preview_mode(frame):
    import wx

    seg = frame.segmentation_panel

    def toggle(value):
        seg.cb_enable_preview.SetValue(value)
        event = wx.CommandEvent(wx.wxEVT_CHECKBOX, seg.cb_enable_preview.GetId())
        event.SetInt(int(value))
        seg.cb_enable_preview.GetEventHandler().ProcessEvent(event)

    toggle(True)
    assert seg.btn_preview_otsu.IsEnabled() is True
    assert seg.btn_preview_region_growing.IsEnabled() is False  # no seed picked yet
    toggle(False)
    assert seg.btn_preview_otsu.IsEnabled() is False


def test_classic_controls_still_wired(frame):
    """Real events through real handlers, on paths with no modal dialog:
    the handlers run and report in Vietnamese."""
    import wx

    seg = frame.segmentation_panel
    seg.btn_undo.GetEventHandler().ProcessEvent(wx.CommandEvent(wx.wxEVT_BUTTON, seg.btn_undo.GetId()))
    assert seg.status_text.GetLabel() in {"Chưa chọn mặt nạ.", "Không có gì để hoàn tác.", "ROI đang bị khóa."}

    seg.btn_checkpoint.GetEventHandler().ProcessEvent(wx.CommandEvent(wx.wxEVT_BUTTON, seg.btn_checkpoint.GetId()))
    assert seg.status_text.GetLabel() in {"Chưa chọn mặt nạ.", "Đã lưu điểm khôi phục."}


def test_dead_interaction_controls_removed(frame):
    inter = frame.interaction_panel
    for name in ("cb_realtime", "slider_delay", "lbl_delay_value", "slider_brush_size", "rb_circle",
                 "rb_square", "lbl_brush_size", "get_brush_config"):
        assert not hasattr(inter, name), name


def test_no_duplicate_window_ids(frame):
    ids = [w.GetId() for w in _walk(frame)]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("width", [400, 330])
@pytest.mark.parametrize("expanded", [False, True])
def test_no_clipped_controls_or_horizontal_overflow(frame, width, expanded):
    import wx

    _layout(frame, width, expanded)
    for i in range(frame.notebook.GetPageCount()):
        page = frame.notebook.GetPage(i)
        assert page.GetVirtualSize().width <= page.GetClientSize().width, frame.notebook.GetPageText(i)

    clipped = []
    for w in _walk(frame):
        if isinstance(w, (wx.Button, wx.ToggleButton)):
            need = w.GetTextExtent(w.GetLabel()).width + 8
        elif isinstance(w, (wx.CheckBox, wx.RadioButton)):
            need = w.GetBestSize().width
        else:
            continue
        if w.GetSize().width + 1 < need:
            clipped.append((w.GetLabel(), w.GetSize().width, need))
    assert clipped == []


def test_segmentation_tab_fits_one_screen_when_collapsed(frame):
    """Before the reorganisation this tab was 1396 px tall at 400 px wide."""
    _layout(frame, 400, expanded=False)
    page = frame.segmentation_panel
    assert page.GetSizer().CalcMin().height <= page.GetClientSize().height
