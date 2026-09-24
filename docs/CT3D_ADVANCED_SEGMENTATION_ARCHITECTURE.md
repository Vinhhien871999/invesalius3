# CT3D — Advanced Segmentation Enhancement Track: Architecture

> See `docs/CT3D_ADVANCED_SEGMENTATION_ROADMAP.md` for scope/branch/priority context. This document records the real, source-verified architecture decisions behind each implemented milestone - updated as each E-stage lands, never retroactively rewritten to claim something existed before it did.

## Source-first audit (before any E1 code was written)

Files read in full before designing E1: `plugins/roi_viewer/core/roi_manager.py`, `plugins/roi_viewer/gui/segmentation_panel.py`, `plugins/roi_viewer/gui/roi_panel.py` (lifecycle hooks: `on_project_load`/`on_project_close`/`on_roi_source_changed`), plus targeted greps of `invesalius/data/slice_.py` and `invesalius/data/mask.py` for the exact real pubsub topics and serialized fields involved.

Key facts established from real code (not assumed):

- `core/roi_manager.ROIManager` was already, deliberately, a **rebuildable cache/view** over `Project().mask_dict` - not an independent data model. `rebuild_from_project_masks()` resyncs `name`/`color`/`visible` from the real `Mask.name`/`.colour`/`.is_shown` on every real mask create/rename/show-hide/remove (triggered via `main.py`'s pubsub subscriptions and `gui/roi_panel.py.on_roi_source_changed()`), whether the change came from this plugin or InVesalius's own native Masks tab.
- Real pubsub topics already used by `gui/segmentation_panel.py` and confirmed still correct: `"Create new mask"`, `"Change mask selected"`, `"Change mask name"`, `"Remove masks"`, `"Show mask"` (takes `index`, `value` - per-index, does NOT require the mask to be "current" first). A separate topic, `"Change mask colour"`, exists in `invesalius/data/slice_.py` but only acts on `self.current_mask` (would require a select-then-recolour two-step) - not used this milestone since E1 only asked for a colour **indicator**, not an editor.
- `invesalius/data/mask.py`'s `Mask` serializes exactly `name`, `colour`, `visible` (`is_shown`) - confirmed by reading its own save/load methods directly. No existing extension point for arbitrary plugin metadata.
- `SegmentationPanel._on_update_surface()`'s D9/C7 `choose_surface_algorithm()` policy (Phase 08/11) and `core/marker_3d`/`core/slice_planes_3d` (C8) were read to confirm E1 touches neither.

## Project().mask_dict relationship (unchanged, extended)

E1 introduces **zero** new data sources. Every ROI still corresponds 1:1 to a real `Project().mask_dict[mask_index]` entry. `ROI.name`/`.color`/`.visible` are still pure mirrors of the real `Mask` object, kept in sync exactly as before.

## Metadata / storage decision: what is, and is NOT, persisted

E1 adds exactly one new field to the in-memory `ROI` object: **`locked: bool`**. This field has **no real `Mask` counterpart** and is a **deliberate, permanent exception** to "everything here mirrors real Mask data":

- `locked` is **never** written to any `Mask` attribute, never sent over any pubsub topic, and never touches `invesalius/data/mask.py`'s serialization. A project Save/Open round-trip does **not** preserve it - confirmed by a real test (`tests/ct3d/test_roi_manager.py::test_save_open_metadata_roundtrip_if_metadata_added`), not just asserted in prose.
- **Why**: extending `Mask`'s real serialization format is a change to `invesalius/data/mask.py` - core, shared, upstream-adjacent code, not plugin-owned code - and a real risk to the Save/Open byte-identity guarantees the Phase 08-14 roadmap spent real effort establishing and testing (`CT3D_P10_DATA_INTEGRITY_REPORT.md`). E1's own scope instructions explicitly required "no phá Save/Open hiện tại" (don't break existing Save/Open) as a hard constraint, and made group/category metadata (which WOULD need real persistence to be useful) conditional on "if it can be done without breaking serialization." Given the real risk/benefit tradeoff, this run's decision is: **lock/solo are plugin-session-only conveniences, not persisted, and item 10 (group/category metadata) is deliberately deferred (`PLANNED`, not attempted)** rather than implemented unsafely.
- **Consequence, stated plainly**: locking a ROI, closing the plugin or the project, and reopening it will show that ROI as unlocked again. This is documented behavior, not a bug - see `docs/CT3D_ADVANCED_SEGMENTATION_PROGRESS.md`'s status table and the real test above.
- `solo_roi_id` (which ROI, if any, is currently solo'd) is `ROIManager`-instance-level state, same non-persistence reasoning, same rationale: it is a UI convenience over real `Mask.is_shown` toggles (which ARE real and ARE persisted per-ROI, exactly as before), not a new fact about the mask itself.

## Naming: why "Advanced ROI Manager", not "multilabel"

The real backend is still N **independent** InVesalius masks (`Project().mask_dict`), each its own `numpy` array with its own `1:,1:,1:`-padded matrix - not a single shared voxel volume with one label id per voxel (what "true multilabel" segmentation, e.g. MITK's LabelSetImage, actually means). Calling this "true multilabel" would be a false claim about the data model. The UI is titled **"Segmentation Set (Advanced ROI Manager)"** throughout, and this document states the real backend explicitly, so nobody downstream (including a future thesis chapter) mistakes UI-level ROI grouping for voxel-level multi-label encoding.

## E1 feature-by-feature backend mapping

| UI control | Backend | Real InVesalius interaction |
|---|---|---|
| Active ROI (label) | `ROIManager.current_roi_id`/`get_current_roi()`/`set_current_roi()` (pre-existing) | `"Change mask selected"` (pre-existing) |
| Colour indicator | `ROI.color` (pre-existing, read-only swatch) | none - display only, no new topic |
| Visibility (checkbox, per ROI) | `ROI.visible` (pre-existing) | `"Show mask"` (pre-existing) |
| Lock / Unlock | `ROIManager.set_locked()`/`is_locked()`/`is_locked_for_mask_index()` (new) | none - plugin-only guard, see below |
| Solo | `ROIManager.enter_solo()`/`exit_solo()`/`cancel_solo()` (new) | `"Show mask"` per affected ROI (replays the resulting visibility diff) |
| Show All / Hide All | `ROIManager.show_all()`/`hide_all()` (new) | `"Show mask"` per affected ROI |
| Rename | (pre-existing) | `"Change mask name"` (pre-existing) |
| Delete | `ROIManager.delete_roi(roi_id, force=False)` (extended: now refuses a locked ROI unless `force=True`) | `"Remove masks"` (pre-existing) |

### Lock enforcement points (where it actually guards something)

Lock is enforced in exactly the operations that can destroy or replace a mask's existing voxel content or identity:
- `SegmentationPanel._on_toggle_brush()` - refuses to enable the real brush editor (`"Enable style"`, `SLICE_STATE_EDITOR`) if the current mask's ROI is locked.
- `SegmentationPanel._on_undo()` / `_on_redo()` - refuse if the current mask's ROI is locked.
- `SegmentationPanel._on_roi_delete()` **and** `ROIManager.delete_roi()` itself (defense in depth - the invariant is enforced at the core layer, not only the wx handler, matching how Region Growing's max-region-fraction safety check already lives in `core/segmentation.py`, not just a GUI confirmation dialog).

Lock deliberately does **NOT** guard: Rename (non-destructive to segmentation data), visibility/solo/show-all/hide-all (non-destructive), Region Growing (always creates a brand-new mask via `"Create new mask"`, never writes into an existing locked mask's matrix - confirmed by reading `_on_region_grown()`), Threshold "Create Mask from Threshold" (same reasoning), Update Surface (reads the mask's voxel data to build a display artifact, never modifies it).

### Solo semantics

Exclusive (single-ROI) solo, matching the common DAW/3D-tool convention the term is borrowed from. `enter_solo(roi_id)` snapshots every ROI's real visibility first, so `exit_solo()` restores exactly what was hidden/shown before solo was engaged - not a blanket "show everything." A manual per-ROI visibility checkbox click, or `Show All`/`Hide All`, while solo is active cancels solo bookkeeping (`cancel_solo()`) rather than leaving a stale `solo_roi_id` pointing at a visibility state the user just explicitly overrode.

## UI implementation notes

`wx.CheckListBox` has no built-in per-item colour swatch or multi-icon column. Rather than build a custom-drawn `wx.ListCtrl` (real rendering risk, disproportionate to this milestone), lock/solo state is shown as a plain-text prefix (`[LOCKED]`, `[SOLO]`) on each list row, and the colour indicator is a single small `wx.Panel` swatch reflecting the **currently selected** ROI's colour (not per-row) next to the "Active ROI:" label. This is a deliberate, documented scope/complexity tradeoff, not an oversight.

## Testing strategy

- `tests/ct3d/test_roi_manager_advanced.py` (new, `unit`, no wx/`Project()` needed): lock/unlock, solo enter/exit, show-all/hide-all, delete-refuses-when-locked, all against a bare `ROIManager()` instance.
- `tests/ct3d/test_roi_manager.py` (existing file, `integration`, extended): real interaction between the new fields and `rebuild_from_project_masks()` against a fake-but-real `Project()` singleton - locked field surviving a real rename, solo target correctly cleared on a full project swap, no-orphan invariant holding for a locked+solo'd ROI whose mask is removed, and the explicit non-persistence contract test.
- GUI-level guard behavior (brush/undo/redo/delete refusing on a locked ROI) is exercised through the pure `ROIManager.is_locked_for_mask_index()`/`delete_roi(force=...)` methods the wx handlers delegate to (see the table above) - the decision logic itself is unit-tested without constructing any wx widget tree; the wx handlers are thin wrappers verified by manual GUI QA (see `docs/CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md`), not fabricated as automated GUI-click tests.

## What is explicitly NOT part of E1

- Group/category metadata (feature list item 10) - deferred, `PLANNED`, not attempted this milestone (see the persistence discussion above).
- Any colour **editing** UI (only an indicator was requested and built).
- Any change to `invesalius/data/mask.py`, `invesalius/project.py`, or any other upstream/core file.
