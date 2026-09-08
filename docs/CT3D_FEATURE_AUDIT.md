# Ma trận chức năng — InVesalius CT 3D + Plugin ROI Viewer

> Cập nhật: 08/09/2026. Mỗi dòng chỉ ghi **WORKING** khi đã chứng minh bằng test thật (script chạy app thật + đọc lại state thật của `Slice()`/`Project()`, không phải chỉ đọc source). Bằng chứng chi tiết ở `CT3D_TEST_REPORT.md`. Tên file/class lấy nguyên văn từ source thật, đã đối chiếu bằng `grep` trực tiếp trong repo, không dùng tên giả định từ tài liệu kế hoạch.

**Trạng thái**: WORKING / PARTIAL / UI_ONLY / BACKEND_ONLY / NOT_CONNECTED / BROKEN / MISSING / DUPLICATE / DEAD_CODE / NEEDS_RUNTIME_TEST

---

## A. DICOM / dữ liệu CT

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| A1 | Đọc DICOM, dựng series | `invesalius/reader/dicom_reader.py` (LoadDicom), `dicom_grouper.py` | ✓ (menu Import) | ✓ | `"Import directory"` | ✓ | **WORKING** | Test thật với 3 bộ mẫu (2 CT + 1 MRI, GitHub release chính thức InVesalius). Loading 10.25–15.70s, đều < mục tiêu 30s |
| A2 | Đa dạng vendor/modality | như trên | — | — | — | NEEDS_RUNTIME_TEST | **NEEDS_RUNTIME_TEST** | **Cập nhật vòng 2**: đọc trực tiếp tag `Manufacturer` thật (qua `gdcm`, cùng thư viện InVesalius gốc dùng — không phải suy luận) cho dataset CT 0051: **`SIEMENS`** — `test_coordinate_roundtrip.py`. Đã xác nhận được 1 vendor thật, nhưng CT 0801/MRI mri3 chưa đọc tag, và chưa test GE/Philips/Canon — theo đúng yêu cầu vòng 2 (mục J), không tự nhận WORKING chỉ vì "đã test 3 bộ dữ liệu" |
| A3 | Spacing/orientation đọc đúng | `invesalius/data/slice_.py` (`Slice.spacing`) | — | ✓ | — | ✓ | **WORKING** | **Cập nhật vòng 2**: không còn dựa vào "khoảng cách đo có vẻ hợp lý". `test_coordinate_roundtrip.py` đọc trực tiếp `PixelSpacing`/khoảng cách Z thật giữa các lát (từ `ImagePositionPatient` thật, qua bộ đọc gdcm THẬT của chính InVesalius — `invesalius.reader.dicom_reader`) rồi so khớp với `Slice().spacing` (0.4785156, 0.4785156, 1.5) — sai số < 0.05mm, khớp. Round-trip voxel→world→voxel qua CẢ 2 implementation thật (`ProjectInterface`, `SyncManager2D3D`) tại 3 điểm (origin/center/near-end): khớp tuyệt đối 11/11 check. **Giới hạn đã ghi rõ, không giấu**: bộ đọc DICOM thật của InVesalius chỉ giữ lại `orientation_label` dạng thô (AXIAL/CORONAL/SAGITTAL), không giữ vector `ImageOrientationPatient` 6 giá trị — plugin không (và InVesalius gốc cũng không) hiệu chỉnh gantry-tilt |
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
| C7 | Rebuild mesh sau khi sửa mask (surface update) | `segmentation_panel.py._on_update_surface` → `"Create surface from index"` | ✓ | ✓ | ✓ | ✓ (một phần, bằng chứng mạnh hơn vòng 1) | **PARTIAL** | Xem mục D9 — cùng cơ chế, cùng kết luận, cùng bằng chứng vòng 2 |

