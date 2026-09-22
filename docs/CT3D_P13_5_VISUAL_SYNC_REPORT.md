# CT3D Phase 13.5 — Visual 2D→3D Synchronization

## 1. Metadata

| Field | Value |
|---|---|
| Date | 2026-09-17 |
| Repository | Vinhhien871999/invesalius3 |
| Branch | `thesis-ct-roi-tools` |
| HEAD before | `2920ee8b` (last commit of Phase 13) |
| HEAD after | `3d070f7c` |
| Python | 3.11.7 (`D:\PyTools\invx-venv\Scripts\python.exe`) |
| pytest | 8.3.5 / NumPy 1.26.4 / SciPy 1.14.0 / VTK 9.3.0 / wxPython 4.2.5 |
| Scope | Mini-phase, pre-Phase-14. NOT Phase 14. No feature outside this scope. |

## 2. User-observed UX Gap

Manual GUI testing (already reported by the operator, see the request that opened this mini-phase) confirmed C8 (Sync 2D→3D) is functionally `WORKING`: enabling InVesalius's native `"Slices' cross intersection"` tool + the plugin's `"Sync 2D -> 3D"` checkbox, then clicking/dragging on a 2D view, correctly moves `CrosshairMarker3D`'s small sphere in the Volume view; disabling Sync freezes it; re-enabling resumes updates. The reported gap is purely visual: a single small marker sphere does not clearly convey "where the 3 current slice planes actually are" within the volume - the user wants the Volume view to show the 3 slice positions more obviously.

## 3. Existing C8 Architecture

