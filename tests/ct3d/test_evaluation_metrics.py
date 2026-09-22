# --------------------------------------------------------------------------
# Persistent unit tests for plugins/roi_viewer/core/evaluation.py (Dice,
# Jaccard, Hausdorff distance). CT3D_P12_QUANTITATIVE_VALIDATION, Sections
# XI-XVI. Pure numpy/scipy - no DICOM/GUI/dataset dependency, runs under
# `-m unit`. Reference values below are computed independently (by hand /
# simple formulas), never copied from evaluation.py's own implementation.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from plugins.roi_viewer.core.evaluation import (
    dice_coefficient,
    hausdorff_distance,
    hausdorff_distance_95,
    jaccard_index,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------
# DICE-T1..T5
# ---------------------------------------------------------------------

def test_dice_t1_identical_non_empty():
    mask = np.zeros((10, 10, 10), dtype=bool)
    mask[2:6, 2:6, 2:6] = True
    assert dice_coefficient(mask, mask.copy()) == pytest.approx(1.0)


def test_dice_t2_no_overlap():
    a = np.zeros((10, 10, 10), dtype=bool)
    b = np.zeros((10, 10, 10), dtype=bool)
    a[0:3, 0:3, 0:3] = True
    b[7:10, 7:10, 7:10] = True
    assert dice_coefficient(a, b) == pytest.approx(0.0)


def test_dice_t3_known_partial_overlap_exact_fraction():
    """|A|=10,|B|=10,intersection=5 along one axis -> Dice = 2*5/20 = 0.5 exactly."""
    a = np.zeros((20, 4, 4), dtype=bool)
    b = np.zeros((20, 4, 4), dtype=bool)
    a[0:10, :, :] = True
    b[5:15, :, :] = True
    assert dice_coefficient(a, b) == pytest.approx(0.5)


def test_dice_t4_empty_empty():
    a = np.zeros((5, 5, 5), dtype=bool)
    b = np.zeros((5, 5, 5), dtype=bool)
    assert dice_coefficient(a, b) == pytest.approx(1.0)


def test_dice_t5_empty_non_empty():
    a = np.zeros((5, 5, 5), dtype=bool)
    b = np.zeros((5, 5, 5), dtype=bool)
    b[0, 0, 0] = True
    assert dice_coefficient(a, b) == pytest.approx(0.0)


# ---------------------------------------------------------------------
# Jaccard - same case families as Dice + the Dice<->Jaccard relation
# ---------------------------------------------------------------------

def test_jaccard_identical_non_empty():
    mask = np.zeros((10, 10, 10), dtype=bool)
    mask[2:6, 2:6, 2:6] = True
    assert jaccard_index(mask, mask.copy()) == pytest.approx(1.0)


def test_jaccard_no_overlap():
    a = np.zeros((10, 10, 10), dtype=bool)
    b = np.zeros((10, 10, 10), dtype=bool)
    a[0:3, 0:3, 0:3] = True
    b[7:10, 7:10, 7:10] = True
    assert jaccard_index(a, b) == pytest.approx(0.0)


def test_jaccard_known_partial_overlap_exact_fraction():
    """|A|=10,|B|=10,intersection=5,union=15 -> Jaccard = 5/15 = 1/3 exactly."""
    a = np.zeros((20, 4, 4), dtype=bool)
    b = np.zeros((20, 4, 4), dtype=bool)
    a[0:10, :, :] = True
    b[5:15, :, :] = True
    assert jaccard_index(a, b) == pytest.approx(1.0 / 3.0)


def test_jaccard_empty_empty():
    a = np.zeros((5, 5, 5), dtype=bool)
    b = np.zeros((5, 5, 5), dtype=bool)
    assert jaccard_index(a, b) == pytest.approx(1.0)


def test_jaccard_empty_non_empty():
    a = np.zeros((5, 5, 5), dtype=bool)
    b = np.zeros((5, 5, 5), dtype=bool)
    b[0, 0, 0] = True
    assert jaccard_index(a, b) == pytest.approx(0.0)


@pytest.mark.parametrize("overlap_fraction", [0.2, 0.5, 0.8])
def test_dice_jaccard_consistency_relation(overlap_fraction):
    """Dice = 2J / (1 + J) for any non-degenerate (non-empty union) case."""
    total = 20
    overlap = int(round(total * overlap_fraction))
    a = np.zeros((total * 2, 4, 4), dtype=bool)
    b = np.zeros((total * 2, 4, 4), dtype=bool)
    a[0:total, :, :] = True
    b[total - overlap : total - overlap + total, :, :] = True

    d = dice_coefficient(a, b)
    j = jaccard_index(a, b)
    assert d == pytest.approx(2 * j / (1 + j), abs=1e-9)