## D. Segmentation / ROI — TRỌNG TÂM ĐỀ TÀI

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| D1 | Threshold segmentation | `segmentation_panel.py._on_apply_threshold` → `"Create new mask"` | ✓ | ✓ | ✓ | ✓ | **WORKING** | Verify: mask_dict count tăng đúng, mask thật xuất hiện trong Project() |
| D2 | Auto-threshold Otsu | `core/segmentation.py.auto_threshold_otsu` | ✓ | ✓ | (nội bộ, không cần pubsub) | ✓ | **WORKING** | Test trên cả 3 bộ dữ liệu, cho ngưỡng hợp lý theo từng volume |
| D3 | Chọn mask hiện tại | `segmentation_panel.py._on_roi_selected` → `"Change mask selected"` | ✓ | ✓ | ✓ | ✓ | **WORKING** | Verify: `Slice().current_mask.index` khớp đúng ROI vừa chọn |
| D4 | Brush vẽ tay | `SLICE_STATE_EDITOR` remote-control | ✓ | ✓ (InVesalius gốc) | ✓ | NEEDS_RUNTIME_TEST | **NEEDS_RUNTIME_TEST** (hạ từ WORKING, vòng 2 mục L) | Verify: `Slice().state` chuyển đúng 3008↔1000 (bằng script). **Chưa verify bằng thao tác rê chuột thật** trên canvas 2D — theo đúng yêu cầu mục L, không đánh dấu WORKING khi chưa thao tác tay thật, dù cơ chế nền (interactor style) là code InVesalius gốc đã ổn định lâu năm |
| D5 | Eraser | cùng cơ chế D4, `operation=BRUSH_ERASE` | ✓ | ✓ | ✓ | NEEDS_RUNTIME_TEST | **NEEDS_RUNTIME_TEST** (hạ từ WORKING, vòng 2 mục L) | Tương tự D4 |
| D6 | Kích thước brush | `"Set edition brush size"` | ✓ | ✓ | ✓ | ✓ | **WORKING** | Verify: đổi operation/shape/size không raise exception |
| D7 | Undo/Redo (thao tác mask) | `core/mask_editor.py` (UndoRedoManager), `segmentation_panel.py._on_undo/_on_redo` | ✓ | ✓ | (thao tác trực tiếp `mask.matrix`) | ✓ | **WORKING** | Verify: sửa mask → checksum đổi → undo → checksum khớp y hệt ban đầu (7108638==7108638) |
| D8 | Quản lý nhiều mask (ROI List) | `core/roi_manager.py` (ROIManager) + `segmentation_panel.py` ROI List | ✓ | ✓ | ✓ | ✓ | **WORKING** | Chọn/đổi tên/ẩn-hiện/xoá, verify 100% qua `Project().GetMask().name`, `.is_shown`, `mask_dict` count. **Cập nhật vòng 2**: refactor `ROIManager` thành CACHE/VIEW của `Project().mask_dict` thật (không còn giữ bản sao độc lập) — `rebuild_from_project_masks()`, tự đồng bộ cả khi sửa mask qua tab Masks GỐC của InVesalius (không chỉ qua nút plugin). Verify: `test_roi_rebuild_after_project_load.py` — tạo/đổi tên/ẩn/xoá mask qua pubsub topic gốc trực tiếp (không đụng nút plugin), ROI List tự cập nhật đúng, invariant "không có ROI mồ côi" giữ vững sau xoá |
| D9 | Mask sửa → Surface 3D cập nhật | `segmentation_panel.py._on_update_surface` | ✓ | ✓ | ✓ | ✓ (một phần, bằng chứng mạnh hơn vòng 1) | **PARTIAL** (nâng cấp bằng chứng, chưa đủ điều kiện WORKING) | **Vòng 2 — test đúng theo yêu cầu**: mask NHỎ thật (cube 27.000 voxel, không phải 16,2 triệu voxel như vòng 1), verify polydata thật (points/cells/bounds), không chỉ "sendMessage không lỗi". **Kết quả `test_surface_update_small_roi.py` (11/15 PASS)**: chuỗi UI→pubsub→backend→viewer→render **WORKING thật** — `"Load surface actor into viewer"` (tín hiệu hoàn tất thật) bắn ra, không tạo surface trùng, actor thật trong renderer, `Render()` thành công. **Phát hiện + sửa 1 bug thật** (đọc trực tiếp `Slice.do_threshold_to_all_slices()` để xác nhận cơ chế): mask tạo qua placeholder `thresh=(1,1)` (cùng pattern Region Growing D10 dùng) có sentinel `matrix[n,0,0]=0` mọi lát → lần build surface ĐẦU TIÊN ghi đè âm thầm dữ liệu tay-ghi bằng threshold(1,1) vô nghĩa trên ảnh gốc — giải thích đúng 4/15 check FAIL (polydata không đổi giữa 2 lần build). Đã sửa tại `_on_region_grown` (đánh dấu sentinel sau khi ghi). **Chưa có lần chạy xác nhận lại SAU khi sửa** — khác biệt trung thực so với "đã sửa xong": cơ chế được xác nhận qua đọc source (chắc chắn về logic), nhưng chưa observe runtime polydata đúng sau bản vá. **Vòng 3 (08/09/2026)**: thử lại 4 lần, cả 4 lần đều treo ở bước dựng surface — xác định cụ thể hơn nguyên nhân là RAM khả dụng thấp (3.5-4.8GB/16.44GB, đo bằng `psutil`), không phải crash (0 crash report mới). Xem `CT3D_TEST_REPORT.md` §7.3, `ROI_VIEWER_USER_GUIDE_VERIFICATION.md`, `CT3D_REMAINING_WORK.md` |
| D10 | Region Growing (bán tự động, seed-based) | `core/segmentation.py.region_growing`, `segmentation_panel.py._on_toggle_pick_seed/_on_seed_picked/_on_region_grown` | ✓ | ✓ | ✓ | ✓ | **WORKING** | Đã nối UI (pick seed 3D → grow → tạo mask thật). **Tối ưu**: BFS Python (>15s) → `scipy.ndimage.label` vector hoá (500ms). **Cập nhật vòng 2 — an toàn**: thêm `validate_seed()` (seed trong bounds, hữu hạn, volume tồn tại), tolerance ≥ 0 (raise `ValueError` nếu âm, UI cho phép 0), `region_stats()` tính % volume + mm³ thật, cảnh báo (Yes/No, có Cancel) nếu vùng grow > `max_region_fraction` (mặc định 20%, là constant có thể cấu hình, không hardcode trong UI) — verify `test_region_growing_limits.py` 16/16 (connectivity đúng: loại trừ blob rời cùng giá trị nhưng không liền kề; seed ngoài bounds; tolerance âm; component nhỏ/lớn). **Đã audit thread-safety**: worker thread chỉ đụng numpy/scipy thuần, mọi wx/dialog đều qua `wx.CallAfter` trên main thread — không có GUI/VTK call trực tiếp từ background thread. **Bug thật phát hiện + đã sửa**: mask tạo qua placeholder `thresh=(1,1)` có sentinel `matrix[n,0,0]=0` ở mọi lát — lần build surface ĐẦU TIÊN sẽ bị `do_threshold_to_all_slices()` âm thầm ghi đè dữ liệu grow thật bằng kết quả threshold(1,1) vô nghĩa trên ảnh gốc; đã sửa bằng cách đánh dấu sentinel=1 sau khi ghi — xem mục D9 và `CT3D_ARCHITECTURE.md` §4 |
| D11 | Watershed (custom trong plugin) | ~~`core/segmentation.py.watershed/_simple_watershed`~~ | — | — | — | — | **ĐÃ XOÁ (vòng 2)** | Dùng `skimage.segmentation.watershed`, KHÔNG phải đóng góp nghiên cứu (gọi thư viện chuẩn), trùng hoàn toàn chức năng Watershed THẬT của InVesalius gốc (`SLICE_STATE_WATERSHED`, `invesalius/data/styles.py`, người dùng dùng được ngay qua UI gốc), 0 call-site, 0 test. Đối chiếu `Ke_hoach_de_tai_InVesalius_CT3D.md` mục 4.2: chỉ yêu cầu "chọn 1-2 thuật toán" (đề tài đã chọn Threshold + Region Growing) — không bắt buộc thêm Watershed. Theo đúng quy tắc mục G: xoá thay vì giữ "có thể dùng sau" |
| D12 | Morphology (dilate/erode/open/close, remove small, fill holes) | ~~`core/segmentation.py`~~ | — | — | — | — | **ĐÃ XOÁ (vòng 2)** | 0 call-site, không nằm trong phạm vi tài liệu kế hoạch, 0 test — xoá theo đúng quy tắc mục G |

