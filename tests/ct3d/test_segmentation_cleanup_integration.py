# --------------------------------------------------------------------------
# Persistent tests for E3's real commit path:
# SegmentationPanel._run_cleanup() against a REAL invesalius.data.mask.Mask
# (real padded matrix/sentinel convention) + real Slice()/Project() +
# the real core/mask_editor.UndoRedoManager (via controller.mask_mgr) +
# E1's real ROIManager lock. Mirrors test_segmentation_preview_commit.py's
# real-singleton-reuse fixture pattern (see that file's docstring for why
# a fresh Slice()/Project() per test is unsafe once real pubsub-driven
# state is involved - this file reuses the SAME real Slice()/Project()
# pair for the same reason, defensively, even though these tests don't
# themselves fire "Create new mask"). Marked integration.
# --------------------------------------------------------------------------
import types

import numpy as np
import pytest

from plugins.roi_viewer.core.mask_editor import MaskEditorManager
from plugins.roi_viewer.core.roi_manager import ROIManager

pytestmark = pytest.mark.integration

_SHAPE = (6, 16, 16)  # small, real, controlled - matches other CT3D synthetic-volume tests


@pytest.fixture
def real_mask_env(real_slice_and_project_singleton):
    """A real Mask (real padded matrix/sentinel layout - invesalius.data.
    mask.Mask.create_mask()), attached as the real current mask of the
    ONE real Slice()/Project() pair shared across the whole session
    (conftest.py's real_slice_and_project_singleton - see its docstring
    for why a single shared pair, not a fresh Slice()/Project() per test
    or per module, is required), plus a real ROIManager/
    MaskEditorManager - everything _run_cleanup() actually touches, for
    real."""
    from invesalius.data.mask import Mask

    s, proj, Project, Slice = real_slice_and_project_singleton
    Project.instance = proj
    Slice.instance = s

    proj.mask_dict = {}
    proj.image_versions = []

    mask = Mask()
    mask.create_mask(_SHAPE)
    mask.index = 0
    mask.name = "TestROI"
    mask.was_edited = False
    proj.mask_dict[0] = mask
    s.current_mask = mask
    s._spacing = (1.0, 1.0, 1.0)

    roi_mgr = ROIManager()
    roi_mgr.rebuild_from_project_masks()

    mask_mgr = MaskEditorManager()

    return mask, roi_mgr, mask_mgr


class _FakeController:
    def __init__(self, roi_mgr, mask_mgr):
        self.roi_mgr = roi_mgr
        self.mask_mgr = mask_mgr


def _panel_like(controller):
    """Bind just the real methods under test to a bare object - same
    pattern used throughout this test suite's E1/E2 integration tests
    (avoids constructing a real wx.Panel/ScrolledPanel tree)."""
    from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel

    fake = types.SimpleNamespace(controller=controller)
    fake._run_cleanup = SegmentationPanel._run_cleanup.__get__(fake)
    fake._current_mask = SegmentationPanel._current_mask.__get__(fake)
    fake._roi_locked_for_mask = SegmentationPanel._roi_locked_for_mask.__get__(fake)
    fake._refresh_after_edit = lambda: None  # touches real pubsub only - irrelevant to what's asserted here
    fake.lbl_cleanup_status = types.SimpleNamespace(SetLabel=lambda *a, **k: None)
    return fake


def _write_region(mask, values: np.ndarray):
    """Write a real (unpadded, logical) array into the mask's real
    padded matrix interior, exactly as core/segmentation.py's own
    _commit_region_growing_result() does - the real production write
    pattern, not a shortcut."""
    mask.matrix[1:, 1:, 1:] = values
    mask.matrix.flush()


def test_cleanup_current_roi_updates_logical_region(real_mask_env):
    from plugins.roi_viewer.core import segmentation_cleanup

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    values[0, 0, 0] = 255  # size-1 speck, will be removed by Keep Largest
    _write_region(mask, values)

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    panel._run_cleanup(lambda region: segmentation_cleanup.keep_largest_component(region), "Keep Largest Component")

    result = np.array(mask.matrix[1:, 1:, 1:])
    assert result[0, 0, 0] == 0  # speck removed
    assert result[2, 2, 2] == 255  # main blob kept


