# Ma trận chức năng — InVesalius CT 3D + Plugin ROI Viewer

> Cập nhật: 08/09/2026. Mỗi dòng chỉ ghi **WORKING** khi đã chứng minh bằng test thật (script chạy app thật + đọc lại state thật của `Slice()`/`Project()`, không phải chỉ đọc source). Bằng chứng chi tiết ở `CT3D_TEST_REPORT.md`. Tên file/class lấy nguyên văn từ source thật, đã đối chiếu bằng `grep` trực tiếp trong repo, không dùng tên giả định từ tài liệu kế hoạch.

**Trạng thái**: WORKING / PARTIAL / UI_ONLY / BACKEND_ONLY / NOT_CONNECTED / BROKEN / MISSING / DUPLICATE / DEAD_CODE / NEEDS_RUNTIME_TEST

---

## A. DICOM / dữ liệu CT

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| A1 | Đọc DICOM, dựng series | `invesalius/reader/dicom_reader.py` (LoadDicom), `dicom_grouper.py` | ✓ (menu Import) | ✓ | `"Import directory"` | ✓ | **WORKING** | Test thật với 3 bộ mẫu (2 CT + 1 MRI, GitHub release chính thức InVesalius). Loading 10.25–15.70s, đều < mục tiêu 30s |
| A2 | Đa dạng vendor/modality | như trên | — | — | — | ✓ | **WORKING** (giới hạn) | Đã test CT 0051, CT 0801, MRI mri3. Chưa test Siemens/GE/Philips cụ thể — dataset dùng là InVesalius sample, không rõ vendor gốc |
| A3 | Spacing/orientation đọc đúng | `invesalius/data/slice_.py` (`Slice.spacing`) | — | ✓ | — | ✓ | **WORKING** | Verify qua đo lường thật: volume 9575.83 mm³, khoảng cách 3D 59.56mm — số hợp lý, không lệch bậc độ lớn |
| A4 | Nhiều series trong 1 study | `dicom_grouper.py` (DicomGrouper) | ✓ | ✓ | — | NEEDS_RUNTIME_TEST | **NEEDS_RUNTIME_TEST** | Code tồn tại (InVesalius gốc), chưa test thật với dataset đa-series trong phiên này |

## B. Hiển thị 2D (Axial/Coronal/Sagittal)

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| B1 | 3 view Axial/Coronal/Sagittal | `invesalius/data/viewer_slice.py` (Viewer) | ✓ | ✓ | — | ✓ | **WORKING** | Verify bằng ảnh chụp UI thật (nhiều lần trong phiên) |
| B2 | Scroll slice, đồng bộ | `viewer_slice.py`, `("Set scroll position", plane)` | ✓ | ✓ | ✓ | ✓ | **WORKING** | Plugin verify: pick 3D → sync_mgr → `Set scroll position` → slice AXIAL đổi đúng (test thật, không giả lập) |
| B3 | Window/Level | `invesalius/data/slice_.py`, `"Update window level value"` | ✓ | ✓ | ✓ | ✓ | **WORKING** | Verify qua export PNG: ảnh CT hàm/răng xuất ra đúng windowing thật |
| B4 | Zoom/Pan 2D | `viewer_slice.py` interactor styles | ✓ | ✓ | — | NEEDS_RUNTIME_TEST | **NEEDS_RUNTIME_TEST** | Tính năng InVesalius gốc, không phải trọng tâm plugin, chưa test riêng trong phiên |

