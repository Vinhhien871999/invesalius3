# Xác minh tài liệu hướng dẫn sử dụng ROI Viewer bằng runtime thật

> Coi `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md` là **danh sách acceptance test**. Mỗi mục được test bằng script chạy app thật (`wx.App` + `Frame` + `Controller` như `app.py`, DICOM thật, plugin load qua `PluginManager` thật), đọc lại state thật của `Slice()`/`Project()` để verify — **không kết luận PASS chỉ vì thấy code/nút bấm**. Ngày verify: 08/09/2026 (vòng 3).

**Phân loại**: `PASS` / `PARTIAL` / `FAIL` / `NOT_IMPLEMENTED` / `NOT_TESTED` / `MANUAL_REQUIRED`.

**Giới hạn môi trường phiên này (ghi rõ, không giấu)**: máy chạy test chỉ còn **3.5-4.8GB RAM khả dụng / 16.44GB** trong suốt phiên (đã đo nhiều lần bằng `psutil`). Các thao tác cần multiprocessing thật (dựng surface 3D) hoặc mảng numpy lớn (~28 triệu voxel, Region Growing) **treo lặp lại nhiều lần** (4/4 lần dựng surface, 2/2 lần Region Growing đầy đủ) mà không sinh crash report nào (0 crash report mới trong suốt phiên — xác nhận qua `crash_reports/`) — tức là tiến trình bị chậm/nghẽn tài nguyên thật, không phải lỗi code gây crash. Với các phần này, báo cáo dùng **bằng chứng đã có từ vòng 1/2** (cùng ngày, cùng máy, lúc RAM còn rộng hơn) làm chứng cứ, ghi rõ là "kế thừa, chưa re-test tươi trong vòng 3".

---

## Bảng tổng hợp

