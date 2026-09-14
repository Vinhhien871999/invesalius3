# --------------------------------------------------------------------------
# Persistent tests for plugins/roi_viewer/core/exporters.py (H1 mask
# export, H2-H5 surface export). CT3D_P11_TEST_AUTOMATION, Section
# XVIII. Small synthetic data only - never a large real mesh in this
# suite.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from plugins.roi_viewer.core.exporters import ExporterManager

pytestmark = pytest.mark.integration  # touches the filesystem (tmp_path) + optional-dependency libs


@pytest.fixture
def mgr():
    return ExporterManager()


@pytest.fixture
def small_mesh():
    # A single triangle - vertices (N,3) + one face (M,3)
    vertices = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    faces = np.array([[0, 1, 2]])
    return vertices, faces


def test_ex_t1_numpy_export_round_trip(mgr, tmp_path):
    mask = np.zeros((5, 5, 5), dtype=np.uint8)
    mask[1:3, 1:3, 1:3] = 255
    path = str(tmp_path / "mask.npy")
    ok = mgr.export_mask_numpy(mask, path)
    assert ok is True

    loaded = np.load(path)
    assert np.array_equal(loaded, mask)
    assert loaded.dtype == np.uint8


def test_ex_t2_nifti_export_round_trip_if_nibabel_available(mgr, tmp_path):
    nib = pytest.importorskip("nibabel", reason="NIfTI export requires nibabel")
    mask = np.zeros((4, 4, 4), dtype=np.uint8)
    mask[1:3, 1:3, 1:3] = 255
    path = str(tmp_path / "mask.nii.gz")
    ok = mgr.export_mask_nifti(mask, path, spacing=(1.0, 1.0, 1.0))
    assert ok is True

    img = nib.load(path)
    data = np.asarray(img.dataobj)
    assert data.shape == mask.shape
    assert np.array_equal(data.astype(np.uint8), mask)


def test_ex_t3_nrrd_export_skipped_when_pynrrd_missing(mgr, tmp_path):
    """Must SKIP (not FAIL the suite) when the optional pynrrd
    dependency is absent - never let an optional dependency break the
    core automated regression."""
    pytest.importorskip("nrrd", reason="pynrrd not installed - NRRD export is optional")
    mask = np.zeros((3, 3, 3), dtype=np.uint8)
    path = str(tmp_path / "mask.nrrd")
    ok = mgr.export_mask_nrrd(mask, path, spacing=(1.0, 1.0, 1.0))
    assert ok is True


def test_ex_t3b_nrrd_export_without_pynrrd_returns_false_not_raise(mgr, tmp_path):
    """When pynrrd genuinely isn't installed in this environment, the
    real export function must fail soft (return False + print), never
    raise - confirmed directly rather than skipped, since this exercises
    the real ImportError branch."""
    try:
        import nrrd  # noqa: F401

        pytest.skip("pynrrd IS installed in this environment - this test targets the missing-dependency branch")
    except ImportError:
        pass
    mask = np.zeros((3, 3, 3), dtype=np.uint8)
    path = str(tmp_path / "mask.nrrd")
    ok = mgr.export_mask_nrrd(mask, path, spacing=(1.0, 1.0, 1.0))
    assert ok is False


def test_ex_t4_surface_vtk_export_round_trip(mgr, small_mesh, tmp_path):
    vertices, faces = small_mesh
    path = str(tmp_path / "mesh.vtk")
    ok = mgr.export_surface_vtk(vertices, faces, path)
    assert ok is True

    from vtkmodules.vtkIOLegacy import vtkPolyDataReader

    reader = vtkPolyDataReader()
    reader.SetFileName(path)
    reader.Update()
    polydata = reader.GetOutput()
    assert polydata.GetNumberOfPoints() == 3
    assert polydata.GetNumberOfCells() == 1


def test_surface_stl_export_round_trip(mgr, small_mesh, tmp_path):
    vertices, faces = small_mesh
    path = str(tmp_path / "mesh.stl")
    ok = mgr.export_surface_stl(vertices, faces, path, binary=True)
    assert ok is True

    from vtkmodules.vtkIOGeometry import vtkSTLReader

    reader = vtkSTLReader()
    reader.SetFileName(path)
    reader.Update()
    polydata = reader.GetOutput()
    assert polydata.GetNumberOfPoints() == 3
    assert polydata.GetNumberOfCells() == 1


def test_surface_ply_export_contains_expected_counts(mgr, small_mesh, tmp_path):
    vertices, faces = small_mesh
    path = str(tmp_path / "mesh.ply")
    ok = mgr.export_surface_ply(vertices, faces, path)
    assert ok is True
    content = (tmp_path / "mesh.ply").read_text()
    assert "element vertex 3" in content
    assert "element face 1" in content


def test_surface_obj_export_contains_vertices_and_faces(mgr, small_mesh, tmp_path):
    vertices, faces = small_mesh
    path = str(tmp_path / "mesh.obj")
    ok = mgr.export_surface_obj(vertices, faces, path)
    assert ok is True
    content = (tmp_path / "mesh.obj").read_text()
    assert content.count("\nv ") + content.startswith("v ") >= 1  # at least the vertex lines exist
    assert "f 1 2 3" in content  # faces are 1-indexed in OBJ


def test_get_supported_formats_lists_expected_extensions(mgr):
    formats = mgr.get_supported_formats()
    assert ".npy" in formats["mask"]
    assert ".stl" in formats["surface"]
    assert ".png" in formats["image"]


# ---------------------------------------------------------------------
# NRRD dependency/UI clarity (Phase 12, CT3D_P12_QUANTITATIVE_VALIDATION
# Section VI): the "Export Mask -> NRRD" option must never imply NRRD is
# guaranteed to work when `pynrrd` isn't installed - the dropdown label/
# tooltip must say so, and clicking Export must fail fast with a clear
# message rather than only after the user has already picked a filename.
# ---------------------------------------------------------------------

def test_is_nrrd_available_matches_real_import_state():
    from plugins.roi_viewer.gui.export_panel import _is_nrrd_available

    try:
        import nrrd  # noqa: F401

        really_available = True
    except ImportError:
        really_available = False
    assert _is_nrrd_available() is really_available


def test_export_panel_nrrd_dropdown_reflects_availability(wx_app):
    """
    Real ExportPanel construction (no controller behavior needed for
    _init_ui - only the dropdown/tooltip logic runs at construction
    time), against a real wx.Frame parent under the session's real
    wx.App. Does not assume pynrrd's presence/absence - asserts whichever
    state is real in this environment is reflected correctly.
    """
    import wx

    from plugins.roi_viewer.gui.export_panel import ExportPanel, _is_nrrd_available

    frame = wx.Frame(None)
    try:
        panel = ExportPanel(frame, controller=object())
        label = panel.choice_mask_format.GetString(1)  # index 1 = NRRD, per the dropdown's fixed order
        assert "NRRD" in label
        if _is_nrrd_available():
            assert "not installed" not in label
            assert panel._nrrd_available is True
        else:
            assert "not installed" in label
            assert panel._nrrd_available is False
            assert panel.choice_mask_format.GetToolTipText()  # non-empty tooltip explaining why
    finally:
        frame.Destroy()
