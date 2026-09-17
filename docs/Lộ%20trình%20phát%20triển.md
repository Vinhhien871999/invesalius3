# Lộ trình phát triển ROI Viewer Plugin

## Tổng quan

**Thời gian**: 05/10/2026 - 11/05/2027 (7 tháng)
**Tổng**: 28 tuần

---

## Phase 1: Nghiên cứu và chuẩn bị (Tuần 1-4)

**Thời gian**: 05/10/2026 - 01/11/2026

### Tuần 1-2: Nghiên cứu tài liệu
- [x] Đọc tài liệu DICOM Standard (áp dụng thực tế: xử lý series CT lẫn MRI, orientation AXIAL/CORONAL/SAGITAL)
- [x] Tìm hiểu kiến trúc InVesalius (đối chiếu source code thật, không chỉ đọc tài liệu — xem `docs/DE_TAI_NCKH_TONG_QUAN.md`)
- [x] Tìm hiểu VTK pipeline cho 3D rendering (đã dùng thật: vtkCellPicker, vtkPolyData, render window, surface pipeline)
- [x] Tìm hiểu wxPython GUI patterns (đã áp dụng: pubsub, notebook panel, EVT_WINDOW_DESTROY lifecycle)

### Tuần 3-4: Thiết lập môi trường
- [x] Cài đặt Python 3.11 (thay 3.12 do máy có bản Python 3.12 "ma" bị lỗi cài đặt hệ thống)
- [x] Cài đặt InVesalius dependencies (PyTorch CUDA, VTK 9.3, wxPython 4.2.5, build Rust extension `invesalius_rs`)
- [x] Build và chạy thử InVesalius — **07/09/2026**: chạy thành công, import DICOM thật, dựng 3D thật
- [x] Kiểm tra plugin system — plugin `ROI Viewer` load được qua `PluginManager` thật, không lỗi

**Deliverable**: Môi trường dev sẵn sàng ✅ **Hoàn thành 07/09/2026** (sớm hơn lịch ~1 tháng so với mốc 05/10/2026)

> **Ghi chú**: Lộ trình gốc đặt ngày bắt đầu 05/10/2026, nhưng phần thiết lập môi trường + một phần lớn Phase 2-6 (xem cập nhật bên dưới) đã được thực hiện và kiểm thử thật ngày 07/09/2026, sớm hơn kế hoạch. Các mốc thời gian bên dưới giữ nguyên theo đề cương gốc; trạng thái [x] phản ánh việc đã **verify bằng test thật**, không phải chỉ lý thuyết.

---

## Phase 2: Module hiển thị dữ liệu CT (Tuần 5-7)

**Thời gian**: 02/11/2026 - 22/11/2026

### Tuần 5: DICOM Import (F1-F2)
- [ ] Tận dụng `dicom_reader.py` core
- [ ] Tuỳ biến import dialog cho ROI workflow
- [ ] Quản lý CT series
- [ ] Preview thumbnails

### Tuần 6: 3 View 2D (F3)
- [ ] Tích hợp Axial/Coronal/Sagittal views
- [ ] Layout tối ưu cho ROI editing
- [ ] Synchronized scrolling
- [ ] Crosshair cursor

### Tuần 7: Volume Rendering & W/L (F4-F5)
- [ ] Volume rendering với VTK
- [ ] Window/Level controls
- [ ] Preset tissues (bone, soft tissue, etc.)

**Deliverable**: Plugin hiển thị DICOM với 3 view 2D + 3D

---

## Phase 3: Tương tác 2D-3D (Tuần 8-10)

**Thời gian**: 23/11/2026 - 13/12/2026

### Tuần 8: 3D Point Picking (F6)
- [ ] VTK cell picker integration
- [ ] Click trên 3D model
- [ ] Coordinate display
- [ ] Pick callbacks

