# CT3D Advanced E6 — AI Segmentation Architecture

**Branch**: `enhancement/advanced-segmentation` · **Date**: 30/09/2026 · Stable `thesis-ct-roi-tools` / tag `ct3d-rc1` (`aa1b3ad3`) not modified.

**E6 PASS means "AI ARCHITECTURE READY", not "AI MODEL READY".** No real model is shipped or run. Real inference: `BLOCKED_NO_REAL_PROVIDER`.

## 1. Pre-E6 validation (this run)

| Item | Result | Evidence |
|---|---|---|
| Git preflight | clean, HEAD = origin = `11dc8e66` | — |
| Baseline | `tests/ct3d` 446/1/0 ×3, upstream 94, pyflakes/compileall/diff-check clean | — |
| Coordinate contract | PASS — `wx = x·sx, wy = y·sy, wz = z·sz`, round+clamp inverse, slice↔view frame | `test_coordinates.py` + `test_coordinate_frames_integration.py`: 49 pass (C8, 3D pick, texture slice, clipping, E4 on 0051 spacing) |
| E5 gate | **PARTIAL → PASS** | Real rendered texture-orientation proof (`test_texture_orientation_render.py`, commit `9868adec`). See E5 report "E5 closure" |
| Operator statement | Group-level ("E4 live 3D preview, E5 texture/clipping basically PASS") recorded; **no manual item changed** | Manual QA doc |
| Native mask contract | **3 real defects found and fixed before E6** (commit `36a24d81`, fixture fix `81ad8638`) | `docs/CT3D_NATIVE_MASK_CONTRACT_FIX_REPORT.md` |

The native-mask defects mattered directly for E6: the Region Growing commit (which AI Accept had to share) lost voxels the first time a coronal/sagittal slice was shown, so "Accept == Preview" could not have held.

## 2. Architecture

```
Slice().matrix (read-only view)
  -> AISegmentationProvider.infer()        worker thread (job_controller)
  -> candidate, validated on native grid   (preview_bridge)
  -> E2 SegmentationPreviewManager, kind "ai"  -> 2D overlay (same aux path)
  -> E4 live 3D preview (source "ai_preview", no AI-specific actor)
  -> Accept -> native_mask.commit_preview_array_to_new_mask()
  -> real Mask in Project().mask_dict (source of truth)
```

Package `plugins/roi_viewer/core/ai/` (no wx, VTK, Project or Mask access):

| Module | Content |
|---|---|
| `__init__.py` | `ENABLE_AI_SEGMENTATION = False` (default of the UI checkbox) |
| `types.py` | `AIProviderInfo` (provider_id, display_name, version, available, unavailable_reason, capabilities, supported_prompt_types, supported_devices, requires_weights), `DeviceKind` AUTO/CPU/CUDA, `PromptType` (positive/negative point, box; scribble/lasso **reserved, PLANNED**), `PointPrompt`, `BoxPrompt`, `AIPrompts` (immutable snapshot), `AIVolume` + `read_only_volume()`, `AIInferenceRequest`, `AIInferenceResult` |
| `prompts.py` | `AIPromptSet` (session only), `make_point_prompt`, `make_box_prompt` (normalized inclusive z/y/x min/max); out-of-volume → `PromptOutOfVolume` (rejected, not clamped) |
| `provider.py` | `AISegmentationProvider` ABC: `probe()`, `validate_request()`, `infer(request, progress, cancel_event)`, `close()`; generic `check_request()` codes |
| `registry.py` | `AIProviderRegistry`: register/unregister/get/list_providers/probe/probe_all/close_all, exceptions isolated; `load_known_providers()`; `KNOWN_PROVIDER_MODULES = ()` |
| `job_controller.py` | `AIInferenceJobController`: IDLE/PREPARING/RUNNING/CANCELLING/RESULT_READY/FAILED, max 1 worker, job_id generation guard, cancel via event (no thread kill), results via injected `dispatch` (`wx.CallAfter`) |
| `preview_bridge.py` | `validate_candidate()`: exact shape, bool or 0/1 or 0/255, finite; otherwise `CandidateError` (shape/dtype/non_finite/not_binary). No reshape, resample or thresholding |

