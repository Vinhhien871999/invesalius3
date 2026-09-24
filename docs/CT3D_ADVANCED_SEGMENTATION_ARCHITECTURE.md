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

---

# E2 Preview Architecture

## Source-first audit before any E2 code

Files read in full: `plugins/roi_viewer/core/segmentation.py` (`SegmentationManager` - Otsu, region growing, `region_stats()`), `plugins/roi_viewer/core/mask_editor.py`, `plugins/roi_viewer/gui/segmentation_panel.py`'s full threshold/region-growing/undo-redo bodies. Targeted reads of `invesalius/data/slice_.py` (mask creation, colour, threshold, and - critically - the `aux_matrices`/`to_show_aux` rendering path) and `invesalius/data/styles.py` (the real `WatershedInteractorStyle`, which turned out to be the load-bearing precedent for E2's entire rendering design).

## Preview source of truth

**A preview is never a real project mask.** `core/segmentation_preview.SegmentationPreviewManager` (new) owns exactly this fact structurally: it has zero `invesalius.*` imports, zero pubsub, zero ability to call `Project().mask_dict` or any real InVesalius mutation - confirmed by the module containing no such import at all (verifiable by inspection, not just by convention). It tracks an opaque `preview_array` (real memmap in production, plain `numpy.ndarray` in tests) plus metadata (`preview_kind`, `source_threshold` or `seed_world`/`seed_voxel`/`tolerance`/`stats`), and a small state machine: `IDLE` → `COMPUTING` → `PREVIEW_READY` → `ACCEPTING` → (back to `IDLE`). `CANCELLED` is not a long-lived state (per the original task's own suggestion) - `cancel()` is a transition straight back to `IDLE`.

**Project().mask_dict is modified before Accept: NO.** Confirmed by construction (see above) and by real tests against a live `Project()` singleton (`tests/ct3d/test_segmentation_preview_commit.py`): `otsu_preview_does_not_create_project_mask`/`region_preview_does_not_create_mask` assert `len(proj.mask_dict) == 0` after running the exact real preview-computation code path.

## No temporary Project mask - the real alternative found

The task's own instructions required proving a safer display path exists before ever considering a temporary `Project().mask_dict` entry. It does: **`invesalius.data.slice_.Slice.aux_matrices`/`.to_show_aux`** - a real, already-shipped mechanism. Confirmed by reading `invesalius/data/slice_.py`'s slice-rendering method directly: after the normal current-mask blend, it separately blends `self.aux_matrices[self.to_show_aux]` (a plain numpy array, per-orientation-sliced via `get_aux_slice()`) using a custom VTK colour lookup table (`do_custom_colour()`), entirely independent of `Project().mask_dict`. This is not a theoretical mechanism - it is the **exact real path InVesalius's own Watershed tool uses for its live segmentation preview** (`invesalius/data/styles.py`'s `WatershedInteractorStyle.SetUp()`/`CleanUp()`: `self.viewer.slice_.aux_matrices["watershed"] = <temp array>`, `self.viewer.slice_.to_show_aux = "watershed"`, then `self.viewer.OnScrollBar()` to redraw; `CleanUp()` resets `to_show_aux = ""`). E2's `_show_preview_overlay()`/`_clear_preview_overlay()` mirror this pattern exactly, using a distinct key (`"roi_viewer_preview"`) and `Publisher.sendMessage("Reload actual slice")` (already used elsewhere in this plugin, e.g. undo/redo refresh) as the redraw trigger instead of holding a direct `Viewer` reference.

The backing array itself is allocated via `Slice.create_temp_mask()` - also a real, pre-existing method (already used by Watershed), returning a `(temp_file_path, np.memmap)` pair shaped like the real volume, `dtype=uint8`. Using it means E2's preview data is disk-backed, not a second full in-RAM copy of the volume (see "Memory" below).

