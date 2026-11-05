# CT3D ROI Viewer: Direct interaction (one-click AI) manual QA

**Branch:** `feature/interactive-ai-direct-click`.

**Status:** every item starts **NOT_RUN**. Only the real operator, running the real InVesalius GUI, can mark PASS. Automated tests are listed for reference only; they are not a manual PASS.

**Preconditions:**
- the separate MedSAM2 environment and `roi_viewer_interactive_ai.json` are in place (`tools/interactive_ai_runtime/README.md`);
- 0543 is imported, and a mask exists, because the E2 overlay needs a current mask;
- in ROI Viewer → Phân đoạn → Phân đoạn AI: "Bật phân đoạn AI" is ticked, "Phân đoạn AI tương tác (MedSAM2)" is selected, and "Kiểm tra môi trường" shows "Môi trường đã sẵn sàng.";
- no InVesalius tool is active (pointer), or the cross tool is active.

| ID | Steps | Expected | Automated reference | Actual |
|---|---|---|---|---|
| DI-A enable | Select the interactive model after the check. | "Tương tác trực tiếp" ticked by default; hint "Nhấp vào cấu trúc cần lấy…"; no "Xem trước bằng AI" button; "Hiện tuỳ chọn nâng cao" shows the old controls. | `test_direct_mode_is_the_default_for_the_interactive_model` | NOT_RUN |
| DI-B single click on liver | Click once inside the liver (Axial). | Green dot at once; "Đang xem nhanh trên lát hiện tại…" then an orange overlay on that slice; then "Đang phân đoạn vùng đã chọn trong 3D…" and the 3D overlay; no mask in the list; record time click→dot, click→quick view, click→3D. | `test_click_marker_first_then_automatic_slice_and_3d` | NOT_RUN |
| DI-C click on spleen | Same on the spleen. | Non-empty plausible candidate; record result. | benchmark (`docs/evidence/direct_ai_20261105/`) | NOT_RUN |
| DI-D marker accuracy | Click a small landmark; scroll ±1 slice. | Dot exactly under the cursor, only on its slice; also on Coronal/Sagittal when scrolled to it. | `test_markers_only_on_their_slice_in_each_orientation` | NOT_RUN |
| DI-E automatic preview | After DI-B. | Preview appears without pressing any button; Chấp nhận disabled during the quick view, enabled for the 3D result. | auto-preview tests | NOT_RUN |
| DI-F second click | Click a missed part. | Preview updates automatically; the 3D result replaces the old one (not stacked). | `test_second_click_refines_automatically` | NOT_RUN |
| DI-G rapid double click | Click 3 times quickly in different places. | GUI responsive; only one result appears at the end, containing all clicks; no backlog of runs. | `test_three_rapid_clicks_show_only_the_last_prompt_set` | NOT_RUN |
| DI-H drag box | Pointer tool, drag a rectangle on Axial around the kidney. | Cyan rectangle while dragging; prediction starts on release; previous candidate replaced; no mask. Drag on Coronal does nothing. | box-drag tests | NOT_RUN |
| DI-I views | Click once each on Axial, Coronal, Sagittal. | Point lands at the clicked spot in each view (no mirror/swap). | geometry + input tests | NOT_RUN |
| DI-J E4 | Tick live 3D preview, repeat DI-B. | E4 source "Xem trước AI tương tác"; mesh equals the 3D overlay (not the quick slice). | – | NOT_RUN |
| DI-K Accept | Chấp nhận. | One mask "AI - MedSAM2 N" (or "AI - MedSAM2 - <name>" after "Dùng tên gợi ý"); console "identical to the candidate"; no AI run at Accept. | `test_accept_commits_exactly_the_3d_candidate` | NOT_RUN |
| DI-L Brush after Accept | Brush on the new mask (direct clicks must stop while the brush is on), then Undo. | Brush edits the mask; no AI point is added while brushing. | `test_brush_or_measure_owns_the_mouse` | NOT_RUN |
| DI-M Analysis | ROI analysis on the new mask. | As for any ROI. | analysis suites | NOT_RUN |
| DI-N Cancel | Hủy on a preview; then "Làm lại vùng này". | Hủy removes the overlay and keeps the dots; Làm lại removes dots and preview. | `test_cancel_keeps_prompts_restart_clears_everything` | NOT_RUN |
| DI-O TotalSegmentator | Switch the model to TotalSegmentator. | Old workflow: structure list, Run button; clicks on CT add nothing. | TS regression tests | NOT_RUN |
| DI-P AI off | Untick AI: Threshold, Otsu, Region Growing, seed pick, Brush, Undo, cross tool, measures, WW/WL. | Unchanged; clicks never add AI points. | full `tests/ct3d` | NOT_RUN |
| DI-Q plugin close/reopen | Close ROI Viewer during a prediction; reopen. | No error; no dots left in the 2D views; worker gone. | `test_plugin_close_during_inference` | NOT_RUN |
| DI-R project close during prediction | Close the project while "…trong 3D…". | No preview, no mask, no crash, no `roiviewer-iai-*` left. | `test_project_close_during_inference` | NOT_RUN |
| DI-S semantic suggestion | Run TotalSegmentator once on 0543 (any structure), switch to MedSAM2, click the spleen. | "Gợi ý cấu trúc: spleen (…)" with the TotalSegmentator sentence; "Dùng tên gợi ý" → name "AI - MedSAM2 - spleen". Without a prior TotalSegmentator run: "Chưa xác định cấu trúc.". | semantic suggestion tests | NOT_RUN |

**DIRECT_INTERACTION_MANUAL_QA_COMPLETE: NO.** 0 PASS, 19 NOT_RUN.
