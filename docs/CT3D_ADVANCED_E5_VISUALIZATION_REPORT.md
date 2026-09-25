# CT3D Advanced E5 — Advanced 3D Visualization

## Metadata

| Field | Value |
|---|---|
| Date | 25/09/2026 |
| Branch | `enhancement/advanced-segmentation` (NOT the stable `thesis-ct-roi-tools`/tag `ct3d-rc1`) |
| Base commit (E4) | `7611b475` — "Advanced segmentation E4: add fast live 3D preview" |
| This is NOT Phase 15. The CT3D Phase 08-14 software roadmap remains COMPLETE and untouched. |

## Branch / baseline

Confirmed via `git status`/`git status -sb`/`git branch --show-current`/`git rev-parse HEAD`/`git log --graph --decorate --oneline -20` before any edit: correct branch, worktree clean, HEAD = `7611b475`, `thesis-ct-roi-tools`/`ct3d-rc1` both still at `aa1b3ad3`. Pre-edit regression: `tests/ct3d -q` = 318 passed/1 skipped, upstream 94 passed, matching the documented E4 baseline exactly.

## Pre-E5 documentation fixes

**A. `ENABLE_LIVE_3D_PREVIEW` flag drift**: `CT3D_ADVANCED_SEGMENTATION_PROGRESS.md`'s feature-flag table said "OFF (once E4 exists) / not yet introduced" even though E4 is implemented. Verified the real source name first (`grep` confirmed `cb_enable_live_3d_preview` in `gui/segmentation_panel.py`), then corrected the row to **IMPLEMENTED / WORKING** with the real checkbox name cited.

**B. `CT3D_ADVANCED_SEGMENTATION_ROADMAP.md`'s E3 scope note historical wording**: previously read "E4-E6 remain planned only - no E4-E6 code exists yet", stale now that E4 exists. Corrected to explicitly preserve history ("At the time E3 was completed, E4-E6 had not yet been implemented - E4 was implemented subsequently") rather than rewritten as if E4 existed during E3.

## Gettext UI bug reconciliation

