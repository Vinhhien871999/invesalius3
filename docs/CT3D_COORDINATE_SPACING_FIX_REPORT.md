# CT3D — World ↔ Voxel Coordinate Fix (spacing order + 3D view frame)

| Field | Value |
|---|---|
| Date | 30/09/2026 |
| Branch | `enhancement/advanced-segmentation` only — stable `thesis-ct-roi-tools` / tag `ct3d-rc1` **not modified** |
| Base | `52eb7f85` |
| Commits | `7b245865` Fix world voxel spacing order for anisotropic volumes · `c9f220bd` Convert between 2D slice and 3D view frames · (this docs commit) |
| Scope | Pre-E6 blocking correctness fix. Not E6, not Phase 15. |

## 1. Discovery

Found during the E6 input-volume audit (30/09/2026): the plugin's world↔voxel conversion paired the axial axis with `Slice().spacing[0]`. While proving the correct convention for this fix, a **second, related bug** surfaced and is fixed here too (separate commit): the plugin never converted between InVesalius's 2D slice frame and its y-flipped 3D view frame. Both are coordinate-correctness bugs in the same functions' callers; fixing only the first would still leave 3D pick → 2D and every plugin 3D actor wrong. This second fix is a scope expansion beyond the original request, made because the request's own validations (C8 planes, 3D pick → correct slice, texture slice, clipping origin) cannot pass without it.

## 2. Real source evidence

### Spacing is (x, y, z); the matrix is (z, y, x)

| Source | Line | Evidence |
|---|---|---|
| `invesalius/reader/dicom.py` | 1870, 481 | `self.spacing = list(parser.GetPixelSpacing())`, documented as "Return [x, y]" |
| `invesalius/control.py` (DICOM import) | 1300 | AXIAL: `spacing = xyspacing[0], xyspacing[1], zspacing` |
| `invesalius/control.py` (bitmap import) | 1180 | same order |
| `invesalius/control.py` (missing-spacing dialog) | 1318 | `spacing = dlg.spacing_new_x, dlg.spacing_new_y, dlg.spacing_new_z` |
| `invesalius/data/slice_.py` (`Slice.spacing` setter) | 202 | `self.center = [(s * d / 2.0) for (d, s) in zip(self.matrix.shape[::-1], self.spacing)]` — pairs spacing with the **reversed** shape |
| `invesalius/data/slice_.py` (axis swap) | 2184–2189 | swapping numpy axes (2, 1) swaps `spacing[1], spacing[0]` — spacing[0] ↔ numpy axis 2 |
| `invesalius/data/converters.py` | 86–95 | `SetSpacing(spacing)` with dimensions `(dx, dy, dz)` from `shape` (z, y, x) — VTK X ↔ spacing[0] |
| `invesalius/data/viewer_slice.py` | 1848–1850 | native slice selection: `axial = round(pos[2]/spacing[2])`, `coronal = round(pos[1]/spacing[1])`, `sagittal = round(pos[0]/spacing[0])` |

### Origin is 0

Every `converters.to_vtk()` call in the native surface (`surface_process.py:114/133/150`), volume (`volume.py:572`) and 2D slice (`slice_.py:757–818`) pipelines passes no origin → default `(0, 0, 0)`. No origin support was added.

### Two frames, differing in the sign of y

| Frame | Used by | y range (dataset 0051) |
|---|---|---|
| **slice frame** | 2D viewers, `"Set cross focal point"` positions, `converters.to_vtk()` images | [0, +244.5] |
| **view frame** | 3D renderer: surfaces (`surface_process.py:156`), volume rendering (`volume.py:597`), mask volumes (`volume_mask.py:70`) — all `vtkImageFlip(FilteredAxis=1, FlipAboutOriginOn)`; `viewer_volume.AddSurface()` adds actors with no transform | [−244.5, 0] (measured) |

Native converts explicitly both ways: 2D crosshair → 3D pointer `position=[x, -y, z]` (`styles.py:555`); 3D pick → 2D `position=[x, -y, z]` (`styles_3d.py:994`, `:1031`).

## 3. Root cause

| | Old | Correct |
|---|---|---|
| world → voxel | `axial = int(z / spacing[0])`, `sagital = int(x / spacing[2])` | `z = round(wz / sz)`, `x = round(wx / sx)` (spacing = (sx, sy, sz)) |
| voxel → world | `z = axial * spacing[0]`, `x = sagital * spacing[2]` | `wz = z * sz`, `wx = x * sx` |
| rounding | `int()` truncation | round-to-nearest, like native (`viewer_slice.py:1848`), then clamp to `[0, n-1]` |
| 3D actors from crosshair | drawn at slice-frame (x, y, z) | drawn at view-frame (x, −y, z) |
| 3D pick → voxel | view-frame y used as-is (negative → clamped to 0) | converted to slice frame first |