## C. Tái tạo & tương tác 3D

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| C1 | Marching Cubes (vtkContourFilter) | `invesalius/data/surface.py` (SurfaceManager) | ✓ | ✓ | `"Create surface from index"` → `"Create surface"` | ✓ | **WORKING** | Đo thật: Extraction ~0.1-0.3s/nhóm lát, Cleaning merged surface ~0.9s cho mesh ~900K điểm |
| C2 | Volume/Surface hiển thị 3D | `invesalius/data/viewer_volume.py` (Viewer) | ✓ | ✓ | `"Load surface actor into viewer"` | ✓ | **WORKING** | Render FPS đo thật: 122.0–158.3 FPS (3 bộ dữ liệu), vượt mục tiêu ≥15 FPS |
| C3 | Rotate/Zoom/Pan 3D (camera VTK) | `viewer_volume.py` | ✓ | ✓ | — | NEEDS_RUNTIME_TEST | **NEEDS_RUNTIME_TEST** | Camera/interactor VTK chuẩn của InVesalius, không viết lại, chưa test tương tác chuột thật trong phiên tự động hoá |
| C4 | Pick điểm 3D trên hình học thật | `plugins/roi_viewer/core/picker_3d.py` (PointPicker3D), `gui/interaction_panel.py` | ✓ | ✓ | — (VTK observer trực tiếp) | ✓ | **WORKING** | Verify bằng `vtkCellPicker.Pick()` thật trên surface đã render: toạ độ world thật `(124.6,-203.9,78.8)` |
| C5 | Liên kết 3D→2D (crosshair) | `interaction_panel.py._on_point_picked` → `sync_mgr` → `"Set scroll position"` | ✓ | ✓ | ✓ | ✓ | **WORKING** | Từ điểm pick thật ở C4, slice AXIAL tự nhảy đến #107 (verify thật) |
| C6 | Volume rendering (raycasting) thuần | `invesalius/data/volume.py` (Volume class) | (task panel gốc) | ✓ | `"Load raycasting preset"`, `"Update raycasting preset"` | — | **NOT_CONNECTED** (từ plugin) | `Volume.OnShowVolume()` — hàm thật duy nhất khởi tạo raycasting lần đầu — **không có nơi nào trong code gọi tới nó** (`grep` xác nhận 0 lời gọi ngoài định nghĩa). Plugin đo FPS trên **surface rendering**, không phải raycasting thuần — ghi rõ trong `CT3D_TEST_REPORT.md`, không báo nhầm |
| C7 | Rebuild mesh sau khi sửa mask (surface update) | `segmentation_panel.py._on_update_surface` → `"Create surface from index"` | ✓ | ✓ | ✓ | ✓ (một phần) | **PARTIAL** | Xem mục D9 — cùng cơ chế, cùng kết luận |

## D. Segmentation / ROI — TRỌNG TÂM ĐỀ TÀI

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| D1 | Threshold segmentation | `segmentation_panel.py._on_apply_threshold` → `"Create new mask"` | ✓ | ✓ | ✓ | ✓ | **WORKING** | Verify: mask_dict count tăng đúng, mask thật xuất hiện trong Project() |
| D2 | Auto-threshold Otsu | `core/segmentation.py.auto_threshold_otsu` | ✓ | ✓ | (nội bộ, không cần pubsub) | ✓ | **WORKING** | Test trên cả 3 bộ dữ liệu, cho ngưỡng hợp lý theo từng volume |
| D3 | Chọn mask hiện tại | `segmentation_panel.py._on_roi_selected` → `"Change mask selected"` | ✓ | ✓ | ✓ | ✓ | **WORKING** | Verify: `Slice().current_mask.index` khớp đúng ROI vừa chọn |
| D4 | Brush vẽ tay | `SLICE_STATE_EDITOR` remote-control | ✓ | ✓ (InVesalius gốc) | ✓ | ✓ (state transition) | **WORKING** (giới hạn) | Verify: `Slice().state` chuyển đúng 3008↔1000. **Thao tác rê chuột vẽ thật vẫn phải làm thủ công trên canvas 2D** — không tự động hoá được, đã ghi rõ |
| D5 | Eraser | cùng cơ chế D4, `operation=BRUSH_ERASE` | ✓ | ✓ | ✓ | ✓ (state) | **WORKING** (giới hạn như D4) | |
| D6 | Kích thước brush | `"Set edition brush size"` | ✓ | ✓ | ✓ | ✓ | **WORKING** | Verify: đổi operation/shape/size không raise exception |
| D7 | Undo/Redo (thao tác mask) | `core/mask_editor.py` (UndoRedoManager), `segmentation_panel.py._on_undo/_on_redo` | ✓ | ✓ | (thao tác trực tiếp `mask.matrix`) | ✓ | **WORKING** | Verify: sửa mask → checksum đổi → undo → checksum khớp y hệt ban đầu (7108638==7108638) |
| D8 | Quản lý nhiều mask (ROI List) | `core/roi_manager.py` (ROIManager) + `segmentation_panel.py` ROI List | ✓ | ✓ | ✓ | ✓ | **WORKING** | **Trước phiên này: code tồn tại, `.clear()` là lời gọi DUY NHẤT, hoàn toàn chưa nối UI (DEAD_CODE)**. Đã nối: chọn/đổi tên/ẩn-hiện/xoá, verify 100% qua `Project().GetMask().name`, `.is_shown`, `mask_dict` count |
| D9 | Mask sửa → Surface 3D cập nhật | `segmentation_panel.py._on_update_surface` | ✓ | ✓ | ✓ | ✓ (một phần) | **PARTIAL** | `invesalius/data/surface.py` xác nhận **không subscribe bất kỳ topic sửa-mask nào** — hành vi thật của InVesalius gốc, không tự động. Nút "Update 3D Surface" đóng vòng lặp này thủ công. **Đã verify chuỗi UI→pubsub→backend đúng 100%** (chặn `Publisher.sendMessage` trực tiếp: xác nhận gửi đúng topic `"Create surface from index"`, đúng `mask_index` thật, đúng `overwrite=True`, `sendMessage` trả về bình thường, không exception). **Chưa verify được bước cuối** ("người dùng thấy kết quả") trong khung thời gian test tự động (thử tới 75s): với mask threshold cỡ thường (bước tạo surface lần đầu, ~900K điểm) rebuild chạy nhanh (vài giây, có log Extraction/Joining/Cleaning thật — xem `CT3D_TEST_REPORT.md`); nhưng với mask region-growing rất lớn (16,2 triệu voxel ≈ 58% cả volume — do tolerance test chọn quá rộng, không phải giá trị thực tế) thì **không thấy log Extraction mới nào xuất hiện dù đã chờ 75s**, kể cả khi build cho mask CHƯA từng có surface (loại trừ khả năng do "overwrite"). Nghi vấn hiệu năng Marching Cubes với mesh cực phức tạp/nhiều mảnh rời — cần verify thủ công qua GUI với mask kích thước hợp lý, xem `CT3D_REMAINING_WORK.md` |
| D10 | Region Growing (bán tự động, seed-based) | `core/segmentation.py.region_growing`, `segmentation_panel.py._on_toggle_pick_seed/_on_seed_picked` | ✓ | ✓ | ✓ | ✓ | **WORKING** | **Trước phiên này: thuật toán đã viết (BFS Python thuần) nhưng hoàn toàn chưa được gọi (DEAD_CODE)**. Đã nối UI (pick seed 3D → grow → tạo mask thật), verify: 16.264.693 voxel thật, mask thật trong `mask_dict`. **Đã tối ưu**: thay BFS Python (>15s, timeout) bằng `scipy.ndimage.label` vector hoá (500ms, tương đương toán học, 6-connectivity) |
| D11 | Watershed | `core/segmentation.py.watershed/_simple_watershed` | — | ✓ | — | — | **BACKEND_ONLY / DEAD_CODE** | Có code (dùng `skimage.segmentation.watershed`) nhưng **chưa nối UI trong plugin**. InVesalius gốc CÓ Watershed thật riêng (`SLICE_STATE_WATERSHED`, `invesalius/data/styles.py`), độc lập với plugin — người dùng vẫn dùng được qua UI gốc InVesalius, task_slice.py |
| D12 | Morphology (dilate/erode/open/close, remove small, fill holes) | `core/segmentation.py` | — | ✓ | — | — | **BACKEND_ONLY / DEAD_CODE** | Code tồn tại, đúng, không import lỗi — chưa có nút UI gọi tới. Ưu tiên thấp (P2/P3), không phải yêu cầu cốt lõi của đề tài |

