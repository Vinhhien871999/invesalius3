# --------------------------------------------------------------------------
# Quantitative Evaluation Module (Phase 12, CT3D_P12_QUANTITATIVE_VALIDATION)
# Description: Segmentation-accuracy metrics (Dice, Jaccard/IoU, Hausdorff
#              distance in physical units) for comparing a real ROI mask
#              against a ground-truth mask. Pure numpy/scipy, no wx/VTK/
#              InVesalius dependency - importable directly from tests and,
#              if ever wired into the GUI, from a panel too, without
#              pulling any GUI code into research-only logic (per the
#              phase spec's explicit instruction not to bury metrics deep
#              inside a GUI panel).
#
# Axis/spacing convention (documented explicitly, not left ambiguous - see
# the phase spec's own warning about this): masks here are expected in
# the SAME array-axis order as invesalius.data.mask.Mask.matrix / the
# real image matrix - axis 0 = AXIAL slice stack, axis 1 = CORONAL,
# axis 2 = SAGITAL (matches invesalius.data.slice_.Slice.spacing's own
# index alignment - see plugins/roi_viewer/core/sync_2d3d.py's
# world_to_voxel()/voxel_to_world() docstrings for the same convention
# used elsewhere in this plugin). Spacing arguments are therefore named
# `spacing_zyx` (NOT a generic/ambiguous `spacing`) meaning
# (axial_spacing, coronal_spacing, sagital_spacing) - i.e. exactly
# `Slice().spacing` / `ProjectInterface().get_spacing()`, index-aligned
# with the mask array's own axes, not a generic image (x, y, z) triple.
# --------------------------------------------------------------------------
from typing import Tuple

import numpy as np
from scipy import ndimage


