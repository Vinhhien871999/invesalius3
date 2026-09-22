# CT3D Phase 14 — Final Audit & Software Release Candidate

## 1. Metadata

| Field | Value |
|---|---|
| Date | 17/09/2026 |
| Repository | `Vinhhien871999/invesalius3` (fork), local path `D:\Learns\DeAn\invesalius\invesalius3` |
| Branch | `thesis-ct-roi-tools` |
| HEAD before this phase | `e56594c6929cba4a84fde3053aa85b524703983d` |
| Housekeeping commit (worktree cleanup, before audit proper) | `54f2f479` |
| Main Phase 14 implementation/documentation commit | `bed0c624` |
| Hash-fill-in follow-up commit (updates self-referencing placeholders in this file, `CT3D_MASTER_PROGRESS.md`, `CT3D_CHANGELOG.md`) | `6dae0922` |
| HEAD after this phase (as originally written, 17/09/2026) | `bed0c624` — **this was imprecise; see Post-Phase-14 Release Closure Corrections below for the reconciled value** |
| Python | 3.11.7 (`D:\PyTools\invx-venv\Scripts\python.exe`) |
| This is the **FINAL** phase of the software roadmap (Phase 08→14). **No Phase 15.** |

## 2. Objective

Close out the software roadmap: reconcile C8 (Visual Sync 2D→3D) manual evidence truthfully, fix documentation drift accumulated across Phase 12→13.5, reconcile benchmark data issues found in Phase 13, run full regression/static analysis one final time, verify no PHI/hardcoded machine paths, and produce release-candidate documentation. No new features, no large refactors, no architecture changes without a real bug, no fabricated data/evidence.

## 3. Git Lineage & Worktree Audit

- `git log --graph --decorate --oneline` confirmed a fully linear history (no branches/merges) from the start of this phase's HEAD back through Phase 08.
- `git status --short` at phase start showed the same pre-existing, uncommitted state flagged in every report since Phase 08: 3 root-level Vietnamese planning `.md` files shown as tracked-deleted, with untracked copies under `docs/`, plus one untracked orphan (`docs/Phan_tich_tien_do_tong_the.md`).
- **Resolved this phase** (not just documented — actually fixed): read both the git-tracked-deleted root content (`git show HEAD:<path>`) and the untracked `docs/` content directly, and diffed them (`diff --strip-trailing-cr`, after discovering an ordinary Windows CRLF-only difference masked the comparison at first). All 3 files are **byte-identical content moves** (CRLF-only difference). `docs/Phan_tich_tien_do_tong_the.md` is a separate, legitimate, previously-uncommitted progress-analysis snapshot (dated post-Phase-10, 14,026 bytes) with no root counterpart.
- Finalized the move as a real git rename via `git add`/`git commit` (commit `54f2f479`) rather than leaving it ambiguous — `git status` is now clean. This is not a destructive action: no content was altered or discarded, only a pre-existing, never-finalized move was completed after verifying byte-identical content.
- `origin/thesis-ct-roi-tools` remains pinned at `b5d304fb` (end of Phase 09) — no push was requested or performed this phase.

## 4. C8 Surface-Rebuild Guard Verification

`grep -rn "Create surface from index" plugins/roi_viewer` returns exactly **1** match: `gui/segmentation_panel.py:866`, inside the explicit "Update 3D Surface from Selected ROI" handler. It does **not** appear anywhere in `gui/roi_panel.py`'s `on_cross_focal_point_changed()` (the crosshair/C8 sync path), whose docstring already states "Does NOT touch the camera... and does NOT rebuild any surface — only actor geometry moves." Confirmed by direct source read, not inference.

## 5. C8 Manual QA Reconciliation

The operator ran one general **smoke test** of the C8 core path (native `"Slices' cross intersection"` tool ON, `Sync 2D -> 3D` ON, click/drag on a 2D view) and reported: marker and slice planes move correctly to match the 2D crosshair position; the 3D surface geometry itself does not change (by design). This is recorded truthfully as **`C8_VISUAL_OPERATOR_SMOKE = PASS`** in `CT3D_MANUAL_QA_CHECKLIST.md`.

The 9 lettered itemized subtests (TEST A-I: per-axis Axial/Sagittal/Coronal, continuous drag, planes-toggle-off, sync-off, sync-on-again, camera-preserved, reattach/no-duplicate-actor) were **not individually confirmed** by the operator during that session. Per this phase's explicit instruction not to fabricate coverage beyond what was actually reported, each of these 9 is recorded as **`NOT_EXPLICITLY_MANUAL_VERIFIED`** — not `PASS`, not `FAIL`. This is separate from, and does not replace, the 25 automated regression tests (16 `SP3D-T` + 9 `SYNC3D-T`) that already independently and mechanically verify toggle/lifecycle/no-duplicate-actor/visibility/pick-safety behavior — those remain 25/25 PASS, unaffected by this phase.

