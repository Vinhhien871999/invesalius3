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

---

# E4 Fast Live 3D Preview Architecture

## Source-first surface audit

Read directly (not assumed): `invesalius/data/surface_process.py.create_surface_piece()` (the real per-piece contour worker the authoritative final surface pipeline runs, in its own OS process - see `invesalius/data/surface.py`'s multiprocessing dispatch), `invesalius/data/converters.py.to_vtk()`/`to_vtk_mask()`, `invesalius/data/viewer_volume.py` (for the real `viewer.ren` attach pattern already established by `marker_3d`/`slice_planes_3d`), `invesalius/data/mask.py` (for `Mask.modified()`/`add_modified_callback()`), `invesalius/data/styles.py` (for the real Brush/Eraser edit-completion event).

**Critical real finding**: `create_surface_piece()`'s `from_binary=True` branch applies a `vtkImageFlip(FilteredAxis=1, FlipAboutOriginOn)` step AFTER `converters.to_vtk()` and BEFORE contouring, and contours a binary mask at isovalue 127. This is not optional cosmetic detail - a preview mesh that skipped this flip would be Y-mirrored relative to the real final surface and every other 3D scene element (C8 marker, slice planes). E4 reuses these exact real steps (see "Coordinate convention" below) rather than deriving an independent transform.

## VTK version / available algorithms

VTK **9.3.0** (verified via `vtk.vtkVersion.GetVTKVersion()`, not assumed). Available and benchmarked: `vtkMarchingCubes`, `vtkFlyingEdges3D`, `vtkSurfaceNets3D` (all in `vtkmodules.vtkFiltersCore`), `vtkDiscreteMarchingCubes`, `vtkDiscreteFlyingEdges3D` (both in `vtkmodules.vtkFiltersGeneral`). The real final-surface pipeline itself uses `vtkContourFilter` (a generic dispatcher, not the same class as any of the above).

## Preview mesh benchmark

Real measurements on a representative dataset-`0051`-shaped array (108×512×512, 3,750,263 real foreground voxels, isovalue 127):

| Algorithm | Runtime | Points | Cells | Notes |
|---|---|---|---|---|
| `vtkFlyingEdges3D` | **0.068s** | 186,569 | 372,072 | Identical geometry to MarchingCubes |
| `vtkMarchingCubes` | 0.150s | 186,569 | 372,072 | Same real algorithm family as `vtkContourFilter`'s effective behavior here |
| `vtkSurfaceNets3D` | 0.043s | **0** | **0** | Wrong usage contract for isovalue 127 - expects discrete label values, not a continuous-field threshold; produced empty output |
| `vtkDiscreteMarchingCubes` | 0.096s | 0 | 0 | Same wrong-contract issue |
| `vtkDiscreteFlyingEdges3D` | 0.025s | 0 | 0 | Same wrong-contract issue |

Downsampled ×2 (simple stride) for reference: `vtkFlyingEdges3D` 0.009s, 46,439 points - confirming downsampling is available if ever needed, but see "Downsampling decision" below for why it wasn't built this milestone.

## Selected algorithm

**`vtkFlyingEdges3D`**, isovalue 127. Chosen because it measurably produces IDENTICAL output geometry (same point count, cell count, bounds - not just "close") to `vtkMarchingCubes` at ~2.2x the speed, making it a safe same-algorithm-family substitution for a non-authoritative preview, not a different technique that could diverge. The 3 discrete/label-based filters were ruled out by their real, measured, wrong behavior for this exact usage (empty output), not by assumption.

## Downsampling decision

**Not implemented this milestone.** Full resolution already measured comfortably fast (0.068s, well within an interactive/debounced budget). Section 7's own guidance ("If full-resolution raw preview is fast enough: prefer it") was followed directly from the benchmark evidence above - adding binary-safe downsampling (block-max pooling, spacing-scaling, alignment tests) would have added real complexity and alignment risk without a measured performance need to justify it. `build_preview_mesh()` always operates at native resolution; `test_downsample_bounds_aligned_if_used` documents this as the current, deliberate contract rather than leaving the requirement silently unaddressed.

## Coordinate convention

`build_preview_mesh()` reuses the EXACT real conversion (`invesalius.data.converters.to_vtk(array, spacing, 0, "AXIAL")`) and the EXACT real pre-contour `vtkImageFlip` step the authoritative final-surface pipeline uses - not an independently-derived transform. Verified for real, not just by construction: `test_matches_real_final_surface_pipeline_bounds` re-runs the literal real pipeline steps (`to_vtk` + `vtkImageFlip` + `vtkContourFilter` at isovalue 127) inline in the test and asserts the bounds match the preview mesh's own bounds to within `1e-6` on a representative anisotropic-spacing (real dataset `0051` spacing convention) mask. `test_axis_order_correct`/`test_spacing_correct` additionally pin the exact per-axis mapping using a deliberately non-cubic, non-isotropic test case (so a silent axis swap or spacing-collapse would be caught, not hidden by symmetry).

## PreviewSurfaceManager3D

`core/preview_surface_3d.PreviewSurfaceManager3D` mirrors `core/marker_3d.CrosshairMarker3D`'s `attach()`/`detach()` lifecycle exactly (same reason: the real 3D renderer is a singleton that outlives any single `ROIViewerFrame`). Owns exactly one `vtkActor`/`vtkPolyDataMapper` pair; `set_polydata_if_current()` swaps the mapper's input polydata in place - never creates a second actor.

## Actor lifecycle

Created once in `attach()`; `set_polydata_if_current()` updates the SAME actor's mapper (`SetInputData()` + `Modified()`); `clear()` hides without detaching (actor/mapper stay ready for the next update); `detach()` removes from the renderer entirely and bumps `generation_id`. Real tests: `test_attach_once`, `test_attach_twice_no_duplicate`, `test_attach_to_new_renderer_moves_not_duplicates`, `test_plugin_reopen_no_duplicate_actor`.

## Source priority

`SegmentationPanel._select_preview_3d_source()`: if `preview_mgr.state == PREVIEW_READY` and `preview_array` is not `None`, use the E2 preview (read-only - never copied into `Project().mask_dict`, never Accepted/Cancelled automatically, never modified). Otherwise fall back to the real current mask's logical voxel region (`mask.matrix[1:, 1:, 1:]` - never the padding, per Section 14's re-audit). Real tests: `test_e4_current_roi_source`, `test_e4_e2_otsu_preview_source`, `test_e4_e2_region_preview_source`, `test_e2_cancel_clears_or_falls_back`.