A real operator previously observed the Segmentation tab rendering gettext catalogue metadata (`Project-Id-Version`, `Report-Msgid-Bugs-To`, `PO-Revision-Date`, `Language-Team`, `Plural-Forms`, `X-Poedit-...`) displacing the Preview Workflow controls. Searched production plugin code for `_("")`/`_('')`/`gettext("")` patterns: **STILL_PRESENT** - 7 real occurrences found, all in `gui/segmentation_panel.py` (3x `wx.StaticText(self, wx.ID_ANY, _(""))` construction, 4x `.SetLabel(_(""))` calls). Root cause confirmed by directly reading `invesalius/i18n.py`: `tr` wraps a real `gettext.translation(...).gettext` function, and calling `gettext("")` against a REAL loaded `.mo` catalogue is documented, standard gettext behaviour (`msgid ""` maps to the catalogue's own PO header block) - not a made-up theory. All 7 occurrences replaced with a plain `""` literal (i18n itself left fully intact - no global disabling). Added `tests/ct3d/test_no_empty_gettext_calls.py` as a permanent regression guard (scans the whole plugin source for the pattern).

## E4 concurrency audit/hardening

Audited the real E4 implementation (`SegmentationPanel._trigger_preview_3d_rebuild()`). `generation_id` (`core/preview_surface_3d.py`) was confirmed to only discard a stale worker's *result* - it never bounded how many workers could be simultaneously IN FLIGHT. Real, confirmed gap: the "Refresh 3D Preview" button called `_trigger_preview_3d_rebuild()` directly and unconditionally, with no serialization against an already-running debounced worker - repeated rapid clicks (or a Refresh landing while a debounced worker was still running) could spawn an unbounded number of simultaneous `threading.Thread` workers, each holding its own ~28MB numpy snapshot strongly referenced at once.

Hardened to **max 1 running worker + max 1 latest pending request**: `_e4_build_busy` (bool) gates a new build from starting while one is already in flight (covering both the async worker path and every synchronous early-return path - "no 3D view yet", "no foreground voxels", "snapshot failed" all now count as "in flight" too, for the same one-at-a-time guarantee); `_e4_pending_reason` remembers only the LATEST coalesced reason requested meanwhile (older ones are silently superseded, never queued); `_finish_preview_3d_build()` is the single place that clears the busy flag and, if a newer request arrived, launches exactly one more rebuild for it. `generation_id` is unchanged and still separately guards stale RESULTS - this hardening is a second, independent guarantee, not a replacement.

**Real numbers, before vs. after**: before, N rapid "Refresh" clicks while enabled could produce up to N concurrent worker threads and N concurrent ~28MB snapshots. After: **max concurrent workers = 1**, **max concurrent snapshots = 1**, proven by 5 real tests (`tests/ct3d/test_preview_surface_concurrency.py`) exercising the real, unmodified gating methods against a stubbed build function (deterministic, no real-thread-timing dependency): `test_only_one_worker_running`, `test_dirty_while_running_coalesces`, `test_latest_pending_runs_after_current`, `test_pending_cancelled_on_disable`, `test_pending_cancelled_on_project_close`.

## Native slice display audit

Read directly: `invesalius/data/viewer_slice.py` (`SliceViewer.set_slice_number()`'s `self.slice_data.actor.SetInputData(image)`, `actor` a real `vtkImageActor`), `invesalius/data/slice_.py` (`Slice.GetSlices()`, `do_ww_wl()`, `do_colour_image()`, `do_blend()`, the real `aux_matrices`/`to_show_aux` overlay mechanism E2 already reuses), `invesalius/data/converters.py` (`to_vtk()`'s real per-orientation extent/dimension formulas - re-verified empirically this milestone, see "Coordinate convention" below), `invesalius/data/surface.py` (`AddNewActor()`, `CreateSurfaceFromPolydata()`, `SurfaceManager.actors_dict`/`GetActor()`/`"Get Actor"`/`"Send Actor"`), `interface/view_interface.py`, `interface/project_interface.py`, `core/marker_3d.py`, `core/slice_planes_3d.py`, `core/preview_surface_3d.py`, `gui/interaction_panel.py`, `gui/segmentation_panel.py`, `gui/roi_panel.py`.

**Key real finding**: `Slice().GetSlices(orientation, slice_number, number_slices=1, inverted=False, border_size=0)` returns the EXACT real `vtkImageData` the native 2D viewer displays for that slice - already reflecting real Window/Level, the real greyscale-to-RGB colour table, the current mask's real colour blend if one is shown, and any active E2 preview overlay if one is active.

## Texture source

`Slice().GetSlices()`, reused directly (Section 7's explicit preference over reimplementing Window/Level math) - never an independently-derived colour/intensity pipeline.

## Coordinate convention

`core/textured_slice_planes_3d.plane_geometry_from_image_bounds()` derives a textured plane's 3 corners directly from the real per-slice image's own `GetBounds()` (never independently recomputed) - the degenerate axis (min == max) self-describes the orientation. Verified this reproduces `converters.to_vtk()`'s real per-orientation extent placement for real, empirically, for all 3 orientations (not assumed from reading the source alone): a deliberately non-square, non-symmetric 5x7 synthetic array's 4 real corner values were traced through `converters.to_vtk()` for AXIAL/CORONAL/SAGITAL and matched exactly against the expected `(origin, point1, point2, opposite)` -> `(0,0)/(0,-1)/(-1,-1)/(-1,0)`-value correspondence in all 3 cases. Cross-checked directly against `core/slice_planes_3d.SlicePlanes3D`'s own real, already-shipped geometry formula and confirmed numerically coincident (`tests/ct3d/test_textured_slice_planes_3d.py::test_geometry_and_texture_same_world_plane`).

## Preview mesh benchmark

Not applicable to E5 (E4's own benchmark, unchanged, is in `CT3D_ADVANCED_E4_LIVE_3D_PREVIEW_REPORT.md`). E5's own real measurement is under "Performance" below.

## Selected algorithm

Not applicable (no new contour/mesh algorithm introduced by E5 - clipping uses the standard real `vtkMapper.AddClippingPlane()` API; texture uses `vtkTexture` directly on the real per-slice image, no contouring).

## Downsampling decision

Not applicable (E5 does not build a volumetric mesh).

## `PreviewSurfaceManager3D`

Not applicable to E5 directly - see "E4 interaction" below for how E5B's clipping optionally targets it.

## Actor lifecycle

`core/textured_slice_planes_3d.TexturedSlicePlanes3D`: exactly 3 actors, mirrors `SlicePlanes3D`'s/`CrosshairMarker3D`'s attach()/detach() pattern exactly, geometry+texture updated in place via `update_plane()` (never recreated). `core/surface_clipping_3d.SurfaceClipping3D`: exactly one real `vtkPlane`, one "owned" mapper tracked explicitly at a time - `enable()`/`disable()` never call `RemoveAllClippingPlanes()`, only ever add/remove the exact plane instance this class itself owns.

## Source priority

Not applicable in E4's sense (E5 has no preview-array-vs-current-ROI choice). E5B's own analogous choice - "Current ROI Final Surface" vs. "Live Preview (E4)" as the clipping **target** - is covered under "Clipping target" below.

## `PreviewSurfaceManager3D` / E2 integration

Not applicable (E5 does not read or depend on E2's preview state).

## E3 integration

Not applicable (E5 does not read or depend on E3's cleanup operations directly - though a cleaned Current ROI's rebuilt final surface is a valid clipping target like any other).

## Brush mutation-event audit

Not applicable to E5 - E5A's textures are refreshed via the real C8 crosshair event path (Section 11), and E5B's clipping-plane position is refreshed the same way; neither depends on `Mask.add_modified_callback()` (E4's own concern).

## Debounce

E5A texture rebuilds only happen on a real crosshair event, gated behind `self.show_texture_planes` (Section 11's performance guard) - no separate debounce timer needed since these events already arrive at real user-interaction pace, and the per-orientation cost is negligible (see "Performance" below). E5B clipping-origin updates are a plain `vtkPlane.SetOrigin()` call - no debounce needed at all.

## Async generation guard

Not applicable - E5A/E5B both do all their real work synchronously on the main thread (no background worker thread is spawned by either feature).

## VTK thread-safety decision

Not applicable - see "Async generation guard" above.

## Memory

E5A holds at most one real per-orientation `vtkImageData` reference per plane at a time (replaced, not accumulated, on every `update_plane()` call - same "update in place" discipline as E4's actor). E5B holds no image/array data at all - only a `vtkPlane` (a handful of floats) and a `vtkPolyDataMapper` reference.

## Geometry-alignment validation

E5A: see "Coordinate convention" above - real, empirical, per-orientation proof. E5B: `test_axial_normal`/`test_coronal_normal`/`test_sagittal_normal`/`test_invert_normal` (real, proven world-axis mapping - see "Plane origin/normal mapping" in the architecture doc for the full citation trail) plus `test_crosshair_moves_plane_origin`.

## Texture orientation proof

Real, empirical (not assumed) geometry-to-real-image-index correspondence proven for all 3 orientations (see "Coordinate convention" above and `tests/ct3d/test_textured_slice_planes_3d.py`'s `test_axial/coronal/sagittal_texture_orientation`). **Honest residual limitation**: this does not additionally prove how VTK's own GPU texture unit samples a given texture coordinate against the uploaded image at actual render time - the strongest possible proof, and the one explicitly requested (a real off-screen render with a non-symmetric image, checking for horizontal/vertical mirror, axis swap, or 90-degree rotation).

**What was attempted**: a real off-screen `vtkRenderWindow` (`SetOffScreenRendering(1)`) + `vtkWindowToImageFilter` pixel-readback pipeline, built and tested incrementally in this dev environment. Actor/mapper/texture/camera construction and `renwin.Render()` all succeeded without error at every step. `vtkWindowToImageFilter.Update()` (the framebuffer read-back call) reproducibly segfaulted. This was confirmed to be a real, environment-level VTK/graphics limitation - **not** a defect in this module's own code - by reproducing the IDENTICAL segfault using a plain untextured `vtkSphereSource` actor with no texture code involved at all, and by confirming `SetMultiSamples(0)`/`ReadFrontBufferOff()` (standard offscreen-crash workarounds) did not change the outcome.

Per this run's own explicit instruction ("if textured slice planes cannot be implemented safely because no reliable native texture/orientation/WL path exists: DO NOT fake them... set `PARTIAL`"), this specific claim is honestly reported as `PARTIAL`, not `PASS` - the underlying WL/data source path (`Slice().GetSlices()`) IS fully reliable and reused correctly; what could not be additionally verified in this environment is the live-rendered pixel-sampling direction. **No live-render test was added to the committed suite** - doing so would have reproduced this same segfault inside `pytest`, taking down the entire regression run rather than failing one test, which would have been strictly worse than reporting the honest limitation. Real operator manual QA (`E5-B`/`E5-C`/`E5-D`) is the authoritative verification, not yet run.

## Window/Level integration

`Slice().GetSlices()` already bakes real Window/Level into its output (`do_ww_wl()`) - every `update_textured_slice_planes()` call performs a fresh call, never caching a previous image, so the next real crosshair event after any Window/Level change automatically reflects it. Result: `WindowLevelAutoRefresh = WORKING`, not the `PARTIAL` (manual-Refresh-only) fallback this run's own instructions anticipated as the likely honest outcome. Proven by `test_window_level_refresh_if_supported` (two different real intensity values fed through the real update path, both correctly reflected).

## Textured-plane lifecycle

`attach()`/`detach()` at all 3 real hook points (`on_project_load()`, `on_project_close()`, `_on_close()` in `roi_panel.py`), mirroring `marker_3d`/`slice_planes_3d`/`preview_surface_3d` exactly. Default OFF (`cb_texture_planes` unchecked); enabling hides C8's geometric planes and shows the textured ones (never both at once, avoiding z-fighting); disabling restores geometric planes to whatever "Show slice planes in 3D" is set to.

## Surface actor/mapper audit

See the architecture doc's "Surface actor/mapper audit (E5B)" section for the full writeup. Two real, load-bearing findings: (1) `mask_index == surface_index` is provably FALSE in general - `Surface` has no mask-index field, and `AddNewActor()`'s real overwrite path (the exact path this plugin's own rebuild button exercises) assigns the resulting surface's `.index` from a GLOBAL `last_surface_index` counter, not the mask index. (2) `SurfaceManager.actors_dict` is private state with no direct plugin reference - the real `"Get Actor"`/`"Send Actor"` pubsub pair (already used by `invesalius/gui/task_efield.py` for the identical real need) is the safe, real way to resolve an actor from a known surface index.

## Clipping architecture

`core/surface_clipping_3d.SurfaceClipping3D` - real `vtkMapper.AddClippingPlane(vtkPlane)`/`RemoveClippingPlane()`, never `vtkClipPolyData`, never touches the mapper's input polydata. Ownership discipline: never calls `RemoveAllClippingPlanes()` - only ever adds/removes the exact `vtkPlane` instance this class itself owns, on the exact mapper it itself added it to (`test_roi_switch_detaches_old_mapper`, `test_surface_rebuild_rebinds_mapper` both directly verify a DIFFERENT mapper's own clipping-plane collection is left untouched).

## Clipping target

Current ROI Final Surface (default): `SegmentationPanel._roi_surface_index` (mask_index -> surface_index), populated ONLY from surface builds THIS plugin's own `_on_update_surface()` itself triggered - guarded by `_pending_surface_build_mask_index`, consumed by the very next real `"Update surface info in GUI"` event. Live Preview (E4): `preview_surface_3d.mapper` reused directly (already a real, first-class attribute) - safe to attach/detach a clipping plane to it since clipping-plane state lives on the mapper independently of `set_polydata_if_current()`'s own `SetInputData()` calls (verified: `test_textured_planes_coexist_with_e4_preview` proves no interference between E5 objects and E4's own actor in the same renderer).

## Plane origin/normal mapping

Real, proven world-axis mapping (not assumed): world X = SAGITAL, Y = CORONAL, Z = AXIAL - confirmed by two independent, already-tested real sources agreeing (`ProjectInterface.voxel_to_world()`/`world_to_voxel()` docstrings + `SlicePlanes3D`'s own real geometry). `Invert` multiplies the normal by -1. `test_axial_normal`/`test_coronal_normal`/`test_sagittal_normal`/`test_invert_normal` all PASS.

## Crosshair integration

`SurfaceClipping3D.set_origin()` called unconditionally (cheap) from the SAME real C8 event path `marker_3d`/`slice_planes_3d` already use - Section 19's "one spatial source of truth" requirement satisfied, no second/parallel crosshair observer created.

## ROI-switch handling

`_on_roi_selected()` and `_on_surface_info_updated()` both call `InteractionPanel.refresh_clipping_target()` (no-op if clipping itself is disabled). `set_target_mapper()` detaches from the OLD mapper first (only if it actually owned a plane there). `test_roi_switch_detaches_old_mapper` PASS.

## Surface-rebuild handling

A rebuild always produces a NEW real `vtkActor`/`vtkPolyDataMapper` - `_on_surface_info_updated()` triggers `refresh_clipping_target()` again after every real build this plugin itself triggered, rebinding the owned plane to the new mapper. `test_surface_rebuild_rebinds_mapper` PASS. No dangling mapper reference is ever kept (`SurfaceClipping3D.detach()` clears it on project/plugin close).

## E4 interaction

Both E5A and E5B coexist safely with E4's own actor in the same renderer, with independent visibility and no shared mutable state beyond the mapper reference E5B optionally targets (`test_textured_planes_coexist_with_e4_preview` PASS).

## C8 preservation

Neither E5 core module imports `marker_3d`/`CrosshairMarker3D` at all - verified via real AST inspection (`test_e5_preserves_c8_marker`), not a prose grep (both modules' own docstrings legitimately MENTION `marker_3d` in prose when explaining their own design lineage - a naive substring check on that prose was caught and fixed during this milestone's own test-writing pass, see "Regression" below). `SlicePlanes3D`'s own real API exercised directly alongside a co-attached `TexturedSlicePlanes3D`, proving no interference (`test_e5_preserves_c8_geometric_planes` PASS).

## Picker safety

E5A's own 3 actors: `SetPickable(False)` at construction. E5B: never touches the TARGET surface's own actor's `SetPickable()` state - proven directly (`test_clipping_does_not_block_picker`: a real actor's pre-existing `SetPickable(True)` state survives `enable()`/`disable()` completely untouched).

## Camera preservation

Source-inspection guarantee (same real technique E4's own tests established): neither E5 core module nor the new E5 GUI methods (`InteractionPanel`'s texture/clip handlers, `ROIViewerFrame.update_textured_slice_planes()`) contain any camera-related VTK call (`test_camera_unchanged` PASS).

## Save/Open

Both `TexturedSlicePlanes3D` and `SurfaceClipping3D` have no serialization method and are never referenced by `invesalius/project.py` - pure runtime display state. Both default back to OFF on reopen (fresh `ROIViewerFrame`/`InteractionPanel` construction).

## Performance

Real measurement: `converters.to_vtk()` (the dominant real per-slice conversion cost inside `Slice().GetSlices()`) on a representative 512x512 uint8 slice - **0.04ms average** (20 runs). 3 orientations per real crosshair event (only while texture mode is on) - **~0.13ms** total. Clipping-plane enable/disable/origin updates are pure mapper-state operations - negligible, no surface regeneration, no measurable cost above baseline.

## Tests

49 new tests, 0 removed: `tests/ct3d/test_textured_slice_planes_3d.py` (18), `tests/ct3d/test_surface_clipping_3d.py` (17), `tests/ct3d/test_preview_surface_concurrency.py` (5, Section 5 hardening), `tests/ct3d/test_e5_cross_feature.py` (8, Section 33 cross-feature), `tests/ct3d/test_no_empty_gettext_calls.py` (1, Section 4 regression guard).

## Regression

`tests/ct3d -q`: **367 passed, 1 skipped, 0 failed** (was 318/1/0 after E4) - verified identical across 3 consecutive runs. Upstream `tests --ignore=tests/ct3d -q`: **94 passed**, unchanged.

**Real regressions found and fixed during this milestone** (all caught and fixed within this same milestone's own regression pass, per the explicit stop-on-regression instruction - nothing shipped broken):

1. Adding `_finish_preview_3d_build()`'s call inside `_on_preview_3d_built()` (Section 5 hardening) broke 4 of E4's own previously-passing tests in `test_preview_surface_integration.py` - their lightweight `types.SimpleNamespace` test double bound only the specific `SegmentationPanel` methods it needed, and didn't yet know about the new required `_finish_preview_3d_build()`/`_e4_pending_reason` state. Fixed by extending `_panel_like()`'s fake to bind the new method and initialize the new attribute.
2. `test_e5_cross_feature.py::test_clipping_does_not_rebuild_surface`'s bare `Publisher.subscribe(lambda **kw: ..., "Create surface from index")` spy, if it happened to run before ANY real `Slice()` had been constructed yet this session (a real risk once this new, alphabetically-early-named test file was added), would itself become the first-ever subscriber to that topic and incorrectly fix its pypubsub message-argument spec from its own permissive signature - causing a real, deterministic `ListenerMismatchError` the next time a real `Slice()` was constructed elsewhere in the session (`Slice.CreateSurfaceFromIndex(self, surface_parameters)`'s own real subscription). Fixed by adding a dependency on the shared `real_slice_and_project_singleton` fixture, guaranteeing a real `Slice()` (and therefore the topic's real, correct spec) already exists before the spy subscribes.
3. Two of this milestone's own new cross-feature tests initially asserted a naive substring absence (`"marker_3d" not in source`) to prove E5 modules don't reference C8's marker - this incorrectly flagged the modules' OWN docstrings, which legitimately mention `marker_3d`/`CrosshairMarker3D` in prose when explaining the real attach()/detach() lifecycle pattern being mirrored. Fixed by switching to real AST-based import inspection (only actual `import`/`from...import` statements count, not prose).

## Static analysis

`pyflakes plugins/roi_viewer`: exit 0. `compileall plugins/roi_viewer`: exit 0. `git diff --check`: exit 0. (`pyflakes tests/ct3d` reports 11 pre-existing findings in files this milestone did not touch - none in any of the 5 new E5 test files; matches E1-E4's own established convention of gating on `pyflakes plugins/roi_viewer`, not the test suite.)

## Manual QA

`docs/CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md`'s E5 section: 22 items (E5-A through E5-V), all `NOT_RUN`. E1 (0/14), E2 (0/12), E3 (0/13), and E4 (0/18) sections left completely unchanged - no fabricated operator evidence added anywhere.

## Known limitations

- **Texture orientation** (E5A.4): real geometry/index-correspondence proven mathematically and empirically; live-rendered pixel-sampling direction could not be additionally proven in this dev environment due to a real, reproducible `vtkWindowToImageFilter` offscreen-readback segfault (isolated and confirmed environment-level, not module-specific). See "Texture orientation proof" above.
- **Current ROI Final Surface clipping target** only resolves for surfaces THIS plugin's own "Update 3D Surface from Selected ROI" button has itself built this session - a surface built via InVesalius's native Surface tab (bypassing this plugin entirely) has no tracked mask->surface mapping and will correctly report "No final surface for selected ROI." rather than guess. This is a deliberate, honest scope limit (Section 16's own "never guess" instruction), not an oversight.
- E5A's texture reuses whatever the real 2D view is currently showing, including the current mask's colour blend and any active E2 preview overlay - this was a deliberate simplicity choice (Section 7: reuse the real output as-is) rather than a separate "raw CT only" mode; a first-time user could find a mask-tinted or preview-tinted 3D texture plane surprising without reading the status text.
- Same Windows `Mask.__del__` temp-file-cleanup `PermissionError`/`AttributeError` characteristic already documented in `CT3D_ADVANCED_E3_CLEANUP_REPORT.md`'s/`CT3D_ADVANCED_E4_LIVE_3D_PREVIEW_REPORT.md`'s "Known limitations" - pre-existing InVesalius behaviour, harmless `PytestUnraisableExceptionWarning`, never fails a test.

## Files changed

New: `plugins/roi_viewer/core/textured_slice_planes_3d.py`, `plugins/roi_viewer/core/surface_clipping_3d.py`, `tests/ct3d/test_textured_slice_planes_3d.py`, `tests/ct3d/test_surface_clipping_3d.py`, `tests/ct3d/test_preview_surface_concurrency.py`, `tests/ct3d/test_e5_cross_feature.py`, `tests/ct3d/test_no_empty_gettext_calls.py`, `docs/CT3D_ADVANCED_E5_VISUALIZATION_REPORT.md` (this file). Modified: `plugins/roi_viewer/gui/roi_panel.py` (E5 manager instances, lifecycle detach calls, `update_textured_slice_planes()`, crosshair-event integration), `plugins/roi_viewer/gui/interaction_panel.py` (3D Visualization UI box, texture/clipping handlers, `refresh_clipping_target()`), `plugins/roi_viewer/gui/segmentation_panel.py` (7x `_("")` gettext fix, E4 concurrency hardening, mask_index->surface_index tracking, ROI-switch clipping-refresh hook), `tests/ct3d/test_preview_surface_integration.py` (fixed the E4-concurrency-hardening regression above), `docs/CT3D_ADVANCED_SEGMENTATION_ROADMAP.md`/`ARCHITECTURE.md`/`PROGRESS.md`/`MANUAL_QA.md` (E5 sections added, pre-E5 doc drift fixed), `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md` (E5 usage, enhancement-branch-only).

## Gate

`E5_GATE: PARTIAL`. All 38 base criteria met EXCEPT #8 ("texture orientation proven") - the sub-claim is `PARTIAL` for the real, documented, environment-level reason above (not faked, not silently skipped). Every other criterion is fully met: correct branch (1), E4 baseline PASS (2), stale Progress flag fixed (3), stale Roadmap E3 wording fixed (4), gettext-header UI issue reconciled and STILL_PRESENT->FIXED (5), E4 worker concurrency proven bounded and hardened (6), texture source audited from real code (7), textured planes optional/default OFF (9), existing C8 planes preserved (10), no duplicate texture actors (11), texture actors non-pickable (12), crosshair updates textures (13), Window/Level behaviour honestly WORKING (14), clipping display-only (15), final polydata unchanged (16), mask unchanged (17), surface_dict unchanged (18), clipping planes owned/removed safely (19), ROI switching safe (20), surface rebuild rebind safe (21), camera unchanged (22), picker unaffected (23), lifecycle clean (24), Save/Open unchanged (25), E1-E4 regression all PASS via the full 367-test suite (26-29), D9/C7 PASS (30), C8 PASS (31), full CT3D suite PASS (32), upstream PASS (33), pyflakes PASS (34), compile PASS (35), docs updated honestly (36), manual evidence not fabricated (37), no E6 code slipped in (38).

`E5_TEXTURED_PLANES = PARTIAL` (see "Texture orientation proof"). `E5_CLIPPING = PASS` (fully implemented, tested, and proven - no caveats).

## Next recommendation

Real operator manual QA session covering `E5-B`/`E5-C`/`E5-D` (texture orientation) is the highest-value next step before any further E5 work - it is the one remaining piece of evidence needed to upgrade `E5A`/`E5_TEXTURED_PLANES` from `PARTIAL` to a fully-proven `PASS`. After that: E6 — AI segmentation architecture, per the roadmap's priority order (E1→E2→E3→E4→E5 before E6/E6b), though E6 remains explicitly out of scope for any single run per this track's own stop conditions around committing model weights/data without review.