def test_cleanup_preserves_padding(real_mask_env):
    """The 1-voxel padding border (index 0 on every axis) must be
    untouched by a cleanup write - only mask.matrix[1:,1:,1:] is ever
    assigned to (Section 6's explicit re-audit requirement)."""
    from plugins.roi_viewer.core import segmentation_cleanup

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    _write_region(mask, values)

    # Mark a recognizable value in the padding border that must survive.
    mask.matrix[0, 5, 5] = 7
    mask.matrix[3, 0, 5] = 7
    mask.matrix[3, 5, 0] = 7

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    panel._run_cleanup(lambda region: segmentation_cleanup.smooth_binary_mask(region, iterations=1), "Smooth Mask")

    assert mask.matrix[0, 5, 5] == 7
    assert mask.matrix[3, 0, 5] == 7
    assert mask.matrix[3, 5, 0] == 7


def test_cleanup_sets_axial_sentinel_after_write(real_mask_env):
    """Real, verified protection against do_threshold_to_all_slices()
    silently discarding the cleanup on a not-yet-visited slice (see
    SegmentationPanel._run_cleanup()'s own docstring and
    invesalius/data/slice_.py.do_threshold_to_all_slices(), re-audited
    for this milestone) - every axial slice's sentinel
    (mask.matrix[n, 0, 0]) must be 1 after a real cleanup write."""
    from plugins.roi_viewer.core import segmentation_cleanup

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    values[2, 2, 2] = 0  # real enclosed cavity, so fill_holes() is a real mutation, not a no-op
    _write_region(mask, values)
    assert (np.array(mask.matrix[1:, 0, 0]) == 0).all()  # sentinels start unvisited

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    panel._run_cleanup(lambda region: segmentation_cleanup.fill_holes(region), "Fill Holes")

    assert (np.array(mask.matrix[1:, 0, 0]) == 1).all()  # all axial slices now marked visited


def test_cleanup_sets_was_edited(real_mask_env):
    from plugins.roi_viewer.core import segmentation_cleanup

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    values[0, 0, 0] = 255
    _write_region(mask, values)
    assert mask.was_edited is False

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    panel._run_cleanup(lambda region: segmentation_cleanup.keep_largest_component(region), "Keep Largest Component")

    assert mask.was_edited is True


def test_cleanup_locked_roi_refused(real_mask_env, monkeypatch):
    from plugins.roi_viewer.core import segmentation_cleanup

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    values[0, 0, 0] = 255
    _write_region(mask, values)
    before = np.array(mask.matrix[1:, 1:, 1:])

    roi = roi_mgr.get_roi_by_mask_index(0)
    roi_mgr.set_locked(roi_mgr.current_roi_id, True) if roi_mgr.current_roi_id is not None else None
    # Lock by roi_id (found via mask_index, matching the real GUI flow).
    for rid, r in roi_mgr.rois.items():
        if r.mask_index == 0:
            roi_mgr.set_locked(rid, True)
    assert roi_mgr.is_locked_for_mask_index(0) is True

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    # wx.MessageBox would normally show a real dialog - monkeypatch it to
    # a no-op for this headless test (same technique the rest of this
    # suite uses to avoid a real modal popup blocking pytest).
    import wx
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: None)

    panel._run_cleanup(lambda region: segmentation_cleanup.keep_largest_component(region), "Keep Largest Component")

    after = np.array(mask.matrix[1:, 1:, 1:])
    assert np.array_equal(before, after)  # refused - nothing changed
    assert mask.was_edited is False


def test_cleanup_unlocked_roi_allowed(real_mask_env):
    from plugins.roi_viewer.core import segmentation_cleanup

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    values[0, 0, 0] = 255
    _write_region(mask, values)
    assert roi_mgr.is_locked_for_mask_index(0) is False

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    panel._run_cleanup(lambda region: segmentation_cleanup.keep_largest_component(region), "Keep Largest Component")

    assert mask.was_edited is True  # allowed - operation actually ran


def test_keep_largest_undo_exact(real_mask_env):
    from plugins.roi_viewer.core import segmentation_cleanup

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    values[0, 0, 0] = 255
    _write_region(mask, values)
    original_full_matrix = np.array(mask.matrix)

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    panel._run_cleanup(lambda region: segmentation_cleanup.keep_largest_component(region), "Keep Largest Component")
    assert not np.array_equal(np.array(mask.matrix), original_full_matrix)  # really changed

    editor = mask_mgr.get_editor(mask.index)
    assert editor.undo_manager.can_undo()
    restored = editor.undo_manager.undo(mask.matrix)
    mask.matrix[:] = restored
    assert np.array_equal(np.array(mask.matrix), original_full_matrix)  # exact previous mask


