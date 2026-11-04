# --------------------------------------------------------------------------
# ROI statistics (core/analysis/roi_statistics.py): exact voxel counts,
# anisotropic physical volume, HU statistics, centroid, bounding box,
# components, slice coverage, histogram, empty / single-voxel / non-CT.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from plugins.roi_viewer.core.analysis.roi_statistics import (
    compute_roi_statistics, roi_histogram, voxel_volume_mm3)

SPACING = (0.5859375, 0.7, 1.25)  # (sx, sy, sz), anisotropic


def _box_volume():
    vol = np.full((40, 30, 50), -1000, dtype=np.int16)
    mask = np.zeros(vol.shape, dtype=bool)
    mask[5:35, 4:24, 10:20] = True  # 30 (z) x 20 (y) x 10 (x)
    vol[mask] = np.arange(mask.sum(), dtype=np.int16) % 200 - 50
    return vol, mask


def test_voxel_count_and_exact_anisotropic_volume():
    vol, mask = _box_volume()
    s = compute_roi_statistics(vol, mask, SPACING, "box")
    assert s.voxel_count == 10 * 20 * 30
    expected = 10 * 20 * 30 * (0.5859375 * 0.7 * 1.25)
    assert s.volume_mm3 == pytest.approx(expected, rel=0, abs=1e-9)
    assert s.volume_ml == pytest.approx(expected / 1000.0, rel=0, abs=1e-12)
    assert voxel_volume_mm3(SPACING) == 0.5859375 * 0.7 * 1.25


def test_hu_statistics_match_numpy():
    vol, mask = _box_volume()
    s = compute_roi_statistics(vol, mask, SPACING)
    v = vol[mask].astype(np.float64)
    assert (s.hu.minimum, s.hu.maximum) == (v.min(), v.max())
    assert s.hu.mean == pytest.approx(v.mean())
    assert s.hu.median == np.median(v)
    assert s.hu.std == pytest.approx(v.std())  # population std (ddof=0)


def test_centroid_bbox_and_slices():
    vol, mask = _box_volume()
    s = compute_roi_statistics(vol, mask, SPACING)
    assert s.centroid_voxel_zyx == pytest.approx((19.5, 13.5, 14.5))
    assert s.centroid_world_xyz == pytest.approx((14.5 * SPACING[0], 13.5 * SPACING[1], 19.5 * SPACING[2]))
    assert s.bbox_voxel_min_zyx == (5, 4, 10) and s.bbox_voxel_max_zyx == (34, 23, 19)
    assert s.bbox_size_mm_xyz == pytest.approx((10 * SPACING[0], 20 * SPACING[1], 30 * SPACING[2]))
    assert (s.first_axial_slice, s.last_axial_slice, s.occupied_axial_slices) == (5, 34, 30)


def test_components_six_connected():
    vol = np.zeros((5, 5, 5), dtype=np.int16)
    mask = np.zeros(vol.shape, dtype=bool)
    mask[0, 0, 0] = mask[1, 1, 1] = True  # corner contact only: 2 components
    mask[3:5, 3:5, 3:5] = True  # 8 voxels
    s = compute_roi_statistics(vol, mask, (1, 1, 1))
    assert s.component_count == 3 and s.largest_component_voxels == 8


def test_empty_roi():
    vol = np.zeros((3, 4, 5), dtype=np.int16)
    s = compute_roi_statistics(vol, np.zeros(vol.shape, bool), SPACING, "empty")
    assert s.voxel_count == 0 and s.volume_mm3 == 0.0 and s.hu is None
    assert s.centroid_voxel_zyx is None and s.component_count == 0 and s.occupied_axial_slices == 0


def test_single_voxel_roi():
    vol = np.zeros((3, 4, 5), dtype=np.int16)
    vol[2, 1, 3] = 77
    mask = np.zeros(vol.shape, bool)
    mask[2, 1, 3] = True
    s = compute_roi_statistics(vol, mask, SPACING)
    assert s.voxel_count == 1 and s.volume_mm3 == pytest.approx(voxel_volume_mm3(SPACING))
    assert (s.hu.minimum, s.hu.maximum, s.hu.mean, s.hu.median, s.hu.std) == (77, 77, 77, 77, 0)
    assert s.centroid_voxel_zyx == (2.0, 1.0, 3.0) and s.component_count == 1


def test_non_ct_disables_hu_only():
    vol, mask = _box_volume()
    s = compute_roi_statistics(vol, mask, SPACING, hu_available=False)
    assert s.hu is None and s.voxel_count == 6000 and s.component_count == 1
    s2 = compute_roi_statistics(None, mask, SPACING)
    assert s2.hu is None and s2.volume_mm3 == s.volume_mm3


def test_inputs_unchanged():
    vol, mask = _box_volume()
    v0, m0 = vol.copy(), mask.copy()
    compute_roi_statistics(vol, mask, SPACING)
    roi_histogram(vol, mask)
    assert np.array_equal(vol, v0) and np.array_equal(mask, m0)


def test_histogram_counts_only_the_roi():
    vol, mask = _box_volume()
    vol[~mask] = 3000  # outside values must not appear
    h = roi_histogram(vol, mask)
    assert sum(h.counts) + h.below + h.above == mask.sum()
    assert h.edges[0] == vol[mask].min() and h.edges[-1] == vol[mask].max() + 1
    h2 = roi_histogram(vol, mask, hu_range=(0, 100), bins=10)
    v = vol[mask]
    assert h2.below == int((v < 0).sum()) and h2.above == int((v > 100).sum())
    assert sum(h2.counts) == int(((v >= 0) & (v <= 100)).sum())
    with pytest.raises(ValueError):
        roi_histogram(vol, mask, hu_range=(5, 5))


def test_shape_mismatch_refused():
    with pytest.raises(ValueError):
        compute_roi_statistics(np.zeros((2, 2, 2)), np.zeros((2, 2, 3), bool), SPACING)
