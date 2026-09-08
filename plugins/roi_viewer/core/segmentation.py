# --------------------------------------------------------------------------
# Segmentation Module
# Description: Segmentation algorithms for ROI extraction
# --------------------------------------------------------------------------

import math
import numpy as np
from typing import Tuple, Optional, List, Callable, Dict
from scipy import ndimage


class SegmentationManager:
    """
    Manages segmentation operations for medical images.
    """

    # Region growing safety limit (Round-2 audit, section C): a seed
    # click with a generous tolerance on a wide-HU-range CT volume can
    # grow to cover most of the volume, which stops being a meaningful
    # "region of interest". This is a configurable class attribute
    # (not a magic number buried in the UI layer) so the policy is
    # visible and testable independently of any wx code - see
    # region_stats() below and segmentation_panel.py's
    # _on_region_grown(), which warns/confirms before committing a
    # result whose fraction exceeds this.
    DEFAULT_MAX_REGION_FRACTION = 0.20

    def __init__(self):
        self.current_threshold = (-1024, 3071)  # HU units for CT
        self.last_mask = None
        self.progress_callbacks: List[Callable] = []
        self.max_region_fraction = self.DEFAULT_MAX_REGION_FRACTION
        
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
        
    @staticmethod
    def validate_seed(seed: Tuple[int, int, int], volume_shape: Tuple[int, int, int]) -> Optional[str]:
        """
        Validate a region-growing seed before spending any time growing
        from it. Returns None if valid, or a human-readable reason
        string if not (so the UI layer can show a clear message instead
        of a silent empty result).
        """
        if volume_shape is None or len(volume_shape) != 3 or any(d <= 0 for d in volume_shape):
            return "No volume loaded"
        if seed is None or len(seed) != 3:
            return "Invalid seed"
        if not all(math.isfinite(s) for s in seed):
            return "Seed coordinates are not finite"
        if not (0 <= seed[0] < volume_shape[0] and
                0 <= seed[1] < volume_shape[1] and
                0 <= seed[2] < volume_shape[2]):
            return f"Seed {seed} is outside the volume bounds {volume_shape}"
        return None

    def region_growing(self, volume: np.ndarray, seed: Tuple[int, int, int],
                      tolerance: int = 10) -> np.ndarray:
        """
        Region growing segmentation: the connected component (6-
        connectivity) reachable from `seed` staying within
        [seed_value - tolerance, seed_value + tolerance].

        NOTE: this used to be a hand-rolled Python BFS (an explicit
        stack + a `set()` of visited (x,y,z) tuples). It was
        functionally correct but, on a real CT volume (~512x512x100+
        voxels), could take well over a minute for a sizeable region -
        Python-level per-voxel loops don't scale to tens of millions of
        voxels. Verified end-to-end (test_regiongrowing_surfaceupdate.py)
        that a real seed pick did eventually produce a correct real
        mask, just far too slowly to be usable interactively.

        Replaced with an equivalent but vectorized approach using
        scipy.ndimage (already a project dependency, no new one added):
        threshold the whole volume to the tolerance band, label its
        connected components (ndimage.label's default 3D structure is
        exactly 6-connected, matching the original BFS's neighbor set),
        and keep only the component containing the seed. Same
        algorithm and result, but runs in native/vectorized code -
        typically well under a second instead of tens of seconds.

        Raises:
            ValueError: if tolerance is negative (Round-2 audit,
                section C - a negative tolerance has no valid meaning
                for an inclusive [seed-tol, seed+tol] band, so this is
                rejected explicitly rather than silently producing an
                empty/nonsensical result).
        """
        if tolerance < 0:
            raise ValueError(f"tolerance must be >= 0, got {tolerance}")

        if self.validate_seed(seed, volume.shape) is not None:
            return np.zeros(volume.shape, dtype=np.uint8)

        seed_value = volume[seed]
        min_val = seed_value - tolerance
        max_val = seed_value + tolerance

        thresholded = (volume >= min_val) & (volume <= max_val)
        labeled, _ = ndimage.label(thresholded)  # default structure = 6-connectivity in 3D

        seed_label = labeled[seed]
        if seed_label == 0:
            return np.zeros(volume.shape, dtype=np.uint8)

        return (labeled == seed_label).astype(np.uint8)

    def region_stats(self, result_mask: np.ndarray, spacing: Optional[Tuple[float, float, float]] = None) -> Dict:
        """
        Summarize a region-growing result for display/safety checks:
        voxel count, fraction of the total volume, whether it exceeds
        `self.max_region_fraction`, and physical volume in mm^3 if
        spacing is known. Kept separate from region_growing() itself so
        the pure algorithm and the UI-facing safety policy can be
        tested independently.
        """
        voxel_count = int(result_mask.sum())
        total_voxels = int(result_mask.size)
        fraction = (voxel_count / total_voxels) if total_voxels else 0.0
        stats = {
            "voxel_count": voxel_count,
            "total_voxels": total_voxels,
            "fraction": fraction,
            "exceeds_limit": fraction > self.max_region_fraction,
        }
        if spacing is not None and len(spacing) == 3:
            voxel_volume_mm3 = spacing[0] * spacing[1] * spacing[2]
            stats["volume_mm3"] = voxel_count * voxel_volume_mm3
        return stats