def test_keep_largest_redo_exact(real_mask_env):
    from plugins.roi_viewer.core import segmentation_cleanup

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    values[0, 0, 0] = 255
    _write_region(mask, values)

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    panel._run_cleanup(lambda region: segmentation_cleanup.keep_largest_component(region), "Keep Largest Component")
    cleaned_full_matrix = np.array(mask.matrix)

    editor = mask_mgr.get_editor(mask.index)
    previous = editor.undo_manager.undo(mask.matrix)
    mask.matrix[:] = previous
    assert editor.undo_manager.can_redo()
    redone = editor.undo_manager.redo(mask.matrix)
    mask.matrix[:] = redone
    assert np.array_equal(np.array(mask.matrix), cleaned_full_matrix)  # exact cleanup result


def test_remove_small_undo_exact(real_mask_env):
    from plugins.roi_viewer.core import segmentation_cleanup

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    values[0, 0, 0] = 255
    _write_region(mask, values)
    original_full_matrix = np.array(mask.matrix)

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    panel._run_cleanup(
        lambda region: segmentation_cleanup.remove_small_components(region, min_voxels=5), "Remove Small Islands"
    )
    editor = mask_mgr.get_editor(mask.index)
    restored = editor.undo_manager.undo(mask.matrix)
    mask.matrix[:] = restored
    assert np.array_equal(np.array(mask.matrix), original_full_matrix)


def test_fill_holes_undo_exact(real_mask_env):
    from plugins.roi_viewer.core import segmentation_cleanup

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    values[2, 2, 2] = 0  # enclosed cavity
    _write_region(mask, values)
    original_full_matrix = np.array(mask.matrix)

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    panel._run_cleanup(lambda region: segmentation_cleanup.fill_holes(region), "Fill Holes")
    editor = mask_mgr.get_editor(mask.index)
    restored = editor.undo_manager.undo(mask.matrix)
    mask.matrix[:] = restored
    assert np.array_equal(np.array(mask.matrix), original_full_matrix)


def test_smooth_undo_exact(real_mask_env):
    from plugins.roi_viewer.core import segmentation_cleanup

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    _write_region(mask, values)
    original_full_matrix = np.array(mask.matrix)

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    panel._run_cleanup(lambda region: segmentation_cleanup.smooth_binary_mask(region, iterations=1), "Smooth Mask")
    editor = mask_mgr.get_editor(mask.index)
    restored = editor.undo_manager.undo(mask.matrix)
    mask.matrix[:] = restored
    assert np.array_equal(np.array(mask.matrix), original_full_matrix)


def test_noop_does_not_corrupt_mask(real_mask_env):
    """A single connected component, already the largest (and only)
    one - Keep Largest Component must be a real no-op: no mutation, no
    Undo checkpoint pushed, was_edited stays False."""
    from plugins.roi_viewer.core import segmentation_cleanup

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    _write_region(mask, values)
    original_full_matrix = np.array(mask.matrix)

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    panel._run_cleanup(lambda region: segmentation_cleanup.keep_largest_component(region), "Keep Largest Component")

    assert np.array_equal(np.array(mask.matrix), original_full_matrix)  # byte-identical, nothing touched
    assert mask.was_edited is False
    editor = mask_mgr.get_editor(mask.index)
    assert editor is None or not editor.undo_manager.can_undo()  # no checkpoint pushed for a no-op


def test_cleanup_does_not_build_surface(real_mask_env, monkeypatch):
    """Section 20: cleanup must NEVER call "Create surface from index"
    automatically - verified for real by subscribing a spy to the real
    pubsub topic and asserting it never fires."""
    from plugins.roi_viewer.core import segmentation_cleanup
    from invesalius.pubsub import pub as Publisher

    mask, roi_mgr, mask_mgr = real_mask_env
    values = np.zeros(_SHAPE, dtype=np.uint8)
    values[1:5, 1:5, 1:5] = 255
    values[0, 0, 0] = 255
    _write_region(mask, values)

    calls = []
    Publisher.subscribe(lambda **kw: calls.append(kw), "Create surface from index")

    controller = _FakeController(roi_mgr, mask_mgr)
    panel = _panel_like(controller)
    panel._run_cleanup(lambda region: segmentation_cleanup.keep_largest_component(region), "Keep Largest Component")

    assert calls == []
