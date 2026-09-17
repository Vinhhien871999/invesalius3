# CT3D Master Progress

> Cập nhật sau MỖI phase (Phase 08 → 14). Nguồn dữ liệu: các `CT3D_PXX_*_REPORT.md`, đối chiếu với `CT3D_FEATURE_AUDIT.md`/`CT3D_REMAINING_WORK.md` (kết quả 3 vòng audit trước Phase 08).

## Current baseline

- **Current phase: 14 (FINAL — hoàn tất, PASS).** Đây là phase cuối của roadmap phần mềm (Phase 08→14). **KHÔNG có Phase 15.**
- Branch: `thesis-ct-roi-tools`
- HEAD: xem `CT3D_P14_FINAL_AUDIT_REPORT.md` mục Git cho commit hash chính xác (điền sau khi commit Phase 14 thật)
- Last completed phase: 14
- Next phase: **NONE.** Software roadmap complete. Remaining work is external research / clinical validation only (xem `CT3D_KNOWN_LIMITATIONS.md`, `CT3D_RELEASE_NOTES.md` mục 11) — không còn công việc kỹ thuật phần mềm nào cần Claude Code tiếp tục.

## Progress Matrix

| ID | Requirement | Status | Evidence | Last Verified Phase |
|---|---|---|---|---|
| A1 | Đọc DICOM, dựng series | WORKING | `CT3D_TEST_REPORT.md` — 3 bộ dữ liệu thật, loading 10-16s | Vòng 1 |
| A2 | Đa dạng vendor/modality | **PARTIAL** (nâng từ NEEDS_RUNTIME_TEST) | Phase 12: 2 vendor thật xác nhận (SIEMENS, Philips), 2 modality (CT, MR) — import thật end-to-end PASS cả 3 dataset local. Thiếu GE/Canon (`BLOCKED_EXTERNAL_DATA`) — xem `CT3D_DATASET_REGISTRY.md` | **Phase 12** |
| A3 | Spacing/orientation đúng | WORKING | `test_coordinate_roundtrip.py` 11/11, sai số <0.05mm | Vòng 2 |
| A4 | Nhiều series 1 study | NEEDS_RUNTIME_TEST (không đổi) | Code gốc. Phase 12: quét thật 3 dataset local — cả 3 chỉ 1 series/study (`BLOCKED_EXTERNAL_DATA`). Unit test logic grouping riêng (`tests/ct3d/test_dicom_grouping.py`, không thay bằng chứng runtime thật) | Phase 12 |
| B1 | 3 view Axial/Coronal/Sagittal | WORKING | Ảnh chụp UI thật | Vòng 1 |
| B2 | Scroll slice đồng bộ | WORKING | Pick 3D → slice AXIAL đổi đúng | Vòng 1 |
| B3 | Window/Level | WORKING | Export PNG windowing đúng | Vòng 1 |
| B4 | Zoom/Pan 2D | **WORKING** (Phase 13) | Manual QA thật PASS — zoom/pan đúng trên cả 3 khung 2D, xem `CT3D_MANUAL_QA_CHECKLIST.md` mục 2 | **Phase 13** |
| C1 | Marching Cubes | WORKING | Đo thật extraction/cleaning time | Vòng 1 |
| C2 | Render 3D + FPS | WORKING | 122-158 FPS, 3 bộ dữ liệu | Vòng 1 |
| C3 | Rotate/Pan/Zoom 3D | **WORKING** (Phase 13) | Manual QA thật PASS — camera xoay/zoom/pan đúng, surface không biến dạng, xem `CT3D_MANUAL_QA_CHECKLIST.md` mục 3 | **Phase 13** |
| C4 | Pick điểm 3D | WORKING | Toạ độ world thật từ `vtkCellPicker` | Vòng 1 |
| C5 | Liên kết 3D→2D | WORKING | Slice AXIAL tự nhảy đúng từ pick thật | Vòng 1 |
| C6 | Raycasting thuần | NOT_CONNECTED | 0 call-site `Volume.OnShowVolume()` trong toàn InVesalius gốc | Vòng 2 |
| C7 | Rebuild mesh sau sửa mask | **WORKING** (nâng từ PARTIAL) | `CT3D_P08_ROI3D_CLOSURE_REPORT.md` — polydata đổi đúng 3/3 chu kỳ | **Phase 08** |
| D1 | Threshold segmentation | WORKING | mask_dict tăng đúng | Vòng 1 |
| D2 | Auto-threshold Otsu | WORKING | Test 3 bộ dữ liệu | Vòng 1 |
| D3 | Chọn mask hiện tại | WORKING | `Slice().current_mask.index` khớp | Vòng 1 |
| D4 | Brush vẽ tay | **WORKING** (Phase 13) | Manual QA thật PASS — vẽ đúng vị trí, giữ nguyên qua đổi slice, không lệch toạ độ, xem `CT3D_MANUAL_QA_CHECKLIST.md` mục 4 | **Phase 13** |
| D5 | Eraser | **WORKING** (Phase 13) | Manual QA thật PASS — xoá đúng vùng kéo chuột, phần còn lại giữ nguyên, xem `CT3D_MANUAL_QA_CHECKLIST.md` mục 5 | **Phase 13** |
| D6 | Kích thước brush | WORKING | Đổi operation/shape/size không lỗi | Vòng 1 |
| D7 | Undo/Redo | **WORKING**, đã đo + tối ưu bộ nhớ | Checksum khớp trước/sau undo (Vòng 1). Phase 10: benchmark thật (27.36MB/checkpoint ở quy mô CT thật) → giảm `max_history` mặc định 20→10, verify 20/20 test (UR-T1..T9). **Sửa lại ở Phase 11**: Phase 10 tính worst case là `1.07GB → 547MB` (giả định 2 stack cùng đầy `max_history` một lúc) — invariant thật (chứng minh bằng test `test_undo_redo_memory_invariant_*`, 300+ chuỗi ngẫu nhiên + 6 chuỗi xác định) cho thấy tổng `len(undo_stack)+len(redo_stack)` KHÔNG BAO GIỜ vượt quá `max_history` (không phải `2×max_history`) — vì `save_state()` luôn xoá sạch `redo_stack` mỗi khi có nội dung mới. Worst case thật đúng: `10 × 27.36MB ≈ 273.6MB` (không phải 547MB — Phase 10 ước lượng cao gấp 2 lần). Quyết định `max_history=10` GIỮ NGUYÊN (vẫn hợp lý, chỉ số liệu justify được sửa đúng) | **Phase 10, sửa số liệu ở Phase 11** |
| D8 | Quản lý ROI List | WORKING | Cache/view đồng bộ 2 chiều thật | Vòng 2 |
| D9 | Mask sửa → Surface cập nhật | **WORKING** (nâng từ PARTIAL) | `CT3D_P08_ROI3D_CLOSURE_REPORT.md` — root cause `algorithm="Default"` tìm ra + sửa, verify runtime 36/36. + Phase 11: logic policy tách thành `choose_surface_algorithm()` (hàm thuần, hành vi giữ nguyên) + `tests/ct3d/test_surface_policy.py` (SP-T1/T2, persistent, unit). + **Phase 13**: real-GUI evidence (P08.5) — Brush/Eraser thật → "Update 3D Surface from Selected ROI" qua dialog thật, surface đổi đúng, xem `CT3D_MANUAL_QA_CHECKLIST.md` mục 1 | **Phase 08** |
| D10 | Region Growing an toàn | WORKING | 16/16 test thuật toán + mask thật 16.2M voxel. + Phase 11: `tests/ct3d/test_segmentation.py` (RG-U1..U8, persistent, unit). + **Phase 12**: full-volume CT thật (0051, 28.3M voxel) chạy lại có kiểm soát RAM — PASS thật (0.30s, 6.84M voxel output, RSS+28.5MB) — đóng dứt điểm item "treo ở vòng 3 do RAM thấp" | **Phase 12** |
| D11 | Watershed (custom) | ĐÃ XOÁ (quyết định kiến trúc) | Trùng Watershed thật InVesalius gốc | Vòng 2 |
| D12 | Morphology | ĐÃ XOÁ (quyết định kiến trúc) | 0 call-site, ngoài phạm vi | Vòng 2 |
| E1 | Đo khoảng cách 3D | WORKING | 59.56mm, verify thật | Vòng 1 |
| E2 | Đo khoảng cách 2D | **WORKING** (Phase 13) | Manual QA thật PASS — M1=143.951mm, M2=189.741mm, đúng chiều vật lý, xem `CT3D_MANUAL_QA_CHECKLIST.md` mục 6 | **Phase 13** |
| E3 | Đo diện tích 2D | **WORKING** (Phase 13) | Manual QA thật PASS — Sagittal=2674.851mm², Coronal=5367.750mm², đúng chiều vật lý, xem `CT3D_MANUAL_QA_CHECKLIST.md` mục 7 | **Phase 13** |
| E4 | Đo thể tích mask | WORKING | Đã sửa bug đếm nhầm padding (vòng 3). + Phase 11: `tests/ct3d/test_measurement.py` (M-U4, regression trực tiếp cho bug padding, persistent, unit) | Vòng 3 |
| E5 | Spacing thật áp dụng | WORKING | Dùng `Slice().spacing` trực tiếp | Vòng 1 |
| F1 | Thêm annotation | WORKING | add → count=1 | Vòng 1 |
| F2 | Goto/Edit/Delete/Prev-Next | WORKING | Verify đầy đủ vòng đời | Vòng 1 |
| F3 | Vị trí annotation chính xác | **WORKING** (nâng từ PARTIAL) | Phase 09: không còn fallback (0,0,0), từ chối + cảnh báo nếu không có vị trí hợp lệ, verify runtime 3/3 test | Phase 09 |
| F4 | Lưu annotation cùng project | WORKING | Sidecar JSON, full-cycle verify. + Phase 11: `tests/ct3d/test_annotation.py` (sidecar round-trip qua `tmp_path`, persistent, unit) | Vòng 2 |
| G1 | Save/Open project | **WORKING**, đã đóng dứt điểm phát hiện checksum | Full-cycle 19/20 PASS (Vòng 2). Phase 10: 30/30 test thật (5 kịch bản RT-A/B/C/D/E) — byte-identical mọi trường hợp; phát hiện checksum trước đó kết luận CASE A (không phải bug thật, nhiều khả năng là lỗi phương pháp test cũ so sánh mask theo index thay vì theo tên/identity — chứng minh cụ thể ở RT-E). + Phase 11: `tests/ct3d/test_serialization.py` (SER-T1..T3 + gzip/metadata, persistent, integration/slow — RT-A/B/C/E của Phase 10 chuyển thành pytest thật) | **Phase 10** |
| G2 | Mask/Surface serialize | WORKING | Verify qua G1 | Vòng 2 |
| G3 | ROI List sau Open | WORKING | Tự rebuild từ `mask_dict` thật | Vòng 2 |
| H1 | Export Mask | WORKING | Đã sửa bug dropdown format (vòng 3). + Phase 11: `tests/ct3d/test_exporters.py` (EX-T1 NumPy round-trip, persistent, integration) | Vòng 3 |
| H2-H4 | Export Surface STL/PLY/OBJ | WORKING | File thật, đọc lại được | Vòng 1 |
| H5 | Export Surface VTK | WORKING | File thật 74.5MB. + Phase 11: `tests/ct3d/test_exporters.py` (EX-T4, small synthetic mesh round-trip, persistent, integration) | Vòng 1 |
| H6 | Export ảnh slice | WORKING | PNG windowing đúng | Vòng 1 |
| H7 | Export DICOM-SEG | MISSING | Ngoài phạm vi đã triển khai | Vòng 1 |
| Sync 2D→3D (C8) | Checkbox đồng bộ ngược + mặt phẳng lát cắt trực quan | **WORKING** (nâng từ NOT_IMPLEMENTED) | Phase 09: tái sử dụng topic thật `"Set cross focal point"`, marker 3D thật cập nhật đúng, verify runtime 8/8 test (SYNC-T1..T6). + Phase 11: `tests/ct3d/test_sync_2d3d.py` (marker VTK thật không renderer trùng lặp, detach, enable/disable, F3 priority, persistent, integration). + **Phase 13.5 (16/09/2026)**: `core/slice_planes_3d.SlicePlanes3D` (3 mặt phẳng bán trong suốt, cùng event/cờ, không topic/timer mới) — 16 unit test (`test_slice_planes_3d.py`) + 9 integration test (`SYNC3D-T1..T9`) PASS thật. Checkbox `"Show slice planes in 3D"` mới, prerequisite native tool ghi rõ trong UI, không tự bật tool gốc, không cản pick 3D, không rebuild surface, không tự đổi camera. + **Phase 14 (17/09/2026, FINAL)**: người vận hành thật đã tự chạy 1 phiên smoke test core path — `C8_VISUAL_OPERATOR_SMOKE = PASS` (marker/mặt phẳng di chuyển đúng, surface không đổi hình học). 9 mục lettered A-I vẫn `NOT_EXPLICITLY_MANUAL_VERIFIED` (không phải FAIL — optional, xem `CT3D_REMAINING_WORK.md` mục 8) — xem `CT3D_MANUAL_QA_CHECKLIST.md` mục "C8 — Visual Sync 2D → 3D Slice Planes" | Phase 09, +Phase 13.5, +Phase 14 |
| Quantitative Metrics | Dice/Jaccard/Hausdorff (+HD95) | **WORKING** (hạ tầng + synthetic validation, mới ở Phase 12) | `core/evaluation.py` (thuần numpy/scipy, spacing anisotropic đúng — `spacing_zyx` tường minh, không mặc định trục). 42 test thật (`test_evaluation_metrics.py` 30, `test_phantom_validation.py` 12) — edge case empty/empty, empty/non-empty, shift-phantom khớp tuyệt đối công thức tay. **Ground-truth THẬT (không synthetic) vẫn `BLOCKED_EXTERNAL_DATA`** — chưa wire vào GUI (chỉ là module core/, đúng chỉ đạo không nhét research code vào GUI panel nếu chưa cần) | **Phase 12** |