The original 7/7 manual QA items (P08.5, B4, C3, D4, D5, E2, E3) from Phase 13 are **unchanged**, still 7/7 PASS with the same operator-supplied numeric evidence (E2: M1=143.951mm/M2=189.741mm; E3: Sagittal=2674.851mm²/Coronal=5367.750mm²).

## 6. Documentation Consistency Fixes

- `docs/CT3D_MANUAL_QA_CHECKLIST.md`: C8 section rewritten per §5 above.
- `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md`: header updated (previously still read "Phase 12" despite containing Phase 13.5 content); the existing C8 usage instructions (3-step manual prerequisite: enable native cross-intersection tool → enable Sync 2D→3D → optionally enable Show slice planes; explicit "does not rebuild surface" statement) were already correct and needed no further change.
- `docs/CT3D_FEATURE_AUDIT.md`: top metadata updated (14/09→17/09/2026, Phase 12→Phase 14 header). Fixed a real internal inconsistency: rows B4/C3/D4/D5/E2/E3 had `Status=WORKING` (raised in Phase 13 from real manual QA evidence) but their separate `Runtime` column still literally read the old `NEEDS_MANUAL_QA` value — now `✓ (manual)`. C8's `Runtime` column changed from a bare `✓` to `✓ automated + operator visual smoke` to reflect the actual evidence composition (automated regression + one operator smoke test, not itemized manual coverage).
- `docs/CT3D_MASTER_PROGRESS.md`: `Current phase: 14`, `Last completed phase: 14`, `Next phase: NONE`, added explicit "Software roadmap complete" wording, added history rows for `13.5` and `14`, updated the C8/Sync row and Manual QA Remaining section to reflect §5.
- `docs/CT3D_REMAINING_WORK.md`: added a Phase 14 closing paragraph; added one new P3-optional line item for the 9 itemized C8 subtests (explicitly non-blocking). No stale P1-sounding entries were found — the file was already accurately reflecting Phase 13's closure.
- `docs/CT3D_CHANGELOG.md`: appended a final Phase 14 entry (Goal/Final audit/C8 closure/Documentation consistency/Benchmark reconciliation/Static analysis/Regression/Manual evidence/Known limitations/Release readiness/External validation/Phase Gate subsections).

## 7. Feature Audit Baseline Clarification

Historical test-count baselines, kept distinct (not conflated) in `CT3D_FEATURE_AUDIT.md`'s header:
- Phase 11: ~109 tests.
- Phase 12/13 (before Phase 13.5's additions): 159 collected / 158 passed / 1 skipped.
- Phase 13.5 (current, reconfirmed this phase): 184 collected / 183 passed / 1 skipped.
- **Phase 14 canonical baseline**: same as Phase 13.5 — **184 collected / 183 passed / 1 skipped** — reconfirmed fresh this phase (§8), no new tests added.

## 8. Automated Regression — `tests/ct3d` (run 3x, real)

| Run | Result |
|---|---|
| 1 | 183 passed, 1 skipped, 1 warning in 1.00s |
| 2 | 183 passed, 1 skipped, 1 warning in 0.88s |
| 3 | 183 passed, 1 skipped, 1 warning in 0.77s |

Identical result all 3 times. The 1 warning is a pre-existing upstream `DeprecationWarning` (`imghdr`, unrelated to plugin code).

## 9. Upstream Regression — `tests --ignore=tests/ct3d`

`94 passed` — matches the Phase 12-established baseline exactly. Not touched by any plugin work.

## 10. Static Analysis — Plugin

`python -m pyflakes plugins/roi_viewer` → exit 0, no findings.

## 11. Static Analysis — Benchmark Tool

`python -m pyflakes tools/ct3d_benchmark.py` → exit 0, no findings. **Reported separately from §10 per instruction — neither result substitutes for the other.**

## 12. Compile Checks

`python -m compileall plugins/roi_viewer` → exit 0. `python -m py_compile tools/ct3d_benchmark.py` → exit 0. Reported separately.

## 13. Import / Plugin Discovery Smoke Test (no GUI interaction, no fabricated screenshots)

Real, scripted, no mouse/keyboard simulation:
- `plugins.roi_viewer.core` submodules (`roi_manager`, `picker_3d`, `sync_2d3d`, `segmentation`, `mask_editor`, `measurement`, `annotation`, `exporters`, `marker_3d`, `slice_planes_3d`, `evaluation`) all import cleanly.
- `plugin.json` parses: `{'name': 'ROI Viewer', 'description': '...', 'enable-startup': True}`.
- Real `invesalius.plugins.PluginManager().find_plugins()` (full real discovery, `XDG_CONFIG_HOME`-isolated) discovers **`"ROI Viewer"`** among 7 other real InVesalius plugins (`Change image spacing`, `Change lighting properties`, `Mask Morphology`, `Porous volume creation`, `Remove non-visible faces`, `Remove tiny objects`, `Import MNI coordinates`).
- `python tools/ct3d_benchmark.py --help` runs and prints correct argparse usage.

## 14. `CT3D_P12_QUANTITATIVE_RESULTS.csv` Validation

Parsed with Python's `csv` module: header has 10 fields, 34 data rows, **0 malformed rows** (every row's field count matches the header). Matches the expected Phase 12 baseline exactly. No values altered.