Both plugin implementations (`core/sync_2d3d.py` lines 124–146, `interface/project_interface.py`) carried the same wrong formula; their docstrings claimed spacing was "index-aligned with matrix.shape" — false. `ProjectInterface.get_spacing()`'s own docstring already said "(x, y, z)".

## 4. Canonical contract (`plugins/roi_viewer/core/coordinates.py`)

```
VOXEL_INDEX_ORDER = (z, y, x)   # Slice().matrix axes: AXIAL, CORONAL, SAGITAL
SPACING_ORDER     = (x, y, z)   # Slice().spacing
WORLD_ORDER       = (x, y, z)   # mm, origin 0

wx = x * sx     wy = y * sy     wz = z * sz              (slice frame)
x = round(wx/sx), y = round(wy/sy), z = round(wz/sz), each clamped to [0, n-1]
view frame = (wx, -wy, wz)
```

Functions: `voxel_zyx_to_world_xyz`, `world_xyz_to_voxel_zyx`, `volume_bounds_world`, `slice_to_view`, `view_to_slice`, `slice_bounds_to_view`. `SyncManager2D3D` and `ProjectInterface` keep their public signatures (voxel tuples still returned as (axial, coronal, sagital) = (z, y, x)) and delegate here — one implementation, not two.

## 5. All conversion sites audited

| Site | Before | After |
|---|---|---|
| `core/sync_2d3d.py` `world_to_voxel`/`voxel_to_world` | spacing swapped | **FIXED** (delegates) |
| `interface/project_interface.py` same pair | spacing swapped | **FIXED** (delegates) |
| `gui/roi_panel.py` `_compute_volume_bounds` (C8 bounds) | swapped spacing, slice frame | **FIXED** — canonical bounds, view frame |
| `gui/roi_panel.py` `on_cross_focal_point_changed` (marker, C8 planes, clipping origin) | slice frame in 3D | **FIXED** — view frame |
| `gui/roi_panel.py` `update_textured_slice_planes` (texture slice index) | swapped spacing | **FIXED** via `ProjectInterface` |
| `core/textured_slice_planes_3d.py` `update_plane` (texture geometry) | slice frame in 3D | **FIXED** — corners moved to view frame, texture coordinates kept per corner |
| `gui/interaction_panel.py` 3D pick → 2D sync | view frame y used as slice y | **FIXED** |
| `gui/interaction_panel.py` texture enable (C8 position → texture) | — | **FIXED** — view → slice before voxel lookup |
| `gui/segmentation_panel.py` Region Growing seed pick | view frame y + swapped spacing | **FIXED** |
| `gui/roi_panel.py` `get_current_reference_position` (annotations) | pick (view) and crosshair (slice) mixed | **FIXED** — always slice frame |
| `core/evaluation.py` Hausdorff/ASSD (`spacing_zyx`) | function correct, header falsely said `spacing_zyx` = `Slice().spacing`; no production caller | **docstring corrected** |
| `core/measurement.py` 3D distance / volume | world-mm distances with unit spacing; volume uses the product only | not affected by order |
| `core/segmentation.py`, `segmentation_cleanup.py` volume stats | product only | not affected |
| E4 `build_preview_mesh`, final surface | already view frame via the real `vtkImageFlip` | not affected |

## 6. Dataset 0051 proof

Shape (z, y, x) = (108, 512, 512); spacing (x, y, z) = (0.4785, 0.4785, 1.5).

| | Before | After | Ground truth |
|---|---|---|---|
| Volume bounds, slice frame | x 0–766.5, z 0–51.2 | x 0–244.51, y 0–244.51, z 0–160.5 | `converters.to_vtk()`: same |
| C8 plane bounds (drawn in 3D view) | x 0–766.5, y 0–244.5, z 0–51.2 | x 0–244.51, y −244.51–0, z 0–160.5 | `to_vtk` + `vtkImageFlip`: same |
| Mid-volume world (122.26, 122.26, 80.25) → voxel | (107, 255, 81) | (54, 256, 256) (exact half-voxel, rounds to nearest even) | ≈ (53.5, 255.5, 255.5) |
| Phase 09's recorded real 3D pick (142.9, −107.3, 154.4) → voxel | (107, 0, 95) | (103, 224, 299) | 154.4/1.5 = 102.9, 107.3/0.4785 = 224.2, 142.9/0.4785 = 298.6 |
| Round trip (0,0,0), (53,255,255), (107,511,511) | — | exact | — |

## 7. Tests

