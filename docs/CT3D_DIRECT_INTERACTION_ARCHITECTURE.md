# CT3D ROI Viewer: Direct interaction (one-click interactive AI)

- **Branch:** `feature/interactive-ai-direct-click`, created from `feature/interactive-ai-medsam2` at `02c15f9e` (DIRECT_CLICK_BASE_HEAD) on 05/11/2026.
- **Isolation:** not merged anywhere.
- **Evidence:** `docs/evidence/direct_ai_20261105/`.

## Goal and result

The goal is **click → view → click → view → Accept**. With MedSAM2 selected and its environment checked, "Tương tác trực tiếp" is ticked by default. A left click on a 2D view adds a positive point, the marker appears at once, and the model runs automatically in two stages:

1. **Quick view:** the clicked slice only. It is provisional and cannot be accepted.
2. **3D candidate:** the full-volume result.

Accept remains the only operation that creates the native ROI.

The previous workflow (prompt type → "Điểm tại con trỏ 2D" → "Xem trước bằng AI" → "Cập nhật xem trước") is unchanged in two places:
- when "Tương tác trực tiếp" is unticked;
- under "Hiện tuỳ chọn nâng cao".

TotalSegmentator is unchanged.

## What did not change

- The external MedSAM2 process and its protocol.
- E2 preview, E4 preview and the native mask commit.
- The candidate SHA-256 identity and Accept exactness.
- The AI job controller and its generation guards.
- The TotalSegmentator provider code, ROI Analysis, and Save/Open.
- `Project().mask_dict` as the single source of truth.

All prompts still go through the one prompt store, `AIPromptSet`, with the voxel as the authoritative position. The same transient overlays are used: green and red dots, and a cyan box.

## Components

| Piece | Role |
|---|---|
| `gui/direct_ai_input.py` | Click and drag capture on the 2D views, with explicit input ownership (below). |
| `core/ai/direct_scheduler.py` | When to run: stages slice → volume; latest wins; at most 1 running job plus 1 "pending" flag. |
| `tools/interactive_ai_runtime/smart_prompt.py` | One-click policy (numpy only): `initial_prompt` (point_first) and `initial_box` (fast_2d_box). |
| worker `providers/medsam2_provider.py` | `scope` slice/volume, smart initialisation, and a reusable session (state plus feature cache). |
| `core/ai/semantic_suggestion.py` | Optional name suggestion from an existing TotalSegmentator cache. |
| `gui/segmentation_panel.py` | Simple/advanced layout, the direct callbacks, provisional preview, "Làm lại vùng này", the window-change guard, and the confirmed name. |

## Input ownership

Observers (left press / move / release) are attached to the 2D views' interactors only while direct interaction is active, and removed otherwise, on project close and on plugin close. A press is taken only in two InVesalius states:

- `STATE_DEFAULT`: no tool. The default style only records the button press (`styles.BaseImageInteractorStyle.OnPressLeftButton`).
- `SLICE_STATE_CROSS`: the cross moves to the same point.

Brush and eraser (`SLICE_STATE_EDITOR`), measures, WW/WL, pan, zoom, watershed and the other tools own the mouse, so nothing is taken. Ctrl or Alt also means nothing is taken. Events are never consumed; the native style still receives them (tested).

| Gesture | Result |
|---|---|
| Click | Positive point. |
| Shift+click | Negative point. It is refused with a message when the model does not declare negatives; MedSAM2 does not by default. |
| Drag > 6 px on Axial in `STATE_DEFAULT` | Box, through the same two-corner path as "Chọn góc 1/2", so the geometry is identical (tested). |
| Any other drag | A native gesture; no AI prompt. |
| Hover | Nothing; it never runs the model. |

Right click, Ctrl+Z and Escape are **not** hijacked. Undo stays a button, because these keys belong to InVesalius.

Positions come from the view's own `get_vtk_mouse_position()` and `get_coordinate_cursor()`, the same as the cross tool. They are in slice-frame world coordinates and are converted to voxels by `core/coordinates.py` (strict: out of volume is rejected).

## Source audit (fast 2D, state reuse)

Evidence: `02_source_audit.txt`.

- `add_new_points_or_box` returns the clicked frame's mask without propagation (`run_mem_encoder=False`). This is used for the quick view and for the smart initialisation.
- `_get_image_feature` keeps one frame and reassigns the cache dict, so every propagation re-encodes all 300 slices.
- `reset_state` keeps the images.

