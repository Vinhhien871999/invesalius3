# CT3D Advanced E3 — Segmentation Cleanup

## Metadata

| Field | Value |
|---|---|
| Date | 24/09/2026 |
| Branch | `enhancement/advanced-segmentation` (NOT the stable `thesis-ct-roi-tools`/tag `ct3d-rc1`) |
| Base commit (E2) | `4e28ff0c` — "Advanced segmentation E2: add preview-confirm workflow" |
| This is NOT Phase 15. The CT3D Phase 08-14 software roadmap remains COMPLETE and untouched. |

## Source-first audit

Read/re-read in full or targeted before any E3 code: `plugins/roi_viewer/core/segmentation.py`, `plugins/roi_viewer/core/segmentation_preview.py`, `plugins/roi_viewer/core/mask_editor.py`, `plugins/roi_viewer/core/roi_manager.py`, `plugins/roi_viewer/gui/segmentation_panel.py`, `plugins/roi_viewer/gui/roi_panel.py`, and - the explicit re-audit requirement for this milestone - `invesalius/data/mask.py`'s `Mask.create_mask()` and `invesalius/data/slice_.py`'s `do_threshold_to_all_slices()`, re-read directly rather than relied on from earlier phases' memory.

## Mask/padding convention

`Mask.create_mask(shape)` allocates `matrix` shaped `(shape[0]+1, shape[1]+1, shape[2]+1)` - confirmed directly. Real data is `matrix[1:, 1:, 1:]`. `do_threshold_to_all_slices()` (re-read in full) iterates ONLY axial slices and checks/sets ONLY `mask.matrix[n, 0, 0]` - never a Coronal/Sagittal sentinel. E3's real mask write therefore: writes only into `mask.matrix[1:, 1:, 1:]`, then sets `mask.matrix[1:, 0, 0] = 1` for every axial slice - the same defensive pattern `_on_region_grown()` already established, confirmed still correct and sufficient by this fresh re-read, and now applied to an EXISTING mask being modified (a live risk: a mask that never had a surface built, or was never fully scrolled through in 2D, can still have unvisited sentinels).

## Connectivity decision

6-connected (`DEFAULT_CONNECTIVITY = 1`, `scipy.ndimage.generate_binary_structure(3, 1)`) - matches `core/segmentation.py.region_growing()`'s own real default (`ndimage.label()` called with no `structure` argument, confirmed 6-connected by that module's own existing comment). Used consistently by every connected-component operation in `core/segmentation_cleanup.py`. Diagonal-only-touching voxels are separate components - locked in by `test_default_connectivity_is_six_connected`.

## Cleanup core architecture

`plugins/roi_viewer/core/segmentation_cleanup.py` (new): pure numpy/scipy, zero `invesalius.*`/wx/pubsub imports. Contract: `(mask) -> (result: uint8 0/255 array, info: dict)`, same shape, input never mutated. Separate `cleanup_stats(before, after, spacing_zyx=None)` for the generic before/after voxel summary shared by all 4 operations.

## Keep Largest Component

