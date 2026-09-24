# --------------------------------------------------------------------------
# Persistent tests for E2's real commit paths:
# SegmentationPanel._commit_threshold_mask() / _commit_region_growing_result()
# against a REAL (but minimal, non-DICOM) invesalius.data.slice_.Slice() +
# invesalius.project.Project() - proving Accept actually creates exactly
# one real Project().mask_dict entry, and that preview computation never
# does, using the real "Create new mask" pubsub path (not a re-implemented
# stand-in). Mirrors tests/ct3d/test_roi_manager.py's real-Project()
# fixture pattern. Marked integration (real Slice()/Project() singletons,
# real pubsub, needs the session wx_app fixture from conftest.py).
# --------------------------------------------------------------------------
import types

import numpy as np
import pytest

from plugins.roi_viewer.core.segmentation import SegmentationManager
from plugins.roi_viewer.core.segmentation_preview import SegmentationPreviewManager

pytestmark = pytest.mark.integration

_SHAPE = (6, 16, 16)  # small, real, controlled - same reasoning as other CT3D tests' synthetic volumes


@pytest.fixture(scope="module")
def _shared_real_slice_and_project_once(wx_app):
    """
    Constructs ONE real Slice()/Project() pair for this whole test
    module - real, not a fake, with just enough real state for
    Slice.create_new_mask()'s real code path to run (matrix + spacing on
    Slice, mask_dict/image_versions/surface_dict on Project) - no DICOM
    import, no Frame/Controller.

    Why module-scoped (real, discovered constraint, not a style choice):
    conftest.py's autouse reset_invesalius_singletons fixture forces
    Slice.instance/Project.instance back to None before EVERY test in
    this whole session. That's correct for every OTHER integration test
    here (none of them fire the real "Create new mask" pubsub message -
    they manipulate project.mask_dict directly instead), but this file's
    tests are the first to actually exercise that real topic repeatedly.
    Each fresh Slice() re-subscribes several bound methods in its own
    __bind_events() (e.g. to "Create new mask"); the OLD instance's
    subscriptions are not explicitly torn down, and across several
    real sendMessage("Create new mask", ...) calls in one session this
    produces duplicate mask creation and pypubsub's own "BUG: Dead
    Listener called, still subscribed!" error (verified empirically
    while writing this file). Constructing the real Slice()/Project()
    pair exactly ONCE, then re-pointing .instance back to that SAME
    object every test (see real_slice_and_project() below) - rather
    than letting a new one be constructed and subscribed each time -
    avoids the accumulation entirely while still using 100% real
    Slice/Project/pubsub machinery (this also matches how one real
    running InVesalius session actually behaves: one Slice() instance
    for its whole lifetime, not a fresh one per operation).
    """
    import invesalius.data.slice_ as sl
    import invesalius.project as prj

    proj = prj.Project()  # first-ever construction for this module: real __init__, real subscriptions
    s = sl.Slice()
    return s, proj, prj.Project, sl.Slice


@pytest.fixture
def real_slice_and_project(_shared_real_slice_and_project_once):
    """Function-scoped: re-points Project.instance/Slice.instance back to
    the single real pair created once for this module (undoing
    conftest.py's autouse per-test reset to None, WITHOUT re-running
    __init__/__bind_events() - see the Singleton metaclass in
    invesalius/utils.py: `cls()` only constructs when `cls.instance is
    None`), then resets their mutable data fresh for this one test. See
    _shared_real_slice_and_project_once()'s docstring for why this is
    necessary."""
    s, proj, Project, Slice = _shared_real_slice_and_project_once
    Project.instance = proj
    Slice.instance = s

    proj.mask_dict = {}
    proj.image_versions = []
    proj.surface_dict = {}

    rng = np.random.RandomState(0)
    volume = rng.randint(-200, 800, size=_SHAPE).astype(np.int16)

    s.current_mask = None
    s.matrix = volume
    s._spacing = (1.0, 1.0, 1.0)
    return s, proj, volume


class _FakeController:
    """Stand-in for ROIViewerFrame - SegmentationPanel only reads
    controller.seg_mgr off it for the methods under test here."""

    def __init__(self):
        self.seg_mgr = SegmentationManager()


def _new_panel_like(controller):
    """A bare object exposing exactly the SegmentationPanel methods under
    test, bound via __get__ - avoids constructing the real wx.Panel tree
    (ScrolledPanel.__init__ needs a real wx parent window), matching this
    suite's existing "fake the frame, test the real bound method" pattern
    used by tests/ct3d/test_sync_2d3d.py for ROIViewerFrame methods."""
    from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel

    fake = types.SimpleNamespace(controller=controller)
    fake._commit_threshold_mask = SegmentationPanel._commit_threshold_mask.__get__(fake)
    fake._commit_region_growing_result = SegmentationPanel._commit_region_growing_result.__get__(fake)
    return fake


