# CT3D Master Progress

> Cập nhật sau MỖI phase (Phase 08 → 14). Nguồn dữ liệu: các `CT3D_PXX_*_REPORT.md`, đối chiếu với `CT3D_FEATURE_AUDIT.md`/`CT3D_REMAINING_WORK.md` (kết quả 3 vòng audit trước Phase 08).

## Current baseline

- Current phase: 10 (hoàn tất, PASS)
- Branch: `thesis-ct-roi-tools`
- HEAD: `0e51bcf9`
- Last completed phase: 10 — Data Integrity, Save/Open Forensics & Undo/Redo Memory
- Next phase: 11 — (chưa bắt đầu; xem "High-priority remaining work")

## Progress Matrix

| ID | Requirement | Status | Evidence | Last Verified Phase |
|---|---|---|---|---|
| A1 | Đọc DICOM, dựng series | WORKING | `CT3D_TEST_REPORT.md` — 3 bộ dữ liệu thật, loading 10-16s | Vòng 1 |
| A2 | Đa dạng vendor/modality | NEEDS_RUNTIME_TEST | 1 vendor thật xác nhận (SIEMENS), thiếu GE/Philips/Canon | Vòng 2 |
| A3 | Spacing/orientation đúng | WORKING | `test_coordinate_roundtrip.py` 11/11, sai số <0.05mm | Vòng 2 |
| A4 | Nhiều series 1 study | NEEDS_RUNTIME_TEST | Code gốc, chưa test dataset đa-series | Vòng 1 |
| B1 | 3 view Axial/Coronal/Sagittal | WORKING | Ảnh chụp UI thật | Vòng 1 |
| B2 | Scroll slice đồng bộ | WORKING | Pick 3D → slice AXIAL đổi đúng | Vòng 1 |
| B3 | Window/Level | WORKING | Export PNG windowing đúng | Vòng 1 |
| B4 | Zoom/Pan 2D | NEEDS_MANUAL_QA | Cần thao tác chuột thật, checklist ở `CT3D_P09_INTERACTION_QA_REPORT.md` mục 9 | Phase 09 |
| C1 | Marching Cubes | WORKING | Đo thật extraction/cleaning time | Vòng 1 |
| C2 | Render 3D + FPS | WORKING | 122-158 FPS, 3 bộ dữ liệu | Vòng 1 |
| C3 | Rotate/Pan/Zoom 3D | NEEDS_MANUAL_QA | Camera VTK gốc, cần thao tác chuột thật, checklist ở Phase 09 report | Phase 09 |
| C4 | Pick điểm 3D | WORKING | Toạ độ world thật từ `vtkCellPicker` | Vòng 1 |
| C5 | Liên kết 3D→2D | WORKING | Slice AXIAL tự nhảy đúng từ pick thật | Vòng 1 |
| C6 | Raycasting thuần | NOT_CONNECTED | 0 call-site `Volume.OnShowVolume()` trong toàn InVesalius gốc | Vòng 2 |
| C7 | Rebuild mesh sau sửa mask | **WORKING** (nâng từ PARTIAL) | `CT3D_P08_ROI3D_CLOSURE_REPORT.md` — polydata đổi đúng 3/3 chu kỳ | **Phase 08** |
| D1 | Threshold segmentation | WORKING | mask_dict tăng đúng | Vòng 1 |
| D2 | Auto-threshold Otsu | WORKING | Test 3 bộ dữ liệu | Vòng 1 |
| D3 | Chọn mask hiện tại | WORKING | `Slice().current_mask.index` khớp | Vòng 1 |
| D4 | Brush vẽ tay | NEEDS_MANUAL_QA | Chỉ verify state chuyển, cần thao tác chuột thật, checklist ở Phase 09 report | Phase 09 |
| D5 | Eraser | NEEDS_MANUAL_QA | Tương tự D4 | Phase 09 |
| D6 | Kích thước brush | WORKING | Đổi operation/shape/size không lỗi | Vòng 1 |
| D7 | Undo/Redo | **WORKING**, đã đo + tối ưu bộ nhớ | Checksum khớp trước/sau undo (Vòng 1). Phase 10: benchmark thật (27.36MB/checkpoint ở quy mô CT thật) → giảm `max_history` mặc định 20→10 (worst case 1.07GB → 547MB), verify 20/20 test (UR-T1..T9) | **Phase 10** |
| D8 | Quản lý ROI List | WORKING | Cache/view đồng bộ 2 chiều thật | Vòng 2 |
| D9 | Mask sửa → Surface cập nhật | **WORKING** (nâng từ PARTIAL) | `CT3D_P08_ROI3D_CLOSURE_REPORT.md` — root cause `algorithm="Default"` tìm ra + sửa, verify runtime 36/36 | **Phase 08** |
| D10 | Region Growing an toàn | WORKING | 16/16 test thuật toán + mask thật 16.2M voxel | Vòng 2 |
| D11 | Watershed (custom) | ĐÃ XOÁ (quyết định kiến trúc) | Trùng Watershed thật InVesalius gốc | Vòng 2 |
| D12 | Morphology | ĐÃ XOÁ (quyết định kiến trúc) | 0 call-site, ngoài phạm vi | Vòng 2 |
| E1 | Đo khoảng cách 3D | WORKING | 59.56mm, verify thật | Vòng 1 |
| E2 | Đo khoảng cách 2D | NEEDS_MANUAL_QA | Bật đúng style, cần test chuột thật, checklist ở Phase 09 report | Phase 09 |
| E3 | Đo diện tích 2D | NEEDS_MANUAL_QA | Tương tự E2 | Phase 09 |
| E4 | Đo thể tích mask | WORKING | Đã sửa bug đếm nhầm padding (vòng 3) | Vòng 3 |
| E5 | Spacing thật áp dụng | WORKING | Dùng `Slice().spacing` trực tiếp | Vòng 1 |
| F1 | Thêm annotation | WORKING | add → count=1 | Vòng 1 |
| F2 | Goto/Edit/Delete/Prev-Next | WORKING | Verify đầy đủ vòng đời | Vòng 1 |
| F3 | Vị trí annotation chính xác | **WORKING** (nâng từ PARTIAL) | Phase 09: không còn fallback (0,0,0), từ chối + cảnh báo nếu không có vị trí hợp lệ, verify runtime 3/3 test | Phase 09 |
| F4 | Lưu annotation cùng project | WORKING | Sidecar JSON, full-cycle verify | Vòng 2 |
| G1 | Save/Open project | **WORKING**, đã đóng dứt điểm phát hiện checksum | Full-cycle 19/20 PASS (Vòng 2). Phase 10: 30/30 test thật (5 kịch bản RT-A/B/C/D/E) — byte-identical mọi trường hợp; phát hiện checksum trước đó kết luận CASE A (không phải bug thật, nhiều khả năng là lỗi phương pháp test cũ so sánh mask theo index thay vì theo tên/identity — chứng minh cụ thể ở RT-E) | **Phase 10** |
| G2 | Mask/Surface serialize | WORKING | Verify qua G1 | Vòng 2 |
| G3 | ROI List sau Open | WORKING | Tự rebuild từ `mask_dict` thật | Vòng 2 |
| H1 | Export Mask | WORKING | Đã sửa bug dropdown format (vòng 3) | Vòng 3 |
| H2-H4 | Export Surface STL/PLY/OBJ | WORKING | File thật, đọc lại được | Vòng 1 |
| H5 | Export Surface VTK | WORKING | File thật 74.5MB | Vòng 1 |
| H6 | Export ảnh slice | WORKING | PNG windowing đúng | Vòng 1 |
| H7 | Export DICOM-SEG | MISSING | Ngoài phạm vi đã triển khai | Vòng 1 |
| Sync 2D→3D | Checkbox đồng bộ ngược | **WORKING** (nâng từ NOT_IMPLEMENTED) | Phase 09: tái sử dụng topic thật `"Set cross focal point"`, marker 3D thật cập nhật đúng, verify runtime 8/8 test (SYNC-T1..T6) | Phase 09 |

