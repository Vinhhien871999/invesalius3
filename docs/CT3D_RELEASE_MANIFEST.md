# CT3D Release Manifest

> Bản đồ tổng thể, ngắn gọn, thao tác được (operational) cho release candidate của đề tài CT3D. Không lặp lại chi tiết đầy đủ — mỗi mục trỏ tới tài liệu nguồn tương ứng. Mọi commit hash bên dưới đã xác minh thật qua `git log -1 <hash>` trước khi ghi vào đây, không đoán.

## Release identity

| Field | Value |
|---|---|
| Project | InVesalius CT3D + Plugin ROI Viewer |
| Branch | `thesis-ct-roi-tools` |
| Software roadmap | Phase 08-14 **COMPLETE** — no Phase 15 |
| `SOFTWARE_RELEASE_CANDIDATE_READY` | YES |
| `RESEARCH_EXTERNAL_VALIDATION_COMPLETE` | NO |
| `CLINICAL_VALIDATION_COMPLETE` | NO |

## Canonical commits

All verified real via `git log -1 <hash>` before being listed here.

| Milestone | Commit |
|---|---|
| Upstream split point (InVesalius merge base) | `ca9aef76` |
| Phase 08 — D9/C7 root cause closure | `40c2c38b` |
| Phase 09 — Bidirectional 2D-3D sync, F3 | `d366a635` |
| Phase 10 — Data integrity, Undo/Redo memory | `0e51bcf9` |
| Phase 11 — Persistent test architecture | `36dc59ba` |
| Phase 12 — Quantitative validation | `52004e28` |
| Phase 13 — Manual QA closure, performance | `787fad80` |
| Phase 13.5 — Visual 2D→3D slice planes | `3d070f7c` |
| Phase 14 — Final audit (main commit) | `bed0c624` |
| Phase 14 — hash-fill-in follow-up | `6dae0922` |
| Post-Phase-14 Release Closure (main doc-fix commit) | `c43fa569` |

**Current branch tip is intentionally not hard-coded here** — a static value in a committed file becomes stale on the very next commit (this was a real, repeated problem in earlier phases, since fixed structurally rather than by re-pointing to a new value each time). Authoritative method:

```
git rev-parse HEAD
```

## Tests (current canonical baseline)

| Suite | Result |
|---|---|
| `tests/ct3d` | 184 collected / 183 passed / 1 skipped (optional) / 0 failed |
| Upstream `tests --ignore=tests/ct3d` | 94 passed / 0 failed |
| Manual QA (7 original items) | 7/7 PASS |
| C8 (Visual Sync 2D→3D) | `C8_VISUAL_OPERATOR_SMOKE=PASS` (operator core-path smoke test); 25/25 automated (`SP3D-T`+`SYNC3D-T`) PASS; 9 itemized TEST A-I = `NOT_EXPLICITLY_MANUAL_VERIFIED` (optional, not a blocker) |

## Main artifacts

**Code**:
- `plugins/roi_viewer/` — the plugin itself (~4700+ lines, 100% thesis-authored)
- `tests/ct3d/` — persistent pytest suite
- `tools/ct3d_benchmark.py` — real-dataset performance benchmark tool

**Documentation**:
- `docs/CT3D_MASTER_PROGRESS.md` — live progress/status tracker
- `docs/CT3D_FEATURE_AUDIT.md` — full feature-by-feature status matrix
- `docs/CT3D_REMAINING_WORK.md` — what genuinely remains (optional-internal / external / out-of-scope)
- `docs/CT3D_CHANGELOG.md` — append-only commit-by-commit changelog
- `docs/CT3D_RELEASE_NOTES.md` — release notes with research-prototype disclaimer
- `docs/CT3D_KNOWN_LIMITATIONS.md` — 14 classified limitations
- `docs/CT3D_P14_FINAL_AUDIT_REPORT.md` — final audit report + closure/freeze addenda
- `docs/CT3D_INSTALL_AND_RUN.md` — CT3D-specific install/run instructions
- `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md` — Vietnamese button-by-button user guide
- `docs/CT3D_MANUAL_QA_CHECKLIST.md` — manual QA evidence, item by item
- `docs/CT3D_SUS_PROTOCOL.md` — SUS usability-survey protocol (no real participants yet)
- `docs/CT3D_DATASET_REGISTRY.md` — real local DICOM dataset registry

## Optional dependency

- `pynrrd` (NRRD export only) — `pip install invesalius[nrrd]` or `pip install pynrrd`. Plugin works fully without it; NRRD export option is hidden/warned in the UI when absent.

## Known non-blocking gaps (external — require data/users/software not available in the development environment)

- GE / Canon CT vendor confirmation (2/4 common vendors confirmed real: SIEMENS, Philips)
- Real multi-series DICOM study (all 3 local datasets are single-series)
- Real ground-truth segmentation for Dice/Jaccard/Hausdorff validation (synthetic/phantom validation complete)
- SUS real participants (protocol ready, 0 participants so far)
- 3D Slicer comparative benchmark (not installed in the development environment)
- Clinical validation

## Out of scope (deliberate architecture decisions, not gaps)

- Pure volume raycasting connection (upstream InVesalius limitation, 0 call-sites to `Volume.OnShowVolume()`)
- DICOM-SEG export (NIfTI already satisfies the interoperability requirement)
- Custom Watershed/Morphology in the plugin (duplicates InVesalius's own real Watershed tool)

## Research disclaimer

This is a research/academic prototype produced for a master's thesis. It is **not** a certified medical device (no FDA/CE/regulatory clearance of any kind), is **not** intended for real clinical diagnosis or treatment, and has **not** undergone clinical validation. See `docs/CT3D_RELEASE_NOTES.md` for the full disclaimer.
