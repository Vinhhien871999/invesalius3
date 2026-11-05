# CT3D ROI Viewer: Interactive AI (MedSAM2) architecture

- **Branch:** `feature/interactive-ai-medsam2`, created from `enhancement/advanced-segmentation` at `70720ca8` (BASE_HEAD) on 05/11/2026.
- **Status vocabulary:** PLANNED / AUDITED / IN_PROGRESS / WORKING / PARTIAL / BLOCKED / PASS / FAIL.
- **Status summary:** the infrastructure is WORKING and verified with automated tests. The real MedSAM2 model is BLOCKED: no separate environment and no checkpoint exist on this machine, and WSL cannot start here.

## Goal

The operator places positive points, negative points and/or a bounding box. MedSAM2 returns a 3D candidate. The operator inspects it in 2D (E2 orange overlay) and 3D (E4 live preview), refines the prompts, and presses **Chấp nhận** only when satisfied. Accept creates a normal InVesalius mask that is exactly the inspected candidate. After that the ROI is like any other: Brush, Cleanup, surface, ROI Analysis, Save/Open.

## Non-goals

- Not a replacement for TotalSegmentator, and no change to E6/E6b.
- No multi-object or multi-label output, no text prompts, no training or fine-tuning UI.
- No cloud, no model downloader, no automatic clinical interpretation.
- No auto-inference on each click: v1 uses explicit Xem trước / Cập nhật xem trước.
- Prompts are not persisted in `.inv3` in v1.

## Existing E6 reuse

Nothing parallel was built. The interactive AI reuses the existing E6/E2/E4 path:

| Piece | Reused | Changed |
|---|---|---|
| `AISegmentationProvider` / registry (`core/ai/provider.py`, `registry.py`) | yes | `registry.update_info()` (result of the explicit environment check) |
| `AIInferenceJobController` (one job, generation guard, GUI-thread dispatch) | yes, unchanged | - |
| `AIPromptSet` / `PointPrompt` / `BoxPrompt` (voxel authoritative, strict out-of-volume rejection) | yes | `undo_last_point()`, `clear_box()` |
| `preview_bridge.validate_candidate` → E2 `set_ai_preview` → 2D overlay → E4 source | yes, unchanged | E4 label "Xem trước AI tương tác" when the preview is interactive |
| Accept → `native_mask.commit_preview_array_to_new_mask` (shared native commit) | yes | name "AI - MedSAM2 N"; SHA-256 identity check |

`AIProviderInfo` gained three optional fields with defaults: `show_when_unavailable`, `checkable` and `details`. The defaults keep TotalSegmentator's info identical, which `test_totalsegmentator_unaffected_by_the_interactive_provider` checks.

## Provider abstraction

`core/ai/providers/medsam2_external_provider.py` (`MedSAM2ExternalProvider`, id `medsam2`) is registered in `KNOWN_PROVIDER_MODULES` after TotalSegmentator. It has three levels:

1. **`probe()`** is cheap and runs on "Bật phân đoạn AI". It reads the configuration only and never starts a process.
   - Not configured → `not_configured`. The UI shows "MedSAM2 chưa được cấu hình." plus "Chức năng này cần môi trường AI riêng. ROI Viewer không tự cài đặt hoặc tải mô hình."
   - Configured → `not_checked`.
2. **`check_environment()`** runs when the operator clicks "Kiểm tra môi trường", on a worker thread.
   - It starts the external runtime and sends HELLO and PROBE.
   - Capabilities, prompt types, devices, version and checkpoint all come from the worker; the host assumes nothing.
3. **`infer()`** runs on the job-controller thread. It sends LOAD_VOLUME once per volume fingerprint, then PREDICT, and returns the validated candidate.

The GUI reads capability metadata only: a prompt control is enabled only if its prompt type is declared, and the CT window choice appears only if presets are declared. Nothing in the GUI special-cases MedSAM2, except the generic "interactive" display name for `checkable` providers.

## External runtime rationale

