# --------------------------------------------------------------------------
# ROI Manager Module
# Description: Manages the plugin's "ROI List" - a named, organized view
#              over real InVesalius masks (invesalius.data.mask.Mask via
#              invesalius.project.Project().mask_dict).
#
# NOTE (Round-2 audit, section E): this used to keep its own independent
# copy of `name`/`color`/`visible` per ROI, hand-synced one-way (plugin
# action -> real mask) on every rename/visibility-toggle button click.
# That is a second source of truth: if a mask were renamed, hidden, or
# deleted through InVesalius's OWN native Masks tab (not through this
# plugin), this list would silently go stale, and if it were serialized
# into a project file separately from the mask it mirrors, a save/open
# cycle could resurrect a name that no longer matches the real mask.
#
# `Project().mask_dict` is the single source of truth for a mask's
# name/colour/visibility (invesalius/data/mask.py's Mask.name/.colour/
# .is_shown, already saved/loaded by InVesalius's own SavePlistProject/
# OpenPList - see invesalius/project.py). ROIManager is now a rebuildable
# cache/view over that real data - see rebuild_from_project_masks(),
# called by gui/roi_panel.py whenever the plugin's window opens, a
# project loads, or a mask is created/renamed/shown-hidden/removed
# (through the plugin OR through InVesalius's native UI - see main.py's
# extra pubsub subscriptions). Nothing here needs its own project-file
# serialization: rebuilding from the real masks after a project load
# reconstructs the exact same list (see
# test_roi_rebuild_after_project_load.py).
#
# The old ROI class also carried `points`/`bounds`/`locked`/
# `annotations` fields and `add_point()`/`contains_point()`/
# `get_center()`/`get_dimensions()`/`find_roi_at_point()` methods -
# grepping the whole plugin found zero call sites for any of them (no
# code ever called `add_point` on a ROI, and no UI ever exposed a way
# to). Removed as genuine dead code rather than kept "in case it's
# useful later" - see docs/CT3D_CHANGELOG.md for this round's audit.
# --------------------------------------------------------------------------

from typing import List, Optional, Dict


class ROI:
    """
    A named, organized view over one real InVesalius mask. `name`,
    `mask_index`, `color`, `visible` mirror the corresponding real Mask
    attribute (see the module docstring) - this object holds no state
    of its own for those fields that isn't already stored (and
    saved/loaded) on the real mask.

    `locked` (E1, Advanced ROI Manager) is the one exception: it is a
    plugin-session-only convenience flag with NO real InVesalius Mask
    counterpart, and is deliberately NOT persisted with the project
    (see ROIManager.rebuild_from_project_masks()'s docstring for why a
    second, separately-serialized source of truth is exactly what this
    module's whole design avoids). It resets to False whenever a ROI is
    freshly discovered from a project load (a newly opened project has
    no way to know what was locked in a previous session) - this is a
    deliberate scope decision (documented in
    docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md), not a bug.
    """

    def __init__(self, name: str, mask_index: int, color=(255, 0, 0), visible: bool = True, locked: bool = False):
        self.name = name
        self.mask_index = mask_index
        self.color = color
        self.visible = visible
        self.locked = locked


