# CT3D Phase 13 — Performance, Comparison & Usability Preparation

## 1. Metadata

| Field | Value |
|---|---|
| Date | 2026-09-16 |
| Repository | Vinhhien871999/invesalius3 |
| Branch | `thesis-ct-roi-tools` |
| HEAD before | `470354a2` (last commit of Phase 12) |
| HEAD after | `787fad80` |
| Python | 3.11.7 (`D:\PyTools\invx-venv\Scripts\python.exe`) |
| pytest | 8.3.5 |
| NumPy | 1.26.4 / SciPy | 1.14.0 / VTK | 9.3.0 / wxPython | 4.2.5 |
| RAM | `RAM_TOTAL≈16.4GB`; `RAM_AVAILABLE` observed as low as **0.55–2.1GB** during this phase's benchmarking (real, measured — this machine is under genuine memory pressure throughout, not a hypothetical constraint) |

## 2. Objectives

Close Manual QA officially (7/7 real PASS reported by the operator); fix remaining documentation drift/hygiene; verify regression after the update; benchmark real performance on real local datasets with a repeatable methodology; prepare an InVesalius-original-vs-ROI-Viewer comparison and a 3D Slicer comparison status (no fabricated data); prepare a SUS usability protocol (no fake participants); prepare the software for Final Audit/Phase 14. No new UI features unless a real bug was found.

## 3. Baseline

`git log --oneline -3` at start: `470354a2` (Phase 12 hash fill-in) → `52004e28` (Phase 12 main) → `95b40f7c` (Phase 11 hash fill-in). `git status`: clean except the same pre-existing, unrelated root-level `.md` file moves noted since Phase 08 (not touched). Confirmed fresh baseline before any change: `tests/ct3d` → 158 passed, 1 skipped; `pyflakes plugins/roi_viewer` → 0 findings.

## 4. Manual QA Closure

**Source of evidence**: reported directly by the human operator in this phase's request — a real mouse/GUI session on `D:\PyTools\dicom_samples\0051` (CT, SIEMENS). Claude Code did not perform any mouse/keyboard interaction and did not generate any screenshot; every "Screenshot" field in `docs/CT3D_MANUAL_QA_CHECKLIST.md` is recorded verbatim as *"Evidence visually supplied by operator during manual QA session; image file not stored in repository."* — no fabricated path.

| ID | Result | Key evidence (verbatim from operator) |
|---|---|---|
| P08.5 (D9/C7 GUI) | **PASS** | Brush added mask outside skull boundary; before Update, surface lacked the corresponding region; after "Update 3D Surface from Selected ROI" (real dialog, not batch mode), surface showed the new protruding region; no crash; no reopen needed |
| B4 (Zoom/Pan 2D) | **PASS** | Zoom/pan worked correctly on all 3 2D views |
| C3 (Rotate/Pan/Zoom 3D) | **PASS** | Camera rotate/zoom/pan correct, no distortion, no crash |
| D4 (Brush) | **PASS** | Drew at correct cursor position, persisted across slice change, Disable Brush Tool stopped editing |
| D5 (Eraser) | **PASS** | Erased exactly the brushed region, rest of mask untouched |
| E2 (Distance 2D) | **PASS** | M1=143.951mm, M2=189.741mm (Axial, Linear) — longer segment gave the larger value |
| E3 (Area 2D) | **PASS** | Sagittal=2674.851mm², Coronal=5367.750mm² — larger polygon gave the larger area, full overlay (Area/Min/Max/Mean/Std/Perimeter) shown |

**`MANUAL_QA_COMPLETE = YES`** — 7/7 PASS. Full detail per item: `docs/CT3D_MANUAL_QA_CHECKLIST.md` (rewritten this phase, in place — not duplicated).

## 5. Documentation Hygiene Fixes

