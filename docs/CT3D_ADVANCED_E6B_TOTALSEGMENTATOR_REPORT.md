# CT3D Advanced E6b — TotalSegmentator Provider

**Branch**: `enhancement/advanced-segmentation` · **Date**: 30/09/2026 · Stable `thesis-ct-roi-tools` / tag `ct3d-rc1` (`aa1b3ad3`) not modified. Not Phase 15, not E7.

**Status: `E6b_GATE = PARTIAL_REAL_INFERENCE_PENDING`.** The provider code is complete and tested without the package. **TotalSegmentator is not installed in this environment and no weights exist, so no real inference was run** (`REAL_AI_INFERENCE = BLOCKED_MODEL_NOT_AVAILABLE`). Nothing below claims segmentation quality, runtime or memory figures for real TotalSegmentator runs.

## 1. Environment (measured, 30/09/2026)

| Item | Value |
|---|---|
| Python | 3.11.7 (`D:\PyTools\invx-venv`) |
| TotalSegmentator | **not installed** (`pip show` → not found; no other Python env on this machine has it) |
| nnunetv2 | **not installed** |
| torch | 2.7.1+cu118 — `torch.cuda.is_available()` True, 1 device (NVIDIA GeForce RTX 4060 Laptop GPU) |
| nibabel | 5.2.1 |
| Weights | none (`~/.totalsegmentator` does not exist) |
| Compatibility | `NOT_INSTALLED` — TotalSegmentator/nnunetv2 version requirements cannot be read from an absent package; check them at install time |

Nothing was installed or downloaded by this run or by the plugin.

## 2. API audit

The package is absent, so the API was read from the official source (github.com/wasserth/TotalSegmentator, `totalsegmentator/python_api.py`, `config.py`, `libs.py`, `nnunet.py`) — read only, nothing fetched into the environment. Because the master branch may differ from any installed release, **`probe()` re-checks the installed version's real signature** (`inspect.signature`) and reports `api_incompatible` if a required parameter is missing.

| Fact (official source) | Used how |
|---|---|
| `totalsegmentator(input: str \| Path \| Nifti1Image, output=None, ml=False, fast=False, task="total", roi_subset=None, quiet=False, device="gpu", …)` | Called with an in-memory `Nifti1Image`, `output=None`, `task="total"`, `roi_subset=[structure]`, `device`, and `fast`/`quiet`/`ml` only if the installed signature has them |
| With `output=None` it returns the segmentation `Nifti1Image` (a tuple if statistics are on) | tuple handled (first element) |
| `nnUNet_predict_image`: `as_closest_canonical` → predict → `undo_canonical` → resample back to the input shape with the input affine; labels are `class_map` ids; `roi_subset` zeroes other labels | output checked for input shape + affine, then exact transposition |
| `roi_subset` must be a list of class names; only for task `total`/`total_mr` | one selected structure per run |
| device: `"gpu"`, `"cpu"`, `"mps"`, `"gpu:N"`; invalid GPU silently falls back to CPU inside TotalSegmentator | plugin only passes `"gpu"` when CUDA is really available; CUDA without a device is refused, never silently CPU |
| `fast` / `fastest`: lower-resolution models | "Nhanh / ít bộ nhớ hơn" = `fast=True`, only when the user picks it |
| **no progress callback** | stage texts only, no percentage |
| **weights are downloaded automatically** (`download_pretrained_weights(task_id)` when the weights folder is missing) | plugin checks weights first **and** replaces `download_pretrained_weights` with a function that raises while its run is active (restored afterwards) — the plugin can never start a download |
| **usage statistics are sent** (`send_usage_stats(config, {...})`, controlled by `config.json`) | replaced by a no-op during the plugin's run — inference stays local |
| weights dir: `$TOTALSEG_WEIGHTS_PATH`, else `$TOTALSEG_HOME_DIR/nnunet/results`, else `~/.totalsegmentator/nnunet/results` (`config.get_weights_dir()`) | the plugin uses TotalSegmentator's own location — no second model directory, no hard-coded path |
| class names/ids: `totalsegmentator.map_to_binary.class_map["total"]` | structure list and label id read from the installed package at probe time |
| internal temp files (`tmp_dir / "s01_0000.nii.gz"`) during prediction | the plugin itself writes no NIfTI; TotalSegmentator's own temp handling was not observable here |