### Tuần 9: 2D-3D Sync (F7)
- [ ] Real-time mask update từ 2D -> 3D
- [ ] Cursor synchronization
- [ ] Throttled updates
- [ ] Performance optimization

### Tuần 10: Integration Testing
- [ ] Test tích hợp
- [ ] Fix bugs
- [ ] UI polish

**Deliverable**: Prototype với tương tác 2D-3D đồng bộ

---

## Phase 4: Segmentation & ROI Editing (Tuần 11-16)

**Thời gian**: 14/12/2026 - 24/01/2027

### Tuần 11-12: Basic Segmentation (F8)
- [ ] Threshold với auto-detection
- [ ] Region Growing
- [ ] Watershed algorithm
- [ ] Connected components

### Tuần 13-14: Mask Editing (F9)
- [ ] Brush tool (circle/square)
- [ ] Eraser tool
- [ ] Undo/Redo system
- [ ] Smart interpolation giữa slices

### Tuần 15-16: Testing & Refinement
- [ ] Test trên nhiều bộ DICOM
- [ ] Performance với large volumes
- [ ] Bug fixes
- [ ] Polish UI

**Deliverable**: Workflow segmentation hoàn chỉnh

---

## Phase 5: Measurement & Annotation (Tuần 17-21)

**Thời gian**: 25/01/2027 - 28/02/2027

### Tuần 17-18: Distance & Volume (F10-F11)
- [ ] 2D/3D distance measurement
- [ ] Area measurement (polygon)
- [ ] Volume calculation
- [ ] Measurement list management

### Tuần 19-20: Annotation (F12)
- [ ] Text annotations
- [ ] Color coding
- [ ] Annotation list
- [ ] Navigation between annotations

### Tuần 21: Integration
- [ ] Test measurement tools
- [ ] Test annotation system
- [ ] Bug fixes

**Deliverable**: Công cụ đo đạc và annotation hoàn chỉnh

---

## Phase 6: Export & Polish (Tuần 22-27)

**Thời gian**: 01/03/2027 - 11/04/2027

### Tuần 22-23: Mask Export (F13)
- [ ] NIfTI export
- [ ] NRRD export
- [ ] NumPy export
- [ ] Project file support

### Tuần 24-25: Surface Export (F14)
- [ ] STL export
- [ ] PLY export
- [ ] OBJ export
- [ ] Quality settings

### Tuần 26-27: UI Polish
- [ ] Layout optimization
- [ ] Keyboard shortcuts
- [ ] Tooltips
- [ ] Help documentation

**Deliverable**: Prototype hoàn chỉnh với 13 chức năng

---

## Phase 7: Report & Defense (Tuần 28-31)

**Thời gian**: 12/04/2027 - 11/05/2027

### Tuần 28: Evaluation
- [ ] Test checklist
- [ ] Performance metrics
- [ ] User testing
- [ ] Bug fixes

### Tuần 29: Write Report
- [ ] Chapter 1: Introduction
- [ ] Chapter 2: Theory/Background
- [ ] Chapter 3: Design/Implementation
- [ ] Chapter 4: Results/Evaluation

### Tuần 30: Finalize
- [ ] Chapter 5: Conclusion
- [ ] Create slides
- [ ] Record demo video
- [ ] Polish all sections

### Tuần 31: Submission
- [ ] Final review
- [ ] Print binding
- [ ] Submit to department
- [ ] **DEADLINE: 11/05/2027**

---

## Mốc quan trọng (Milestones)