## Critical blockers

- **Không có blocker nghiêm trọng nào đang mở sau Phase 14 (phase cuối).** Manual QA 7/7 PASS — `MANUAL_QA_COMPLETE = YES`. C8 core path có operator evidence thật (`C8_VISUAL_OPERATOR_SMOKE = PASS`) + 25/25 automated regression PASS. Blocker external còn lại (GE/Canon, real ground-truth, SUS participants, 3D Slicer comparison) đều `EXTERNAL_VALIDATION_GAP`/`BLOCKED_EXTERNAL_DATA`, không phải blocker kỹ thuật — xem `CT3D_KNOWN_LIMITATIONS.md`.

## High-priority remaining work

*(Đã đóng ở Phase 13: Manual QA thao tác chuột thật cho 7 mục — P08.5 (D9/C7), B4, C3, D4, D5, E2, E3 — 7/7 PASS thật, `MANUAL_QA_COMPLETE = YES`. Xem `CT3D_MANUAL_QA_CHECKLIST.md`, `CT3D_P13_PERFORMANCE_COMPARISON_REPORT.md` mục 4. Không còn mục high-priority nào đang mở.)*

## Medium-priority work

- Đánh giá `"ca_smoothing"` như lựa chọn thay thế mượt hơn `"Binary"` cho D9/C7 (không bắt buộc).