## 3. Provider (`plugins/roi_viewer/core/ai/providers/totalsegmentator_provider.py`)

- Listed in `registry.KNOWN_PROVIDER_MODULES`; the module imports only numpy + stdlib. `probe()` uses `importlib.util.find_spec` (no import) when the package is absent → `package_missing`. Proven in a fresh interpreter: loading and probing the registry here imports none of torch/tensorflow/onnxruntime/monai/totalsegmentator/segment_anything/nnunetv2/nibabel.
- `probe()` (never runs the model): package → dependencies (python_api, nibabel, torch) → required API parameters → class map → weights folder → CUDA (`is_available()` and `device_count() > 0`) → modes. Reasons: `package_missing` / `dependency_missing` / `api_incompatible` / `weights_missing`, shown in Vietnamese ("TotalSegmentator chưa được cài đặt.", "Mô hình TotalSegmentator chưa sẵn sàng.", …); detail printed to console.
- Capabilities: `AUTOMATIC` only — no prompts (point/box controls disabled when it is selected; no prompts are passed) and **not `INTERRUPTIBLE`**.
- Parameters via the new generic `AIProviderInfo.parameter_choices` / `request.options`: `target_structure` (from the class map), `mode` (`standard` / `fast`). Generic E6 types gained only `parameter_choices`, `Capability.INTERRUPTIBLE`, stage/option/reason codes, and `progress(None, stage)`.
- `validate_request`: available, structure in list, mode supported, device supported, `acquisition_orientation == "AXIAL"` and a valid IOP.
- `infer` (worker thread only): build image → (only real stop point: cancel before the model) → run under `_guard()` → `extract_structure()` → `AIInferenceResult(mask bool, extra={structure, label_id, mode, ts_device, input_conversion_s, inference_s, output_mapping_s, foreground_voxels, output_affine})`.
- `close()`: `torch.cuda.empty_cache()` if available (project close/load, plugin close).

## 4. NIfTI affine — hard gate

**Source facts** (InVesalius): single-frame axial DICOM series are sorted by `gdcm.IPPSorter` — ascending along the slice normal (verified on 0051: z 116 → 276 mm) — and each slice's rows are flipped on import (`imagedata_utils.dcm2memmap`: `read_dcm_slice_as_np2(f)[::-1]`). `Project().patient_orientation` stores ImageOrientationPatient (LPS) — present in the 0051 sample `.inv3` as `[1, 0, 0, 0, 1, 0]`; `Slice().affine` is identity for DICOM imports (no patient affine is kept).

**Mapping** (row cosine r, column cosine c, normal n = r × c, spacing (sx, sy, sz)):

```
native (z, y, x)          -> NIfTI array index (i, j, k) = (x, y, z)   (np.transpose, exact)
matrix x axis  (LPS)      =  r
matrix y axis  (LPS)      = -c      (rows flipped on import)
matrix z axis  (LPS)      =  n      (IPPSorter ascending)
affine[:3, :3] = diag(-1, -1, 1) @ [r·sx | -c·sy | n·sz]   (LPS -> RAS), translation 0
```

0051: x → patient Left, y → Anterior, z → Superior; spacing (0.4785, 0.4785, 1.5) kept per axis. Anatomical cross-check on the real 0051 matrix: the body contour is flat against y = 0 (table, posterior) and rounded at high y (anterior).

**Why translation 0**: the plugin's grid origin is 0, TotalSegmentator only uses orientation/spacing, and the result is mapped back by exact transposition after checking the returned affine equals the input affine. Positions are therefore not scanner coordinates — irrelevant for segmentation, documented.

**Refused (never guessed)**: no IOP, non-orthonormal IOP, acquisition not AXIAL ("Không xác định được hướng bệnh nhân của khối ảnh - hiện chỉ hỗ trợ chuỗi DICOM lát ngang.").

