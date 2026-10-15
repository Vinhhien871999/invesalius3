# --------------------------------------------------------------------------
# Status lines wrap instead of being cut off at the sidebar edge, and
# region volumes read in ml (15/10/2026, real application on 0543:
# "Đã tạo xem trước AI: 102.861 voxel (0,1% thể tích), 35.31" - cut).
# --------------------------------------------------------------------------
import types

import wx

from plugins.roi_viewer.gui import ui_helpers
from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel

LONG = "Đã tạo xem trước AI: 3.278.229 voxel (4,2% thể tích), 1.125,4 ml."


def test_status_text_wraps_and_keeps_its_plain_label(wx_app):
    frame = wx.Frame(None)
    try:
        label = ui_helpers.StatusText(frame, "Idle", indent=90)
        label.SetLabel(LONG)
        assert label.GetLabel() == LONG  # callers and tests see the text as set
        label.set_wrap_width(260)
        assert "\n" in wx.StaticText.GetLabel(label)  # displayed on several lines
        label.set_wrap_width(1200)
        assert "\n" not in wx.StaticText.GetLabel(label) and label.GetLabel() == LONG
    finally:
        frame.Destroy()


def test_rewrap_reaches_status_lines(wx_app):
    frame = wx.Frame(None)
    try:
        label = ui_helpers.StatusText(wx.Panel(frame), LONG)
        ui_helpers.rewrap_hints(frame, 300)
        assert label._wrap_width == 300 - 48
    finally:
        frame.Destroy()


def test_region_info_in_ml(wx_app):
    fake = types.SimpleNamespace()
    info = SegmentationPanel._region_info(fake, {"voxel_count": 102861, "fraction": 0.0013, "volume_mm3": 35314.7})
    assert info.endswith(", 35,3 ml") and "102.861" in info
    small = SegmentationPanel._region_info(fake, {"voxel_count": 4169, "fraction": 0.00005, "volume_mm3": 1431.4})
    assert small.endswith(", 1,43 ml")
