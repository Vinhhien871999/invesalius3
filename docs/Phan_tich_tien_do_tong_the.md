# PHÂN TÍCH TỔNG THỂ TIẾN ĐỘ PHẦN MỀM
## InVesalius3 + Plugin ROI Viewer

> **Ngày phân tích**: 14/09/2026  
> **Trạng thái**: Sau Phase 10 (hoàn tất PASS)  
> **Branch**: `thesis-ct-roi-tools`  
> **Commit**: `0e51bcf9`

---

## BẢNG TÓM TẮT

| Nội dung đề cương | % hoàn thiện | Trạng thái |
|---|---|---|
| N1. Tổng quan lý thuyết | 0% | Chưa viết (việc luận văn) |
| N2. Quản lý/hiển thị CT | 81% | WORKING (cần test thêm vendor) |
| N3. Tái tạo & tương tác 3D | 54% | WORKING (raycasting hạn chế InVesalius gốc) |
| N4. Segmentation & ROI | 85% | WORKING (trọng tâm đề tài) |
| N5. Đo lường & Annotation | 81% | WORKING (chưa validate ground-truth) |
| N6a. UI/Save-Load/Export | ~90% | WORKING |
| N6b. Đánh giá phần mềm | **~15-20%** | **YẾU NHẤT** |

---

## 1. BỐI CẢNH DỰ ÁN

### 1.1 Giới thiệu
Đề tài **NCKH** xây dựng phần mềm hỗ trợ trực quan hóa và thao tác ảnh CT 3D, dựa trên nền tảng mã nguồn mở **InVesalius** (GPL v2).

### 1.2 Điểm xuất phát
- **InVesalius3**: Python + wxPython + VTK, kiến trúc pubsub (pypubsub)
- **Plugin ROI Viewer**: Module bổ sung với ~4700+ dòng code mới
- **Branch**: `thesis-ct-roi-tools` (fork từ `ca9aef76`)

### 1.3 Phương pháp làm việc
- **3 vòng audit kỹ thuật** (Phase 08, 09, 10)
- **0 tự bịa kết quả** — mọi WORKING đều có bằng chứng runtime thật
- **Script test chạy app thật** — không giả lập, đọc state thật từ `Slice()`/`Project()`
- **Xoá dead code** có bằng chứng (-841 dòng / +496 dòng, net -345)

---

## 2. TIẾN ĐỘ THEO 6 NỘI DUNG ĐỀ CƯƠNG

### 2.1 Nội dung 1 — Tổng quan lý thuyết (0%)

**Yêu cầu**: Tổng quan ảnh CT 3D, bảng so sánh phần mềm, cơ sở lý thuyết segmentation.

**Trạng thái**: **0% — hoàn toàn chưa làm, và đây KHÔNG PHẢI việc của phần mềm.**

Đây là phần **viết luận văn** (literature review), không có dòng code nào tương ứng để kiểm chứng runtime.

**Các bước cần làm**:
- [ ] Viết tổng quan nguyên lý CT 3D (Marching Cubes, ray casting, DICOM)
- [ ] Bảng so sánh InVesalius/3D Slicer/MITK/OsiriX/ITK-SNAP
- [ ] Cơ sở lý thuyết segmentation (đề tài đã chọn Threshold + Region Growing — lý do có trong `CT3D_ARCHITECTURE.md`)

---

### 2.2 Nội dung 2 — Quản lý và hiển thị dữ liệu CT (81%)

| Yêu cầu | Mã | Trạng thái | Bằng chứng |
|---|---|---|---|
| Đọc DICOM, dựng series | A1 | **WORKING** | Test thật 3 bộ dữ liệu, loading 10-16s |
| Đa vendor (Siemens/GE/Philips) | A2 | **NEEDS_RUNTIME_TEST** | Mới xác nhận 1/nhiều (SIEMENS) |
| Nhiều series trong 1 study | A4 | **NEEDS_RUNTIME_TEST** | Code InVesalius gốc, chưa test |
| Spacing/orientation đọc đúng | A3 | **WORKING** | 11/11 check, sai số <0.05mm |
| 3 view Axial/Coronal/Sagittal | B1 | **WORKING** | Ảnh chụp UI thật |
| Scroll slice đồng bộ | B2 | **WORKING** | Pick 3D → slice AXIAL đổi đúng |
| Window/Level | B3 | **WORKING** | Export PNG windowing đúng |
| Zoom/Pan 2D | B4 | **NEEDS_MANUAL_QA** | Cần thao tác chuột thật |

**Điểm mạnh**: Đọc DICOM + spacing chính xác, có số liệu thật.

