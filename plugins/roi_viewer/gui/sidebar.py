# --------------------------------------------------------------------------
# ROI Viewer sidebar host (30/09/2026).
#
# InVesalius's main window lays out its panels with wx.aui
# (invesalius/gui/frame.py, Frame.__init_aui: `self.aui_manager`, pane
# "Tasks" docked left, the viewers in the centre, import panes shown/hidden
# by name). The ROI Viewer panel is added as one more AUI pane, docked on
# the right like a sidebar - no InVesalius file is changed. Standard AUI
# lets the user drag it to float it or dock it on another side.
#
# Closing the pane (its [X]) runs ROIViewerPanel.shutdown() - the same
# cleanup the old separate window ran on close - and AUI then destroys it
# (DestroyOnClose). Choosing "ROI Viewer" in the Plugins menu again opens a
# fresh pane. If the host window has no AUI manager, a plain frame is used.
#
# InVesalius only imports a plugin when its Plugins-menu item is chosen,
# so the pane cannot appear by itself at application start without a
# change to InVesalius itself (not done - the plugin never edits
# InVesalius).
# --------------------------------------------------------------------------
import wx
import wx.aui

from ..i18n import _
from .roi_panel import ROIViewerPanel

PANE_NAME = "roi_viewer"
SIDEBAR_WIDTH = 400
SIDEBAR_MIN_WIDTH = 340
FLOATING_SIZE = (420, 780)


def aui_manager_of(window):
    manager = getattr(window, "aui_manager", None)
    return manager if isinstance(manager, wx.aui.AuiManager) else None


def pane_info() -> wx.aui.AuiPaneInfo:
    return (
        wx.aui.AuiPaneInfo()
        .Name(PANE_NAME)
        .Caption("ROI Viewer")
        .Right()
        .Layer(1)
        .Position(0)
        .BestSize((SIDEBAR_WIDTH, -1))
        .MinSize((SIDEBAR_MIN_WIDTH, -1))
        .FloatingSize(FLOATING_SIZE)
        .CaptionVisible(True)
        .CloseButton(True)
        .MaximizeButton(False)
        .MinimizeButton(False)
        .PinButton(False)
        .Floatable(True)
        .Dockable(True)
        .DestroyOnClose(True)
    )


def _on_pane_close(event):
    pane = event.GetPane()
    window = getattr(pane, "window", None) if pane is not None else None
    if pane is not None and pane.name == PANE_NAME and isinstance(window, ROIViewerPanel):
        window.shutdown()
    event.Skip()  # AUI then detaches and destroys the pane (DestroyOnClose)


def open_viewer(top_window) -> ROIViewerPanel:
    """Create the panel docked as a sidebar in `top_window` (or in a plain
    frame when there is no AUI manager) and return it."""
    manager = aui_manager_of(top_window)
    if manager is None:
        return _open_in_frame(top_window)
    panel = ROIViewerPanel(top_window)
    manager.AddPane(panel, pane_info())
    if not getattr(top_window, "_roi_viewer_pane_close_bound", False):
        top_window.Bind(wx.aui.EVT_AUI_PANE_CLOSE, _on_pane_close)
        top_window._roi_viewer_pane_close_bound = True
    manager.Update()
    panel.Layout()
    panel.Refresh()  # first paint right away, not only on the next repaint
    return panel


def show_viewer(panel) -> bool:
    """Bring an existing panel back into view. False if it is gone."""
    if not panel:
        return False
    manager = wx.aui.AuiManager.GetManager(panel)
    if manager is not None:
        info = manager.GetPane(panel)
        if info.IsOk():
            info.Show()
            manager.Update()
    top = panel.GetTopLevelParent()
    if top:
        top.Raise()
    panel.SetFocus()
    return True


def close_viewer(panel) -> None:
    """Plugin unload: shut down and remove the panel wherever it lives."""
    if not panel:
        return
    panel.shutdown()
    manager = wx.aui.AuiManager.GetManager(panel)
    if manager is not None and manager.GetPane(panel).IsOk():
        manager.DetachPane(panel)
        panel.Destroy()
        manager.Update()
        return
    host = panel.GetTopLevelParent()
    if getattr(host, "_roi_viewer_host", False):
        host.Destroy()
    else:
        panel.Destroy()


def _open_in_frame(parent) -> ROIViewerPanel:
    host = wx.Frame(parent, title=_("ROI Viewer - CT 3D Visualization"), size=FLOATING_SIZE)
    host._roi_viewer_host = True
    panel = ROIViewerPanel(host)
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(panel, 1, wx.EXPAND)
    host.SetSizer(sizer)

    def on_close(event):
        panel.shutdown()
        host.Destroy()

    host.Bind(wx.EVT_CLOSE, on_close)
    host.Centre()
    host.Show()
    return panel
