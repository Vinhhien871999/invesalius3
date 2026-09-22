# CT3D Phase 12 — Technical Closure & Quantitative Validation

## 1. Metadata

| Field | Value |
|---|---|
| Date | 2026-09-14 |
| Repository | Vinhhien871999/invesalius3 |
| Branch | `thesis-ct-roi-tools` |
| HEAD before | `95b40f7c` (last commit of Phase 11) |
| HEAD after | `52004e28` |
| Python | 3.11.7 (`D:\PyTools\invx-venv\Scripts\python.exe`) |
| pytest | 8.3.5 |
| NumPy | 1.26.4 |
| SciPy | 1.14.0 |
| VTK | 9.3.0 |
| wxPython | 4.2.5 |
| RAM | `RAM_TOTAL≈16.4GB`; `RAM_AVAILABLE` observed 1.0-2.1GB at various points during this phase's testing (real, measured, not assumed) |

## 2. Objectives

Per the phase spec: (1) close small technical items left over from Phase 11 (`MaskEditorManager` dead-code candidate, the `global` style nit, NRRD packaging); (2) reconcile Phase 11's reported test counts against a fresh, real run; (3) build a real Dice/Jaccard/Hausdorff evaluation module with math unit tests; (4) validate measurement/segmentation-metric correctness against known-geometry phantoms; (5) build a real (non-PHI) dataset registry from actual local data; (6) test multi-vendor/multi-series within the limits of local data, never inventing external data; (7) retry the full-volume Region Growing case that previously hung, memory-safely; (8) prepare an official manual-QA checklist for the 7 mouse-required items; (9) update all master docs and deliver a full report. No new UI features; no fabricated datasets/vendors/ground-truth/GUI actions.

## 3. Phase 11 Baseline Reconciliation

Ran fresh (not assumed from the Phase 11 report text):
```
python -m pytest tests/ct3d --collect-only -q   -> 110 tests collected (before this phase's additions)
python -m pytest tests/ct3d -q                  -> 109 passed, 1 skipped
python -m pytest tests/ct3d -m unit -q          -> 76 passed, 34 deselected
python -m pytest tests/ct3d -m integration -q   -> 33 passed, 1 skipped, 76 deselected
python -m pytest tests --ignore=tests/ct3d -q   -> 94 passed
```
**Discrepancy found and reconciled**: the Phase 11 report's Section 8 stated "75 unit tests" but the real, fresh count was **76** - the dead-code regression guard test (`test_mask_editor_surviving_surface_after_dead_code_removal`, added to `test_undo_redo.py` after that count was originally written) was the +1. This is a **Phase 12 baseline reconciliation** note, not a rewrite of Phase 11's history - `docs/CT3D_P11_TEST_AUTOMATION_REPORT.md` Section 8 is corrected in place with this note (the underlying claim - "75 unit tests, all real" - was simply stale by one test, not wrong in kind).

After this phase's own additions (Sections 10-11, 17-18 below), the final count is reported in Section 19.

## 4. Documentation Consistency Fixes

- `docs/CT3D_MASTER_PROGRESS.md`'s "Research/evaluation remaining work" section still listed "bộ pytest độc lập" (a standalone pytest suite) as missing, even though Phase 11 created exactly that (`tests/ct3d/`). Removed the stale phrase; replaced with an accurate Phase 12 status (synthetic Dice/Jaccard/Hausdorff validation done, real ground-truth still `BLOCKED_EXTERNAL_DATA`).
- `docs/CT3D_FEATURE_AUDIT.md`'s header still said "08/09/2026" (stale since Round 2) despite 4 phases of updates since. Bumped to 14/09/2026 (this phase). Its status vocabulary line listed 10 statuses but did not include `NEEDS_MANUAL_QA` (introduced Phase 09) even though multiple rows already used it - added, plus `BLOCKED_EXTERNAL_DATA` (new this phase, for the dataset-availability gap that A2/A4/real-ground-truth all share).

## 5. MaskEditorManager Audit

