# --------------------------------------------------------------------------
# Point Picker 3D Module
# Description: Handles 3D point picking in VTK renderer
# --------------------------------------------------------------------------

import numpy as np
from typing import Tuple, Optional, Callable, List


class PointPicker3D:
    """
    Handles 3D point picking functionality.
    Uses VTK's picker functionality.
    """
    
    def __init__(self):
        self.picker = None  # VTK picker will be initialized later
        self.last_picked_point = None
        self.picked_points = []  # History of picked points
        self.callbacks: List[Callable] = []
        self.enabled = True
        self.renderer = None
        self.interactor = None
        self._observer_tag = None

    def initialize_picker(self, renderer, interactor):
        """
        Initialize the VTK picker.

        Args:
            renderer: VTK renderer
            interactor: VTK render window interactor
        """
        try:
            # NOTE: vtkCellPicker/vtkPointPicker live in vtkRenderingCore, not
            # vtkCommonCore (the previous import silently broke all 3D
            # picking: ImportError was swallowed below and self.picker was
            # left as None).
            from vtkmodules.vtkRenderingCore import vtkCellPicker, vtkPointPicker
            from vtkmodules.vtkInteractionStyle import vtkInteractorStyleRubberBandPick

            # If this instance was already initialized (e.g. re-armed
            # after cleanup()), drop the old observer first so repeated
            # init calls never stack up duplicate observers on the same
            # real interactor.
            self.cleanup()

            # Use cell picker for surface picking
            self.picker = vtkCellPicker()
            self.picker.SetTolerance(0.005)

            # Store renderer and interactor
            self.renderer = renderer
            self.interactor = interactor

            # Add observer for mouse click events. Keep the tag so
            # cleanup() can remove exactly this observer later - see
            # cleanup()'s docstring for why this matters.
            self._observer_tag = self.interactor.AddObserver(
                "LeftButtonPressEvent", self._on_left_click
            )

        except ImportError as e:
            print(f"Could not import VTK: {e}")
            self.picker = None

    def cleanup(self):
        """
        Detach this picker from the real VTK interactor.

        NOTE: the real 3D viewer (invesalius.data.viewer_volume.Viewer)
        and its interactor are singletons that outlive any single
        ROIViewerFrame - every time the ROI Viewer plugin window is
        reopened, a brand new PointPicker3D gets initialize_picker()'d
        against the *same* real interactor. Without removing the old
        observer here, each reopen leaves a permanent extra
        "LeftButtonPressEvent" observer whose callback
        (self._on_left_click) still calls into this (now possibly
        destroyed) instance's registered panel callbacks on every
        future 3D click - InVesalius's own crash handler caught exactly
        this for real ("wrapped C/C++ object of type TextCtrl has been
        deleted" from interaction_panel.py's update_coordinates, fired
        from a stale observer after the window that owned it was
        closed). Must be called when the owning ROIViewerFrame is
        destroyed.
        """
        if self.interactor is not None and self._observer_tag is not None:
            try:
                self.interactor.RemoveObserver(self._observer_tag)
            except Exception:
                pass
        self._observer_tag = None
        self.callbacks.clear()
            
    def _on_left_click(self, obj, event):
        """Handle left mouse button click."""
        if not self.enabled:
            return
            
        try:
            from vtkmodules.vtkRenderingCore import vtkCoordinate
            
            # Get click position
            click_pos = self.interactor.GetEventPosition()
            
            # Pick at click position
            if self.picker:
                self.picker.Pick(click_pos[0], click_pos[1], 0, self.renderer)
                
                # Get picked position
                picked_position = self.picker.GetPickPosition()
                
                if picked_position:
                    self.last_picked_point = tuple(picked_position)
                    self.picked_points.append(self.last_picked_point)
                    
                    # Call callbacks
                    for callback in self.callbacks:
                        callback(self.last_picked_point)
                        
        except Exception as e:
            print(f"Error in point picking: {e}")
            
    def pick(self, x: int, y: int) -> Optional[Tuple[float, float, float]]:
        """
        Programmatically pick a point at screen coordinates.
        
        Args:
            x: Screen X coordinate
            y: Screen Y coordinate
            
        Returns:
            Tuple of (world_x, world_y, world_z) or None
        """
        if self.picker and self.enabled:
            self.picker.Pick(x, y, 0, self.renderer)
            picked_position = self.picker.GetPickPosition()
            if picked_position:
                self.last_picked_point = tuple(picked_position)
                return self.last_picked_point
        return None
        
    def add_callback(self, callback: Callable):
        """Add a callback function to be called when a point is picked."""
        self.callbacks.append(callback)
        
    def remove_callback(self, callback: Callable):
        """Remove a callback function."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            
    def clear_points(self):
        """Clear all picked points."""
        self.picked_points.clear()
        self.last_picked_point = None
        
    def enable(self):
        """Enable point picking."""
        self.enabled = True
        
    def disable(self):
        """Disable point picking."""
        self.enabled = False
        
    def get_last_point(self) -> Optional[Tuple[float, float, float]]:
        """Get the last picked point."""
        return self.last_picked_point
        
    def get_pick_distance(self, point1: Tuple[float, float, float], 
                         point2: Tuple[float, float, float]) -> float:
        """
        Calculate Euclidean distance between two 3D points.
        
        Args:
            point1: First point (x, y, z)
            point2: Second point (x, y, z)
            
        Returns:
            Distance in mm
        """
        return np.sqrt(
            (point1[0] - point2[0])**2 +
            (point1[1] - point2[1])**2 +
            (point1[2] - point2[2])**2
        )