**Điểm yếu**: Chỉ mới xác nhận 1 vendor (SIEMENS), chưa có GE/Philips/Canon — cần dataset TCIA/LIDC-IDRI.

---

### 2.3 Nội dung 3 — Tái tạo và tương tác mô hình 3D (54%)

| Yêu cầu | Mã | Trạng thái | Bằng chứng |
|---|---|---|---|
| Marching Cubes | C1 | **WORKING** | Extraction 0.1-0.3s, cleaning ~0.9s |
| Render 3D + FPS | C2 | **WORKING** | 122-158 FPS trên 3 bộ dữ liệu |
| Rotate/Pan/Zoom 3D | C3 | **NEEDS_MANUAL_QA** | Cần thao tác chuột thật |
| Pick điểm 3D | C4 | **WORKING** | Toạ độ world thật |
| Liên kết 3D→2D | C5 | **WORKING** | Pick → slice AXIAL nhảy đúng |
| Volume rendering raycasting | C6 | **NOT_CONNECTED** | 0 call-site `Volume.OnShowVolume()` |
| Rebuild mesh sau sửa mask | C7 | **WORKING** | Phase 08, 36/36 check |
| Sync 2D → 3D | C8 | **WORKING** | Phase 09, 8/8 check |

**Điểm mạnh**: Pick 3D → nhảy đúng 2D — đây chính là **"điểm mới"** theo hướng A đề cương gợi ý.

**Điểm yếu**: Raycasting thuần không hoạt động được (hạn chế của InVesalius gốc, không phải việc plugin sửa).

---

### 2.4 Nội dung 4 — Phân đoạn và chỉnh sửa ROI (85%) — TRỌNG TÂM

| Yêu cầu | Mã | Trạng thái | Bằng chứng |
|---|---|---|---|
| Threshold segmentation | D1 | **WORKING** | mask_dict tăng đúng |
| Auto-threshold Otsu | D2 | **WORKING** | Test 3 bộ dữ liệu |
| Chọn mask hiện tại | D3 | **WORKING** | `Slice().current_mask.index` khớp |
| Brush vẽ tay | D4 | **NEEDS_MANUAL_QA** | State chuyển đúng |
| Eraser | D5 | **NEEDS_MANUAL_QA** | State chuyển đúng |
| Kích thước brush | D6 | **WORKING** | Đổi không lỗi |
| Undo/Redo | D7 | **WORKING** | Checksum khớp, benchmark 27.36MB/checkpoint |
| Quản lý ROI List | D8 | **WORKING** | Cache/view `Project().mask_dict` thật |
| Mask → Surface 3D | D9 | **WORKING** | Phase 08, 36/36 check |
| Region Growing | D10 | **WORKING** | 30x speedup, 16.264.693 voxel |
| Watershed custom | D11 | **ĐÃ XOÁ** | Trùng InVesalius gốc |
| Morphology | D12 | **ĐÃ XOÁ** | 0 call-site |

**Điểm sáng nhất của đề tài**: **Region Growing bán tự động**
- BFS Python gốc: >15s (timeout)
- scipy.ndimage.label vector hoá: **~500ms (30 lần nhanh hơn)**
- Có validate seed, cảnh báo vùng >20% volume, thread-safety

---

### 2.5 Nội dung 5 — Đo lường và Annotation (81%)

| Yêu cầu | Mã | Trạng thái | Bằng chứng |
|---|---|---|---|
| Đo khoảng cách 3D | E1 | **WORKING** | 59.56mm |
| Đo khoảng cách 2D | E2 | **NEEDS_MANUAL_QA** | Cần thao tác chuột thật |
| Đo diện tích 2D | E3 | **NEEDS_MANUAL_QA** | Cần thao tác chuột thật |
| Đo thể tích mask | E4 | **WORKING** | Đã sửa bug đếm padding |
| Spacing thực áp dụng | E5 | **WORKING** | Dùng `Slice().spacing` |
| Thêm annotation | F1 | **WORKING** | count=1 |
| Goto/Edit/Delete | F2 | **WORKING** | Verify đầy đủ |
| Vị trí annotation chính xác | F3 | **WORKING** | Phase 09, 3/3 check |
| Lưu annotation | F4 | **WORKING** | Sidecar JSON |

**Điểm mạnh**: Annotation đầy đủ vòng đời + persistence.

**Điểm yếu**: Chưa validate độ chính xác phép đo với ground-truth.

---

### 2.6 Nội dung 6a — Giao diện và Save/Load/Export (~90%)