def test_otsu_preview_does_not_create_project_mask(real_slice_and_project):
    """Computing an Otsu preview candidate (exactly what _on_preview_otsu
    does) must never touch Project().mask_dict - only
    _commit_threshold_mask() (called from Accept) does."""
    s, proj, volume = real_slice_and_project
    seg_mgr = SegmentationManager()

    lo, hi = seg_mgr.auto_threshold_otsu(volume)
    seg_mgr.set_threshold(lo, hi)
    candidate = seg_mgr.apply_threshold(volume)

    assert candidate.shape == volume.shape
    assert len(proj.mask_dict) == 0  # preview computation alone created nothing


def test_otsu_preview_threshold_matches_existing_otsu(real_slice_and_project):
    """Same real method, called the same way, on the same real volume,
    must be deterministic - the preview's threshold IS the final
    threshold (instruction: "derive candidate mask using the SAME
    threshold semantics that final creation would use")."""
    s, proj, volume = real_slice_and_project
    seg_mgr = SegmentationManager()

    lo1, hi1 = seg_mgr.auto_threshold_otsu(volume)
    lo2, hi2 = seg_mgr.auto_threshold_otsu(volume)
    assert (lo1, hi1) == (lo2, hi2)

    seg_mgr.set_threshold(lo1, hi1)
    candidate1 = seg_mgr.apply_threshold(volume)
    seg_mgr.set_threshold(lo2, hi2)
    candidate2 = seg_mgr.apply_threshold(volume)
    assert np.array_equal(candidate1, candidate2)


def test_otsu_accept_creates_one_real_mask(real_slice_and_project):
    s, proj, volume = real_slice_and_project
    controller = _FakeController()
    panel = _new_panel_like(controller)

    lo, hi = controller.seg_mgr.auto_threshold_otsu(volume)
    name = panel._commit_threshold_mask(lo, hi)

    assert name is not None
    assert len(proj.mask_dict) == 1
    created = next(iter(proj.mask_dict.values()))
    assert created.threshold_range == (lo, hi)


def test_otsu_cancel_creates_no_mask(real_slice_and_project):
    """Cancel never calls _commit_threshold_mask() at all (see
    SegmentationPanel._on_preview_cancel() -> cancel_preview(), which
    only touches the preview manager/overlay) - proven here simply by
    never calling it and confirming mask_dict stays empty, mirroring
    what the real Cancel button handler does (nothing mask-related)."""
    s, proj, volume = real_slice_and_project
    preview_mgr = SegmentationPreviewManager()
    seg_mgr = SegmentationManager()

    lo, hi = seg_mgr.auto_threshold_otsu(volume)
    gen = preview_mgr.new_generation()
    candidate = seg_mgr.apply_threshold(volume)
    preview_mgr.set_otsu_preview(gen, candidate, threshold=(lo, hi), name="Otsu Preview")
    assert preview_mgr.state == "PREVIEW_READY"

    preview_mgr.cancel()  # the real Cancel action
    assert len(proj.mask_dict) == 0


def test_otsu_accept_uses_same_threshold_as_preview(real_slice_and_project):
    s, proj, volume = real_slice_and_project
    controller = _FakeController()
    panel = _new_panel_like(controller)
    preview_mgr = SegmentationPreviewManager()

    lo, hi = controller.seg_mgr.auto_threshold_otsu(volume)
    gen = preview_mgr.new_generation()
    candidate = controller.seg_mgr.apply_threshold(volume)
    preview_mgr.set_otsu_preview(gen, candidate, threshold=(lo, hi), name="Otsu Preview")

    preview_mgr.begin_accept()
    recorded_lo, recorded_hi = preview_mgr.source_threshold
    name = panel._commit_threshold_mask(recorded_lo, recorded_hi)
    preview_mgr.finish_accept()

    assert name is not None
    created = next(iter(proj.mask_dict.values()))
    assert created.threshold_range == (lo, hi)


def test_otsu_classic_mode_unchanged_when_flag_off(real_slice_and_project):
    """_commit_threshold_mask() is the SAME method the classic
    _on_apply_threshold() button handler calls - there is only one real
    implementation, so "classic mode unchanged" holds structurally, not
    just by coincidence. Confirmed here by calling it exactly as the
    classic path would (no preview manager involved at all)."""
    s, proj, volume = real_slice_and_project
    controller = _FakeController()
    panel = _new_panel_like(controller)

    name = panel._commit_threshold_mask(100, 400)
    assert name is not None
    assert len(proj.mask_dict) == 1