MedSAM2 has hard requirements: torch ≥ 2.5.1, numpy ≥ 2.0.1 and Python 3.12, and its documentation is Linux-oriented. `invx-venv` has Python 3.11.7, torch 2.7.1+cu118, numpy 1.26.4, nnunetv2 2.8.1 and TotalSegmentator 2.18.0. Installing MedSAM2 there would move numpy to 2.x under InVesalius/VTK/TotalSegmentator, so it would risk breaking a working environment. A separate process removes that risk entirely, and also isolates crashes, GPU memory and model lifetime.

## Dependency isolation

- ROI Viewer imports no torch, sam2 or model code for this feature. `core/ai/external/*` uses the standard library and numpy only.
- Nothing is pip-installed into `invx-venv`. Evidence: `pip freeze` SHA-256 before and after is identical (`docs/evidence/interactive_ai_20261105/01_baseline.txt` and `12_final_regression_1.txt`).
- The worker (`tools/interactive_ai_runtime/worker.py`) owns torch, CUDA, the checkpoint, the model and the cached state.
- The setup scripts (`setup_medsam2_linux.sh` and the experimental `setup_medsam2_windows.ps1`) are run by the operator by hand, into a new folder. They never touch `invx-venv` and never download weights.

## IPC protocol

`core/ai/external/protocol.py` is standard library only and has a byte-identical copy in `tools/interactive_ai_runtime/protocol.py`; a test checks the two are identical.

**Transport.** The worker is a persistent child process (`RuntimeProcess`, one `subprocess.Popen`). Control messages are JSON Lines on stdin and on a private duplicate of the worker's original stdout. The worker redirects fd 1 and `sys.stdout` to stderr, so library prints cannot corrupt the channel (tested with Python prints and raw fd-1 writes).

**Commands:** HELLO, PROBE, LOAD_VOLUME, SET_PROMPTS, PREDICT, CLEAR_PROMPTS, RELEASE_VOLUME, CANCEL, SHUTDOWN.

**Envelope.**
- Every request carries `request_id`, `generation_id` and `volume_id`.
- Every response echoes the three ids and adds `status` (`ok` / `error` / `progress`), `error_code` and `message`.

**Parsing and safety.**
- `json.loads` is the only deserializer: no pickle, no eval.
- NaN/Infinity, lines over 1 MiB, non-objects and boolean ids are rejected.
- Large arrays are never sent in JSON. They travel as `.npy` files (`allow_pickle=False`) in the private session directory.

**Stale and cancelled requests.**
- A response for a request the host gave up on is counted (`stale_responses`) and dropped.
- CANCEL is handled by the worker's stdin thread at once. The provider checks it between propagated slices.

**Error codes.** These are in `protocol.E_*`:
- unknown_command, bad_request, protocol_version, dependency_missing, checkpoint_missing, model_load_failed, cuda_unavailable, cuda_oom, volume_not_loaded, volume_mismatch, prompt_unsupported, needs_prompt, internal_error
- host side only: worker_start_failed, worker_exited, timeout, cancelled, malformed_response, invalid_output, not_configured

Each code has a Vietnamese message. No traceback is shown in the GUI; details go to the console.

## Volume contract

- **Input.** The input is `Slice().matrix`, exactly as InVesalius holds it:
  - (z, y, x), int16 HU (rescale applied on import)
  - spacing (x, y, z) mm, origin 0
  - a read-only view via `read_only_volume`. A test proves the source volume is unchanged.
- **Transfer.** The host writes `volume.npy` plus `metadata.json` (shape, dtype, spacing, orientation, fingerprint, min/max). No DICOM is copied, and no patient name, ID or study text is included.
- **Fingerprint.** blake2b over shape, dtype, spacing, orientation and the voxel bytes (0.25 s for 0543). The worker keeps the volume and its preprocessed slices per fingerprint. A new CT releases the old state.

## Coordinate contract

`core/coordinates.py` is the single source of coordinate conversions; nothing re-derives them.

| Input | Path to voxel |
|---|---|
| 2D cursor (cross focal point, slice frame) | voxel by `world_to_voxel_strict`; out of volume is rejected, never clamped |
| 3D pick | `view_to_slice` (y negated) first, then as above |

