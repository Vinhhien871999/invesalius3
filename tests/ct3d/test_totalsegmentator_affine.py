# --------------------------------------------------------------------------
# E6b hard gate - NIfTI affine for TotalSegmentator
# (plugins/roi_viewer/core/ai/providers/totalsegmentator_provider.py).
#
# Two independent proofs, on anisotropic and asymmetric spacing:
#
# 1. ANATOMY. A synthetic axial DICOM series is described by its real DICOM
#    geometry (ImageOrientationPatient, ImagePositionPatient per slice,
#    pixel spacing). The native InVesalius volume is built by InVesalius's
#    OWN import function (imagedata_utils.dcm2memmap - row flip included;
#    only the file reading is replaced). Every landmark's position from our
#    affine must equal its physical DICOM position (LPS -> RAS), up to the
#    constant translation the provider leaves at 0.
# 2. GRID ROUNDTRIP through what TotalSegmentator does to geometry
#    (nibabel canonical reorientation, predict, reorient back to the input):
#    every landmark returns to its original native voxel - no mirror, no
#    axis swap, no rotation, no off-by-one, no spacing collapse.
# --------------------------------------------------------------------------
import numpy as np
import pytest

nib = pytest.importorskip("nibabel")

from plugins.roi_viewer.core.ai.providers import totalsegmentator_provider as ts  # noqa: E402

SPACINGS = [(0.4785, 0.4785, 1.5), (0.5, 0.8, 2.3)]  # (x, y, z): 0051, asymmetric
IOPS = {
    "0051 / standard supine": (1.0, 0.0, 0.0, 0.0, 1.0, 0.0),  # real 0051 header value
    "rows flipped": (1.0, 0.0, 0.0, 0.0, -1.0, 0.0),
    "rotated 90 deg in-plane": (0.0, 1.0, 0.0, -1.0, 0.0, 0.0),
    "slightly oblique": (0.9961947, 0.0871557, 0.0, -0.0871557, 0.9961947, 0.0),
}
SHAPE_ZYX = (7, 11, 13)  # every axis a different length


def _landmarks(shape_zyx):
    nz, ny, nx = shape_zyx
    return {  # distinct values, far from any symmetry
        (0, 0, 0): 101,  # origin corner
        (1, 2, 3): 102,  # near origin
        (4, 7, 5): 103,  # off-centre
        (2, 9, 11): 104,  # off-centre
        (nz - 1, ny - 1, nx - 1): 105,  # last corner
    }


def _dicom_series(shape_zyx, spacing_xyz, iop, ipp0=(-122.5, -167.5, 116.0)):
    """Per-slice pixel arrays (as the DICOM file stores them: rows x cols)
    and each pixel's LPS position function, for slices listed in the order
    InVesalius's IPPSorter yields (ascending along the normal)."""
    nz, ny, nx = shape_zyx
    sx, sy, sz = spacing_xyz
    row = np.array(iop[:3])
    col = np.array(iop[3:])
    normal = np.cross(row, col)
    ipp = [np.array(ipp0) + k * sz * normal for k in range(nz)]

    def lps(k, r, c):  # DICOM: column index along row cosine, row index along column cosine
        return ipp[k] + c * sx * row + r * sy * col

    return ipp, lps


def _native_from_dicom(monkeypatch, pixels):
    """InVesalius's real axial import (dcm2memmap) of per-slice arrays."""
    from invesalius.data import imagedata_utils as iu

    monkeypatch.setattr(iu, "read_dcm_slice_as_np2", lambda f, resolution_percentage=1.0: pixels[f])
    monkeypatch.setattr(iu.vtk_utils, "ShowProgress", lambda *a, **k: (lambda *a2, **k2: None))
    files = sorted(pixels)
    matrix, _, temp_file = iu.dcm2memmap(files, None, "AXIAL", 1.0)
    native = np.array(matrix)
    matrix._mmap.close()
    del matrix
    import os

    os.remove(temp_file)
    return native