## E2 integration

Otsu/Region Growing preview-ready events, and Cancel/Accept, all call the shared `_mark_preview_3d_dirty()` (Otsu/Region-Growing-ready call it directly; Cancel calls it after `cancel_preview()`; Accept reaches it indirectly via `_refresh_after_edit()`, which now calls it unconditionally - see "Internal dirty notification" below). E4 never mutates `preview_mgr`'s own state, never Accepts/Cancels on its own initiative. `test_e2_accept_does_not_duplicate_e4_actor` confirms the manager still owns exactly one actor across a full preview-ready → E4-build → Accept → E4-rebuild-from-new-Current-ROI sequence.

## E3 integration

`_run_cleanup()`'s real (non-no-op) mutation path ends in `_refresh_after_edit()`, which now unconditionally calls `_mark_preview_3d_dirty("mask edited")` - the SAME single shared entry point Undo/Redo/classic-mask-creation paths use, per Section 16's explicit "call one common `mark_preview_3d_dirty`, do not duplicate rebuild logic in each handler" instruction. A true no-op cleanup returns before ever reaching `_refresh_after_edit()`, so it correctly does NOT mark E4 dirty either.

## Internal dirty notification

`_mark_preview_3d_dirty(reason)` is the ONE real entry point (Section 16), called from: `_refresh_after_edit()` (covers classic Region Growing commit, E2 Accept, Undo, Redo, E3 cleanup - 5 real call sites via 1 shared helper), `_on_apply_threshold()`'s success path (classic mask creation), `_on_preview_otsu()`/`_on_region_grown_preview()`'s success paths (E2 preview ready), `_on_preview_cancel()` and `_on_enable_preview_toggle()`'s disable branch (E2 preview cancelled/disabled), `_on_roi_selected()` (ROI switch), and `_on_current_mask_modified()` (the real Brush/Eraser signal below).

## Brush mutation-event audit