Shared commit: `core/native_mask.commit_preview_array_to_new_mask()` — shape checked before anything is created, native "Create new mask", exact 0/255 write, all three "computed" flag planes, `was_edited`, slice buffers discarded. Used by Region Growing (classic + E2) and AI Accept.

## 3. AI input volume (audited from source)

| Property | Value |
|---|---|
| Source | `Slice().matrix` via `ProjectInterface().get_volume_data()`, passed as a **read-only view** (provider cannot write; `np.shares_memory` proven in tests) — never a screenshot, texture, W/L image or mask-blended image |
| Shape / order | (z, y, x) |
| dtype | int16 memmap (`imagedata_utils.dcm2memmap`) |
| Values | CT DICOM: rescale slope/intercept applied on read (`converters.gdcm_to_numpy`) → HU, truncated to int16. Other imports: raw values |
| Spacing | (x, y, z) mm (`Slice().spacing`) |
| Origin | 0 (voxel centre = index × spacing) |
| Orientation | InVesalius's own grid: axial rows flipped on import (`[::-1]`), not re-oriented to RAS/LPS; may be the active filtered image version; gantry tilt corrected on import |

Providers own normalization/resampling/cropping and must return a mask on this exact grid.

## 4. UI (tab "Phân đoạn", collapsed section "Phân đoạn AI (thử nghiệm)")

`[ ] Bật phân đoạn AI (thử nghiệm)` · Mô hình · Thiết bị (Tự động/CPU/CUDA as the provider reports) · Kiểu điểm (Thuộc vùng / Loại trừ) · [Chọn điểm (3D)] [Điểm tại con trỏ 2D] · Hộp giới hạn: [Chọn góc 1] [Chọn góc 2] (at the 2D cursor) · prompt summary · [Xóa điểm AI] · [Xem trước bằng AI] [Hủy xử lý AI] · Trạng thái.

- Off (default): no registry, no provider module imported, no controller, no thread; all AI controls disabled.
- On, no provider: "Chưa có mô hình AI tương thích.", model "(chưa có)", Run disabled. Provider needing weights but missing them: "Mô hình chưa được cài đặt.".
- 3D picks go through `view_to_slice`; the 2D cursor is already slice frame (`ROIViewerFrame.get_crosshair_position()`).
- The AI result appears in the existing "Xem trước" box; Accept/Cancel there.
- All strings Vietnamese via `locale_vi.py`; English only for AI/CPU/CUDA. No `_("")`.
- Layout: outer borders of "Phân đoạn" 5 → 3 px so the tab still fits one screen with sections collapsed.

## 5. Behaviour guarantees and where they are tested

| Guarantee | Tests |
|---|---|
| Registry empty / register / duplicate / unregister closes / probe / probe exception isolated / close exception isolated / missing dependency module safe | `test_ai_provider.py` |
| Default OFF; no production provider; no Dummy/Fake/Random/Stub class in plugin; no AI framework or download/install import; importing the plugin loads no torch/tensorflow/onnxruntime/monai/totalsegmentator/segment_anything (fresh interpreter) | `test_ai_provider.py` |
| Points ±, world↔voxel round-trip, 0051 anisotropy, 3D pick via `view_to_slice`, box normalization, out-of-bounds rejected, clear, immutable snapshot, reserved types | `test_ai_prompts.py` |
| IDLE start, result only on GUI thread, progress, one job max (no queue), generation increments, cancel discards late result, stale never replaces new job, project close, plugin close, provider failure, request-check failure starts no thread | `test_ai_job_controller.py` |
| Real frame: prompts from 2D cursor; result → E2 preview with **no Project mask**; same 2D overlay; request is the real read-only volume; E4 source `ai_preview`; **Accept == Preview bit for bit** (also after every slice is shown); model not re-run; double Accept → one mask; Cancel → no mask, no checkpoint, E4 back to Current ROI; late result after E2 cancel / AI cancel / project close discarded; plugin close during inference safe; locked ROI untouched, new ROI unlocked; wrong-shape / probabilities / NaN / empty rejected with Vietnamese message; 0/255 candidate accepted; provider failure; no prompt → refused; E5 flags don't change the candidate; nothing AI on Project; `.inv3` save/open round-trip of an AI-accepted mask bit-identical | `test_ai_preview_integration.py` (23) |
| UI: off by default and nothing loaded, collapsed + Vietnamese, no-provider state, model-not-installed state, devices, disabling, classic controls unchanged | `test_ai_ui_state.py` |

