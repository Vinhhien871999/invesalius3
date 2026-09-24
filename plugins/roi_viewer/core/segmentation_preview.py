# --------------------------------------------------------------------------
# Segmentation Preview Module (E2, Advanced Segmentation Enhancement Track)
# Description: Pure state-machine bookkeeping for the "Preview -> Accept/
#              Cancel" segmentation workflow. Owns NO real InVesalius
#              object (no wx, no pubsub, no invesalius.* import) - the
#              array it tracks is whatever the caller hands it (a real
#              memmap from invesalius.data.slice_.Slice.create_temp_mask()
#              in production, a plain small numpy array in tests). See
#              gui/segmentation_panel.py for the real wx/pubsub glue that
#              actually renders a preview (via Slice().aux_matrices/
#              to_show_aux - the same real, native mechanism InVesalius's
#              own Watershed tool already uses for its live overlay, NOT
#              a temporary Project().mask_dict entry - see
#              docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md's "E2
#              Preview Architecture" section for the full source-audit
#              trail behind this choice) and
#              docs/CT3D_ADVANCED_E2_PREVIEW_REPORT.md for the design
#              writeup.
#
# Core invariant this module exists to protect: a preview is NEVER a real
# project mask. Nothing in this file ever touches Project().mask_dict,
# ROIManager, Save/Open, Undo/Redo, or any other real InVesalius state -
# it is pure bookkeeping the GUI layer consults before deciding what real
# action (if any) to take.
# --------------------------------------------------------------------------
from typing import Optional, Tuple


class PreviewState:
    """String constants, not an Enum - kept consistent with this
    project's existing style (see invesalius.constants's plain int/str
    constants) and trivially printable in test failure messages."""

    IDLE = "IDLE"
    COMPUTING = "COMPUTING"
    PREVIEW_READY = "PREVIEW_READY"
    ACCEPTING = "ACCEPTING"


class SegmentationPreviewManager:
    """
    Tracks at most one in-flight or ready preview at a time. A second
    preview request always replaces the first (see new_generation()) -
    there is no accumulation of multiple previews in memory.

    `generation_id` guards against a real, concrete race: Region Growing
    runs its scipy computation on a background thread
    (gui/segmentation_panel.py's existing worker-thread pattern, reused
    unchanged for the preview path). If the user starts preview A, then
    (before A's worker finishes) starts preview B, A's worker may still
    complete and try to hand back a result AFTER B is already showing.
    Every "start a computation" call must capture the generation id
    returned by new_generation() and pass it back to
    set_otsu_preview()/set_region_growing_preview() - if the manager's
    generation has moved on (because cancel() or a newer
    new_generation() happened first), that stale result is silently
    dropped instead of overwriting a newer/different preview.
    """

    def __init__(self):
        self.state: str = PreviewState.IDLE
        self.generation_id: int = 0

        self.preview_array = None  # real (memmap) or fake (plain ndarray) - opaque to this module
        self.preview_kind: Optional[str] = None  # "otsu" | "region_growing"
        self.preview_name: Optional[str] = None  # suggested name for the eventual final mask

        # Otsu-specific
        self.source_threshold: Optional[Tuple[int, int]] = None

        # Region-growing-specific
        self.seed_world: Optional[Tuple[float, float, float]] = None
        self.seed_voxel: Optional[Tuple[int, int, int]] = None
        self.tolerance: Optional[int] = None
        self.stats: Optional[dict] = None  # SegmentationManager.region_stats() result

    # ------------------------------------------------------------------
    # Starting / rejecting async computations
    # ------------------------------------------------------------------
    def new_generation(self) -> int:
        """Call right before starting a (possibly async) computation -
        before spawning a worker thread. Moves state to COMPUTING and
        returns the generation id that computation must present back to
        set_*_preview() below."""
        self.generation_id += 1
        self.state = PreviewState.COMPUTING
        return self.generation_id

    def is_stale(self, generation_id: int) -> bool:
        return generation_id != self.generation_id

    # ------------------------------------------------------------------
    # Committing a computed candidate as THE current preview
    # ------------------------------------------------------------------
    def set_otsu_preview(self, generation_id: int, array, threshold: Tuple[int, int], name: str) -> bool:
        """Returns False (no-op, nothing changed) if generation_id is
        stale - see the class docstring."""
        if self.is_stale(generation_id):
            return False
        self._reset_metadata()
        self.preview_array = array
        self.preview_kind = "otsu"
        self.preview_name = name
        self.source_threshold = threshold
        self.state = PreviewState.PREVIEW_READY
        return True

    def set_region_growing_preview(
        self, generation_id: int, array, seed_world, seed_voxel, tolerance: int, stats: dict, name: str
    ) -> bool:
        """Returns False (no-op) if generation_id is stale."""
        if self.is_stale(generation_id):
            return False
        self._reset_metadata()
        self.preview_array = array
        self.preview_kind = "region_growing"
        self.preview_name = name
        self.seed_world = seed_world
        self.seed_voxel = seed_voxel
        self.tolerance = tolerance
        self.stats = stats
        self.state = PreviewState.PREVIEW_READY
        return True

    def _reset_metadata(self):
        """Shared by set_*_preview() - clears every field before setting
        the new preview's own subset, so a stale otsu field can never
        leak into a region_growing preview or vice versa."""
        self.preview_array = None
        self.preview_kind = None
        self.preview_name = None
        self.source_threshold = None
        self.seed_world = None
        self.seed_voxel = None
        self.tolerance = None
        self.stats = None

    # ------------------------------------------------------------------
    # Cancel / Accept
    # ------------------------------------------------------------------
    def cancel(self):
        """Discard everything, return to IDLE. Also bumps generation_id,
        so any in-flight async worker's eventual result is automatically
        treated as stale (is_stale() -> True) when it completes - it can
        never resurrect a preview the user explicitly cancelled."""
        self.generation_id += 1
        self._reset_metadata()
        self.state = PreviewState.IDLE

    def begin_accept(self) -> bool:
        """Transition PREVIEW_READY -> ACCEPTING. Returns False (caller
        must NOT proceed with any commit) if not currently
        PREVIEW_READY - this is what makes "Accept exactly once" and
        "double-click Accept is a no-op" hold: the second call, while
        already ACCEPTING, returns False immediately."""
        if self.state != PreviewState.PREVIEW_READY:
            return False
        self.state = PreviewState.ACCEPTING
        return True

    def revert_accept(self) -> bool:
        """Roll back ACCEPTING -> PREVIEW_READY, WITHOUT clearing the
        preview data - for when the real commit didn't actually happen
        (the user declined a required oversized-region confirmation, or
        the commit call itself failed) and the preview should remain
        exactly as it was so the user can retry Accept or Cancel
        normally, rather than losing it. No-op (returns False) if not
        currently ACCEPTING."""
        if self.state != PreviewState.ACCEPTING:
            return False
        self.state = PreviewState.PREVIEW_READY
        return True

    def finish_accept(self):
        """Call after a real commit has actually succeeded. Same end
        state as cancel() (everything cleared, back to IDLE) - kept as a
        separately-named method so call sites and tests can distinguish
        "the user cancelled" from "a commit just completed" even though
        the manager's own bookkeeping ends up identical either way."""
        self.generation_id += 1
        self._reset_metadata()
        self.state = PreviewState.IDLE
