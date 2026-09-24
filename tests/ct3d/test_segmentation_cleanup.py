# --------------------------------------------------------------------------
# Persistent tests for E3 (Advanced Segmentation Enhancement Track):
# core/segmentation_cleanup.py - pure numpy/scipy logic, no wx, no
# invesalius.* import. Marked unit. See
# docs/CT3D_ADVANCED_E3_CLEANUP_REPORT.md for the design/audit writeup
# behind the algorithm/connectivity/tie-break choices this file locks in.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from plugins.roi_viewer.core.segmentation_cleanup import (
    DEFAULT_CONNECTIVITY,
    MAX_SMOOTH_ITERATIONS,
    cleanup_stats,
    fill_holes,
    keep_largest_component,
    remove_small_components,
    smooth_binary_mask,
)

pytestmark = pytest.mark.unit


def _cube(shape=(10, 10, 10), lo=2, hi=8, dtype=np.uint8, value=255):
    m = np.zeros(shape, dtype=dtype)
    m[lo:hi, lo:hi, lo:hi] = value
    return m


# ------------------------------------------------------------------
# keep_largest_component
# ------------------------------------------------------------------
def test_keep_largest_empty():
    empty = np.zeros((5, 5, 5), dtype=np.uint8)
    result, info = keep_largest_component(empty)
    assert result.shape == empty.shape
    assert result.sum() == 0
    assert info == {"component_count_before": 0, "removed_component_count": 0, "removed_voxels": 0}


def test_keep_largest_one_component():
    m = _cube()
    result, info = keep_largest_component(m)
    assert np.array_equal(result > 0, m > 0)  # single component - nothing removed
    assert info["component_count_before"] == 1
    assert info["removed_component_count"] == 0
    assert info["removed_voxels"] == 0


def test_keep_largest_removes_smaller():
    m = np.zeros((10, 10, 10), dtype=np.uint8)
    m[1:4, 1:4, 1:4] = 255  # small component, 27 voxels
    m[6:9, 6:9, 6:9] = 255  # equal-size component - use a bigger one instead
    m[6:9, 6:9, 6:9] = 0
    m[5:9, 5:9, 5:9] = 255  # larger component, 64 voxels
    result, info = keep_largest_component(m)
    assert result.sum() // 255 == 64
    assert not result[1:4, 1:4, 1:4].any()  # smaller component removed
    assert result[5:9, 5:9, 5:9].all()  # larger component kept
    assert info["component_count_before"] == 2
    assert info["removed_component_count"] == 1
    assert info["removed_voxels"] == 27


def test_keep_largest_equal_size_deterministic():
    m = np.zeros((10, 10, 10), dtype=np.uint8)
    m[1:3, 1:3, 1:3] = 255  # component A, 8 voxels, scanned first (lower z)
    m[6:8, 6:8, 6:8] = 255  # component B, 8 voxels, scanned second
    result1, info1 = keep_largest_component(m)
    result2, info2 = keep_largest_component(m)
    assert np.array_equal(result1, result2)  # deterministic across repeated calls
    assert info1 == info2
    # Documented tie-break: smallest label id (scan order) wins - the
    # first-scanned component (lower z) is kept.
    assert result1[1:3, 1:3, 1:3].all()
    assert not result1[6:8, 6:8, 6:8].any()


# ------------------------------------------------------------------
# remove_small_components
# ------------------------------------------------------------------
def test_remove_small_empty():
    empty = np.zeros((5, 5, 5), dtype=np.uint8)
    result, info = remove_small_components(empty, min_voxels=10)
    assert result.sum() == 0
    assert info["component_count_before"] == 0