Real, source-verified (Section 15/30), not assumed or faked: `invesalius.data.mask.Mask.add_modified_callback(callback)` is a real, pre-existing, public API (`weakref.WeakMethod`-based, safe to register a bound method against). Direct source read of the ENTIRE codebase found exactly 2 real call sites of `Mask.modified()`, both in `invesalius/data/styles.py` - `OnBrushRelease()` (the real `SLICE_STATE_EDITOR` style both Brush and Eraser share, fired on `"LeftButtonReleaseEvent"`) and one other real edit-completion handler. `_ensure_modified_callback_registered_for_current_mask()` registers `_on_current_mask_modified` on whichever mask is current, re-registering (idempotently) whenever `_mark_preview_3d_dirty()` runs or the checkbox is enabled. **Result: `BrushAutoRefresh = WORKING`, not the `PARTIAL` the task's own instructions anticipated as the likely outcome** - a real, reliable native signal was found, not an unsafe mouse-hook interception and not merely a manual-Refresh-only fallback.

## Debounce

`wx.Timer`, 400ms (within the suggested 300-500ms range), restarted (`Stop()` + `StartOnce()`) on every `_mark_preview_3d_dirty()` call - rapid successive dirty-marks coalesce into exactly one rebuild, using whatever state is current when the timer actually fires (not anything snapshotted at dirty-mark time). Real tests (`test_dirty_coalescing`, `test_latest_generation_wins`, `test_no_unbounded_queue`) verify the coalescing CONTRACT (via `PreviewSurfaceManager3D.generation_id`) without relying on real wall-clock sleeps or a running wx event loop - matching how E2's own async contract is tested elsewhere in this suite.

## Async generation guard

