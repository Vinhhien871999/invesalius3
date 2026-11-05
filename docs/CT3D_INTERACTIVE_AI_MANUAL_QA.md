# CT3D ROI Viewer: Interactive AI (MedSAM2) manual QA

- **Branch:** `feature/interactive-ai-medsam2`.
- **Status:** every item starts at **NOT_RUN**. Only the real operator, running the real application, can mark PASS. Automated tests are listed for reference only; they are not a manual PASS.

## Preconditions

- **Common:** InVesalius with the plugin from this branch; dataset 0543 imported (thorax and upper abdomen); a mask exists, because the E2 overlay needs a current mask; ROI Viewer → Phân đoạn → "Phân đoạn AI (thử nghiệm)" → tick "Bật phân đoạn AI (thử nghiệm)".
- **IA-B onward:** done on this machine on 05/11/2026 (`D:\PyTools\medsam2-venv`, `D:\PyTools\MedSAM2`, config file written, probe exit 0). The original requirements:
  - The separate MedSAM2 environment is set up by hand (`tools/interactive_ai_runtime/README.md`).
  - The checkpoint is placed by hand.
  - `roi_viewer_interactive_ai.json` is written.
  - `probe_runtime.py` returns exit code 0.

| ID | Steps | Expected | Automated reference | Actual |
|---|---|---|---|---|
| IA-A provider unavailable | No config file. Choose "Phân đoạn AI tương tác (MedSAM2)". | Status "MedSAM2 chưa được cấu hình."; hint "Chức năng này cần môi trường AI riêng. ROI Viewer không tự cài đặt hoặc tải mô hình."; Xem trước disabled; "Kiểm tra môi trường" re-reads the configuration and still says not configured; no Python process started (Task Manager); no traceback. | `test_not_configured_is_shown_and_safe` | NOT_RUN |
| IA-B provider probe | With the config file, click "Kiểm tra môi trường". | Within ~1–2 min "Môi trường đã sẵn sàng."; info line shows model MedSAM2, version (commit), checkpoint, devices, GPU; GUI does not freeze while checking. | `test_configured_then_checked` | NOT_RUN |
| IA-C positive point from 2D | Cross tool → click inside the liver on Axial → "Điểm tại con trỏ 2D" (Thuộc vùng). | Green dot exactly at the crosshair on that slice only; label "Điểm: 1 thuộc vùng…"; appears on Coronal and Sagittal when scrolled to its slice. | geometry tests | NOT_RUN |
| IA-D negative point from 2D | Only if the worker declares negative points (`allow_negative_points`). Otherwise check that "Loại trừ" is disabled. | Red dot; or Loại trừ disabled. | `test_positive_only_provider_disables_negative` | NOT_RUN |
| IA-E 3D point | Visible surface → "Chọn điểm (3D)" → click it. | Point added at the picked surface position (boundary); tooltip explains the limitation. | `test_3d_pick_goes_through_view_to_slice` | NOT_RUN |
| IA-F bounding box | Corner 1 and corner 2 at the 2D cursor (two slices), then "Xóa hộp", then set again. | Cyan rectangle on every slice in range; ring while only one corner is set; Xóa hộp removes it. | `test_box_outline_in_each_orientation` | NOT_RUN |
| IA-G first preview | Set a box (two corners on the same slice, around the organ), or several positive points: one point alone gave an empty result on 0543. Click "Xem trước bằng AI". | Status shows stages; orange overlay on Axial/Coronal/Sagittal around the target; no new mask in the list; GUI responsive. | `test_prompt_preview_refine_cancel_accept` | NOT_RUN |
| IA-H E4 preview | Tick live 3D preview. | E4 source "Xem trước AI tương tác"; mesh matches the overlay. | same | NOT_RUN |
| IA-I positive refinement | Add a positive point in a missed part → "Cập nhật xem trước". | Preview replaced (not stacked); covers the missed part; still no mask. Record voxels and runtime A/B. | same | NOT_RUN |
| IA-J negative refinement | If supported: negative point in a false-positive area → update. | False-positive area removed. Record voxels and runtime C. | same | NOT_RUN |
| IA-K undo last prompt | "Hoàn tác điểm cuối". | Last marker gone; counts updated. | `test_undo_last_and_clear` | NOT_RUN |
| IA-L clear prompts | "Xóa gợi ý". | All markers gone; the preview (if any) stays. | same | NOT_RUN |
| IA-M Cancel Preview | Preview → Hủy. | Overlay and E4 candidate gone; prompts kept; button back to "Xem trước bằng AI"; no mask. | same | NOT_RUN |
| IA-N Accept exact candidate | Preview → Chấp nhận. | Exactly one new mask "AI - MedSAM2 1"; console "sha256=… (identical to the candidate)"; no AI run at Accept; overlay equals the mask. | same | NOT_RUN |
| IA-O Brush after Accept | Brush on the new mask, then Undo. | Normal behaviour. | (E3/brush suites) | NOT_RUN |
| IA-P Cleanup after Accept | Keep largest / fill holes. | Normal behaviour. | (E3 suites) | NOT_RUN |
| IA-Q final surface | "Cập nhật bề mặt 3D" on the new mask. | Surface created only when asked. | `test_surface_policy` | NOT_RUN |
| IA-R ROI Analysis | HU statistics / comparison / CSV / PDF on the new mask. | Same as any ROI; provenance AI. | (analysis suites) | NOT_RUN |
| IA-S Save/Open | Save project, close, reopen. | Accepted mask identical; AI off, no prompts, no preview. | – | NOT_RUN |
| IA-T project close during AI job | Close the project while "Đang chạy…". | No preview, no mask, no crash; worker process gone; no `roiviewer-iai-*` left in %TEMP%. | `test_project_close_during_inference` | NOT_RUN |
| IA-U plugin close/reopen | Close ROI Viewer during or after a job, then reopen. | Worker gone; reopen starts AI off; markers gone from the 2D views. | `test_plugin_close_during_inference` | NOT_RUN |
| IA-V TotalSegmentator unaffected | Choose TotalSegmentator; run a structure. | Same as before: structure list, no point/box controls, preview/accept unchanged. | `test_totalsegmentator_unaffected_by_the_interactive_provider` + E6b suites | NOT_RUN |
| IA-W classic workflow with AI OFF | AI unticked: Threshold, Otsu, Region Growing, Brush, Undo, E4, E5. | Unchanged. | full `tests/ct3d` | NOT_RUN |

**INTERACTIVE_AI_MANUAL_QA_COMPLETE: NO**: 0 PASS, 23 NOT_RUN.