# ---------------------------------------------------------------------
# Input validation (Section XV)
# ---------------------------------------------------------------------

def test_dice_shape_mismatch_raises():
    a = np.zeros((5, 5, 5), dtype=bool)
    b = np.zeros((5, 5, 6), dtype=bool)
    with pytest.raises(ValueError):
        dice_coefficient(a, b)


def test_jaccard_shape_mismatch_raises():
    a = np.zeros((5, 5, 5), dtype=bool)
    b = np.zeros((6, 5, 5), dtype=bool)
    with pytest.raises(ValueError):
        jaccard_index(a, b)


def test_dice_casts_non_boolean_input_correctly():
    """A uint8 mask with values {0, 255} (the real InVesalius mask
    convention) must be treated identically to an equivalent bool mask -
    dice_coefficient/jaccard_index must cast explicitly, not silently
    misinterpret 255 as anything but True."""
    a_bool = np.zeros((5, 5, 5), dtype=bool)
    a_bool[0:2, 0:2, 0:2] = True
    a_uint8 = (a_bool.astype(np.uint8)) * 255
    b_bool = np.zeros((5, 5, 5), dtype=bool)
    b_bool[0:2, 0:2, 0:2] = True
    assert dice_coefficient(a_uint8, b_bool) == pytest.approx(dice_coefficient(a_bool, b_bool))


def test_hausdorff_spacing_length_mismatch_raises():
    a = np.zeros((5, 5, 5), dtype=bool)
    a[2, 2, 2] = True
    b = a.copy()
    with pytest.raises(ValueError):
        hausdorff_distance(a, b, spacing_zyx=(1.0, 1.0))  # only 2 values for a 3D mask


def test_hausdorff_spacing_non_positive_raises():
    a = np.zeros((5, 5, 5), dtype=bool)
    a[2, 2, 2] = True
    b = a.copy()
    with pytest.raises(ValueError):
        hausdorff_distance(a, b, spacing_zyx=(1.0, 0.0, 1.0))


def test_hausdorff_spacing_non_finite_raises():
    a = np.zeros((5, 5, 5), dtype=bool)
    a[2, 2, 2] = True
    b = a.copy()
    with pytest.raises(ValueError):
        hausdorff_distance(a, b, spacing_zyx=(1.0, float("inf"), 1.0))


# ---------------------------------------------------------------------
# HD-T1..T5 (Hausdorff distance, physical spacing)
# ---------------------------------------------------------------------

def test_hd_t1_identical_is_zero():
    a = np.zeros((10, 10, 10), dtype=bool)
    a[3:6, 3:6, 3:6] = True
    assert hausdorff_distance(a, a.copy(), spacing_zyx=(1.0, 1.0, 1.0)) == pytest.approx(0.0)


def test_hd_t2_single_voxel_shift_isotropic_spacing():
    """Single-voxel masks, shifted by exactly 1 voxel along axis 2
    (sagital), isotropic spacing 1.0mm -> Hausdorff = 1.0mm exactly."""
    a = np.zeros((10, 10, 10), dtype=bool)
    b = np.zeros((10, 10, 10), dtype=bool)
    a[5, 5, 5] = True
    b[5, 5, 6] = True
    assert hausdorff_distance(a, b, spacing_zyx=(1.0, 1.0, 1.0)) == pytest.approx(1.0)


def test_hd_t3_anisotropic_spacing_shift_along_z():
    """Single-voxel masks, shifted by 1 voxel along axis 0 (axial, the
    axis with spacing_zyx[0]=3.0mm) -> Hausdorff = 3.0mm exactly, NOT
    1.0 (which a voxel-index-only computation would wrongly give)."""
    a = np.zeros((10, 10, 10), dtype=bool)
    b = np.zeros((10, 10, 10), dtype=bool)
    a[5, 5, 5] = True
    b[6, 5, 5] = True  # shift along axis 0 (axial)
    result = hausdorff_distance(a, b, spacing_zyx=(3.0, 1.0, 1.0))
    assert result == pytest.approx(3.0)
    assert result != pytest.approx(1.0)  # would be wrong if spacing were ignored