`PreviewSurfaceManager3D.generation_id`, bumped by `new_generation()` (before a build starts) and by `clear()`/`detach()` (so a superseded/hidden/disabled preview's in-flight worker result, if any, is automatically rejected on arrival) - the SAME proven concept E2's `SegmentationPreviewManager` already established, reused (not reimplemented) here.

## VTK thread-safety decision

The worker thread (`threading.Thread`, daemon) constructs its OWN fresh, thread-local VTK pipeline objects (`vtkImageData` via `converters.to_vtk()`, `vtkImageFlip`, `vtkFlyingEdges3D`) from a plain numpy snapshot taken before the thread starts - it never touches the renderer, the actor, the mapper, the camera, or any object the main thread might concurrently access. This avoids the real concurrent-shared-VTK-object hazard the strict rule (Section 21/22) warns about; the result (a `vtkPolyData`) is handed back via `wx.CallAfter`, and `_on_preview_3d_built()` is the ONLY code that touches the actor/mapper/renderer, always on the main thread. This differs from the real final-surface pipeline's own approach (full OS-process isolation via `multiprocessing`) - a heavier mechanism appropriate for a slow, authoritative, full-quality build, not proportionate for a fast, best-effort preview.

## Memory

At most one real numpy snapshot (`np.array(source)`) strongly referenced per rebuild (~28MB for a dataset-`0051`-sized volume, same order of magnitude as one Undo/Redo checkpoint) - `generation_id` means an OLD snapshot's worker, once superseded, has nothing further to do with its reference once the callback rejects it; no queue of multiple snapshots is ever held.

## Geometry-alignment validation

Mandatory per Section 24 - satisfied by 3 independent real checks: (1) a known cuboid at known voxel indices, asserting real-world bounds span (`test_bounds_correct`); (2) anisotropic spacing applied correctly per axis, not collapsed/swapped (`test_spacing_correct`, `test_axis_order_correct`, using a deliberately non-cubic shape); (3) a direct bounds comparison against the literal real final-surface pipeline's own classes re-run inline (`test_matches_real_final_surface_pipeline_bounds`) - not a separately-derived approximation.

## Picker safety

`actor.SetPickable(False)` at construction - a real VTK mechanism (`vtkProp.SetPickable`), not a convention this plugin has to separately enforce in `core/picker_3d.py` or anywhere else; any real VTK picker (the plugin's own `PointPicker3D`, Region Growing's seed pick, 3D distance measurement) skips this actor by construction.

## Camera preservation

Verified by real source inspection, not just by omission: `test_camera_never_touched_by_manager_api`/`test_gui_layer_never_touches_camera` assert that neither `core/preview_surface_3d.py` nor any of `segmentation_panel.py`'s E4 methods contain any camera-related VTK call (`GetActiveCamera`, `ResetCamera`, `SetPosition`, `SetFocalPoint`, `SetViewUp`) at all.

## Final-surface isolation

E4 never sends `"Create surface from index"` (grep-confirmed, and verified for real with a live pubsub spy in `test_e4_never_calls_create_surface_from_index`), never creates or reads a `Project().surface_dict` entry (`test_e4_never_creates_project_surface`), and a real pre-existing `surface_dict` entry's identity/count is provably unchanged across multiple E4 rebuilds (`test_final_surface_untouched`).

## Save/Open

`PreviewSurfaceManager3D` has no serialization method and is never referenced by `invesalius/project.py`. A preview mesh is pure runtime VTK state - saving a project while live preview is on saves the real masks exactly as before; on open, the checkbox defaults OFF and the manager starts with zero actors (fresh `SegmentationPanel`/`ROIViewerFrame` construction).

## Lifecycle

`roi_panel.py`'s `on_project_close()`, `on_project_load()`, and `_on_close()` all call `self.preview_surface_3d.detach()` - the SAME real pattern already established for `marker_3d`/`slice_planes_3d`, added at all 3 real hook points (not just close) since a preview mesh built for the OLD project's voxel data is meaningless once a different project loads. `segmentation_panel.py`'s `cancel_live_preview_3d()` (called from its own `_on_destroy()`) stops the debounce timer and unregisters the real `Mask.add_modified_callback()` registration.

## Performance

See "Preview mesh benchmark" above - full-resolution `vtkFlyingEdges3D` build: 0.068s on a representative dataset-`0051`-shaped array. Combined with the 400ms debounce, real end-to-end latency after the LAST edit in a rapid sequence is dominated by the debounce window, not the build itself. No `FAST_PREVIEW_INTERACTIVE_LIMITATION` was hit - the feature ships enabled-by-default-OFF but fully functional, not gated behind a "too slow, manual Refresh only" fallback.

---

# E5 Advanced 3D Visualization Architecture

## Pre-E5 reconciliation

Two real issues, found by this run's own required audit steps, fixed before any E5 feature code:

**Gettext empty-string UI bug** (a real operator report: the Segmentation tab was observed rendering raw gettext catalogue metadata - `Project-Id-Version`, `Report-Msgid-Bugs-To`, `PO-Revision-Date`, `Language-Team`, `Plural-Forms`, `X-Poedit-...` - displacing the Preview Workflow controls). Root cause, confirmed by directly reading `invesalius/i18n.py`: `tr` wraps a real `gettext.translation(...).gettext` function, and `gettext("")` on a REAL loaded `.mo` catalogue is documented, standard gettext behaviour - `msgid ""` maps to the catalogue's own PO header block, not an empty string. This plugin's own `_(s): return s` fallback (used only when `invesalius.i18n` cannot be imported, e.g. some test contexts) does not exhibit the bug - only the real InVesalius i18n system does, exactly the real-application case the operator hit. 7 real occurrences of `_("")` were found in `gui/segmentation_panel.py` (3x `wx.StaticText` construction, 4x `.SetLabel()` calls) and fixed to a plain `""` literal. `tests/ct3d/test_no_empty_gettext_calls.py` is a permanent regression guard (scans the whole plugin source for the pattern).

**E4 worker-concurrency audit/hardening**: re-reading `SegmentationPanel._trigger_preview_3d_rebuild()` (E4) found a real, confirmed gap - `generation_id` (`core/preview_surface_3d.py`) only discards a STALE worker's *result*, it never bounded how many workers could be simultaneously IN FLIGHT. Repeated "Refresh 3D Preview" clicks, or a Refresh landing while a debounced worker was still running, could spawn an unbounded number of simultaneous `threading.Thread` workers, each holding its own ~28MB numpy snapshot strongly referenced at once. Hardened to "max 1 running build + max 1 latest pending request": `_e4_build_busy` gates a new build from starting while one is in flight (covering both the async worker path and the synchronous early-return paths); `_e4_pending_reason` remembers only the LATEST coalesced reason requested meanwhile; `_finish_preview_3d_build()` is the one place that clears the busy flag and launches exactly one more rebuild if a newer request arrived. `generation_id` is unchanged and still separately guards stale RESULTS - this hardening is a second, independent guarantee, not a replacement. 5 real tests (`tests/ct3d/test_preview_surface_concurrency.py`) exercise the real, unmodified gating methods against a stubbed build function, deterministically (no dependence on real thread timing).

## Native slice display audit (E5A)

Read directly: `invesalius/data/viewer_slice.py` (`SliceViewer.set_slice_number()`'s `self.slice_data.actor.SetInputData(image)`, where `actor` is a real `vtkImageActor` and `image` comes from `self.slice_.GetSlices(...)`), `invesalius/data/slice_.py` (`Slice.GetSlices()`, `do_ww_wl()`, `do_colour_image()`, `do_blend()`, `get_aux_slice()`/`aux_matrices`/`to_show_aux` - the same real overlay mechanism E2's preview already reuses). Real finding: `Slice().GetSlices(orientation, slice_number, number_slices=1, inverted=False, border_size=0)` returns the EXACT real `vtkImageData` the native 2D viewer displays for that slice - already reflecting real Window/Level (`do_ww_wl()`), the real greyscale-to-RGB colour table (`do_colour_image()`), the current mask's real colour blend (`do_blend()`) if one is shown, AND any active E2 preview overlay (`to_show_aux`) if one is active. E5A reuses this exact real output rather than reimplementing Window/Level math independently (this run's Section 7 explicit preference) - the texture a user sees is, by construction, pixel-for-pixel the same real display data the 2D view already shows for that slice.

