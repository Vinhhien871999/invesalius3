# --------------------------------------------------------------------------
# View Interface Module
# Description: Interface to InVesalius viewer controls
# --------------------------------------------------------------------------

from typing import Optional, Tuple, Callable, List
import wx


class ViewInterface:
    """
    Interface to control InVesalius viewers.
    This class provides methods to control the 2D/3D views.
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._frame = None
        self._current_plane = "AXIAL"
        self._current_slice_index = 0
        
        # Callbacks for view events
        self._slice_change_callbacks: List[Callable] = []
        
        # Subscribe to events
        self._subscribe_events()
        
    def _subscribe_events(self):
        """Subscribe to view-related pubsub events."""
        try:
            from invesalius.pubsub import pub as Publisher
            
            # NOTE: same "Set scroll position" hierarchical-topic bug fixed
            # in main.py and project_interface.py - see the comment in
            # main.py's _subscribe_events() for the full explanation.
            for _plane in ("AXIAL", "SAGITAL", "CORONAL"):
                Publisher.subscribe(
                    lambda index, _plane=_plane: self._on_set_scroll_position(_plane, index),
                    ("Set scroll position", _plane),
                )
            Publisher.subscribe(self._on_render_volume, "Render volume viewer")

        except ImportError:
            pass

    def _on_set_scroll_position(self, plane, index):
        """Handle scroll position change."""
        self._current_plane = plane
        self._current_slice_index = index
        
        # Notify callbacks
        for callback in self._slice_change_callbacks:
            callback(plane, index)
            
    def _on_render_volume(self):
        """Handle volume render request."""
        pass  # Rendering is handled by the core
        
    def set_frame(self, frame: wx.Frame):
        """Set the main frame reference."""
        self._frame = frame
        
    def get_frame(self) -> Optional[wx.Frame]:
        """Get the main frame."""
        return self._frame
        
    def set_slice_position(self, plane: str, index: int):
        """
        Set the current slice position.
        
        Args:
            plane: Plane name (AXIAL, CORONAL, SAGITTAL)
            index: Slice index
        """
        try:
            from invesalius.pubsub import pub as Publisher

            # NOTE: real InVesalius subscribers listen on the per-plane
            # tuple topic with a single `index` kwarg - see
            # invesalius/data/viewer_slice.py's
            # `Publisher.subscribe(self.ChangeSliceNumber, ("Set scroll
            # position", self.orientation))` where
            # `def ChangeSliceNumber(self, index)`. Sending the bare
            # string with a `plane=` kwarg (as this used to do) reaches no
            # real listener, so the 2D viewers never actually move.
            Publisher.sendMessage(("Set scroll position", plane), index=index)

            self._current_plane = plane
            self._current_slice_index = index

        except ImportError:
            pass
            
    def get_slice_position(self) -> Tuple[str, int]:
        """Get the current slice position."""
        return self._current_plane, self._current_slice_index
        
    def next_slice(self):
        """Move to the next slice."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage(
                ("Set scroll position", self._current_plane),
                index=self._current_slice_index + 1
            )
        except ImportError:
            pass

    def previous_slice(self):
        """Move to the previous slice."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage(
                ("Set scroll position", self._current_plane),
                index=max(0, self._current_slice_index - 1)
            )
        except ImportError:
            pass
            
    def request_render(self):
        """Request a volume render update."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("Render volume viewer")
        except ImportError:
            pass
            
    def set_zoom(self, zoom_factor: float):
        """
        Set the zoom factor for the current view.
        
        Args:
            zoom_factor: Zoom level (1.0 = 100%)
        """
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("Set zoom", factor=zoom_factor)
        except ImportError:
            pass
            
    def add_slice_change_callback(self, callback: Callable):
        """Add a callback for slice position changes."""
        if callback not in self._slice_change_callbacks:
            self._slice_change_callbacks.append(callback)
            
    def remove_slice_change_callback(self, callback: Callable):
        """Remove a slice change callback."""
        if callback in self._slice_change_callbacks:
            self._slice_change_callbacks.remove(callback)
            
    def show_import_dialog(self):
        """Show the import directory dialog."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("Show import directory dialog")
        except ImportError:
            pass
            
    def show_open_project_dialog(self):
        """Show the open project dialog."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("Show open project dialog")
        except ImportError:
            pass
            
    def show_save_project_dialog(self):
        """Show the save project dialog."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("Show save dialog")
        except ImportError:
            pass