Prompts are stored with voxel (z, y, x) as the authoritative position. World mm is informational. Nothing is re-inferred from screen pixels.

Tests (`test_interactive_ai_geometry.py`) cover axial, coronal and sagittal points, 3D picks, the round trip, and 0543 (300×512×512, 0.5859 × 0.5859 × 1.0) and 0051 (108×512×512, 0.4785 × 0.4785 × 1.5) geometry. They also check: no mirror, no axis swap, no y-flip regression.

## Prompt model

| Prompt | Entered by | Stored as | MedSAM2 use |
|---|---|---|---|
| Positive point "Thuộc vùng" | "Điểm tại con trỏ 2D" (recommended; tooltip "Đặt điểm chính xác bên trong cấu trúc tại vị trí con trỏ 2D") or "Chọn điểm (3D)" (tooltip "…điểm thường nằm ở biên") | `PointPrompt(world_xyz, voxel_zyx, positive=True)` | SAM2 point, label 1, on its slice |
| Negative point "Loại trừ" | same | `positive=False` | label 0, only if the worker declares it (off by default) |
| Box | "Chọn góc 1" / "Chọn góc 2" at the 2D cursor, in any order | `BoxPrompt`, inclusive voxel min/max per axis | a **2D box on the middle slice** of the box; result limited to the box's slice range when the corners are on different slices |

- **Editing:** "Hoàn tác điểm cuối", "Xóa hộp" and "Xóa gợi ý" (clears all).
- **Markers:** green and red dots, and a thin cyan box outline (a ring for a single corner), in the 2D views on their own slices only.
  - They are drawn by `gui/ai_prompt_overlay.py`: one plugin `CanvasHandlerBase` per 2D view in the canvas draw list, the same mechanism as InVesalius's measurement handles.
  - They are transient: never Project data, never the image, `is_over()` is always None so they never take the mouse, and they are removed on clear, provider change, project close and plugin close.
  - The yellow 3D crosshair marker is not reused.
- **Clearing:** prompts are cleared on project close/load, provider change and plugin close. They are not saved.

## Provider capabilities

Each statement is sourced from the official-source audit of 05/11/2026; each row of the table below names its source.

**Repository and licences.**
- `bowang-lab/MedSAM2` main @ `332f30d420f1d1b08e2a79b3ae6a602458808383` (2025-07-11), Apache-2.0.
- Python 3.12 (README) / ≥ 3.10 (setup.py), torch 2.5.1 / torchvision 0.20.1 with CUDA 12.4 wheels. The README is Linux-only; SAM2's INSTALL.md recommends WSL on Windows. The CUDA extension is optional.
- Checkpoints: `wanglab/MedSAM2` (HF), `MedSAM2_latest.pt` (156 MB, "recommended"), config `configs/sam2.1_hiera_t512.yaml`.
- Weights licence: the metadata says cc-by-sa-4.0, but the card text says "research and education purposes" only. This conflict must be checked by the operator.

| Capability | MedSAM2 | Source |
|---|---|---|
| positive point | YES | SAM2 API `add_new_points_or_box(points, labels)`; official `medsam2_infer_CT_lesion_npz_recist.py` uses label-1 points |
| negative point | UNKNOWN → off by default | SAM2 API accepts label 0; no official MedSAM2 path uses it; paper: "reliance on bounding boxes as the main prompts" |
| 2D box | YES | official `medsam2_infer_3D_CT.py`: box on the key slice |
| 3D box | NO (approximated, see Prompt model) | the official path takes a 2D box |
| 3D propagation | YES | `propagate_in_video` forward + `reverse=True` |
| multi-object | NO in this provider (API: yes, `obj_id`) | single target object in v1 |
| incremental refinement | YES (re-run with the full prompt set) | SAM2 supports correction clicks; v1 recomputes from all prompts |
| CPU | library: falls back (`get_best_available_device`); official scripts: CUDA only, untested | build_sam / scripts |
| CUDA | YES | official scripts (bfloat16 autocast) |

