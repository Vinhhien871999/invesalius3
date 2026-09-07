# ĐỀ CƯƠNG NGHIÊN CỨU KHOA HỌC

## Tên đề tài (chính thức)

**"Nghiên cứu và xây dựng phần mềm hỗ trợ trực quan hóa và thao tác ảnh CT 3D tập trung vào chỉnh sửa vùng quan tâm (ROI)"**

## Tên đề tài (tiếng Anh)

*"Research and development of a software supporting 3D CT image visualization and interaction with focus on Region of Interest (ROI) editing"*

---

## 1. Tổng quan và lý do chọn đề tài

Trong y học hiện đại, ảnh CT 3D đóng vai trò then chốt trong chẩn đoán, lập kế hoạch phẫu thuật và theo dõi điều trị. Tuy nhiên, các phần mềm thương mại thường có chi phí cao và giao diện phức tạp. InVesalius là phần mềm mã nguồn mở (GPL) được phát triển bởi CTI Brazil, hỗ trợ đầy đủ tái tạo 3D từ DICOM nhưng **còn hạn chế về**: liên kết tương tác 2D-3D, chỉnh sửa ROI trực quan, annotation, và quy trình đo lường chuyên biệt.

Đề tài tập trung phát triển một **lớp chức năng mới** trên nền tảng InVesalius nhằm cung cấp công cụ ROI chuyên nghiệp cho bác sĩ và cán bộ kỹ thuật y tế.

---

## 2. Mục tiêu nghiên cứu

### 2.1 Mục tiêu tổng quát
Xây dựng prototype phần mềm trực quan hóa và tương tác ảnh CT 3D, phát triển dựa trên InVesalius, với trọng tâm là **trực quan hóa tương tác và chỉnh sửa vùng quan tâm (ROI)**.

### 2.2 Mục tiêu cụ thể
1. Tìm hiểu kiến trúc InVesalius (Python + wxPython + VTK 9.3)
2. Tái sử dụng các module có sẵn: DICOM reader, 2D/3D viewer, segmentation
3. Phát triển 06 nhóm chức năng mới (xem mục 5)
4. Đánh giá prototype với bộ dữ liệu CT thực tế
5. Hoàn thiện báo cáo NCKH

---

## 3. Đối tượng và phạm vi nghiên cứu

- **Đối tượng**: Ảnh CT 3D định dạng DICOM (.dcm), series Axial
- **Phạm vi**: Prototype desktop trên Windows, phát triển dưới dạng **plugin module** tích hợp vào InVesalius
- **Công nghệ nền tảng**: Python 3.12, wxPython 4.2, VTK 9.3, GDCM, scikit-image, numpy
- **Công cụ phát triển**: VSCode/Cursor, Git, pyproject.toml

---

## 4. Phương pháp nghiên cứu

### 4.1 Nghiên cứu tài liệu
- Tài liệu DICOM standard (NEMA)
- Source code InVesalius (đã có sẵn)
- Tài liệu VTK 9.3, wxPython
- Các bài báo về ROI segmentation, medical image annotation

### 4.2 Phương pháp phát triển
- **Fork InVesalius** + xây dựng plugin module riêng trong thư mục `plugins/roi_viewer/`
- Sử dụng pattern **Plugin** của InVesalius (`plugins.py` + `plugin.json`)
- Tích hợp với core thông qua **pubsub** (`from invesalius.pubsub import pub as Publisher`)

### 4.3 Phương pháp đánh giá
- Chạy thử trên bộ dữ liệu mẫu trong `invesalius3/samples/`
- Đánh giá chức năng theo checklist 14 tính năng
- So sánh thời gian thao tác với workflow thủ công

---

## 5. Nội dung nghiên cứu và chức năng prototype

### 5.1 Các chức năng tận dụng từ InVesalius (sẵn có - không phát triển)
| # | Chức năng | Module tham chiếu |
|---|-----------|-------------------|
| 1 | Đọc dữ liệu DICOM | `invesalius/reader/dicom_reader.py` |
| 2 | Quản lý CT series | `invesalius/reader/dicom_grouper.py` |
| 3 | Hiển thị Axial/Coronal/Sagittal | `invesalius/gui/task_slice.py` |
| 4 | Dựng mô hình CT 3D (volume rendering) | `invesalius/gui/task_surface.py` |
| 5 | Window/Level | `invesalius/gui/widgets/gradient.py` |

### 5.2 Các chức năng phát triển mới (điểm mới đề tài)