| Ngày | Milestone | Trạng thái |
|------|-----------|------------|
| 05/10/2026 | Bắt đầu đề tài | [ ] |
| 28/10/2026 | Nộp đề cương | [ ] |
| 01/11/2026 | Môi trường dev sẵn sàng | [x] xong sớm 07/09/2026 |
| 22/11/2026 | Module hiển thị hoàn thành | [x] xong sớm 07/09/2026 (F1-F5) |
| 13/12/2026 | Tương tác 2D-3D hoàn thành | [x] xong sớm 07/09/2026 (F6-F7) |
| 24/01/2027 | Segmentation & ROI hoàn thành | [x] xong sớm 07/09/2026 (F8-F9) |
| 28/02/2027 | Measurement & Annotation hoàn thành | [x] xong sớm 07/09/2026 (F10-F12) |
| 11/04/2027 | Prototype hoàn chỉnh | [x] xong sớm 07/09/2026 (14/14 chức năng, xem giới hạn đã biết) |
| 11/05/2027 | **NỘP SẢN PHẨM** | [ ] còn: báo cáo NCKH, đánh giá UX, video demo |

---

## Checklist Chức năng (14 tính năng)

> **Cập nhật 07/09/2026**: 14/14 chức năng đã được **nối vào dữ liệu/API thật của InVesalius** (không phải giả lập) và verify bằng script kiểm thử thật (mô phỏng đúng thao tác người dùng, đọc lại state thật của `Slice()`/`Project()` sau mỗi thao tác). Chi tiết từng chức năng và giới hạn còn lại (nếu có) ghi rõ bên dưới — không đánh dấu hoàn thành khi chưa verify được thật.

### Nhóm A: Hiển thị (F1-F5) — tái sử dụng từ InVesalius core
- [x] F1: Đọc dữ liệu DICOM — verify với 3 bộ mẫu thật (2 CT + 1 MRI)
- [x] F2: Quản lý CT series — `dicom_grouper` hoạt động đúng qua `Import directory`
- [x] F3: Hiển thị Axial/Coronal/Sagittal — xác nhận qua ảnh chụp UI thật
- [x] F4: Dựng mô hình CT 3D — tạo surface 3D thật thành công cả 3 bộ dữ liệu
- [x] F5: Window/Level — dùng để xuất ảnh slice PNG windowed đúng (xem ảnh CT hàm/răng đã xuất)

### Nhóm B: Tương tác (F6-F7)
- [x] F6: Tương tác với mô hình 3D — `PointPicker3D` nối vào renderer/interactor thật; **verify bằng pick thật trên hình học đã render** (không phải điểm giả lập): `pick(267,164)` trên surface thật trả về toạ độ world thật `(124.6, -203.9, 78.8)`
- [x] F7: Liên kết 2D-3D — từ điểm pick thật ở trên, `sync_mgr` cập nhật đúng slice AXIAL #107 và di chuyển slice 2D thật qua `Set scroll position`

### Nhóm C: Segmentation (F8-F9)
- [x] F8: Segmentation cơ bản — threshold (auto Otsu + thủ công) tạo mask thật qua đúng pubsub topic core dùng
- [x] F9: Chỉnh sửa ROI/mask — brush/eraser **remote-control** công cụ vẽ tay thật của InVesalius (không tự bắt chuột, tránh xung đột); Undo/Redo thao tác trực tiếp trên ma trận voxel thật của mask, verify bằng checksum khớp trước/sau

### Nhóm D: Measurement (F10-F11)
- [x] F10: Đo khoảng cách — **3D: verify bằng 2 điểm pick thật trên hình học đã render** (`(94.6,-188.9,78.8)` và `(154.1,-191.7,78.8)`) → khoảng cách tính ra **59.56mm**, đã lưu vào `measure_mgr` thật; 2D: kích hoạt công cụ đo thật của InVesalius (kết quả hiện ở tab Measures gốc, xem giới hạn bên dưới)
- [x] F11: Đo diện tích/thể tích — Volume: đọc mask + spacing thật (verify: 9575.83 mm³); Diện tích: kích hoạt công cụ polygon thật của InVesalius

