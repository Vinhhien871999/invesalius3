# --------------------------------------------------------------------------
# Persistent phantom (known-geometry) validation tests.
# CT3D_P12_QUANTITATIVE_VALIDATION, Sections XVII-XVIII.
#
# Phantom A: an exact rectangular cuboid with known voxel dimensions and
# spacing - physical volume computed independently by hand, never copied
# from core/measurement.py's own formula.
# Phantom B: Phantom A shifted by a known offset - used for Dice/Jaccard/
# Hausdorff phantom validation (a sphere is deliberately NOT used for the
# exact-volume test, per the spec, since voxelizing a sphere introduces
# discretization error that would make "exact" assertions meaningless;
# a sphere-based approximate test is kept separate and clearly labeled).
#
# Every "Expected" value here is computed independently of the
# production function under test (hand arithmetic / a different code
# path), matching the phase spec's explicit instruction.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from plugins.roi_viewer.core.evaluation import dice_coefficient, hausdorff_distance, jaccard_index
from plugins.roi_viewer.core.measurement import MeasurementManager

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------
# Phantom A: exact rectangular cuboid, known physical volume
# ---------------------------------------------------------------------

PHANTOM_A_SHAPE_ZYX = (20, 15, 10)  # voxel dimensions (axial, coronal, sagital)
PHANTOM_A_SPACING_ZYX = (2.0, 1.5, 1.0)  # mm/voxel


def _phantom_a_mask():
    mask = np.zeros(PHANTOM_A_SHAPE_ZYX, dtype=np.uint8)
    mask[:, :, :] = 255  # the whole array IS the cuboid - no padding, no ambiguity
    return mask


def test_phantom_a_volume_matches_independent_hand_calculation():
    mask = _phantom_a_mask()
    expected_voxel_count = PHANTOM_A_SHAPE_ZYX[0] * PHANTOM_A_SHAPE_ZYX[1] * PHANTOM_A_SHAPE_ZYX[2]
    assert expected_voxel_count == 3000  # 20*15*10, arithmetic sanity-check of the fixture itself

    expected_volume_mm3 = expected_voxel_count * (
        PHANTOM_A_SPACING_ZYX[0] * PHANTOM_A_SPACING_ZYX[1] * PHANTOM_A_SPACING_ZYX[2]
    )
    assert expected_volume_mm3 == pytest.approx(9000.0)  # 3000 * 3.0 mm^3/voxel

    mgr = MeasurementManager()
    mgr.set_spacing(PHANTOM_A_SPACING_ZYX)
    measured_volume_mm3 = mgr.calculate_volume(mask)

    absolute_error = abs(measured_volume_mm3 - expected_volume_mm3)
    relative_error_pct = 100.0 * absolute_error / expected_volume_mm3
    assert absolute_error < 1e-9
    assert relative_error_pct < 1e-9


def test_phantom_a_partial_cuboid_volume():
    """A sub-region of Phantom A with a hand-computable voxel count, to
    confirm the measurement isn't just correct for "the whole array"."""
    mask = np.zeros((20, 15, 10), dtype=np.uint8)
    mask[2:12, 3:9, 1:7] = 255  # 10 * 6 * 6 = 360 voxels
    expected_voxel_count = 10 * 6 * 6
    assert expected_voxel_count == 360

    spacing = (0.8, 1.2, 2.5)
    expected_volume_mm3 = expected_voxel_count * (spacing[0] * spacing[1] * spacing[2])

    mgr = MeasurementManager()
    mgr.set_spacing(spacing)
    measured = mgr.calculate_volume(mask)
    assert measured == pytest.approx(expected_volume_mm3, rel=1e-9)


# ---------------------------------------------------------------------
# Phantom B: Phantom A shifted by a known offset - Dice/Jaccard/Hausdorff
# ---------------------------------------------------------------------

def _phantom_b_mask(shift_axial: int):
    """Phantom A's cuboid, embedded in a larger volume and shifted by a
    known number of voxels along the axial axis, so the true overlap/
    Hausdorff distance can be computed by hand."""
    padded_shape = (PHANTOM_A_SHAPE_ZYX[0] + 10, PHANTOM_A_SHAPE_ZYX[1], PHANTOM_A_SHAPE_ZYX[2])
    a = np.zeros(padded_shape, dtype=bool)
    a[0 : PHANTOM_A_SHAPE_ZYX[0], :, :] = True
    b = np.zeros(padded_shape, dtype=bool)
    b[shift_axial : shift_axial + PHANTOM_A_SHAPE_ZYX[0], :, :] = True
    return a, b