| Mục hướng dẫn | Chức năng | Code | Runtime | Kết quả | Vấn đề |
|---|---|---|---|---|---|
| §1 | Import DICOM → Axial/Coronal/Sagittal hiển thị | ✓ | ✓ | **PASS** | `test_guide_part1.py`, vòng 3 |
| §1 | Mở Plugins → ROI Viewer, đủ 5 tab đúng tên | ✓ | ✓ | **PASS** | Tab names khớp chính xác |
| §1 | Đóng rồi mở lại không crash | ✓ | ✓ | **PASS** | Window mới thật, object khác |
| §1 | Mở nhiều lần không tạo nhiều window | ✓ | ✓ | **PASS** | Cùng object id sau lần mở thứ 2 |
| §2 | Auto threshold (Otsu) cập nhật Min/Max thật | ✓ | ✓ | **PASS** | |
| §2 | Create Mask from Threshold → mask_dict tăng, xuất hiện native + ROI List, current mask đúng | ✓ | ✓ | **PASS** | |
| §3 | Update 3D Surface from Selected ROI (P1) | ✓ | (kế thừa vòng 2) | **PARTIAL** | Xem mục "P1: Update 3D Surface" bên dưới |
| §4 | Pick Point in 3D trên hình học thật, X/Y/Z cập nhật | ✓ | (kế thừa vòng 1/2) | **PASS (kế thừa)** | `test_gap_fill.py` vòng 1/2 — chưa re-test tươi vòng 3 (cần surface thật) |
| §4 | Sync 3D → 2D (Axial/Coronal/Sagittal nhảy đúng) | ✓ | (kế thừa vòng 1/2) | **PASS (kế thừa)** | Đã verify bằng voxel/world conversion thật (`test_coordinate_roundtrip.py` vòng 2, 11/11) |
| §4 | Sync 2D → 3D | (chỉ có state, không có logic) | — | **NOT_IMPLEMENTED** | Xem mục riêng bên dưới |
| §5 | Region Growing (tolerance 0/10/20/50) | ✓ | (kế thừa vòng 1/2) | **PARTIAL** | Không re-test tươi được vòng 3 (môi trường treo 2/2 lần) — xem mục riêng bên dưới |
| §5 | Cảnh báo vùng >20% (dialog Yes/No, voxel/%/mm³) | ✓ | **✓ (test moi, khong can surface)** | **PASS** | `region_stats()` + `_on_region_grown()` dialog logic test trực tiếp — xem mục riêng |
| §6 | ROI List: mask tạo ngoài plugin tự xuất hiện | ✓ | ✓ | **PASS** | |
| §6 | Select/Rename/Visibility/Delete | ✓ | ✓ | **PASS** | Verify trực tiếp `Project().mask_dict` + `Slice().current_mask` |
| §6 | ROIManager không phải source-of-truth độc lập | ✓ | ✓ | **PASS** | Xoá mask qua topic native → ROIManager tự đồng bộ, không mồ côi |
| §7 | Brush: Draw/Erase/Circle/Square/size, checksum đổi thật khi vẽ | ✓ | — | **MANUAL_REQUIRED** | Môi trường không điều khiển được thao tác rê chuột GUI thật |
| §7 | Save Checkpoint → Draw → Undo → Redo (checksum) | ✓ | (một phần, không phải brush chuột) | **PARTIAL** | Verify bằng edit trực tiếp ma trận, không phải brush chuột thật |
| §7 | Update 3D Surface sau khi vẽ | ✓ | — | **MANUAL_REQUIRED** | Phụ thuộc thao tác vẽ tay + cùng giới hạn môi trường ở §3 |
| §8 | 3D Distance (Start Distance + pick 2 điểm) | ✓ | (kế thừa vòng 1/2) | **PASS (kế thừa)** | `test_gap_fill.py`, 59.56mm |
| §8 | Measure Volume = voxel_count × spacing | ✓ | ✓ | **PASS (đã sửa 1 bug)** | Xem mục BUG |
| §8 | 2D Distance (bật tool + click 2 điểm) | ✓ | (một phần) | **PARTIAL** | Bật đúng style thật xác nhận; click chuột thật = MANUAL_REQUIRED |
| §8 | 2D Area (polygon + verify) | ✓ | (một phần) | **PARTIAL** | Tương tự |
| §9 | Add/Edit/Go to/Prev/Next/Delete annotation | ✓ | ✓ | **PASS** | |
| §9 | Annotation persistence (save→close→open) | ✓ | ✓ | **PASS** | File `.roi_annotations.json` thật tồn tại, đọc lại đúng text/position/colour |
| §10 | Save/Open full roundtrip (mask count/name/colour/visibility) | ✓ | ✓ | **PASS** | |
| §10 | Save/Open: mask checksum voxel data | ✓ | ✗ | **FAIL (bug thật, chưa rõ nguyên nhân)** | Xem mục BUG |
| §11 | ROI List tự rebuild sau Open, không cần tạo lại thủ công | ✓ | ✓ | **PASS** | Tên/index/visibility/colour đều đúng |
| §12 | Export Mask — NIfTI | ✓ | ✓ | **PASS** | |
| §12 | Export Mask — NRRD dropdown | ✗ (trước khi sửa) | ✗→✓ | **BUG THẬT, ĐÃ SỬA** | Xem mục BUG |
| §12 | Export Mask — MetaImage dropdown | không có backend | — | **ĐÃ XOÁ KHỎI UI** | Xem mục BUG |
| §12 | Export Mask — NumPy | ✓ (chưa nối trước sửa) | ✓ | **PASS (sau khi nối)** | |
| §13 | Export Surface (STL/PLY/OBJ/VTK) | ✓ | (kế thừa vòng 1) | **PASS (kế thừa)** | `test_gap_fill.py` vòng 1 — chưa re-test tươi vòng 3 (cần surface thật) |
| §14 | Export Current View (PNG/JPG/TIFF/BMP) | ✓ | ✓ | **PASS** | 5/5, `test_guide_export_view.py` — kèm test Scale=2 → kích thước gấp đôi thật |

---

## P1: Update 3D Surface — đánh giá trung thực

**KHÔNG đánh PASS.** Theo đúng yêu cầu: "nếu chỉ gửi pubsub được mà polydata không thay đổi thì FAIL/PARTIAL, tuyệt đối không PASS."

