# CT3D — Advanced Segmentation Enhancement Track: Progress

> Live status table. See `docs/CT3D_ADVANCED_SEGMENTATION_ROADMAP.md` for scope and `docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md` for the real design decisions behind each row. **Never mark `WORKING` without real evidence** (automated test PASS for backend/logic claims, real operator GUI session for manual claims) - matches the same evidence discipline as the Phase 08-14 roadmap's `CT3D_FEATURE_AUDIT.md`.

**Status vocabulary**: `PLANNED` / `AUDITED` / `IN_PROGRESS` / `WORKING` / `PARTIAL` / `BLOCKED` / `EXPERIMENTAL`.

## E1 — Multi-label / Advanced ROI Management

| ID | Feature | Backend | UI | Tests | Manual | Status |
|---|---|---|---|---|---|---|
| E1.1 | Active ROI indicator | `ROIManager.current_roi_id`/`get_current_roi()` (pre-existing) | `lbl_active_roi` label, updated on selection + list refresh | `test_active_roi_selection` PASS | `NOT_RUN` | **WORKING** |
| E1.2 | Colour indicator | `ROI.color` (pre-existing) | `roi_color_swatch` panel | covered indirectly (colour stored/read correctly, pre-existing coverage) | `NOT_RUN` | **WORKING** |
| E1.3 | Visibility (per ROI) | `ROI.visible` (pre-existing) | `roi_list` checkbox (pre-existing) | `test_visibility_toggle` + pre-existing `test_rebuild_reflects_visibility_toggle` PASS | `NOT_RUN` | **WORKING** |
| E1.4 | Lock / Unlock | `ROIManager.set_locked()`/`is_locked()`/`is_locked_for_mask_index()` (new) | `btn_roi_lock`/`btn_roi_unlock` buttons, `[LOCKED]` list prefix | `test_lock_prevents_edit`, `test_unlock_restores_edit` PASS | `NOT_RUN` | **WORKING** (backend+guards); manual GUI confirmation pending |
| E1.5 | Solo | `ROIManager.enter_solo()`/`exit_solo()`/`cancel_solo()` (new) | `btn_roi_solo` toggle button, `[SOLO]` list prefix | `test_solo_visibility`, `test_solo_unknown_roi_is_a_noop`, `test_exit_solo_without_active_solo_is_a_noop` PASS | `NOT_RUN` | **WORKING** (backend); manual GUI confirmation pending |
| E1.6 | Show All | `ROIManager.show_all()` (new) | `btn_roi_show_all` button | `test_show_all` PASS | `NOT_RUN` | **WORKING** (backend); manual GUI confirmation pending |
| E1.7 | Hide All | `ROIManager.hide_all()` (new) | `btn_roi_hide_all` button | `test_hide_all` PASS | `NOT_RUN` | **WORKING** (backend); manual GUI confirmation pending |
| E1.8 | Rename | (pre-existing) | `btn_roi_rename` (pre-existing) | pre-existing coverage | `NOT_RUN` | **WORKING** |
| E1.9 | Delete (refuses when locked) | `ROIManager.delete_roi(roi_id, force=False)` (extended) | `btn_roi_delete`, now checks `roi.locked` first | `test_delete_locked_behavior`, `test_delete_locked_solo_target_is_also_refused_and_solo_survives`, `test_delete_unknown_roi_returns_false` PASS | `NOT_RUN` | **WORKING** |
| E1.10 | Group/category metadata | — | — | — | — | **PLANNED** (deliberately deferred - see architecture doc's "Metadata / storage decision") |
| E1.11 | Project sync (rebuild preserves `.locked`, drops orphans, clears stale solo) | `ROIManager.rebuild_from_project_masks()` (extended: `delete_roi(force=True)` for stale entries) | — | `test_roi_project_sync`, `test_rebuild_after_project_load`, `test_no_orphan_roi_with_locked_and_solo_state` PASS | `NOT_RUN` | **WORKING** |
| E1.12 | Save/Open: `.locked` intentionally NOT persisted | `ROI.locked` never written to any real `Mask` field | — | `test_save_open_metadata_roundtrip_if_metadata_added` PASS (confirms non-persistence) | `NOT_RUN` | **WORKING** (as designed - see architecture doc) |

**E1 automated regression this run**: `tests/ct3d -q` = **199 passed, 1 skipped** (was 183 passed/1 skipped before E1 - 16 new tests, 0 removed, 0 failed). Upstream `tests --ignore=tests/ct3d -q` = **94 passed**, unchanged. `pyflakes plugins/roi_viewer` = exit 0. `compileall plugins/roi_viewer` = exit 0.

**E1 manual GUI QA**: see `docs/CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md` - all items `NOT_RUN` (no operator session has happened yet; Claude Code does not fabricate manual GUI evidence).

**E1_GATE: PASS** (automated). Manual GUI confirmation remains open, non-blocking for continuing to plan E2 (per the classic-workflow-preserving design, E1 changes are additive/opt-in within the existing "Segmentation Set" box - no classic control was removed or altered).

## E2 — Preview / Confirm segmentation workflow

`PLANNED`. Not started. Will require: `SegmentationPreviewManager` (states `IDLE`/`PREVIEW_READY`/`ACCEPTING`/`CANCELLED`), applied first to Otsu and Region Growing, with explicit non-goals (must not modify `Project().mask_dict` permanently until Accept, must not pollute Save/Open, must not create duplicate masks, must not push unnecessary Undo history).

## E3 — Segmentation cleanup tools

`PLANNED`. Not started. Will require: `keep_largest_component()`, `remove_small_components()`, `fill_holes()`, `smooth_binary_mask()` - pure numpy/scipy, deterministic, dimension-preserving, integrated with `UndoRedoManager` so every destructive cleanup op is undoable.

## E4 — Fast live 3D preview

`PLANNED`. Not started. Will require a separate `PreviewSurfaceManager` (dirty→debounce→fast low-quality rebuild→actor swap), explicitly never replacing the authoritative D9/C7 "Update 3D Surface" pipeline, measured (not assumed) interactive-editing performance.

## E5 — Advanced 3D visualization

`PLANNED`. Not started. Textured slice planes require investigating whether InVesalius's real VTK pipeline supports this safely (no invented coordinate mapping) before any implementation attempt. Clipping plane is a VTK clipping/display-pipeline feature, must not modify final surface geometry.

## E6 / E6b — AI segmentation architecture / TotalSegmentator

`PLANNED`. Not started, and explicitly not to start before E1-E4 are stable per the roadmap's priority order. No model weights, no fake/mock inference results, no claimed support until real inference has actually succeeded. Default OFF via `ENABLE_AI_SEGMENTATION` when eventually scaffolded.

## Feature flags

| Flag | Default | Status |
|---|---|---|
| `ENABLE_ADVANCED_ROI` | — | **Not yet introduced as an explicit flag this run** - E1's new controls live inside the existing "Segmentation Set" box, additive to (not replacing) the classic Rename/Delete/visibility controls, and every new action (lock/solo/show-all/hide-all) is purely opt-in per-click. A dedicated on/off flag was judged unnecessary risk-wise for E1 specifically (nothing it added can silently change classic-workflow behavior when unused) - this decision, and whether E2+ needs one, is revisited per-milestone. |
| `ENABLE_PREVIEW_SEGMENTATION` | OFF (once E2 exists) | not yet introduced |
| `ENABLE_LIVE_3D_PREVIEW` | OFF (once E4 exists) | not yet introduced |
| `ENABLE_AI_SEGMENTATION` | OFF (once E6 exists) | not yet introduced |