def _validate_masks(mask_a: np.ndarray, mask_b: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Cast both masks to boolean and validate they can be meaningfully
    compared. Raises ValueError (never silently resamples/reshapes) on
    a shape mismatch - resampling is a separate research problem, not
    something this module does implicitly (per the spec's explicit
    instruction).
    """
    a = np.asarray(mask_a)
    b = np.asarray(mask_b)
    if a.shape != b.shape:
        raise ValueError(f"mask_a and mask_b must have the same shape, got {a.shape} vs {b.shape}")
    if a.ndim < 1:
        raise ValueError(f"masks must have at least 1 dimension, got ndim={a.ndim}")
    return a.astype(bool), b.astype(bool)


def _validate_spacing(spacing_zyx: Tuple[float, ...], ndim: int) -> Tuple[float, ...]:
    """
    Validate a spacing tuple for physical-unit distance metrics: must
    have one positive, finite value per mask axis. NOT a generic (x,y,z)
    triple - see this module's header docstring for the real axis
    convention (index-aligned with the mask array's own axes).
    """
    if len(spacing_zyx) != ndim:
        raise ValueError(
            f"spacing_zyx must have {ndim} values (one per mask axis, index-aligned "
            f"with the mask array - see this module's header docstring), got {len(spacing_zyx)}"
        )
    for s in spacing_zyx:
        if not np.isfinite(s):
            raise ValueError(f"spacing_zyx values must be finite, got {spacing_zyx}")
        if s <= 0:
            raise ValueError(f"spacing_zyx values must be positive, got {spacing_zyx}")
    return tuple(float(s) for s in spacing_zyx)


def dice_coefficient(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """
    Dice similarity coefficient: 2|A∩B| / (|A| + |B|).

    Edge cases (documented, not left to fall out of the formula
    accidentally):
      - both masks empty (no foreground voxels at all): 1.0 (identical -
        two empty sets are considered a perfect match, the conventional
        choice for this metric).
      - exactly one mask empty: 0.0 (no possible overlap).
    """
    a, b = _validate_masks(mask_a, mask_b)
    a_count = int(a.sum())
    b_count = int(b.sum())
    if a_count == 0 and b_count == 0:
        return 1.0
    if a_count == 0 or b_count == 0:
        return 0.0
    intersection = int(np.logical_and(a, b).sum())
    return 2.0 * intersection / (a_count + b_count)


def jaccard_index(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """
    Jaccard index (Intersection over Union): |A∩B| / |A∪B|.

    Edge cases, matching dice_coefficient()'s convention for consistency
    (see the Dice/Jaccard relationship checked in
    tests/ct3d/test_evaluation_metrics.py):
      - both masks empty: 1.0.
      - exactly one mask empty: 0.0.
    """
    a, b = _validate_masks(mask_a, mask_b)
    a_count = int(a.sum())
    b_count = int(b.sum())
    if a_count == 0 and b_count == 0:
        return 1.0
    if a_count == 0 or b_count == 0:
        return 0.0
    intersection = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return intersection / union


def hausdorff_distance(
    mask_a: np.ndarray, mask_b: np.ndarray, spacing_zyx: Tuple[float, ...]
) -> float:
    """
    Hausdorff distance (maximum of the two directed Hausdorff distances)
    between the surfaces of two binary masks, in the SAME physical units
    as `spacing_zyx` (mm, if spacing_zyx is in mm - the real InVesalius
    convention).

    Uses `scipy.ndimage.distance_transform_edt(..., sampling=spacing_zyx)`
    so ANISOTROPIC spacing is honored correctly (never voxel-index
    distance - see this module's header docstring for why that would be
    wrong whenever spacing isn't isotropic). For each mask, computes the
    distance transform of its background (distance to the nearest
    foreground voxel) sampled at the other mask's foreground voxels,
    matching the standard "distance from set A to set B" definition via
    an exact Euclidean distance transform rather than a surface-mesh
    extraction (simpler, still exact for the voxel-boundary case, no
    extra dependency needed since SciPy is already a project dependency).

    Edge cases (documented, not left ambiguous - see the phase spec's
    explicit requirement):
      - both masks empty: 0.0 (identical - no discrepancy to measure).
      - exactly one mask empty: raises ValueError. Hausdorff distance is
        mathematically undefined between an empty set and a non-empty
        set (there is no nearest point in the empty set) - returning a
        silent `inf`/`nan` here risks a caller comparing/aggregating it
        without noticing, so this fails loudly and explicitly instead
        (matches this plugin's established convention elsewhere, e.g.
        core/segmentation.py's region_growing() raising ValueError for
        a negative tolerance rather than returning a nonsensical result).
    """
    a, b = _validate_masks(mask_a, mask_b)
    spacing_zyx = _validate_spacing(spacing_zyx, a.ndim)

    a_count = int(a.sum())
    b_count = int(b.sum())
    if a_count == 0 and b_count == 0:
        return 0.0
    if a_count == 0 or b_count == 0:
        raise ValueError(
            "hausdorff_distance is undefined when exactly one mask is empty "
            f"(mask_a has {a_count} foreground voxels, mask_b has {b_count})"
        )

    # Distance transform of "not A" gives, at every voxel, the physical
    # distance to the nearest A voxel. Sampling B's foreground voxels
    # into that gives directed distance B->A; symmetric for A->B.
    dist_to_a = ndimage.distance_transform_edt(~a, sampling=spacing_zyx)
    dist_to_b = ndimage.distance_transform_edt(~b, sampling=spacing_zyx)

    d_b_to_a = dist_to_a[b].max()
    d_a_to_b = dist_to_b[a].max()

    return float(max(d_b_to_a, d_a_to_b))


def hausdorff_distance_95(
    mask_a: np.ndarray, mask_b: np.ndarray, spacing_zyx: Tuple[float, ...]
) -> float:
    """
    HD95: the 95th percentile of the combined directed-distance
    distributions, in the same physical units as hausdorff_distance().

    THIS IS A DIFFERENT METRIC FROM hausdorff_distance() (the maximum) -
    HD95 is more robust to a single outlier voxel but is NOT a drop-in
    replacement for the true Hausdorff maximum. Report both when both
    are relevant (see docs/CT3D_P12_QUANTITATIVE_VALIDATION_REPORT.md
    Section 13) - never substitute one for the other silently.

    Same edge-case behavior as hausdorff_distance() (both empty -> 0.0,
    exactly one empty -> ValueError).
    """
    a, b = _validate_masks(mask_a, mask_b)
    spacing_zyx = _validate_spacing(spacing_zyx, a.ndim)

    a_count = int(a.sum())
    b_count = int(b.sum())
    if a_count == 0 and b_count == 0:
        return 0.0
    if a_count == 0 or b_count == 0:
        raise ValueError(
            "hausdorff_distance_95 is undefined when exactly one mask is empty "
            f"(mask_a has {a_count} foreground voxels, mask_b has {b_count})"
        )

    dist_to_a = ndimage.distance_transform_edt(~a, sampling=spacing_zyx)
    dist_to_b = ndimage.distance_transform_edt(~b, sampling=spacing_zyx)

    d_b_to_a = dist_to_a[b]
    d_a_to_b = dist_to_b[a]
    combined = np.concatenate([d_b_to_a.ravel(), d_a_to_b.ravel()])
    return float(np.percentile(combined, 95))