| Yêu cầu | Mã | Trạng thái | Bằng chứng |
|---|---|---|---|
| Save/Open project | G1 | **WORKING** | 30/30 test round-trip |
| Mask/Surface serialize | G2 | **WORKING** | Verify qua G1 |
| ROI List sau Open | G3 | **WORKING** | Tự rebuild |
| Export Mask | H1 | **WORKING** | NIfTI/NRRD/NumPy |
| Export STL/PLY/OBJ | H2-H4 | **WORKING** | File thật đọc lại được |
| Export VTK | H5 | **WORKING** | 74.5MB |
| Export ảnh slice | H6 | **WORKING** | PNG windowing đúng |
| Export DICOM-SEG | H7 | **MISSING** | Ngoài phạm vi |

---

### 2.7 Nội dung 6b — Đánh giá phần mềm (~15-20%) — YẾU NHẤT

| Yêu cầu | Trạng thái |
|---|---|
| Dataset thử nghiệm (LIDC-IDRI/TCIA) | **CHƯA CÓ** |
| Dice/Jaccard/Hausdorff | **CHƯA LÀM** |
| Độ chính xác đo lường | **CHƯA LÀM** |
| Hiệu năng hệ thống | **ĐÃ CÓ MỘT PHẦN** |
| Usability (SUS) | **CHƯA LÀM** |
| Bảng so sánh 3D Slicer | **CHƯA LÀM** |
| Unit test pytest | **CHƯA CÓ** |

**Đây là phần có tỷ lệ hoàn thành THẤP NHẤT** — theo chính đề cương tự nhận, đây là phần quyết định điểm số nhiều nhất.

---

## 3. CÁC PHASE ĐÃ HOÀN THÀNH

### Phase 08 — ROI3D Closure (`40c2c38b`)

**Mục tiêu**: Đóng dứt điểm D9 (mask sửa → surface 3D cập nhật).

**Phát hiện quan trọng**: Nguyên nhân gốc thật KHÁC với nghi ngờ ban đầu (không phải RAM/timing).
- `_on_update_surface()` hardcode `algorithm="Default"` → marching cubes đọc ẢNH GỐC thay vì MASK
- Đã sửa: chọn `algorithm="Binary"` khi `mask.was_edited=True`

**Kết quả**: 36/36 check PASS, 3 chu kỳ sửa mask liên tiếp, polydata đổi đúng.

**Gate**: PASS

---

### Phase 09 — Interaction QA (`d366a635`)

**Mục tiêu**: Runtime QA thao tác, Sync 2D→3D, F3 annotation.

**Đã thêm**:
- `CrosshairMarker3D` — marker 3D theo crosshair 2D
- Sync 2D→3D: tái sử dụng topic thật `"Set cross focal point"`, marker cập nhật đúng

**Đã sửa**:
- F3: Bỏ fallback `(0,0,0)`, từ chối + cảnh báo nếu không có vị trí
- Bug `project_loaded`: Plugin mở SAU project load bị vô hiệu hoá Sync

**Kết quả**: 28/28 check PASS (8 Sync, 5 F3, 15 regression).

**Gate**: PASS

---

### Phase 10 — Data Integrity (`0e51bcf9`)

**Mục tiêu**: Điều tra checksum Save/Open, đo + tối ưu Undo/Redo memory.

**Phát hiện**: "Checksum voxel lệch" → CASE A (không có bug thật)
- 30/30 test round-trip khớp byte-đối-byte
- Nguyên nhân cũ: lỗi phương pháp test (so sánh theo index thay vì theo tên/identity)

**Tối ưu**: Giảm `max_history` 20→10
- Before: worst case ~1.07GB (CT thật 109×513×513)
- After: worst case ~547MB (giảm ~50%)

**Kết quả**: 20/20 test Undo/Redo, 30/30 test Save/Open.

**Gate**: PASS

---

## 4. VIỆC CÒN LẠI

### Ưu tiên 1 — Manual QA (P1)

**7 mục cần thao tác chuột thật** (30-45 phút):

| Mã | Chức năng |
|---|---|
| P08.5 | D9/C7 qua dialog mặc định |
| B4 | Zoom/Pan 2D |
| C3 | Rotate/Pan/Zoom 3D |
| D4 | Brush vẽ tay |
| D5 | Eraser |
| E2 | Đo khoảng cách 2D |
| E3 | Đo diện tích 2D |

Checklist đầy đủ: `CT3D_P09_INTERACTION_QA_REPORT.md` mục 9.

---

### Ưu tiên 2 — Đánh giá phần mềm (P3)

**Đây là phần quan trọng nhất còn lại cho luận văn**.