#### Nhóm A: Tương tác và liên kết 2D-3D
| # | Chức năng | Mô tả |
|---|-----------|-------|
| 6 | Tương tác với mô hình 3D | Click chọn điểm trên 3D -> đồng bộ cursor trên 3 view 2D |
| 7 | Liên kết 2D-3D | Brush vẽ trên 2D -> cập nhật mask 3D real-time |

#### Nhóm B: ROI/Mask chỉnh sửa nâng cao
| # | Chức năng | Mô tả |
|---|-----------|-------|
| 8 | Segmentation cơ bản | Threshold, region growing, watershed (nâng cấp từ core) |
| 9 | Chỉnh sửa ROI/mask | Brush/Eraser với nhiều kích thước, undo/redo, smart interpolation giữa các slice |

#### Nhóm C: Đo lường và Annotation
| # | Chức năng | Mô tả |
|---|-----------|-------|
| 10 | Đo khoảng cách | Đo giữa 2 điểm (3D Euclidean) |
| 11 | Đo diện tích/thể tích | Đo area polygon trên 2D, volume của mask 3D |
| 12 | Annotation | Gắn nhãn vùng quan tâm, lưu text note |

#### Nhóm D: Lưu trữ và xuất kết quả
| # | Chức năng | Mô tả |
|---|-----------|-------|
| 13 | Lưu kết quả phân đoạn | Lưu mask (.nii.gz, .nrrd, .stl) + project file (.inv3) |
| 14 | Xuất mô hình 3D | Xuất surface (.stl, .ply, .obj) |

---

## 6. Sản phẩm dự kiến

1. **Prototype phần mềm** ROI Viewer chạy được trên Windows, tích hợp vào InVesalius
2. **Mã nguồn** plugin trong `invesalius3/plugins/roi_viewer/`
3. **Báo cáo NCKH** (khoảng 60-80 trang) theo format khoa
4. **Slide thuyết trình** và poster (nếu yêu cầu)
5. **Video demo** các chức năng (5-10 phút)

---

## 7. Lộ trình và thời gian thực hiện

> **Tổng thời gian**: 05/10/2026 → 11/05/2027 (khoảng **28 tuần / 7 tháng**)

### Giai đoạn 1: Nghiên cứu và chuẩn bị (05/10/2026 - 01/11/2026) — 4 tuần

| Tuần | Nội dung | Sản phẩm |
|------|----------|----------|
| Tuần 1-2 (05/10-19/10) | Đọc tài liệu DICOM, tổng quan ảnh CT 3D, tìm hiểu kiến trúc InVesalius | Tài liệu tổng quan, sơ đồ kiến trúc |
| Tuần 3-4 (20/10-01/11) | Cài đặt môi trường Python 3.12 + wxPython + VTK, build InVesalius thành công | Môi trường dev sẵn sàng |

**Sản phẩm cuối giai đoạn**: Môi trường phát triển chạy được, hiểu kiến trúc core InVesalius

### Giai đoạn 2: Xây dựng module quản lý và hiển thị dữ liệu CT (02/11/2026 - 22/11/2026) — 3 tuần

| Tuần | Chức năng | Thời gian |
|------|-----------|-----------|
| Tuần 5 (02/11-08/11) | **F1. Đọc dữ liệu DICOM** + **F2. Quản lý CT series** (tận dụng core + tuỳ biến dialog) | 1 tuần |
| Tuần 6 (09/11-15/11) | **F3. Hiển thị Axial/Coronal/Sagittal** (tích hợp 3 view với layout mới) | 1 tuần |
| Tuần 7 (16/11-22/11) | **F4. Dựng mô hình CT 3D** (volume rendering) + **F5. Window/Level** | 1 tuần |

**Sản phẩm cuối giai đoạn**: Plugin hiển thị được DICOM với 3 view 2D + 3D, điều chỉnh W/L

### Giai đoạn 3: Tương tác mô hình 3D (23/11/2026 - 13/12/2026) — 3 tuần

| Tuần | Chức năng | Thời gian |
|------|-----------|-----------|
| Tuần 8 (23/11-29/11) | **F6. Tương tác với mô hình 3D** - Pick point trên 3D renderer, sync với 2D | 1 tuần |
| Tuần 9 (30/11-06/12) | **F7. Liên kết 2D-3D** - Brush vẽ mask trên 2D -> cập nhật surface 3D | 1 tuần |
| Tuần 10 (07/12-13/12) | Test tích hợp, fix bug | 1 tuần |

