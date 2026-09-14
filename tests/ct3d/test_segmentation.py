# --------------------------------------------------------------------------
# Persistent unit tests for plugins/roi_viewer/core/segmentation.py
# (D10 Region Growing, D2 threshold/Otsu). CT3D_P11_TEST_AUTOMATION,
# Section V. Pure numpy/scipy - no wx/InVesalius/VTK dependency, so these
# run under `-m unit`.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from plugins.roi_viewer.core.segmentation import SegmentationManager

pytestmark = pytest.mark.unit


@pytest.fixture
def mgr():
    return SegmentationManager()


def test_rg_u1_seed_component_simple(mgr):
    """A single connected foreground block: region growing from a seed
    inside it must recover exactly that block."""
    volume = np.zeros((10, 10, 10), dtype=np.int16)
    volume[2:6, 2:6, 2:6] = 100  # a 4x4x4 = 64-voxel block
    result = mgr.region_growing(volume, seed=(3, 3, 3), tolerance=5)
    assert result.sum() == 64
    assert np.array_equal(result[2:6, 2:6, 2:6], np.ones((4, 4, 4), dtype=np.uint8))
    assert result[0, 0, 0] == 0


def test_rg_u2_two_disjoint_same_intensity_regions(mgr):
    """Two blocks with identical intensity but not touching: only the
    component containing the seed must be selected."""
    volume = np.zeros((10, 10, 10), dtype=np.int16)
    volume[0:2, 0:2, 0:2] = 100  # block A (8 voxels)
    volume[7:9, 7:9, 7:9] = 100  # block B (8 voxels), not adjacent to A
    result = mgr.region_growing(volume, seed=(0, 0, 0), tolerance=5)
    assert result.sum() == 8
    assert result[0, 0, 0] == 1
    assert result[7, 7, 7] == 0  # block B must NOT be included


def test_rg_u3_tolerance_zero_exact_match_only(mgr):
    volume = np.zeros((6, 6, 6), dtype=np.int16)
    volume[1:3, 1:3, 1:3] = 100
    volume[3, 1, 1] = 105  # adjacent but outside tolerance=0 band
    result = mgr.region_growing(volume, seed=(1, 1, 1), tolerance=0)
    assert result[3, 1, 1] == 0
    assert result[1, 1, 1] == 1


def test_rg_u4_negative_tolerance_raises(mgr):
    volume = np.zeros((5, 5, 5), dtype=np.int16)
    with pytest.raises(ValueError):
        mgr.region_growing(volume, seed=(0, 0, 0), tolerance=-1)


def test_rg_u5_seed_out_of_bounds_returns_empty_mask(mgr):
    volume = np.zeros((5, 5, 5), dtype=np.int16)
    result = mgr.region_growing(volume, seed=(10, 10, 10), tolerance=5)
    assert result.shape == volume.shape
    assert result.sum() == 0


def test_rg_u6_seed_with_nan_is_rejected_by_validate_seed(mgr):
    reason = mgr.validate_seed((float("nan"), 0, 0), (5, 5, 5))
    assert reason is not None
    assert "finite" in reason.lower()


def test_rg_u6b_seed_with_inf_is_rejected(mgr):
    reason = mgr.validate_seed((float("inf"), 0, 0), (5, 5, 5))
    assert reason is not None


def test_rg_u7_boundary_seed_is_valid_and_grows(mgr):
    """A seed exactly on the volume's edge (index 0 or shape-1) is a
    valid position, not an off-by-one out-of-bounds case."""
    volume = np.zeros((5, 5, 5), dtype=np.int16)
    volume[0, 0, 0] = 50
    volume[4, 4, 4] = 50
    assert mgr.validate_seed((0, 0, 0), volume.shape) is None
    assert mgr.validate_seed((4, 4, 4), volume.shape) is None
    result = mgr.region_growing(volume, seed=(0, 0, 0), tolerance=5)
    assert result[0, 0, 0] == 1
    assert result[4, 4, 4] == 0  # not connected to the seed's component


def test_rg_u8_six_connectivity_diagonal_not_connected(mgr):
    """ndimage.label()'s default 3D structure is 6-connected (face
    neighbors only) - two voxels touching only at a corner/edge must NOT
    be considered connected."""
    volume = np.zeros((4, 4, 4), dtype=np.int16)
    volume[1, 1, 1] = 100
    volume[2, 2, 2] = 100  # diagonal neighbor only, not face-adjacent
    result = mgr.region_growing(volume, seed=(1, 1, 1), tolerance=5)
    assert result[1, 1, 1] == 1
    assert result[2, 2, 2] == 0  # diagonal - not reachable via 6-connectivity
    assert result.sum() == 1


def test_rg_u8b_six_connectivity_face_adjacent_is_connected(mgr):
    volume = np.zeros((4, 4, 4), dtype=np.int16)
    volume[1, 1, 1] = 100
    volume[1, 1, 2] = 100  # face-adjacent along one axis
    result = mgr.region_growing(volume, seed=(1, 1, 1), tolerance=5)
    assert result.sum() == 2
    assert result[1, 1, 2] == 1


def test_validate_seed_none_volume_shape():
    mgr = SegmentationManager()
    assert mgr.validate_seed((0, 0, 0), None) is not None


def test_validate_seed_wrong_length():
    mgr = SegmentationManager()
    assert mgr.validate_seed((0, 0), (5, 5, 5)) is not None


def test_region_stats_fraction_and_limit(mgr):
    result_mask = np.zeros((10, 10, 10), dtype=np.uint8)
    result_mask[0:3, 0:10, 0:10] = 1  # 300 / 1000 = 30% > default 20% limit
    stats = mgr.region_stats(result_mask)
    assert stats["voxel_count"] == 300
    assert stats["total_voxels"] == 1000
    assert stats["fraction"] == pytest.approx(0.3)
    assert stats["exceeds_limit"] is True


def test_region_stats_within_limit(mgr):
    result_mask = np.zeros((10, 10, 10), dtype=np.uint8)
    result_mask[0, 0:10, 0:10] = 1  # 100/1000 = 10% < 20%
    stats = mgr.region_stats(result_mask)
    assert stats["exceeds_limit"] is False


def test_region_stats_volume_mm3_with_spacing(mgr):
    result_mask = np.zeros((5, 5, 5), dtype=np.uint8)
    result_mask[0:2, 0:2, 0:2] = 1  # 8 voxels
    stats = mgr.region_stats(result_mask, spacing=(0.5, 0.5, 2.0))
    assert stats["volume_mm3"] == pytest.approx(8 * 0.5 * 0.5 * 2.0)


def test_apply_threshold_basic():
    mgr = SegmentationManager()
    mgr.set_threshold(100, 200)
    volume = np.array([50, 100, 150, 200, 250], dtype=np.int16).reshape(1, 1, 5)
    mask = mgr.apply_threshold(volume)
    assert mask.tolist() == [[[0, 1, 1, 1, 0]]]


def test_auto_threshold_otsu_returns_int_tuple():
    mgr = SegmentationManager()
    rng = np.random.default_rng(42)
    # Bimodal distribution: two separated clusters
    low = rng.normal(50, 5, 500)
    high = rng.normal(200, 5, 500)
    volume = np.concatenate([low, high]).reshape(10, 10, 10).astype(np.int16)
    lo, hi = mgr.auto_threshold_otsu(volume)
    assert isinstance(lo, int)
    assert isinstance(hi, int)
    assert lo < hi