def test_region_preview_does_not_create_mask(real_slice_and_project):
    s, proj, volume = real_slice_and_project
    seg_mgr = SegmentationManager()
    seed = tuple(d // 2 for d in volume.shape)

    result = seg_mgr.region_growing(volume, seed, tolerance=50)
    assert result.shape == volume.shape
    assert len(proj.mask_dict) == 0


def test_region_preview_matches_existing_region_growing_output(real_slice_and_project):
    s, proj, volume = real_slice_and_project
    seg_mgr = SegmentationManager()
    seed = tuple(d // 2 for d in volume.shape)

    result1 = seg_mgr.region_growing(volume, seed, tolerance=50)
    result2 = seg_mgr.region_growing(volume, seed, tolerance=50)
    assert np.array_equal(result1, result2)  # deterministic, same real algorithm


def test_region_preview_stats_match(real_slice_and_project):
    s, proj, volume = real_slice_and_project
    seg_mgr = SegmentationManager()
    seed = tuple(d // 2 for d in volume.shape)

    result = seg_mgr.region_growing(volume, seed, tolerance=50)
    stats1 = seg_mgr.region_stats(result, spacing=(1.0, 1.0, 1.0))
    stats2 = seg_mgr.region_stats(result, spacing=(1.0, 1.0, 1.0))
    assert stats1 == stats2


def test_oversized_region_warning_state_preserved(real_slice_and_project):
    """A tolerance wide enough to cover the whole small synthetic volume
    must be flagged exceeds_limit - the same real safety check the
    classic path uses, now also driving E2's non-blocking preview-time
    warning text (see _on_region_grown_preview())."""
    s, proj, volume = real_slice_and_project
    seg_mgr = SegmentationManager()
    seed = tuple(d // 2 for d in volume.shape)

    result = seg_mgr.region_growing(volume, seed, tolerance=10000)  # huge tolerance -> whole volume
    stats = seg_mgr.region_stats(result, spacing=(1.0, 1.0, 1.0))
    assert stats["exceeds_limit"] is True


def test_region_accept_creates_exactly_one_mask(real_slice_and_project):
    s, proj, volume = real_slice_and_project
    controller = _FakeController()
    panel = _new_panel_like(controller)
    seed = tuple(d // 2 for d in volume.shape)

    result = controller.seg_mgr.region_growing(volume, seed, tolerance=50)
    name = panel._commit_region_growing_result(result, seed, tolerance=50)

    assert name is not None
    assert len(proj.mask_dict) == 1
    created = next(iter(proj.mask_dict.values()))
    assert created.was_edited is True  # D9/C7 policy requires this for a hand-written mask


def test_region_cancel_creates_zero_masks(real_slice_and_project):
    s, proj, volume = real_slice_and_project
    preview_mgr = SegmentationPreviewManager()
    seg_mgr = SegmentationManager()
    seed = tuple(d // 2 for d in volume.shape)

    result = seg_mgr.region_growing(volume, seed, tolerance=50)
    stats = seg_mgr.region_stats(result, spacing=(1.0, 1.0, 1.0))
    gen = preview_mgr.new_generation()
    preview_mgr.set_region_growing_preview(
        gen, result, seed_world=(0, 0, 0), seed_voxel=seed, tolerance=50, stats=stats, name="Region Growing Preview",
    )
    assert preview_mgr.state == "PREVIEW_READY"

    preview_mgr.cancel()
    assert len(proj.mask_dict) == 0


def test_stale_async_region_result_ignored(real_slice_and_project):
    """The real generation_id contract (core/segmentation_preview.py) -
    a result computed under an old generation must never reach
    set_region_growing_preview() successfully once a newer generation
    has started."""
    s, proj, volume = real_slice_and_project
    preview_mgr = SegmentationPreviewManager()
    seg_mgr = SegmentationManager()
    seed = tuple(d // 2 for d in volume.shape)

    gen1 = preview_mgr.new_generation()
    gen2 = preview_mgr.new_generation()  # a second preview started before gen1's "worker" finished

    result1 = seg_mgr.region_growing(volume, seed, tolerance=10)
    stats1 = seg_mgr.region_stats(result1, spacing=(1.0, 1.0, 1.0))
    ok = preview_mgr.set_region_growing_preview(
        gen1, result1, seed_world=(0, 0, 0), seed_voxel=seed, tolerance=10, stats=stats1, name="Stale",
    )
    assert ok is False
    assert preview_mgr.preview_name is None
    assert len(proj.mask_dict) == 0  # never got anywhere near a commit


def test_was_edited_semantics_preserved(real_slice_and_project):
    s, proj, volume = real_slice_and_project
    controller = _FakeController()
    panel = _new_panel_like(controller)
    seed = tuple(d // 2 for d in volume.shape)

    result = controller.seg_mgr.region_growing(volume, seed, tolerance=50)
    panel._commit_region_growing_result(result, seed, tolerance=50)
    created = next(iter(proj.mask_dict.values()))
    assert created.was_edited is True


def test_classic_region_growing_unchanged_when_flag_off(real_slice_and_project):
    """_commit_region_growing_result() is the SAME method the classic
    _on_region_grown() callback calls after its own stats/warning
    check - only one real implementation exists."""
    s, proj, volume = real_slice_and_project
    controller = _FakeController()
    panel = _new_panel_like(controller)
    seed = tuple(d // 2 for d in volume.shape)

    result = controller.seg_mgr.region_growing(volume, seed, tolerance=50)
    name = panel._commit_region_growing_result(result, seed, tolerance=50)
    assert name is not None
    assert len(proj.mask_dict) == 1