@pytest.mark.parametrize("shift", [2, 5, 8])
def test_phantom_b_dice_matches_hand_computed_overlap_fraction(shift):
    a, b = _phantom_b_mask(shift_axial=shift)
    total = PHANTOM_A_SHAPE_ZYX[0]
    overlap_voxels = (total - shift) * PHANTOM_A_SHAPE_ZYX[1] * PHANTOM_A_SHAPE_ZYX[2]
    a_voxels = total * PHANTOM_A_SHAPE_ZYX[1] * PHANTOM_A_SHAPE_ZYX[2]
    b_voxels = a_voxels  # same shape, just shifted
    expected_dice = 2 * overlap_voxels / (a_voxels + b_voxels)

    measured_dice = dice_coefficient(a, b)
    assert measured_dice == pytest.approx(expected_dice, rel=1e-9)


@pytest.mark.parametrize("shift", [2, 5, 8])
def test_phantom_b_jaccard_matches_hand_computed_overlap_fraction(shift):
    a, b = _phantom_b_mask(shift_axial=shift)
    total = PHANTOM_A_SHAPE_ZYX[0]
    overlap_voxels = (total - shift) * PHANTOM_A_SHAPE_ZYX[1] * PHANTOM_A_SHAPE_ZYX[2]
    a_voxels = total * PHANTOM_A_SHAPE_ZYX[1] * PHANTOM_A_SHAPE_ZYX[2]
    union_voxels = 2 * a_voxels - overlap_voxels
    expected_jaccard = overlap_voxels / union_voxels

    measured_jaccard = jaccard_index(a, b)
    assert measured_jaccard == pytest.approx(expected_jaccard, rel=1e-9)


@pytest.mark.parametrize("shift", [2, 5, 8])
def test_phantom_b_hausdorff_matches_shift_distance_in_physical_units(shift):
    """The cuboids are shifted purely along the axial axis by `shift`
    voxels - the Hausdorff distance between them (both directions) is
    exactly shift * spacing_axial, since the leading/trailing faces are
    flat and the shift is axis-aligned."""
    a, b = _phantom_b_mask(shift_axial=shift)
    spacing_zyx = (1.7, 1.0, 1.0)  # anisotropic on purpose
    expected_hd_mm = shift * spacing_zyx[0]

    measured_hd = hausdorff_distance(a, b, spacing_zyx=spacing_zyx)
    assert measured_hd == pytest.approx(expected_hd_mm, rel=1e-9)


# ---------------------------------------------------------------------
# Sphere phantom - approximate only, clearly labeled (voxelization
# discretization error is expected and documented, not a bug)
# ---------------------------------------------------------------------

def test_sphere_phantom_volume_is_approximately_correct_not_exact():
    """
    A voxelized sphere's volume only approximates 4/3*pi*r^3 - this test
    documents and bounds that expected discretization error rather than
    asserting exact equality (which would be a wrong expectation for a
    voxelized sphere, per the phase spec's explicit warning).
    """
    radius_voxels = 15
    spacing = (1.0, 1.0, 1.0)
    shape = (2 * radius_voxels + 3,) * 3
    center = shape[0] // 2
    zz, yy, xx = np.ogrid[: shape[0], : shape[1], : shape[2]]
    sphere = ((zz - center) ** 2 + (yy - center) ** 2 + (xx - center) ** 2) <= radius_voxels**2

    mgr = MeasurementManager()
    mgr.set_spacing(spacing)
    measured_volume = mgr.calculate_volume(sphere.astype(np.uint8))

    expected_volume = (4.0 / 3.0) * np.pi * radius_voxels**3
    relative_error_pct = 100.0 * abs(measured_volume - expected_volume) / expected_volume
    # Voxelization error for a radius-15 sphere is small but real -
    # bound it generously (a few percent) rather than asserting exact
    # equality or an arbitrarily tight tolerance.
    assert relative_error_pct < 5.0