## Texture source

`Slice().GetSlices()`, called once per orientation per real crosshair event (only while texture mode is on - Section 11's performance guard), from `ROIViewerFrame.update_textured_slice_planes()`, itself called from the SAME existing C8 `on_cross_focal_point_changed()` event path `marker_3d`/`slice_planes_3d` already use (no parallel crosshair observer created).

## Coordinate convention (E5A)

`core/textured_slice_planes_3d.plane_geometry_from_image_bounds()` derives a textured plane's (origin, point1, point2) directly from the real per-slice image's own `GetBounds()` - never independently recomputed from spacing/shape - so it is provably consistent with whatever real spacing/extent convention `converters.to_vtk()` used to build that image (the exact same convention `SlicePlanes3D._update_geometry()`'s own hardcoded per-axis formula already uses). Which axis is degenerate (min == max) self-describes the orientation (Axial: flat in Z; Coronal: flat in Y; Sagittal: flat in X - the real, proven world-axis mapping, see `core/surface_clipping_3d.py`'s own citation trail below), so the SAME formula produces the correct 3 corners for any of the 3 orientations without a separate orientation string needing to agree with the bounds. `tests/ct3d/test_textured_slice_planes_3d.py::test_geometry_and_texture_same_world_plane` directly cross-checks this against `SlicePlanes3D`'s own real, already-shipped Axial formula and confirms exact numeric coincidence.

## Texture orientation proof

`core/textured_slice_planes_3d.build_textured_plane_polydata()` builds an explicit quad (4 points, 1 cell) with explicit per-corner texture coordinates - NOT `vtkPlaneSource`'s auto-generated TCoords - so the image-to-world mapping is fully explicit and independently testable. Real, empirical (not assumed) proof obtained this milestone: for each of the 3 real orientation strings, a deliberately non-symmetric synthetic image (4 distinct corner values, non-square shape) was built via the real `converters.to_vtk()`, and the world position of each of the 4 quad corners was directly cross-checked against that real image's own `GetScalarComponentAsDouble()` value at the corresponding voxel index - confirming, for real, that this module's own geometry/TCoord-assignment code correctly correlates each world corner with the correct real image voxel (`tests/ct3d/test_textured_slice_planes_3d.py`'s `test_axial/coronal/sagittal_texture_orientation`).

**Honest residual limitation**: this does NOT additionally prove how VTK's own GPU texture unit samples a given TCoord against the uploaded image at actual render time (the strongest possible proof, and the one this run's own instructions explicitly asked for - "must catch horizontal mirror / vertical mirror / axis swap / 90-degree rotation" via a real render). This was attempted during this milestone's audit: a real off-screen `vtkRenderWindow` (`SetOffScreenRendering(1)`) + `vtkWindowToImageFilter` pixel-readback pipeline was built and tested step by step. Every step up to and including `renwin.Render()` (actor/mapper/texture construction, camera setup) succeeded without error. `vtkWindowToImageFilter.Update()` (the framebuffer read-back call) reproducibly segfaulted - and this was confirmed to be a real, environment-level VTK/graphics limitation, not a defect in this module's own code, by reproducing the IDENTICAL segfault with a plain untextured `vtkSphereSource` actor and no texture code involved at all. Per this run's own explicit instruction ("if textured slice planes cannot be implemented safely... DO NOT fake them... set `PARTIAL`"), this specific claim is reported as `PARTIAL`, not `PASS` - real operator manual QA (`E5-B`/`E5-C`/`E5-D` in `CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md`) is the authoritative verification of live-rendered pixel orientation, not yet run.