## Critical blockers

- Không có blocker nghiêm trọng nào đang mở sau Phase 10.

## High-priority remaining work

1. **Manual QA thao tác chuột thật** cho 7 mục: P08.5 (D9/C7), B4, C3, D4, D5, E2, E3 — checklist đầy đủ ở `CT3D_P09_INTERACTION_QA_REPORT.md` mục 9.

## Medium-priority work

- Đánh giá `"ca_smoothing"` như lựa chọn thay thế mượt hơn `"Binary"` cho D9/C7 (không bắt buộc).
- `MaskEditor.draw_point_2d/draw_point_3d/interpolate_slices` là dead code (brush thật dùng `SLICE_STATE_EDITOR` gốc) — phát hiện ở Phase 10, chưa dọn (ngoài phạm vi phase đó).

## Research/evaluation remaining work

- Dice/Jaccard/Hausdorff, đa vendor CT đầy đủ, khảo sát Usability (SUS), bảng so sánh với 3D Slicer, bộ `pytest` độc lập — xem `Ke_hoach_de_tai_InVesalius_CT3D.md` mục 4 và `DANH_GIA_TIEN_DO_THEO_GIAI_DOAN.md` (Nội dung 6b, ~15-20% hoàn thiện, phần yếu nhất của đề tài theo chính đề cương tự đánh giá) — dự kiến Phase 11-13.

## Manual QA remaining

- 7 mục: P08.5 (D9/C7 qua dialog mặc định), B4, C3, D4, D5, E2, E3 — checklist đầy đủ ở `CT3D_P09_INTERACTION_QA_REPORT.md` mục 9.

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