The worker therefore keeps one session per (volume, CT window, device): the normalised image tensor, one `inference_state` (reset before every prediction, with the prompts replayed in full from the prompt set), and a per-slice feature cache. The cache wraps `_get_image_feature` and hands the original method its stored entry, so the model code is unchanged. Caching stops when free GPU memory falls below `cache_min_free_mb` (1024), and it can be turned off with `"cache_features": false`.

## Smart initial prompt (measured, not assumed)

The spec's preferred pipeline was: click → fast 2D mask → its padded bbox + the point → 3D. It was implemented (`fast_2d_box`) and **measured worse** on 0543 than the plain point. The shipped default is `point_first`:

- the point alone, when the quick 2D mask is a real region (≥ 400 px and containing the click);
- otherwise an automatic click-centred box (half 64 px) plus the point.

The click-centred box is an automatic initial box, not anatomical recognition.

The table below uses the real model on 0543. Dice is against TotalSegmentator (a reference, not ground truth). Evidence: `03_benchmark_strategies.txt` and `04_benchmark_point_first.txt`.

| one click on | point only | fast-2D bbox (pad 0.1) | click box 16 / 32 / 64 | operator box (reference bbox) | **point_first (shipped)** |
|---|---|---|---|---|---|
| liver | 0.969 | 0.966 | 0.000 / 0.004 / 0.794 | 0.967 | **0.969** |
| spleen | 0.953 | 0.695 (box leaked to the kidney) | 0.08 / 0.23 / 0.69 | 0.696 | **0.953** |
| kidney left | 0.949 | 0.947 | 0.07 / 0.45 / 0.94 | 0.949 | **0.949** |
| kidney right | 0.964 | 0.961 | 0.08 / 0.82 / 0.95 | 0.963 | **0.964** |
| vertebra T12 | 0.634 | 0.628 | 0.42 / 0.71 / 0.83 | 0.842 | **0.634** |
| lung lower lobe left | 0.0003 (142 voxels) | 0.0007 (quick 2D 28 px) | 0.002 / 0.05 / 0.44 | 0.443 | **0.438** (fallback box) |
| mean | 0.745 | 0.700 | – / – / 0.775 | 0.810 | **0.818** |

- **One-click non-empty rate:** 6/6. The clicked voxel was inside the result in 6/6 cases.
- **The 400 px threshold:** the measured quick-2D sizes were 28 px (lung, where the point fails) versus 5,638–52,565 px (the five other targets, where the point works).
- **The 64 px fallback:** 64 was the best of the measured 16/32/64 for the lung and the vertebra.
- **Caveat:** these are 6 targets on one dataset. The policy is configurable (`DIRECT_SMART_*` in `segmentation_panel.py`, and the worker options).

## Refinement (measured, reported as is)

A second and third positive click were placed at the deepest voxel of the reference that the candidate **missed** (point_first, Dice vs TotalSegmentator):

| | 1 click | 2 clicks | 3 clicks |
|---|---|---|---|
| liver | 0.969 | 0.966 | 0.971 |
| spleen | 0.953 | **0.026** | 0.537 |
| kidney left | 0.949 | 0.719 | 0.804 |
| kidney right | 0.964 | 0.963 | 0.963 |
| vertebra T12 | 0.634 | 0.459 | 0.527 |
| lung (box) | 0.438 | 0.434 | 0.432 |

The previews update automatically and correctly; the plumbing is tested. But **with MedSAM2 on 0543, extra positive clicks on other slices did not reliably improve the result and sometimes made it much worse.** The operator should inspect each update and use "Hoàn tác điểm cuối" / "Làm lại vùng này". This is a model behaviour finding, not hidden. A box is the most stable way to correct an extent.

## Two stages and latest wins

`DirectPreviewScheduler`:

1. A click starts the **slice** stage (scope "slice", the clicked slice). Its result is shown as an E2 preview with `provisional=True`. Accept is disabled and refused; the status reads "Xem nhanh chỉ trên lát này - kết quả 3D sẽ hiện tiếp theo.". There is no E4 update.
2. The **volume** stage then starts automatically (smart init). It replaces the provisional preview; previews never stack.

If the prompts change while a stage runs, only a pending flag is set. When that stage ends, its result is discarded and the slice stage restarts from the current prompts. So at most 1 job runs and nothing queues (tested: 3 rapid clicks → 3 jobs in total; the visible result has all 3 points).