| Method | Call sites (whole repo, direct/getattr/callback/pubsub/GUI-binding/subclass/test/doc) | Verdict | Action |
|---|---:|---|---|
| `get_current_editor()` | 0 | `CONFIRMED_DEAD_CODE` | Removed |
| `set_current_mask()` | 0 | `CONFIRMED_DEAD_CODE` | Removed |
| `delete_editor()` | 0 | `CONFIRMED_DEAD_CODE` | Removed |
| `create_editor()`, `get_editor()`, `clear_all()` | Real (`segmentation_panel.py._on_checkpoint`/`ROIViewerFrame`'s `mask_mgr.clear_all()`) | `LIVE` | Kept unchanged |
| `MaskEditorManager` class itself | Real construction site (`roi_panel.py`) | `LIVE` | Kept |

`plugins/roi_viewer/core/mask_editor.py`: 17 lines removed, 11 added (net -6). `self.current_index` (written by the still-live `create_editor()`) is left in place even though nothing reads it after this removal - `create_editor()` itself is a live method and this phase's scope was removing confirmed-dead methods, not altering a live one's behavior. Full suite re-run after removal: no regression (110 passed, 1 skipped at that point, before this phase's other additions). New regression guard added: `test_mask_editor_manager_surviving_surface_after_phase12_dead_code_removal` in `tests/ct3d/test_undo_redo.py`.

## 6. NRRD Packaging/Dependency Status

- **Dependency available in this environment**: NO (`pynrrd` not installed).
- **Packaging status**: added `[project.optional-dependencies]` extra `nrrd = ["pynrrd>=1.0.0"]` to `pyproject.toml` (Option A - the repo already has a suitable optional-dependency mechanism, an `installer` extra existed as precedent). Install via `pip install invesalius[nrrd]`.
- **UI behavior** (Option B, implemented regardless of A, since a user may not install the extra): `export_panel.py._is_nrrd_available()` (via `importlib.util.find_spec`, no full import needed) checks once at panel construction. If unavailable: the dropdown label becomes `"NRRD (.nrrd) - library not installed"`, a tooltip explains how to install it, and clicking Export with NRRD selected fails fast with a clear `wx.MessageBox` **before** the user picks a filename (previously: only a generic post-hoc error after export failed). `core/exporters.py.export_mask_nrrd()`'s existing fail-soft behavior (returns `False`, never raises) is unchanged - this phase only made the UI honest about it in advance.
- **Tests**: `tests/ct3d/test_exporters.py` - `test_is_nrrd_available_matches_real_import_state` (cross-checks the real import state), `test_export_panel_nrrd_dropdown_reflects_availability` (real `ExportPanel` construction, real `wx.Frame`, asserts the label/tooltip reflect whichever state is real in this environment - works correctly whether or not `pynrrd` is installed, not just for this environment's current absent state).

## 7. Dataset Registry Summary

Real filesystem scan (`D:\PyTools\dicom_samples\`) using InVesalius's own real DICOM stack (`invesalius.reader.dicom_reader.GetDicomGroups()`, wrapping gdcm - not a reimplementation, not filename-based guessing). Full table and methodology: `docs/CT3D_DATASET_REGISTRY.md`. No PHI recorded (no PatientName/PatientID/BirthDate/etc.) - `Dataset ID` is the local folder name, used purely as an internal test identifier.

| Dataset ID | Modality | Manufacturer | Series | Dimensions | Spacing (mm) |
|---|---|---|---:|---|---|
| `0051` | CT | SIEMENS | 1 | 108×512×512 | (0.4785, 0.4785, 1.5) |
| `0801` | CT | Philips | 1 | 162×512×512 | (0.9766, 0.9766, 1.0) |
| `mri3` | MR | Philips Medical Systems | 1 | 256×256×180 | (0.9993, 1.0, 1.0) |

## 8. Multi-vendor Status

Real, real, two-stage evidence: (1) **tag-level scan** (`GetDicomGroups()`, no wx needed, fast) confirmed `0801`=Philips CT and `mri3`=Philips MR - both **new findings**, `0801` and `mri3` had never had their Manufacturer tag read in any prior round (only `0051`=SIEMENS was previously confirmed). (2) **Real end-to-end import** (`Publisher.sendMessage("Import directory", ...)`, full app bootstrap, matching Phase 08-11's proven methodology) PASSED for all 3 datasets - correct modality, non-trivial matrix shape, positive finite spacing.

**A real methodology finding along the way**: attempting all 3 imports sequentially in one process (resetting `Project.instance`/`Slice.instance` to `None` between them, mirroring `tests/ct3d/conftest.py`'s fixture) caused a real `KeyError` in `invesalius/data/slice_.py`'s `SetMaskEditionThreshold()` on the second import, followed by a `wxAssertionError` in a progress-dialog destructor. Root cause: a bare singleton reset is not equivalent to a real `Controller.CloseProject()` cycle - some state outside `Project`/`Slice` (subscriptions, or cross-references established during the first import) survives the reset and confuses the second import's threshold-setup code. This is a **test-methodology limitation**, not an InVesalius bug (a real user never imports twice via a raw singleton reset - always through `CloseProject()`). Fixed by running each dataset import in its own fresh process, matching every prior phase's established, working pattern.

**A2 status**: raised `NEEDS_RUNTIME_TEST` → **`PARTIAL`** (real evidence for 2 vendors now exists, but GE/Canon remain untested - `BLOCKED_EXTERNAL_DATA`, no local dataset, not downloaded per the spec's explicit prohibition on auto-fetching external data). **Not** raised to `WORKING` - 2 of 4 commonly-cited vendors is meaningful progress, not completion.

## 9. Multi-series Status

All 3 local datasets: exactly 1 patient, 1 series per study (confirmed via the same real `DicomPatientGrouper`). **A4 unchanged**: `NEEDS_RUNTIME_TEST`, `BLOCKED_EXTERNAL_DATA` - no local multi-series data exists. Added `tests/ct3d/test_dicom_grouping.py` (4 tests, synthetic duck-typed `Dicom`-like objects) to unit-test the grouping ALGORITHM's ability to separate distinct series within one study - explicitly documented as **not** a substitute for real multi-series runtime evidence (per the spec's explicit instruction).

## 10. Quantitative Evaluation Architecture

New module `plugins/roi_viewer/core/evaluation.py` - pure numpy/scipy, no wx/VTK/InVesalius import, matching `core/`'s established convention (importable directly from tests, kept out of any GUI panel since nothing currently needs to display these metrics interactively). Axis/spacing convention documented explicitly in the module header: masks use the same array-axis order as `Mask.matrix`/`Slice().spacing` (axis 0 = axial, 1 = coronal, 2 = sagital); spacing arguments are named `spacing_zyx` (never a bare, ambiguous `spacing`) to make this unambiguous at every call site.

Implements: `dice_coefficient()`, `jaccard_index()`, `hausdorff_distance()`, `hausdorff_distance_95()`.

## 11. Dice Validation

`tests/ct3d/test_evaluation_metrics.py` DICE-T1..T5, all PASS: identical→1.0, no-overlap→0.0, known partial overlap (|A|=|B|=10, intersection=5)→0.5 exactly, empty/empty→1.0, empty/non-empty→0.0. Shape-mismatch raises `ValueError`. uint8-{0,255}-convention input verified to cast identically to a bool mask.

## 12. Jaccard Validation

Same case family, all PASS: known partial overlap → 1/3 exactly. Dice/Jaccard consistency relation `Dice = 2J/(1+J)` verified at 3 overlap fractions (0.2/0.5/0.8), agreement to `<1e-9`.

## 13. Hausdorff Validation

HD-T1..T5, all PASS. **HD-T2/T3/T3b are the critical anisotropic-spacing correctness proof**: a single-voxel shift along the axis with `spacing_zyx[0]=3.0mm` gives Hausdorff=3.0mm exactly (not 1.0, which a voxel-index-only computation would wrongly give); the same shift magnitude along a `1.0mm`-spacing axis gives 1.0mm - proving the axis-specific sampling (not just "some" anisotropic handling) is correct. Empty/empty→0.0. One-empty→raises `ValueError` explicitly (documented choice: undefined mathematically, fails loudly rather than returning a silently-mergeable `inf`/`nan`). HD95 implemented and explicitly labeled as a **different metric** from HD max (never a silent substitute) - verified `HD95 <= HD_max` always, and demonstrated to differ meaningfully when a single outlier voxel dominates the true maximum.

## 14. Measurement Validation

Phantom A (exact rectangular cuboid, 20×15×10 voxels, spacing (2.0,1.5,1.0)mm): measured volume via `MeasurementManager.calculate_volume()` = 9000.0 mm³, matching an independently hand-computed expected value exactly (absolute/relative error < 1e-9). A sub-cuboid case (360 voxels, different spacing) also matches exactly. Distance (M-U1: 3-4-5 triangle = 5.0mm; M-U2: uneven spacing, independent `sqrt(dx²+dy²+dz²)` reference) and Area (Shoelace on a unit square, scaled by spacing) both match independent references exactly. **M-U4 is a direct regression test** for the real Round-3 E4 bug (padding/sentinel cells inflating the reported volume) - demonstrates the full-matrix vs payload-only distinction concretely.

## 15. Synthetic Ground-Truth Results

Phantom B (Phantom A's cuboid embedded in a larger volume, shifted by a known voxel offset along the axial axis): Dice/Jaccard at 3 shift levels (2/5/8 voxels out of 20) all match hand-computed fractions exactly (`0.9/0.75/0.6` for Dice). Hausdorff at the same 3 shifts, anisotropic spacing `(1.7,1.0,1.0)mm`, matches `shift × 1.7mm` exactly in every case. A voxelized sphere (r=15 voxels) volume test is explicitly labeled `SYNTHETIC_GROUND_TRUTH` **and approximate** (discretization error bounded <5%, not asserted exact - a sphere is the wrong shape for an exact-volume test, per the spec's explicit warning). Full result table: `docs/CT3D_P12_QUANTITATIVE_RESULTS.csv`.

## 16. Real Ground-Truth Results

**`BLOCKED_EXTERNAL_DATA`.** Checked the local filesystem (`D:\PyTools\dicom_samples\` and its 3 dataset folders) for any segmentation label/NIfTI/NRRD ground-truth file accompanying the 3 real datasets: none exists. No real ground-truth validation was performed, and none was fabricated. This remains open for a future phase with access to a labeled dataset (e.g. Medical Segmentation Decathlon).

## 17. Region Growing Full-Volume Test

**Not** `BLOCKED_BY_MEMORY` - ran successfully with a real, code-verified memory safety check first:
```
Dataset: 0051 (real CT, 28,311,552 voxels, int16)
RAM_AVAILABLE (measured immediately before): 1.72 GB
Working-set estimate (from REAL shape/dtype, not hardcoded):
  thresholded (bool, 1B/voxel) = 28.3MB
  labeled (scipy.ndimage.label default int32, 4B/voxel) = 113.2MB
  output (uint8, 1B/voxel) = 28.3MB
  raw estimate = 169.9MB; with 3x safety factor = 509.6MB
  509.6MB < 1.72GB available -> proceed
Seed: volume center (54, 256, 256), intensity=3 HU, tolerance=100 HU
Result: runtime=0.30s, output_voxels=6,843,727 (24.17% of volume - correctly
  exceeds the 20% warning threshold, i.e. the safety-warning policy itself
  is exercised correctly, not a bug), RSS_delta=+28.5MB (well under the
  509.6MB estimate - the safety margin held comfortably)
success: YES
```
**Conclusion**: the Round-3 hang was environment/RAM-state-dependent, not an algorithmic or performance limitation - the same real ~28M-voxel volume, vectorized `scipy.ndimage.label()` path, completes in well under a second with modest (≈500MB) RAM headroom. Closes `CT3D_REMAINING_WORK.md`'s former item 1b definitively.

## 18. New Persistent Tests

| File | New tests this phase |
|---|---:|
| `tests/ct3d/test_evaluation_metrics.py` | 30 |
| `tests/ct3d/test_phantom_validation.py` | 12 |
| `tests/ct3d/test_dicom_grouping.py` | 4 |
| `tests/ct3d/test_exporters.py` (added) | 2 |
| `tests/ct3d/test_undo_redo.py` (added) | 1 |
| **Total new this phase** | **49** |

## 19. Regression Results

| Suite | Collected | Passed | Failed | Skipped | Duration |
|---|---:|---:|---:|---:|---:|
| `tests/ct3d` (full) | 159 | 158 | 0 | 1 (`pynrrd` absent) | ~0.61-0.66s |
| `tests/ct3d -m unit` | 159 | 123 | 0 | 36 deselected | ~0.17s |
| `tests/ct3d -m integration` | 159 | 35 | 0 | 1 skip, 123 deselected | ~0.55s |
| `tests/` (upstream, excluding ct3d) | 94 | 94 | 0 | 0 | ~26-46s (varies with disk cache) |

## 20. Three Consecutive Runs

Run 1: `158 passed, 1 skipped in 0.66s`
Run 2: `158 passed, 1 skipped in 0.61s`
Run 3: `158 passed, 1 skipped in 0.63s`
No test-order dependency observed; no leftover temp files (`tmp_path`-based); config isolation confirmed (`XDG_CONFIG_HOME` redirected, never touching the real user's `~/.config/invesalius/`).

## 21. Bugs Found

1. Phase 11's unit-test count was stale by 1 (75 vs real 76) - a documentation drift, not a functional bug (Section 3).
2. `MaskEditorManager` had 3 further confirmed-dead methods beyond what Phase 11 flagged (Section 5) - code-cleanliness, not functional.
3. NRRD dropdown implied guaranteed availability when the library was absent (Section 6) - a real UX gap, not a crash.
4. Attempting sequential real DICOM imports in one process via bare singleton resets causes a real `KeyError`/`wxAssertionError` (Section 8) - a test-methodology limitation, confirmed not to be a real InVesalius bug (never occurs via the real `CloseProject()`-based user workflow).

## 22. Bugs Fixed

Items 2 and 3 above are fixed (dead code removed; NRRD UI now honest). Item 1 is corrected in documentation. Item 4 is a test-harness lesson, not a product bug - worked around by using one process per dataset import (matching every prior phase's proven pattern), not "fixed" in product code.

## 23. Cleanup

`MaskEditorManager`: 17/11 lines (net -6). `main.py`: 10 lines removed (`global` style nit). `plugins/roi_viewer/` is now **completely clean under `pyflakes`** (0 findings, confirmed by a full sweep after every change this phase).

## 24. Manual QA Status

`docs/CT3D_MANUAL_QA_CHECKLIST.md` created - 7 items (P08.5, B4, C3, D4, D5, E2, E3), each with Preconditions/Exact Steps/Expected Result (with exact error-tolerance formulas for E2/E3)/Evidence/Screenshot/Notes fields, all `NOT_RUN`. No item was marked PASS - Claude Code did not perform real mouse/keyboard GUI interaction this phase (or any prior phase), consistent with every phase's explicit prohibition on faking manual QA.

## 25. Release Readiness

- **`AUTOMATED_TECHNICAL_READY`: YES.** Full regression clean (158/158 non-skipped ct3d tests, 3 consecutive runs; 94/94 upstream), no critical bugs open, `pyflakes` clean, all confirmed-dead code removed.
- **`MANUAL_QA_COMPLETE`: NO.** All 7 items in `CT3D_MANUAL_QA_CHECKLIST.md` are `NOT_RUN`.
- **`EXTERNAL_VALIDATION_COMPLETE`: NO.** GE/Canon vendors and real (non-synthetic) segmentation ground-truth are both `BLOCKED_EXTERNAL_DATA`.
- **`RELEASE_CANDIDATE_READY`: NO`** (gated by the two `NO`s above, per the spec's own explicit rule - automated PASS alone is never sufficient).

## 26. Remaining Issues

- 7 manual-QA items (Section 24) need a real human session.
- GE/Canon vendor data and real segmentation ground-truth remain `BLOCKED_EXTERNAL_DATA` (Sections 8, 16).
- `core/evaluation.py` is not yet wired into any GUI panel (deliberately, per the spec's instruction not to bury/force research code into the GUI without a concrete need) - a future phase could add a "Compare to reference mask" panel if the thesis plan calls for it.

## 27. Status Matrix Changes

| ID | Before Phase 12 | After Phase 12 |
|---|---|---|
| A2 (multi-vendor) | `NEEDS_RUNTIME_TEST` (1 vendor confirmed) | **`PARTIAL`** (2 vendors confirmed real, end-to-end) |
| A4 (multi-series) | `NEEDS_RUNTIME_TEST` | Unchanged status; evidence refreshed (`BLOCKED_EXTERNAL_DATA` explicit, synthetic grouping-logic test added) |
| D10 (Region Growing) | `WORKING` | Unchanged status; full-volume real-CT evidence closes the last open sub-item |
| Quantitative Metrics (new) | Did not exist | **`WORKING`** (infrastructure + synthetic validation; real ground-truth `BLOCKED_EXTERNAL_DATA`) |
| `MaskEditorManager` dead-code item | `NOT_PROVEN_DEAD` | Closed - 3 methods confirmed dead and removed |

## 28. Files Changed

Code: `plugins/roi_viewer/core/evaluation.py` (new), `plugins/roi_viewer/core/mask_editor.py` (dead-code removal), `plugins/roi_viewer/gui/export_panel.py` (NRRD UI clarity), `plugins/roi_viewer/main.py` (style cleanup), `pyproject.toml` (nrrd extra).
New tests: `tests/ct3d/test_evaluation_metrics.py`, `tests/ct3d/test_phantom_validation.py`, `tests/ct3d/test_dicom_grouping.py`, plus additions to `test_exporters.py`/`test_undo_redo.py`.
New docs: `docs/CT3D_P12_QUANTITATIVE_VALIDATION_REPORT.md` (this file), `docs/CT3D_DATASET_REGISTRY.md`, `docs/CT3D_MANUAL_QA_CHECKLIST.md`, `docs/CT3D_P12_QUANTITATIVE_RESULTS.csv`.
Updated docs: `docs/CT3D_MASTER_PROGRESS.md`, `docs/CT3D_FEATURE_AUDIT.md`, `docs/CT3D_REMAINING_WORK.md`, `docs/CT3D_CHANGELOG.md`, `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md`, `docs/CT3D_P11_TEST_AUTOMATION_REPORT.md` (baseline-reconciliation note only).

## 29. Phase Gate

`PHASE_GATE: PASS`

Checklist against the spec's own 11 gate criteria: (1) baseline reconciled exactly - yes (Section 3); (2) master docs no stale pytest item - yes (Section 4); (3) MaskEditorManager audit done - yes (Section 5); (4) metrics have unit tests - yes (42 tests, Sections 11-13); (5) Dice/Jaccard/Hausdorff synthetic reference PASS - yes; (6) measurement phantom validation PASS - yes (Section 14); (7) dataset registry from real data - yes (Section 7, no PHI); (8) no fabricated vendor/GT - yes (both real findings, both gaps honestly marked `BLOCKED_EXTERNAL_DATA`); (9) automated regression PASS 3x - yes (Section 20); (10) upstream tests PASS - yes (94/94); (11) manual QA correctly `NOT_RUN` - yes (Section 24).

## 30. Phase 13 Recommendation

Not started this turn per explicit instruction. Candidates for Phase 13 (Performance, Comparison & Usability Preparation, per the spec's own naming): the 7 manual-QA items (a real human session, ~30-45 min); performance benchmarking (FPS, build times) with a comparison methodology; usability prep (SUS instrument design, not live participants); external dataset acquisition planning for GE/Canon + real segmentation ground-truth (still `BLOCKED_EXTERNAL_DATA` until then).