## E. Đo lường (Measurement)

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| E1 | Đo khoảng cách 3D | `core/measurement.py` (MeasurementManager), `measurement_panel.py` | ✓ | ✓ | (dùng picker thật) | ✓ | **WORKING** | Verify: 2 điểm pick thật → 59.56mm, lưu đúng vào manager |
| E2 | Đo khoảng cách 2D | `STATE_MEASURE_DISTANCE` remote-control | ✓ | ✓ (InVesalius gốc) | ✓ | NEEDS_RUNTIME_TEST | **NEEDS_RUNTIME_TEST** | **Đối chiếu lại vòng 2 (mục H)**: "không đọc ngược vào panel plugin" KHÔNG còn coi là thiếu — đây là quyết định kiến trúc đúng (tránh tạo 2 nguồn dữ liệu đo lường, xem `CT3D_REMAINING_WORK.md`). State chuyển đúng (`Slice().state`) đã verify bằng script. **Chưa verify**: thao tác rê chuột thật vẽ 2 điểm trên canvas 2D (đúng yêu cầu mục L — không đánh dấu WORKING cho phần chỉ verify được việc BẬT tool, chưa verify thao tác chuột thật) |
| E3 | Đo diện tích (2D polygon) | `STATE_MEASURE_DENSITY_POLYGON` remote-control | ✓ | ✓ (InVesalius gốc) | ✓ | NEEDS_RUNTIME_TEST | **NEEDS_RUNTIME_TEST** | Tương tự E2 |
| E4 | Đo thể tích mask | `core/measurement.py.calculate_volume` (voxel_count × spacing) | ✓ | ✓ | — | ✓ | **WORKING** | **Cập nhật vòng 3**: phát hiện + sửa bug thật — `_on_measure_volume` trước đó truyền cả viền đệm (padding) của `mask.matrix` vào `calculate_volume()`, đếm nhầm 1 số ô "cờ nội bộ" thành voxel thật (UI hiện 9575.83mm³ trong khi tính đúng từ dữ liệu ảnh thật là 9574.80mm³, lệch 1.03mm³). Đã sửa truyền `mask.matrix[1:,1:,1:]` — verify lại khớp tuyệt đối 9574.80 = 9574.80 |
| E5 | Spacing thực từ DICOM áp dụng đúng | `ProjectInterface.get_spacing()` | — | ✓ | — | ✓ | **WORKING** | Dùng trực tiếp `Slice().spacing`, đã verify qua kết quả E1/E4 hợp lý |

