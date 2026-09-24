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

---

# E3 Cleanup Architecture

## Source-first audit before any E3 code

Files re-read in full/targeted for this milestone: `plugins/roi_viewer/core/segmentation.py` (for the region-growing connectivity precedent), `plugins/roi_viewer/core/segmentation_preview.py`, `plugins/roi_viewer/core/mask_editor.py`, `plugins/roi_viewer/core/roi_manager.py`, `plugins/roi_viewer/gui/segmentation_panel.py`, `plugins/roi_viewer/gui/roi_panel.py`, and - critically, per this milestone's own explicit re-audit requirement - `invesalius/data/mask.py` (`Mask.create_mask()`'s exact padded-shape construction) and `invesalius/data/slice_.py.do_threshold_to_all_slices()` (the exact real sentinel-check logic, re-read line by line rather than assumed from memory of earlier phases).

## Mask/padding convention (re-audited, not assumed)

`Mask.create_mask(shape)` allocates `matrix` with shape `(shape[0]+1, shape[1]+1, shape[2]+1)` - confirmed directly in `invesalius/data/mask.py`. Real logical voxel data lives at `matrix[1:, 1:, 1:]`; index 0 on every axis is padding. `do_threshold_to_all_slices()` was re-read in full: it iterates ONLY over axial slices (`range(1, mask.matrix.shape[0])`) and checks/sets ONLY `mask.matrix[n, 0, 0]` (the per-axial-slice "already thresholded" sentinel) - it never reads or writes any Coronal/Sagittal-indexed sentinel cell. This confirms the exact, minimal protection E3's real mask-write path needs: writing into `mask.matrix[1:, 1:, 1:]` (real data) and then marking `mask.matrix[1:, 0, 0] = 1` (all axial sentinels) is sufficient and correct - the same real defensive write `_on_region_grown()` already established for a newly-created region-growing mask, now reused for an EXISTING mask being cleaned up (a live risk here too: a mask that has never had a surface built for it, or been fully scrolled through in 2D, may still have some axial sentinels at 0 when E3 cleanup runs).

## Connectivity decision

`core/segmentation.py.SegmentationManager.region_growing()` calls `ndimage.label(thresholded)` with no explicit `structure` - scipy's real default for a 3D array is `generate_binary_structure(3, 1)`, i.e. 6-connected (face neighbors only). `core/segmentation_cleanup.py`'s `DEFAULT_CONNECTIVITY = 1` matches this exactly and is used by every connected-component operation in the module (`keep_largest_component()`, `remove_small_components()`, `fill_holes()`'s structuring element, `smooth_binary_mask()`'s structuring element) - E3 never introduces a second, silently-different adjacency convention. Diagonal-only touching voxels (sharing an edge or corner, not a face) are separate components under this scheme - locked in by `test_default_connectivity_is_six_connected`.

## Cleanup core architecture

`core/segmentation_cleanup.py`: pure numpy/scipy functions, zero `invesalius.*`/wx/pubsub imports (same architectural pattern as `core/segmentation.py` and `core/segmentation_preview.py`). Contract: every function takes a foreground-is-nonzero array and returns `(result: np.ndarray[uint8, 0/255], info: dict)` of the SAME shape - `info` carries operation-specific stats (component counts, voxels added, etc.); a separate `cleanup_stats(before, after, spacing_zyx=None)` computes the generic before/after voxel-count summary shared by every operation. Never mutates its input (`test_cleanup_does_not_mutate_input`).

## Keep Largest Component

Connected-component labeling (6-connected, see above), keeps only the component with the most voxels. **Tie-break** (deliberately documented, not left to scipy implementation-order accident): the SMALLEST label id wins. `scipy.ndimage.label()` assigns ids in a fixed, deterministic raster-scan order for a given input - so "smallest label id" is itself fully deterministic and reproducible, not an artifact - verified by `test_keep_largest_equal_size_deterministic` (identical input, repeated calls, identical result).

## Remove Small Islands

