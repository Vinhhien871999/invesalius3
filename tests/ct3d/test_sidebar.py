# --------------------------------------------------------------------------
# ROI Viewer as a sidebar pane (gui/sidebar.py, 30/09/2026). The host is a
# stand-in for InVesalius's main window built the way
# invesalius/gui/frame.py builds it: a wx.aui.AuiManager in
# `frame.aui_manager` with a "Tasks" pane docked left and a centre pane.
# The real ROIViewerPanel is docked into it.
# --------------------------------------------------------------------------
import types

import pytest
import wx
import wx.aui

from plugins.roi_viewer.gui import sidebar
from plugins.roi_viewer.gui.roi_panel import ROIViewerPanel


@pytest.fixture
def host(real_slice_and_project_singleton):
    s, proj, Project, Slice = real_slice_and_project_singleton
    Slice.instance, Project.instance = s, proj
    frame = wx.Frame(None, size=(1400, 860))
    manager = wx.aui.AuiManager(frame)
    frame.aui_manager = manager
    manager.AddPane(wx.Panel(frame), wx.aui.AuiPaneInfo().Name("Tasks").CaptionVisible(False).Left()
                    .BestSize((385, -1)).MinSize((385, -1)).CloseButton(False).Layer(0))
    manager.AddPane(wx.Panel(frame), wx.aui.AuiPaneInfo().Name("Data").CaptionVisible(False).Centre().Layer(1))
    manager.Update()
    yield frame
    manager.UnInit()
    frame.Destroy()


def _pane(frame):
    return frame.aui_manager.GetPane(sidebar.PANE_NAME)


def test_docks_as_right_sidebar_next_to_invesalius_panes(host):
    panel = sidebar.open_viewer(host)
    assert isinstance(panel, ROIViewerPanel) and panel.GetParent() is host
    pane = _pane(host)
    assert pane.IsOk() and pane.IsShown() and pane.IsDocked()
    assert pane.dock_direction == wx.aui.AUI_DOCK_RIGHT
    assert pane.caption == "ROI Viewer" and pane.HasCloseButton() and pane.IsFloatable()
    destroy_bit = wx.aui.AuiPaneInfo().DestroyOnClose(True).state ^ wx.aui.AuiPaneInfo().state  # no Python getter
    assert pane.state & destroy_bit
    assert pane.min_size.width == sidebar.SIDEBAR_MIN_WIDTH
    # InVesalius's own panes are untouched
    assert host.aui_manager.GetPane("Tasks").IsShown() and host.aui_manager.GetPane("Data").IsOk()


def test_pane_close_runs_shutdown(host):
    panel = sidebar.open_viewer(host)
    event = wx.aui.AuiManagerEvent(wx.aui.wxEVT_AUI_PANE_CLOSE)
    event.SetPane(_pane(host))
    event.SetManager(host.aui_manager)
    host.GetEventHandler().ProcessEvent(event)
    assert panel._shut_down is True


def test_show_existing_pane_again(host):
    panel = sidebar.open_viewer(host)
    _pane(host).Hide()
    host.aui_manager.Update()
    assert sidebar.show_viewer(panel) is True
    assert _pane(host).IsShown()


def test_close_viewer_detaches_and_shuts_down(host):
    panel = sidebar.open_viewer(host)
    sidebar.close_viewer(panel)
    assert not _pane(host).IsOk()
    assert not panel  # destroyed


def test_plain_frame_fallback_without_aui():
    parent = wx.Frame(None)
    try:
        panel = sidebar.open_viewer(parent)
        top = panel.GetTopLevelParent()
        assert top is not parent and getattr(top, "_roi_viewer_host", False)
        sidebar.close_viewer(panel)
    finally:
        parent.Destroy()


def test_main_load_uses_the_sidebar_and_reuses_it(host, monkeypatch):
    from plugins.roi_viewer import main

    monkeypatch.setattr(wx, "GetApp", lambda: types.SimpleNamespace(GetTopWindow=lambda: host))
    monkeypatch.setattr(main, "_roi_viewer_window", None)
    monkeypatch.setattr(main, "_subscribe_events", lambda: None)
    main.load()
    first = main._roi_viewer_window
    assert _pane(host).IsOk() and _pane(host).window is first
    main.load()  # chosen again from the Plugins menu: same pane, no second panel
    assert main._roi_viewer_window is first
    assert len([p for p in host.aui_manager.GetAllPanes() if p.name == sidebar.PANE_NAME]) == 1
    sidebar.close_viewer(first)
    main.load()  # after closing, a fresh pane opens
    assert main._roi_viewer_window and main._roi_viewer_window is not first
    sidebar.close_viewer(main._roi_viewer_window)


@pytest.mark.parametrize("colour, rgb", [
    ((0.33, 1, 0.33), (84, 255, 84)),  # InVesalius MASK_COLOUR entry (floats 0..1)
    ((0.9, 0.2, 0.2), (230, 51, 51)),
    ((255, 0, 0), (255, 0, 0)),  # 0..255 still accepted
])
def test_roi_colour_swatch_scale(colour, rgb):
    from plugins.roi_viewer.gui.segmentation_panel import mask_colour_to_wx

    c = mask_colour_to_wx(colour)
    assert (c.Red(), c.Green(), c.Blue()) == rgb