## E. Đo lường (Measurement)

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| E1 | Đo khoảng cách 3D | `core/measurement.py` (MeasurementManager), `measurement_panel.py` | ✓ | ✓ | (dùng picker thật) | ✓ | **WORKING** | Verify: 2 điểm pick thật → 59.56mm, lưu đúng vào manager |
| E2 | Đo khoảng cách 2D | `STATE_MEASURE_DISTANCE` remote-control | ✓ | ✓ (InVesalius gốc) | ✓ | ✓ (state) | **PARTIAL** | State chuyển đúng (1007). **Kết quả hiện ở tab Measures gốc InVesalius, chưa đọc ngược vào panel plugin** — giới hạn đã ghi rõ |
| E3 | Đo diện tích (2D polygon) | `STATE_MEASURE_DENSITY_POLYGON` remote-control | ✓ | ✓ (InVesalius gốc) | ✓ | ✓ (state) | **PARTIAL** | Tương tự E2 |
| E4 | Đo thể tích mask | `core/measurement.py.calculate_volume` (voxel_count × spacing) | ✓ | ✓ | — | ✓ | **WORKING** | Verify: 9575.83 mm³ (không tính theo pixel đơn thuần, có nhân spacing thật) |
| E5 | Spacing thực từ DICOM áp dụng đúng | `ProjectInterface.get_spacing()` | — | ✓ | — | ✓ | **WORKING** | Dùng trực tiếp `Slice().spacing`, đã verify qua kết quả E1/E4 hợp lý |

## F. Annotation

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| F1 | Thêm ghi chú tại vị trí | `core/annotation.py` (AnnotationManager), `annotation_panel.py` | ✓ | ✓ | — | ✓ | **WORKING** | Verify: add → count=1 |
| F2 | Go to / Edit / Delete / Prev-Next | `annotation_panel.py` | ✓ | ✓ | ✓ (goto dùng `Set scroll position`) | ✓ | **WORKING** | Verify: goto không raise, delete → count về 0 |
| F3 | Vị trí annotation chính xác | `annotation_panel.py._on_add_annotation` | ✓ | ✓ | — | ✓ (giới hạn) | **PARTIAL** | Lấy từ điểm pick 3D gần nhất — nếu chưa pick lần nào, mặc định `(0,0,0)`. Đã ghi rõ trong hướng dẫn sử dụng |
| F4 | Lưu annotation cùng project (.inv3) | — | — | — | — | ❌ | **MISSING** | `AnnotationManager` là state **thuần Python trong bộ nhớ plugin**, KHÔNG serialize vào `.inv3`. Đóng/mở lại project sẽ MẤT toàn bộ annotation. Xem `CT3D_REMAINING_WORK.md` |