`size < min_voxels` is removed; a component of size EXACTLY `min_voxels` is KEPT (an inclusive lower bound - "keep everything at or above this size" is the natural reading of "Minimum component size"). Locked in by `test_remove_small_threshold_boundary`. `min_voxels < 1` raises `ValueError` (matches this project's existing validation style, e.g. `region_growing()`'s tolerance check).

## Fill Holes

Real `scipy.ndimage.binary_fill_holes()`, same connectivity structuring element as the rest of the module. Its real, standard definition (background reachable from the array border is never filled) was verified directly, not assumed: `test_fill_holes_external_background_unchanged` constructs a solid object whose background touches every side of the volume and asserts zero change.

## Smooth algorithm selection

Real synthetic-phantom comparison (not a "looks smoother" guess) between binary closing→opening and Gaussian-blur-then-threshold-at-0.5, on 5 phantoms (cube, sphere, jagged-boundary cube, single-voxel background noise, 1-voxel-thin line), 1 iteration each:

| Phantom | Gaussian Δ% | Closing→Opening Δ% |
|---|---|---|
| cube | -10.4% | -10.4% |
| sphere (convex) | -4.4% | **-0.6%** |
| jagged | -5.8% | -13.4% |
| noise (30 specks) | -12.7% | -11.7% |
| thin (1-voxel line) | -100% (destroyed) | -100% (destroyed) |

Both candidates were fully deterministic. **Closing→opening was chosen**: dramatically less unwanted volume drift on the convex sphere phantom (real anatomical ROIs are frequently convex-ish), and it reuses the exact same connectivity/structuring-element convention already established for `keep_largest_component()`/`remove_small_components()`/`fill_holes()` above, rather than introducing a second, unrelated smoothing paradigm. **Both candidates completely destroyed the 1-voxel-thin phantom** at iteration 1 - a real, shared limitation of any binary morphological/blur-based smoothing at that scale, documented here and in `CT3D_ADVANCED_E3_CLEANUP_REPORT.md` rather than hidden. `iterations` is bounded to `[1, MAX_SMOOTH_ITERATIONS=5]` (`ValueError` outside that range) - not exposed as an unbounded control.

## Cleanup targets

**Current ROI is the only target implemented this milestone.** Active Preview cleanup was audited and explicitly deferred: E2's `_on_preview_accept()` commits an Otsu preview by calling `_commit_threshold_mask(lo, hi)`, which re-triggers InVesalius's real threshold-based mask creation (`"Create new mask"` → `do_threshold_to_all_slices()` deriving voxels from `threshold_range` against the raw image) - it does **not** write the accepted array directly. If E3 cleaned the preview's `preview_array` and the user then clicked Accept, the committed mask would silently be the ORIGINAL, un-cleaned Otsu threshold result - a real correctness bug the task's own instructions explicitly warned against ("Never allow preview != accepted output"). Region Growing's own Accept path (`_commit_region_growing_result()`) already commits an arbitrary passed-in array directly, so it COULD safely support Active Preview cleanup - but shipping cleanup for Region-Growing-previews-only while leaving Otsu-previews silently unsupported (or worse, silently unsafe if implemented uniformly) was judged more confusing and riskier than deferring the whole target consistently. This is a deliberate, documented, correctness-first scope decision - not a limitation discovered too late to fix.

## E1 Lock integration

`_run_cleanup()` delegates to the same pure `ROIManager.is_locked_for_mask_index()` decision E1's brush/undo/redo/delete guards already use - no duplicated lock state, no new lock mechanism. Lock does not apply to Active Preview (moot this milestone, since that target is deferred) - a preview is not an existing ROI, so E1's per-ROI lock concept does not describe it.

## Undo/Redo integration

`_run_cleanup()` calls the EXISTING `controller.mask_mgr`/`core/mask_editor.UndoRedoManager.save_state()` - the SAME real mechanism the "Save Checkpoint"/"Undo"/"Redo" buttons already use, exactly once per successful (non-no-op) cleanup operation. No E3-specific undo stack. Verified with exact array-equality round-trips (`test_keep_largest_undo_exact`, `test_keep_largest_redo_exact`, `test_remove_small_undo_exact`, `test_fill_holes_undo_exact`, `test_smooth_undo_exact`).

