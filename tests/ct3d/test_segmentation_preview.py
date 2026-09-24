# --------------------------------------------------------------------------
# Persistent tests for the E2 (Advanced Segmentation Enhancement Track)
# core/segmentation_preview.SegmentationPreviewManager state machine.
#
# Pure logic - no wx, no invesalius.* import, no real Slice()/Project().
# A plain small numpy array stands in for the real memmap array the GUI
# layer would hand this in production (this module is deliberately
# array-type-agnostic - see the module docstring). Marked unit.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from plugins.roi_viewer.core.segmentation_preview import PreviewState, SegmentationPreviewManager

pytestmark = pytest.mark.unit


def _small_array(value=255):
    a = np.zeros((4, 4, 4), dtype=np.uint8)
    a[1:3, 1:3, 1:3] = value
    return a


def test_preview_initial_state_idle():
    mgr = SegmentationPreviewManager()
    assert mgr.state == PreviewState.IDLE
    assert mgr.preview_array is None
    assert mgr.preview_kind is None


def test_set_preview_moves_to_ready():
    mgr = SegmentationPreviewManager()
    gen = mgr.new_generation()
    assert mgr.state == PreviewState.COMPUTING

    ok = mgr.set_otsu_preview(gen, _small_array(), threshold=(100, 300), name="Otsu Preview")
    assert ok is True
    assert mgr.state == PreviewState.PREVIEW_READY
    assert mgr.preview_kind == "otsu"
    assert mgr.source_threshold == (100, 300)
    assert mgr.preview_name == "Otsu Preview"


def test_cancel_clears_preview():
    mgr = SegmentationPreviewManager()
    gen = mgr.new_generation()
    mgr.set_otsu_preview(gen, _small_array(), threshold=(1, 2), name="X")
    assert mgr.state == PreviewState.PREVIEW_READY

    mgr.cancel()
    assert mgr.state == PreviewState.IDLE
    assert mgr.preview_array is None
    assert mgr.preview_kind is None
    assert mgr.source_threshold is None


def test_cancel_idle_safe_noop():
    mgr = SegmentationPreviewManager()
    mgr.cancel()  # must not raise
    assert mgr.state == PreviewState.IDLE


def test_accept_requires_ready():
    mgr = SegmentationPreviewManager()
    assert mgr.begin_accept() is False  # IDLE, not PREVIEW_READY
    assert mgr.state == PreviewState.IDLE

    gen = mgr.new_generation()
    assert mgr.begin_accept() is False  # COMPUTING, not PREVIEW_READY yet
    assert mgr.state == PreviewState.COMPUTING

    mgr.set_otsu_preview(gen, _small_array(), threshold=(1, 2), name="X")
    assert mgr.begin_accept() is True
    assert mgr.state == PreviewState.ACCEPTING


def test_accept_exactly_once():
    mgr = SegmentationPreviewManager()
    gen = mgr.new_generation()
    mgr.set_otsu_preview(gen, _small_array(), threshold=(1, 2), name="X")

    assert mgr.begin_accept() is True
    assert mgr.state == PreviewState.ACCEPTING
    mgr.finish_accept()
    assert mgr.state == PreviewState.IDLE


def test_second_accept_no_duplicate():
    mgr = SegmentationPreviewManager()
    gen = mgr.new_generation()
    mgr.set_otsu_preview(gen, _small_array(), threshold=(1, 2), name="X")

    assert mgr.begin_accept() is True  # first click: proceeds
    # Simulate a rapid double-click BEFORE finish_accept() runs: the
    # manager is already ACCEPTING, so a second begin_accept() must
    # refuse - this is what the real GUI handler checks to decide
    # whether to actually commit a second real mask.
    assert mgr.begin_accept() is False
    assert mgr.state == PreviewState.ACCEPTING


def test_second_preview_replaces_first():
    mgr = SegmentationPreviewManager()
    gen1 = mgr.new_generation()
    mgr.set_otsu_preview(gen1, _small_array(100), threshold=(1, 2), name="First")
    assert mgr.preview_name == "First"

    gen2 = mgr.new_generation()
    assert gen2 != gen1
    mgr.set_region_growing_preview(
        gen2, _small_array(200), seed_world=(1.0, 2.0, 3.0), seed_voxel=(1, 2, 3),
        tolerance=50, stats={"voxel_count": 8}, name="Second",
    )
    assert mgr.preview_kind == "region_growing"
    assert mgr.preview_name == "Second"
    # No leftover otsu metadata from the first preview.
    assert mgr.source_threshold is None


def test_generation_id_rejects_stale_result():
    mgr = SegmentationPreviewManager()
    gen1 = mgr.new_generation()  # "request 1 starts"
    gen2 = mgr.new_generation()  # "request 2 starts later" (before request 1 finished)
    assert gen2 != gen1

    # "request 1 finishes late" - must NOT overwrite request 2's slot.
    ok1 = mgr.set_otsu_preview(gen1, _small_array(), threshold=(1, 2), name="Stale")
    assert ok1 is False
    assert mgr.state == PreviewState.COMPUTING  # still waiting on gen2, untouched by the stale result
    assert mgr.preview_name is None

    ok2 = mgr.set_otsu_preview(gen2, _small_array(), threshold=(3, 4), name="Fresh")
    assert ok2 is True
    assert mgr.preview_name == "Fresh"


def test_project_close_clear():
    """Same real call as cancel() - project close uses this to guarantee
    no preview state (or its underlying array reference) survives into
    a different/no project. See gui/segmentation_panel.py's lifecycle
    hooks."""
    mgr = SegmentationPreviewManager()
    gen = mgr.new_generation()
    mgr.set_region_growing_preview(
        gen, _small_array(), seed_world=(0, 0, 0), seed_voxel=(0, 0, 0),
        tolerance=10, stats={}, name="X",
    )
    mgr.cancel()
    assert mgr.state == PreviewState.IDLE
    assert mgr.preview_array is None


def test_plugin_close_clear():
    """Same mechanism as project_close - plugin close/destroy also just
    calls cancel()."""
    mgr = SegmentationPreviewManager()
    gen = mgr.new_generation()
    mgr.set_otsu_preview(gen, _small_array(), threshold=(1, 2), name="X")
    mgr.cancel()
    assert mgr.state == PreviewState.IDLE
    assert mgr.preview_kind is None


def test_preview_array_released_after_cancel():
    mgr = SegmentationPreviewManager()
    gen = mgr.new_generation()
    arr = _small_array()
    mgr.set_otsu_preview(gen, arr, threshold=(1, 2), name="X")
    assert mgr.preview_array is arr

    mgr.cancel()
    assert mgr.preview_array is None  # manager drops its reference


def test_preview_array_released_after_accept():
    mgr = SegmentationPreviewManager()
    gen = mgr.new_generation()
    arr = _small_array()
    mgr.set_otsu_preview(gen, arr, threshold=(1, 2), name="X")
    mgr.begin_accept()
    mgr.finish_accept()
    assert mgr.preview_array is None