**Bằng chứng đang có (vòng 2, cùng máy, RAM rộng hơn lúc đó)**: `test_surface_update_small_roi.py` — mask nhỏ thật (cube 27.000 voxel), verify polydata thật:
- Chuỗi UI→pubsub→backend→viewer→render: **11/15 PASS** — `"Load surface actor into viewer"` bắn ra thật, không tạo duplicate, actor thật trong renderer, `Render()` thành công.
- Nội dung hình học (points/cells/bounds đổi đúng sau sửa mask): **4/15 FAIL ban đầu**, chẩn đoán chính xác nguyên nhân bằng cách đọc trực tiếp `Slice.do_threshold_to_all_slices()` (bug sentinel — xem `CT3D_CHANGELOG.md`), đã sửa tại `_on_region_grown`.
- **Chưa có lần chạy nào (vòng 2 lẫn vòng 3) xác nhận lại polydata thật đổi ĐÚNG sau bản vá** — thử lại 4 lần trong vòng 3 này, cả 4 lần đều treo ở bước dựng surface do thiếu RAM (xem ghi chú đầu file).

**Kết luận**: giữ nguyên **PARTIAL** — không nâng lên PASS. Đây là mục P1 duy nhất còn treo, cần xác nhận thủ công qua GUI thật (thao tác tay, xem mục "CÁCH TÔI TỰ DEMO") hoặc chạy lại script trên máy có RAM rộng hơn.

## Section 5: Region Growing — đánh giá trung thực

**Không re-test được tươi trong vòng 3** (2/2 lần thử — kể cả bản test đã bỏ hẳn yêu cầu dựng surface, chỉ tính toán trên mảng numpy thật ~28 triệu voxel — đều treo ở CPU ~14-15s rồi dừng tăng, lặp lại gần như chính xác cùng 1 điểm giữa 2 lần chạy độc lập; nghi vấn do RAM khả dụng quá thấp khiến `scipy.ndimage.label()` (vốn ~500ms theo baseline vòng 1) bị swap/thrashing nặng, không phải deadlock code — nhưng **chưa chứng minh được chắc chắn**, ghi nhận trung thực là chưa rõ nguyên nhân 100%, cần điều tra thêm khi có máy rộng RAM hơn).

**Bằng chứng đã có (vòng 1/2)**: seed pick thật → mask thật 16.264.693 voxel, đăng ký đúng vào ROI List (`test_regiongrowing_surfaceupdate.py` vòng 1); `test_region_growing_limits.py` vòng 2 — **16/16 PASS** cho thuật toán thuần (connectivity đúng, validate_seed đúng, tolerance âm raise lỗi đúng).

**Test MỚI làm được trong vòng 3 (không cần surface, PASS thật)**: cảnh báo vùng >20% — gọi trực tiếp `region_stats()` và `_on_region_grown()` (đúng handler thật của nút, không viết lại) với mảng giả lập đúng shape volume thật:
- `region_stats()` cho vùng ~100% volume: `exceeds_limit=True`, voxel_count đúng, %  đúng (~100%), `volume_mm3` > 0 khi có spacing — **PASS**.
- Dialog cảnh báo THẬT xuất hiện (chặn `wx.MessageBox` để đọc nội dung) — nội dung có số voxel, có `%`, có `mm3` — **PASS**.
- Chọn **No**: `Project().mask_dict` count **không đổi** — **PASS** (không âm thầm tạo mask khi người dùng từ chối).
- Chọn **Yes**: `Project().mask_dict` count **tăng thật** — **PASS** (mask thật được tạo khi người dùng đồng ý).

→ Riêng phần "cảnh báo vùng lớn" (tính năng MỚI được quảng cáo trong hướng dẫn vòng 2) đã **verify PASS đầy đủ, tươi, trong vòng 3 này** — không phụ thuộc vấn đề RAM/surface.

## Section 4: Sync 2D → 3D — NOT_IMPLEMENTED (xác nhận qua đọc code, đúng yêu cầu không tự suy diễn PASS)

