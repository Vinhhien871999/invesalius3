# --------------------------------------------------------------------------
# Utils Module - Helper Functions
# Description: Utility functions for the ROI Viewer plugin
# --------------------------------------------------------------------------

import numpy as np
from typing import Tuple, Optional
import math


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(value, max_val))


def world_to_voxel(x: float, y: float, z: float,
                   spacing: Tuple[float, float, float],
                   origin: Tuple[float, float, float] = (0, 0, 0)) -> Tuple[int, int, int]:
    """
    Convert world coordinates to voxel coordinates.
    
    Args:
        x, y, z: World coordinates
        spacing: Voxel spacing (sx, sy, sz) in mm
        origin: Volume origin
        
    Returns:
        Tuple of (i, j, k) voxel indices
    """
    i = int((x - origin[0]) / spacing[0]) if spacing[0] != 0 else 0
    j = int((y - origin[1]) / spacing[1]) if spacing[1] != 0 else 0
    k = int((z - origin[2]) / spacing[2]) if spacing[2] != 0 else 0
    
    return i, j, k


def voxel_to_world(i: int, j: int, k: int,
                   spacing: Tuple[float, float, float],
                   origin: Tuple[float, float, float] = (0, 0, 0)) -> Tuple[float, float, float]:
    """
    Convert voxel coordinates to world coordinates.
    
    Args:
        i, j, k: Voxel indices
        spacing: Voxel spacing (sx, sy, sz) in mm
        origin: Volume origin
        
    Returns:
        Tuple of (x, y, z) world coordinates in mm
    """
    x = i * spacing[0] + origin[0]
    y = j * spacing[1] + origin[1]
    z = k * spacing[2] + origin[2]
    
    return x, y, z


def calculate_slice_index_from_world(z_world: float,
                                    spacing: Tuple[float, float, float],
                                    orientation: str = "AXIAL") -> int:
    """
    Calculate slice index from world Z coordinate.
    
    Args:
        z_world: World Z coordinate
        spacing: Voxel spacing
        orientation: Slice orientation (AXIAL, CORONAL, SAGITTAL)
        
    Returns:
        Slice index
    """
    if orientation == "AXIAL":
        return int(z_world / spacing[2])
    elif orientation == "CORONAL":
        return int(z_world / spacing[1])
    else:  # SAGITTAL
        return int(z_world / spacing[0])


def format_distance(distance_mm: float) -> str:
    """Format distance in mm to human readable string."""
    if distance_mm < 1:
        return f"{distance_mm * 1000:.2f} µm"
    elif distance_mm < 10:
        return f"{distance_mm:.2f} mm"
    elif distance_mm < 100:
        return f"{distance_mm:.1f} mm"
    else:
        return f"{distance_mm:.0f} mm"


def format_area(area_mm2: float) -> str:
    """Format area in mm² to human readable string."""
    if area_mm2 < 1:
        return f"{area_mm2 * 1e6:.2f} µm²"
    elif area_mm2 < 100:
        return f"{area_mm2:.2f} mm²"
    elif area_mm2 < 1e6:
        return f"{area_mm2 / 100:.2f} cm²"
    else:
        return f"{area_mm2 / 1e6:.2f} m²"


def format_volume(volume_mm3: float) -> str:
    """Format volume in mm³ to human readable string."""
    if volume_mm3 < 1:
        return f"{volume_mm3 * 1e9:.2f} µm³"
    elif volume_mm3 < 1000:
        return f"{volume_mm3:.2f} mm³"
    elif volume_mm3 < 1e6:
        return f"{volume_mm3 / 1000:.2f} cm³"
    elif volume_mm3 < 1e9:
        return f"{volume_mm3 / 1e6:.2f} ml"
    else:
        return f"{volume_mm3 / 1e9:.2f} L"


def create_circular_mask(shape: Tuple[int, int], center: Tuple[int, int],
                         radius: int) -> np.ndarray:
    """
    Create a circular binary mask.
    
    Args:
        shape: Image shape (height, width)
        center: Circle center (y, x)
        radius: Circle radius
        
    Returns:
        Binary mask array
    """
    y, x = np.ogrid[:shape[0], :shape[1]]
    dist = np.sqrt((x - center[1])**2 + (y - center[0])**2)
    return (dist <= radius).astype(np.uint8)


def create_rectangular_mask(shape: Tuple[int, int], top_left: Tuple[int, int],
                           bottom_right: Tuple[int, int]) -> np.ndarray:
    """
    Create a rectangular binary mask.
    
    Args:
        shape: Image shape (height, width)
        top_left: Top-left corner (y, x)
        bottom_right: Bottom-right corner (y, x)
        
    Returns:
        Binary mask array
    """
    mask = np.zeros(shape, dtype=np.uint8)
    mask[top_left[0]:bottom_right[0], top_left[1]:bottom_right[1]] = 1
    return mask