- `tests/ct3d/test_coordinates.py`: 3 tests corrected, each with the reason written in the test — `test_roundtrip_center_non_uniform_spacing` (labelled spacing as axial-first and built its "independent" reference with the same wrong mapping), `..._rounds_to_nearest_like_native` (was asserting truncation; native rounds), `test_world_to_voxel_zero_spacing...` (`spacing[0]` is x, so the SAGITAL index falls back). 12 new canonical test functions (17 cases, 385 → 402), incl. `test_spacing_order_xyz`, `test_voxel_zyx_to_world_xyz`, `test_world_xyz_to_voxel_zyx`, `test_roundtrip_anisotropic` (0051), `test_roundtrip_asymmetric_spacing` (0.5, 0.8, 2.3), `test_bounds_match_vtk`, `test_midpoint_dataset_0051`, `test_last_voxel_dataset_0051`, rounding boundary, clamping, and `ProjectInterface` ≡ `SyncManager2D3D`.
- `tests/ct3d/test_coordinate_frames_integration.py` (23, real handlers, 0051 spacing): C8 marker = native pointer; C8 bounds = real 3D volume bounds; `test_c8_axial_uses_z_spacing` / `coronal_uses_y` / `sagittal_uses_x`; axial plane reaches the top slice; `test_3d_pick_maps_to_correct_slice_anisotropic` (×3); Region Growing seed from a 3D pick; `test_texture_slice_selection_{axial,coronal,sagittal}_anisotropic`; textured plane ≡ C8 plane (×3); `test_clipping_origin_matches_crosshair_anisotropic` (×3); E4 mesh inside C8 bounds.
- **Proven to catch the bugs**: with the 6 pre-fix production files restored from `52eb7f85`, 18 of the 23 integration tests fail with real value mismatches. The 5 that still pass do so for explained reasons (coronal already used the right spacing index; old textures and old C8 planes were mirrored *together*; an unclamped sagittal position; one test checks the new convention directly).
- Existing tests that encoded the bug, corrected with reasons in-file: `test_sync_2d3d.py` (spacing labelled axial-first; its fake `ProjectInterface` re-implemented the wrong mapping; 3D actor positions asserted in the slice frame; F3 pick in the wrong frame), `test_textured_slice_planes_wl_refresh.py` (C8 position is view frame), `test_preview_surface_mesh.py:157` (spacing labelled as the 0051 convention was reversed — the test compares two pipelines with the same tuple, so its result was never wrong).

## 8. Regression

Before: `tests/ct3d` 385 passed / 1 skipped / 0 failed (386 collected). After commit 1: 402 / 1 / 0. After commit 2: **425 passed / 1 skipped / 0 failed** (426 collected), identical across 3 consecutive runs. Upstream **94 passed**. `pyflakes`/`compileall plugins/roi_viewer` exit 0. `git diff --check` clean.

## 9. Impacted features and manual QA

Automated evidence now covers C8 marker/planes, 3D pick → 2D, Region Growing seed, texture slice selection and placement, clipping origin, E4 frame agreement. Any manual result that depended on these on anisotropic data must be re-run **after** this fix: advanced `E5-B/C/D/E/J/K/L` → `RETEST_REQUIRED`. Region Growing via a 3D-picked seed (E2-E/F/G, and the stable Region Growing workflow) was also affected; those items were `NOT_RUN`. `E5-A` (visibility only) stays PASS.

## 10. Stable branch

`ct3d-rc1` / `thesis-ct-roi-tools` contain both bugs (the conversion code dates from Phase 09) and are **not modified**. Known stable issue: *world↔voxel spacing order and 2D/3D frame are wrong for anisotropic data — C8 planes mis-sized/mirrored, 3D pick → 2D and 3D-picked Region Growing seeds select the wrong voxel.* Near-isotropic data (e.g. `0801`, 0.977/0.977/1.0 mm) hides the spacing half; the y mirror affects every dataset. A future stable maintenance release may reimplement this fix after review.

## 11. Known limitations

- Round-to-nearest uses Python's `round()` (banker's rounding at exact half-voxels), the same function native uses.
- No gantry-tilt / oblique-orientation handling (pre-existing, unchanged); only the axis-aligned path with origin 0 that native uses.
- ~~The Pick Point coordinate readout in the Interaction tab still shows the raw 3D-view pick (y ≤ 0); only its use for slice selection was converted.~~ **Closed 30/09/2026 in `4d0ca6e5`** (UI polish): the "Chọn điểm trong 3D" readout in tab "Tương tác & Hiển thị" now shows `view_to_slice(pick)` - the same slice-frame millimetres (y ≥ 0) as the 2D views and the slice selection. See `docs/CT3D_UI_UX_VIETNAMESE_POLISH_REPORT.md`.

## 12. Status after the UI polish run (30/09/2026)

The coordinate fix was re-verified unchanged after the UI/localization commit `4d0ca6e5`: `tests/ct3d` 446 passed / 1 skipped / 0 failed (447 collected, 3 identical runs), which includes the coordinate tests of this report (`test_coordinates.py` and the 23 real-handler integration tests of `test_coordinate_frames_integration.py`). Dataset `0051` (108×512×512, spacing (0.4785, 0.4785, 1.5) mm): expected bounds x 0–244.5, y 0–244.5, z 0–160.5 mm (slice frame); the plugin's C8 bounds equal the real VTK volume bounds in the 3D view frame (x 0–244.5, y −244.5–0, z 0–160.5 mm). Manual E5-B/C/D/E/J/K/L remain `RETEST_REQUIRED`; E5-A stays `PASS`.
