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
        
        # Slice events
        Publisher.subscribe(_on_slice_change, "Set scroll position")
        Publisher.subscribe(_on_mask_update, "Reload actual slice")
        
        # Mask events
        Publisher.subscribe(_on_mask_created, "Create new mask")
        Publisher.subscribe(_on_mask_selected, "Change mask selected")
        
        print("ROI Viewer: Subscribed to pubsub events")
    except ImportError as e:
        print(f"ROI Viewer: Could not import Publisher - {e}")


def _on_project_load():
    """Handle project load event."""
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
        Publisher.unsubscribe(_on_project_load)
        Publisher.unsubscribe(_on_project_close)
        Publisher.unsubscribe(_on_slice_change)
        Publisher.unsubscribe(_on_mask_update)
        Publisher.unsubscribe(_on_mask_created)
        Publisher.unsubscribe(_on_mask_selected)
    except ImportError:
        pass
    
    if _roi_viewer_window:
        _roi_viewer_window.Destroy()
        _roi_viewer_window = None
    
    print("ROI Viewer plugin unloaded")