| Việc | Dataset/Deadline |
|---|---|
| Dice/Jaccard/Hausdorff | Cần ground-truth từ TCIA/LIDC-IDRI |
| Usability (SUS score) | Cần tiếp cận bác sĩ/KTV thật |
| So sánh 3D Slicer | Khảo sát độc lập |
| Validate đo lường | Phantom hoặc baseline 3D Slicer |
| Unit test pytest | Thiết lập framework test |

---

### Ưu tiên 3 — Các mục nhỏ

| Việc | Trạng thái |
|---|---|
| Test đa vendor (GE/Philips/Canon) | Cần dataset ngoài |
| Export DICOM-SEG | Ngoài phạm vi (NIfTI đã đủ) |
| Dead code cleanup | `MaskEditor.draw_point_2d` |

---

## 5. GIÁ TRỊ ĐỀ TÀI ĐÃ THỂ HIỆN

### 5.1 Điểm mới rõ ràng nhất
- **Region Growing bán tự động** với 30x speedup (BFS → scipy vector hoá)
- **Liên kết 2D-3D thời gian thực** (Pick 3D → slice tự nhảy đúng)
- **Điểm mới theo hướng A đề cương** đề xuất

### 5.2 Đóng góp kiến trúc
- Phát hiện lazy-threshold sentinel bug (âm thầm ghi đè Region Growing)
- Sidecar JSON cho annotation (điều tra kỹ trước khi chọn giải pháp)
- ROIManager refactor thành cache/view (tránh 2 nguồn dữ liệu lệch nhau)

### 5.3 Bug thật đã sửa
- Dropdown Export Mask không có tác dụng
- Đo thể tích đếm nhầm padding
- Crash rò rỉ VTK observer khi đóng/mở plugin
- Crash `DensityMeasureStyle.CleanUp()` trong styles.py

### 5.4 Phương pháp làm việc
- 3 vòng audit kỹ thuật, 0 tự bịa kết quả
- Mọi WORKING đều có bằng chứng runtime thật
- Dọn dead code có bằng chứng (-345 dòng net)

---

## 6. THÔNG TIN HỆ THỐNG TÀI LIỆU

| File | Mô tả |
|---|---|
| `CT3D_MASTER_PROGRESS.md` | Ma trận tiến độ tổng thể |
| `CT3D_FEATURE_AUDIT.md` | Ma trận chức năng chi tiết |
| `CT3D_REMAINING_WORK.md` | Việc còn lại theo ưu tiên |
| `CT3D_CHANGELOG.md` | Lịch sử commit |
| `CT3D_ARCHITECTURE.md` | Kiến trúc thật |
| `CT3D_TEST_REPORT.md` | Báo cáo test runtime |
| `CT3D_P10_DATA_INTEGRITY_REPORT.md` | Phase 10 chi tiết |
| `CT3D_P09_INTERACTION_QA_REPORT.md` | Phase 09 chi tiết |
| `CT3D_P08_ROI3D_CLOSURE_REPORT.md` | Phase 08 chi tiết |
| `DANH_GIA_TIEN_DO_THEO_GIAI_DOAN.md` | Đánh giá % hoàn thiện |
| `ROI_VIEWER_USER_GUIDE_VERIFICATION.md` | Xác minh hướng dẫn |
| `HUONG_DAN_SU_DUNG_ROI_VIEWER.md` | Hướng dẫn sử dụng |

---

## 7. KẾT LUẬN

### 7.1 Trạng thái tổng thể
- **Phần code chức năng (N2-N5)**: 54-85%, phần lớn có bằng chứng runtime thật
- **Đã đóng dứt điểm các mục P1** qua 3 phase (08, 09, 10)
- **Phần yếu nhất**: Đánh giá phần mềm (N6b — ~15-20%)

### 7.2 Lộ trình tiếp theo
1. **Ngay lập tức**: Manual QA 7 mục (30-45 phút)
2. **Tiếp theo**: Thu thập dataset TCIA/LIDC-IDRI, tiếp cận bác sĩ/KTV
3. **Song song**: Viết Nội dung 1 (tổng quan lý thuyết luận văn)

### 7.3 Đánh giá cho buổi bảo vệ
Phần mềm đã thể hiện:
- **Điểm mới có số liệu**: Region Growing 30x speedup, liên kết 2D-3D đã verify
- **Phương pháp khoa học**: 3 vòng audit, 0 tự bịa, mọi WORKING có bằng chứng
- **Kiến trúc đúng đắn**: Remote-control qua pubsub, không phá InVesalius gốc

---

*Document generated: 14/09/2026*  
*Phase 10 complete — Next: Manual QA + Phần đánh giá luận văn*
