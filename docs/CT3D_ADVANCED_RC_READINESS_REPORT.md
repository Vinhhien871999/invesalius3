# CT3D Advanced Segmentation — Release-Candidate Readiness

**Branch**: `enhancement/advanced-segmentation` · **Date**: 30/09/2026 · Not merged into the stable branch. Stable `thesis-ct-roi-tools` / tag `ct3d-rc1` (`aa1b3ad3`) unchanged.

## 1. Verdict

**`ADVANCED_RC_READY = NO`.**

Release blockers:
1. **E6b real inference has not been run** (`E6b_GATE = PARTIAL_REAL_INFERENCE_PENDING`): TotalSegmentator is not installed in the InVesalius environment. Installing it needs the constrained command in §6 — a plain install would break the environment.
2. **Sidebar only partly verified in a real InVesalius**: an operator screenshot (30/09/2026, project 0801) shows the pane docked on the right with the viewers usable (UI-K `PARTIAL`); UI-L..UI-N `NOT_RUN`. The same screenshot exposed an AI status defect (provider loaded twice under InVesalius's plugin loader), fixed and covered by a test that uses the application's loader.

Everything else automated is green. The remaining manual items below are coverage, not blockers, except where marked.

## 2. Implemented (E1–E6b)

| Stage | Content | Technical gate |
|---|---|---|
| E1 | ROI management (current ROI, colour, lock, show only, show/hide all) | PASS |
| E2 | Preview → Accept/Cancel (Otsu, Region Growing, AI) | PASS |
| E3 | Post-processing (largest component, small islands, fill holes, smooth) | PASS (smooth: WARNING, §5) |
| E4 | Live 3D preview mesh | PASS |
| E5 | Textured slice planes, clipping | PASS (rendered orientation proof) |
| E6 | AI architecture (providers, prompts, jobs, validation, E2/E4 reuse, exact Accept) | PASS |
| E6b | TotalSegmentator provider | **PARTIAL_REAL_INFERENCE_PENDING** |
| — | Coordinate contract fix, native mask contract fix, Vietnamese UI, sidebar docking | fixed / tested |

## 3. Automated evidence (this run)

- `tests/ct3d`: 616 passed / 1 skipped (optional `pynrrd`) / 0 failed, 3 consecutive runs; upstream `tests`: 94 passed; `pyflakes` / `compileall plugins/roi_viewer` / `git diff --check` clean.
- All test and helper processes use a temporary `XDG_CONFIG_HOME`; verified that a full run leaves `%USERPROFILE%\.config\invesalius\config.json` / `state.json` untouched.

## 4. Manual QA status

`docs/CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md`. Item-level operator evidence exists only for **E5-A (PASS)**. Group-level operator statements (E4, E5 texture/clipping "basically work") are recorded as notes, not as item PASS.

| Group | Status | Blocking? |
|---|---|---|
| E6b-A..P (real TotalSegmentator) | NOT_RUN — real inference BLOCKED (not installed) | **yes** (E6b-D/F/G/I/J/M at minimum) |
| UI-K..UI-N (sidebar in real InVesalius) | UI-K PARTIAL (screenshot: docked right); UI-L..N NOT_RUN | **yes** (UI-K reuse, UI-M) |
| E5-B/C/D/E/J/K/L | RETEST_REQUIRED (after the coordinate fix) | no — orientation is proven by a rendered automated test; operator confirmation recommended |
| E1-A..N, E2-A..L, E3-A..M, E4-A..R, E5 others, E6-A..L, UI-A..J | NOT_RUN | no (coverage) |

## 5. Known limitations (kept as documented)

- TotalSegmentator only for single-frame axial DICOM series with a stored ImageOrientationPatient; other volumes are refused.
- After InVesalius's own flip/swap-axis tools the stored orientation no longer describes the matrix (AI orientation may then be wrong; not detectable).
- Enhanced multi-frame DICOM: z direction unverified.
- One AI structure per preview. TotalSegmentator inference cannot be interrupted (cancel discards the late result; the computation continues). CPU inference can be slow. Standard mode needs weights 291–295 + 298; fast mode 297 + 298.
- **E3 "Làm mịn mặt nạ" (smooth)** — measured on real 0051 (head CT, 0.4785 × 0.4785 × 1.5 mm, 1 pass): bone threshold ROI 1,730,409 → 1,704,840 (−1.5 %, thin skull-base parts removed); soft-tissue ROI 7,130,381 → 7,026,144 (−1.5 %); **the same soft tissue on only 2 axial slices (brush-like): 174,504 → 0 (−100 %)**. Mechanism: the voxel-based 6-connected opening removes anything thinner than 3 voxels along any axis (4.5 mm in z here). This matches the operator's earlier report (170,405 → 10,127, −94 %). Undo restores it. **Investigation item open** (e.g. warn before a large loss, or an in-plane/anisotropy-aware option); algorithm not changed without a decision.
- The preview overlay needs a current mask (native InVesalius constraint).
- Lock/"show only" state is session-only by design.
- The sidebar cannot appear automatically when InVesalius starts without a change to InVesalius itself (plugins are imported on menu click).
- Not clinically validated.

## 6. AI requirements and installation (operator; the plugin never installs or downloads)

Environment: the Python that runs InVesalius — here `D:\PyTools\invx-venv\Scripts\python.exe` (3.11.7), torch 2.7.1+cu118, RTX 4060 Laptop GPU (CUDA available).

```bat
REM 0. (recommended) record the current environment for rollback
D:\PyTools\invx-venv\Scripts\python.exe -m pip freeze > "%USERPROFILE%\invx-venv-before-totalseg.txt"

REM 1. install without changing InVesalius's packages (checked with pip --dry-run)
cd /d D:\Learns\DeAn\invesalius\invesalius3
D:\PyTools\invx-venv\Scripts\python.exe -m pip install -c tools\ct3d_ai_constraints.txt --extra-index-url https://download.pytorch.org/whl/cu118 TotalSegmentator==2.18.0

REM 2. check nothing critical moved (expect 2.7.1+cu118 True 1.26.4)
D:\PyTools\invx-venv\Scripts\python.exe -c "import torch, numpy; print(torch.__version__, torch.cuda.is_available(), numpy.__version__)"

REM 3. download the "total" weights once, outside ROI Viewer (tasks 291-295 + 298)
D:\PyTools\invx-venv\Scripts\totalseg_download_weights.exe -t total
REM    optional, for "Nhanh / ít bộ nhớ hơn": tasks 297 + 298
D:\PyTools\invx-venv\Scripts\totalseg_download_weights.exe -t total_fast
```

Weights go to TotalSegmentator's own directory (`$TOTALSEG_WEIGHTS_PATH`, else `$TOTALSEG_HOME_DIR\nnunet\results`, else `%USERPROFILE%\.totalsegmentator\nnunet\results`). Optional privacy setting for TotalSegmentator runs outside the plugin: `"send_usage_stats": false` in `%USERPROFILE%\.totalsegmentator\config.json` (inside the plugin the upload is always disabled). Then restart InVesalius → Plugins → ROI Viewer → Phân đoạn → Phân đoạn AI.

## 7. Security / privacy behaviour

Inference runs locally. During a plugin run TotalSegmentator's weight download is replaced by a presence check and its usage-statistics upload by a no-op (both restored afterwards). CT data is passed in memory (no NIfTI written by the plugin). Nothing is installed or downloaded by the plugin.

## 8. Startup / sidebar

Plugins → ROI Viewer docks the "ROI Viewer" pane on the right of the InVesalius window (floatable; close button cleans up; menu again reuses the pane).

## 9. Next steps to reach YES

1. Operator runs §6.
2. One real inference on 0051 with **structure `brain`** (CUDA, standard), with the E6b-D/F/G/I/J/K/L/M checks and the timings the provider records. 0051 is a **head CT** (skull, 108 axial slices) - `spleen`/`liver` (the usual first choices) are not in the field of view and would give an empty result. `brain` (id 90) and `skull` (id 91) are in TotalSegmentator 2.18.0's 117-class `total` map.
3. UI-K..UI-N in the real InVesalius.
4. Re-run the regression; update this report.