The stub provider (`tests/ct3d/ai_stub_provider.py`) is test-only; a PASS with it proves orchestration, not AI quality.

## 6. Integration notes

- **E1**: AI runs on a locked current ROI (it creates a candidate, never edits the ROI); Accept creates a new unlocked ROI.
- **E2**: reused — `SegmentationPreviewManager.set_ai_preview()` (kind "ai", `ai_metadata`: provider, model/version, device, runtime, prompt count). A new AI run replaces any current preview; E2 "Hủy xem trước" also cancels a running AI job.
- **E3**: never applied automatically; usable on the accepted mask.
- **E4**: reused — the AI preview is just the E2 preview; source label "Xem trước AI".
- **E5**: independent (display only).
- **Lifecycle**: project close/load → `reset_ai_session()` (cancel, clear prompts, `close_all()`); plugin close → `shutdown_ai()` called first in `ROIViewerFrame._on_close()` (wx destroys windows at idle time, so the destroy hook alone was too late — found by test), and again from the panel's destroy hook (idempotent).
- **Save/Open**: nothing AI serialized; an accepted mask is an ordinary Mask.

## 7. Regression

`tests/ct3d`: **540 passed / 1 skipped / 0 failed** ×3 (541 collected; 446 at run start + 10 render + 10 native-mask − 1 replaced E3 test + 75 E6). Upstream 94. pyflakes / compileall / diff-check clean. Warnings are the pre-existing native `Mask.__del__` temp-file PermissionError on Windows.

## 8. Manual QA

E6-A..E6-L appended to `CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md`, all `NOT_RUN`. Real inference: `BLOCKED_NO_REAL_PROVIDER`. Nothing marked PASS from the stub.

## 9. Gate

| Criterion | Status |
|---|---|
| E1–E5 no regression, coordinates PASS | PASS |
| Default OFF, optional deps safe, no fake production AI, no downloads | PASS |
| Provider abstraction, prompts, job controller, stale guard | PASS |
| E2 reused, E4 reused, no Project mask before Accept, Accept == Preview | PASS |
| Lifecycle, Save/Open unchanged, classic workflow unchanged | PASS |
| CT3D / upstream / pyflakes / compile | PASS |
| Docs truthful | PASS |

**E6_GATE = PASS (AI ARCHITECTURE READY).** AI model: none.

## 10. E6b (TotalSegmentator) readiness

| Area | Status |
|---|---|
| Python compatibility | venv is Python 3.11; TotalSegmentator needs PyTorch + nnU-Net — install/compat not checked in this run (no install allowed) |
| Optional dependency mechanism | READY — provider module in `KNOWN_PROVIDER_MODULES`, lazy imports, import failure isolated |
| CPU/GPU path | READY at the API level (`DeviceKind`, provider-reported devices); real CUDA untested |
| Model storage | Policy set: no weights in repo, no auto-download; the provider must read a user-configured path and report "Mô hình chưa được cài đặt." otherwise. Config location still to be decided |
| Volume input contract | READY — documented in §3. TotalSegmentator expects NIfTI with a patient affine: the provider must build an affine for InVesalius's flipped, origin-0 grid and map its output back exactly |
| Output → preview | READY for binary masks. TotalSegmentator returns a multi-label map: the provider must choose one structure and return a binary mask (the bridge rejects label maps by design) |

**E6b readiness: READY to start** (architecture), with the open items above to resolve inside E6b.