## No-op policy

`_run_cleanup()` computes the real result FIRST, compares it (`np.array_equal(result > 0, before > 0)`) to the input, and returns immediately - no checkpoint pushed, no mask write, no `was_edited` flip, no dirty state - if they're identical. Verified by `test_noop_does_not_corrupt_mask` (a single, already-largest component run through Keep Largest Component: byte-identical matrix, `was_edited` stays `False`, no Undo checkpoint exists afterward).

## Surface semantics

`_run_cleanup()` never sends `"Create surface from index"` - verified for real via a pubsub spy asserting zero calls (`test_cleanup_does_not_build_surface`), not just by code inspection. Preserves the Phase 08 D9/C7 policy exactly: the surface intentionally goes stale after a mask edit, and the status message explicitly tells the user to use "Update 3D Surface from Selected ROI" to refresh it.

## Statistics

`cleanup_stats(before, after, spacing_zyx)` returns `before_voxels`/`after_voxels`/`delta_voxels`/`delta_percent`, plus `before_volume_mm3`/`after_volume_mm3`/`delta_volume_mm3` when real spacing is available (via `ProjectInterface().get_spacing()`). Each operation's own `info` dict (component counts, voxels added, etc.) is appended to the same status message - no fabricated anatomical interpretation, only real measured numbers.

## Performance

Measured on a representative dataset-`0051`-shaped array (108×512×512 ≈ 28.3M voxels, ~3.75M real foreground voxels, 435 real connected components including scattered noise):

| Operation | Runtime |
|---|---|
| Keep Largest Component | 0.54s |
| Remove Small Islands | 0.53s |
| Fill Holes | 0.71s |
| Smooth (iterations=1) | 0.70s |
| Smooth (iterations=5) | 1.19s |

All comfortably under 1.2s even at the maximum bounded smoothing iteration count. **Decision: synchronous, no threading** - matches this project's own established principle (see `core/segmentation.py.region_growing()`'s own history: it was vectorized specifically BECAUSE the old Python-loop BFS took over a minute; these operations, already vectorized scipy calls, do not exhibit that problem) - measured evidence, not a default guess.

## Memory

All four operations allocate at most a small constant number of same-shape intermediate arrays (scipy's own internal working memory for labeling/morphology) plus one `before` copy (`np.array(region)`) taken by `_run_cleanup()` for the no-op comparison and Undo checkpoint. No new persistent/long-lived array is retained beyond the operation itself - unlike E2's preview (which deliberately keeps one array alive while `PREVIEW_READY`), E3's Current ROI cleanup either commits immediately or discards, nothing lingers.

## Known test-infrastructure issue found and fixed this milestone

Adding this milestone's real-`Mask()`/`Slice()`/`Project()` integration test file (a THIRD file using the "one real Slice()/Project() pair, reused across a module's tests" pattern E2 already established) caused real, deterministic (non-flaky, reproduced identically across 5 consecutive full-suite runs) failures in E2's own previously-passing tests (`test_otsu_accept_creates_one_real_mask` and others in `test_segmentation_preview_commit.py`). Root cause: `reset_invesalius_singletons` (the suite's autouse per-test isolation fixture) only un-points `Slice.instance`/`Project.instance`, it does not unsubscribe a `Slice()` instance's real pypubsub bindings (made once, in `__init__`) - and pytest sets up a newly-needed MODULE-scoped fixture before the FUNCTION-scoped autouse reset runs for the first test in that module, so each of the 3 files' own private "construct once per module" fixture ended up creating its own real, still-subscribed `Slice()` instance, and pypubsub invoked ALL of their handlers (not just the current one) whenever any test sent the real `"Create new mask"` message. Fixed by hoisting a single `real_slice_and_project_singleton` fixture into `tests/ct3d/conftest.py`, session-scoped, shared by all three files - exactly one real `Slice()`/`Project()` pair now exists for the whole session, eliminating the accumulation. See that fixture's own docstring for the full explanation.