## G. Project Save/Load

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| G1 | Save/Open project (.inv3) — InVesalius gốc | `invesalius/project.py`, `export_panel.py` (Save/Save As remote-control) | ✓ | ✓ | `"Show save dialog"` | NEEDS_RUNTIME_TEST | **NEEDS_RUNTIME_TEST** | Nút Save/Save As gọi đúng dialog gốc InVesalius (đã verify topic tồn tại + đúng subscriber qua grep), nhưng **chưa test full-cycle save→close→open→so sánh state** trong phiên này |
| G2 | Mask/Surface được InVesalius gốc serialize | `invesalius/project.py` | — | ✓ | — | — | **WORKING** (kế thừa) | Cơ chế gốc InVesalius, mask/surface tạo qua plugin là mask/surface THẬT nên đã tự động nằm trong luồng save/load gốc — không cần code thêm |
| G3 | ROI List (tên/màu/hiển thị riêng của plugin) khi load lại | `core/roi_manager.py` | — | — | — | ❌ | **MISSING** | Giống F4 — `ROIManager` là state trong bộ nhớ, không serialize. Sau khi mở lại project, mask vẫn còn (nhờ G2) nhưng **danh sách ROI List của plugin sẽ trống, phải build lại thủ công** |

## H. Export

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| H1 | Export Mask (NIfTI) | `export_panel.py._export_mask_to_file` → `"Show export mask dialog"` / `"Export masks to nifti"` | ✓ | ✓ | ✓ | ✓ | **WORKING** | Verify bằng cách gọi thẳng `"Export masks to nifti"` (bypass dialog modal): file .nii.gz thật, 1.901.372 voxel thật, đọc lại bằng `nibabel` thành công |
| H2 | Export Surface — STL Binary/ASCII | `export_panel.py._export_surface_to_file` → `"Export surface to file"` | ✓ | ✓ | ✓ | ✓ | **WORKING** | File thật 90.5MB, đọc lại xác nhận có vertex/face |
| H3 | Export Surface — PLY | như trên | ✓ | ✓ | ✓ | ✓ | **WORKING** | File thật 144.3MB |
| H4 | Export Surface — OBJ | như trên | ✓ | ✓ | ✓ | ✓ | **WORKING** | File thật 191.8MB (kèm .mtl) |
| H5 | Export Surface — VTK PolyData | `core/exporters.py.export_surface_vtk` (tự triển khai, không qua InVesalius gốc vì gốc không hỗ trợ .vtk cho export dialog) | ✓ | ✓ | — (trực tiếp VTK writer) | ✓ | **WORKING** | File thật 74.5MB. **Lưu ý**: định dạng KHÔNG có trong danh sách export gốc của InVesalius — plugin tự thêm bằng `vtkPolyDataWriter`, đã sửa lỗi dùng nhầm `vtkPolyLine` (khung dây) thay vì `vtkTriangle` (mặt tam giác) |
| H6 | Export ảnh slice (PNG/JPG/TIFF/BMP) | `export_panel.py._export_image_to_file` | ✓ | ✓ | — | ✓ | **WORKING** | File PNG thật, windowing đúng (verify bằng ảnh CT hàm/răng) |
| H7 | Export DICOM-SEG | — | — | — | — | ❌ | **MISSING** | Ngoài phạm vi đã triển khai — NIfTI đã đáp ứng yêu cầu tương tác với phần mềm y tế khác |

## I. Kiến trúc/Hạ tầng chung

| ID | Chức năng | File/Class | Trạng thái | Ghi chú |
|---|---|---|---|---|
| I1 | Plugin load qua PluginManager | `invesalius/plugins.py`, `plugins/roi_viewer/plugin.json` | **WORKING** | Verify qua `find_plugins()` + `Load plugin` thật |
| I2 | Mở lại plugin nhiều lần không rò rỉ | `main.py.load()`, `roi_panel.py` EVT_CLOSE | **WORKING** (đã sửa bug thật) | Phát hiện qua sử dụng thực tế của người dùng: observer VTK rò rỉ khi đóng/mở lại → crash `TextCtrl has been deleted`. Đã sửa 3 lớp, verify 9/9 test |
| I3 | Không có `except:` trần nuốt lỗi | toàn bộ `plugins/roi_viewer/` | **WORKING** (đã sửa) | Tìm thấy 5 chỗ `except:` trần trong `interface/project_interface.py`, đã sửa thành `except Exception as e: print(...)` |
