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
    A named, organized view over one real InVesalius mask. Every field
    here mirrors the corresponding real Mask attribute (see the module
    docstring) - this object holds no state of its own that isn't
    already stored (and saved/loaded) on the real mask.
    """

    def __init__(self, name: str, mask_index: int, color=(255, 0, 0), visible: bool = True):
        self.name = name
        self.mask_index = mask_index
        self.color = color
        self.visible = visible


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

    def delete_roi(self, roi_id: int):
        """Delete a ROI."""
        if roi_id in self.rois:
            del self.rois[roi_id]
            if self.current_roi_id == roi_id:
                self.current_roi_id = None

    def get_all_rois(self) -> List[ROI]:
        """Get all ROIs."""
        return list(self.rois.values())

    def clear(self):
        """Clear all ROIs."""
        self.rois.clear()
        self.current_roi_id = None
        self.next_id = 0

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
        stale_ids = [
            roi_id for roi_id, roi in self.rois.items()
            if roi.mask_index not in seen_mask_indexes
        ]
        for roi_id in stale_ids:
            self.delete_roi(roi_id)