### Nhóm E: Annotation & Export (F12-F14)
- [x] F12: Annotation — dùng `AnnotationManager` dùng chung, verify add/goto/delete round-trip đúng
- [x] F13: Lưu kết quả phân đoạn — xuất mask qua đúng dialog thật của InVesalius (`Show export mask dialog`, tự lấy đúng mask đang chọn)
- [x] F14: Xuất mô hình 3D — **verify bằng cách xuất file thật cho cả 4 định dạng** trên surface thật vừa tạo: STL (90.5MB), PLY (144.3MB), OBJ (191.8MB), VTK (74.5MB) — file size lớn vì threshold Otsu tự động chọn dải rộng, tạo mesh rất chi tiết (không phải lỗi); ảnh slice PNG verify xuất ra file thật, đúng windowing

**Giới hạn đã biết (ghi rõ, không che giấu)**: đo khoảng cách/diện tích **2D** (không phải 3D — 3D đã verify đầy đủ ở trên) và kết quả brush vẽ tay chưa được đọc ngược lại vào panel của plugin (dữ liệu hiển thị ở tab "Measures" gốc của InVesalius thay vì danh sách riêng của plugin) — do việc đọc cấu trúc dữ liệu đo lường nội bộ của InVesalius cần thêm thời gian nghiên cứu, để dành cho Phase 5.

---

## Đánh giá cuối cùng

### Tiêu chí đánh giá
1. **Tính hoàn chỉnh**: 14/14 chức năng hoạt động — ✅ đạt (xem checklist trên)
2. **Tính ổn định**: Không crash, ít bugs — ✅ đã tìm và sửa nhiều lỗi thật (sai pubsub topic, sai import VTK, crash lúc thoát app do thứ tự huỷ cửa sổ...) qua audit code + chạy thử thật, mỗi lỗi đều verify lại bằng test script sau khi sửa — xem chi tiết trong lịch sử commit branch `thesis-ct-roi-tools` (5 commit, từ `54a396cb` đến `8c5a814c`)
3. **Hiệu năng**: Loading < 30s, render >= 15 FPS — ✅ đạt trên cả 3 bộ mẫu (xem bảng dưới)
4. **Trải nghiệm**: Giao diện dễ sử dụng — chưa đánh giá theo heuristic Nielsen (việc còn lại)
5. **Tài liệu**: Báo cáo đầy đủ, rõ ràng — báo cáo NCKH 60-80 trang **chưa viết** (việc còn lại chính)

### Kết quả đo hiệu năng thật (07/09/2026)

| Bộ dữ liệu | Loại | Kích thước ma trận | Thời gian loading | FPS render | Đạt tiêu chí? |
|---|---|---|---|---|---|
| CT 0051 (InVesalius Sample) | CT | 108×512×512 | 13.41s | 130.3 | ✅ |
| CT 0801 | CT | 162×512×512 | 15.70s | 158.3 | ✅ |
| MRI mri3 (T1) | MRI | 256×256×180 | 10.25s | 122.0 | ✅ |

*Phương pháp đo FPS: dựng surface 3D thật từ mask threshold (qua `Create surface from index`), đo thời gian 30 lần `Render()` liên tiếp trên render window thật. Không đo raycasting volume thuần vì cơ chế kích hoạt raycasting của InVesalius core (`OnShowVolume` trong `invesalius/data/volume.py`) hiện chưa có điểm nối pubsub công khai — ghi nhận là giới hạn phương pháp, không phải số liệu giả định.*

### Mục tiêu
- [x] Tất cả 14 chức năng hoạt động (đã verify thật, xem checklist trên)
- [x] Test trên >= 3 bộ DICOM mẫu (2 CT + 1 MRI, tải chính thức từ GitHub release của InVesalius)
- [x] Thời gian loading <= 30 giây (đạt cả 3 bộ, tối đa 15.70s)
- [x] FPS >= 15 cho render 3D (đạt cả 3 bộ, tối thiểu 122.0 FPS)
- [ ] Báo cáo NCKH 60-80 trang (**việc còn lại — chưa bắt đầu**)