`interaction_panel.py` có checkbox **Sync 2D → 3D** (`cb_sync_2d_3d`), khi tick chỉ gọi `self.controller.sync_mgr.enable_sync_2d_3d()` — đặt cờ `self.sync_2d_3d = True` trong `core/sync_2d3d.py.SyncManager2D3D`. **Grep toàn bộ plugin xác nhận: cờ `sync_2d_3d` không được ĐỌC lại ở bất kỳ đâu khác** — không có handler nào lắng nghe scroll 2D thật rồi tự điều khiển camera/pick 3D. Đây đúng như tài liệu tự mô tả "mới ở mức khai báo" — **giữ nguyên NOT_IMPLEMENTED**, không nâng lên PASS/PARTIAL.

---

## BUG PHÁT HIỆN (vòng 3)

### 1. Export Mask: dropdown "Format" (NRRD/MetaImage) hoàn toàn không có tác dụng — ĐÃ SỬA
**Trước khi sửa**: `_on_export_mask()` luôn gọi `_export_mask_to_file()`, hàm này CHỈ mở dialog thật "Export Mask as NIfTI" của InVesalius gốc (`invesalius/control.py.OnShowDialogExportMaskDialog`, wildcard NIfTI-only, tự ép đuôi `.nii.gz`). Chọn "NRRD" hay "MetaImage" trong dropdown của plugin **không có tác dụng gì** — file luôn ra NIfTI.

**Verify thật**: chọn "NRRD" trong dropdown rồi export → xác nhận **không có file `.nrrd` nào được ghi**.

**Đã sửa**: `_on_export_mask()` giờ đọc đúng lựa chọn dropdown — NIfTI vẫn qua dialog gốc InVesalius (giữ nguyên đường đã verify hoạt động); NRRD/NumPy dùng đúng hàm export thật đã có sẵn trong `core/exporters.py` (`export_mask_nrrd`/`export_mask_numpy` — code cũ tồn tại nhưng chưa từng được gọi) qua dialog riêng của plugin. Đã xoá "MetaImage" khỏi dropdown vì **hoàn toàn không có hàm ghi file nào** cho định dạng này trong toàn bộ `exporters.py` (không phải "chưa nối", mà là chưa từng được viết).

**Lưu ý**: package `pynrrd` (thư viện NRRD) **không được cài trong venv hiện tại** — chọn NRRD bây giờ sẽ hiện thông báo lỗi rõ ràng ("cần cài pynrrd") thay vì âm thầm ghi sai thành NIfTI như trước. Đây là cải thiện thật (từ "sai âm thầm" thành "báo lỗi đúng"), không phải NRRD đã hoạt động đầy đủ.

### 2. Measure Volume: đếm nhầm voxel viền đệm (padding) vào kết quả — ĐÃ SỬA
**Trước khi sửa**: `_on_measure_volume()` truyền `mask.matrix` (mảng CÓ viền đệm 1-voxel, viền này không phải dữ liệu ảnh thật — 1 ô trong viền còn được dùng làm "cờ đã xử lý" nội bộ của InVesalius) thẳng vào `calculate_volume()`, hàm này đếm mọi voxel `> 0` — **kể cả các ô viền đệm/cờ nội bộ đó**.

**Verify thật**: giá trị UI hiển thị **9575.83mm³** trong khi tính độc lập từ đúng dữ liệu ảnh thật (bỏ viền đệm) cho ra **9574.80mm³** — lệch 1.03mm³ (~0.01%), nhỏ nhưng có thật và có nguyên nhân xác định rõ.

**Đã sửa**: truyền `mask.matrix[1:, 1:, 1:]` (chỉ phần dữ liệu ảnh thật) — verify lại: UI khớp đúng **9574.80mm³ = 9574.80mm³**, khớp tuyệt đối.