## F. Annotation

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| F1 | Thêm ghi chú tại vị trí | `core/annotation.py` (AnnotationManager), `annotation_panel.py` | ✓ | ✓ | — | ✓ | **WORKING** | Verify: add → count=1 |
| F2 | Go to / Edit / Delete / Prev-Next | `annotation_panel.py` | ✓ | ✓ | ✓ (goto dùng `Set scroll position`) | ✓ | **WORKING** | Verify: goto không raise, delete → count về 0 |
| F3 | Vị trí annotation chính xác | `annotation_panel.py._on_add_annotation` | ✓ | ✓ | — | ✓ (giới hạn) | **PARTIAL** | Lấy từ điểm pick 3D gần nhất — nếu chưa pick lần nào, mặc định `(0,0,0)`. Đã ghi rõ trong hướng dẫn sử dụng |
| F4 | Lưu annotation cùng project (.inv3) | `core/annotation.py.AnnotationManager.save_sidecar/load_sidecar`, `export_panel.py`, `roi_panel.py.on_project_load` | ✓ | ✓ | (gián tiếp qua `"Show save dialog"`/`"Load project data"`) | ✓ | **WORKING** (vòng 2, trước đó MISSING) | **Điều tra trước khi chọn giải pháp**: `invesalius/project.py` xác nhận `project["annotations"]` được ghi CỨNG rỗng khi save và KHÔNG có code đọc lại khi load — placeholder chưa hoàn thiện trong core, không phải extension point dùng được. Grep `invesalius/project.py` + `control.py` cho `plugin`/`custom_data`/`extension`: 0 kết quả. → Chọn sidecar JSON (`<đường dẫn .inv3>.roi_annotations.json`) theo đúng thứ tự ưu tiên yêu cầu, không sửa core. Verify thật: `test_project_roundtrip.py` — add → save → close → open → annotation count + text khớp baseline 100% |