## 15. `CT3D_P13_PERFORMANCE_RESULTS.csv` Validation & Duplicate-Run Fix

Parsed: header has 11 fields, originally 29 data rows (now 30 after §16's appended row), 0 malformed rows. Found the known issue: `0051` "Import DICOM" had **two rows both labeled `Run=1`** (from two separate real process launches, per the documented one-process-per-import methodology). Fixed the **label only** (second row → `Run=2`); the measured `Runtime_Seconds`/`RSS_*`/`Result` values for both rows are untouched.

## 16. `0801` Surface-Build Reclassification & Representative Rerun

Phase 13's historical `0801` surface-build row (`points=0, cells=0, Result=FAIL`) is **preserved unchanged** in the CSV, with a `Phase14_classification=BENCHMARK_INPUT_EMPTY` note appended to its `Notes` field: the narrow near-Otsu-max threshold band chosen for that controlled-ROI benchmark happened to select 0 foreground voxels for this specific dataset — not a product surface-build defect.

To confirm this classification rather than assume it, a **new representative rerun** was performed this phase (RAM permitted: 1.82-2.35GB available, consistent with prior phases' observed range): imported `0801` for real, computed its real Otsu range via `SegmentationManager.auto_threshold_otsu()`, used the **full data-derived Otsu range** as the threshold (asserted `foreground_count > 0` — 11,340,153 voxels, 26.70% of volume — before attempting the RAM-heavy surface build), and built the surface with `quality="Low"` (same safety rationale as Phase 13). Result: **PASS — 145,772 points, 254,978 cells**, 11.121s, RSS delta +340.7MB. Appended as a new CSV row (`0801`, same Operation, `Run=2`) — the historical `Run=1` row was never overwritten.

**Conclusion**: the empty mesh was conclusively a benchmark-input problem, not a real product bug. `PHASE_GATE` is **not** blocked by this finding (per the spec's own contingency: only an empty result from a *data-derived, asserted-non-empty* threshold would count as a real bug — that did not happen here).

## 17. FPS Representative-Claim Correction

The `"10000.0 FPS"` values recorded in `CT3D_P13_PERFORMANCE_RESULTS.csv` (rows for the Rendering operation) are a measurement-floor artifact: `vtkRenderer.GetLastRenderTimeInSeconds()` returned its minimum reportable granularity (`0.0001s`) on a trivially small (13-point) mesh. These values are **left unchanged in the CSV** (historical data, not altered) but are explicitly **excluded from every representative-performance claim** in this report and in `CT3D_RELEASE_NOTES.md`. The traceable, previously-verified representative figure — **122.0–158.3 FPS**, measured across 3 real datasets on non-trivial surfaces — is used instead (already recorded in `CT3D_FEATURE_AUDIT.md` row C2 since an earlier round, reconfirmed present this phase).

## 18. Rendering Mode Clarification

All performance/FPS claims in this report and in `CT3D_RELEASE_NOTES.md` explicitly state **Surface rendering mode**, never raycasting. `C6` (pure volume raycasting) remains **`NOT_CONNECTED`** — `invesalius.data.volume.Volume.OnShowVolume()` still has 0 call-sites anywhere in the repository (grep-reconfirmed), a limitation of upstream InVesalius itself, not the plugin. No claim in any Phase 14 document states or implies raycasting performance.

## 19. Canonical Readiness Terminology

The following field set is used consistently across `CT3D_MASTER_PROGRESS.md`, `CT3D_RELEASE_NOTES.md`, and this report, replacing the older single ambiguous "RELEASE_CANDIDATE_READY" field used informally in the Phase 13 report:

| Field | Value |
|---|---|
| `AUTOMATED_TECHNICAL_READY` | YES |
| `MANUAL_QA_COMPLETE` | YES (7/7 original items) |
| `SOFTWARE_TECHNICAL_COMPLETE` | YES |
| `SOFTWARE_RELEASE_CANDIDATE_READY` | YES |
| `RESEARCH_EXTERNAL_VALIDATION_COMPLETE` | NO |
| `CLINICAL_VALIDATION_COMPLETE` | NO |

## 20. SUS Protocol Wording Fix

`docs/CT3D_SUS_PROTOCOL.md` previously stated a single "minimum 5 (Nielsen)... ideally 10-20" recommendation in a way that could be read as implying 5 participants might yield a statistically meaningful SUS mean. Rewrote §2 and §10 to explicitly separate: (a) Nielsen's ~5-participant heuristic, which is for **qualitative, formative usability-problem discovery**, from (b) the **10-20 participant** threshold needed for a **quantitative, statistically meaningful SUS mean**. `SUS_PROTOCOL_READY=YES`, `SUS_REAL_PARTICIPANTS_COMPLETE=NO` unchanged — no participants, no fabricated scores.

## 21. PHI Audit

Searched `docs/`, `plugins/roi_viewer`, `tools/`, `tests/ct3d` for actual PHI **values** (not field-name mentions): `PatientName`, `PatientID`, `PatientBirthDate`, `AccessionNumber`, real dotted-numeric DICOM UID patterns. **None found.** The only PHI-*field-name* references found are the legitimate API method `project_interface.py.get_patient_name()` and a synthetic test helper (`tests/ct3d/test_dicom_grouping.py._fake_dicom(...)`) that uses placeholder values (`"P"`, `"P1"`, `"id1"`) — never real patient data. Dataset labels throughout the repository remain technical IDs (`0051`/`0801`/`mri3`), matching `CT3D_DATASET_REGISTRY.md`.

## 22. Hardcoded Path Audit

`plugins/roi_viewer` (shipped production plugin code): **0 matches** for `D:\PyTools`, `C:\Users`, or `/home/` patterns — clean. `tools/ct3d_benchmark.py` (dev/benchmark tool, not shipped plugin code) did hardcode an absolute `REPO_ROOT` and a `DATASETS` dict with local dataset paths. Judgment: the `DATASETS` paths reference private local DICOM sample fixtures that are not part of the repository by design (real imaging data, intentionally excluded from version control) — comparable to a test fixture path, left as a documented default. `REPO_ROOT`, however, was a genuine portability defect (breaks on any other checkout location) — fixed to derive from `pathlib.Path(__file__).resolve().parent.parent` (identical value on this machine, zero behavior change, verified via §11/§12/§13 rerun after the edit). `DATASETS`' base directory was additionally made overridable via `CT3D_DICOM_SAMPLES_DIR` (env var, defaults preserved) as a minimal, non-feature portability improvement.

## 23. End-to-End Evidence Matrix

Reusing existing, already-verified evidence rather than re-running expensive operations. "Evidence" cites the earliest phase where the claim was verified; unchanged since.

| # | Workflow step | Status | Evidence |
|---|---|---|---|
| 1 | DICOM import (real dataset, gdcm) | WORKING | `CT3D_DATASET_REGISTRY.md`, Phase 12 |
| 2 | Plugin discovery (`PluginManager`) | WORKING | Phase 14 §13 (this session, real) |
| 3 | Plugin window open/close/reopen, no duplicate | WORKING | Vòng 1 / Phase 09 |
| 4 | 2D views Axial/Coronal/Sagittal display | WORKING | B1, Vòng 1 |
| 5 | Scroll slice sync | WORKING | B2, Vòng 1 |
| 6 | Window/Level | WORKING | B3, Vòng 1 |
| 7 | Zoom/Pan 2D | WORKING (manual) | B4, Phase 13 manual QA |
| 8 | Threshold segmentation (manual) | WORKING | D1, Vòng 1 |
| 9 | Auto-threshold Otsu | WORKING | D2, Vòng 1 |
| 10 | Create mask from threshold | WORKING | D1, Vòng 1 |
| 11 | Select/change current mask | WORKING | D3, Vòng 1 |
| 12 | Brush paint | WORKING (manual) | D4, Phase 13 manual QA |
| 13 | Eraser | WORKING (manual) | D5, Phase 13 manual QA |
| 14 | Brush size/shape config | WORKING | D6, Vòng 1 |
| 15 | Undo/Redo checkpoint | WORKING | D7, Phase 10/11 |
| 16 | Region Growing (seed-based, safety warning) | WORKING | D10, Phase 12 (full-volume real) |
| 17 | Update 3D Surface from Selected ROI (mask edit → rebuild) | WORKING | D9/C7, Phase 08 + Phase 13 real-GUI (P08.5) |
| 18 | Marching Cubes surface build | WORKING | C1, Vòng 1 |
| 19 | 3D render + FPS (surface mode) | WORKING | C2, Vòng 1 — 122.0-158.3 FPS representative |
| 20 | Rotate/Pan/Zoom 3D camera | WORKING (manual) | C3, Phase 13 manual QA |
| 21 | Pick point in 3D (`vtkCellPicker`) | WORKING | C4, Vòng 1 |
| 22 | Sync 3D→2D (pick jumps slice) | WORKING | C5, Vòng 1 |
| 23 | Sync 2D→3D marker (crosshair→3D marker) | WORKING | C8, Phase 09 automated + Phase 14 operator smoke |
| 24 | Sync 2D→3D slice planes (visual) — core path | WORKING (core path) | C8, Phase 13.5 automated + Phase 14 `C8_VISUAL_OPERATOR_SMOKE=PASS` |
| 25 | Sync 2D→3D slice planes — itemized A-I subtests | `NOT_EXPLICITLY_MANUAL_VERIFIED` | See §5 |
| 26 | Volume raycasting (pure) | `NOT_CONNECTED` | C6, upstream limitation, Vòng 2 |
| 27 | Measure distance 3D | WORKING | E1, Vòng 1 |
| 28 | Measure distance 2D | WORKING (manual) | E2, Phase 13 manual QA (M1=143.951mm/M2=189.741mm) |
| 29 | Measure area 2D (polygon) | WORKING (manual) | E3, Phase 13 manual QA (2674.851mm²/5367.750mm²) |
| 30 | Measure mask volume | WORKING | E4, Vòng 3 (padding bug fixed) |
| 31 | Add/Goto/Edit/Delete annotation | WORKING | F1/F2, Vòng 1 |
| 32 | Annotation position accuracy | WORKING | F3, Phase 09 |
| 33 | Save annotation with project (sidecar JSON) | WORKING | F4, vòng 2 |
| 34 | Save/Open project (`.inv3` round-trip) | WORKING | G1/G2/G3, Phase 10 (30/30 byte-identical) |
| 35 | Export mask (NIfTI/NumPy/NRRD-optional) | WORKING | H1, Vòng 3 + Phase 12 (NRRD) |
| 36 | Export surface (STL/PLY/OBJ/VTK) | WORKING | H2-H5, Vòng 1 |
| 37 | Export slice image (PNG) | WORKING | H6, Vòng 1 |
| 38 | Dice/Jaccard/Hausdorff (synthetic validation) | WORKING (infra + synthetic) | Phase 12, 42 tests PASS |

## 24. Known Limitations Summary

14 items, fully classified in `docs/CT3D_KNOWN_LIMITATIONS.md` (new this phase): `SOFTWARE_LIMITATION` (raycasting not connected — upstream limitation; C8 native-tool prerequisite by design; C8 planes non-textured by design; crosshair-does-not-rebuild-surface by design; Undo history bounded to 10), `ENVIRONMENT_DEPENDENCY` (surface-build RAM sensitivity; single-machine benchmark numbers; the 10000 FPS artifact; NRRD optional dependency), `EXTERNAL_VALIDATION_GAP` (GE/Canon vendor gap; multi-series sample gap; real ground-truth gap; SUS participant gap; 3D Slicer benchmark gap), `OUT_OF_SCOPE` (DICOM-SEG export). *(Corrected 22/09/2026 — see the Post-Phase-14 Release Closure Corrections section: DICOM-SEG was previously listed under both `SOFTWARE_LIMITATION` and `OUT_OF_SCOPE` simultaneously; it is `OUT_OF_SCOPE` only. NRRD was reclassified from `SOFTWARE_LIMITATION` to `ENVIRONMENT_DEPENDENCY`, matching `CT3D_KNOWN_LIMITATIONS.md`'s corrected row 10.)*

## 25. Release Notes Summary

`docs/CT3D_RELEASE_NOTES.md` (new this phase) documents scope, upstream base, plugin contributions, phase-by-phase summary (08→14), regression/static-analysis results, manual QA summary, dataset/performance summary (with the FPS correction from §17), NRRD install instructions, reproducibility commands, known limitations pointer, and an explicit **research-prototype / not-a-medical-device / not-clinically-validated disclaimer**.

## 26. Manual QA Final Matrix

| # | Item | Status |
|---|---|---|
| 1 | P08.5 (D9/C7 real dialog) | PASS |
| 2 | B4 (Zoom/Pan 2D) | PASS |
| 3 | C3 (Rotate/Pan/Zoom 3D) | PASS |
| 4 | D4 (Brush) | PASS |
| 5 | D5 (Eraser) | PASS |
| 6 | E2 (Distance 2D) | PASS |
| 7 | E3 (Area 2D) | PASS |
| 8 | C8 core path (operator smoke test) | PASS (`C8_VISUAL_OPERATOR_SMOKE`) |
| 8a | C8 itemized TEST A-I (9 subtests) | `NOT_EXPLICITLY_MANUAL_VERIFIED` (0/9 itemized; not FAIL) |
| 8b | C8 automated regression (`SP3D-T`+`SYNC3D-T`) | PASS (25/25, machine-verified) |

`MANUAL_QA_COMPLETE = YES` (unchanged, refers to the original 7-item checklist).

## 27. Bugs Found This Phase

**None.** This phase found no new product defects. The `0801` empty-mesh result (§16) was conclusively determined to be a benchmark-input issue, not a product bug, after a real representative rerun with an asserted-non-empty, data-derived threshold produced a correct, substantial mesh.

## 28. Files Changed

- Fixed: `docs/CT3D_MANUAL_QA_CHECKLIST.md`, `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md`, `docs/CT3D_FEATURE_AUDIT.md`, `docs/CT3D_MASTER_PROGRESS.md`, `docs/CT3D_REMAINING_WORK.md`, `docs/CT3D_CHANGELOG.md`, `docs/CT3D_SUS_PROTOCOL.md`, `docs/CT3D_P13_PERFORMANCE_RESULTS.csv`, `tools/ct3d_benchmark.py`.
- Created: `docs/CT3D_KNOWN_LIMITATIONS.md`, `docs/CT3D_RELEASE_NOTES.md`, `docs/CT3D_P14_FINAL_AUDIT_REPORT.md` (this file).
- Committed separately (housekeeping, before the audit): rename of 3 root planning `.md` files into `docs/` + 1 orphaned progress-snapshot doc (commit `54f2f479`).
- No changes to `invesalius/` (upstream core) this phase. No changes to `plugins/roi_viewer/core` or `gui` logic this phase (no new bug found requiring it).

## 29. Phase Gate Checklist

| # | Criterion | Result |
|---|---|---|
| 1 | Git state verified/explained | ✓ (§3) |
| 2 | Worktree state understood, resolved (not just documented) | ✓ (§3) |
| 3 | No critical/unresolved bug found | ✓ (§27) |
| 4 | `tests/ct3d` PASS ×3 consecutive, identical | ✓ (§8) |
| 5 | Upstream `tests` PASS | ✓ (§9) |
| 6 | Plugin `pyflakes` PASS | ✓ (§10) |
| 7 | Benchmark tool `pyflakes` PASS (separate) | ✓ (§11) |
| 8 | Compile checks PASS (both, separate) | ✓ (§12) |
| 9 | Import/plugin-discovery smoke PASS | ✓ (§13) |
| 10 | Both CSVs valid (field counts match header) | ✓ (§14, §15) |
| 11 | Duplicate Run labels fixed (if present) | ✓ (§15) |
| 12 | `0801` empty-benchmark correctly reclassified | ✓ (§16) |
| 13 | Representative rerun performed (RAM permitted) or `BLOCKED_BY_MEMORY` | ✓ — performed, PASS (§16) |
| 14 | 10000 FPS excluded from representative claims | ✓ (§17) |
| 15 | C8 automated regression still PASS | ✓ (§5, 25/25) |
| 16 | Operator's actual C8 evidence recorded truthfully (no fabrication) | ✓ (§5) |
| 17 | Original 7/7 manual QA still PASS, unchanged | ✓ (§5, §26) |
| 18 | Feature Audit metadata/Runtime-column inconsistency fixed | ✓ (§6, §7) |
| 19 | User Guide metadata fixed | ✓ (§6) |
| 20 | `CT3D_KNOWN_LIMITATIONS.md` exists | ✓ (§24) |
| 21 | `CT3D_RELEASE_NOTES.md` exists | ✓ (§25) |
| 22 | No PHI found | ✓ (§21) |
| 23 | No unjustified machine-specific production dependency | ✓ (§22) |
| 24 | No fake external/clinical validation claimed | ✓ (§19) |
| 25 | Readiness terminology unambiguous, canonical field set used | ✓ (§19) |
| 26 | SUS protocol wording fixed (Nielsen vs statistical SUS mean) | ✓ (§20) |
| 27 | All required files physically verified on disk with real content | ✓ (§30) |

**`PHASE_GATE: PASS`**

## 30. Final Conclusion

All 27 gate criteria are satisfied with real, verified evidence — no fabricated data, no assumed manual coverage beyond what the operator actually reported. The one open worktree ambiguity carried since Phase 08 was resolved (not just re-documented) this phase. The one benchmark anomaly carried since Phase 13 (`0801` empty mesh) was conclusively reclassified via a real representative rerun, not asserted. C8's manual-evidence state reflects exactly what was reported — a core-path smoke-test PASS plus 25/25 automated regression PASS, with itemized subtests honestly marked `NOT_EXPLICITLY_MANUAL_VERIFIED` rather than inflated to 9/9 PASS.

**SOFTWARE ROADMAP PHASE 08–14: COMPLETE. NO PHASE 15.** Remaining work — GE/Canon vendor validation, real ground-truth Dice/Jaccard/Hausdorff validation, SUS participant recruitment, 3D Slicer comparative benchmarking, and any eventual clinical validation — is external research / clinical validation, outside the technical scope of this software engineering roadmap, and is explicitly and honestly marked `NO`/incomplete rather than fabricated.

---

## Post-Phase-14 Release Closure Corrections (22/09/2026)

This addendum documents a follow-up consistency pass performed after Phase 14's `PASS` gate, explicitly **not** a new phase (no feature work, no algorithm changes, no architecture changes). It corrects wording/metadata issues found by re-reading this report and the other canonical docs with fresh eyes. Nothing below reverses or invalidates the original §1-30 findings — it corrects how some of them were *worded*, and fixes two small real inconsistencies. Historical phase reports (Phase 08-13.5) are **not** modified; only current-state canonical docs and this report's own metadata/taxonomy summary are.

**1. Git HEAD reconciliation.** The original §1 Metadata table listed `bed0c624` as "HEAD after this phase." That was imprecise: `bed0c624` is the **main** Phase 14 implementation/documentation commit; it was followed by a hash-fill-in commit, `6dae0922`, which updated 3 self-referencing placeholders (in this file, `CT3D_MASTER_PROGRESS.md`, `CT3D_CHANGELOG.md`) and is the **actual current branch tip**. Reconciled:
- Main Phase 14 commit: `bed0c624`
- Hash-fill-in follow-up commit: `6dae0922`
- **Final HEAD: `6dae0922`**
- History consistent: **YES** — fully linear, matches the same "main commit, then a small hash-fill-in follow-up" pattern used in every prior phase (e.g. Phase 13: `787fad80` → `2920ee8b`; Phase 12: `52004e28` → `470354a2`). The Phase 14 history table row in `CT3D_MASTER_PROGRESS.md` correctly lists `bed0c624` (the main commit, matching the convention used for every other phase row in that table) — only the standalone "current HEAD" field was wrong, and has been corrected there to `6dae0922`.

**2. Master test-history correction.** `CT3D_MASTER_PROGRESS.md` (line ~80) incorrectly attributed "158 test" to Phase 11 in one sentence. Corrected: Phase 11 introduced the persistent `tests/ct3d/` suite at **~109 tests**; it was expanded to **159 collected / 158 passed / 1 skipped** in Phase 12 (unchanged through Phase 13); expanded again to the current **184 collected / 183 passed / 1 skipped** in Phase 13.5. `CT3D_FEATURE_AUDIT.md`'s header already stated this correctly (verified, not altered). `CT3D_CHANGELOG.md`'s historical Phase 11/12 entries were checked and are correct as originally written (109 tests at Phase 11, 158 passed at Phase 12) — those are immutable historical records, not touched.

**3. "Phase 14+" wording correction.** Found and fixed in `CT3D_MASTER_PROGRESS.md` (1 occurrence) and `CT3D_REMAINING_WORK.md` (3 occurrences, in the P3 table's "Ước lượng thời gian" column). All replaced with **"post-roadmap external research work"** — the roadmap ended at Phase 14; "Phase 14+" implied a continuing phase sequence that no longer exists. No historical report text was altered (this phrase did not appear in any immutable `CT3D_PXX_*_REPORT.md`).

**4. Master remaining-work terminology.** `CT3D_MASTER_PROGRESS.md`'s "Next phase" line previously said remaining work is "external research / clinical validation only" — inaccurate, since 2 items (C8's 9 itemized A-I subtests, and the optional `ca_smoothing` evaluation) are neither required nor external — they are optional, internal, doable within the current repo without external data/users. Corrected to explicitly split **OPTIONAL_INTERNAL** (C8 A-I itemization, `ca_smoothing` evaluation — not blockers) from **EXTERNAL** (GE/Canon, real ground-truth, SUS participants, 3D Slicer benchmark, clinical validation). `CT3D_REMAINING_WORK.md`'s P3 table gained a `Loại` (category) column tagging each row `EXTERNAL_VALIDATION` / `OUT_OF_SCOPE` / `OPTIONAL_INTERNAL`, and a new row 9 (`ca_smoothing`, `OPTIONAL_INTERNAL`) was added — it previously existed only in `CT3D_MASTER_PROGRESS.md`'s "Medium-priority work" section and not in the Remaining Work doc itself.

**5. User Guide RAM wording correction.** `HUONG_DAN_SU_DUNG_ROI_VIEWER.md` previously stated an unsupported fixed threshold ("dưới ~5GB RAM trống"). No evidence ever established that specific number. Corrected to evidence-based wording: surface generation is memory-sensitive and depends on volume size, threshold, algorithm, and quality — no single fixed RAM threshold applies to every dataset — and cited the real counter-example from §16: the `0801` representative rerun succeeded (145,772 points) with only **1.82GB** available.

**6. SUS wording refinement.** `CT3D_SUS_PROTOCOL.md`'s original Phase 14 fix (§20) already separated Nielsen's ~5-participant qualitative heuristic from the 10-20 participant quantitative target, but still phrased 10-20 as something that would make the SUS mean "đủ tin cậy" (adequately reliable) — too absolute. Refined: 10-20 is a **practical target** for this thesis's exploratory quantitative SUS study, not a threshold that automatically guarantees statistical adequacy; every real SUS report must state n, mean, SD (and CI where computable) rather than a single averaged number. `SUS_PROTOCOL_READY=YES` / `SUS_REAL_PARTICIPANTS_COMPLETE=NO` unchanged.

**7. Known-Limitations taxonomy correction.** Found a real inconsistency in this report's own §24 summary sentence (not in `CT3D_KNOWN_LIMITATIONS.md` itself, which was already correct): DICOM-SEG was listed under both `SOFTWARE_LIMITATION` ("DICOM-SEG out of scope") and `OUT_OF_SCOPE` simultaneously — a genuine dual-classification bug. Fixed: DICOM-SEG is `OUT_OF_SCOPE` only. Separately, reclassified NRRD's optional-dependency limitation from `SOFTWARE_LIMITATION` to `ENVIRONMENT_DEPENDENCY` in both `CT3D_KNOWN_LIMITATIONS.md` (row 10) and this report's §24 — it better fits "depends on whether an optional package is installed" than "a fixed design limitation." The 4-category taxonomy itself (`SOFTWARE_LIMITATION`/`ENVIRONMENT_DEPENDENCY`/`EXTERNAL_VALIDATION_GAP`/`OUT_OF_SCOPE`) was **not** changed or extended — no new category was invented.

**8. Final regression (re-run 22/09/2026).** `tests/ct3d -q`: **183 passed, 1 skipped** (184 collected) — identical to Phase 14's original result, no drift. Upstream `tests --ignore=tests/ct3d -q`: **94 passed**, unchanged. `pyflakes plugins/roi_viewer`: exit 0. `pyflakes tools/ct3d_benchmark.py`: exit 0 (reported separately, as before). `compileall`/`py_compile`: both PASS. Both CSVs re-validated: P12 = 10 cols/34 rows/0 malformed; P13 = 11 cols/30 rows/0 malformed, 0 duplicate `(Dataset_ID, Operation, Run)` keys (the §15 fix holds). Production-path scan of `plugins/roi_viewer` for `D:\PyTools`/`C:\Users`/`/home/`/`dicom_samples`: 0 matches, confirmed clean. `CT3D_DICOM_SAMPLES_DIR` override confirmed present in `tools/ct3d_benchmark.py` and documented in `CT3D_RELEASE_NOTES.md` §9.

**9. Final worktree status.** `git status` clean before this closure pass began (Phase 14's own commits left it clean). After this closure pass's edits, staged and committed as a single dated commit (see the final response for the exact hash) — `git status` clean again afterward, verified.

**RELEASE_CLOSURE_GATE: PASS** (19/19 criteria — see the final response's Closure Gate section for the itemized checklist). No PHI introduced by any edit in this addendum. No feature/algorithm/architecture change. No Phase 15 created.