- `docs/CT3D_MASTER_PROGRESS.md`: removed the closed "Manual QA 7 mục" item from High-priority remaining work; "Manual QA remaining" section now states 0 pending; B4/C3/D4/D5/E2/E3 rows raised to `WORKING`; D9 row appended with the real-GUI closure note; baseline/history updated to Phase 13.
- `docs/CT3D_FEATURE_AUDIT.md`: B4/C3/D4/D5/E2/E3 raised `NEEDS_MANUAL_QA` → `WORKING` with the operator's real evidence cited per row; D9/C7's status is **unchanged** (already `WORKING` since Phase 08) — only a "Phase 13 manual closure" note was appended, exactly as instructed (no functional-status change beyond the 6 explicit items).
- `docs/CT3D_REMAINING_WORK.md`: item "1c" (7-item manual QA) marked closed with real results, removed from the priority table; item "3" (multi-vendor) no longer says "chưa đọc 0801/mri3" — corrected to state both are confirmed real (Philips); item "4" (Dice/Jaccard/Hausdorff) no longer says "hoàn toàn chưa thực hiện" — corrected to "infrastructure complete, synthetic validation complete, real ground-truth `BLOCKED_EXTERNAL_DATA`"; item "5" (SUS) updated to reference the new protocol document.
- `docs/CT3D_CHANGELOG.md`: the ambiguous "158 passed → 159" wording (which could misread as "159 passed") corrected to explicit "158 passed, 1 skipped (159 collected)".
- `docs/CT3D_MANUAL_QA_CHECKLIST.md`: button names verified against real source before writing (`segmentation_panel.py`: `btn_update_surface` label is literally `"Update 3D Surface from Selected ROI"`; `btn_toggle_brush` toggles between `"Enable Brush Tool"`/`"Disable Brush Tool"`; `rb_brush_draw`/`rb_brush_erase` radio buttons are literally `"Draw"`/`"Erase"` — the old checklist's `"Toggle Brush"` name never existed in source, corrected).

## 6. CSV Integrity Fix

`docs/CT3D_P12_QUANTITATIVE_RESULTS.csv` row `AREA-M-U-scaled`: the `Notes` field `Unit square spacing (2.0,3.0)mm` contained an unquoted comma, producing an 11-field row against a 10-field header. Fixed by quoting: `"Unit square spacing (2.0,3.0)mm"`. Verified with Python's `csv` module (34/34 data rows, all 10 columns, 0 parse errors) **and** `pandas.read_csv()` (shape `(34, 10)`, same column list). No metric values were changed — only the quoting.

## 7. Regression Baseline

Re-ran after all documentation edits above (no code changes yet at this point):
```
tests/ct3d -q            -> 158 passed, 1 skipped (3x consecutive, see Section 20)
pyflakes plugins/roi_viewer -> 0 findings
```

## 8. Benchmark Methodology

New tracked tool: `tools/ct3d_benchmark.py` (not ad-hoc, not inside the GUI — a standalone script importing `plugins.roi_viewer.core` modules directly, real machine-readable CSV output). Modes: `--mode import` (one real import per process launch), `--mode full` (one real import, then Otsu/Region Growing/Surface build/Rendering FPS repeated within the same process), `--mode saveopen` (no DICOM import needed, direct `Mask()`/`Project()` construction).

**A real finding during script development, kept and documented rather than discarded**: the first `--mode full` attempt on `0051` used the real Otsu-derived threshold range at `"Optimal *"` surface quality and **stalled this machine** (confirmed via `Get-Process` CPU deltas ≈0 over real elapsed time — genuinely stuck, not just slow) under the observed low RAM (0.55–1.9GB free at various points) — killed via verified-PID `Stop-Process` (same safe-kill discipline established after the Phase-08-era incident: exact PID/command-line confirmed via `Get-CimInstance Win32_Process` before any kill, never by image name). Root cause: `"Default"` algorithm's marching-cubes cost is dominated by the **full original image array size**, not by mask sparsity (confirmed: a run with `mask_foreground_fraction≈0.0000` still took multiple seconds) — combined with `"Optimal *"` quality's `imagedata_resolution=0` (no downsampling, per `invesalius.constants.SURFACE_QUALITY`), this was a genuinely heavy real-CT-scale operation on a RAM-constrained machine, not a bug. **Fixed methodology**: `"Low"` quality (`imagedata_resolution=3`, real downsampling) and, separately, a repeat-run experiment showed that repeating the SAME build 3x back-to-back made each subsequent run 6-7x slower (9.5s → 66-67s) — most likely `multiprocessing.Pool` startup/contention compounding under real memory pressure. **Surface build is therefore benchmarked only ONCE per dataset** (not 3x) — per the spec's own "≥3 runs **if safe**" qualifier, repeating was empirically shown not to be safe/reproducible on this machine's current RAM state. Otsu/Region Growing/Rendering (cheap, stable, no multiprocessing) are still run 3x each with min/median/max reported. Import runs one real process launch per sample (Phase 12 already found bare singleton resets between sequential in-process imports cause a real `KeyError`/`wxAssertionError` — not repeated here).

RAM safety check (Region Growing and, implicitly, Surface build): real `psutil.virtual_memory().available` checked immediately before; working-set estimated from the **actual** loaded volume's shape/dtype (never hardcoded), 3× safety factor; `BLOCKED_BY_MEMORY` if the estimate exceeds available RAM (did not trigger this phase — see Section 12).

## 9. Dataset Benchmark Matrix

| Dataset_ID | Modality | Applicable operations run this phase |
|---|---|---|
| `0051` | CT (SIEMENS) | Import ×2, Otsu ×3, Region Growing ×3, Surface build ×1, Rendering ×3 |
| `0801` | CT (Philips) | Otsu ×3, Region Growing ×3, Surface build ×1, Rendering ×3 (import timed in Phase 12: 4.9s, not re-run this phase to conserve time under low RAM) |
| `mri3` | MR (Philips Medical Systems) | Import ×1 (Otsu/Region Growing/Surface build not re-run this phase for MR — Phase 12 already covers this dataset's real import; not interpreted as a CT-specific benchmark, and no claim is made that Otsu/RG were exercised on it this phase) |
| `synthetic_small` | N/A (controlled, not from the dataset registry) | Project Save/Open ×3 — small controlled case per the spec's own instruction (30×128×128), not a registry dataset |

Full raw data: `docs/CT3D_P13_PERFORMANCE_RESULTS.csv` (29 rows, verified with Python's `csv` module and pandas — 0 parse errors).

## 10. Import Performance

| Dataset | Runs | Min | Median | Max |
|---|---:|---:|---:|---:|
| `0051` (CT, 108×512×512, 28,311,552 voxels) | 2 | 8.181s | 8.226s | 8.271s |
| `mri3` (MR, 256×256×180, 11,796,480 voxels) | 1 | 7.819s | 7.819s | 7.819s |

RSS delta per real import: `0051` ≈ +305MB, `mri3` ≈ +210MB — consistent with each dataset's real voxel count (int16 source array + InVesalius's own internal buffers).

## 11. Otsu Performance

| Dataset | Runs | Min | Median | Max | Real result range |
|---|---:|---:|---:|---:|---|
| `0051` (CT) | 3 | 0.435s | 0.443s | 0.448s | (-405, 3033) HU |
| `0801` (CT) | 3 | 0.637s | 0.643s | 0.647s | (-472, 3095) HU |

Pure numpy histogram computation on the real loaded volume — fast, stable, near-zero RSS delta (<2MB) in all 6 runs.

## 12. Region Growing Performance

| Dataset | Runs | Min | Median | Max | Seed | Output fraction |
|---|---:|---:|---:|---:|---|---:|
| `0051` (CT, 28.3M voxels) | 3 | 0.385s | 0.503s | 0.520s | volume center, tolerance=100 HU | 24.17% (correctly exceeds the 20% warning threshold) |
| `0801` (CT, 42.5M voxels) | 3 | 0.569s | 0.716s | 0.726s | volume center, tolerance=100 HU | 15.96% (correctly under the 20% threshold) |

RAM safety check passed both times (estimated peak well under real available RAM; RSS delta ≤43MB in all runs). Consistent with Phase 12's `0051` finding (0.30s single-run) within normal machine-load variance. Algorithm unchanged (per the explicit instruction not to alter it for benchmark cosmetics).

## 13. Surface Build Performance

| Dataset | Runs | Runtime | Mask threshold (real, narrow band near Otsu max) | Foreground fraction | Points/Cells | Result |
|---|---:|---:|---|---:|---|---|
| `0051` | 1 | 10.044s | (2933, 3033) HU | ~0.0000 | 13 / 8 | PASS |
| `0801` | 1 | 12.652s | (2995, 3095) HU | ~0.0000 | 0 / 0 | **FAIL** (empty mesh) |

Algorithm: `"Default"` in both cases (masks were threshold-derived, never hand-edited — `mask.was_edited` stayed `False`, so the D9 policy correctly kept `"Default"`, not `"Binary"` — no regression, policy unchanged). Quality: `"Low"` (real downsampling, `imagedata_resolution=3`). The `0801` result is a genuine, explainable outcome (not a bug): the deliberately narrow 100-HU band near this dataset's real Otsu maximum happened to contain zero voxels for this specific real CT — narrowing the band was a benchmark-design choice to keep the mask "controlled/small" (Section 8), and for `0801` it went all the way to empty. Reported honestly as `FAIL` for that specific run, not hidden or re-run with a wider band to force a PASS.

## 14. Rendering Performance

Real VTK API: `vtkRenderer.GetLastRenderTimeInSeconds()` (confirmed via direct introspection this phase - NOT on `vtkRenderWindow`, an initial wrong assumption that was caught and fixed, not left silently broken). `viewer.ren` is the same real renderer attribute this project already uses elsewhere (`core/marker_3d.py`'s `attach(renderer)`).

| Dataset | Runs | Render time | Reported FPS | Note |
|---|---:|---:|---:|---|
| `0051` | 3 | 0.0001s (floor) | 10000.0 | Mesh has only 13 points - render time is below meaningful measurement granularity, **not a representative real-world FPS figure**; reported honestly rather than omitted or dressed up |
| `0801` | 3 | 0.0001s (floor) | 10000.0 | Same caveat - mesh was empty (0 points) |

**Rendering_mode = Surface** in every row (explicit, per the spec's requirement never to conflate this with volume raycasting). **C6 (volume rendering raycasting) remains `NOT_CONNECTED`** - unchanged, confirmed again this phase by the same real-code-path reasoning as prior rounds (`invesalius/data/volume.py.Volume.OnShowVolume()` has zero real call-sites).

## 15. Memory Observations

RAM was the dominant constraint this phase, not CPU: `RAM_AVAILABLE` ranged 0.55-2.1GB throughout benchmarking (real, repeatedly measured, never assumed). The stalled first surface-build attempt (Section 8) and the 6-7x slowdown on repeated builds are both real, reproducible symptoms of this constraint on real (not synthetic) operations, distinct from - but consistent with - the same class of RAM sensitivity documented in Phase 08/12's Region Growing findings. `BLOCKED_BY_MEMORY` was never actually triggered this phase (every RAM check passed), but the safety-check methodology proved its worth by informing the "1 run, not 3" decision for surface builds.

## 16. InVesalius Original vs ROI Viewer

| Feature | InVesalius Original | ROI Viewer Extension | Implementation Source | Evidence |
|---|---|---|---|---|
| DICOM import, 2D views, camera, native measurement tools, native mask/surface engine, native Save/Open | Yes (all pre-existing) | Remote-controls the same real tools via pubsub (`"Enable style"`, `"Create surface from index"`, etc.) - never reimplemented | `invesalius/` core, unchanged | `CT3D_FEATURE_AUDIT.md` sections A/B/C/G |
| Centralized ROI workflow (single panel: threshold → edit → surface → measure → annotate → export) | No (native UI spreads these across separate menus/tabs/dialogs) | **New** - `plugins/roi_viewer/gui/roi_panel.py` + 5 sub-panels | Plugin, 100% new | `CT3D_CHANGELOG.md` "Tổng kết" |
| Otsu auto-threshold | No (manual threshold only) | **New** - `core/segmentation.py.auto_threshold_otsu()` | Plugin, new (pure numpy, no new dependency) | `CT3D_FEATURE_AUDIT.md` D2 |
| Region Growing (seed-based, vectorized) | No | **New** - `core/segmentation.py.region_growing()`, `scipy.ndimage.label`-based | Plugin, new (SciPy already a project dependency) | `CT3D_FEATURE_AUDIT.md` D10, this report Section 12 |
| 3D→2D sync (pick in 3D moves 2D slice) | Partial (native, separate mechanism) | Wired into the plugin's own UI flow | Existing InVesalius pubsub, reused | `CT3D_FEATURE_AUDIT.md` C4/C5 |
| 2D→3D marker sync (crosshair shown in 3D) | No | **New** - `core/marker_3d.py.CrosshairMarker3D`, real `"Set cross focal point"` topic reused (not invented) | Plugin, new | `CT3D_P09_INTERACTION_QA_REPORT.md` |
| Annotation with persistence | No (no annotation feature at all) | **New** - `core/annotation.py`, sidecar JSON (native `.inv3` has no working extension point for this - confirmed by source read, see `CT3D_CHANGELOG.md`) | Plugin, new | `CT3D_FEATURE_AUDIT.md` F1-F4 |
| Explicit manual surface rebuild after mask edit | Implicit/automatic in native flow (different UX) | **New button + real root-cause fix** (D9/C7 - `algorithm="Default"` never read mask data; fixed) | Plugin UI + a genuine bug found and fixed in the plugin's own code | `CT3D_P08_ROI3D_CLOSURE_REPORT.md` |
| NumPy / VTK PolyData export | No (native supports NIfTI/STL/PLY/OBJ, not NumPy or raw VTK PolyData) | **New** formats added | Plugin, new (reuses `vtkSTLWriter`/`vtkPolyDataWriter` already in InVesalius, no new dependency for VTK; NumPy via `numpy.save`) | `CT3D_FEATURE_AUDIT.md` H1-H5 |
| ROI management (rename/hide/delete, synced with native Masks tab) | Native "Masks" tab only | **New** - `core/roi_manager.py`, a cache/view over the real `Project().mask_dict` (not a second source of truth) | Plugin, new | `CT3D_FEATURE_AUDIT.md` D8 |
| Quantitative evaluation (Dice/Jaccard/Hausdorff) | No | **New** - `core/evaluation.py` | Plugin, new (Phase 12) | `CT3D_P12_QUANTITATIVE_VALIDATION_REPORT.md` |

Per the spec's explicit instruction: no feature InVesalius already had natively is claimed here as the thesis's own new code - every "ROI Viewer Extension" cell above is sourced back to a real file/report, and every "InVesalius Original" row is explicitly credited as pre-existing/reused, not reimplemented.

## 17. 3D Slicer Comparison Status

Checked this machine for a real 3D Slicer installation: `Get-Command Slicer`, `C:\Program Files\*Slicer*`, `%LOCALAPPDATA%\Programs\*Slicer*` - **none found. 3D Slicer is NOT installed.** No runtime/FPS numbers for 3D Slicer are fabricated. A functional (feature-availability) comparison, not a performance comparison, is given instead:

| Aspect | InVesalius + ROI Viewer | 3D Slicer |
|---|---|---|
| DICOM import, native segmentation editor, 3D surface generation | Yes (native + plugin) | `NEEDS_EXTERNAL_VERIFICATION` - no local install to confirm current-version behavior directly |
| Otsu auto-threshold in this specific workflow | Yes (plugin, this thesis) | `NEEDS_EXTERNAL_VERIFICATION` |
| Region Growing (seed-based) | Yes (plugin, this thesis) | `NEEDS_EXTERNAL_VERIFICATION` (Slicer has a "Grow from seeds" effect in its Segment Editor, per its public documentation, but this claim is not independently verified against a running instance here - no source/runtime evidence available in this environment) |
| Bidirectional 2D↔3D crosshair sync | Yes (native 3D→2D; plugin-added 2D→3D, Phase 09) | `NEEDS_EXTERNAL_VERIFICATION` |
| Annotation persisted with project | Yes (plugin sidecar JSON, Phase 06/Round-2-era) | `NEEDS_EXTERNAL_VERIFICATION` |
| Quantitative segmentation metrics (Dice/Jaccard/Hausdorff) | Yes (plugin, Phase 12, synthetic-validated) | `NEEDS_EXTERNAL_VERIFICATION` (Slicer has a "Segment Comparison" module per public documentation - not independently verified here) |
| Export formats | NIfTI/STL/PLY/OBJ (native) + NumPy/VTK PolyData (plugin) | `NEEDS_EXTERNAL_VERIFICATION` |
| Performance (import/segmentation/render time) | Real, measured this phase (Sections 10-14) | **No comparable number produced** - would require a real installed instance, real dataset, real methodology; not fabricated |

**3D Slicer real benchmark available: NO.** This table only records features this project could verify are real (InVesalius+ROI Viewer side, all cited to real files/reports) versus features attributed to 3D Slicer from its own public documentation without independent local verification (marked `NEEDS_EXTERNAL_VERIFICATION`, never asserted as confirmed).

## 18. SUS Protocol Status

`docs/CT3D_SUS_PROTOCOL.md` created: objectives, target participants (radiologists/technologists/students with relevant background), eligibility, a concrete task scenario (9 real plugin operations), the unmodified 10-question SUS instrument (Brooke 1996), the standard 5-point Likert scale, the standard scoring formula (odd items: `x-1`; even items: `5-x`; sum×2.5; average across participants), an anonymized-storage plan (participant IDs only, no PII), and a consent/privacy note. **`SUS_PROTOCOL_READY = YES`, `SUS_REAL_PARTICIPANTS_COMPLETE = NO`** - 0 real participants so far; no fake participant or score was created.

## 19. Manual QA Final Matrix

| ID | Result |
|---|---|
| P08.5 | PASS |
| B4 | PASS |
| C3 | PASS |
| D4 | PASS |
| D5 | PASS |
| E2 | PASS |
| E3 | PASS |

**7/7 PASS. `MANUAL_QA_COMPLETE = YES`.**

## 20. Automated Regression

| Suite | Collected | Passed | Failed | Skipped |
|---|---:|---:|---:|---:|
| `tests/ct3d` | 159 | 158 | 0 | 1 (`pynrrd` absent) |
| `tests/` (upstream) | 94 | 94 | 0 | 0 |

Three consecutive `tests/ct3d` runs after all Phase 13 documentation edits: `158 passed, 1 skipped` × 3 (0.95s/1.12s/1.10s - see Section 7). `pyflakes plugins/roi_viewer`: 0 findings (re-confirmed after every edit this phase, including the new `tools/ct3d_benchmark.py`).

## 21. Bugs Found

1. `CT3D_P12_QUANTITATIVE_RESULTS.csv` had one real CSV-quoting defect (Section 6) - a documentation/data-file bug, not a code bug.
2. A wrong initial assumption in this phase's own new benchmark tool (`GetLastRenderTimeInSeconds()` on `vtkRenderWindow` instead of the real location, `vtkRenderer`) - caught via direct introspection before being reported as a false "FAIL", not left silently wrong.
3. `"Default"`-algorithm surface builds at `"Optimal *"` quality on a real, RAM-constrained machine can stall (Section 8) - a real, reproducible environment/performance characteristic, not a plugin logic bug (the D9 algorithm-choice policy itself is correct and unchanged; this is a raw compute-cost/RAM finding about the "Default" contour-the-whole-image behavior already documented since Phase 08).

## 22. Bugs Fixed

Item 1 (CSV) is fixed. Item 2 (benchmark tool's own API assumption) is fixed. Item 3 is not a code bug to "fix" - documented as a real performance/RAM characteristic and worked around methodologically (Low quality, single-run for surface builds) rather than papered over.

## 23. Remaining External Blockers

GE/Canon CT vendor data, real (non-synthetic) segmentation ground-truth, and real SUS participants all remain `BLOCKED_EXTERNAL_DATA` / not yet collected - none fabricated this phase either.

## 24. Release Readiness

- **`AUTOMATED_TECHNICAL_READY` = YES.** Regression clean (158/158 non-skipped `ct3d` tests ×3 runs; 94/94 upstream), `pyflakes` clean, no critical bug open.
- **`MANUAL_QA_COMPLETE` = YES.** 7/7 real PASS (Section 4/19).
- **`SOFTWARE_TECHNICAL_COMPLETE` = YES.** (Automated suite clean AND manual QA 7/7 PASS AND no critical bug - exactly the criteria given this phase for this specific label, distinct from and narrower than "release readiness" in general.)
- **`EXTERNAL_VALIDATION_COMPLETE` = NO** → equivalently, **`RESEARCH_EXTERNAL_VALIDATION_COMPLETE` = NO.** GE/Canon vendor data, real segmentation ground-truth, and real SUS participants are all still missing (Section 23).
- **`RELEASE_CANDIDATE_READY`**: this label's definition in the canonical docs (`CT3D_MASTER_PROGRESS.md`/prior phase reports) was never previously pinned to a precise formula, so per this phase's own instruction ("không tự thay định nghĩa cũ - giải thích chính xác tiêu chí"), it is reported here using the same criteria Phase 12's report used for it (no critical bug; automated suite PASS; manual QA critical workflow PASS; known limitations documented): by that same standard, **YES** as of this phase (manual QA is now complete, which it was not in Phase 12). This is **not** the same claim as `EXTERNAL_VALIDATION_COMPLETE`, which remains `NO` - the two are tracked separately, and `RELEASE_CANDIDATE_READY=YES` here means "ready as a technical release candidate for further (e.g. Phase 14 final audit / eventual external validation) work," not "externally validated."

## 25. Files Changed

New: `tools/ct3d_benchmark.py`, `docs/CT3D_P13_PERFORMANCE_COMPARISON_REPORT.md` (this file), `docs/CT3D_P13_PERFORMANCE_RESULTS.csv`, `docs/CT3D_SUS_PROTOCOL.md`.
Updated: `docs/CT3D_MANUAL_QA_CHECKLIST.md` (rewritten in place with real 7/7 PASS evidence), `docs/CT3D_MASTER_PROGRESS.md`, `docs/CT3D_FEATURE_AUDIT.md`, `docs/CT3D_REMAINING_WORK.md`, `docs/CT3D_CHANGELOG.md`, `docs/CT3D_P12_QUANTITATIVE_RESULTS.csv` (CSV-quoting fix only, no metric values changed).

## 26. Phase Gate

`PHASE_GATE: PASS`

Checklist against the spec's own 13 gate criteria: (1) Manual QA docs show 7/7 PASS - yes; (2) B4/C3/D4/D5/E2/E3 changed to WORKING - yes; (3) D9/C7 has GUI evidence appended - yes; (4) P12 CSV parses with a standard CSV parser - yes (Section 6); (5) Remaining Work has no stale Phase-12 text - yes (Section 5); (6) test counts consistent across docs - yes (Section 7 of this report, and the changelog fix in Section 5); (7) `tests/ct3d` PASS 3x - yes (Section 20); (8) upstream suite PASS - yes (94/94); (9) `pyflakes` clean - yes; (10) performance benchmark has methodology and raw results - yes (Sections 8-15, `CT3D_P13_PERFORMANCE_RESULTS.csv`); (11) comparison does not fabricate data - yes (Sections 16-17, 3D Slicer explicitly marked `NEEDS_EXTERNAL_VERIFICATION` where unverified); (12) SUS is protocol-only (no fake participants) - yes (Section 18); (13) no new critical bug - yes (Section 21/22, all addressed or documented as real environment characteristics, not code defects).

## 27. Phase 14 Recommendation

Not started this turn per explicit instruction. Candidates for Phase 14 (Final Audit & Release Candidate, per the spec's own naming): a final, holistic re-read of every canonical doc for cross-consistency; a release-notes/changelog summary spanning Phases 08-13; the smoke-test checklist already sketched in this phase's spec (Section XX, not executed by Claude Code this turn since evidence already exists for most items across prior phases - a final consolidated run-through could still be valuable); continued pursuit of the remaining `BLOCKED_EXTERNAL_DATA` items (GE/Canon data, real segmentation ground-truth, SUS participants) whenever external access becomes available.
