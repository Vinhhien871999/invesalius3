# CT3D Advanced Segmentation E2 — Preview / Confirm

## 1. Metadata

| Field | Value |
|---|---|
| Date | 24/09/2026 |
| Branch | `enhancement/advanced-segmentation` (NOT the stable `thesis-ct-roi-tools`/tag `ct3d-rc1`) |
| Base commit (E1) | `11d81dbb` — "Advanced segmentation E1: add enhanced ROI management" |
| This is NOT Phase 15. The CT3D Phase 08-14 software roadmap remains COMPLETE and untouched. |

## 2. Source-first audit

Read in full before any E2 code: `plugins/roi_viewer/core/segmentation.py`, `plugins/roi_viewer/core/mask_editor.py`, `plugins/roi_viewer/gui/segmentation_panel.py` (full threshold/region-growing/undo-redo bodies), `plugins/roi_viewer/gui/roi_panel.py` (lifecycle hooks). Targeted reads of `invesalius/data/slice_.py` (mask creation/colour/threshold pipeline, and specifically its `aux_matrices`/`to_show_aux` render-blend logic) and `invesalius/data/styles.py` (the real `WatershedInteractorStyle`). This audit is what determined the entire preview-rendering design in §3 — it was not assumed.

## 3. Preview rendering architecture

