# CT3D ROI Viewer: Direct interaction progress

- **Branch:** `feature/interactive-ai-direct-click`, from `feature/interactive-ai-medsam2` @ `02c15f9e`.
- **Isolation:** not merged. `enhancement/advanced-segmentation` @ `70720ca8`, `feature/interactive-ai-medsam2` @ `02c15f9e`, and `thesis-ct-roi-tools` / `ct3d-rc1` @ `aa1b3ad3` are unchanged.

| Item | Status | Evidence |
|---|---|---|
| Git preflight, new branch | PASS | `00_git_preflight.txt` |
| Baseline (ct3d 824/2, upstream 94, lint clean) | PASS | `01_baseline.txt` |
| Source audit: fast 2D / state reuse APIs | AUDITED | `02_source_audit.txt` |
| Direct 2D click capture with input ownership | WORKING (headless + real VTK interactors); GUI NOT_RUN | `05_direct_ai_tests.txt` |
| Automatic two-stage preview (quick slice → 3D), latest wins | WORKING | `05` |
| Smart one-click policy | WORKING. **Shipped `point_first`**, chosen by measurement over the spec's fast-2D bbox | `03`, `04` |
| Fast 2D mask (current-frame API) | PASS (real model: 0.75–3.5 s) | `04` |
| Model state + feature reuse | PASS: state reused; the feature cache gives identical candidates and is ~30–40 % faster, but is **OFF by default** after the out-of-memory report (+3.9 GB VRAM charged to commit on Windows) | `04`, `07` |
| Operator out-of-memory report (real app) | FIXED: cache off by default, low-memory paths, no scheduler wedge, new RAM message. Real re-check: worker 4.6–4.9 GB (was 8.6 GB) | `07` |
| Drag box | WORKING (geometry identical to the corner buttons); GUI NOT_RUN | `05` |
| Semantic suggestion (existing TotalSegmentator cache only) | WORKING | `05`, architecture |
| Refinement quality with MedSAM2 | **PARTIAL**: updates work, extra clicks on other slices were unreliable (spleen 0.95 → 0.03) | `04` |
| TotalSegmentator / AI-off unchanged | PASS (automated) | `06`, `11`–`13` |
| Final regression ×3, upstream, pyflakes, compileall, diff-check | runs 1–2: 870/2. Run 3: 869/2 + **1 error** during a ~60× slow period (2 h 24 min); test name not captured; cause not established. Then 1 diagnostic + **3 extra consecutive clean runs, 870/2 each (`-rEf`, ~2 min 50 s)**. Upstream 94; pyflakes / compileall / diff-check exit 0; invx-venv pip-freeze hash unchanged | `11`–`17`, `13b` |
| Manual QA DI-A…DI-S | NOT_RUN (0/19) | `CT3D_DIRECT_INTERACTION_MANUAL_QA.md` |
| User guide | PLANNED: only after real GUI operator validation (spec §39) | – |

## Gates

- **DIRECT_INTERACTION_INFRA_GATE: PASS**, on automated evidence plus real-model measurements outside the GUI.
- **DIRECT_INTERACTION_GUI_GATE: PARTIAL_MANUAL_QA_PENDING.**
- **DIRECT_INTERACTION_RELEASE_READY: NO.**
