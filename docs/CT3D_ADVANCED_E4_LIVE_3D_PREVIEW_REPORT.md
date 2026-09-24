# CT3D Advanced E4 — Fast Live 3D Preview

## Metadata

| Field | Value |
|---|---|
| Date | 24/09/2026 |
| Branch | `enhancement/advanced-segmentation` (NOT the stable `thesis-ct-roi-tools`/tag `ct3d-rc1`) |
| Base commit (E3) | `dbbc4a50` — "Advanced segmentation E3: add segmentation cleanup tools" |
| This is NOT Phase 15. The CT3D Phase 08-14 software roadmap remains COMPLETE and untouched. |

## Source-first surface audit

Read directly before any E4 code: `invesalius/data/surface_process.py.create_surface_piece()` (the real per-piece contour worker the authoritative "Update 3D Surface" pipeline dispatches to, one OS process per piece via `invesalius/data/surface.py`'s multiprocessing pool), `invesalius/data/converters.py.to_vtk()`, `invesalius/data/mask.py` (`Mask.create_mask()`, `Mask.modified()`, `Mask.add_modified_callback()`), `invesalius/data/styles.py` (real Brush/Eraser edit-completion call sites), `plugins/roi_viewer/core/marker_3d.py` (the existing `attach()`/`detach()` renderer-lifecycle pattern this milestone reuses), `plugins/roi_viewer/core/slice_planes_3d.py`, `plugins/roi_viewer/gui/roi_panel.py`.

## VTK version / available algorithms

VTK **9.3.0**, confirmed via `vtk.vtkVersion.GetVTKVersion()` (not assumed). Available and benchmarked: `vtkMarchingCubes`, `vtkFlyingEdges3D`, `vtkSurfaceNets3D` (`vtkmodules.vtkFiltersCore`), `vtkDiscreteMarchingCubes`, `vtkDiscreteFlyingEdges3D` (`vtkmodules.vtkFiltersGeneral`). The real final-surface pipeline itself uses the generic `vtkContourFilter` dispatcher.

## Preview mesh benchmark

Real measurements, dataset-`0051`-shaped array (108×512×512, 3,750,263 real foreground voxels), isovalue 127:

| Algorithm | Runtime | Points | Cells | Notes |
|---|---|---|---|---|
| `vtkFlyingEdges3D` | **0.068s** | 186,569 | 372,072 | Identical geometry to MarchingCubes |
| `vtkMarchingCubes` | 0.150s | 186,569 | 372,072 | Same output, 2.2x slower |
| `vtkSurfaceNets3D` | 0.043s | 0 | 0 | Wrong usage contract for isovalue 127 (discrete-label filter) |
| `vtkDiscreteMarchingCubes` | 0.096s | 0 | 0 | Same wrong-contract issue |
| `vtkDiscreteFlyingEdges3D` | 0.025s | 0 | 0 | Same wrong-contract issue |

Downsampled ×2 (simple stride) for reference only: `vtkFlyingEdges3D` 0.009s, 46,439 points.

## Selected algorithm

`vtkFlyingEdges3D`, isovalue 127 (`ComputeNormalsOff`/`ComputeGradientsOff`/`ComputeScalarsOff` for speed — the preview mesh does not need per-vertex normals/scalars to render usefully). Identical output geometry to `vtkMarchingCubes` at 2.2x the speed — a safe same-family substitution, not a different technique that could silently diverge from the real final surface's shape. The 3 discrete/label-based filters were ruled out by real, measured empty output for this exact isovalue-on-continuous-field usage, not by assumption.

## Downsampling decision

Not implemented this milestone. Full resolution already measured comfortably fast (0.068s) for a 400ms-debounced, best-effort preview — no measured performance need to justify the added complexity/alignment risk of block-downsampling. `build_preview_mesh()` always operates at native resolution.

## Coordinate convention

`build_preview_mesh()` reuses the real final-surface pipeline's exact conversion (`converters.to_vtk(array, spacing, 0, "AXIAL")`) and its exact pre-contour `vtkImageFlip(FilteredAxis=1, FlipAboutOriginOn)` step — not an independently-derived transform. Directly verified (not just asserted by construction): `test_matches_real_final_surface_pipeline_bounds` re-runs the literal real pipeline steps inline on a representative anisotropic-spacing mask and asserts bounds match `build_preview_mesh()`'s output to within `1e-6`. `test_axis_order_correct`/`test_spacing_correct` pin the exact per-axis mapping using a deliberately non-cubic shape, so a silent axis swap or spacing collapse would fail, not hide behind symmetry.

## `PreviewSurfaceManager3D`

`plugins/roi_viewer/core/preview_surface_3d.py` (new). Mirrors `core/marker_3d.CrosshairMarker3D`'s `attach()`/`detach()` lifecycle exactly, for the same reason: the real VTK renderer is a singleton that outlives any single `ROIViewerFrame`. Owns exactly one `vtkActor`/`vtkPolyDataMapper` pair, `actor.SetPickable(False)` at construction.

## Actor lifecycle

`attach(renderer)` — idempotent, creates the actor once, moves it to a new renderer if called again with a different one, never duplicates. `set_polydata_if_current(gen, polydata, source_kind=None)` — swaps the SAME actor's mapper input in place; returns `False` (no-op) for a stale generation or before `attach()`. `set_visible(bool)`. `clear()` — hides, bumps generation, keeps actor/mapper ready. `detach()` — removes from renderer, bumps generation. Verified: `test_attach_once`, `test_attach_twice_no_duplicate`, `test_attach_to_new_renderer_moves_not_duplicates`, `test_plugin_reopen_no_duplicate_actor`.

## Source priority

`SegmentationPanel._select_preview_3d_source()`: E2 preview (`preview_mgr.state == PREVIEW_READY` and a preview array present) takes priority; otherwise falls back to Current ROI's logical voxel region (`mask.matrix[1:, 1:, 1:]`, never the padding sentinel, per the E3-established convention). Read-only with respect to E2/E3 state — E4 never mutates, Accepts, or Cancels a preview on its own initiative. Verified: `test_e4_current_roi_source`, `test_e4_e2_otsu_preview_source`, `test_e4_e2_region_preview_source`, `test_e2_cancel_clears_or_falls_back`.

## E2 integration

Otsu-preview-ready, Region-Growing-preview-ready, Accept, and Cancel all reach the one shared `_mark_preview_3d_dirty()` entry point (directly, or indirectly via `_refresh_after_edit()` for Accept). E4 never duplicates the actor across a preview-ready → build → Accept → rebuild-from-new-Current-ROI sequence (`test_e2_accept_does_not_duplicate_e4_actor`).

## E3 integration

`_run_cleanup()`'s real (non-no-op) mutation path ends in `_refresh_after_edit()`, which now unconditionally calls `_mark_preview_3d_dirty("mask edited")` — the same shared entry point Undo/Redo/classic mask creation use, per the "one common dirty-mark function, no duplicated rebuild logic per handler" requirement. A true no-op cleanup returns before reaching `_refresh_after_edit()` and correctly does not mark E4 dirty.

## Brush mutation-event audit

Real, source-verified: `invesalius.data.mask.Mask.add_modified_callback(callback)` is a real, pre-existing, public API (`weakref.WeakMethod`-based — safe against a bound method). A full-codebase grep for `Mask.modified()` found exactly 2 real call sites, both in `invesalius/data/styles.py`, both real edit-completion events for the `SLICE_STATE_EDITOR` style that Brush and Eraser both use. `_ensure_modified_callback_registered_for_current_mask()` registers `_on_current_mask_modified` on the current mask, idempotently re-registered on dirty-mark/toggle-enable. **Result: `BrushAutoRefresh = WORKING`** — the task's own instructions anticipated `PARTIAL` (manual-Refresh-only) as the likely honest outcome; a genuine, reliable native signal was found instead, so no compromise was needed.

## Debounce

`wx.Timer`, 400ms (within the specified 300-500ms range), `Stop()` + `StartOnce()` on every `_mark_preview_3d_dirty()` call — coalesces rapid successive dirty-marks into exactly one rebuild using whatever state is current when the timer fires.

## Async generation guard

`PreviewSurfaceManager3D.generation_id`, bumped by `new_generation()` before a build starts and by `clear()`/`detach()` — reuses the same proven concept as E2's `SegmentationPreviewManager`, not reimplemented independently. A superseded/hidden/disabled preview's in-flight worker result is rejected on arrival by `set_polydata_if_current()`'s staleness check. Verified: `test_dirty_coalescing`, `test_latest_generation_wins`, `test_no_unbounded_queue`.

## VTK thread-safety decision

The worker (`threading.Thread`, daemon) builds its own fresh, thread-local VTK objects from a plain numpy snapshot taken before the thread starts (`converters.to_vtk()`, `vtkImageFlip`, `vtkFlyingEdges3D`) — it never touches the renderer/actor/mapper/camera. The result (`vtkPolyData`) crosses back to the main thread via `wx.CallAfter`; `_on_preview_3d_built()` is the only code touching the actor/mapper/renderer, always on the main thread. Lighter than the real final-surface pipeline's own full OS-process isolation — appropriate for a fast, best-effort, non-authoritative preview rather than a slow, authoritative build. Verified by source inspection: `test_camera_never_touched_by_manager_api`, `test_gui_layer_never_touches_camera`.

## Memory

At most one real numpy snapshot strongly referenced per rebuild (~28MB for a dataset-`0051`-sized volume) — `generation_id` means a superseded worker's snapshot has no further use once its callback is rejected; no queue of multiple snapshots is ever held.

## Geometry-alignment validation

3 independent checks: (1) a known cuboid at known voxel indices, asserting real-world bounds span (`test_bounds_correct`); (2) anisotropic spacing applied correctly per axis on a deliberately non-cubic shape (`test_spacing_correct`, `test_axis_order_correct`); (3) a direct bounds comparison against the literal real final-surface pipeline's own classes re-run inline (`test_matches_real_final_surface_pipeline_bounds`), matching to within `1e-6`.

## Picker safety

`actor.SetPickable(False)` at construction — a real VTK mechanism, not a plugin-side convention to separately maintain; any existing picker (`core/picker_3d.PointPicker3D`, Region Growing's seed pick, measurement tools) skips this actor by construction.

## Camera preservation

`test_camera_never_touched_by_manager_api`/`test_gui_layer_never_touches_camera` assert (via source inspection) that neither `core/preview_surface_3d.py` nor any of `segmentation_panel.py`'s E4 methods contain any camera-related VTK call (`GetActiveCamera`, `ResetCamera`, `SetPosition`, `SetFocalPoint`, `SetViewUp`).

## Final-surface isolation

E4 never sends `"Create surface from index"` (grep-confirmed and verified live with a pubsub spy: `test_e4_never_calls_create_surface_from_index`), never creates or reads a `Project().surface_dict` entry (`test_e4_never_creates_project_surface`), and a real pre-existing `surface_dict` entry's identity/count is unchanged across multiple E4 rebuilds (`test_final_surface_untouched`).

## Save/Open

`PreviewSurfaceManager3D` has no serialization method and is never referenced by `invesalius/project.py`. Saving a project with live preview on saves exactly the same real mask data as without it; on reopen, the checkbox defaults OFF and the manager starts with zero actors (fresh construction).

## Lifecycle

`roi_panel.py`'s `on_project_close()`, `on_project_load()`, and `_on_close()` all call `self.preview_surface_3d.detach()` — the same pattern already used for `marker_3d`/`slice_planes_3d`, added at all 3 hook points since a preview mesh built from the old project's voxel data is meaningless once a different project loads. `segmentation_panel.py`'s `cancel_live_preview_3d()` (called from its own `_on_destroy()`) stops the debounce timer and unregisters the `Mask.add_modified_callback()` registration.

## Performance

Full-resolution `vtkFlyingEdges3D` build: 0.068s on a representative dataset-`0051`-shaped array (see benchmark table above). Combined with the 400ms debounce, real end-to-end latency after the last edit in a rapid sequence is dominated by the debounce window, not the build itself. No interactive-latency limitation was hit — the feature ships functional, default OFF, not gated behind a manual-Refresh-only fallback.

## Tests

44 new tests, 0 removed: `tests/ct3d/test_preview_surface_3d.py` (15, manager lifecycle, real `vtkRenderer`), `tests/ct3d/test_preview_surface_mesh.py` (10, `build_preview_mesh()` geometry/alignment), `tests/ct3d/test_preview_surface_integration.py` (14, real `Mask()`/`Slice()`/`Project()`/`ROIManager` via the shared session-scoped `real_slice_and_project_singleton` fixture), `tests/ct3d/test_preview_surface_debounce.py` (5, generation-id coalescing + camera-never-touched source inspection).

## Regression

`tests/ct3d -q`: **318 passed, 1 skipped, 0 failed** (was 274/1/0 after E3) — verified identical across 3 consecutive runs. Upstream `tests --ignore=tests/ct3d -q`: **94 passed**, unchanged.

## Static analysis

`pyflakes plugins/roi_viewer`: exit 0. `compileall plugins/roi_viewer`: exit 0. `git diff --check`: exit 0.

## Manual QA

`docs/CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md`'s E4 section: 18 items, all `NOT_RUN`. E1 (0/14), E2 (0/12), and E3 (0/13) sections left completely unchanged — no fabricated operator evidence added anywhere.

## Known limitations

- The preview mesh's own geometry-alignment guarantee (matching the real final-surface pipeline's bounds) has only been validated against binary/`from_binary=True`-style masks, matching how the plugin's own "Update 3D Surface from Selected ROI" always builds — raw-image dual-isovalue surfaces are outside this plugin's existing scope entirely (pre-existing, not E4-specific).
- Live 3D preview and the real "Update 3D Surface" pipeline are visually independent: enabling live preview does not mark the real surface as fresh, and building the real surface does not disable live preview — both can be on screen at once. This is an intentional non-authoritative-preview design (per the milestone's own core invariant), not an oversight, but a first-time user could initially find two overlapping meshes confusing without reading the status labels.
- Same Windows `Mask.__del__` temp-file-cleanup `PermissionError`/`AttributeError` characteristic already documented in `CT3D_ADVANCED_E3_CLEANUP_REPORT.md`'s "Known limitations" — pre-existing InVesalius behavior, surfaces only as a harmless `PytestUnraisableExceptionWarning`, never fails a test.

## Files changed

New: `plugins/roi_viewer/core/preview_surface_3d.py`, `tests/ct3d/test_preview_surface_3d.py`, `tests/ct3d/test_preview_surface_mesh.py`, `tests/ct3d/test_preview_surface_integration.py`, `tests/ct3d/test_preview_surface_debounce.py`, `docs/CT3D_ADVANCED_E4_LIVE_3D_PREVIEW_REPORT.md` (this file). Modified: `plugins/roi_viewer/gui/roi_panel.py` (`preview_surface_3d` manager, `ensure_preview_surface_attached()`, `request_render()`, `detach()` at all 3 lifecycle hooks), `plugins/roi_viewer/gui/segmentation_panel.py` (3D Preview UI box, debounce timer, `_mark_preview_3d_dirty()` and its call sites, `_select_preview_3d_source()`, `_trigger_preview_3d_rebuild()`, `_on_preview_3d_built()`, `cancel_live_preview_3d()`, Brush/Eraser auto-refresh registration, Smooth Mask tooltip warning), `docs/CT3D_ADVANCED_SEGMENTATION_ROADMAP.md`/`ARCHITECTURE.md`/`PROGRESS.md`/`MANUAL_QA.md` (E4 sections added), `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md` (Section 3.3e E4 usage; Section 3B Otsu-Accept-recomputes correction; Section 3C Smooth Mask thin-structure warning, both per this run's Section 3 documentation-fix requirement).

## Gate

`E4_GATE: PASS` — real source-first surface-pipeline audit performed, real benchmark drove the algorithm choice (not assumption), `PreviewSurfaceManager3D` follows the established attach/detach single-actor pattern, source priority (E2 preview > Current ROI) implemented and tested, debounce + generation-id guard implemented and tested (reusing E2's proven concept), Brush/Eraser auto-refresh genuinely `WORKING` (real `Mask.add_modified_callback()`, not a fabricated hook), strict thread-safety rule upheld (worker never touches wx/renderer/camera), geometry-alignment proven against the literal real final-surface pipeline to `1e-6`, picker safety and camera preservation both verified, final-surface isolation verified (never touches `surface_dict`, never sends `"Create surface from index"`), Save/Open unaffected, lifecycle cleanup added at all 3 existing hook points, regression clean (318/1/0, upstream 94 unchanged), static analysis clean, manual QA honestly `NOT_RUN` (18 items), all 3 required documentation corrections (Section 3 A/B/C) applied, no E5/E6 implementation slipped in.

## Next recommendation

E5 — Advanced 3D visualization (textured planes, clipping), per the roadmap's priority order (E1→E2→E3→E4 before E5/E6).
