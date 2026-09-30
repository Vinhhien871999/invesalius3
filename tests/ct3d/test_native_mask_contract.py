# --------------------------------------------------------------------------
# Native mask read/write contract (30/09/2026) - see
# plugins/roi_viewer/core/native_mask.py.
#
# Three real defects, each reproduced here through the plugin's own
# handlers on a real Slice()/Project() with real native mask creation:
#
# 1. A committed candidate (Region Growing; also E2 Accept and E6 Accept,
#    which share the commit) lost voxels the first time a 2D view showed a
#    coronal/sagittal slice: only the axial "computed" flags were set, so
#    get_mask_slice() re-thresholded that plane with the (1, 1) placeholder.
#    Slices a view thresholded during mask creation also kept stray (1, 1)
#    voxels.
# 2. Whole-mask reads (E3 cleanup, E4 Current ROI, Measure Volume,
#    NumPy/NRRD export) skipped the native do_threshold_to_all_slices()
#    step, so a threshold mask read as empty wherever no view had been yet
#    - and E3 then wrote that partial mask back as final.
# 3. Those reads used "!= 0", so brush-erased voxels (native value 1) were
#    foreground - E3 even turned them back into mask.
#
# The "view" helpers below call Slice.get_mask_slice() exactly as the 2D
# viewer does when it shows a slice.
# --------------------------------------------------------------------------
import types

import numpy as np
import pytest
from scipy import ndimage

pytestmark = pytest.mark.integration

_SHAPE = (6, 16, 16)  # (z, y, x)
_LO, _HI = 200, 400


def _volume():
    v = np.zeros(_SHAPE, dtype=np.int16)
    v[1:5, 2:10, 2:10] = 300  # large blob
    v[1:3, 12:14, 12:14] = 300  # small blob
    return v


@pytest.fixture
def env(real_slice_and_project_singleton):
    s, proj, Project, Slice = real_slice_and_project_singleton
    Project.instance, Slice.instance = proj, s
    proj.mask_dict = {}
    proj.image_versions = []
    proj.surface_dict = {}
    s.current_mask = None
    s.matrix = _volume()
    s._spacing = (0.5, 0.8, 2.0)
    # What "Load project data" does in the app: ProjectInterface (a
    # singleton) re-reads shape/spacing - otherwise it keeps an earlier test's.
    from plugins.roi_viewer.interface.project_interface import ProjectInterface

    ProjectInterface()._refresh_project_data()
    _reset_buffers(s)
    return s, proj


def _reset_buffers(s):
    for buffer in s.buffer_slices.values():
        buffer.index = -1
        buffer.discard_mask()
        buffer.discard_vtk_mask()


def _show_slice(s, orientation, index):
    """What the 2D viewer does when it displays this slice."""
    s.buffer_slices[orientation].index = -1
    s.buffer_slices[orientation].discard_mask()
    s.get_mask_slice(orientation, index)


def _show_every_slice(s):
    nz, ny, nx = _SHAPE
    for orientation, n in (("AXIAL", nz), ("CORONAL", ny), ("SAGITAL", nx)):
        for k in range(n):
            _show_slice(s, orientation, k)


def _threshold_mask(s):
    """A real native threshold mask, lazily computed like in the GUI."""
    from invesalius.pubsub import pub as Publisher

    Publisher.sendMessage("Create new mask", mask_name="Threshold", thresh=(_LO, _HI), colour=(1.0, 0.0, 0.0))
    return s.current_mask


def _threshold_fg():
    v = _volume()
    return (v >= _LO) & (v <= _HI)


def _largest(fg):
    labels, n = ndimage.label(fg, structure=ndimage.generate_binary_structure(3, 3))
    sizes = ndimage.sum(fg, labels, range(1, n + 1))
    return labels == (int(np.argmax(sizes)) + 1)