**Proof** — `tests/ct3d/test_totalsegmentator_affine.py` (25):
- Anatomy: landmarks placed in DICOM pixel space, volume built by **InVesalius's real `dcm2memmap`** (only file reading replaced); the affine position of each landmark equals its physical DICOM position (LPS→RAS) — 4 orientations (0051 standard, rows flipped, 90° in-plane, 5° oblique) × 2 spacings ((0.4785, 0.4785, 1.5) and (0.5, 0.8, 2.3)), 5 landmarks (origin corner, near origin, two off-centre, last corner), shape (7, 11, 13).
- Control: an affine without the row flip fails that check.
- Roundtrip through TotalSegmentator-style geometry (canonical → predict → reorient back → extract): every landmark returns to its native voxel, all 8 combinations — no mirror, swap, rotation, off-by-one or spacing collapse.
- Output mismatch detection: y-mirrored, x/y-swapped, rescaled affines and a wrong shape all raise `OutputGridMismatch` (never reshaped).
- Invalid orientations refused.

## 5. UI ("Phân đoạn AI (thử nghiệm)", collapsed, off by default)

Mô hình: TotalSegmentator · **Cấu trúc**: search-as-you-type combo of the installed class names (canonical English names, not translated) · Thiết bị: Tự động / CPU (+ CUDA only if really available) · **Chế độ**: Chính xác tiêu chuẩn / Nhanh – ít bộ nhớ hơn · [Xem trước bằng AI] [Hủy xử lý AI]. Point/box controls disabled for this provider. Status: "Đang chuẩn bị dữ liệu…" → "Đang chạy TotalSegmentator…" → "Đang ánh xạ kết quả…" → "Đã hoàn thành trong … s." (no percentages). Cancel: "Đã yêu cầu hủy - mô hình đang chạy sẽ tự kết thúc ở chế độ nền, kết quả sẽ bị bỏ qua." Accept creates "AI - <structure>".

## 6. Pipeline and integration

TotalSegmentator → binary candidate on the native grid → `validate_candidate` → E2 `set_ai_preview` (orange overlay, all 3 views) → E4 source "ai_preview" → Accept → `native_mask.commit_preview_array_to_new_mask()`. No TotalSegmentator-specific preview, actor or storage. E1: locked ROI untouched, new ROI unlocked. E3: only after Accept. E5: independent. Lifecycle: project close/load → `reset_ai_session()` (+ `close()`); plugin close → `shutdown_ai()`.

## 7. Tests

| File | Count | Covers |
|---|---:|---|
| `test_totalsegmentator_affine.py` | 25 | §4 |
| `test_totalsegmentator_provider.py` | 33 | probe: missing package / dependency / API / weights / available / CUDA-only-if-real / probe never runs the model; device mapping; request validation (structure, mode, orientation, CUDA, prompts refused); inference returns exactly the class on the native grid (non-contiguous ids), in-memory input, roi_subset/device/fast/quiet/ml as chosen; missing class → empty; download and usage-stats guards (and restored); output grid mismatch; failure through the job controller with stage-only progress; close; module imports nothing heavy/Project/wx; real-environment probe truthful; **real frame end to end** (UI, structure required, E2 overlay, E4 source, no mask before Accept, Accept == preview, one mask, "AI - kidney_right", model not re-run, truthful cancel with late result discarded, no "%", unknown orientation refused) |
| E6 tests updated | — | one production provider (TotalSegmentator) instead of none; fresh-interpreter check that loading + probing imports no framework when the package is absent; no-provider / weights-missing states use explicit registries |

Fakes of the TotalSegmentator modules exist only in `tests/`; a PASS with them proves orchestration and geometry, not the model.

**Also fixed this run** (commit `6b491799`): `test_coordinate_frames_integration.py`'s helper called `ProjectInterface.__new__`, which returns the process-wide singleton, so it overwrote the real one's slice/spacing/shape and left a `get_volume_data` stub behind; the new E6b frame tests read the volume through `ProjectInterface` and exposed it. Now `object.__new__` (private instance).

## 8. Regression

`tests/ct3d`: **599 passed / 1 skipped / 0 failed** ×3 (600 collected; 540 before + 58 E6b + 1 E6 subprocess test). Upstream 94. pyflakes / compileall / diff-check clean.

