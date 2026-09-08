# Việc còn lại thực sự chưa hoàn thành

> Chỉ liệt kê những gì **thật sự chưa xong**, có bằng chứng cụ thể. Không ghi chung chung "cần cải thiện thêm".

---

## P1 — ảnh hưởng trực tiếp workflow trọng tâm đề tài

### 1. Xác nhận thủ công qua GUI: "Update 3D Surface" với mask kích thước hợp lý
- **Module**: `plugins/roi_viewer/gui/segmentation_panel.py._on_update_surface`
- **Nguyên nhân**: đã verify bằng script rằng UI gửi đúng pubsub message, đúng tham số, không exception (chuỗi UI→event→backend đúng 100%). Nhưng bước cuối "người dùng thấy surface mới" **chưa quan sát được trong test tự động** với mask lớn (16,2 triệu voxel — do tolerance test quá rộng, không đại diện cho use-case thực tế). Với mask kích thước bình thường (bước tạo surface lần đầu trong cùng phiên test, ~900K điểm) thì cơ chế THẬT SỰ chạy nhanh (vài giây, có log Extraction/Joining/Cleaning thật).
- **Mức ưu tiên**: P1 (ảnh hưởng trực tiếp workflow "sửa ROI → xem 3D")
- **Cách hoàn thiện**: mở app thật, tạo mask threshold cỡ vừa phải (không phải toàn bộ volume), sửa bằng brush, bấm "Update 3D Surface", đo thời gian thật bằng đồng hồ. Nếu > 10-15 giây với mask vừa phải, cần điều tra sâu hơn `invesalius/data/surface.py` (multiprocessing pool trong `AddNewActor`) — không nằm trong phạm vi phiên này vì đó là code InVesalius gốc, sửa cần cẩn trọng hơn.

### 2. Region Growing với tolerance mặc định có thể tạo mask quá lớn
- **Module**: `core/segmentation.py.region_growing`, `segmentation_panel.py` (spin_rg_tolerance mặc định = 50)
- **Nguyên nhân**: với tolerance quá rộng trên dữ liệu CT xương (dải HU rộng), region growing có thể lan ra >50% toàn bộ volume — không còn ý nghĩa "vùng quan tâm" (ROI) nữa. Thuật toán ĐÚNG, chỉ là chưa có giới hạn/cảnh báo hợp lý.
- **Mức ưu tiên**: P1 (ảnh hưởng chất lượng kết quả segmentation)
- **Cách hoàn thiện**: thêm cảnh báo UI khi vùng grow ra vượt quá X% volume (ví dụ >20%), hoặc giới hạn `max_voxels` trong `region_growing()`. Ước lượng: ~30 phút code + test.

## P2 — hoàn thiện nhưng không chặn workflow chính

### 3. Annotation không được lưu cùng project (.inv3)
- **Module**: `core/annotation.py` (AnnotationManager)
- **Nguyên nhân**: state thuần Python trong bộ nhớ plugin, không có code serialize vào `.inv3`. Đóng/mở lại project sẽ MẤT toàn bộ annotation.
- **Mức ưu tiên**: P2
- **Cách hoàn thiện**: 2 hướng — (a) tự implement serialize riêng (lưu JSON cạnh file `.inv3`, load lại khi mở project, dùng `AnnotationManager.export_to_dict()`/`import_from_dict()` đã có sẵn); (b) nghiên cứu cơ chế `project["custom_data"]` (nếu InVesalius core hỗ trợ plugin lưu data tuỳ biến vào project — cần đọc thêm `invesalius/project.py`, ngoài phạm vi đã audit trong phiên này). Ước lượng: 2-4 giờ.

### 4. ROI List (metadata tên/màu/hiển thị riêng plugin) không lưu cùng project
- **Module**: `core/roi_manager.py` (ROIManager)
- **Nguyên nhân**: tương tự mục 3 — state trong bộ nhớ. Mask THẬT vẫn được lưu (nhờ cơ chế InVesalius gốc), nhưng danh sách ROI List riêng của plugin sẽ trống khi mở lại project, phải build lại thủ công (mất tên tuỳ chỉnh, không mất mask).
- **Mức ưu tiên**: P2
- **Cách hoàn thiện**: cùng hướng với mục 3.

### 5. Đo khoảng cách/diện tích 2D — kết quả không hiện trong panel riêng của plugin
- **Module**: `measurement_panel.py._on_start_distance` (nhánh 2D), `_on_measure_area`
- **Nguyên nhân**: cố tình remote-control công cụ đo 2D gốc của InVesalius (đúng kiến trúc, tránh viết lại) thay vì tự bắt sự kiện vẽ trên canvas. Kết quả đo hiện đúng ở tab "Measures" gốc InVesalius, nhưng **không đọc ngược được vào danh sách của plugin** vì chưa nghiên cứu cấu trúc dữ liệu nội bộ `invesalius/data/measures.py` (Measurement/LinearMeasure class) đủ sâu để biết khi nào 1 phép đo "hoàn tất" và đọc lại giá trị.
- **Mức ưu tiên**: P2 (tính năng vẫn dùng được, chỉ là hiển thị ở nơi khác)
- **Cách hoàn thiện**: đọc `invesalius/data/measures.py`, tìm pubsub topic báo "đã thêm 1 measurement" (nếu có) để subscribe và đồng bộ vào panel riêng. Ước lượng: 3-5 giờ nghiên cứu + code.