class ROIManager:
    """
    Manages the plugin's ROI List - a cache/view over real InVesalius
    masks, keyed by an internal id stable across rebuilds. See the
    module docstring for why this is a cache and not an independent
    source of truth.
    """

    def __init__(self):
        self.rois: Dict[int, ROI] = {}
        self.next_id = 0
        self.current_roi_id = None
        # E1 (Advanced ROI Manager): at most one ROI may be "solo'd" at
        # a time (exclusive solo, matching the common DAW/3D-tool
        # convention this UI gesture is borrowed from - not a MITK/
        # InVesalius concept). `_pre_solo_visibility` snapshots every
        # ROI's real visibility right before solo is engaged, so
        # exit_solo() can restore it exactly rather than just showing
        # everything (which would silently discard whatever the user
        # had hidden before soloing).
        self.solo_roi_id: Optional[int] = None
        self._pre_solo_visibility: Dict[int, bool] = {}

    def create_roi(self, name: str, mask_index: int, color=(255, 0, 0), visible: bool = True) -> int:
        """Create a new ROI and return its ID."""
        roi_id = self.next_id
        self.rois[roi_id] = ROI(name, mask_index, color, visible)
        self.next_id += 1
        self.current_roi_id = roi_id
        return roi_id

    def get_roi(self, roi_id: int) -> Optional[ROI]:
        """Get ROI by ID."""
        return self.rois.get(roi_id)

    def get_roi_by_mask_index(self, mask_index: int) -> Optional[ROI]:
        """Find the ROI (if any) that mirrors a given real mask index."""
        for roi in self.rois.values():
            if roi.mask_index == mask_index:
                return roi
        return None

    def get_current_roi(self) -> Optional[ROI]:
        """Get the currently selected ROI."""
        if self.current_roi_id is not None:
            return self.rois.get(self.current_roi_id)
        return None

    def set_current_roi(self, roi_id: int):
        """Set the currently selected ROI."""
        if roi_id in self.rois:
            self.current_roi_id = roi_id

    def delete_roi(self, roi_id: int, force: bool = False) -> bool:
        """Delete a ROI. Returns True if it was actually removed.

        E1 (Advanced ROI Manager): a locked ROI refuses deletion unless
        `force=True` - this is enforced HERE, at the core/ layer, not
        only in the GUI button handler, so the "locked ROIs can't be
        deleted" invariant holds no matter what calls this (matching
        this codebase's existing pattern of putting real safety
        invariants in core/, e.g. Region Growing's max-fraction check -
        see core/segmentation.py - rather than only in a wx handler).

        `force=True` is for rebuild_from_project_masks()'s own cleanup
        of ROIs whose real mask is already gone (deleted via
        InVesalius's native Masks tab, or any other real removal) - a
        cache entry for a mask that no longer exists must always be
        dropped regardless of this plugin-only lock flag, or the "no
        orphan ROI" invariant (see that method's tests) would break for
        locked ROIs."""
        if roi_id not in self.rois:
            return False
        if self.rois[roi_id].locked and not force:
            return False
        del self.rois[roi_id]
        if self.current_roi_id == roi_id:
            self.current_roi_id = None
        if self.solo_roi_id == roi_id:
            self.solo_roi_id = None
            self._pre_solo_visibility = {}
        return True

    def get_all_rois(self) -> List[ROI]:
        """Get all ROIs."""
        return list(self.rois.values())

    def clear(self):
        """Clear all ROIs."""
        self.rois.clear()
        self.current_roi_id = None
        self.next_id = 0
        self.solo_roi_id = None
        self._pre_solo_visibility = {}

    # ------------------------------------------------------------------
    # E1 (Advanced ROI Manager): lock
    # ------------------------------------------------------------------
    def set_locked(self, roi_id: int, locked: bool) -> bool:
        """Set a ROI's locked flag. Returns True if the ROI exists and
        was updated, False otherwise (caller decides how to report a
        missing ROI - this method never raises for a bad id)."""
        roi = self.rois.get(roi_id)
        if roi is None:
            return False
        roi.locked = bool(locked)
        return True

    def is_locked_for_mask_index(self, mask_index: int) -> bool:
        """Same as is_locked(), but keyed by real mask index rather than
        the internal roi_id - what GUI edit-guard call sites actually
        have on hand (e.g. sl.Slice().current_mask.index). Kept as a
        pure, wx-free method here (rather than inlined in
        gui/segmentation_panel.py) specifically so the "is this ROI
        locked" decision itself is unit-testable without constructing
        any wx widget."""
        roi = self.get_roi_by_mask_index(mask_index)
        return roi is not None and roi.locked

    def is_locked(self, roi_id: int) -> bool:
        """False for an unknown roi_id - an already-deleted/never-existed
        ROI cannot meaningfully be "locked", and callers (edit guards)
        should treat "unknown" the same as "not locked" (the mask lookup
        itself will separately fail for a genuinely missing mask)."""
        roi = self.rois.get(roi_id)
        return bool(roi.locked) if roi is not None else False

    # ------------------------------------------------------------------
    # E1 (Advanced ROI Manager): solo / show-all / hide-all
    #
    # All three return {roi_id: new_visible} for ONLY the ROIs whose
    # visible flag actually changed (not the full set) - the real
    # source of truth for visibility is InVesalius's own
    # Mask.is_shown, driven by the "Show mask" pubsub topic per index
    # (see gui/segmentation_panel.py's module docstring); this method
    # updates the cache and hands back exactly what the GUI layer needs
    # to replay onto that real topic, without this pure module needing
    # to know pubsub/wx exists.
    # ------------------------------------------------------------------
    def enter_solo(self, roi_id: int) -> Dict[int, bool]:
        """Hide every ROI except roi_id. No-op (returns {}) if roi_id is
        unknown. Snapshots current visibility first so exit_solo() can
        restore it exactly."""
        if roi_id not in self.rois:
            return {}
        self._pre_solo_visibility = {rid: roi.visible for rid, roi in self.rois.items()}
        self.solo_roi_id = roi_id
        changes: Dict[int, bool] = {}
        for rid, roi in self.rois.items():
            new_visible = rid == roi_id
            if roi.visible != new_visible:
                changes[rid] = new_visible
            roi.visible = new_visible
        return changes

    def cancel_solo(self) -> None:
        """Clear solo bookkeeping WITHOUT restoring pre-solo visibility -
        for when something else (a manual per-ROI visibility toggle,
        show_all(), hide_all()) has already made the current visibility
        state the new intentional one, and re-applying the stale
        pre-solo snapshot on a later exit_solo() would be wrong. Use
        exit_solo() instead when the user explicitly turns solo off
        without having changed anything else in the meantime."""
        self.solo_roi_id = None
        self._pre_solo_visibility = {}

    def exit_solo(self) -> Dict[int, bool]:
        """Restore visibility to what it was right before enter_solo()
        was called. No-op if solo isn't currently active."""
        if self.solo_roi_id is None:
            return {}
        changes: Dict[int, bool] = {}
        for rid, roi in self.rois.items():
            prev = self._pre_solo_visibility.get(rid, roi.visible)
            if roi.visible != prev:
                changes[rid] = prev
            roi.visible = prev
        self.solo_roi_id = None
        self._pre_solo_visibility = {}
        return changes

    def show_all(self) -> Dict[int, bool]:
        """Show every ROI. Also cancels any active solo (a bare
        "show everything" request is a clearer signal to abandon
        whatever was hidden pre-solo than to silently keep it around)."""
        changes: Dict[int, bool] = {}
        for rid, roi in self.rois.items():
            if not roi.visible:
                changes[rid] = True
            roi.visible = True
        self.solo_roi_id = None
        self._pre_solo_visibility = {}
        return changes

    def hide_all(self) -> Dict[int, bool]:
        """Hide every ROI. Also cancels any active solo (same reasoning
        as show_all())."""
        changes: Dict[int, bool] = {}
        for rid, roi in self.rois.items():
            if roi.visible:
                changes[rid] = False
            roi.visible = False
        self.solo_roi_id = None
        self._pre_solo_visibility = {}
        return changes

    def rebuild_from_project_masks(self):
        """
        Resync this cache against the real `Project().mask_dict` - the
        single source of truth. Safe to call any time (no project
        loaded, empty mask_dict, etc.) - see the module docstring for
        when this is called from.

        Existing ROI objects are updated IN PLACE (name/color/visible
        reassigned on the same instance) rather than replaced, so any
        code already holding a `roi` reference (e.g. mid-handler in
        segmentation_panel.py) sees the fresh values without needing to
        re-fetch it. ROIs whose mask no longer exists (deleted, or
        never associated with a real mask) are dropped. New ROIs are
        created for real masks this cache doesn't know about yet
        (covers masks created through InVesalius's native Masks tab,
        not just this plugin's own threshold/region-growing actions).
        """
        try:
            import invesalius.project as prj
        except ImportError:
            return

        mask_dict = prj.Project().mask_dict or {}

        seen_mask_indexes = set()
        for mask_index, mask in mask_dict.items():
            seen_mask_indexes.add(mask_index)
            roi = self.get_roi_by_mask_index(mask_index)
            colour = tuple(mask.colour[:3]) if getattr(mask, "colour", None) else (255, 0, 0)
            visible = bool(getattr(mask, "is_shown", True))
            name = getattr(mask, "name", f"Mask {mask_index}")
            if roi is None:
                self.create_roi(name, mask_index, colour, visible)
            else:
                roi.name = name
                roi.color = colour
                roi.visible = visible

        # Drop cached ROIs for masks that no longer exist in the project
        # (deleted via this plugin or via InVesalius's native Masks tab).
        # Note: `roi.name`/`.color`/`.visible` above are reassigned in
        # place for ROIs that already existed, so `.locked` (E1 - see
        # the ROI class docstring) is naturally preserved across a
        # rebuild for any ROI this cache already knew about; only
        # newly-discovered ROIs (create_roi() above) start unlocked.
        stale_ids = [
            roi_id for roi_id, roi in self.rois.items()
            if roi.mask_index not in seen_mask_indexes
        ]
        for roi_id in stale_ids:
            # force=True: the real mask is already gone, so the lock
            # flag (a plugin-only convenience over an already-deleted
            # mask) must not keep a dangling cache entry alive - see
            # delete_roi()'s docstring.
            self.delete_roi(roi_id, force=True)  # also clears solo_roi_id if it was the solo target