def apply_brush_to_slice(slice_data: np.ndarray, mask: np.ndarray,
                        x: int, y: int, brush_size: int,
                        brush_shape: str = 'circle',
                        value: int = 255,
                        operation: str = 'draw') -> np.ndarray:
    """
    Apply brush to a single slice.
    
    Args:
        slice_data: 2D slice data
        mask: Current mask slice
        x, y: Center position
        brush_size: Brush radius
        brush_shape: 'circle' or 'square'
        value: Drawing value
        operation: 'draw', 'erase', or 'threshold'
        
    Returns:
        Updated mask slice
    """
    h, w = slice_data.shape
    
    if brush_shape == 'circle':
        y1, y2 = max(0, y - brush_size), min(h, y + brush_size + 1)
        x1, x2 = max(0, x - brush_size), min(w, x + brush_size + 1)
        
        if y1 >= y2 or x1 >= x2:
            return mask
            
        yy, xx = np.ogrid[y1:y2, x1:x2]
        dist = np.sqrt((xx - x)**2 + (yy - y)**2)
        brush_mask = dist <= brush_size
    else:  # square
        y1, y2 = max(0, y - brush_size), min(h, y + brush_size + 1)
        x1, x2 = max(0, x - brush_size), min(w, x + brush_size + 1)
        brush_mask = np.ones((y2 - y1, x2 - x1), dtype=bool)
        
    if brush_mask.size == 0:
        return mask
        
    if operation == 'draw':
        mask[y1:y2, x1:x2] = np.where(brush_mask, value, mask[y1:y2, x1:x2])
    elif operation == 'erase':
        mask[y1:y2, x1:x2] = np.where(brush_mask, 0, mask[y1:y2, x1:x2])
    elif operation == 'threshold':
        # Draw where slice value is within threshold
        threshold_mask = (slice_data[y1:y2, x1:x2] > 0)
        combined = brush_mask & threshold_mask
        mask[y1:y2, x1:x2] = np.where(combined, value, mask[y1:y2, x1:x2])
        
    return mask


def interpolate_mask_slices(slice1: np.ndarray, slice2: np.ndarray,
                            num_slices: int) -> list:
    """
    Interpolate between two mask slices.
    
    Args:
        slice1: First mask slice
        slice2: Second mask slice
        num_slices: Number of intermediate slices to generate
        
    Returns:
        List of interpolated mask slices
    """
    if num_slices < 1:
        return []
        
    interpolated = []
    for i in range(1, num_slices + 1):
        alpha = i / (num_slices + 1)
        interp_slice = (slice1.astype(float) * (1 - alpha) + 
                       slice2.astype(float) * alpha)
        interpolated.append((interp_slice > 127).astype(np.uint8))
        
    return interpolated


def get_bounding_box(mask: np.ndarray) -> Optional[Tuple[int, int, int, int, int, int]]:
    """
    Get the bounding box of non-zero elements in a mask.
    
    Args:
        mask: Binary mask
        
    Returns:
        Tuple of (x_min, x_max, y_min, y_max, z_min, z_max) or None
    """
    nonzero = np.nonzero(mask)
    if len(nonzero[0]) == 0:
        return None
        
    return (nonzero[2].min(), nonzero[2].max(),
            nonzero[1].min(), nonzero[1].max(),
            nonzero[0].min(), nonzero[0].max())


def get_largest_component(mask: np.ndarray) -> np.ndarray:
    """
    Extract the largest connected component from a binary mask.
    
    Args:
        mask: Binary mask
        
    Returns:
        Mask with only the largest component
    """
    from scipy import ndimage
    
    labeled, num_features = ndimage.label(mask)
    if num_features == 0:
        return mask
        
    component_sizes = ndimage.sum(mask, labeled, range(1, num_features + 1))
    largest_label = 1 + np.argmax(component_sizes)
    
    return (labeled == largest_label).astype(np.uint8)


def smooth_mask_boundary(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    """
    Smooth the boundary of a binary mask.
    
    Args:
        mask: Binary mask
        iterations: Number of smoothing iterations
        
    Returns:
        Smoothed mask
    """
    from scipy import ndimage
    from skimage import morphology
    
    # Opening to remove noise
    opened = morphology.binary_opening(mask.astype(bool), iterations=iterations)
    
    # Closing to fill holes
    closed = morphology.binary_closing(opened, iterations=iterations)
    
    return closed.astype(np.uint8)


def calculate_surface_area(vertices: np.ndarray, faces: np.ndarray) -> float:
    """
    Calculate the surface area of a mesh.
    
    Args:
        vertices: Vertex coordinates (N, 3)
        faces: Face indices (M, 3)
        
    Returns:
        Surface area in mm²
    """
    total_area = 0.0
    
    for face in faces:
        v0, v1, v2 = vertices[face]
        
        # Calculate edge vectors
        e1 = v1 - v0
        e2 = v2 - v0
        
        # Calculate triangle area using cross product
        cross = np.cross(e1, e2)
        area = np.linalg.norm(cross) / 2
        total_area += area
        
    return total_area


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB to hex color string."""
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