def _build(monkeypatch, shape_zyx, spacing, iop):
    """Landmarks placed in DICOM pixel space, imported by InVesalius."""
    nz, ny, nx = shape_zyx
    pixels = {f"slice{k:03d}": np.zeros((ny, nx), dtype=np.int16) for k in range(nz)}
    dicom_pixel = {}
    for (z, y, x), value in _landmarks(shape_zyx).items():
        r = ny - 1 - y  # where the landmark must be in the DICOM file for InVesalius to put it at native y
        pixels[f"slice{z:03d}"][r, x] = value
        dicom_pixel[value] = (z, r, x)
    native = _native_from_dicom(monkeypatch, pixels)
    return native, dicom_pixel


@pytest.mark.parametrize("spacing", SPACINGS)
@pytest.mark.parametrize("iop_name", list(IOPS))
def test_affine_places_each_voxel_at_its_physical_dicom_position(monkeypatch, spacing, iop_name):
    iop = IOPS[iop_name]
    native, dicom_pixel = _build(monkeypatch, SHAPE_ZYX, spacing, iop)
    _, lps = _dicom_series(SHAPE_ZYX, spacing, iop)
    affine = ts.nifti_affine(spacing, iop)
    to_ras = np.diag([-1.0, -1.0, 1.0])
    ref_value = 101
    ref_native = tuple(int(i) for i in np.argwhere(native == ref_value)[0])
    ref_world = affine @ np.array([ref_native[2], ref_native[1], ref_native[0], 1.0])
    ref_truth = to_ras @ lps(*dicom_pixel[ref_value])
    for value, (k, r, c) in dicom_pixel.items():
        z, y, x = (int(i) for i in np.argwhere(native == value)[0])  # where InVesalius really put it
        world = affine @ np.array([x, y, z, 1.0])
        truth = to_ras @ lps(k, r, c)
        np.testing.assert_allclose(world[:3] - ref_world[:3], truth - ref_truth, atol=1e-6,
                                   err_msg=f"landmark {value} at native {(z, y, x)}")


def test_anatomy_check_detects_a_missing_row_flip(monkeypatch):
    """Control: an affine that forgets InVesalius's row flip (native y along
    +column cosine) must FAIL the physical-position check above."""
    spacing, iop = SPACINGS[1], IOPS["0051 / standard supine"]
    native, dicom_pixel = _build(monkeypatch, SHAPE_ZYX, spacing, iop)
    _, lps = _dicom_series(SHAPE_ZYX, spacing, iop)
    wrong = ts.nifti_affine(spacing, iop)
    wrong[:3, 1] *= -1
    to_ras = np.diag([-1.0, -1.0, 1.0])
    ref = tuple(int(i) for i in np.argwhere(native == 101)[0])
    ref_world = wrong @ np.array([ref[2], ref[1], ref[0], 1.0])
    ref_truth = to_ras @ lps(*dicom_pixel[101])
    errors = []
    for value, pixel in dicom_pixel.items():
        z, y, x = (int(i) for i in np.argwhere(native == value)[0])
        world = wrong @ np.array([x, y, z, 1.0])
        errors.append(np.abs((world[:3] - ref_world[:3]) - (to_ras @ lps(*pixel) - ref_truth)).max())
    assert max(errors) > 1.0


def test_0051_axis_directions():
    """0051 header: IOP (1,0,0, 0,1,0), slices ascending in +z (116 -> 276 mm).
    Native x -> patient Left, native y -> Anterior (rows flipped on import),
    native z -> Superior; spacing kept per axis."""
    dx, dy, dz = ts.matrix_axis_directions_ras(IOPS["0051 / standard supine"])
    np.testing.assert_allclose(dx, (-1, 0, 0))  # RAS: -x = Left
    np.testing.assert_allclose(dy, (0, 1, 0))  # +y = Anterior
    np.testing.assert_allclose(dz, (0, 0, 1))  # +z = Superior
    affine = ts.nifti_affine((0.4785, 0.4785, 1.5), IOPS["0051 / standard supine"])
    np.testing.assert_allclose(np.abs(np.diag(affine)[:3]), (0.4785, 0.4785, 1.5))
    np.testing.assert_allclose(affine[:3, 3], 0.0)


