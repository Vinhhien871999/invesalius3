# CT3D ROI Viewer: Interactive AI (MedSAM2) progress

- **Branch:** `feature/interactive-ai-medsam2`, from `enhancement/advanced-segmentation` @ `70720ca8`.
- **Isolation:** not merged anywhere. `thesis-ct-roi-tools` and `ct3d-rc1` remain at `aa1b3ad3`.

| Item | Status | Evidence |
|---|---|---|
| Git preflight (clean worktree, new branch) | PASS | `docs/evidence/interactive_ai_20261105/00_git_preflight.txt` |
| Baseline (ct3d 742/2, upstream 94, pyflakes / compileall / diff-check clean) | PASS | `01_baseline.txt` |
| Official model audit (MedSAM2 / SAM2 / MedSAM) | AUDITED | `02_model_audit.txt`; architecture § Provider capabilities |
| Model decision | **MEDSAM2** (box + positive points; negative off by default) | architecture |
| External runtime protocol + worker + client | WORKING | `04_protocol_tests.txt` |
| invx-venv unchanged (no MedSAM2/sam2 installed) | PASS | `pip freeze` SHA-256 identical before and after |
| MedSAM2 worker provider (official preprocessing) | IN_PROGRESS: written; numpy parts tested; model path untested | `05_coordinate_tests.txt` |
| Host provider + UI (not configured / check / prompts / markers / refine) | WORKING | `06_preview_tests.txt` |
| Accept == candidate (SHA-256), one mask, no inference | PASS (automated, fake worker) | `07_accept_tests.txt` |
| Lifecycle / cancellation / crash / timeout | PASS (automated) | `08_lifecycle_tests.txt` |
| TotalSegmentator regression | PASS (automated) | `09_totalsegmentator_regression.txt` |
| Real MedSAM2 smoke | **BLOCKED**: no separate environment, no checkpoint; WSL cannot start here | `10_real_model_smoke.txt` |
| Performance (infrastructure only) | PARTIAL | `11_performance.txt` |
| Final regression ×3, upstream, pyflakes, compileall, diff-check | PASS: ct3d 823/2 ×3, upstream 94, all exit 0 | `12`–`18` |
| Manual QA IA-A…IA-W | NOT_RUN (0/23) | `CT3D_INTERACTIVE_AI_MANUAL_QA.md` |
| User guide section | PLANNED: written only after the real provider works (spec §56) | – |

## Gates

- **INTERACTIVE_AI_INFRA_GATE: PASS.** All §58 conditions are met by automated evidence: separate branch, clean baseline, isolation, no MedSAM in invx-venv, protocol, coordinates, E2/E4 reuse, exact Accept, lifecycle, TotalSegmentator, AI-off workflow. This is not a manual GUI PASS: IA-A…IA-W are NOT_RUN.
- **MEDSAM2_REAL_GATE: BLOCKED.**
- **INTERACTIVE_AI_RELEASE_READY: NO.**
