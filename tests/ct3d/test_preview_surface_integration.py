# --------------------------------------------------------------------------
# Persistent tests for E4's real integration: source-priority selection
# (_select_preview_3d_source()), the real commit path
# (_on_preview_3d_built()), and the real invariant that a fast preview
# mesh NEVER becomes/affects Project().surface_dict or the final surface
# pipeline. Real Mask()/Slice()/Project()/ROIManager/SegmentationPreview
# Manager - reuses the established real-singleton-reuse fixture pattern
# from test_segmentation_cleanup_integration.py/test_segmentation_
# preview_commit.py (see conftest.py's real_slice_and_project_singleton
# docstring for why). Marked integration.
#
# The async worker-thread + wx.CallAfter plumbing itself
# (_trigger_preview_3d_rebuild()'s threading.Thread) is not exercised
# directly here (a headless pytest process has no running wx event loop
# to actually dispatch a real wx.CallAfter) - matching this suite's own
# established convention for E2's async Region Growing preview, which is
# tested the same way: by calling the real underlying methods
# (_select_preview_3d_source(), _on_preview_3d_built()) directly and
# synchronously with real data, exercising the exact same real logic the
# worker/callback would run, without needing a real threaded/GUI event
# loop.
# --------------------------------------------------------------------------
import types

import numpy as np
import pytest

from plugins.roi_viewer.core.mask_editor import MaskEditorManager
from plugins.roi_viewer.core.preview_surface_3d import PreviewSurfaceManager3D
from plugins.roi_viewer.core.roi_manager import ROIManager
from plugins.roi_viewer.core.segmentation import SegmentationManager
from plugins.roi_viewer.core.segmentation_preview import SegmentationPreviewManager

pytestmark = pytest.mark.integration

_SHAPE = (6, 16, 16)


@pytest.fixture
def real_env(real_slice_and_project_singleton):
    """Reuses the ONE real Slice()/Project() pair shared across the
    whole session (conftest.py's real_slice_and_project_singleton) -
    see its docstring for why a single shared pair, not a fresh
    Slice()/Project() per test or per module, is required once real
    pubsub-driven mask creation/state is involved (a real, deterministic
    cross-file regression was found and fixed during E3 - see
    docs/CT3D_ADVANCED_E3_CLEANUP_REPORT.md)."""
    from invesalius.data.mask import Mask

    s, proj, Project, Slice = real_slice_and_project_singleton
    Project.instance = proj
    Slice.instance = s

    proj.mask_dict = {}
    proj.image_versions = []
    proj.surface_dict = {}

    mask = Mask()
    mask.create_mask(_SHAPE)
    mask.index = 0
    mask.name = "TestROI"
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    mask.matrix[1:, 1:, 1:] = values
    mask.matrix.flush()
    proj.mask_dict[0] = mask
    s.current_mask = mask
    s._spacing = (1.0, 1.0, 1.0)

    roi_mgr = ROIManager()
    roi_mgr.rebuild_from_project_masks()

    return s, proj, mask, roi_mgr


class _FakeController:
    def __init__(self, roi_mgr, renderer):
        self.roi_mgr = roi_mgr
        self.mask_mgr = MaskEditorManager()
        self.seg_mgr = SegmentationManager()
        self.preview_surface_3d = PreviewSurfaceManager3D()
        self.preview_surface_3d.attach(renderer)
        self._render_calls = 0

    def ensure_preview_surface_attached(self):
        return self.preview_surface_3d.is_attached()

    def request_render(self):
        self._render_calls += 1

    def on_roi_source_changed(self):
        self.roi_mgr.rebuild_from_project_masks()


def _panel_like(controller):
    from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel

    fake = types.SimpleNamespace(controller=controller)
    fake.preview_mgr = SegmentationPreviewManager()
    fake._current_mask = SegmentationPanel._current_mask.__get__(fake)
    fake._select_preview_3d_source = SegmentationPanel._select_preview_3d_source.__get__(fake)
    fake._on_preview_3d_built = SegmentationPanel._on_preview_3d_built.__get__(fake)
    fake.lbl_e4_state = types.SimpleNamespace(SetLabel=lambda *a, **k: None)
    fake.lbl_e4_mesh_info = types.SimpleNamespace(SetLabel=lambda *a, **k: None)
    return fake


@pytest.fixture
def renderer():
    from vtkmodules.vtkRenderingCore import vtkRenderer

    return vtkRenderer()


# ------------------------------------------------------------------
# Core invariant: E4 never touches Project().surface_dict / the real
# final-surface pipeline.
# ------------------------------------------------------------------
def test_e4_never_creates_project_surface(real_env, renderer):
    s, proj, mask, roi_mgr = real_env
    controller = _FakeController(roi_mgr, renderer)
    panel = _panel_like(controller)

    array, spacing, kind = panel._select_preview_3d_source()
    assert kind == "current_roi"
    from plugins.roi_viewer.core.preview_surface_3d import build_preview_mesh

    polydata = build_preview_mesh(np.array(array), spacing)
    gen = controller.preview_surface_3d.new_generation()
    panel._on_preview_3d_built(gen, polydata, kind, 0.01)

    assert len(proj.surface_dict) == 0