def test_remove_small_threshold_boundary():
    """Documented comparison: `size < min_voxels` is removed; a
    component of size EXACTLY min_voxels is KEPT."""
    m = np.zeros((10, 10, 10), dtype=np.uint8)
    m[0, 0, 0] = 255  # size 1
    m[3:3 + 2, 3, 3] = 255  # size 2
    m[6:6 + 3, 6, 6] = 255  # size 3

    result, info = remove_small_components(m, min_voxels=2)
    assert result[0, 0, 0] == 0  # size 1 < 2 -> removed
    assert result[3, 3, 3] != 0 and result[4, 3, 3] != 0  # size 2 == 2 -> kept (boundary, not removed)
    assert result[6, 6, 6] != 0  # size 3 >= 2 -> kept
    assert info["removed_component_count"] == 1
    assert info["removed_voxels"] == 1


def test_remove_small_multiple_components():
    m = np.zeros((12, 12, 12), dtype=np.uint8)
    m[0, 0, 0] = 255  # size 1
    m[2, 2, 2] = 255  # size 1
    m[5:9, 5:9, 5:9] = 255  # size 64
    result, info = remove_small_components(m, min_voxels=5)
    assert info["component_count_before"] == 3
    assert info["removed_component_count"] == 2
    assert info["removed_voxels"] == 2
    assert result.sum() // 255 == 64


def test_remove_small_rejects_invalid_min_voxels():
    m = _cube()
    with pytest.raises(ValueError):
        remove_small_components(m, min_voxels=0)
    with pytest.raises(ValueError):
        remove_small_components(m, min_voxels=-5)


# ------------------------------------------------------------------
# fill_holes
# ------------------------------------------------------------------
def test_fill_holes_enclosed_hole():
    m = _cube(shape=(12, 12, 12), lo=2, hi=10).astype(bool)
    m[5, 5, 5] = False  # carve a fully-enclosed 1-voxel cavity
    assert not m[5, 5, 5]
    result, info = fill_holes(m)
    assert result[5, 5, 5] != 0  # cavity filled
    assert info["voxels_added"] == 1


def test_fill_holes_external_background_unchanged():
    """Real, verified behavior of scipy.ndimage.binary_fill_holes():
    background touching the array border is never filled - not just
    assumed from the docstring."""
    m = np.zeros((10, 10, 10), dtype=np.uint8)
    m[3:7, 3:7, 3:7] = 255  # solid cube, no cavity, background reaches the border on all sides
    result, info = fill_holes(m)
    assert np.array_equal(result > 0, m > 0)  # nothing changed
    assert info["voxels_added"] == 0


def test_fill_holes_solid_object_no_change():
    m = _cube()
    result, info = fill_holes(m)
    assert np.array_equal(result > 0, m > 0)
    assert info["voxels_added"] == 0


# ------------------------------------------------------------------
# smooth_binary_mask
# ------------------------------------------------------------------
def test_smooth_shape_preserved():
    m = _cube(shape=(10, 10, 10))
    result, info = smooth_binary_mask(m, iterations=1)
    assert result.shape == m.shape
    assert result.dtype == np.uint8


def test_smooth_deterministic():
    m = _cube(shape=(14, 14, 14), lo=3, hi=11)
    result1, info1 = smooth_binary_mask(m, iterations=1)
    result2, info2 = smooth_binary_mask(m, iterations=1)
    assert np.array_equal(result1, result2)
    assert info1 == info2


def test_smooth_iterations_validated():
    m = _cube()
    with pytest.raises(ValueError):
        smooth_binary_mask(m, iterations=0)
    with pytest.raises(ValueError):
        smooth_binary_mask(m, iterations=MAX_SMOOTH_ITERATIONS + 1)
    smooth_binary_mask(m, iterations=1)  # must not raise
    smooth_binary_mask(m, iterations=MAX_SMOOTH_ITERATIONS)  # must not raise


