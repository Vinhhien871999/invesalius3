# --------------------------------------------------------------------------
# Statistics of one ROI: voxel count, physical volume, HU statistics,
# centroid, bounding box, connected components, axial slice coverage, and
# the HU histogram of the voxels inside the ROI.
#
# Conventions (the plugin's coordinate contract, core/coordinates.py):
#   volume and mask are (z, y, x); spacing is (sx, sy, sz) in mm; world
#   coordinates are (x, y, z) mm with origin 0 (the 2D views' frame).
#   Volume = foreground voxels * sx * sy * sz, in float64.
#   HU standard deviation is the population value (ddof=0).
#   Connectivity is 6 (faces), the same as region growing and E3.
# --------------------------------------------------------------------------
from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple

import numpy as np
from scipy import ndimage

from ..coordinates import voxel_zyx_to_world_xyz


@dataclass(frozen=True)
class HUStatistics:
    minimum: float
    maximum: float
    mean: float
    median: float
    std: float


@dataclass(frozen=True)
class ROIStatistics:
    name: str
    voxel_count: int
    volume_mm3: float
    volume_ml: float
    hu: Optional[HUStatistics]  # None: empty ROI or no HU semantics
    centroid_voxel_zyx: Optional[Tuple[float, float, float]]
    centroid_world_xyz: Optional[Tuple[float, float, float]]
    bbox_voxel_min_zyx: Optional[Tuple[int, int, int]]
    bbox_voxel_max_zyx: Optional[Tuple[int, int, int]]  # inclusive
    bbox_size_mm_xyz: Optional[Tuple[float, float, float]]
    component_count: int
    largest_component_voxels: int
    first_axial_slice: Optional[int]
    last_axial_slice: Optional[int]
    occupied_axial_slices: int
    spacing_xyz: Tuple[float, float, float] = field(default=(1.0, 1.0, 1.0))


def voxel_volume_mm3(spacing_xyz: Sequence[float]) -> float:
    sx, sy, sz = (float(s) for s in spacing_xyz)
    if min(sx, sy, sz) <= 0:
        raise ValueError(f"spacing must be positive, got {tuple(spacing_xyz)}")
    return sx * sy * sz


def _bool_mask(mask, shape=None) -> np.ndarray:
    m = np.asarray(mask) != 0
    if shape is not None and m.shape != tuple(shape):
        raise ValueError(f"mask shape {m.shape} does not match volume shape {tuple(shape)}")
    return m


def hu_statistics(values: np.ndarray) -> Optional[HUStatistics]:
    """Statistics of a 1-D array of HU values (None when empty)."""
    v = np.asarray(values, dtype=np.float64).ravel()
    if v.size == 0:
        return None
    return HUStatistics(minimum=float(v.min()), maximum=float(v.max()), mean=float(v.mean()),
                        median=float(np.median(v)), std=float(v.std()))


def compute_roi_statistics(volume, mask, spacing_xyz, name: str = "", hu_available: bool = True) -> ROIStatistics:
    """`volume` may be None when HU values are not available (non-CT
    modality): every HU field is then None, the geometry is still
    computed. Neither input is modified."""
    m = _bool_mask(mask, None if volume is None else np.shape(volume))
    voxel_mm3 = voxel_volume_mm3(spacing_xyz)
    count = int(np.count_nonzero(m))
    volume_mm3 = float(count) * voxel_mm3
    spacing = tuple(float(s) for s in spacing_xyz)
    if count == 0:
        return ROIStatistics(name=name, voxel_count=0, volume_mm3=0.0, volume_ml=0.0, hu=None,
                             centroid_voxel_zyx=None, centroid_world_xyz=None, bbox_voxel_min_zyx=None,
                             bbox_voxel_max_zyx=None, bbox_size_mm_xyz=None, component_count=0,
                             largest_component_voxels=0, first_axial_slice=None, last_axial_slice=None,
                             occupied_axial_slices=0, spacing_xyz=spacing)

    idx = np.nonzero(m)
    centroid = tuple(float(np.mean(a, dtype=np.float64)) for a in idx)
    world = voxel_zyx_to_world_xyz(centroid, spacing)
    lo = tuple(int(a.min()) for a in idx)
    hi = tuple(int(a.max()) for a in idx)
    size_xyz = ((hi[2] - lo[2] + 1) * spacing[0], (hi[1] - lo[1] + 1) * spacing[1], (hi[0] - lo[0] + 1) * spacing[2])
    labels, n = ndimage.label(m)
    largest = int(np.bincount(labels.ravel())[1:].max()) if n else 0
    occupied = np.flatnonzero(m.any(axis=(1, 2)))
    hu = hu_statistics(np.asarray(volume)[m]) if (hu_available and volume is not None) else None
    return ROIStatistics(
        name=name, voxel_count=count, volume_mm3=volume_mm3, volume_ml=volume_mm3 / 1000.0, hu=hu,
        centroid_voxel_zyx=centroid, centroid_world_xyz=tuple(float(c) for c in world),
        bbox_voxel_min_zyx=lo, bbox_voxel_max_zyx=hi, bbox_size_mm_xyz=tuple(float(s) for s in size_xyz),
        component_count=int(n), largest_component_voxels=largest,
        first_axial_slice=int(occupied[0]), last_axial_slice=int(occupied[-1]),
        occupied_axial_slices=int(occupied.size), spacing_xyz=spacing,
    )


@dataclass(frozen=True)
class Histogram:
    edges: Tuple[float, ...]  # len(counts) + 1, bins [edges[i], edges[i+1]), the last one closed
    counts: Tuple[int, ...]
    below: int  # ROI voxels under the range
    above: int  # ROI voxels over the range
    bin_width: float


def auto_histogram_range(values) -> Tuple[float, float]:
    """The ROI's own HU range: [floor(min), floor(max) + 1)."""
    v = np.asarray(values)
    if v.size == 0:
        return (0.0, 1.0)
    return (float(np.floor(v.min())), float(np.floor(v.max()) + 1.0))


def roi_histogram(volume, mask, hu_range: Optional[Tuple[float, float]] = None, bins: int = 100) -> Histogram:
    """HU histogram of the voxels INSIDE the ROI only. Default range = the
    ROI's own HU range; `hu_range` overrides it. counts + below + above =
    ROI voxel count."""
    m = _bool_mask(mask, np.shape(volume))
    values = np.asarray(volume)[m].astype(np.float64)
    lo, hi = auto_histogram_range(values) if hu_range is None else (float(hu_range[0]), float(hu_range[1]))
    if not hi > lo:
        raise ValueError(f"histogram range must be increasing, got {(lo, hi)}")
    if bins < 1:
        raise ValueError("bins must be >= 1")
    counts, edges = np.histogram(values, bins=int(bins), range=(lo, hi))
    below = int(np.count_nonzero(values < lo))
    above = int(np.count_nonzero(values > hi))
    return Histogram(edges=tuple(float(e) for e in edges), counts=tuple(int(c) for c in counts),
                     below=below, above=above, bin_width=(hi - lo) / int(bins))