*(Đã đóng ở Phase 12: `MaskEditorManager.set_current_mask/get_current_editor/delete_editor` — xác nhận `CONFIRMED_DEAD_CODE` (0 call-site toàn repo), đã xoá. `global _roi_viewer_window` dư thừa ở 10 chỗ trong `main.py` — đã xoá, `pyflakes` sạch tuyệt đối cho toàn plugin. Xem `CT3D_P12_QUANTITATIVE_VALIDATION_REPORT.md` mục 5.)*

## Research/evaluation remaining work

> **Cập nhật Phase 12 (baseline reconciliation)**: mục "bộ pytest độc lập" từng liệt kê ở đây **đã đóng từ Phase 11** (`tests/ct3d/`, 158 test — xem `CT3D_P11_TEST_AUTOMATION_REPORT.md`) — đã xoá khỏi danh sách bên dưới, không còn để stale. Dice/Jaccard/Hausdorff **đã có hạ tầng thật + unit test synthetic đầy đủ ở Phase 12** (`plugins/roi_viewer/core/evaluation.py`, `tests/ct3d/test_evaluation_metrics.py`, `tests/ct3d/test_phantom_validation.py`) — không còn "hoàn toàn chưa thực hiện" như trước, nhưng **ground-truth THẬT (không phải synthetic) vẫn `BLOCKED_EXTERNAL_DATA`** (cần dataset có nhãn sẵn, ví dụ Medical Segmentation Decathlon — không có local). Đa vendor: **2/2 vendor thật xác nhận trong dữ liệu local hiện có** (SIEMENS, Philips — xem `CT3D_DATASET_REGISTRY.md`), GE/Canon vẫn `BLOCKED_EXTERNAL_DATA`.

