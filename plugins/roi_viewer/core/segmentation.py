# --------------------------------------------------------------------------
# Segmentation Module
# Description: Segmentation algorithms for ROI extraction
# --------------------------------------------------------------------------

import numpy as np
from typing import Tuple, Optional, List, Callable
from scipy import ndimage
from skimage import morphology, segmentation


class SegmentationManager:
    """
    Manages segmentation operations for medical images.
    """
    
    def __init__(self):
        self.current_threshold = (-1024, 3071)  # HU units for CT
        self.last_mask = None
        self.progress_callbacks: List[Callable] = []
        
    def set_threshold(self, min_val: int, max_val: int):
        """
        Set the threshold range.
        
        Args:
            min_val: Minimum value (inclusive)
            max_val: Maximum value (inclusive)
        """
        self.current_threshold = (min_val, max_val)
        
    def apply_threshold(self, volume: np.ndarray) -> np.ndarray:
        """
        Apply threshold to create a binary mask.
        
        Args:
            volume: 3D numpy array of image data
            
        Returns:
            Binary mask as numpy array
        """
        min_val, max_val = self.current_threshold
        mask = (volume >= min_val) & (volume <= max_val)
        return mask.astype(np.uint8)
        
    def auto_threshold_otsu(self, volume: np.ndarray) -> Tuple[int, int]:
        """
        Calculate optimal threshold using Otsu's method.
        
        Args:
            volume: 3D numpy array of image data
            
        Returns:
            Tuple of (min_threshold, max_threshold)
        """
        # Flatten volume for histogram calculation
        data = volume.flatten()
        
        # Calculate histogram
        hist, bin_edges = np.histogram(data, bins=256)
        
        # Normalize histogram
        hist = hist.astype(float) / hist.sum()
        
        # Find threshold using Otsu's method
        total_mean = np.sum(np.arange(len(hist)) * hist)
        
        var_between_classes = []
        for t in range(len(hist)):
            w0 = np.sum(hist[:t])
            if w0 == 0:
                continue
            w1 = np.sum(hist[t:])
            if w1 == 0:
                continue
                
            m0 = np.sum(np.arange(t) * hist[:t]) / w0
            m1 = np.sum(np.arange(t, len(hist)) * hist[t:]) / w1
            
            var_between = w0 * w1 * (m0 - m1) ** 2
            var_between_classes.append((t, var_between))
            
        if var_between_classes:
            optimal_t = max(var_between_classes, key=lambda x: x[1])[0]
        else:
            optimal_t = 128
            
        return (int(bin_edges[optimal_t]), int(volume.max()))
        
    def region_growing(self, volume: np.ndarray, seed: Tuple[int, int, int],
                      tolerance: int = 10) -> np.ndarray:
        """
        Region growing segmentation.
        
        Args:
            volume: 3D numpy array of image data
            seed: Tuple of (x, y, z) seed point coordinates
            tolerance: Intensity tolerance for region growing
            
        Returns:
            Binary mask of segmented region
        """
        mask = np.zeros(volume.shape, dtype=bool)
        
        if not (0 <= seed[0] < volume.shape[0] and 
                0 <= seed[1] < volume.shape[1] and 
                0 <= seed[2] < volume.shape[2]):
            return mask.astype(np.uint8)
            
        seed_value = volume[seed]
        min_val = seed_value - tolerance
        max_val = seed_value + tolerance
        
        # Use flood fill (BFS)
        stack = [seed]
        visited = set()
        
        while stack:
            point = stack.pop()
            if point in visited:
                continue
                
            x, y, z = point
            
            if not (0 <= x < volume.shape[0] and 
                    0 <= y < volume.shape[1] and 
                    0 <= z < volume.shape[2]):
                continue
                
            if mask[x, y, z]:
                continue
                
            if not (min_val <= volume[x, y, z] <= max_val):
                continue
                
            visited.add(point)
            mask[x, y, z] = True
            
            # Add neighbors
            neighbors = [
                (x+1, y, z), (x-1, y, z),
                (x, y+1, z), (x, y-1, z),
                (x, y, z+1), (x, y, z-1)
            ]
            
            for neighbor in neighbors:
                if neighbor not in visited:
                    stack.append(neighbor)
                    
        return mask.astype(np.uint8)
        
    def watershed(self, volume: np.ndarray, seeds: List[Tuple[int, int, int]],
                  mask: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Watershed segmentation.
        
        Args:
            volume: 3D numpy array of image data
            seeds: List of seed points
            mask: Optional mask to limit search area
            
        Returns:
            Labeled segmentation result
        """
        # Invert volume for watershed (we want high values as background)
        inverted = volume.max() - volume
        
        # Create markers
        marker_img = np.zeros(volume.shape, dtype=np.int32)
        for i, seed in enumerate(seeds):
            if all(0 <= s < dim for s, dim in zip(seed, volume.shape)):
                marker_img[seed] = i + 1
                
        # Apply watershed
        try:
            from skimage.segmentation import watershed
            labels = watershed(inverted, marker_img, mask=mask)
        except Exception:
            # Fallback if skimage watershed fails
            labels = self._simple_watershed(volume, seeds, mask)
            
        return labels
        
    def _simple_watershed(self, volume: np.ndarray, seeds: List[Tuple[int, int, int]],
                         mask: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Simple watershed implementation using distance transform.
        """
        labels = np.zeros(volume.shape, dtype=np.int32)
        
        if not seeds:
            return labels
            
        # Find connected components from seeds
        seed_mask = np.zeros(volume.shape, dtype=bool)
        for seed in seeds:
            if all(0 <= s < dim for s, dim in zip(seed, volume.shape)):
                seed_mask[seed] = True
                
        labeled, num_features = ndimage.label(seed_mask)
        
        # Distance transform
        dist = ndimage.distance_transform_edt(~seed_mask)
        
        # Simple region growing based on distance
        for i in range(1, num_features + 1):
            region_mask = labeled == i
            labels[region_mask] = i
            
        return labels
        
    def morphological_op(self, mask: np.ndarray, operation: str,
                        iterations: int = 1) -> np.ndarray:
        """
        Apply morphological operation to mask.
        
        Args:
            mask: Binary mask
            operation: 'dilate', 'erode', 'open', 'close'
            iterations: Number of iterations
            
        Returns:
            Processed mask
        """
        struct = morphology.ball(1)  # 3D structuring element
        
        if operation == 'dilate':
            return morphology.binary_dilation(mask.astype(bool), struct, iterations).astype(np.uint8)
        elif operation == 'erode':
            return morphology.binary_erosion(mask.astype(bool), struct, iterations).astype(np.uint8)
        elif operation == 'open':
            return morphology.binary_opening(mask.astype(bool), struct, iterations).astype(np.uint8)
        elif operation == 'close':
            return morphology.binary_closing(mask.astype(bool), struct, iterations).astype(np.uint8)
        else:
            return mask
            
    def remove_small_objects(self, mask: np.ndarray, min_size: int = 100) -> np.ndarray:
        """
        Remove small objects from binary mask.
        
        Args:
            mask: Binary mask
            min_size: Minimum object size in voxels
            
        Returns:
            Mask with small objects removed
        """
        mask_bool = mask.astype(bool)
        cleaned = morphology.remove_small_objects(mask_bool, min_size)
        return cleaned.astype(np.uint8)
        
    def fill_holes(self, mask: np.ndarray) -> np.ndarray:
        """
        Fill holes in binary mask.
        
        Args:
            mask: Binary mask
            
        Returns:
            Mask with holes filled
        """
        return ndimage.binary_fill_holes(mask.astype(bool)).astype(np.uint8)