**Real, pre-existing constraint this inherits (not introduced by E2)**: the generic `to_show_aux` blend only runs when `self.current_mask is not None` (confirmed directly in the render method - the exact same condition gates Watershed's own overlay). E2's preview buttons therefore require a current mask to already exist (any mask), with the same user-facing guard message pattern `_on_toggle_brush()` already uses for its own "no mask selected" case - not a new limitation invented for this feature, a real one shared with native code.

## State machine

`IDLE` → (`new_generation()`) → `COMPUTING` → (`set_otsu_preview()`/`set_region_growing_preview()`) → `PREVIEW_READY` → (`begin_accept()`) → `ACCEPTING` → (`finish_accept()`) → `IDLE`. `cancel()` can fire from any state and always lands on `IDLE`. `revert_accept()` (`ACCEPTING` → `PREVIEW_READY`, added during E2 for the oversized-region-declined/commit-failed case) preserves the preview data instead of discarding it, so a declined confirmation or a transient commit failure doesn't lose the user's work-in-progress preview.

## Otsu preview

`_on_preview_otsu()` calls the SAME real `SegmentationManager.auto_threshold_otsu()`/`apply_threshold()` the classic Otsu checkbox already uses - no second implementation. Accept calls `_commit_threshold_mask()`, extracted from the classic `_on_apply_threshold()` handler's commit body so both paths share one real "Create new mask" call using the exact threshold the preview showed (proven by `otsu_accept_uses_same_threshold_as_preview`, a real test asserting the committed mask's `threshold_range` equals the value the preview computed).

## Region Growing preview

Seed-pick UX is unchanged (`btn_pick_seed`, same 3D picker). With Preview Workflow enabled, `_on_seed_picked()` now only *records* the seed (`self._preview_seed_world`/`_preview_seed_voxel`) instead of immediately spawning the background-growing worker - an explicit "Preview Region Growing" click starts the (still background-threaded, still `wx.CallAfter`-marshalled) computation, using whatever Tolerance value is set at that moment. This lets the user adjust Tolerance after picking, before paying the compute cost - a real UX improvement over the classic immediate-commit flow, not just a mechanical port of it. `_commit_region_growing_result()` was extracted from the classic `_on_region_grown()` handler's tail (mask creation + padded matrix write + `was_edited=True`) so Accept reuses the identical real commit, never a second implementation.

## Accept semantics

`_on_preview_accept()`: `preview_mgr.begin_accept()` gates entry (returns `False`, no-op, if not `PREVIEW_READY` - covers "already accepting" from a rapid double-click, and "nothing to accept"). Buttons are disabled immediately on entry. For Region Growing, if `preview_mgr.stats["exceeds_limit"]`, the SAME real oversized-region confirmation dialog the classic path shows appears here too, at commit time (not preview time) - declining it calls `revert_accept()` (preview preserved, state back to `PREVIEW_READY`) rather than losing the preview. On success: overlay cleared, `finish_accept()` (state → `IDLE`, all preview data released), `controller.on_roi_source_changed()` (real ROIManager resync, same call `_commit_threshold_mask`'s underlying `"Create new mask"` pubsub already triggers indirectly - kept explicit here for clarity), status updated. Real tests (`otsu_accept_creates_one_real_mask`, `region_accept_creates_exactly_one_mask`) confirm exactly one `Project().mask_dict` entry results.

## Cancel semantics

`_on_preview_cancel()` calls the shared `cancel_preview()` (also used by the lifecycle hooks below): clears the real overlay (`_clear_preview_overlay()`), calls `preview_mgr.cancel()` (bumps `generation_id`, clears all preview data/metadata, state → `IDLE`), clears the recorded seed, and resets UI state. Creates zero `Project()` masks - confirmed by `otsu_cancel_creates_no_mask`/`region_cancel_creates_zero_masks`.

## Async race protection

`SegmentationPreviewManager.generation_id`, bumped by `new_generation()` (before a computation starts) and by `cancel()`/`finish_accept()` (so a cancelled/completed preview's own in-flight worker, if any, can never resurrect it). `set_otsu_preview()`/`set_region_growing_preview()` both check `is_stale(generation_id)` first and return `False` (no mutation at all) for a stale result. Proven for real with the exact "request 1 starts, request 2 starts, request 1 finishes late" scenario the task specified (`test_generation_id_rejects_stale_result`, `test_stale_async_region_result_ignored`).

## Lifecycle

Preview is cleared via the shared `SegmentationPanel.cancel_preview()` from: `roi_panel.py`'s `on_project_close()` AND `on_project_load()` (a preview computed for the OLD project's volume is meaningless once a different project is loaded, defensive even though close-then-load already covers the normal flow), and `segmentation_panel.py`'s own `_on_destroy()` (plugin window closing) - unconditionally, not gated behind the brush-specific early-return that follows it. Widget-touching cleanup is wrapped separately from data cleanup and defends against `RuntimeError` from an already-destroyed wx widget (same real crash class already documented for the brush toggle's own destroy handler).