- Ground-truth THẬT cho Dice/Jaccard/Hausdorff (cần dataset có nhãn, `BLOCKED_EXTERNAL_DATA`), người tham gia SUS thật (protocol đã sẵn sàng — `CT3D_SUS_PROTOCOL.md`, `SUS_PROTOCOL_READY=YES`/`SUS_REAL_PARTICIPANTS_COMPLETE=NO`), benchmark thật với 3D Slicer (không cài trên máy hiện tại — `NEEDS_EXTERNAL_VERIFICATION`, xem `CT3D_P13_PERFORMANCE_COMPARISON_REPORT.md` mục 17), GE/Canon (`BLOCKED_EXTERNAL_DATA`) — xem `Ke_hoach_de_tai_InVesalius_CT3D.md` mục 4 và `DANH_GIA_TIEN_DO_THEO_GIAI_DOAN.md` (Nội dung 6b) — dự kiến Phase 14+.

## Manual QA remaining

**7 mục gốc — 7/7 PASS (Phase 13, 16/09/2026, real mouse/GUI session).** P08.5 (D9/C7 qua dialog thật), B4, C3, D4, D5, E2, E3 — xem `CT3D_MANUAL_QA_CHECKLIST.md` cho evidence đầy đủ từng mục.

**C8 Visual Sync (mặt phẳng lát cắt 2D→3D, Phase 13.5/14)**: core path đã có `C8_VISUAL_OPERATOR_SMOKE = PASS` (Phase 14, real operator evidence). 9 mục lettered A-I (TEST A-I) vẫn `NOT_EXPLICITLY_MANUAL_VERIFIED` — optional, không phải blocker cho release candidate, xem `CT3D_MANUAL_QA_CHECKLIST.md` và `CT3D_REMAINING_WORK.md` mục 8.