def test_hd_t3b_anisotropic_spacing_shift_along_different_axis():
    """Same shift distance in voxels, but along the axis with spacing
    1.0mm (not 3.0mm) -> Hausdorff = 1.0mm, confirming the axis-specific
    (not just "some" anisotropic) sampling is applied correctly."""
    a = np.zeros((10, 10, 10), dtype=bool)
    b = np.zeros((10, 10, 10), dtype=bool)
    a[5, 5, 5] = True
    b[5, 6, 5] = True  # shift along axis 1 (coronal), spacing 1.0mm
    result = hausdorff_distance(a, b, spacing_zyx=(3.0, 1.0, 1.0))
    assert result == pytest.approx(1.0)


def test_hd_t4_empty_empty_is_zero():
    a = np.zeros((5, 5, 5), dtype=bool)
    b = np.zeros((5, 5, 5), dtype=bool)
    assert hausdorff_distance(a, b, spacing_zyx=(1.0, 1.0, 1.0)) == pytest.approx(0.0)


def test_hd_t5_one_empty_raises():
    a = np.zeros((5, 5, 5), dtype=bool)
    b = np.zeros((5, 5, 5), dtype=bool)
    b[2, 2, 2] = True
    with pytest.raises(ValueError):
        hausdorff_distance(a, b, spacing_zyx=(1.0, 1.0, 1.0))
    with pytest.raises(ValueError):
        hausdorff_distance(b, a, spacing_zyx=(1.0, 1.0, 1.0))  # symmetric - either order raises


# ---------------------------------------------------------------------
# HD95 (Section XIV - explicitly a different metric from HD max)
# ---------------------------------------------------------------------

def test_hd95_identical_is_zero():
    a = np.zeros((10, 10, 10), dtype=bool)
    a[3:6, 3:6, 3:6] = True
    assert hausdorff_distance_95(a, a.copy(), spacing_zyx=(1.0, 1.0, 1.0)) == pytest.approx(0.0)


def test_hd95_is_less_than_or_equal_to_hd_max():
    """HD95 (95th percentile) must never exceed the true maximum - a
    basic sanity relationship between the two metrics."""
    rng = np.random.default_rng(20260914)
    a = rng.random((15, 15, 15)) > 0.7
    b = rng.random((15, 15, 15)) > 0.7
    if not a.any() or not b.any():
        pytest.skip("degenerate random draw - regenerate not needed for this sanity check")
    hd_max = hausdorff_distance(a, b, spacing_zyx=(1.0, 1.0, 1.0))
    hd95 = hausdorff_distance_95(a, b, spacing_zyx=(1.0, 1.0, 1.0))
    assert hd95 <= hd_max + 1e-9


def test_hd95_empty_empty_is_zero():
    a = np.zeros((5, 5, 5), dtype=bool)
    b = np.zeros((5, 5, 5), dtype=bool)
    assert hausdorff_distance_95(a, b, spacing_zyx=(1.0, 1.0, 1.0)) == pytest.approx(0.0)


def test_hd95_one_empty_raises():
    a = np.zeros((5, 5, 5), dtype=bool)
    b = np.zeros((5, 5, 5), dtype=bool)
    b[2, 2, 2] = True
    with pytest.raises(ValueError):
        hausdorff_distance_95(a, b, spacing_zyx=(1.0, 1.0, 1.0))


def test_hd95_differs_from_hd_max_when_there_is_an_outlier():
    """Directly demonstrates HD95 != HD max is expected (not a bug) when
    a single outlier voxel dominates the true maximum."""
    a = np.zeros((30, 10, 10), dtype=bool)
    b = np.zeros((30, 10, 10), dtype=bool)
    # A big block that matches closely (small per-voxel distances)...
    a[0:20, :, :] = True
    b[0:20, :, :] = True
    b[1:19, 1:9, 1:9] = False  # carve out interior of b slightly - small boundary mismatch
    a[1:19, 1:9, 1:9] = False
    # ...plus one far-away outlier voxel only in b.
    b[29, 0, 0] = True
    hd_max = hausdorff_distance(a, b, spacing_zyx=(1.0, 1.0, 1.0))
    hd95 = hausdorff_distance_95(a, b, spacing_zyx=(1.0, 1.0, 1.0))
    assert hd_max > hd95  # the outlier dominates the max but not the 95th percentile