## Save/Open isolation

Preview is plugin-session state only - `SegmentationPreviewManager` has no serialization method at all, and nothing in E2 writes to any `Mask`/`Project` field before Accept. A project Save while a preview is visible saves the real masks exactly as they were (untouched); on Open, preview state is definitionally `IDLE` (a freshly constructed `SegmentationPanel`/`SegmentationPreviewManager`, or an existing one whose `cancel_preview()` already ran via `on_project_load()`). No change was made to `invesalius/project.py`'s serialization.

## E1 interaction

**Lock**: Otsu/Region Growing always create NEW masks (confirmed by reading `_commit_threshold_mask()`/`_commit_region_growing_result()` - both call `"Create new mask"`, never write into an already-existing mask), so a locked *current* ROI does not block preview generation - preview only *reads* the volume and the current mask's existence-as-a-render-precondition, never its content. **Solo**: the preview overlay renders via a completely separate mechanism (`aux_matrices`/`to_show_aux`) from per-ROI `Show mask`/`is_shown` visibility (confirmed by reading the render method - the aux blend happens unconditionally after the normal mask blend, regardless of which real mask is or isn't shown) - Solo hiding other ROIs has **zero effect** on whether the preview overlay renders. **Show All/Hide All**: only touch `ROI.visible`/`"Show mask"`, never `preview_mgr` or the aux overlay - cannot accidentally destroy preview state, confirmed by the same "separate mechanism" reasoning.

## C8 interaction

The preview overlay creates **no VTK actor/prop at all** - it is a 2D raster blend baked into each slice's own `vtkImageData` (via `do_custom_colour()`/`do_blend()`), the same way a real mask's own colour overlay is not a separate pickable actor either. It therefore cannot intercept 3D picking, cannot obstruct the C8 marker or slice planes (which live entirely in the 3D `Viewer`, a completely different rendering pipeline from the 2D slice views this overlay touches), cannot interfere with measurement tools, and cannot move the camera (nothing in this feature ever touches a `vtkCamera`). `test_overlay_is_not_actor_based_pickability_not_applicable` asserts the stored preview data has no `GetPickable` method at all, confirming by construction that "pickability" is not a concept that applies here.

## Memory

`Slice.create_temp_mask()` allocates `dtype=uint8`, shape = real volume shape, memmap-backed (disk, not pure RAM). For dataset `0051` (108×512×512 ≈ 28.3M voxels, see `CT3D_DATASET_REGISTRY.md`), that is ≈28.3MB per preview array - the SAME real order of magnitude as one Undo/Redo checkpoint (Phase 10 measured ≈27.36MB for a comparable real CT volume). At most ONE preview array is ever live at a time (`_reset_metadata()` clears the previous one's reference before a new one is set; `SegmentationPreviewManager` never accumulates multiple generations in memory), and `_clear_preview_overlay()`/a successful Accept always removes the backing temp file. This does not reintroduce the Phase 10 Undo/Redo memory-estimation mistake (a *single* array per preview, not an unbounded history).

## Feature flag

`ENABLE_PREVIEW_SEGMENTATION` is realized as `cb_enable_preview` (a real wx checkbox, "Enable Preview Workflow"), **default unchecked**. With it unchecked: `btn_preview_otsu`/`btn_preview_region_growing` stay disabled (`Enable(False)` at construction), `_on_seed_picked()` takes its original, unmodified immediate-grow branch, and `_commit_threshold_mask()`/`_commit_region_growing_result()` are reached ONLY through the classic handlers - E2 adds no new code to the classic call path at all when the flag is off (structurally, not just behaviorally, unchanged - proven by `otsu_classic_mode_unchanged_when_flag_off`/`test_classic_region_growing_unchanged_when_flag_off`).