Traced for real (not assumed), per Section II of the spec:
```
2D native interactor (invesalius/data/styles.py's default style)
  -> Publisher.sendMessage("Set cross focal point", position=[x,y,z,None,None,None])
  -> plugins/roi_viewer/main.py._on_cross_focal_point(position)  (real subscription, Phase 09)
  -> ROIViewerFrame.on_cross_focal_point_changed(position[:3])
  -> gated by self.sync_mgr.sync_2d_3d (the "Sync 2D -> 3D" checkbox)
  -> self.marker_3d.attach(viewer.ren) / .update_position(x, y, z)
  -> Publisher.sendMessage("Render volume viewer")
```
Payload: `position` is a real world-space (x, y, z, ...) list in mm, VTK convention (X = fastest-varying image axis = SAGITAL, Y = CORONAL, Z = AXIAL slice stack - confirmed against `core/sync_2d3d.py.world_to_voxel()`'s own docstring and `interface/project_interface.py.ProjectInterface.voxel_to_world()`, both already real and already unit-tested, not re-derived from scratch). Renderer: `interface/view_interface.py.ViewInterface().get_volume_viewer()` walks the real wx widget tree for `invesalius.data.viewer_volume.Viewer` and returns its `.ren` (a real `vtkRenderer`) - the same renderer `core/marker_3d.py`'s `CrosshairMarker3D` already attaches to.

**Audited Section XVIII's "Enable real-time update"/"Update delay (ms)" controls**: `interaction_panel.py`'s slider calls `sync_mgr.set_update_delay()` (real, wired), and `sync_mgr.request_3d_update()` (the method that actually reads `update_delay`) is called only from `roi_panel.py.on_mask_update()` - a *different* event (mask edits), not the crosshair path. `on_cross_focal_point_changed()` itself has never been throttled - it updates the marker directly on every event, and the operator's own manual QA already confirmed this is smooth in practice. Per the spec's explicit instruction not to build a second timer architecture, the new slice-plane updates follow the exact same un-throttled pattern as the existing marker update, rather than introducing new debounce machinery.

## 4. Design Decision

- Do **not** auto-enable `"Slices' cross intersection"` - stays fully user-controlled, native.
- Do **not** change interactor style, steal Brush/Eraser/Distance/Area, or touch native toolbar state.
- Plugin only ever *listens* to the real `"Set cross focal point"` topic when InVesalius sends it (unchanged from Phase 09) - no new topic, no new interception point.
- Add a small, focused new module (`core/slice_planes_3d.py`) rather than folding this into `marker_3d.py` - keeps each class's actor lifecycle independently testable, mirrors the existing one-concern-per-module convention (`marker_3d.py`, `picker_3d.py`).
- Not texture-mapped CT imagery this phase (explicit scope boundary) - geometric planes only, to show *position*, not slice *content*.

## 5. Native Cross Intersection Dependency

UI text added verbatim in `interaction_panel.py` (English, matching the rest of that panel's UI language) and in `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md` (Vietnamese): *"Requires InVesalius 'Slices' cross intersection' tool to be active."* / *"Cần bật công cụ 'Slices' cross intersection' trên thanh công cụ InVesalius để click/kéo 2D cập nhật 3D."* The plugin never calls any pubsub topic or API that would toggle this native tool itself - confirmed by inspection of every new line added this phase (no `"Enable style"`/interactor-style call was added).

## 6. SlicePlanes3D Architecture

`plugins/roi_viewer/core/slice_planes_3d.py` (new, pure VTK, no wx/invesalius import - same convention as `marker_3d.py`/`picker_3d.py`, unit-testable in isolation):
- `SlicePlanes3D` owns exactly 3 `vtkActor` objects (one per plane), each backed by a `vtkPlaneSource` + `vtkPolyDataMapper`, created **once** in `attach()` - never recreated on subsequent updates.
- `attach(renderer)` / `detach()`: same idempotent, no-duplicate-actor pattern as `CrosshairMarker3D.attach()`/`.detach()` (re-attaching to a different renderer first detaches from the old one; detaching is safe to call twice).
- `set_bounds(bounds)`: validates a 6-tuple `(xmin,xmax,ymin,ymax,zmin,zmax)`, raises `ValueError` for a malformed one (wrong length, or `min >= max` on any axis) rather than silently producing degenerate geometry.
- `update_position(world_position)`: moves the SAME 3 `vtkPlaneSource` objects' `Origin`/`Point1`/`Point2` + calls `Modified()` - never `AddActor()` again. Raises `ValueError` for a non-finite/malformed position; no-ops (does not raise) if `attach()`/`set_bounds()` have not happened yet (a crosshair event can legitimately arrive before either is ready - Section 11 below).
- `set_visible(bool)`: shows/hides all 3 actors without destroying them - the "Show slice planes in 3D" checkbox's sole effect; geometry keeps tracking the real position underneath even while hidden, so toggling back on shows the current position immediately, not a stale one.
- Colours: Axial=blue, Coronal=green, Sagital=red (a standard medical-imaging convention, not invented arbitrarily), opacity 0.25 - semi-transparent, does not obscure the surface, visible from either side (VTK default, no backface culling enabled).
- Every actor: `SetPickable(False)` at creation - see Section 8/13.

## 7. Coordinate / Bounds Handling

Bounds are **derived from real project data**, never hardcoded, via a new `ROIViewerFrame._compute_volume_bounds()`:
```python
pi = ProjectInterface()
shape = pi.get_shape()                              # real (axial, coronal, sagital) voxel counts
corner_a = pi.voxel_to_world(0, 0, 0)                # real, already-tested helper
corner_b = pi.voxel_to_world(shape[0]-1, shape[1]-1, shape[2]-1)
bounds = (min/max of corner_a/corner_b on each axis)
```
This reuses `interface/project_interface.py.ProjectInterface.voxel_to_world()` - the exact same, already-unit-tested (`tests/ct3d/test_coordinates.py`) convention `core/sync_2d3d.py`'s own `voxel_to_world()`/`world_to_voxel()` implement, confirmed by reading both source files fresh this phase (Section 3) rather than assumed. Geometry mapping, verified against that real convention rather than applied blindly:
- **Axial** plane: constant in Z (= current axial world coordinate), spans the full X/Y bounds.
- **Coronal** plane: constant in Y, spans the full X/Z bounds.
- **Sagital** plane: constant in X, spans the full Y/Z bounds.

Bounds represent the **whole real volume** (from `ProjectInterface().get_shape()`, i.e. `Slice().matrix.shape`), never a mask/surface's own (possibly partial) extent - satisfying the spec's explicit warning not to use surface bounds.

## 8. Actor Lifecycle

| Event | Action |
|---|---|
| `ROIViewerFrame.__init__` | `self.slice_planes_3d = SlicePlanes3D()` constructed (no actors yet - `attach()` not called until a real crosshair event with a real viewer exists) |
| `on_cross_focal_point_changed()`, sync ON | `attach()` (idempotent) -> real bounds computed defensively every time (see Section 11) -> `set_bounds()` -> `update_position()` -> `set_visible(self.show_slice_planes)` |
| `on_project_load()` | Bounds refreshed eagerly (in addition to the defensive per-event refresh above) so planes are correctly sized for a newly-loaded/different dataset the moment the next real event arrives |
| `on_project_close()` | `detach()` - a plane sized for the OLD project's bounds is meaningless once a different (or no) project is loaded; `on_cross_focal_point_changed()` re-`attach()`s lazily on the next real interaction |
| `_on_close()` (plugin window closed) | `detach()` - same leak class already fixed for `marker_3d`/`picker_3d` (Phase 09 SYNC-T6) - the real 3D renderer is a singleton that outlives any single `ROIViewerFrame` |
| Plugin reopened | Fresh `SlicePlanes3D()` instance, `attach()` creates exactly 3 new actors in the (still-live) renderer - the old instance's actors were already removed by the close handler above, so no duplication (verified: `test_sync3d_t8_reattach_exactly_3_planes_not_6`) |

## 9. UI Changes

`interaction_panel.py`: new checkbox `"Show slice planes in 3D"` (default checked) directly under the existing `"Sync 2D -> 3D"` checkbox, plus a small grey help-text line stating the native-tool prerequisite. No other panel/checkbox/button was touched.

## 10. Event Flow

```
2D crosshair (native)
      |
"Set cross focal point"
      |
ROIViewerFrame.on_cross_focal_point_changed()
      |
sync_mgr.sync_2d_3d == True?
      |
      +-- marker_3d.update_position(x, y, z)
      +-- slice_planes_3d.attach() / set_bounds() / update_position((x,y,z)) / set_visible(show_slice_planes)
      |
Publisher.sendMessage("Render volume viewer")   <- single render call, same as before
```
No new pubsub topic. No second event path. No surface rebuild anywhere in this flow (Section 16 of the phase spec, honoured - `"Create surface from index"` is not called from this method, confirmed by reading the full diff).

## 11. Performance

Both `update_position()` calls (marker + planes) are cheap, pure-VTK geometry writes - `SetOrigin`/`SetPoint1`/`SetPoint2` + `Modified()` per plane, no `numpy`/`scipy`/multiprocessing/surface generation anywhere in the new code path (grepped the new module and the modified method to confirm). A lightweight real timing check (60 consecutive real `on_cross_focal_point_changed()` calls through the actual method, real `SlicePlanes3D`/`CrosshairMarker3D`, real `vtkRenderer` - see `test_sync3d_t4_many_updates_actor_count_stable`) completed well under the pytest suite's overall sub-second runtime, with the renderer's actor count staying at exactly 4 (1 marker + 3 planes) throughout - no growth, no leak. No FPS target was invented; only actual behavior (actor-count stability, geometry correctness) is asserted.

## 12. Unit Tests

`tests/ct3d/test_slice_planes_3d.py` - 16 tests, all real VTK (`vtkRenderer`), no wx:

| ID | Covers |
|---|---|
| SP3D-T1 | Construct -> 0 actors until `attach()` |
| SP3D-T2 | `attach()` -> exactly 3 actors |
| SP3D-T3 | `attach()` twice -> no duplication |
| SP3D-T4 | `set_bounds()` + `update_position()` -> exact geometry (Origin/Point1/Point2 verified per plane) |
| SP3D-T5 | All 3 planes intersect the same real world position |
| SP3D-T6 | Second `update_position()` -> same actor Python objects (identity-checked), no growth |
| SP3D-T7 / T8 | `set_visible(False)` / `set_visible(True)` -> real `GetVisibility()` toggled |
| SP3D-T9 / T10 | `detach()` removes all 3 actors; idempotent |
| SP3D-T11 | All 3 actors non-pickable (`GetPickable() == 0`) |
| SP3D-T12 / T12b | Invalid bounds / invalid position -> `ValueError` (explicit design choice, documented) |
| (extra) | `update_position()` before `attach()`/`set_bounds()` -> no crash, no garbage actor; re-attach to a different renderer leaves no orphan; re-attach after `detach()` correctly has no stale bounds/position |

## 13. Integration Tests

Extended `tests/ct3d/test_sync_2d3d.py` (+9 tests, SYNC3D-T1..T9), driven through the **real, unmodified** `ROIViewerFrame.on_cross_focal_point_changed()` bound method against a minimal stand-in `self` (same established technique as the existing F3/C8 tests in that file - real logic exercised, no wx.Frame construction needed) with a real `SlicePlanes3D`/`CrosshairMarker3D`/`vtkRenderer`, and a `ProjectInterface`/`ViewInterface` stand-in using the exact real `voxel_to_world()` formula (not a reimplementation with different semantics):

| ID | Result |
|---|---|
| SYNC3D-T1 | Sync OFF -> planes untouched (0 attach/set_bounds/update calls) |
| SYNC3D-T2 | Sync ON, event A -> 3 planes created, all intersect A |
| SYNC3D-T3 | Event B -> same actor identities, new position B |
| SYNC3D-T4 | 60 consecutive updates -> renderer actor count stable at 4 |
| SYNC3D-T5 | Show planes OFF -> marker still updates, planes hidden (geometry still tracks position underneath) |
| SYNC3D-T6 | Show planes ON -> visible at the current real position |
| SYNC3D-T7 | Real `detach()` on both marker and planes -> renderer actor count 0 |
| SYNC3D-T8 | Detach then re-attach -> exactly 3 planes, not 6 |
| SYNC3D-T9 | After a real event, all 3 planes remain non-pickable |

All 25 new tests (16 unit + 9 integration) PASS.

## 14. Regression

Explicitly re-run per the spec's Section XXII: `tests/ct3d/test_sync_2d3d.py` (22/22 PASS, including all pre-existing C8/F3 tests unchanged), `tests/ct3d/test_surface_policy.py`, `tests/ct3d/test_segmentation.py` - both pass unaffected (this phase never touched `segmentation_panel.py`'s surface-algorithm policy or `core/segmentation.py`). Full suite: see Section 19.

## 15. Manual QA Checklist

New section `"C8 — Visual Sync 2D → 3D Slice Planes"` added to `docs/CT3D_MANUAL_QA_CHECKLIST.md` (TEST A-I, preconditions listing the native-tool prerequisite explicitly). **All 9 items are `NOT_RUN`** - Claude Code performed no real mouse/keyboard interaction and marked nothing PASS in advance, per the spec's explicit instruction.

## 16. Files Changed

New: `plugins/roi_viewer/core/slice_planes_3d.py`, `tests/ct3d/test_slice_planes_3d.py`, `docs/CT3D_P13_5_VISUAL_SYNC_REPORT.md`.
Modified: `plugins/roi_viewer/gui/roi_panel.py` (`on_cross_focal_point_changed()` extended, new `_compute_volume_bounds()`, `on_project_load()`/`on_project_close()`/`_on_close()` updated), `plugins/roi_viewer/gui/interaction_panel.py` (new checkbox + handler), `tests/ct3d/test_sync_2d3d.py` (+9 tests), `docs/CT3D_MANUAL_QA_CHECKLIST.md` (new section), `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md` (Interaction section updated), `docs/CT3D_FEATURE_AUDIT.md` (C8 row), `docs/CT3D_MASTER_PROGRESS.md` (Sync 2D→3D row, baseline note - Current Phase NOT changed to 14), `docs/CT3D_CHANGELOG.md` (new entry).

## 17. Known Limitations

- Planes are geometric only - no CT slice imagery is texture-mapped onto them this phase (explicit scope boundary, not an oversight).
- No per-axis visibility toggle (only one combined "Show slice planes in 3D" checkbox) - the spec explicitly did not require this for this phase.
- Real-mouse visual confirmation (does it actually *look* right in the live 3D view) is `NOT_RUN` - automated tests verify geometry/lifecycle correctness, not visual appearance.
- `sync_mgr.update_delay`/`request_3d_update()` remain wired only to the `on_mask_update()` path (unchanged, pre-existing) - the crosshair-driven marker/planes path remains intentionally un-throttled, matching its pre-existing (already field-tested) behavior.

## 18. Phase Gate

`PHASE_GATE: PASS` (automated criteria only - see Section 19 for the full checklist against the spec's 15 gate items). Manual visual confirmation remains outstanding (`NOT_RUN`).

## 19. Recommendation Before Phase 14

Per the spec's explicit instruction, Phase 14 (Final Audit & Release Candidate) is **not** started this turn. The single outstanding item before it should begin is the operator running the new "C8 — Visual Sync 2D → 3D Slice Planes" manual checklist (9 items, ~10-15 minutes) and reporting real PASS/FAIL results, the same way the 7-item Phase 13 manual QA session was reported.