### 3. Save/Open: checksum voxel mask không khớp byte-để-byte sau roundtrip — CHƯA SỬA (chưa rõ nguyên nhân)
Xác nhận **2 lần độc lập** (vòng 2 và vòng 3, mask khác nhau, kịch bản khác nhau) — mọi thuộc tính khác của mask (tên, màu, hiển thị, số lượng) đều khớp đúng 100% sau Save→Close→Open, chỉ riêng nội dung voxel (SHA-256 checksum) lệch. Đã thử giả thuyết "chưa flush() trước khi save" — gọi `flush()` thêm trước Save không làm checksum trước-save đổi (dữ liệu đã flush sẵn từ trước), nên giả thuyết này KHÔNG giải thích được lệch sau khi ĐỌC LẠI. Chưa xác định được nguyên nhân chính xác (nghi vấn liên quan `invesalius/data/mask.py.SavePlist()` map thẳng file `.dat` vào archive, hoặc hành vi thật của `do_threshold_to_all_slices()` khi mask được load lại — cả hai đều là code InVesalius GỐC, không phải plugin). **Không tự đoán sửa khi chưa chắc nguyên nhân** — ghi vào `CT3D_REMAINING_WORK.md`.

---

## HƯỚNG DẪN NÀO ĐANG SAI (trích chính xác + trạng thái thật)

1. **Tiêu đề "Export Mask (chọn định dạng NIfTI/NRRD/MetaImage)"** (mục 6 tài liệu cũ) — SAI trước khi sửa: dropdown không hoạt động, luôn ra NIfTI. Đã sửa code (mục BUG #1) và đã sửa tài liệu (bỏ MetaImage, ghi rõ NRRD cần cài `pynrrd`).
2. **"Sync 2D → 3D: Cấu hình đồng bộ chiều ngược lại (đang ở mức khai báo, chưa có nút thao tác riêng)"** — tài liệu cũ đã tự nói đúng thực tế (NOT_IMPLEMENTED), không cần sửa nhưng đã làm rõ hơn trong bản cập nhật.
3. **"Update 3D Surface... Việc dựng lại có thể mất vài giây đến hơn chục giây"** — cần bổ sung: trên máy RAM hạn chế, có thể mất lâu hơn nhiều hoặc không hoàn tất — đã cập nhật.

---

## CÁCH TÔI TỰ DEMO (tối đa 10 bước, chỉ dùng chức năng đã PASS thật)

1. `python app.py -i <thư mục DICOM>` → đợi Axial/Coronal/Sagittal hiện ảnh.
2. **Plugins → ROI Viewer** → xác nhận đủ 5 tab.
3. Tab **Segmentation**: tick **Auto threshold (Otsu)** → **Create Mask from Threshold** → thấy mask mới trong **ROI List**.
4. Trong **ROI List**: click chọn dòng mask vừa tạo → **Rename** → đổi tên → xác nhận tên đổi ở cả ROI List lẫn tab Masks gốc InVesalius.
5. Tick/bỏ tick checkbox trước tên mask → xác nhận mask ẩn/hiện thật trên khung 2D.
6. Tab **Measurements**: chọn mask ở bước 3 làm current mask → **Measure Volume** → xem kết quả mm³.
7. Tab **Annotations**: **Add at Current Position** → nhập text → xác nhận xuất hiện trong danh sách.
8. Tab **Export**: **Export Mask**, chọn định dạng **NIfTI**, lưu file → mở file bằng phần mềm đọc NIfTI bất kỳ để kiểm chứng.
9. Tab **Export**: **Save** project `.inv3` → đóng InVesalius hẳn.
10. Mở lại InVesalius → **File → Open Project** đúng file vừa lưu → **Plugins → ROI Viewer** → xác nhận ROI List tự có lại đúng mask (tên/màu/hiển thị), annotation ở bước 7 còn nguyên.

*(Không đưa vào demo: Update 3D Surface, Region Growing, brush vẽ tay, đo 2D bằng chuột — do các mục này hoặc cần thao tác chuột thật (MANUAL_REQUIRED), hoặc cần xác nhận lại trên máy rộng RAM hơn (PARTIAL, chưa đủ điều kiện demo tự tin).)*
