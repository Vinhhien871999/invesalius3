# --------------------------------------------------------------------------
# ROI Viewer Plugin - Entry Point
# Software:     InVesalius ROI Viewer Plugin
# Description:  Interactive 3D CT visualization and ROI editing
# --------------------------------------------------------------------------

import wx
import os

from .gui import roi_panel, interaction_panel, measurement_panel, annotation_panel, export_panel
from .interface import project_interface, view_interface

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

    # NOTE: nothing prevented this from running again while a ROI
    # Viewer window was already open (selecting "ROI Viewer" from the
    # Plugins menu more than once) - each call created a whole second
    # ROIViewerFrame with its own new PointPicker3D, which
    # initialize_picker() then attached to the *same* real, singleton
    # VTK interactor (invesalius.data.viewer_volume.Viewer outlives any
    # single plugin window). Every extra open left one more permanent
    # observer on that interactor, and _subscribe_events() below
    # duplicated every pubsub subscription too. If the user later
    # closed one of the windows, its stale observer/subscriptions kept
    # firing into now-destroyed widgets - this is exactly the real
    # crash InVesalius's own crash handler caught ("wrapped C/C++
    # object of type TextCtrl has been deleted" from interaction_panel.
    # py's update_coordinates). Reuse the existing window instead of
    # creating a second one.
    if _roi_viewer_window is not None:
        try:
            _roi_viewer_window.Raise()
            _roi_viewer_window.SetFocus()
            print("ROI Viewer: window already open, bringing it to front")
            return
        except RuntimeError:
            # The wx C++ object is gone (window was closed) even though
            # this module-level reference wasn't cleared - fall through
            # and create a fresh one.
            _roi_viewer_window = None

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

        # NOTE (Round-2 audit, section E): these three additionally
        # keep ROIManager's cache in sync with masks renamed/hidden/
        # removed through InVesalius's OWN native Masks tab, not just
        # through this plugin's own ROI List buttons - see
        # core/roi_manager.py's module docstring. Signatures matched
        # exactly to invesalius/data/slice_.py's real subscribers
        # (__set_mask_name(index, name), __show_mask(index, value),
        # OnRemoveMasks(mask_indexes)) - Slice() is always the first
        # subscriber on these topics (registered at app startup, well
        # before any plugin loads), so it fixes each topic's pypubsub
        # message-data-spec; a mismatched signature here would raise
        # ListenerMismatchError at subscribe time.
        Publisher.subscribe(_on_mask_name_changed, "Change mask name")
        Publisher.subscribe(_on_mask_visibility_changed, "Show mask")
        Publisher.subscribe(_on_masks_removed, "Remove masks")

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
        _roi_viewer_window.on_roi_source_changed()


def _on_mask_selected(index):
    """Handle mask selected event."""
    global _roi_viewer_window
    if _roi_viewer_window:
        _roi_viewer_window.on_mask_selected(index)


def _on_mask_name_changed(index, name):
    """A mask was renamed (through this plugin or InVesalius's native Masks tab)."""
    global _roi_viewer_window
    if _roi_viewer_window:
        _roi_viewer_window.on_roi_source_changed()


def _on_mask_visibility_changed(index, value):
    """A mask's visibility was toggled (through this plugin or the native Masks tab)."""
    global _roi_viewer_window
    if _roi_viewer_window:
        _roi_viewer_window.on_roi_source_changed()


def _on_masks_removed(mask_indexes):
    """One or more masks were removed (through this plugin or the native Masks tab)."""
    global _roi_viewer_window
    if _roi_viewer_window:
        _roi_viewer_window.on_roi_source_changed()


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
        Publisher.unsubscribe(_on_mask_name_changed, "Change mask name")
        Publisher.unsubscribe(_on_mask_visibility_changed, "Show mask")
        Publisher.unsubscribe(_on_masks_removed, "Remove masks")
    except ImportError:
        pass
    
    if _roi_viewer_window:
        # NOTE: Close() (not Destroy() directly) so ROIViewerFrame's own
        # EVT_CLOSE handler runs first and detaches the shared picker
        # from the real VTK interactor - see picker_3d.PointPicker3D.
        # cleanup()'s docstring and roi_panel.ROIViewerFrame._on_close().
        # Calling Destroy() here directly used to skip that cleanup
        # entirely.
        _roi_viewer_window.Close()
        _roi_viewer_window = None
    
    print("ROI Viewer plugin unloaded")