## Preprocessing

This reproduces the official `medsam2_infer_3D_CT.py` in `providers/medsam2_provider.py`. The numpy-only parts are tested here.

1. Clip to a CT window [lower, upper].
2. Scale with the clipped volume's own min/max to 0..255 and cast to uint8.
3. Convert each slice with PIL `convert("RGB").resize((512, 512))` (PIL default filter), then /255 and ImageNet mean (0.485, 0.456, 0.406) / std (0.229, 0.224, 0.225).
4. Call `build_sam2_video_predictor_npz` → `init_state(images, H, W)` → `add_new_points_or_box(frame, obj_id=1)` → forward propagation → `reset_state` → the same prompts again → reverse propagation.
5. Threshold at logits > 0. The predictor resizes logits to H × W bilinearly, as the official code does.
6. Keep the largest connected component (full connectivity, = `getLargestCC`).

Deviations, all explicit and configurable:
- **Window:** chosen by the operator from the paper's presets:
  - soft tissue W400/L40 → [-160, 240] (default)
  - lung W1500/L-600 → [-1350, 150]
  - bone W1800/L400 → [-500, 1300]

  The official script reads a per-lesion DICOM window from its dataset CSV.
- **`flip_rows_to_dicom` (default on):** InVesalius reverses each axial slice's rows on import (`imagedata_utils.dcm2memmap`, `[::-1]`). The model therefore sees the DICOM row order, and the mask is flipped back by exact index reversal (tested).
- **Prompts on several slices:** each such slice is a conditioning frame. Forward propagation starts at the first one; reverse output is taken for frames before it.

## Candidate contract

**Worker side.** The worker returns 0/1 uint8 at exactly the native (z, y, x) shape. A wrong shape is rejected in the worker (`invalid_output`).

**Host checks, in order:**
1. `load_candidate`: `.npy` without pickle, exact shape, integer or bool dtype, values {0, 1}.
2. Response `volume_id` and `generation_id` must equal the request's.
3. `preview_bridge.validate_candidate`.
4. An empty result shows "AI không tìm thấy vùng nào." and creates no preview.

**Provenance.** This information is kept with the preview:
- provider, model version (repository commit), checkpoint name, model config, device
- point counts, box, CT window, key frames, peak VRAM
- runtime and generation id
- candidate SHA-256

## E2 integration

`_on_ai_run` → job controller → `infer` → `_on_ai_result` → `set_ai_preview(kind "ai")` → the E2 2D orange overlay, through the same Slice aux mechanism as every E2 preview. The run button reads "Xem trước bằng AI", and "Cập nhật xem trước" while an AI preview is shown.

A new run replaces the preview through the E2 generation counter; previews never stack. A late result from an older generation is discarded, both by the job controller and by the E2 generation. No mask exists until Accept. Tests check this before the prediction, after it, and after a refinement.

## E4 integration

With E4 on, the source becomes the AI preview array itself, labelled "Xem trước AI tương tác". The mesh is built from exactly that array; no special case was added. Cancel makes E4 fall back to the Current ROI.

## Accept contract

1. `_on_preview_accept` (kind "ai") → `_commit_ai_preview(preview_array)`.
2. The SHA-256 of the preview is checked against the candidate's SHA-256 recorded at preview time. On a mismatch, Accept is refused.
3. → `native_mask.commit_preview_array_to_new_mask` (shared commit).
4. The SHA-256 of the committed logical mask is printed to the console ("identical to the candidate").

Guarantees:
- No inference, preprocessing or resampling happens at Accept. The test counts `infer` calls.
- The name is "AI - MedSAM2 N", never an existing mask's name.
- The parent and current ROIs are untouched, and no surface is created. Tests: `test_prompt_preview_refine_cancel_accept`.

## Lifecycle

- **Startup:** the worker starts lazily, only after AI is ticked on, the interactive model is selected, and the check passes. The model is loaded once and stays resident. The volume and preprocessed slices are cached per fingerprint.
- **Project close/load:** `reset_ai_session` → job cancel → `close_all` → `provider.close()`.
  - The worker gets SHUTDOWN, or is killed if a request is running.
  - The session directory is deleted, and prompts and markers are cleared.
  - The environment check result is kept; the next prediction starts the worker again.