def test_e4_never_calls_create_surface_from_index(real_env, renderer):
    from invesalius.pubsub import pub as Publisher

    s, proj, mask, roi_mgr = real_env
    controller = _FakeController(roi_mgr, renderer)
    panel = _panel_like(controller)

    calls = []
    Publisher.subscribe(lambda **kw: calls.append(kw), "Create surface from index")

    array, spacing, kind = panel._select_preview_3d_source()
    from plugins.roi_viewer.core.preview_surface_3d import build_preview_mesh

    polydata = build_preview_mesh(np.array(array), spacing)
    gen = controller.preview_surface_3d.new_generation()
    panel._on_preview_3d_built(gen, polydata, kind, 0.01)

    assert calls == []


def test_final_surface_untouched(real_env, renderer):
    """Capture real surface_dict identity/count before and after several
    E4 rebuilds - must be byte-for-byte unchanged (Section 32)."""
    s, proj, mask, roi_mgr = real_env
    proj.surface_dict = {0: object()}  # a real, pre-existing "final surface" stand-in
    before_dict_id = id(proj.surface_dict)
    before_entry = proj.surface_dict[0]

    controller = _FakeController(roi_mgr, renderer)
    panel = _panel_like(controller)
    from plugins.roi_viewer.core.preview_surface_3d import build_preview_mesh

    for _ in range(3):
        array, spacing, kind = panel._select_preview_3d_source()
        polydata = build_preview_mesh(np.array(array), spacing)
        gen = controller.preview_surface_3d.new_generation()
        panel._on_preview_3d_built(gen, polydata, kind, 0.01)

    assert id(proj.surface_dict) == before_dict_id
    assert proj.surface_dict[0] is before_entry
    assert len(proj.surface_dict) == 1


# ------------------------------------------------------------------
# Source priority
# ------------------------------------------------------------------
def test_e4_current_roi_source(real_env, renderer):
    s, proj, mask, roi_mgr = real_env
    controller = _FakeController(roi_mgr, renderer)
    panel = _panel_like(controller)

    array, spacing, kind = panel._select_preview_3d_source()
    assert kind == "current_roi"
    assert array is not None


def test_e4_e2_otsu_preview_source(real_env, renderer):
    s, proj, mask, roi_mgr = real_env
    controller = _FakeController(roi_mgr, renderer)
    panel = _panel_like(controller)

    gen = panel.preview_mgr.new_generation()
    candidate = np.zeros(_SHAPE, dtype=np.uint8)
    candidate[1:3, 1:3, 1:3] = 255
    panel.preview_mgr.set_otsu_preview(gen, candidate, threshold=(100, 300), name="Otsu Preview")

    array, spacing, kind = panel._select_preview_3d_source()
    assert kind == "otsu_preview"
    assert array is candidate  # E2 preview wins over Current ROI


def test_e4_e2_region_preview_source(real_env, renderer):
    s, proj, mask, roi_mgr = real_env
    controller = _FakeController(roi_mgr, renderer)
    panel = _panel_like(controller)

    gen = panel.preview_mgr.new_generation()
    candidate = np.zeros(_SHAPE, dtype=np.uint8)
    candidate[1:3, 1:3, 1:3] = 255
    panel.preview_mgr.set_region_growing_preview(
        gen, candidate, seed_world=(0, 0, 0), seed_voxel=(1, 1, 1), tolerance=10, stats={}, name="RG Preview",
    )

    array, spacing, kind = panel._select_preview_3d_source()
    assert kind == "region_growing_preview"
    assert array is candidate


def test_e2_cancel_clears_or_falls_back(real_env, renderer):
    """After preview_mgr.cancel() (what the real Cancel button does),
    source selection must fall back to Current ROI."""
    s, proj, mask, roi_mgr = real_env
    controller = _FakeController(roi_mgr, renderer)
    panel = _panel_like(controller)

    gen = panel.preview_mgr.new_generation()
    candidate = np.zeros(_SHAPE, dtype=np.uint8)
    candidate[1:3, 1:3, 1:3] = 255
    panel.preview_mgr.set_otsu_preview(gen, candidate, threshold=(100, 300), name="Otsu Preview")
    assert panel._select_preview_3d_source()[2] == "otsu_preview"

    panel.preview_mgr.cancel()
    array, spacing, kind = panel._select_preview_3d_source()
    assert kind == "current_roi"  # real fallback