## 9. Performance

Not measured: no real inference possible. The provider records `input_conversion_s`, `inference_s`, `output_mapping_s` and `foreground_voxels` per run (console + preview metadata) so the first real run produces these numbers.

## 10. Installation (for the operator — the plugin does none of this)

1. Into the same Python environment InVesalius runs in: `pip install TotalSegmentator` (pulls torch/nnunetv2; for GPU use a CUDA build of torch matching the driver — this venv already has torch 2.7.1+cu118). Check TotalSegmentator's own Python-version requirement at install time.
2. Get the `total` weights once **outside the plugin**, with TotalSegmentator's own tools (e.g. one CLI run on any CT NIfTI, or its weight-download command — see its README / `--help`). They go to TotalSegmentator's weights directory (§2). Optionally set `TOTALSEG_HOME_DIR` / `TOTALSEG_WEIGHTS_PATH` to use another folder.
3. Restart InVesalius, open ROI Viewer, tick "Bật phân đoạn AI (thử nghiệm)": the model list shows "TotalSegmentator" when package + dependencies + weights are found; otherwise the reason.

Stored in TotalSegmentator's directory: model weights (`nnunet/results/Dataset…`) and its `config.json`. The plugin stores nothing there and sends nothing over the network; CT data never leaves the machine.

## 11. Limitations

- Only single-frame axial DICOM series with stored ImageOrientationPatient. Coronal/sagittal acquisitions, NIfTI/bitmap imports and old projects without `patient_orientation` are refused. Enhanced multi-frame DICOM keeps file frame order on import — its z direction is unverified.
- If the user flips/swaps axes with InVesalius's own tools after import, the stored orientation no longer describes the matrix; the provider cannot detect this.
- A running TotalSegmentator call cannot be interrupted: cancel discards the late result; the computation (and GPU/CPU load) continues until it finishes.
- One structure per preview; other classes are ignored (no bulk mask creation).
- CPU inference of the full-resolution model can be very slow and memory-hungry; "Nhanh" trades accuracy for speed. Not clinically validated.

## 12. Manual QA / gate

E6b-A..E6b-P added to `CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md`, all `NOT_RUN`; on this machine only the "not installed" state is reachable.

| Criterion (spec §45) | Status |
|---|---|
| 1–7 E6 PASS, optional deps safe, plugin opens without package, truthful probe, no install, no download, cache policy documented | PASS |
| 8–9 affine tested, no swap/mirror | PASS |
| 10–14 structure selection, device mapping, off GUI thread, cancel/stale guard, exact native grid | PASS (with fakes) |
| 15–21 E2, E4, no mask before Accept, Accept == Preview, lifecycle, Save/Open (E6 round-trip test), classic workflow | PASS |
| 22–26 regression, upstream, pyflakes, compile, docs | PASS |
| **27 real inference actually succeeded** | **NOT DONE — package and weights absent** |

**`E6b_GATE = PARTIAL_REAL_INFERENCE_PENDING`**, `E6b_IMPLEMENTATION = WORKING_PROVIDER_CODE`. Next: install TotalSegmentator + `total` weights (§10), then run one bounded real inference (e.g. `spleen` or `liver`, GPU, standard) on 0051 and the Accept/E3/E4/surface/Save-Open checks of spec §37–38.

---

## 13. Final completion run (30/09/2026, evening)

### Environment (measured again)

Interpreter running InVesalius: `D:\PyTools\invx-venv\Scripts\python.exe` (Python 3.11.7). torch 2.7.1+cu118, CUDA 11.8 build, `torch.cuda.is_available()` True, 1 device "NVIDIA GeForce RTX 4060 Laptop GPU". nibabel 5.2.1, numpy 1.26.4, scipy 1.14.0, vtk 9.3.0, wxPython 4.2.5, setuptools 65.5.0. **TotalSegmentator and nnunetv2: not installed. No weights.** → `SETUP_REQUIRED`; no real inference possible in this run.

### Dependency audit (pip `--dry-run`, nothing installed)

