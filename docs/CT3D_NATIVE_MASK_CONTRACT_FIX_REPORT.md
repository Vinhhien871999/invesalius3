# CT3D — Native Mask Read/Write Contract Fix (pre-E6)

**Branch**: `enhancement/advanced-segmentation` · **Date**: 30/09/2026 · Found during the E6 run's pre-E6 audit of the commit path E6 AI Accept would reuse. Stable `thesis-ct-roi-tools` / tag `ct3d-rc1` not modified.

## 1. Native facts (source, not assumed)

| Fact | Source |
|---|---|
| `Mask.matrix` is (z+1, y+1, x+1) uint8; index 0 of each axis is padding whose cells flag "slice computed": `matrix[n,0,0]` axial, `matrix[0,n,0]` coronal, `matrix[0,0,n]` sagittal | `mask.py` `create_mask()`; `slice_.py` `get_mask_slice()` |
| Threshold masks are computed lazily: a 2D view thresholds a slice the first time it shows it (flag 0 → compute → 1) | `slice_.py:1121-1171` `get_mask_slice()` |
| Before any whole-volume use native code calls `do_threshold_to_all_slices(mask)` (surface, NIfTI export — commented "lazy threshold only generates visited slices" — boolean ops, morphology, density, area) | `control.py:364`, `slice_.py:1900/2287/2303` |
| Recomputing a slice keeps only edit values 1, 2, 253, 254; a plain 255 is overwritten | `slice_.py:1722` `do_threshold_to_a_slice()` |
| Brush Draw writes 254, brush Erase writes 1 | `slice_.py` `edit_mask_pixel()` |
| Visible mask = value > 127: the mask colour table makes 0/1/2 transparent and colours 253-255; the binary surface is contoured at 127 | `slice_.py:1803-1812` `do_colour_mask()`; `surface_process.py:175` |
| After a hand-written whole-volume write native code sets all three flag planes (`matrix[0]`, `[:,0]`, `[:,:,0]` = 1) and discards the 2D slice buffers | `mask.py` `modified(all_volume=True)`; `styles.py:3004-3006` (Watershed); `slice_.py` boolean op |

## 2. Defects (all reproduced through the plugin's own handlers)

1. **Commit lost voxels on first view.** Region Growing (classic and E2 Accept) marked only the axial flags. The first time a 2D view showed a coronal or sagittal slice, `get_mask_slice()` re-thresholded that plane with the (1, 1) placeholder threshold and overwrote the committed 255s. Reproduced: 56 of the committed voxels lost after showing one coronal and one sagittal slice. Also, `np.where(result > 0, 255, target)` kept stray (1, 1)-threshold voxels on slices a view had already thresholded during mask creation.
2. **Whole-mask reads skipped the lazy computation.** E3 cleanup, E4 "Current ROI", Measure Volume and NumPy/NRRD export read `matrix[1:,1:,1:]` directly, so a threshold mask read as empty wherever no view had been. E3 then wrote that partial mask back and flagged every axial slice computed — permanent loss. Reproduced: Measure Volume 54.4 mm³ instead of 210.4 mm³ (only the displayed slice counted).
3. **Wrong foreground value.** Those reads used `!= 0`, so brush-erased voxels (value 1) counted as foreground; E3 wrote them back as 255, undoing the user's erasures.

Not affected: E2 Otsu Accept (native threshold commit), the final surface (native path computes all slices), Undo/Redo data (full-matrix snapshots), native NIfTI export (computes all slices; it does use `> 0`, a native choice left alone).

## 3. Fix

New `plugins/roi_viewer/core/native_mask.py`:

- `logical_foreground(slice_, mask)`: `do_threshold_to_all_slices(mask)` first, then `matrix[1:,1:,1:] > 127` (bool copy).
- `write_logical_region(slice_, mask, foreground)`: writes exactly 0/255, sets all three flag planes, flushes, sets `was_edited`, discards the 2D slice buffers.
- `commit_preview_array_to_new_mask(foreground, name, colour)`: the single commit for computed candidates — checks the shape **before** creating anything, creates the mask through the native "Create new mask" topic, then `write_logical_region()`. Used by Region Growing (classic + E2 Accept) and by E6 AI Accept.

Call sites: `_commit_region_growing_result()`, `_run_cleanup()` (read + write), `_select_preview_3d_source()` (E4 Current ROI), `MeasurementPanel._on_measure_volume()`, `ExportPanel._export_mask_via_exporter()`. `_refresh_after_edit()` (shared by commit, Accept, Undo, Redo, cleanup) now discards the 2D slice buffers before "Reload actual slice", so the views show the edited mask instead of a cached slice.

Classic behaviour for a fully computed mask without brush erasures is unchanged (the existing suite passes unchanged apart from the fixtures below).

## 4. Tests

`tests/ct3d/test_native_mask_contract.py` (10) on a real `Slice()`/`Project()` with real native mask creation; "showing a slice" calls `get_mask_slice()` exactly as the 2D viewer does:

- commit survives the first view of every slice; commit exact when views threshold during creation;
- E3 on a lazily computed threshold mask uses the whole mask; E3 keeps brush erasures;
- E4 Current ROI, Measure Volume and NumPy export read the whole mask without erased voxels;
- `write_logical_region()` flags all planes / discards buffers / writes only 0 and 255; wrong-shape commit rejected before any mask exists; foreground matches the native colour table (0/1/2 → no, 253/254/255 → yes).

**Proven to catch the defects**: with the three pre-fix GUI files restored from HEAD, all 7 handler-level tests fail with value mismatches; files restored byte-identically afterwards.

Existing tests updated, reasons written in-file: `test_preview_surface_integration.py` and `test_segmentation_cleanup_integration.py` fixtures wrote voxels into slices flagged "not computed" (a state real InVesalius never keeps data in) — they now flag the axial slices computed; `test_cleanup_preserves_padding` + `test_cleanup_sets_axial_sentinel_after_write` (both encoded the bug) replaced by `test_cleanup_marks_every_sentinel_plane`; E4's ROI-switch test compares the bool foreground.

## 5. Regression

`tests/ct3d`: 465 passed / 1 skipped / 0 failed (466 collected). Upstream 94. `pyflakes`/`compileall plugins/roi_viewer` clean. (Full 3× run recorded with the E6 run.)

## 6. Manual QA / stable

- Manual items touching these paths (E2-G, E3-A..M, E4 Current ROI items) are still `NOT_RUN`; run them on a build that includes this fix.
- Known issue of stable `ct3d-rc1` (not modified): Region Growing masks can lose voxels when a coronal/sagittal slice is shown for the first time; Measure Volume and NumPy/NRRD export count only computed slices and include brush-erased voxels.