**Sản phẩm cuối giai đoạn**: Prototype có khả năng tương tác đồng bộ 2D-3D

### Giai đoạn 4: Phân đoạn và chỉnh sửa ROI (14/12/2026 - 24/01/2027) — 6 tuần

| Tuần | Chức năng | Thời gian |
|------|-----------|-----------|
| Tuần 11-12 (14/12-27/12) | **F8. Segmentation cơ bản** (threshold, region growing, watershed) | 2 tuần |
| Tuần 13-14 (28/12-10/01) | **F9. Chỉnh sửa ROI/mask** (brush/eraser nhiều size, undo/redo, interpolation) | 2 tuần |
| Tuần 15-16 (11/01-24/01) | Tích hợp F8+F9, test trên nhiều bộ dữ liệu | 2 tuần |

**Sản phẩm cuối giai đoạn**: Workflow segmentation hoàn chỉnh từ auto đến manual edit

### Giai đoạn 5: Đo lường và Annotation (25/01/2027 - 28/02/2027) — 5 tuần

| Tuần | Chức năng | Thời gian |
|------|-----------|-----------|
| Tuần 17-18 (25/01-07/02) | **F10. Đo khoảng cách** + **F11. Đo diện tích/thể tích** | 2 tuần |
| Tuần 19-20 (08/02-21/02) | **F12. Annotation** (text note, color tag, list view) | 2 tuần |
| Tuần 21 (22/02-28/02) | Test tích hợp đo lường + annotation | 1 tuần |

**Sản phẩm cuối giai đoạn**: Công cụ đo đạc và annotation hoạt động ổn định

### Giai đoạn 6: Lưu trữ, xuất kết quả và hoàn thiện UI (01/03/2027 - 11/04/2027) — 6 tuần

| Tuần | Chức năng | Thời gian |
|------|-----------|-----------|
| Tuần 22-23 (01/03-14/03) | **F13. Lưu kết quả phân đoạn** (.nii.gz, .nrrd, .inv3 project) | 2 tuần |
| Tuần 24-25 (15/03-28/03) | **F14. Xuất mô hình 3D** (.stl, .ply, .obj) | 2 tuần |
| Tuần 26-27 (29/03-11/04) | Hoàn thiện giao diện, polishing UI/UX, fix bug toàn diện | 2 tuần |

**Sản phẩm cuối giai đoạn**: Prototype hoàn chỉnh 14/14 chức năng

### Giai đoạn 7: Đánh giá, viết báo cáo và chuẩn bị bảo vệ (12/04/2027 - 11/05/2027) — 4 tuần

| Tuần | Nội dung | Sản phẩm |
|------|----------|----------|
| Tuần 28 (12/04-18/04) | Đánh giá chức năng theo checklist, đo thời gian thao tác | Bảng đánh giá |
| Tuần 29 (19/04-25/04) | Viết báo cáo NCKH (Chương 1-4) | Bản thảo báo cáo |
| Tuần 30 (26/04-02/05) | Viết Chương 5 (Kết luận), slide, demo video | Slide + video |
| Tuần 31 (03/05-11/05) | Hoàn thiện báo cáo, in ấn, nộp sản phẩm | **Sản phẩm hoàn chỉnh** |

---

## 8. Cấu trúc plugin đã xây dựng

```
invesalius3/plugins/roi_viewer/
├── plugin.json                   # Metadata
├── __init__.py
├── main.py                       # Entry point
├── SETUP.md                      # Hướng dẫn cài đặt
├── gui/
│   ├── __init__.py
│   ├── roi_panel.py              # Main ROI panel
│   ├── interaction_panel.py       # 2D-3D interaction tools
│   ├── measurement_panel.py      # Distance/area/volume
│   ├── annotation_panel.py       # Annotations
│   └── export_panel.py           # Export options
├── core/
│   ├── __init__.py
│   ├── roi_manager.py            # ROI management
│   ├── picker_3d.py              # 3D point picking
│   ├── sync_2d3d.py              # 2D-3D synchronization
│   ├── segmentation.py           # Segmentation algorithms
│   ├── mask_editor.py            # Mask editing
│   ├── measurement.py            # Measurements
│   ├── annotation.py              # Annotations
│   └── exporters.py               # Export functions
├── interface/
│   ├── __init__.py
│   ├── project_interface.py      # InVesalius project data
│   ├── view_interface.py          # Viewer controls
│   └── task_panel.py             # Task panel for sidebar
└── utils/
    ├── __init__.py
    └── helpers.py                 # Utility functions
```