## Out-of-scope items

- Watershed/Morphology custom trong plugin (D11/D12) — quyết định kiến trúc đã chốt, không làm lại.
- Volume rendering raycasting thuần (C6) — hạn chế của chính InVesalius gốc, không tự viết raycaster mới.
- Export DICOM-SEG (H7) — NIfTI đã đáp ứng yêu cầu tương tác cơ bản.

## Completed phase history

| Phase | Goal | Gate | Commit | Report |
|---|---|---|---|---|
| 08 | Đóng dứt điểm ROI → Surface 3D (D9/C7) | **PASS** | `40c2c38b` | `CT3D_P08_ROI3D_CLOSURE_REPORT.md` |
| 09 | Runtime Interaction QA & Bidirectional 2D-3D Sync | **PASS** | `d366a635` | `CT3D_P09_INTERACTION_QA_REPORT.md` |
| 10 | Data Integrity, Save/Open Forensics & Undo/Redo Memory | **PASS** | `0e51bcf9` | `CT3D_P10_DATA_INTEGRITY_REPORT.md` |
| 11 | Persistent Test & Regression Architecture + Code Hardening | **PASS** | `36dc59ba` | `CT3D_P11_TEST_AUTOMATION_REPORT.md` |
| 12 | Technical Closure & Quantitative Validation | **PASS** | `52004e28` | `CT3D_P12_QUANTITATIVE_VALIDATION_REPORT.md` |
| 13 | Manual-QA Closure, Performance, Comparison & Usability Preparation | **PASS** | `787fad80` | `CT3D_P13_PERFORMANCE_COMPARISON_REPORT.md` |
| 13.5 | Pre-Phase-14: Visual 2D→3D Slice Synchronization (mini-phase) | **PASS** | `3d070f7c` | `CT3D_P13_5_VISUAL_SYNC_REPORT.md` |
| 14 | Final Audit & Software Release Candidate (FINAL — KHÔNG có Phase 15) | **PASS** | `<điền sau commit Phase 14 — xem CT3D_P14_FINAL_AUDIT_REPORT.md>` | `CT3D_P14_FINAL_AUDIT_REPORT.md` |
