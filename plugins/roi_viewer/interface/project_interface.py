# --------------------------------------------------------------------------
# Project Interface Module
# Description: Interface to InVesalius core project/slice data
# --------------------------------------------------------------------------

from typing import Optional, Tuple, Dict, Any
import numpy as np


class ProjectInterface:
    """
    Interface to access InVesalius project data.
    This class provides a clean API to access project data from the core.
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern for project interface."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._project = None
        self._slice = None
        self._spacing = (1.0, 1.0, 1.0)
        self._shape = (0, 0, 0)
        self._window_width = 400
        self._window_level = 40
        
        # Subscribe to project events
        self._subscribe_events()

        # NOTE: this is a lazily-created singleton - the first
        # ProjectInterface() call can happen well after a project was
        # already loaded (e.g. the plugin is loaded from the menu after
        # DICOM import, and nothing touched ProjectInterface before
        # that). Pubsub only delivers messages sent *after* a listener
        # subscribes, so without this call _project/_slice would stay
        # None forever - every method here would silently report "no
        # project" even with one wide open. Sync to whatever already
        # exists right now instead of only reacting to future loads.
        self._refresh_project_data()


    def _subscribe_events(self):
        """Subscribe to pubsub events for project data."""
        try:
            from invesalius.pubsub import pub as Publisher
            
            Publisher.subscribe(self._on_project_load, "Load project data")
            Publisher.subscribe(self._on_project_close, "Close project data")
            # NOTE: "Set scroll position" is only ever sent as
            # ("Set scroll position", "AXIAL"/"SAGITAL"/"CORONAL") with a
            # single `index` kwarg - see invesalius/data/viewer_slice.py.
            # Subscribing to the bare string with a (plane, index) handler
            # raises TypeError from pypubsub on every scroll. Same bug as
            # the one fixed in main.py's _subscribe_events - see that
            # comment for the full explanation.
            for _plane in ("AXIAL", "SAGITAL", "CORONAL"):
                Publisher.subscribe(
                    lambda index, _plane=_plane: self._on_slice_change(_plane, index),
                    ("Set scroll position", _plane),
                )
            Publisher.subscribe(self._on_window_level_change, "Update window level value")
            Publisher.subscribe(self._on_mask_update, "Reload actual slice")

        except ImportError:
            pass

    def _on_project_load(self, create_default_mask=True, end_busy_cursor=True):
        """
        Handle project load event.

        NOTE: pypubsub infers this topic's accepted arguments from
        invesalius.control.Controller.LoadProject, the first subscriber
        (`create_default_mask=True, end_busy_cursor=True` - see
        invesalius/control.py:853), and requires every subscriber to
        accept them. A zero-arg handler here raised ListenerMismatchError
        the moment anything tried to instantiate ProjectInterface().
        """
        self._refresh_project_data()

    def _on_project_close(self):
        """Handle project close event."""
        self._project = None
        self._slice = None
        self._shape = (0, 0, 0)

    def _on_slice_change(self, plane, index):
        """Handle slice position change."""
        pass  # Events are handled by the UI
        
    def _on_window_level_change(self, window, level):
        """Handle window/level change."""
        self._window_width = window
        self._window_level = level
        
    def _on_mask_update(self):
        """Handle mask update event."""
        pass  # Events are handled by the UI
        
    def _refresh_project_data(self):
        """Refresh project data from core."""
        try:
            import invesalius.project as prj
            import invesalius.data.slice_ as sl
            
            self._project = prj.Project()
            self._slice = sl.Slice()
            
            # Get shape and spacing
            if self._slice.matrix is not None:
                self._shape = self._slice.matrix.shape
                self._spacing = self._slice.spacing
                
        except Exception as e:
            print(f"Error refreshing project data: {e}")
            
    def is_project_loaded(self) -> bool:
        """Check if a project is loaded."""
        try:
            import invesalius.project as prj
            return prj.Project().name != ""
        except Exception as e:
            print(f"ROI Viewer: is_project_loaded check failed - {e}")
            return False
            
    def get_volume_data(self) -> Optional[np.ndarray]:
        """Get the 3D volume data matrix."""
        if self._slice and self._slice.matrix is not None:
            return np.asarray(self._slice.matrix)
        return None
        
    def get_slice(self, plane: str, index: int) -> Optional[np.ndarray]:
        """
        Get a 2D slice from the volume.
        
        Args:
            plane: Plane name (AXIAL, CORONAL, SAGITTAL)
            index: Slice index
            
        Returns:
            2D numpy array or None
        """
        volume = self.get_volume_data()
        if volume is None:
            return None
            
        if plane.upper() == "AXIAL":
            if 0 <= index < volume.shape[0]:
                return volume[index]
        elif plane.upper() == "CORONAL":
            if 0 <= index < volume.shape[1]:
                return volume[:, index, :]
        elif plane.upper() in ("SAGITAL", "SAGITTAL"):
            # NOTE: real InVesalius pubsub messages use the one-T spelling
            # "SAGITAL" (see invesalius/control.py, invesalius/data/
            # viewer_slice.py); this method only ever matched the more
            # common two-T spelling, so it silently returned None for any
            # plane string that actually came from real InVesalius data.
            # Both spellings are accepted here.
            if 0 <= index < volume.shape[2]:
                return volume[:, :, index]
                
        return None
        
    def get_spacing(self) -> Tuple[float, float, float]:
        """Get voxel spacing (x, y, z) in mm."""
        return self._spacing
        
    def get_shape(self) -> Tuple[int, int, int]:
        """Get volume shape (slices, height, width)."""
        return self._shape
        
    def get_window_level(self) -> Tuple[float, float]:
        """Get current window width and level."""
        if self._slice:
            return self._slice.window_width, self._slice.window_level
        return self._window_width, self._window_level
        
    def set_window_level(self, window: float, level: float):
        """Set window width and level."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("Update window level value", window=window, level=level)
        except ImportError:
            pass
            
    def get_hounsfield_range(self) -> Tuple[int, int]:
        """Get HU range for CT images."""
        volume = self.get_volume_data()
        if volume is not None:
            return int(volume.min()), int(volume.max())
        return -1024, 3071  # Default CT range
        
    def world_to_voxel(self, x: float, y: float, z: float) -> Tuple[int, int, int]:
        """
        Convert a VTK world-space point (mm) to a (axial, coronal,
        sagital) index into self._shape / Slice().matrix.

        NOTE: self._spacing is index-aligned with self._shape
        (Slice().matrix.shape): axis 0 = AXIAL, 1 = CORONAL, 2 = SAGITAL
        (see the axis-swap code in invesalius/data/slice_.py, which
        permutes both together). InVesalius's VTK actors use the
        standard convention where world X is the fastest-varying image
        axis (SAGITAL), Y is CORONAL, and Z is the AXIAL slice stack -
        see core/sync_2d3d.py's world_to_voxel() for the same mapping,
        used for the exact same reason.
        """
        axial = int(z / self._spacing[0]) if self._spacing[0] != 0 else 0
        coronal = int(y / self._spacing[1]) if self._spacing[1] != 0 else 0
        sagital = int(x / self._spacing[2]) if self._spacing[2] != 0 else 0

        # Clamp to valid range
        axial = max(0, min(axial, self._shape[0] - 1))
        coronal = max(0, min(coronal, self._shape[1] - 1))
        sagital = max(0, min(sagital, self._shape[2] - 1))

        return axial, coronal, sagital

    def voxel_to_world(self, axial: int, coronal: int, sagital: int) -> Tuple[float, float, float]:
        """Inverse of world_to_voxel() - see its docstring for the axis mapping."""
        x = sagital * self._spacing[2]
        y = coronal * self._spacing[1]
        z = axial * self._spacing[0]
        return x, y, z
        
    def get_mask_dict(self) -> Dict[int, Any]:
        """Get dictionary of masks in the project."""
        try:
            import invesalius.project as prj
            return prj.Project().mask_dict or {}
        except Exception as e:
            print(f"ROI Viewer: get_mask_dict failed - {e}")
            return {}
            
    def get_current_mask(self) -> Optional[Any]:
        """Get the currently selected mask."""
        try:
            import invesalius.data.slice_ as sl
            return sl.Slice().current_mask
        except Exception as e:
            print(f"ROI Viewer: get_current_mask failed - {e}")
            return None
            
    def get_surface_dict(self) -> Dict[int, Any]:
        """Get dictionary of surfaces in the project."""
        try:
            import invesalius.project as prj
            return prj.Project().surface_dict or {}
        except Exception as e:
            print(f"ROI Viewer: get_surface_dict failed - {e}")
            return {}
            
    def get_project_name(self) -> str:
        """Get the current project name."""
        try:
            import invesalius.project as prj
            return prj.Project().name
        except Exception as e:
            print(f"ROI Viewer: get_project_name failed - {e}")
            return ""
            
    def get_patient_name(self) -> str:
        """Get the patient name from DICOM."""
        # NOTE: Project has no `dicom_sample` attribute (that was a guess -
        # it always raised AttributeError, silently swallowed by the bare
        # except below, so this always returned "Unknown"). The patient's
        # name is stored directly on Project.name - see the "# patient's
        # name" comment next to `self.name` in invesalius/project.py.
        try:
            import invesalius.project as prj
            name = prj.Project().name
            return name if name else "Unknown"
        except Exception:
            return "Unknown"
