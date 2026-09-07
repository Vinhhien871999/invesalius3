# --------------------------------------------------------------------------
# ROI Manager Module
# Description: Manages ROI (Region of Interest) operations
# --------------------------------------------------------------------------

import numpy as np
from typing import List, Tuple, Optional, Dict, Any


class ROI:
    """
    Represents a Region of Interest.
    """
    
    def __init__(self, name: str, mask_index: int):
        self.name = name
        self.mask_index = mask_index
        self.points = []  # List of (x, y, z) tuples
        self.bounds = None  # (x_min, x_max, y_min, y_max, z_min, z_max)
        self.color = (255, 0, 0)  # RGB
        self.visible = True
        self.locked = False
        self.annotations = []
        
    def add_point(self, x: float, y: float, z: float):
        """Add a point to the ROI."""
        self.points.append((x, y, z))
        self._update_bounds()
        
    def _update_bounds(self):
        """Update the bounding box of the ROI."""
        if self.points:
            points_array = np.array(self.points)
            self.bounds = (
                points_array[:, 0].min(), points_array[:, 0].max(),
                points_array[:, 1].min(), points_array[:, 1].max(),
                points_array[:, 2].min(), points_array[:, 2].max()
            )
            
    def contains_point(self, x: float, y: float, z: float, tolerance: float = 1.0) -> bool:
        """Check if a point is within the ROI bounds."""
        if self.bounds is None:
            return False
        x_min, x_max, y_min, y_max, z_min, z_max = self.bounds
        return (x_min - tolerance <= x <= x_max + tolerance and
                y_min - tolerance <= y <= y_max + tolerance and
                z_min - tolerance <= z <= z_max + tolerance)
                
    def get_center(self) -> Tuple[float, float, float]:
        """Get the center of the ROI."""
        if self.bounds is None:
            return (0, 0, 0)
        x_min, x_max, y_min, y_max, z_min, z_max = self.bounds
        return ((x_min + x_max) / 2, 
                (y_min + y_max) / 2, 
                (z_min + z_max) / 2)
                
    def get_dimensions(self) -> Tuple[float, float, float]:
        """Get the dimensions (width, height, depth) of the ROI."""
        if self.bounds is None:
            return (0, 0, 0)
        x_min, x_max, y_min, y_max, z_min, z_max = self.bounds
        return (x_max - x_min, y_max - y_min, z_max - z_min)


class ROIManager:
    """
    Manages all ROIs in the current project.
    """
    
    def __init__(self):
        self.rois: Dict[int, ROI] = {}
        self.next_id = 0
        self.current_roi_id = None
        
    def create_roi(self, name: str, mask_index: int) -> int:
        """Create a new ROI and return its ID."""
        roi_id = self.next_id
        self.rois[roi_id] = ROI(name, mask_index)
        self.next_id += 1
        self.current_roi_id = roi_id
        return roi_id
        
    def get_roi(self, roi_id: int) -> Optional[ROI]:
        """Get ROI by ID."""
        return self.rois.get(roi_id)
        
    def get_current_roi(self) -> Optional[ROI]:
        """Get the currently selected ROI."""
        if self.current_roi_id is not None:
            return self.rois.get(self.current_roi_id)
        return None
        
    def set_current_roi(self, roi_id: int):
        """Set the currently selected ROI."""
        if roi_id in self.rois:
            self.current_roi_id = roi_id
            
    def delete_roi(self, roi_id: int):
        """Delete a ROI."""
        if roi_id in self.rois:
            del self.rois[roi_id]
            if self.current_roi_id == roi_id:
                self.current_roi_id = None
                
    def get_all_rois(self) -> List[ROI]:
        """Get all ROIs."""
        return list(self.rois.values())
        
    def add_point_to_current(self, x: float, y: float, z: float):
        """Add a point to the current ROI."""
        roi = self.get_current_roi()
        if roi:
            roi.add_point(x, y, z)
            
    def find_roi_at_point(self, x: float, y: float, z: float) -> Optional[int]:
        """Find the ROI that contains the given point."""
        for roi_id, roi in self.rois.items():
            if roi.contains_point(x, y, z):
                return roi_id
        return None
        
    def clear(self):
        """Clear all ROIs."""
        self.rois.clear()
        self.current_roi_id = None
        self.next_id = 0
