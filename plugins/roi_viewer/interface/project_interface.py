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
        
    def _subscribe_events(self):
        """Subscribe to pubsub events for project data."""
        try:
            from invesalius.pubsub import pub as Publisher
            
            Publisher.subscribe(self._on_project_load, "Load project data")
            Publisher.subscribe(self._on_project_close, "Close project data")
            Publisher.subscribe(self._on_slice_change, "Set scroll position")
            Publisher.subscribe(self._on_window_level_change, "Update window level value")
            Publisher.subscribe(self._on_mask_update, "Reload actual slice")
            
        except ImportError:
            pass
            
    def _on_project_load(self):
        """Handle project load event."""
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
        except:
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
        elif plane.upper() == "SAGITTAL":
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
        """Convert world coordinates to voxel indices."""
        i = int(x / self._spacing[0]) if self._spacing[0] != 0 else 0
        j = int(y / self._spacing[1]) if self._spacing[1] != 0 else 0
        k = int(z / self._spacing[2]) if self._spacing[2] != 0 else 0
        
        # Clamp to valid range
        i = max(0, min(i, self._shape[2] - 1))
        j = max(0, min(j, self._shape[1] - 1))
        k = max(0, min(k, self._shape[0] - 1))
        
        return i, j, k
        
    def voxel_to_world(self, i: int, j: int, k: int) -> Tuple[float, float, float]:
        """Convert voxel indices to world coordinates."""
        x = i * self._spacing[0]
        y = j * self._spacing[1]
        z = k * self._spacing[2]
        return x, y, z
        
    def get_mask_dict(self) -> Dict[int, Any]:
        """Get dictionary of masks in the project."""
        try:
            import invesalius.project as prj
            return prj.Project().mask_dict or {}
        except:
            return {}
            
    def get_current_mask(self) -> Optional[Any]:
        """Get the currently selected mask."""
        try:
            import invesalius.data.slice_ as sl
            return sl.Slice().current_mask
        except:
            return None
            
    def get_surface_dict(self) -> Dict[int, Any]:
        """Get dictionary of surfaces in the project."""
        try:
            import invesalius.project as prj
            return prj.Project().surface_dict or {}
        except:
            return {}
            
    def get_project_name(self) -> str:
        """Get the current project name."""
        try:
            import invesalius.project as prj
            return prj.Project().name
        except:
            return ""
            
    def get_patient_name(self) -> str:
        """Get the patient name from DICOM."""
        try:
            import invesalius.project as prj
            proj = prj.Project()
            if proj.dicom_sample:
                return proj.dicom_sample.patient.name
        except:
            pass
        return "Unknown"