## Window/Level integration

`Slice().GetSlices()` already bakes real Window/Level into the image it returns (`do_ww_wl()`) - a fresh call to it (which `update_textured_slice_planes()` always performs, never caching a previous image) therefore automatically reflects whatever Window/Level is current at call time, with no separate W/L-change-event subscription needed. Real result: `WindowLevelAutoRefresh = WORKING`, not the `PARTIAL` (manual-Refresh-only) outcome this run's own instructions anticipated as the likely honest fallback.

## Textured-plane lifecycle

`core/textured_slice_planes_3d.TexturedSlicePlanes3D` mirrors `SlicePlanes3D`'s/`CrosshairMarker3D`'s attach()/detach() pattern exactly - exactly 3 actors, created once, geometry+texture updated in place on every `update_plane()` call (never recreated), so scrolling/crosshair movement never grows the renderer's actor count. `actor.SetPickable(False)` at construction (Section 14). Default OFF (`cb_texture_planes` unchecked); enabling hides C8's existing geometric planes and shows the textured ones instead (never both at once, avoiding the z-fighting Section 13 explicitly calls out); disabling restores the geometric planes to whatever "Show slice planes in 3D" is currently set to.

## Surface actor/mapper audit (E5B)

Read `invesalius/data/surface.py` directly. Two real, load-bearing findings:

1. **`mask_index == surface_index` is NOT a safe assumption - it is, in fact, provably FALSE in general.** `Surface` (the class backing `Project().surface_dict` entries) has no mask-index field anywhere. `SurfaceManager.AddNewActor()`'s real overwrite path (the exact path this plugin's own `_on_update_surface()` always exercises via `overwrite=True`) assigns the newly-built `Surface`'s `.index` from `self.last_surface_index` - a single GLOBAL "most recently touched surface" counter shared across ALL masks, not the mask index that was rebuilt.
2. **`SurfaceManager.actors_dict` (index -> real `vtkActor`) is private state this plugin has no direct reference to** (`SurfaceManager` lives inside `invesalius.control.Controller`, never exposed). The real, already-existing, already-used-elsewhere (`invesalius/gui/task_efield.py`) way to fetch a real actor for a known surface index is the real pubsub request/reply pair `Publisher.sendMessage("Get Actor", surface_index=...)` -> `SurfaceManager.GetActor()` -> `Publisher.sendMessage("Send Actor", e_field_actor=...)`, synchronous within the same call stack for a single subscriber.

## Clipping architecture

`core/surface_clipping_3d.SurfaceClipping3D` owns exactly one real `vtkPlane` and tracks exactly one "owned" `vtkMapper` at a time. Uses the standard, real `vtkMapper.AddClippingPlane(vtkPlane)`/`RemoveClippingPlane()` API - clips display at the mapper level, never touches the mapper's input polydata (`vtkClipPolyData` was explicitly NOT used, per this run's own instruction). Ownership discipline: never calls `RemoveAllClippingPlanes()` (which could remove a plane something else added) - only ever adds/removes the exact `vtkPlane` instance it itself owns, on the exact mapper it itself added it to.

## Clipping target

Current ROI Final Surface (default) or Live Preview (E4), selectable via a `wx.Choice` in `interaction_panel.py`. Current ROI resolution: `SegmentationPanel._roi_surface_index` (a `mask_index -> surface_index` dict) is populated ONLY from surface builds THIS plugin's own `_on_update_surface()` itself triggered - guarded by `_pending_surface_build_mask_index`, set right before sending `"Create surface from index"` and consumed by the very next real `"Update surface info in GUI"` event (fired with the actual just-created `Surface` object). Live Preview resolution reuses `preview_surface_3d.mapper` directly (already a real, first-class attribute) - Section 25's "same vtkPlane safely attached/detached with no lifecycle conflict" is satisfied because clipping-plane state lives on a mapper independently of `set_polydata_if_current()`'s own `SetInputData()` calls, so the two never conflict.

## Plane origin/normal mapping