@pytest.mark.parametrize("spacing", SPACINGS)
@pytest.mark.parametrize("iop_name", list(IOPS))
def test_landmarks_roundtrip_through_totalsegmentator_geometry(monkeypatch, spacing, iop_name):
    """native -> NIfTI -> canonical (what TotalSegmentator predicts in) ->
    segmentation reoriented back to the input -> native candidate."""
    iop = IOPS[iop_name]
    native, _ = _build(monkeypatch, SHAPE_ZYX, spacing, iop)
    affine = ts.nifti_affine(spacing, iop)
    image = nib.Nifti1Image(np.ascontiguousarray(ts.to_nifti_data(native)), affine)

    canonical = nib.as_closest_canonical(image)
    seg_canonical = np.where(np.asanyarray(canonical.dataobj) > 100,
                             np.asanyarray(canonical.dataobj) - 100, 0).astype(np.uint8)
    back = nib.Nifti1Image(seg_canonical, canonical.affine).as_reoriented(
        nib.orientations.ornt_transform(nib.io_orientation(canonical.affine), nib.io_orientation(affine)))

    for value, label in ((v, v - 100) for v in _landmarks(SHAPE_ZYX).values()):
        candidate = ts.extract_structure(back, label, SHAPE_ZYX, affine)
        assert candidate.shape == SHAPE_ZYX and candidate.dtype == bool
        assert np.array_equal(candidate, native == value), f"landmark {value} ({iop_name}, {spacing})"


def test_world_of_canonical_landmark_maps_back_to_native_voxel():
    spacing, iop = SPACINGS[1], IOPS["rotated 90 deg in-plane"]
    native = np.zeros(SHAPE_ZYX, dtype=np.int16)
    native[2, 9, 11] = 7
    affine = ts.nifti_affine(spacing, iop)
    canonical = nib.as_closest_canonical(nib.Nifti1Image(ts.to_nifti_data(native).copy(), affine))
    ijk = np.argwhere(np.asanyarray(canonical.dataobj) == 7)[0]
    world = canonical.affine @ np.append(ijk, 1.0)
    x, y, z = np.round(np.linalg.inv(affine) @ world)[:3].astype(int)
    assert (z, y, x) == (2, 9, 11)


def test_output_grid_mismatch_is_detected():
    spacing, iop = SPACINGS[0], IOPS["0051 / standard supine"]
    affine = ts.nifti_affine(spacing, iop)
    data = np.zeros(SHAPE_ZYX[::-1], dtype=np.uint8)
    flipped = affine.copy()
    flipped[:3, 1] *= -1  # a y mirror
    with pytest.raises(ts.OutputGridMismatch):
        ts.extract_structure(nib.Nifti1Image(data, flipped), 1, SHAPE_ZYX, affine)
    swapped = affine[:, [1, 0, 2, 3]]  # an x/y swap
    with pytest.raises(ts.OutputGridMismatch):
        ts.extract_structure(nib.Nifti1Image(data, swapped), 1, SHAPE_ZYX, affine)
    with pytest.raises(ts.OutputGridMismatch):  # wrong shape - never reshaped to fit
        ts.extract_structure(nib.Nifti1Image(np.zeros((13, 11, 6), np.uint8), affine), 1, SHAPE_ZYX, affine)
    rescaled = affine.copy()
    rescaled[:3, 2] *= 2  # spacing changed
    with pytest.raises(ts.OutputGridMismatch):
        ts.extract_structure(nib.Nifti1Image(data, rescaled), 1, SHAPE_ZYX, affine)


@pytest.mark.parametrize("iop", [None, (1, 0, 0), (1, 0, 0, 1, 0, 0), (2, 0, 0, 0, 1, 0), (np.nan,) * 6])
def test_unknown_orientation_refused(iop):
    with pytest.raises(ts.OrientationUnknown):
        ts.nifti_affine((1.0, 1.0, 1.0), iop)