### 6. Watershed và Morphology (dilate/erode/remove small/fill holes) chưa nối UI
- **Module**: `core/segmentation.py.watershed`, `._simple_watershed`, `.morphological_op`, `.remove_small_objects`, `.fill_holes`
- **Nguyên nhân**: code tồn tại, đúng, không lỗi import — chưa có nút UI gọi tới (DEAD_CODE, giống tình trạng ban đầu của Region Growing trước phiên này).
- **Mức ưu tiên**: P2/P3 — InVesalius gốc **đã có Watershed thật riêng** (`SLICE_STATE_WATERSHED`, dùng được qua UI gốc ngay bây giờ, không cần plugin), nên đây không phải tính năng bị thiếu hoàn toàn với người dùng cuối, chỉ là chưa tích hợp vào panel của plugin.
- **Cách hoàn thiện**: tương tự cách đã làm với Region Growing (D10) — nối `watershed()` vào UI (pick nhiều seed), hoặc đơn giản hơn: remote-control `SLICE_STATE_WATERSHED` giống Brush. Ước lượng: 1-2 giờ (theo pattern đã có).

## P3 — không chặn tiến độ, làm khi còn thời gian

### 7. Chưa test đa vendor CT thật (Siemens/GE/Philips)
Đã test 3 bộ dữ liệu (2 CT + 1 MRI) từ GitHub release chính thức InVesalius — chưa rõ vendor gốc máy chụp. Đề cương/tài liệu kế hoạch khuyến nghị test đa vendor cho luận văn — cần tìm thêm dataset (TCIA/LIDC-IDRI như tài liệu kế hoạch đề xuất).

### 8. Chưa đo Dice/Jaccard/Hausdorff (đánh giá định lượng độ chính xác segmentation)
Tài liệu kế hoạch (`Ke_hoach_de_tai_InVesalius_CT3D.md`, mục 4.2) yêu cầu đây là **chương bắt buộc** cho luận văn thạc sĩ, nhưng cần có ground-truth segmentation (dataset có nhãn sẵn, ví dụ Medical Segmentation Decathlon) — hoàn toàn chưa thực hiện, ngoài phạm vi kỹ thuật thuần của phiên này (cần thêm dataset + quy trình đánh giá riêng).

### 9. Chưa khảo sát Usability (SUS score) với bác sĩ/KTV thật
Theo tài liệu kế hoạch mục 4.2 — cần tiếp cận người dùng thật, ngoài phạm vi kỹ thuật.

### 10. Volume rendering (raycasting) thuần chưa có điểm nối pubsub từ plugin
`invesalius/data/volume.py.Volume.OnShowVolume()` là hàm duy nhất khởi tạo raycasting nhưng không có nơi nào (kể cả trong InVesalius gốc, theo grep) gọi tới nó ngoài định nghĩa — nghi vấn đây là code chưa hoàn thiện/legacy trong chính InVesalius gốc, không phải giới hạn riêng của plugin. Đo FPS trong phiên này dùng surface rendering thay thế (đã ghi rõ, không báo nhầm là raycasting).

### 11. Export DICOM-SEG
Ngoài phạm vi đã triển khai — NIfTI (đã có, đã verify) đáp ứng yêu cầu tương tác chuẩn với phần mềm y tế khác nêu trong tài liệu kế hoạch mục 4.7.

---

## Tổng kết ưu tiên

| # | Việc | Ưu tiên | Ước lượng thời gian |
|---|---|---|---|
| 1 | Verify thủ công Update 3D Surface (mask vừa phải) | P1 | 15 phút (thao tác tay) |
| 2 | Giới hạn/cảnh báo Region Growing tolerance quá rộng | P1 | 30 phút |
| 3 | Serialize Annotation vào project | P2 | 2-4 giờ |
| 4 | Serialize ROI List metadata vào project | P2 | (gộp cùng #3) |
| 5 | Đọc ngược kết quả đo 2D vào panel plugin | P2 | 3-5 giờ |
| 6 | Nối Watershed/Morphology vào UI plugin | P2/P3 | 1-2 giờ |
| 7-11 | Đánh giá định lượng, đa vendor, usability, DICOM-SEG, raycasting | P3 | Ngoài phạm vi kỹ thuật phiên này |
