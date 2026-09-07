# --------------------------------------------------------------------------
# ROI Viewer Plugin - Entry Point
# Software:     InVesalius ROI Viewer Plugin
# Description:  Interactive 3D CT visualization and ROI editing
# --------------------------------------------------------------------------

import wx
import os

from .gui import roi_panel, interaction_panel, measurement_panel, annotation_panel, export_panel
from .interface import project_interface, view_interface, task_panel

# Global reference to the main window
_main_frame = None
_roi_viewer_window = None

# Per-plane slice-change listeners registered in _subscribe_events(), kept
# around so unload() can unsubscribe the exact same callables (they are
# lambdas, not _on_slice_change itself - see _subscribe_events()).
_slice_change_listeners = []


def load():
    """
    Load the ROI Viewer plugin.
    This function is called when the plugin is selected from the menu.
    """
    global _main_frame, _roi_viewer_window
    
    top_window = wx.GetApp().GetTopWindow()
    _main_frame = top_window
    
    # Create main ROI Viewer window
    _roi_viewer_window = roi_panel.ROIViewerFrame(top_window)
    _roi_viewer_window.Show()
    
    # Subscribe to pubsub events
    _subscribe_events()
    
    print("ROI Viewer plugin loaded successfully")


def _subscribe_events():
    """
    Subscribe to relevant pubsub events from InVesalius core.
    """
    try:
        from invesalius.pubsub import pub as Publisher
        
        # Project events
        Publisher.subscribe(_on_project_load, "Load project data")
        Publisher.subscribe(_on_project_close, "Close project data")
        
        # Slice events.
        # NOTE: "Set scroll position" is a hierarchical topic in InVesalius
        # core - it is only ever sent as ("Set scroll position", "AXIAL") /
        # ("Set scroll position", "SAGITAL") / ("Set scroll position",
        # "CORONAL") with a single `index` kwarg (see
        # invesalius/control.py and invesalius/data/viewer_slice.py, which
        # subscribes with `Publisher.subscribe(handler, ("Set scroll
        # position", self.orientation))` and `def handler(self, index)`).
        # Subscribing to the bare string with a (plane, index) handler, as
        # this used to do, means pypubsub calls the handler with only
        # `index` and raises a TypeError on every single slice scroll once
        # this plugin is loaded. Subscribe per-plane instead, matching the
        # real topic shape exactly.
        global _slice_change_listeners
        _slice_change_listeners = []
        for _plane in ("AXIAL", "SAGITAL", "CORONAL"):
            listener = lambda index, _plane=_plane: _on_slice_change(_plane, index)
            Publisher.subscribe(listener, ("Set scroll position", _plane))
            _slice_change_listeners.append((listener, _plane))
        Publisher.subscribe(_on_mask_update, "Reload actual slice")
        
        # Mask events
        Publisher.subscribe(_on_mask_created, "Create new mask")
        Publisher.subscribe(_on_mask_selected, "Change mask selected")
        
        print("ROI Viewer: Subscribed to pubsub events")
    except ImportError as e:
        print(f"ROI Viewer: Could not import Publisher - {e}")


def _on_project_load(create_default_mask=True, end_busy_cursor=True):
    """
    Handle project load event.

    NOTE: pypubsub infers each topic's accepted arguments from every
    subscriber (invesalius.control.Controller.LoadProject subscribes
    first, with `create_default_mask=True, end_busy_cursor=True`), and
    requires every other subscriber on that same topic to be able to
    accept them too - see invesalius/control.py:853. A zero-arg handler
    here raised `ListenerMismatchError` at subscribe time, which crashed
    the whole plugin the instant `load()` ran, before any of the other
    subscriptions below were even registered.
    """
    global _roi_viewer_window
    if _roi_viewer_window:
        _roi_viewer_window.on_project_load()


def _on_project_close():
    """Handle project close event."""
    global _roi_viewer_window
    if _roi_viewer_window:
        _roi_viewer_window.on_project_close()


def _on_slice_change(plane, index):
    """Handle slice position change."""
    global _roi_viewer_window
    if _roi_viewer_window:
        _roi_viewer_window.on_slice_change(plane, index)


def _on_mask_update():
    """Handle mask update event."""
    global _roi_viewer_window
    if _roi_viewer_window:
        _roi_viewer_window.on_mask_update()


def _on_mask_created(mask_name, thresh, colour):
    """Handle mask created event."""
    global _roi_viewer_window
    if _roi_viewer_window:
        _roi_viewer_window.on_mask_created(mask_name, thresh, colour)


def _on_mask_selected(index):
    """Handle mask selected event."""
    global _roi_viewer_window
    if _roi_viewer_window:
        _roi_viewer_window.on_mask_selected(index)


def get_plugin_info():
    """
    Return information about the plugin.
    
    Returns:
        dict: A dictionary containing plugin information
    """
    return {
        "name": "ROI Viewer",
        "description": "Interactive 3D CT visualization and ROI editing plugin with "
                      "2D-3D synchronization, measurements, and annotations. "
                      "This plugin provides advanced ROI editing tools for medical image analysis.",
        "version": "1.0.0",
        "author": "Student Research Project",
        "contact": "",
        "features": [
            "2D-3D synchronization and interaction",
            "ROI/Mask editing with brush and eraser",
            "Distance and area/volume measurements",
            "Annotation with text notes",
            "Export masks and surfaces"
        ]
    }


def unload():
    """
    Unload the plugin and cleanup.
    """
    global _roi_viewer_window
    
    try:
        from invesalius.pubsub import pub as Publisher
        
        # Unsubscribe from events
        Publisher.unsubscribe(_on_project_load, "Load project data")
        Publisher.unsubscribe(_on_project_close, "Close project data")
        for listener, plane in _slice_change_listeners:
            Publisher.unsubscribe(listener, ("Set scroll position", plane))
        _slice_change_listeners.clear()
        Publisher.unsubscribe(_on_mask_update, "Reload actual slice")
        Publisher.unsubscribe(_on_mask_created, "Create new mask")
        Publisher.unsubscribe(_on_mask_selected, "Change mask selected")
    except ImportError:
        pass
    
    if _roi_viewer_window:
        _roi_viewer_window.Destroy()
        _roi_viewer_window = None
    
    print("ROI Viewer plugin unloaded")
