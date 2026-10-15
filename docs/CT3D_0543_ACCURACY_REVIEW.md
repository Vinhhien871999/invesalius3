# CT3D / ROI Viewer — Accuracy review on dataset 0543 (15/10/2026)

Branch `enhancement/advanced-segmentation`. Headless runs (no InVesalius window, temporary `XDG_CONFIG_HOME`; the user's configuration was not touched). Every TotalSegmentator call ran inside the provider's guard (no weight download, no usage-statistics upload). There is **no expert ground truth** for this dataset: accuracy statements below are either exact (geometry, run-to-run identity) or relative to TotalSegmentator's full-task result used as a *silver* reference, and are labelled as such.

## 1. Dataset

`D:\PyTools\dicom_samples\0543_slc_01_300` — 300 single-frame axial CT images, Philips Mx8000 IDT 16, series "TX+ABD+PV" (thorax + upper abdomen, portal-venous contrast), 512 × 512, pixel 0.5859 mm, slice spacing 1.0 mm (SliceThickness 2.0 mm, overlapping reconstruction), IOP (1,0,0,0,1,0), **feet-first supine**, InstanceNumber 1 at the highest z (descending z). Field of view: lung apex to mid-abdomen — liver, kidneys, pancreas, L1 and the gallbladder are **cut by the lower edge** (z index 0), so their volumes below are partial organs.

## 2. Loading and geometry (exact)

Loaded with InVesalius's own functions (`dicom_reader.GetDicomGroups` → `DicomGroup.GetFilenameList` (gdcm.IPPSorter) → `imagedata_utils.dcm2memmap`). IPPSorter reversed the instance order (IM0300, z = 1165.5 mm, first), as the plugin's NIfTI contract assumes. Memory pre-check `calculate_resizing_tofitmemory` = 1.0 (no resize dialog on this machine).

Plugin affine (`nifti_affine`) checked against the raw DICOM headers on 800 random pixels of 4 slices (first, second, middle, last): **maximum world-position error 0.0 mm, 0 HU mismatches** between `Slice().matrix` and the DICOM pixel data.

## 3. TotalSegmentator — integration fidelity and configuration

Runs (RTX 4060 Laptop, CUDA, TotalSegmentator 2.18.0, standard mode):

| Run | Input | Configuration | Time |
|---|---|---|---:|
| R1 | plugin NIfTI | plugin path as shipped until 15/10/2026: `roi_subset=[structure]` | 28–45 s per structure |
| R2 | `dicom2nifti` of the raw DICOM (independent) | full task | 77.7 s |
| R3 | plugin NIfTI | full task | 80.6 s (all 117 classes) |
| R4 | plugin NIfTI | full task + `higher_order_resampling` | 175.0 s |

**Conversion fidelity: Dice(R2, R3) = 1.0000 for every structure** — the plugin's in-memory conversion gives exactly the same segmentation as TotalSegmentator's own DICOM converter.

**Anatomy (R3)**: T1 and trachea at the top, heart mid, liver/kidneys at the bottom; liver centroid at patient right (LPS x 108 mm) and spleen at left (243 mm); left kidney x > right kidney x. Orientation correct.

**roi_subset vs full task (R1 vs R3):**

| Structure | Dice | HD95 | R1 → R3 volume |
|---|---:|---:|---|
| liver | 0.983 | 0 mm | 1130.9 → 1125.5 ml |
| spleen | 0.958 | 0 mm | 104.3 → 104.5 ml |
| stomach | 0.960 | 0 mm | 160.3 → 155.8 ml |
| kidney_left | 0.962 | 0 mm | 77.2 → 74.7 ml |
| kidney_right | 0.932 | 0.59 mm | 55.4 → 58.7 ml |
| aorta | 0.917 | 1.17 mm | 519.7 → 583.0 ml |
| pancreas | **0.816** | 2.02 mm | 23.7 → 32.2 ml |
| inferior_vena_cava | **0.477** | 10.5 mm | 11.3 → 29.5 ml |
| vertebrae_L1 | **0.278** | 26.2 mm | 6.2 → 35.3 ml (2 components in R1) |
| gallbladder | **0** | – | 0 → 1.4 ml |

With `roi_subset`, TotalSegmentator first crops with its rough 6 mm model and predicts only inside that crop; small or thin structures lose voxels or vanish. The full task is TotalSegmentator's standard configuration and labels everything in one run. **Change made:** the provider now runs the full task once per volume and keeps the label image (keyed by a blake2b hash of the voxel values, grid, mode and device; one volume; released on project close/plugin close). Verified on 0543 through the provider: first structure 76.6 s, every further structure 0.65–0.72 s, masks equal to R3 (Dice 1.0000; liver and IVC differ by a few dozen voxels — GPU non-determinism between runs). The 6 mm crop weights (task 298) are no longer required.

**higher_order_resampling (R4 vs R3):** Dice 0.951–0.989, HD95 0 mm (one-voxel boundary shifts), 17–26 % fewer boundary voxels (smoother), image-edge proxy (mean gradient magnitude on the boundary) unchanged within ±5 % with no consistent direction; 2.2 × slower. **Not adopted** — no measurable accuracy gain on this data.

`robust_crop` (3 mm crop model, task 297) was not tested: those weights are not installed, and the full task makes cropping unnecessary.

## 4. Classic tools (silver reference: R3 masks)

**Otsu (plugin, whole volume):** −424 HU → 3095 HU, 38 % of the volume — i.e. it separates air from the body (expected for a two-class Otsu on CT). Otsu restricted to voxels > −500 HU gives 188 HU (contrast-enhanced vessels + bone). Unchanged; documented.

**Region growing (liver, 8 interior seeds, R3 liver as reference):**

| Tolerance | Size vs liver | Outside the liver | Dice mean (min–max) |
|---|---:|---:|---|
| 20 | 1.44 × | 57 % | 0.46 (0.15–0.62) |
| 35 | 2.67 × | 71 % | 0.41 (0.21–0.54) |
| 50 (default) | 3.59 × | 75 % | 0.38 (0.31–0.43) |

It leaks into neighbouring tissue of similar HU through thin bridges. Tested variants: band centre = local 5×5×3 mean, or median-filtered image → no gain (≤ +0.02). Seed on the liver boundary (what a 3D pick gives): Dice 0.36 (0.03–0.51). Opening before labelling (bridge cutting, radius 1–3): liver 0.44 → 0.57–0.66 but unstable (min 0.21–0.38), aorta 0.26 → 0.29, 2.5 × slower. **Not adopted.** Region growing is not a suitable tool for soft organs in contrast CT; use TotalSegmentator for organs.

**Smoothing (1 pass):**

| Mask | 3D element (before) Δ / Dice to original | In-plane (now) Δ / Dice |
|---|---|---|
| liver | −0.30 % / 0.992 | +0.16 % / 0.998 |
| spleen | +0.87 % / 0.989 | +0.36 % / 0.994 |
| kidney_left | −1.06 % / 0.978 | +0.45 % / 0.993 |
| aorta | +0.80 % / 0.989 | +0.39 % / 0.994 |
| pancreas | −0.78 % / 0.966 | +0.63 % / 0.986 |
| liver on 2 slices | **−100 %** / 0 | +0.14 % / 0.998 |

**Change made:** smoothing now acts within each axial slice (no z neighbours). This closes the E3 smoothing investigation item (0051: 2-slice ROI 174,504 → 0; operator report −94 %).

**Measurements:** liver E4 mesh volume 1121.4 ml vs voxel volume 1125.5 ml (−0.4 %); distance/volume code uses physical spacing correctly.

## 5. Practical notes

- RAM: free memory on this 15 GB machine was 1.7–6 GB during the runs (other applications open; peak use of a run not measured). A first experiment script without a `__main__` guard exhausted memory because nnUNet starts worker processes with "spawn" (each re-ran the script); InVesalius's `app.py` has the guard. Closing other large applications before AI runs on big volumes is advisable.
- Pre-existing test-isolation issue: `test_segmentation_cleanup_integration.py` followed directly by `test_ui_localization.py` fails on the old code too (masks left from the first file); the full suite in its normal order passes.

## 6. Status after this review

| Item | Status |
|---|---|
| Geometry / orientation on an FFS, reversed-instance dataset | exact (0 mm, 0 HU mismatch) |
| AI conversion fidelity | exact (Dice 1.0 vs dicom2nifti) |
| AI configuration | improved: full task + per-volume reuse |
| Smoothing | improved: in-plane |
| Region growing on organs | limited by the method; documented |
| Clinical accuracy | not assessed (no ground truth) |

## 7. Confirmed in the real application (15/10/2026, operator)

0543 in InVesalius, CUDA: vertebrae_L1 129.4 s (first preview, full run), then pancreas and liver **1.3 s each** (reused run); voxel counts within 8–19 voxels of the headless results; overlays on the right anatomy. The cut status line seen in the same screenshots was fixed (ml, wrapping status lines). Details: Manual QA "Operator run 15/10/2026".
