# --------------------------------------------------------------------------
# Measurement Module
# Description: Measurement tools for distance, area, and volume
# --------------------------------------------------------------------------

import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import time


@dataclass
class DistanceMeasurement:
    """Represents a distance measurement."""
    name: str
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    distance: float
    unit: str = "mm"
    measurement_type: str = "3D"  # "2D" or "3D"


@dataclass
class AreaMeasurement:
    """Represents an area measurement."""
    name: str
    points: List[Tuple[float, float]]  # 2D polygon points
    area: float
    unit: str = "mm²"
    plane: str = "AXIAL"


@dataclass
class VolumeMeasurement:
    """Represents a volume measurement."""
    name: str
    mask_index: int
    volume: float
    unit: str = "mm³"


class MeasurementManager:
    """
    Manages all measurements in the ROI Viewer.
    """
    
    def __init__(self):
        self.distance_measurements: List[DistanceMeasurement] = []
        self.area_measurements: List[AreaMeasurement] = []
        self.volume_measurements: List[VolumeMeasurement] = []
        
        self.current_distance_points: List[Tuple[float, float, float]] = []
        self.spacing = (1.0, 1.0, 1.0)  # mm per voxel
        
        self.measurement_counter = 0
        
    def set_spacing(self, spacing: Tuple[float, float, float]):
        """
        Set voxel spacing for accurate measurements.
        
        Args:
            spacing: Voxel spacing in mm (x, y, z)
        """
        self.spacing = spacing
        
    def start_distance_measurement(self):
        """Start a new distance measurement."""
        self.current_distance_points = []
        
    def add_point(self, x: float, y: float, z: float):
        """
        Add a point to the current distance measurement.
        
        Args:
            x, y, z: World coordinates in mm
        """
        self.current_distance_points.append((x, y, z))
        
    def finish_distance_measurement(self, measurement_type: str = "3D") -> Optional[DistanceMeasurement]:
        """
        Finish the current distance measurement and create a measurement object.
        
        Args:
            measurement_type: "2D" or "3D"
            
        Returns:
            DistanceMeasurement object or None if not enough points
        """
        if len(self.current_distance_points) < 2:
            self.current_distance_points = []
            return None
            
        self.measurement_counter += 1
        p1 = self.current_distance_points[0]
        p2 = self.current_distance_points[-1]
        
        if measurement_type == "3D":
            # Calculate 3D Euclidean distance
            distance = self._calculate_3d_distance(p1, p2)
        else:
            # Calculate 2D distance (on current plane)
            distance = self._calculate_2d_distance(p1, p2)
            
        measurement = DistanceMeasurement(
            name=f"D{self.measurement_counter:03d}",
            start_point=p1,
            end_point=p2,
            distance=distance,
            measurement_type=measurement_type
        )
        
        self.distance_measurements.append(measurement)
        self.current_distance_points = []
        
        return measurement
        
    def _calculate_3d_distance(self, p1: Tuple[float, float, float],
                               p2: Tuple[float, float, float]) -> float:
        """
        Calculate 3D Euclidean distance.
        
        Args:
            p1: First point (x, y, z) in mm
            p2: Second point (x, y, z) in mm
            
        Returns:
            Distance in mm
        """
        dx = (p1[0] - p2[0]) * self.spacing[0]
        dy = (p1[1] - p2[1]) * self.spacing[1]
        dz = (p1[2] - p2[2]) * self.spacing[2]
        return np.sqrt(dx**2 + dy**2 + dz**2)
        
    def _calculate_2d_distance(self, p1: Tuple[float, float, float],
                               p2: Tuple[float, float, float]) -> float:
        """
        Calculate 2D distance (projected on a plane).
        
        Args:
            p1: First point (x, y, z) in mm
            p2: Second point (x, y, z) in mm
            
        Returns:
            Distance in mm
        """
        dx = (p1[0] - p2[0]) * self.spacing[0]
        dy = (p1[1] - p2[1]) * self.spacing[1]
        return np.sqrt(dx**2 + dy**2)
        
    def calculate_area(self, points: List[Tuple[float, float]]) -> float:
        """
        Calculate area of a polygon using the Shoelace formula.
        
        Args:
            points: List of (x, y) points in pixel coordinates
            
        Returns:
            Area in mm²
        """
        if len(points) < 3:
            return 0.0
            
        # Convert to numpy array
        poly = np.array(points)
        
        # Shoelace formula
        x = poly[:, 0] * self.spacing[0]  # Convert to mm
        y = poly[:, 1] * self.spacing[1]  # Convert to mm
        n = len(points)
        
        area = 0.5 * abs(sum(x[i] * y[(i+1) % n] - x[(i+1) % n] * y[i] for i in range(n)))
        
        return area
        
    def add_area_measurement(self, name: str, points: List[Tuple[float, float]],
                            plane: str = "AXIAL") -> AreaMeasurement:
        """
        Add an area measurement.
        
        Args:
            name: Measurement name
            points: Polygon points in pixel coordinates
            plane: Plane name (AXIAL, CORONAL, SAGITTAL)
            
        Returns:
            AreaMeasurement object
        """
        self.measurement_counter += 1
        area = self.calculate_area(points)
        
        measurement = AreaMeasurement(
            name=name or f"A{self.measurement_counter:03d}",
            points=points,
            area=area,
            plane=plane
        )
        
        self.area_measurements.append(measurement)
        return measurement
        
    def calculate_volume(self, mask: np.ndarray) -> float:
        """
        Calculate volume of a binary mask.
        
        Args:
            mask: 3D binary mask (numpy array)
            
        Returns:
            Volume in mm³
        """
        # Count voxels in mask
        voxel_count = np.sum(mask > 0)
        
        # Calculate volume (voxel volume = spacing_x * spacing_y * spacing_z)
        voxel_volume = self.spacing[0] * self.spacing[1] * self.spacing[2]
        volume = voxel_count * voxel_volume
        
        return volume
        
    def add_volume_measurement(self, name: str, mask_index: int,
                              mask: np.ndarray) -> VolumeMeasurement:
        """
        Add a volume measurement.
        
        Args:
            name: Measurement name
            mask_index: Index of the mask
            mask: 3D binary mask
            
        Returns:
            VolumeMeasurement object
        """
        self.measurement_counter += 1
        volume = self.calculate_volume(mask)
        
        measurement = VolumeMeasurement(
            name=name or f"V{self.measurement_counter:03d}",
            mask_index=mask_index,
            volume=volume
        )
        
        self.volume_measurements.append(measurement)
        return measurement
        
    def get_all_measurements(self) -> Dict[str, List]:
        """Get all measurements."""
        return {
            'distance': self.distance_measurements,
            'area': self.area_measurements,
            'volume': self.volume_measurements
        }
        
    def get_distance_count(self) -> int:
        """Get the number of distance measurements."""
        return len(self.distance_measurements)
        
    def get_area_count(self) -> int:
        """Get the number of area measurements."""
        return len(self.area_measurements)
        
    def get_volume_count(self) -> int:
        """Get the number of volume measurements."""
        return len(self.volume_measurements)
        
    def delete_measurement(self, measurement_type: str, index: int):
        """Delete a measurement."""
        if measurement_type == 'distance' and 0 <= index < len(self.distance_measurements):
            del self.distance_measurements[index]
        elif measurement_type == 'area' and 0 <= index < len(self.area_measurements):
            del self.area_measurements[index]
        elif measurement_type == 'volume' and 0 <= index < len(self.volume_measurements):
            del self.volume_measurements[index]
            
    def clear(self):
        """Clear all measurements."""
        self.distance_measurements.clear()
        self.area_measurements.clear()
        self.volume_measurements.clear()
        self.current_distance_points.clear()
        self.measurement_counter = 0
        
    def clear_current(self):
        """Clear the current (in-progress) measurement."""
        self.current_distance_points = []