Changing the CT window removes the preview; nothing reruns until the next click. "Làm lại vùng này" clears the prompts and the candidate. Cancel keeps the prompts.

## Latency (real model, 0543)

| | Time |
|---|---|
| click → marker | 39.7 ms in the headless panel, incl. starting the job thread (`test_click_to_marker_latency…`); the marker never waits for the model |
| click → quick 2D view | 0.75–3.5 s (first ever: 7.6 s incl. state preparation) |
| click → 3D preview | 7.0–21.1 s (quick view + 3D stage) |
| operator-box path (previous workflow, one 3D run) | 5.6–11.5 s |

For refinements, the 3D stage takes 6.5–14.7 s.

## Model state reuse (A/B, same prompt, real model)

| | run 1 | run 2 | run 3 | peak VRAM | cached frames |
|---|---|---|---|---|---|
| cache on | 24.0 s | 10.9 s | 13.3 s | 5,257–5,273 MB | 300 |
| cache off | 23.1 s | 18.6 s | 17.4 s | 1,277–1,338 MB | 0 |

The candidates were **identical** (0 differing voxels), and identical across runs.

Repeated predictions on the same volume are about 30–40 % faster with the cache, at the cost of about 3.9 GB more VRAM. The cache is on by default with the free-memory guard; set `"cache_features": false` in `provider_config` on a GPU shared with heavy rendering. Run-to-run times varied (the same prompt took 10.9–13.3 s), so the numbers are ranges, not guarantees.

## Semantic suggestion

A suggestion is made only if TotalSegmentator **already ran** on the exact same voxel data in this session. The check uses the provider's in-memory `_cache` key, which is the blake2b of the voxels. The cache is read, never modified, and TotalSegmentator is never started for this.

The best label must pass all three thresholds:
- `coverage = |C∩L|/|C|` ≥ 0.80
- Dice ≥ 0.70
- `coverage − second coverage` ≥ 0.50

Measured on 0543:

| Candidate | Best label | coverage / Dice | second coverage | Outcome |
|---|---|---|---|---|
| liver | liver | 0.964 / 0.966 | 0.005 | suggested |
| kidney left | kidney_left | 0.903 / 0.947 | 0.007 | suggested |
| kidney right | kidney_right | 0.928 / 0.961 | 0.009 | suggested |
| leaked spleen box candidate | spleen | 0.535 | kidney 0.384 | refused |
| vertebra | T12 | 0.466 | T11 0.417 | refused |
| lung, tiny | – | – | – | refused |

The text says "Gợi ý dựa trên sự chồng lấn với phân đoạn TotalSegmentator đã có." Without a suggestion it says "Chưa xác định cấu trúc.". The ROI is renamed "AI - MedSAM2 - <label>" only after "Dùng tên gợi ý" is clicked. Labels are TotalSegmentator's canonical names (not translated, as in E6b). A suggestion is not a diagnosis.

## Geometry

A click uses the same coordinate path as the cross tool and the existing prompt store. Tests (0543, 0051 geometry):
- axial, coronal and sagittal clicks map to the expected voxel;
- the marker appears only on its slice;
- the quick 2D mask returns in native rows, centred on the click (`test_row_flip_is_applied_to_the_fast_2d_mask`).

In the real runs, every one-click candidate contained the clicked voxel (6/6).

## Data integrity

- No Project mask exists before Accept, including during the provisional and 3D stages.
- Candidate = E2 array. E4 uses the same preview array, and the provisional result is never sent to E4.
- Accept refuses provisional previews. It checks the candidate SHA-256, runs no inference, and creates exactly one mask. The parent ROI is unchanged and no surface is created. Tests: `test_accept_commits_exactly_the_3d_candidate`.

## Limitations

- Refinement clicks on other slices are unreliable with MedSAM2 (above).
- The vertebra one-click result was 0.63; a box reaches 0.84.
- The lung lower lobe is only 0.44, because MedSAM2 segments the whole dark lung region, not one lobe.
- The 0543 policy numbers come from one dataset and 6 targets.
- The feature cache uses about 5.3 GB of VRAM.
- No keyboard shortcuts.
- The 3D pick stays a manual (advanced) control.
- The headless tests cannot prove real-GUI behaviour. **The GUI gate needs the operator (DI-A…DI-S).**