6-connected labeling, keeps the largest component. Tie-break: smallest label id (scipy's deterministic raster-scan assignment order) - documented, tested (`test_keep_largest_equal_size_deterministic`), not left as an implementation-order accident.

## Remove Small Islands

`size < min_voxels` removed; `size == min_voxels` kept (documented inclusive-lower-bound reading of "Minimum component size"). `min_voxels < 1` raises `ValueError`. Boundary locked in by `test_remove_small_threshold_boundary`.

## Fill Holes

Real `scipy.ndimage.binary_fill_holes()`. Border-touching background verified (not assumed) to remain unfilled: `test_fill_holes_external_background_unchanged`.

## Smooth algorithm selection

Real comparison (binary closing→opening vs. Gaussian-blur+threshold-0.5) on 5 synthetic phantoms:

| Phantom | Gaussian Δ% | Closing→Opening Δ% |
|---|---|---|
| cube | -10.4% | -10.4% |
| sphere (convex) | -4.4% | **-0.6%** |
| jagged | -5.8% | -13.4% |
| noise (30 specks) | -12.7% | -11.7% |
| thin (1-voxel line) | -100% (destroyed) | -100% (destroyed) |

Both deterministic. **Closing→opening chosen**: far less volume drift on the convex sphere phantom, and reuses the same connectivity/structuring-element convention as the other 3 operations. **Both destroyed the 1-voxel-thin phantom** — a real, shared, documented limitation, not hidden. `iterations` bounded `[1, 5]` (`ValueError` outside), not unbounded.

## Cleanup targets

**Current ROI only, this milestone.** Active Preview cleanup was audited and explicitly deferred: E2's Otsu Accept (`_commit_threshold_mask()`) recreates a mask from its recorded `(lo, hi)` threshold, NOT from an array - cleaning `preview_array` and then Accepting would silently commit the un-cleaned original. Region Growing's Accept (`_commit_region_growing_result()`) DOES commit an arbitrary array directly and could safely support it, but shipping cleanup for Region-Growing-previews only (while Otsu previews stayed silently unsupported or unsafe) was judged a worse, more confusing outcome than deferring the whole target consistently, with the exact reason documented. **No correctness compromise was made to claim this feature partially.**

## E1 Lock integration

`_run_cleanup()` delegates to the same pure `ROIManager.is_locked_for_mask_index()` E1's other guards already use - no duplicated lock state. Verified: `test_cleanup_locked_roi_refused` (real mask, nothing changes), `test_cleanup_unlocked_roi_allowed`.

## Undo/Redo integration

`_run_cleanup()` calls the EXISTING `controller.mask_mgr`/`UndoRedoManager.save_state()` exactly once per real (non-no-op) mutation - no E3-specific undo stack. Exact array-equality round-trips verified for all 4 operations: `test_keep_largest_undo_exact`, `test_keep_largest_redo_exact`, `test_remove_small_undo_exact`, `test_fill_holes_undo_exact`, `test_smooth_undo_exact`.

## E2 Preview integration

None this milestone (Active Preview cleanup deferred - see "Cleanup targets" above). E1 interaction confirmed real via tests; E2/Preview interaction is moot since Current-ROI-only cleanup never touches `preview_mgr` or the aux overlay at all.

## Accepted-preview correctness

Not applicable this milestone (no preview-cleanup path exists to commit). The correctness requirement itself (deferred Preview cleanup rather than committing an uncleaned array under a "cleaned" label) is exactly what drove the "Cleanup targets" decision above.

## Surface semantics

`_run_cleanup()` never sends `"Create surface from index"` - verified with a real pubsub spy asserting zero calls (`test_cleanup_does_not_build_surface`). `mask.was_edited = True` is set (Phase 08 D9/C7 policy), surface intentionally stays stale, status message tells the user how to refresh it manually.

## Statistics

`cleanup_stats()` (before/after voxels, delta, delta%, optional mm³) plus each operation's own `info` dict, shown together in the real status message. `test_cleanup_stats`/`test_cleanup_stats_with_spacing` verify the numbers.

## Performance

Measured on a dataset-`0051`-shaped array (108×512×512, ≈3.75M real foreground voxels, 435 components):

| Operation | Runtime |
|---|---|
| Keep Largest Component | 0.54s |
| Remove Small Islands | 0.53s |
| Fill Holes | 0.71s |
| Smooth (iterations=1) | 0.70s |
| Smooth (iterations=5) | 1.19s |

**Decision: synchronous, no threading** - all comfortably under 1.2s even at max iterations, measured before deciding (not a default guess).

## Memory

At most a small constant number of same-shape scipy working arrays plus one `before` copy per operation call - no new persistent/long-lived array retained (unlike E2's preview, which deliberately keeps one array alive while `PREVIEW_READY`).

## Tests

40 new tests, 0 removed: `tests/ct3d/test_segmentation_cleanup.py` (27, unit, pure `core/segmentation_cleanup.py`), `tests/ct3d/test_segmentation_cleanup_integration.py` (13, integration, real `Mask()`/`Slice()`/`Project()`/`UndoRedoManager`/`ROIManager`).

## Regression

`tests/ct3d -q`: **274 passed, 1 skipped, 0 failed** (was 234/1/0 after E2) - verified identical across 5 consecutive runs. Upstream `tests --ignore=tests/ct3d -q`: **94 passed**, unchanged.

**Real regression found and fixed during this milestone**: adding this file's real-`Mask()` integration tests (a third module independently reusing "one real `Slice()`/`Project()` per module") caused real, deterministic failures in E2's own previously-passing `test_segmentation_preview_commit.py` tests - a genuine, reproducible cross-file pypubsub-subscription-accumulation bug in the shared test infrastructure, not a flaky artifact (reproduced identically across repeated runs before the fix, and confirmed gone across 5 repeated runs after). Root cause and fix: see `docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md`'s "Known test-infrastructure issue found and fixed this milestone" section and `tests/ct3d/conftest.py`'s new `real_slice_and_project_singleton` fixture docstring. This was caught and fixed within this milestone's own regression pass, per the explicit stop-on-regression instruction - nothing was shipped broken.

## Static analysis

`pyflakes plugins/roi_viewer`: exit 0. `compileall plugins/roi_viewer`: exit 0. `git diff --check`: exit 0.

## Manual QA

`docs/CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md`'s E3 section: 13 items, all `NOT_RUN`. E1 (0/14) and E2 (0/12) sections left completely unchanged - no fabricated operator evidence added anywhere.

## Known limitations

- Active Preview cleanup target: deferred (see "Cleanup targets" above) - a real, deliberate scope decision, not an oversight.
- Group/category metadata (E1, still deferred, unrelated to E3).
- Both smoothing candidates (and therefore E3's shipped `smooth_binary_mask()`) destroy 1-voxel-thin structures at any iteration count ≥1 - a real, measured, shared limitation of binary morphological/blur-based smoothing at that scale, not something a different iteration count fixes.
- On Windows, constructing multiple real `invesalius.data.mask.Mask()` objects with temp-file-backed matrices within one test process can produce a harmless `PermissionError`/`AttributeError` from `Mask.__del__`'s temp-file cleanup racing with Python's own object finalization order - a pre-existing InVesalius characteristic (not introduced by E3), surfaces only as a `PytestUnraisableExceptionWarning`, never fails a test.

## Files changed

New: `plugins/roi_viewer/core/segmentation_cleanup.py`, `tests/ct3d/test_segmentation_cleanup.py`, `tests/ct3d/test_segmentation_cleanup_integration.py`, `docs/CT3D_ADVANCED_E3_CLEANUP_REPORT.md` (this file). Modified: `plugins/roi_viewer/gui/segmentation_panel.py` (Cleanup UI + `_run_cleanup()` + 4 handlers), `tests/ct3d/conftest.py` (new session-scoped `real_slice_and_project_singleton` fixture - pure addition, no existing fixture behavior changed), `tests/ct3d/test_segmentation_preview_commit.py` + `tests/ct3d/test_segmentation_preview_overlay.py` (both switched to the shared session fixture, fixing the cross-file regression above), `docs/CT3D_ADVANCED_SEGMENTATION_ROADMAP.md`/`ARCHITECTURE.md`/`PROGRESS.md`/`MANUAL_QA.md` (E3 sections added; E2's stale `ENABLE_PREVIEW_SEGMENTATION` doc drift also corrected per this run's Section 3), `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md` (E3 usage, enhancement-branch-only).

## Gate

`E3_GATE: PASS` (Current ROI target - all 25 base criteria from the originating task's Section 33 met: correct branch, E2 baseline confirmed then re-confirmed clean after the regression fix, stale E2 flag documentation fixed, 4 operations implemented deterministically, logical shape/padding/sentinel preserved, lock blocks real-mask cleanup, undo/redo exact, `was_edited` correct, no automatic surface build, statistics correct, no-op safe, E1/E2/D9-C7/C8 regression all PASS via the full 274-test suite, upstream PASS, pyflakes PASS, compile PASS, docs updated, manual evidence honestly `NOT_RUN`, no E4/E5/E6 implementation slipped in). Criteria 26-30 (Active Preview cleanup specifics) do not apply - that target was deferred, not attempted unsafely, per the explicit instruction "If Preview cleanup cannot satisfy #27 safely: disable/defer Preview cleanup. Do NOT compromise correctness merely to claim the feature."

## Next recommendation

E4 — Fast Live 3D Preview, per the roadmap's priority order (E1→E2→E3→E4 before E5/E6).