---

## 9. Công nghệ và công cụ sử dụng

| Hạng mục | Công nghệ |
|----------|-----------|
| Ngôn ngữ | Python 3.12 |
| GUI Framework | wxPython 4.2.5 |
| Visualization | VTK 9.3.0 |
| DICOM | GDCM, pydicom |
| Xử lý ảnh | scikit-image, scipy, numpy |
| Build | uv, maturin (cho Rust extension) |
| Quản lý mã nguồn | Git + GitHub |
| IDE | VSCode / Cursor |

---

## 10. Kế hoạch đánh giá

| Tiêu chí | Phương pháp | Mục tiêu |
|----------|-------------|----------|
| Tính đúng đắn | Chạy trên 3 bộ DICOM mẫu | 100% chức năng chạy được |
| Tính tương thích | Test trên Windows 10/11 | Chạy mượt trên cả 2 |
| Hiệu năng | Volume ≤ 512³ voxels | Loading < 30s, render ≥ 15 FPS |
| UX | Tự đánh giá theo heuristic Nielsen | ≥ 7/10 điểm |

---

## 11. Kết quả kỳ vọng

1. **Về khoa học**: Đóng góp một plugin mã nguồn mở có thể cộng đồng y tế sử dụng
2. **Về thực tiễn**: Công cụ ROI hỗ trợ bác sĩ/chuyên viên y tế thao tác nhanh hơn 30-50% so với InVesalius mặc định
3. **Về học thuật**: 01 bài báo/báo cáo NCKH hoàn chỉnh

---

## 12. Tài liệu tham khảo (dự kiến)

1. InVesalius Documentation (https://github.com/invesalius/invesalius3)
2. DICOM Standard - NEMA (https://dicom.nema.org/)
3. VTK User's Guide (Kitware)
4. wxPython Documentation
5. Scikit-image Documentation
6. Các bài báo về ROI segmentation trong y tế (PubMed)

---

## Tóm tắt mốc thời gian

| Mốc | Ngày | Cột mốc |
|-----|------|---------|
| Bắt đầu | 05/10/2026 | Nhận nhiệm vụ, nghiên cứu |
| 28/10/2026 | Nộp đề cương | |
| 01/11/2026 | Hoàn thành môi trường dev | |
| 22/11/2026 | Xong module hiển thị DICOM | |
| 13/12/2026 | Xong tương tác 2D-3D | |
| 24/01/2027 | Xong segmentation + ROI edit | |
| 28/02/2027 | Xong đo lường + annotation | |
| 11/04/2027 | Hoàn thiện prototype 14 chức năng | |
| 11/05/2027 | **Nộp sản phẩm cuối** | |

---

## File quan trọng cần nghiên cứu trong InVesalius

- [invesalius3/invesalius/reader/dicom_reader.py](invesalius3/invesalius/reader/dicom_reader.py) - Đọc DICOM
- [invesalius3/invesalius/reader/dicom_grouper.py](invesalius3/invesalius/reader/dicom_grouper.py) - Nhóm series
- [invesalius3/invesalius/gui/task_slice.py](invesalius3/invesalius/gui/task_slice.py) - 3 view 2D
- [invesalius3/invesalius/gui/task_surface.py](invesalius3/invesalius/gui/task_surface.py) - 3D surface
- [invesalius3/invesalius/gui/widgets/gradient.py](invesalius3/invesalius/gui/widgets/gradient.py) - Window/Level
- [invesalius3/invesalius/plugins.py](invesalius3/invesalius/plugins.py) - Hệ thống plugin
- [invesalius3/plugins/mask_morphology/](invesalius3/plugins/mask_morphology/) - Plugin mẫu tham khảo

---

## Tài liệu đã tạo trong dự án

1. **Đề cương chi tiết**: [Lộ trình phát triển.md](Lộ%20trình%20phát%20triển.md)
2. **Tài liệu tổng quan**: [docs/DE_TAI_NCKH_TONG_QUAN.md](docs/DE_TAI_NCKH_TONG_QUAN.md)
3. **Hướng dẫn cài đặt**: [plugins/roi_viewer/SETUP.md](plugins/roi_viewer/SETUP.md)
4. **Mã nguồn plugin**: [plugins/roi_viewer/](plugins/roi_viewer/)