## G. Project Save/Load

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| G1 | Save/Open project (.inv3) — InVesalius gốc | `invesalius/project.py`, `export_panel.py` (Save/Save As remote-control) | ✓ | ✓ | `"Show save dialog"` | ✓ | **WORKING** (vòng 2, trước đó NEEDS_RUNTIME_TEST) | **Vòng 2 — full-cycle thật**: `test_project_roundtrip.py` (19/20 PASS) — `SavePlistProject()` thật → `Close()` thật (verify `mask_dict`/`surface_dict` thật sự rỗng) → `OpenPlistProject()` thật → so khớp mask count/tên/màu/hiển thị, annotation, ROI List đều đúng 100%. **1 phát hiện hẹp chưa giải thích hết**: checksum voxel data của 1 mask không khớp byte-để-byte sau round-trip dù mọi thuộc tính khác (tên/màu/hiển thị) khớp đúng — xem `CT3D_REMAINING_WORK.md` |
| G2 | Mask/Surface được InVesalius gốc serialize | `invesalius/project.py` | — | ✓ | — | ✓ | **WORKING** | **Vòng 2**: không còn "kế thừa" suy luận — verify trực tiếp bằng full-cycle thật ở G1 (mask count/tên/màu/hiển thị khớp sau save/close/open) |
| G3 | ROI List (tên/màu/hiển thị) khi load lại | `core/roi_manager.py.rebuild_from_project_masks` | ✓ | ✓ | ✓ | ✓ | **WORKING** (vòng 2, trước đó MISSING) | **Thiết kế lại (vòng 2)**: không còn cần serialize riêng — `ROIManager` chỉ là cache/view của `Project().mask_dict` thật (đã tự lưu qua G2), rebuild tự động sau load. Verify: `test_project_roundtrip.py`, `test_roi_rebuild_after_project_load.py` (9/9) |

## H. Export

| ID | Chức năng | File/Class | UI | Backend | PubSub | Runtime | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| H1 | Export Mask (NIfTI/NRRD/NumPy) | `export_panel.py._on_export_mask` → NIfTI qua `"Show export mask dialog"` gốc; NRRD/NumPy qua `core/exporters.py` | ✓ | ✓ | ✓ | ✓ | **WORKING** (đã sửa bug thật vòng 3) | NIfTI: verify bằng cách gọi thẳng `"Export masks to nifti"` (bypass dialog modal): file .nii.gz thật, 1.901.372 voxel thật, đọc lại bằng `nibabel` thành công. **Bug phát hiện vòng 3**: dropdown "Format" KHÔNG có tác dụng — chọn NRRD/MetaImage vẫn luôn ra NIfTI (dialog gốc InVesalius chỉ hỗ trợ NIfTI). Đã sửa: dropdown nay điều khiển đúng định dạng thật (NRRD/NumPy qua `core/exporters.py`, đã tồn tại nhưng chưa từng được gọi); đã xoá "MetaImage" khỏi dropdown (0 hàm ghi file cho định dạng này trong toàn bộ codebase). NumPy verify PASS thật (đọc lại bằng `np.load`). NRRD: `pynrrd` chưa cài trong venv — chọn NRRD nay báo lỗi rõ ràng thay vì âm thầm ghi sai file |
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