def test_smooth_bounded_volume_drift_on_convex_shape():
    """Real measured evidence backing the algorithm choice (see
    core/segmentation_cleanup.py's module-level comment and
    docs/CT3D_ADVANCED_E3_CLEANUP_REPORT.md): closing+opening keeps
    volume drift small on a convex (sphere-like) phantom."""
    shape = (20, 20, 20)
    zz, yy, xx = np.ogrid[:20, :20, :20]
    c, r = 10, 7
    sphere = ((zz - c) ** 2 + (yy - c) ** 2 + (xx - c) ** 2) <= r * r
    m = (sphere.astype(np.uint8)) * 255

    result, info = smooth_binary_mask(m, iterations=1)
    before = int((m > 0).sum())
    after = int((result > 0).sum())
    drift_pct = abs(after - before) / before * 100.0
    assert drift_pct < 5.0  # real, measured bound from the comparison - not arbitrary


# ------------------------------------------------------------------
# Shared contract across all four operations
# ------------------------------------------------------------------
@pytest.mark.parametrize("op", ["keep_largest", "remove_small", "fill_holes", "smooth"])
def test_cleanup_preserves_shape(op):
    m = _cube(shape=(9, 11, 13))
    if op == "keep_largest":
        result, _ = keep_largest_component(m)
    elif op == "remove_small":
        result, _ = remove_small_components(m, min_voxels=1)
    elif op == "fill_holes":
        result, _ = fill_holes(m)
    else:
        result, _ = smooth_binary_mask(m, iterations=1)
    assert result.shape == m.shape


@pytest.mark.parametrize("op", ["keep_largest", "remove_small", "fill_holes", "smooth"])
def test_cleanup_output_binary(op):
    m = _cube()
    if op == "keep_largest":
        result, _ = keep_largest_component(m)
    elif op == "remove_small":
        result, _ = remove_small_components(m, min_voxels=1)
    elif op == "fill_holes":
        result, _ = fill_holes(m)
    else:
        result, _ = smooth_binary_mask(m, iterations=1)
    assert result.dtype == np.uint8
    assert set(np.unique(result).tolist()) <= {0, 255}  # only 0/255, no intermediate values


def test_cleanup_does_not_mutate_input():
    m = _cube()
    original = m.copy()
    keep_largest_component(m)
    remove_small_components(m, min_voxels=1)
    fill_holes(m)
    smooth_binary_mask(m, iterations=1)
    assert np.array_equal(m, original)


# ------------------------------------------------------------------
# cleanup_stats
# ------------------------------------------------------------------
def test_cleanup_stats():
    before = _cube(shape=(10, 10, 10), lo=2, hi=8)  # 216 voxels
    after = _cube(shape=(10, 10, 10), lo=3, hi=7)  # 64 voxels

    stats = cleanup_stats(before, after)
    assert stats["before_voxels"] == 216
    assert stats["after_voxels"] == 64
    assert stats["delta_voxels"] == 64 - 216
    assert stats["delta_percent"] == pytest.approx((64 - 216) / 216 * 100.0)
    assert "before_volume_mm3" not in stats  # no spacing given


def test_cleanup_stats_with_spacing():
    before = _cube(shape=(10, 10, 10), lo=2, hi=8)
    after = before.copy()
    stats = cleanup_stats(before, after, spacing_zyx=(1.0, 2.0, 0.5))
    voxel_vol = 1.0 * 2.0 * 0.5
    assert stats["before_volume_mm3"] == pytest.approx(216 * voxel_vol)
    assert stats["delta_volume_mm3"] == pytest.approx(0.0)


def test_default_connectivity_is_six_connected():
    """Documents (Section 7) that DEFAULT_CONNECTIVITY=1 means 6-connected
    (face neighbors only) via scipy's own convention - two voxels
    touching only diagonally (edge/corner, not a shared face) must be
    SEPARATE components under the default."""
    assert DEFAULT_CONNECTIVITY == 1
    m = np.zeros((4, 4, 4), dtype=np.uint8)
    m[1, 1, 1] = 255
    m[2, 2, 2] = 255  # touches (1,1,1) only at a shared corner, not a face
    result, info = keep_largest_component(m)
    # Two equal-size (1-voxel) components under 6-connectivity - kept
    # exactly one of them (the tie-break, not both).
    assert info["component_count_before"] == 2
    assert int(result.sum()) // 255 == 1