| Command | Result |
|---|---|
| `pip install TotalSegmentator` | resolves TotalSegmentator 2.18.0 + 71 packages and **changes torch 2.7.1+cu118 → 2.14.0 (PyPI, CPU-only on Windows), numpy 1.26.4 → 2.2.6, setuptools 65.5.0 → 84.0.0** — conflicts with InVesalius's pins (`numpy==1.26.4`, `setuptools>=65,<68` for wxPython) and would lose CUDA. **Not acceptable.** |
| same with `-c tools/ct3d_ai_constraints.txt --extra-index-url https://download.pytorch.org/whl/cu118` | resolves 69 new packages (TotalSegmentator 2.18.0, nnunetv2 2.8.1, torchvision 0.22.1+cu118, SimpleITK, dipy, …) and **changes no installed package** |

`TotalSegmentator` declares `requires_python >=3.9` (3.11.7 OK).

### Installed-version API audit (TotalSegmentator 2.18.0 wheel, read from the wheel, not installed)

- `python_api.totalsegmentator(input, output=None, ml=False, …, fast=False, …, task="total", roi_subset=None, …, quiet=False, …, device="gpu", …)` — every parameter the provider uses exists.
- **Every run calls `download_pretrained_weights(task_id)`** (a no-op when the weight folder exists; it also deletes old weight folders), and with `roi_subset` a CT run first uses the 6 mm crop model **task 298**. `map_tasks_config.TASK_CONFIGS["total"]["sub_modes"]`: default 291–295, fast 297; folder names in `TASK_ID_WEIGHTS_CONFIGS`.
- Network calls reachable from a plugin run: `send_usage_stats` (stats server; config key `send_usage_stats`, default True) and the weight download (GitHub releases). License checks and the `dcm2niix` download only apply to commercial tasks / DICOM input (the plugin passes an in-memory NIfTI).
- Official weight tool: `totalseg_download_weights -t total` → tasks [291, 292, 293, 294, 295, 298]; `-t total_fast` → [297, 298].

### Defect found and fixed (`42875a5d`)

The E6b guard replaced `download_pretrained_weights` with a function that **always raised**. Because 2.18.0 calls it on every run, **every real inference would have failed even with all weights present**. Now the replacement returns when the required folder exists and raises `WeightsNotReady` (never downloading) when it does not. `probe()` checks the exact folders per mode (standard: 291–295 + 298; fast: 297 + 298) from the installed package's tables and offers only complete modes. Test fakes now behave like 2.18.0 (weight function called on every run); 4 of the new tests (all-weights-present run, and the per-mode weight checks for a missing 297, 293 or 298) fail on the old code and pass on the fix.

### Status

`REAL_AI_INFERENCE = BLOCKED` (package not installed). **`E6b_GATE = PARTIAL_REAL_INFERENCE_PENDING`** (unchanged). Setup steps: user guide §2.8 and `docs/CT3D_ADVANCED_RC_READINESS_REPORT.md` §6.

**First real run plan**: dataset 0051 is a head CT, so use structure `brain` (2.18.0 class id 90; `skull` = 91) - not `spleen`/`liver`, which are outside its field of view. 2.18.0's `total` map has 117 classes.

### Real-application defect (30/09/2026, from an operator screenshot)

In the real InVesalius the AI status read "totalsegmentator hiện không dùng được." instead of "TotalSegmentator chưa được cài đặt.". Cause: InVesalius's PluginManager imports the plugin as the package **"ROI Viewer"** (`invesalius.plugins.import_source`), while `KNOWN_PROVIDER_MODULES` named the provider absolutely (`plugins.roi_viewer...`). That loaded a second copy of `core/ai`; the provider's `AIProviderInfo` was a different class, and the registry rejected every probe ("probe returned invalid provider info"). pytest imports the plugin as `plugins.roi_viewer`, so no test saw it. Fix: provider modules are named relative to the registry's package (`.providers.totalsegmentator_provider`). New test loads the plugin exactly like the application (fresh interpreter, `import_source("ROI Viewer", ...)`) and checks the provider's own info and that no second package copy exists; it fails on the old code with the operator's symptom.