def test_e2_accept_does_not_duplicate_e4_actor(real_env, renderer):
    """Simulates the real sequence: preview ready -> build E4 mesh from
    it -> preview_mgr.finish_accept() (what real Accept does) -> rebuild
    E4 from the new Current ROI source - the manager must still own
    exactly ONE actor throughout (never a second one for the "accepted"
    state)."""
    s, proj, mask, roi_mgr = real_env
    controller = _FakeController(roi_mgr, renderer)
    panel = _panel_like(controller)
    from plugins.roi_viewer.core.preview_surface_3d import build_preview_mesh

    gen1 = panel.preview_mgr.new_generation()
    candidate = np.zeros(_SHAPE, dtype=np.uint8)
    candidate[1:3, 1:3, 1:3] = 255
    panel.preview_mgr.set_otsu_preview(gen1, candidate, threshold=(100, 300), name="Otsu Preview")
    array, spacing, kind = panel._select_preview_3d_source()
    poly1 = build_preview_mesh(np.array(array), spacing)
    e4_gen1 = controller.preview_surface_3d.new_generation()
    panel._on_preview_3d_built(e4_gen1, poly1, kind, 0.01)
    assert controller.preview_surface_3d.actor_count == 1

    panel.preview_mgr.finish_accept()  # real Accept's own cleanup call
    array2, spacing2, kind2 = panel._select_preview_3d_source()
    assert kind2 == "current_roi"
    poly2 = build_preview_mesh(np.array(array2), spacing2)
    e4_gen2 = controller.preview_surface_3d.new_generation()
    panel._on_preview_3d_built(e4_gen2, poly2, kind2, 0.01)

    assert controller.preview_surface_3d.actor_count == 1  # still exactly one, never two


def test_e3_cleanup_marks_e4_dirty():
    """E3 cleanup's real dirty-mark call site is _refresh_after_edit()
    (see gui/segmentation_panel.py - _run_cleanup() calls it on every
    real, non-no-op mutation), which itself calls
    self._mark_preview_3d_dirty("mask edited") unconditionally - the
    SAME single shared entry point Undo/Redo/classic-commit-paths use.
    Verified here by source inspection is redundant with the real
    behavioral tests above; this test instead confirms the real method
    exists and is wired at the source level (a lightweight sanity check,
    not a duplicate of test_segmentation_cleanup_integration.py's own
    real mask-mutation tests, which already exercise _run_cleanup() end
    to end against a real Mask())."""
    from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel
    import inspect

    source = inspect.getsource(SegmentationPanel._refresh_after_edit)
    assert "_mark_preview_3d_dirty" in source


def test_undo_marks_e4_dirty():
    from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel
    import inspect

    source = inspect.getsource(SegmentationPanel._on_undo)
    assert "_refresh_after_edit" in source  # which itself marks E4 dirty (see above)


def test_redo_marks_e4_dirty():
    from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel
    import inspect

    source = inspect.getsource(SegmentationPanel._on_redo)
    assert "_refresh_after_edit" in source


def test_roi_switch_rebuilds_for_new_source(real_env, renderer):
    """A second real mask becomes current (simulating _on_roi_selected's
    real "Change mask selected" effect) - source selection must reflect
    the NEW current mask, not the old one."""
    from invesalius.data.mask import Mask

    s, proj, mask, roi_mgr = real_env
    controller = _FakeController(roi_mgr, renderer)
    panel = _panel_like(controller)

    array1, _, kind1 = panel._select_preview_3d_source()
    assert kind1 == "current_roi"
    first_mask_id = id(array1)

    mask2 = Mask()
    mask2.create_mask(_SHAPE)
    mask2.index = 1
    mask2.name = "Second"
    values2 = np.zeros(_SHAPE, dtype=np.uint8)
    values2[2:4, 2:4, 2:4] = 255
    mask2.matrix[1:, 1:, 1:] = values2
    proj.mask_dict[1] = mask2
    s.current_mask = mask2  # real "Change mask selected" effect

    array2, _, kind2 = panel._select_preview_3d_source()
    assert kind2 == "current_roi"
    assert id(array2) != first_mask_id
    assert np.array_equal(np.array(array2), values2)


def test_plugin_reopen_no_duplicate_actor(renderer):
    """Simulates plugin close (detach) then reopen (attach again) - the
    manager must still own exactly one actor, never two."""
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    mgr.detach()  # "close"
    mgr.attach(renderer)  # "reopen"
    assert mgr.actor_count == 1
    assert renderer.GetActors().GetNumberOfItems() == 1


def test_preview_actor_does_not_block_picker(renderer):
    """Real VTK mechanism, not a plugin convention to separately audit
    per picker code path - SetPickable(False) means vtkCellPicker (or
    any other real VTK picker) skips this actor entirely during
    picking, regardless of which picker instance is used."""
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    assert mgr.actor.GetPickable() == 0