No temporary `Project().mask_dict` entry was needed. The audit found a real, already-shipped, native mechanism: `invesalius.data.slice_.Slice.aux_matrices` (a `dict[str, np.ndarray]`) + `.to_show_aux` (a string key), blended into the 2D slice render after the normal mask blend, via `do_custom_colour()`/`do_blend()`. This is the exact real path InVesalius's own Watershed tool uses for its live segmentation preview (`invesalius/data/styles.py`'s `WatershedInteractorStyle.SetUp()`/`CleanUp()`). E2's `SegmentationPanel._show_preview_overlay()`/`_clear_preview_overlay()` mirror it directly: allocate via the real `Slice.create_temp_mask()` (same method Watershed uses), write the candidate array, set `aux_matrices["roi_viewer_preview"]`/`to_show_aux`, redraw via `Publisher.sendMessage("Reload actual slice")` (already used elsewhere in this plugin). See `docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md`'s "E2 Preview Architecture" section for the full trail. `Project().mask_dict` is never touched before Accept — confirmed both by code inspection (the preview-computation methods contain no `"Create new mask"` call) and by real tests (`test_segmentation_preview_commit.py`'s `*_does_not_create_project_mask` tests, asserting `len(proj.mask_dict) == 0` against a live `Project()` singleton).

## 4. State machine

`core/segmentation_preview.SegmentationPreviewManager`: `IDLE` → `new_generation()` → `COMPUTING` → `set_otsu_preview()`/`set_region_growing_preview()` → `PREVIEW_READY` → `begin_accept()` → `ACCEPTING` → `finish_accept()` → `IDLE`. `cancel()` reachable from any state, always lands on `IDLE`. `revert_accept()` (`ACCEPTING` → `PREVIEW_READY`) added for the oversized-region-declined/commit-failed case, preserving preview data rather than discarding it. Pure Python/numpy, zero `invesalius.*`/wx/pubsub imports — 13 unit tests in `tests/ct3d/test_segmentation_preview.py`, all PASS.

## 5. Otsu preview

`_on_preview_otsu()` calls the real, unmodified `SegmentationManager.auto_threshold_otsu()`/`apply_threshold()` — the SAME methods the classic Otsu checkbox already uses. Accept calls `_commit_threshold_mask()`, extracted from the classic `_on_apply_threshold()` handler so both paths share one real commit with the exact threshold the preview showed. Real tests: `otsu_preview_does_not_create_project_mask`, `otsu_preview_threshold_matches_existing_otsu`, `otsu_accept_creates_one_real_mask`, `otsu_accept_uses_same_threshold_as_preview`, `otsu_cancel_creates_no_mask`, `otsu_classic_mode_unchanged_when_flag_off` — all PASS against a real `Slice()`/`Project()`.

## 6. Region Growing preview

Seed-pick UX unchanged (`btn_pick_seed`, same real 3D picker). With Preview Workflow enabled, `_on_seed_picked()` now only records the seed instead of auto-growing; an explicit "Preview Region Growing" click starts the (still background-threaded, `wx.CallAfter`-marshalled) computation using the Tolerance value at click time. `_commit_region_growing_result()` was extracted from the classic `_on_region_grown()` handler's tail so Accept reuses the identical real mask-creation/matrix-write/`was_edited=True` commit. Real tests: `region_preview_does_not_create_mask`, `region_preview_matches_existing_region_growing_output`, `region_preview_stats_match`, `oversized_region_warning_state_preserved`, `region_accept_creates_exactly_one_mask`, `region_cancel_creates_zero_masks`, `was_edited_semantics_preserved`, `test_classic_region_growing_unchanged_when_flag_off` — all PASS.

## 7. Accept semantics

`begin_accept()` gates entry: returns `False` (no-op) if not `PREVIEW_READY`, covering both "nothing to accept" and "already accepting" (rapid double-click). Buttons disabled immediately on entry. For an oversized region, the same real confirmation dialog the classic path shows fires here too, at commit time — declining calls `revert_accept()`, preserving the preview rather than losing it. On success: overlay cleared, `finish_accept()`, `controller.on_roi_source_changed()`, status updated. Verified: exactly one `Project().mask_dict` entry results (`otsu_accept_creates_one_real_mask`, `region_accept_creates_exactly_one_mask`).

## 8. Cancel semantics

Shared `cancel_preview()`: clears the real overlay, calls `preview_mgr.cancel()` (bumps `generation_id`, clears all data, state → `IDLE`), clears the recorded seed. Creates zero project masks (`otsu_cancel_creates_no_mask`, `region_cancel_creates_zero_masks`). Safe no-op when already `IDLE` (`test_cancel_idle_safe_noop`).

## 9. Async race protection

`generation_id`, bumped by `new_generation()` and by `cancel()`/`finish_accept()`. `set_*_preview()` checks staleness first, returns `False` (no mutation) for a stale result — proven with the exact "request 1 starts, request 2 starts, request 1 finishes late" scenario (`test_generation_id_rejects_stale_result`, `test_stale_async_region_result_ignored`).

## 10. Lifecycle

`SegmentationPanel.cancel_preview()` called from `roi_panel.py`'s `on_project_close()` AND `on_project_load()` (defensive, even though close-then-load already covers the normal project-swap flow), and from `segmentation_panel.py`'s own `_on_destroy()`, unconditionally (not gated behind the brush-specific early return). Widget-touching cleanup wrapped separately from data cleanup, defends against `RuntimeError` on an already-destroyed wx widget (same real crash class documented for the existing brush-toggle destroy handler). Manager-level lifecycle proven by `test_project_close_clear`/`test_plugin_close_clear`; full wx-widget teardown is not automatable and is listed in the manual QA checklist (E2-I, E2-J) instead of faked.

## 11. Save/Open isolation

`SegmentationPreviewManager` has no serialization method and no real `invesalius.*` import at all. Nothing in E2 writes to any `Mask`/`Project` field before Accept. No change was made to `invesalius/project.py`.

## 12. E1 interaction

Lock: Otsu/Region Growing always create NEW masks (never write into an existing locked one), so a locked current ROI does not block preview generation. Solo: the preview overlay renders via a completely separate real mechanism (`aux_matrices`/`to_show_aux`) from per-ROI `Show mask`/`is_shown` — confirmed by reading the render method, the aux blend is unconditional regardless of any specific mask's visibility — so Solo has zero effect on the preview overlay. Show All/Hide All: only touch `ROI.visible`/`"Show mask"`, never `preview_mgr` or the aux overlay.

## 13. C8 interaction

The preview overlay creates no VTK actor/prop at all (a 2D raster blend into each slice's own `vtkImageData`, same as a real mask's own colour blend). Cannot intercept 3D picking, cannot obstruct the C8 marker/slice planes (entirely different rendering pipeline — 3D `Viewer` vs. 2D slice views), cannot interfere with measurement tools, never touches a `vtkCamera`. `test_overlay_is_not_actor_based_pickability_not_applicable` confirms by construction (no `GetPickable` method on the stored data).

## 14. Memory

`Slice.create_temp_mask()`: `dtype=uint8`, real volume shape, memmap-backed (disk, not pure RAM). For dataset `0051` (108×512×512 ≈ 28.3M voxels): ≈28.3MB per preview array — same order of magnitude as one Undo/Redo checkpoint (Phase 10: ≈27.36MB). At most one preview array live at a time (`_reset_metadata()` drops the previous reference before a new one is set); no accumulation across generations. Backing temp file always removed on cancel/accept/lifecycle cleanup.

## 15. Tests added

35 new tests, 0 removed: `tests/ct3d/test_segmentation_preview.py` (13, unit, state machine), `tests/ct3d/test_segmentation_preview_commit.py` (15, integration, real `Slice()`/`Project()`/pubsub), `tests/ct3d/test_segmentation_preview_overlay.py` (7, integration, real `Slice()` overlay mechanism).

## 16. Regression

`tests/ct3d -q`: **234 passed, 1 skipped, 0 failed** (was 199/1/0 after E1) — verified identical across 3 consecutive runs. Upstream `tests --ignore=tests/ct3d -q`: **94 passed**, unchanged.

## 17. Static analysis

`pyflakes plugins/roi_viewer`: exit 0. `compileall plugins/roi_viewer`: exit 0. `git diff --check`: exit 0 (no whitespace errors).

## 18. Manual QA status

`docs/CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md`'s E2 section: 12 items, all `NOT_RUN`. No fabricated operator evidence.

## 19. Files changed

New: `plugins/roi_viewer/core/segmentation_preview.py`, `tests/ct3d/test_segmentation_preview.py`, `tests/ct3d/test_segmentation_preview_commit.py`, `tests/ct3d/test_segmentation_preview_overlay.py`, `docs/CT3D_ADVANCED_E2_PREVIEW_REPORT.md` (this file). Modified: `plugins/roi_viewer/gui/segmentation_panel.py` (Preview UI, `_commit_threshold_mask()`/`_commit_region_growing_result()` extraction, preview handlers, overlay helpers, lifecycle hook), `plugins/roi_viewer/gui/roi_panel.py` (`cancel_preview()` calls in `on_project_close()`/`on_project_load()`), `docs/CT3D_ADVANCED_SEGMENTATION_ROADMAP.md` (E1 naming correction, E2 status), `docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md` (E2 section added), `docs/CT3D_ADVANCED_SEGMENTATION_PROGRESS.md` (E1 naming correction, E2 table), `docs/CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md` (E2 section added), `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md` (E2 usage, enhancement-branch-only).

## 20. Known limitations

- Preview's 2D overlay only renders once a current mask already exists — a real, pre-existing InVesalius constraint (shared with Watershed's own overlay), not an E2-specific gap; documented and guarded with a clear user-facing message.
- No live 3D surface preview (explicitly out of scope for E2 — that is E4).
- Full wx-widget-teardown lifecycle (project close/plugin close while a preview is visible) is verified at the manager/data level by automated tests, but the complete real-window teardown path is not automatable and is deferred to manual QA (E2-I/E2-J), consistent with how this project has always separated automated from manual GUI evidence.
- Group/category metadata for E1 remains deferred (unrelated to E2, carried over from E1's own known limitations).

## 21. E2 Gate

`E2_GATE: PASS` — all 25 criteria in the originating task's Section 30 checklist met: correct branch, clean baseline, classic workflow preserved (proven structurally, not just behaviorally), preview never creates a Project mask, preview visibly renders in 2D (via the real native overlay mechanism), Otsu Preview/Accept/Cancel work, Region Growing Preview/Accept/Cancel work, async stale result rejected, no duplicate preview overlay entries, no memory accumulation across previews, lifecycle cleanup passes at the manager level, Save/Open remains untouched, E1 tests remain PASS (199/199 carried forward, part of the 234 total), CT3D suite PASS, upstream suite PASS, pyflakes PASS, compile PASS, docs updated, manual QA honestly `NOT_RUN`, no E3/E4/E5/E6 implementation slipped in.

## 22. Next recommendation

E3 — Segmentation cleanup tools (Keep Largest Component / Remove Small Islands / Fill Holes / Smooth Mask), per the roadmap's priority order (E1→E2→E3→E4 before E5/E6).