def _seg_panel(controller):
    from plugins.roi_viewer.core.segmentation_preview import SegmentationPreviewManager
    from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel

    fake = types.SimpleNamespace(controller=controller, preview_mgr=SegmentationPreviewManager())
    for name in ("_commit_region_growing_result", "_run_cleanup", "_current_mask", "_roi_locked_for_mask",
                 "_select_preview_3d_source"):
        setattr(fake, name, getattr(SegmentationPanel, name).__get__(fake))
    fake._refresh_after_edit = lambda: None
    fake.lbl_cleanup_status = types.SimpleNamespace(SetLabel=lambda *a, **k: None)
    return fake


def _controller():
    from plugins.roi_viewer.core.mask_editor import MaskEditorManager
    from plugins.roi_viewer.core.roi_manager import ROIManager
    from plugins.roi_viewer.core.segmentation import SegmentationManager

    roi_mgr = ROIManager()
    roi_mgr.rebuild_from_project_masks()
    return types.SimpleNamespace(roi_mgr=roi_mgr, mask_mgr=MaskEditorManager(), seg_mgr=SegmentationManager())


def _logical(mask):
    return np.asarray(mask.matrix[1:, 1:, 1:]) > 127


# ------------------------------------------------------------------
# 1. Commit (Region Growing / E2 Accept / E6 Accept)
# ------------------------------------------------------------------

def test_committed_region_survives_first_view_of_every_slice(env):
    s, proj = env
    region = np.zeros(_SHAPE, dtype=np.uint8)
    region[1:5, 3:12, 4:10] = 1
    name = _seg_panel(_controller())._commit_region_growing_result(region, (2, 5, 5), 10)
    assert name is not None
    mask = s.current_mask
    _show_every_slice(s)
    assert np.array_equal(_logical(mask), region > 0)


def test_commit_is_exact_when_views_threshold_during_creation(env):
    """A real viewer shows the new mask while it is being created ("Update
    slice viewer"), thresholding the shown slices with the (1, 1)
    placeholder. Voxels equal to 1 there must not leak into the commit."""
    from invesalius.pubsub import pub as Publisher

    s, proj = env
    s.matrix[0, 0:3, 0:3] = 1
    region = np.zeros(_SHAPE, dtype=np.uint8)
    region[2:4, 5:9, 5:9] = 1

    def viewer(**kwargs):
        for orientation in ("AXIAL", "CORONAL", "SAGITAL"):
            _show_slice(s, orientation, 0)

    Publisher.subscribe(viewer, "Update slice viewer")
    try:
        _seg_panel(_controller())._commit_region_growing_result(region, (2, 6, 6), 10)
    finally:
        Publisher.unsubscribe(viewer, "Update slice viewer")
    assert np.array_equal(_logical(s.current_mask), region > 0)


# ------------------------------------------------------------------
# 2 + 3. Whole-mask reads
# ------------------------------------------------------------------

def test_cleanup_on_lazily_computed_threshold_mask_uses_whole_mask(env):
    from plugins.roi_viewer.core import segmentation_cleanup

    s, proj = env
    mask = _threshold_mask(s)
    _show_slice(s, "AXIAL", 2)  # the only slice a view has shown
    panel = _seg_panel(_controller())
    panel._run_cleanup(lambda r: segmentation_cleanup.keep_largest_component(r), "Keep largest")
    _show_every_slice(s)
    assert np.array_equal(_logical(mask), _largest(_threshold_fg()))


def test_cleanup_keeps_brush_erasures(env):
    from plugins.roi_viewer.core import segmentation_cleanup

    s, proj = env
    mask = _threshold_mask(s)
    s.do_threshold_to_all_slices(mask)
    mask.matrix[1 + 2, 1 + 5, 1 + 2:1 + 10] = 1  # brush Erase writes 1
    expected = _largest(_threshold_fg())
    expected[2, 5, 2:10] = False
    panel = _seg_panel(_controller())
    panel._run_cleanup(lambda r: segmentation_cleanup.keep_largest_component(r), "Keep largest")
    assert np.array_equal(_logical(mask), expected)