Real, proven world-axis mapping (not assumed): world X = SAGITAL (fastest-varying image axis), Y = CORONAL, Z = AXIAL slice stack - confirmed by TWO independent, already-tested real sources that had to agree with each other for either to be correct: `interface/project_interface.py`'s `ProjectInterface.voxel_to_world()`/`world_to_voxel()` docstrings, and `core/slice_planes_3d.py`'s own real, already-shipped geometry (Axial plane constant in Z, Coronal constant in Y, Sagital constant in X). A clipping plane's normal for a given orientation is the SAME axis that orientation's geometric plane is constant along. `Invert` multiplies the normal by -1 (`tests/ct3d/test_surface_clipping_3d.py`'s `test_axial/coronal/sagittal_normal`, `test_invert_normal`).

## Crosshair integration

`SurfaceClipping3D.set_origin()` is called unconditionally (cheap - a plain `vtkPlane.SetOrigin()`) from the SAME real C8 crosshair event path (`on_cross_focal_point_changed()`) `marker_3d`/`slice_planes_3d`/E5A's own texture update already use - Section 19's explicit "one spatial source of truth" requirement (no second, independent clipping-position slider).

## ROI-switch handling

`SegmentationPanel._on_roi_selected()` and `_on_surface_info_updated()` both call `InteractionPanel.refresh_clipping_target()`, which re-resolves the real mapper for whatever target is currently selected (no-op if clipping itself is disabled). `SurfaceClipping3D.set_target_mapper()` detaches from the OLD mapper (only if it actually owned a plane there) before adopting the new one - `tests/ct3d/test_surface_clipping_3d.py`'s `test_roi_switch_detaches_old_mapper`.

## Surface-rebuild handling

A surface rebuild (`_on_update_surface()`) always produces a NEW real `vtkActor`/`vtkPolyDataMapper` (`AddNewActor()`'s real overwrite path still creates a fresh actor even when overwriting the same surface index) - `_on_surface_info_updated()` triggers `refresh_clipping_target()` again after every real build this plugin itself triggered, re-resolving and re-binding the owned plane to the NEW mapper (`test_surface_rebuild_rebinds_mapper`). No dangling mapper reference is ever kept.

## E4 interaction

Textured planes and clipping both coexist safely with E4's live preview actor in the same renderer (`tests/ct3d/test_e5_cross_feature.py::test_textured_planes_coexist_with_e4_preview`) - independent actors, independent visibility, no shared state beyond the mapper reference clipping optionally targets (E5B.4).

## C8 preservation

Neither `core/textured_slice_planes_3d.py` nor `core/surface_clipping_3d.py` imports `marker_3d`/`CrosshairMarker3D` at all (verified via real AST inspection, not a prose grep - `test_e5_preserves_c8_marker`). `SlicePlanes3D`'s own real API (attach/set_bounds/update_position/set_visible) is exercised directly in a test alongside a co-attached `TexturedSlicePlanes3D` in the same renderer, proving no interference (`test_e5_preserves_c8_geometric_planes`).

## Picker safety

E5A's own 3 actors: `SetPickable(False)` at construction (same mechanism every other renderer-attached plugin actor already uses). E5B (clipping): never touches the TARGET surface's own actor's `SetPickable()` state at all - a real final-surface actor's pre-existing pickable state (whatever native code set it to) survives `enable()`/`disable()` completely untouched (`test_clipping_does_not_block_picker`).

## Camera preservation

Source-inspection guarantee (same real technique E4's own `test_camera_never_touched_by_manager_api` established): neither E5 core module, nor `InteractionPanel`'s/`ROIViewerFrame`'s new E5 methods, contain any camera-related VTK call (`test_camera_unchanged`).

## Save/Open

Both E5A and E5B are pure runtime VTK/display state - `TexturedSlicePlanes3D`/`SurfaceClipping3D` have no serialization method and are never referenced by `invesalius/project.py`. Saving/reopening a project is unaffected; both features default back to OFF on reopen (fresh `ROIViewerFrame`/`InteractionPanel` construction).

## Performance

Real measurement this milestone: `converters.to_vtk()` (the dominant real per-slice conversion cost inside `Slice().GetSlices()`) on a representative 512x512 uint8 slice - **0.04ms average** (20 runs). 3 orientations per real crosshair event (only while texture mode is on) - **~0.13ms** total, negligible relative to the 2D/3D render itself. `do_ww_wl()`/`do_colour_image()` are the SAME real VTK LUT-based filters the native 2D viewer already runs on every slice scroll - no additional cost profile beyond what InVesalius's own 2D views already pay continuously. Clipping-plane enable/disable/origin updates are pure mapper-state operations - negligible cost, no surface regeneration.