- **Plugin close:** `shutdown_ai` does the same. The job controller never calls back afterwards.
- **Abandoned temp directories:** cleaned at worker start. Only directories with the prefix `roiviewer-iai-`, the marker file, located directly in the temp root, and older than 24 h are deleted (tested).
- **Process termination:** only the plugin's own `Popen` is ever killed. The worker also exits on its own when its stdin closes, even mid-inference.

## Failure handling

| Failure | Behaviour (tested) |
|---|---|
| not configured / invalid config | listed, "chưa được cấu hình", nothing started |
| runtime executable missing | `worker_start_failed`, reported after the check |
| checkpoint / dependency missing | the worker's PROBE says so → unavailable with the reason |
| worker crash | `worker_exited` message; the UI is usable; the next run restarts the worker |
| timeout | the worker is killed, `timeout` message |
| malformed output line | the worker is killed, `malformed_response` |
| invalid candidate | rejected, no preview, no mask |
| CUDA OOM | `cuda_oom`: "Không đủ bộ nhớ GPU…". **No silent CPU fallback**, even on "Tự động". Auto picks CUDA if available, else CPU, when the model loads. |
| project closed / plugin closed during inference | the worker is killed; no preview, no mask, no temp files left |
| new prediction while one runs | refused by the job controller (one job at a time) |

## Privacy

Everything stays local: there is no HTTP, no telemetry and no upload. Only voxel values, geometry and prompts cross the boundary. Temp names are random, and metadata has no patient fields.

## Provenance

At Accept, `roi_provenance[mask] = {"source": "AI", "ai": {...}}` is recorded. This is session-only, the same as E6. It is optional, so older projects still open.

## Performance

These timings are measured with the fake worker on the 0543-size volume (300×512×512 int16, 150 MiB). They cover the protocol and I/O only, not MedSAM2. Evidence: `11_performance.txt`.

| Step | Time |
|---|---|
| fingerprint | 0.25 s |
| worker start + HELLO | 0.26 s |
| volume write | 0.14 s |
| LOAD_VOLUME | 0.10 s |
| candidate SHA-256 | 0.14 s |
| SHUTDOWN + cleanup | 0.03 s |

Model load, preprocessing, inference and peak VRAM are reported by the real provider (`details`) but have **not been measured**, because the model is blocked.

## Save/Open

The accepted mask is a normal InVesalius mask, saved and opened by InVesalius. Prompts, preview and runtime state are not persisted. After reopening, AI starts off. The real Save/Open round trip is the operator item IA-S, NOT_RUN.

## Risks

1. **The real model has not run here.** Preprocessing fidelity, prompt effect, VRAM on the RTX 4060 (8 GB) with 300 slices, and runtime are unverified.
2. **Negative points:** not officially used by MedSAM2. Off by default.
3. **3D box:** approximated by a middle-slice 2D box plus slice limits.
4. **Window choice:** the official script uses dataset-specific windows. A wrong preset can degrade results.
5. **Row flip:** `flip_rows_to_dicom` assumes the axial import flip, which holds for InVesalius's DICOM import. Other import paths are not analysed.
6. **Largest component** drops disconnected parts (official behaviour).
7. **Native Windows:** not the documented MedSAM2 platform. WSL could not start on this machine (`HCS_E_SERVICE_NOT_AVAILABLE`).
8. **Weights licence** conflict (cc-by-sa-4.0 metadata vs "research and education" card).

## Deferred work

- Real MedSAM2 smoke and interaction test (needs the environment and checkpoint).
- User guide section, which the spec says to write only after the real provider works.
- Multi-object, prompt persistence, auto-refinement, and 3D prompt markers.
- Embedding reuse across prompt edits: SAM2 inference state is rebuilt per prediction in v1, while the preprocessed slices are cached.
- A CPU (EfficientTAM) variant, and DPI verification of the 3D pick.