def test_e4_current_roi_reads_whole_mask_without_erasures(env):
    s, proj = env
    mask = _threshold_mask(s)
    _show_slice(s, "AXIAL", 2)
    mask.matrix[1 + 2, 1 + 5, 1 + 5] = 1  # erased on the shown slice
    expected = _threshold_fg()
    expected[2, 5, 5] = False
    array, spacing, kind = _seg_panel(_controller())._select_preview_3d_source()
    assert kind == "current_roi"
    assert np.array_equal(np.asarray(array) != 0, expected)


def test_measure_volume_counts_whole_mask_without_erasures(env):
    from plugins.roi_viewer.core.measurement import MeasurementManager
    from plugins.roi_viewer.gui.measurement_panel import MeasurementPanel

    s, proj = env
    mask = _threshold_mask(s)
    _show_slice(s, "AXIAL", 2)
    mask.matrix[1 + 2, 1 + 5, 1 + 5] = 1
    recorded = []
    fake = types.SimpleNamespace(
        controller=types.SimpleNamespace(measure_mgr=MeasurementManager()),
        txt_volume=types.SimpleNamespace(SetValue=lambda *a: None),
        add_measurement=lambda name, value, unit: recorded.append(value),
    )
    MeasurementPanel._on_measure_volume.__get__(fake)(None)
    expected_voxels = int(_threshold_fg().sum()) - 1
    assert recorded and recorded[-1] == pytest.approx(expected_voxels * 0.5 * 0.8 * 2.0)


def test_numpy_export_writes_whole_mask_without_erasures(env, tmp_path):
    from plugins.roi_viewer.core.exporters import ExporterManager
    from plugins.roi_viewer.gui.export_panel import ExportPanel

    s, proj = env
    mask = _threshold_mask(s)
    _show_slice(s, "AXIAL", 2)
    mask.matrix[1 + 2, 1 + 5, 1 + 5] = 1
    expected = _threshold_fg()
    expected[2, 5, 5] = False
    fake = types.SimpleNamespace(controller=types.SimpleNamespace(exporter=ExporterManager()))
    path = str(tmp_path / "mask.npy")
    ExportPanel._export_mask_via_exporter.__get__(fake)(mask, 2, path)
    assert np.array_equal(np.load(path) != 0, expected)


# ------------------------------------------------------------------
# core/native_mask.py itself
# ------------------------------------------------------------------

def test_write_marks_every_slice_and_discards_view_buffers(env):
    from plugins.roi_viewer.core import native_mask

    s, proj = env
    mask = _threshold_mask(s)
    s.buffer_slices["AXIAL"].mask = np.zeros((16, 16), dtype=np.uint8)  # a cached slice
    fg = np.zeros(_SHAPE, dtype=bool)
    fg[1, 1, 1] = True
    native_mask.write_logical_region(s, mask, fg)
    assert (np.asarray(mask.matrix[0]) == 1).all()
    assert (np.asarray(mask.matrix[:, 0, :]) == 1).all()
    assert (np.asarray(mask.matrix[:, :, 0]) == 1).all()
    assert s.buffer_slices["AXIAL"].mask is None
    assert mask.was_edited is True
    assert set(np.unique(np.asarray(mask.matrix[1:, 1:, 1:]))) == {0, 255}


def test_commit_rejects_wrong_shape_before_creating_a_mask(env):
    from plugins.roi_viewer.core import native_mask

    s, proj = env
    with pytest.raises(ValueError):
        native_mask.commit_preview_array_to_new_mask(np.ones((2, 2, 2), dtype=bool), "Bad", (1.0, 0.0, 0.0))
    assert len(proj.mask_dict) == 0


def test_logical_foreground_matches_what_the_views_colour(env):
    """0/1/2 are transparent in the native mask colour table, 253-255
    coloured; the binary surface is contoured at 127."""
    from plugins.roi_viewer.core import native_mask

    s, proj = env
    mask = _threshold_mask(s)
    s.do_threshold_to_all_slices(mask)
    interior = mask.matrix[1:, 1:, 1:]
    interior[0, 0, 0:6] = (0, 1, 2, 253, 254, 255)
    fg = native_mask.logical_foreground(s, mask)
    assert fg[0, 0, 0:6].tolist() == [False, False, False, True, True, True]
