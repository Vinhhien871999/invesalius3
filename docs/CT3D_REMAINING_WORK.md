# Việc còn lại thực sự chưa hoàn thành

> Chỉ liệt kê những gì **thật sự chưa xong**, có bằng chứng cụ thể. Không ghi chung chung "cần cải thiện thêm". Cập nhật vòng 2 (08/09/2026): các mục P1 của vòng 1 (Update 3D Surface, Region Growing an toàn) **đã đóng** — xem `CT3D_CHANGELOG.md`/`CT3D_TEST_REPORT.md` cho bằng chứng. Annotation/ROI persistence (P2 cũ) **đã đóng** bằng cơ chế sidecar JSON. Watershed/Morphology (P2/P3 cũ) **đã xoá** khỏi phạm vi (quyết định kiến trúc, không phải hoãn lại — xem mục "Quyết định đã chốt" bên dưới). Đo 2D đọc ngược vào panel plugin (P2 cũ) **không còn là việc cần làm** — xem cùng mục. **Cập nhật Phase 09 (14/09/2026)**: Sync 2D→3D và F3 (vị trí annotation) **đã đóng** (WORKING, verify runtime đầy đủ — xem `CT3D_P09_INTERACTION_QA_REPORT.md`). Các mục manual-QA rải rác (1c, 2b cũ) đã gộp lại thành 1 checklist duy nhất ở Phase 09. **Cập nhật Phase 10 (14/09/2026)**: mục "2a" (checksum voxel mask lệch sau Save/Open) **đã điều tra dứt điểm và đóng** — kết luận CASE A (không có bug thật, 30/30 test round-trip thật khớp byte-để-byte tuyệt đối trong mọi kịch bản, kể cả gzip và mask bị xoá giữa danh sách) — mục này đã **xoá khỏi danh sách** (không còn là việc-chưa-xong), xem `CT3D_P10_DATA_INTEGRITY_REPORT.md`. Undo/Redo cũng đã đo bộ nhớ thật và tối ưu (`max_history` 20→10) trong Phase 10. **Cập nhật Phase 11 (14/09/2026)**: số liệu worst-case bộ nhớ Undo/Redo của Phase 10 (547MB) được xác nhận **sai gấp 2 lần** qua test invariant thật — số đúng là 273.6MB (xem `CT3D_P11_TEST_AUTOMATION_REPORT.md` mục 11, `CT3D_MASTER_PROGRESS.md`/`CT3D_FEATURE_AUDIT.md` đã sửa theo). Mục dead code `MaskEditor` (item 8 cũ) **đã xoá thật** (146 dòng, 10 method — nhiều hơn 3 method Phase 10 phát hiện ban đầu) sau khi xác nhận 0 call-site toàn repo và bộ test bền vững PASS. Toàn bộ bằng chứng quan trọng từ các script scratchpad tạm thời của Phase 08-10 nay đã có bản `pytest` thật, chạy lại được, nằm trong `tests/ct3d/` (109 test, xem báo cáo Phase 11). **Cập nhật Phase 12 (14/09/2026)**: `MaskEditorManager` 3 method dead code đã xoá thật (điều tra cùng chuẩn Phase 11). NRRD có extra `pynrrd` chính thức + UI phát hiện/cảnh báo rõ khi thiếu. Dataset registry thật đã lập (`CT3D_DATASET_REGISTRY.md`) — xác nhận 2 vendor thật (SIEMENS, Philips), 2 modality (CT, MR), cả 3 dataset local đều chỉ 1 series/study. Region Growing full-volume CT thật (mục 1b cũ) đã đóng — PASS thật, hết treo. Dice/Jaccard/Hausdorff có hạ tầng thật (`core/evaluation.py`) + 42 test synthetic PASS. Manual QA checklist chính thức tạo ở `CT3D_MANUAL_QA_CHECKLIST.md` (7 mục, tất cả `NOT_RUN`). Xem `CT3D_P12_QUANTITATIVE_VALIDATION_REPORT.md` cho toàn bộ chi tiết. **Cập nhật Phase 13 (16/09/2026)**: **Manual QA 7/7 PASS thật** (P08.5, B4, C3, D4, D5, E2, E3) — người vận hành thao tác chuột thật trên GUI InVesalius thật, xem `CT3D_MANUAL_QA_CHECKLIST.md`. `MANUAL_QA_COMPLETE = YES`. Đã sửa lỗi CSV thật trong `CT3D_P12_QUANTITATIVE_RESULTS.csv` (1 field chưa quote đúng chuẩn CSV). Đã chuẩn bị `CT3D_SUS_PROTOCOL.md` (protocol only, chưa có người tham gia thật) và benchmark hiệu năng có phương pháp (`CT3D_P13_PERFORMANCE_RESULTS.csv`). Xem `CT3D_P13_PERFORMANCE_COMPARISON_REPORT.md` cho toàn bộ chi tiết.

---

## P1 — ảnh hưởng trực tiếp workflow trọng tâm đề tài (ĐÃ ĐÓNG — xem Phase 08)

### 1. [ĐÃ ĐÓNG — Phase 08, 14/09/2026] D9 (Update 3D Surface) — nguyên nhân gốc thật khác hẳn nghi ngờ ban đầu
- **Kết quả**: KHÔNG phải vấn đề RAM/timing như nghi ngờ ở vòng 3. Nguyên nhân thật: `_on_update_surface()` luôn hardcode `algorithm="Default"`, khiến marching cubes contour lại ảnh gốc thay vì đọc mask — mọi chỉnh sửa mask vô tác dụng lên surface. Đã sửa (chọn `algorithm` theo `mask.was_edited`) và verify runtime thật 36/36 check PASS (dataset tổng hợp nhỏ né giới hạn RAM, chạy 100% code thật). D9/C7 chính thức WORKING.
- **Chi tiết đầy đủ**: `CT3D_P08_ROI3D_CLOSURE_REPORT.md`.
- **Còn lại (không phải P1 nữa, chuyển P2)**: xác nhận thủ công qua GUI thật (chuột thật, dialog mặc định không `batch_mode`) — xem báo cáo Phase 08 mục P08.5.

### 1b. [ĐÃ ĐÓNG — Phase 12, 14/09/2026] Region Growing với volume CT thật đầy đủ — hết treo
- **Kết quả**: chạy lại thật có kiểm soát (đọc RAM khả dụng thật trước, ước lượng working-set từ shape/dtype thật, có safety factor, sẵn sàng `BLOCKED_BY_MEMORY` nếu không đủ) trên dataset `0051` (28.311.552 voxel, đúng quy mô đã từng treo ở vòng 3). **PASS thật**: runtime 0.30s, 6.843.727 voxel output (24.17% — đúng vượt ngưỡng cảnh báo 20%, hành vi đúng), RSS chỉ tăng 28.5MB. Xác nhận: lần treo ở vòng 3 là do RAM máy lúc đó thấp (machine-state-dependent), không phải giới hạn thuật toán/hiệu năng thật.
- **Chi tiết đầy đủ**: `CT3D_P12_QUANTITATIVE_VALIDATION_REPORT.md` mục 17.

### 1c. [ĐÃ ĐÓNG — Phase 13, 16/09/2026] Manual QA thao tác chuột thật — 7 mục
- **Kết quả**: người vận hành thật thực hiện đúng checklist `CT3D_MANUAL_QA_CHECKLIST.md` trên GUI InVesalius thật (dataset `0051`) — **7/7 PASS**: P08.5 (D9/C7 qua dialog thật), B4 (Zoom/Pan 2D), C3 (Rotate/Pan/Zoom 3D), D4 (Brush), D5 (Eraser), E2 (Distance 2D: M1=143.951mm, M2=189.741mm), E3 (Area 2D: Sagittal=2674.851mm², Coronal=5367.750mm²). Không crash ở bất kỳ bước nào. `MANUAL_QA_COMPLETE = YES`.
- **Chi tiết đầy đủ**: `CT3D_MANUAL_QA_CHECKLIST.md` (evidence từng mục), `CT3D_P13_PERFORMANCE_COMPARISON_REPORT.md` mục 4.

## P2 — hoàn thiện nhưng không chặn workflow chính

*(Mục "2a" — checksum voxel mask lệch sau Save/Open — đã điều tra dứt điểm và đóng ở Phase 10, CASE A/không có bug thật. Đã xoá khỏi danh sách này — xem `CT3D_P10_DATA_INTEGRITY_REPORT.md`.)*

## P3 — không chặn tiến độ, làm khi còn thời gian

### 3. Chưa test đa vendor CT thật đầy đủ (GE/Canon còn thiếu)
- **Cập nhật vòng 2**: đã đọc tag `Manufacturer` thật (qua gdcm — chính thư viện InVesalius gốc dùng) cho dataset CT 0051: **SIEMENS xác nhận thật**.
- **Cập nhật Phase 12**: đã đọc tag + import thật end-to-end cho cả `0801` (**CT/Philips xác nhận thật**) và `mri3` (**MR/Philips Medical Systems xác nhận thật**) — xem `CT3D_DATASET_REGISTRY.md`. **2/4 vendor phổ biến đã xác nhận thật bằng dữ liệu local** (SIEMENS, Philips), A2 nâng lên `PARTIAL`. Còn thiếu GE/Canon — không có dataset local, cần dataset ngoài (TCIA/LIDC-IDRI như tài liệu kế hoạch đề xuất) — `BLOCKED_EXTERNAL_DATA`, không tự tải dataset ngoài.

### 4. Dice/Jaccard/Hausdorff — hạ tầng + synthetic validation đã xong, ground-truth THẬT còn thiếu
Tài liệu kế hoạch (`Ke_hoach_de_tai_InVesalius_CT3D.md`, mục 4.2) yêu cầu đây là **chương bắt buộc** cho luận văn thạc sĩ. **Cập nhật Phase 12**: hạ tầng thật đã hoàn tất — `plugins/roi_viewer/core/evaluation.py` (Dice/Jaccard/Hausdorff/HD95, spacing anisotropic đúng), 42 test synthetic PASS (`tests/ct3d/test_evaluation_metrics.py`, `tests/ct3d/test_phantom_validation.py`) — edge case, phantom biết trước, đúng công thức tay. **Trạng thái đúng: infrastructure complete, synthetic ground-truth validation complete.** Còn thiếu duy nhất: ground-truth segmentation THẬT (dataset có nhãn sẵn, ví dụ Medical Segmentation Decathlon) để validate trên dữ liệu thật — không có local, `BLOCKED_EXTERNAL_DATA`.

### 5. Chưa khảo sát Usability (SUS score) với bác sĩ/KTV thật
Theo tài liệu kế hoạch mục 4.2 — cần tiếp cận người dùng thật, ngoài phạm vi kỹ thuật.

### 6. Volume rendering (raycasting) thuần chưa có điểm nối pubsub từ plugin
**Vòng 2 — đã kiểm tra lại kỹ hơn theo đúng yêu cầu mục K** (không chỉ grep tên hàm, mà tìm cả `getattr`/binding động/pubsub/task panel/plugin loading): `invesalius/data/volume.py.Volume.OnShowVolume()` vẫn xác nhận **0 call-site thật trong toàn bộ repo**, không có cơ chế dispatch động nào gọi tới nó. Đây là hạn chế/thiếu sót trong CHÍNH InVesalius gốc (không phải do plugin), và launch app thật xác nhận: người dùng KHÔNG có cách nào từ UI gốc để bật raycasting thuần qua đường này. Theo đúng chỉ đạo mục K: ghi nhận `NOT_CONNECTED`, **không tự viết raycaster mới trong vòng này**. Đo FPS dùng surface rendering thay thế (đã ghi rõ, không báo nhầm là raycasting).

### 7. Export DICOM-SEG
Ngoài phạm vi đã triển khai — NIfTI (đã có, đã verify) đáp ứng yêu cầu tương tác chuẩn với phần mềm y tế khác nêu trong tài liệu kế hoạch mục 4.7.

---

## Quyết định đã chốt (vòng 2) — không phải "việc còn thiếu", là lựa chọn kiến trúc có lý do

- **Watershed/Morphology custom trong plugin: ĐÃ XOÁ, không làm nữa.** `core/segmentation.py.watershed()`/`_simple_watershed()`/`morphological_op()`/`remove_small_objects()`/`fill_holes()` bị xoá hẳn (không phải "chưa nối UI" nữa). Lý do: gọi thư viện chuẩn (`skimage`) không phải đóng góp nghiên cứu, trùng hoàn toàn Watershed THẬT của InVesalius gốc (`SLICE_STATE_WATERSHED`, dùng được ngay qua UI gốc), 0 test, 0 call-site, không nằm trong phạm vi bắt buộc của tài liệu kế hoạch (mục yêu cầu "chọn 1-2 thuật toán" — đề tài đã chọn Threshold + Region Growing).
- **Đo 2D không tạo danh sách thứ hai trong plugin: giữ nguyên remote-control.** Theo câu hỏi kỹ thuật mục H ("plugin có thực sự cần danh sách measurement thứ hai không?") — tab "Measures" gốc InVesalius đã đáp ứng đúng yêu cầu "đo được"; tạo thêm 1 bản sao sẽ chỉ tạo nguy cơ divergence (2 nguồn dữ liệu lệch nhau) mà không giải quyết thêm gì. Không viết thêm code cho việc này.
- **ROIManager không serialize riêng — chỉ rebuild từ `Project().mask_dict` thật.** Không phải việc thiếu, là thiết kế đúng (tránh 2 nguồn dữ liệu) — xem `CT3D_ARCHITECTURE.md` mục 4.

---

## Tổng kết ưu tiên

> **Cập nhật sau Phase 13 (16/09/2026)**: **Manual QA 7/7 PASS thật** (mục "1c" cũ, người vận hành thao tác chuột thật trên GUI thật — xem `CT3D_MANUAL_QA_CHECKLIST.md`) — đã đóng hoàn toàn, xoá khỏi bảng. Không còn mục P1 nào đang mở. D9/C7 (Phase 08), Sync 2D→3D và F3 (Phase 09), checksum Save/Open "2a" (Phase 10) đã đóng. Undo/Redo: số liệu worst-case đã sửa đúng (273.6MB) ở Phase 11. Dead code `MaskEditor`/`MaskEditorManager` đã xoá thật. Region Growing full-volume CT thật đã đóng ở Phase 12. Đa vendor: 2/2 vendor thật xác nhận (SIEMENS, Philips) — chỉ còn thiếu GE/Canon (`BLOCKED_EXTERNAL_DATA`). Dice/Jaccard/Hausdorff: infrastructure + synthetic validation complete — chỉ còn thiếu ground-truth THẬT (`BLOCKED_EXTERNAL_DATA`). Bảng dưới đây phản ánh đúng baseline SAU Phase 13 — **chỉ còn các mục `BLOCKED_EXTERNAL_DATA`/ngoài phạm vi kỹ thuật, không còn mục P1 nào**.

| # | Việc | Ưu tiên | Ước lượng thời gian |
|---|---|---|---|
| 3 | GE/Canon CT — `BLOCKED_EXTERNAL_DATA` (2/4 vendor phổ biến đã xác nhận thật: SIEMENS, Philips — xem `CT3D_DATASET_REGISTRY.md`) | P3 | Cần dataset ngoài, ngoài khả năng môi trường hiện tại (Phase 14+) |
| 4 | Ground-truth THẬT cho Dice/Jaccard/Hausdorff — `BLOCKED_EXTERNAL_DATA` (hạ tầng + synthetic validation đã xong ở Phase 12, `core/evaluation.py`) | P3 | Cần dataset có nhãn sẵn (vd. Medical Segmentation Decathlon), ngoài khả năng môi trường hiện tại (Phase 14+) |
| 5 | Khảo sát Usability (SUS) — protocol đã chuẩn bị ở Phase 13 (`CT3D_SUS_PROTOCOL.md`), chưa có người tham gia thật | P3 | Cần người dùng thật (bác sĩ/KTV), ngoài phạm vi kỹ thuật (Phase 14+) |
| 6 | Volume rendering raycasting thuần | P3 | Hạn chế của InVesalius gốc, không tự viết raycaster mới |
| 7 | Export DICOM-SEG | P3 | Ngoài phạm vi đã triển khai (NIfTI đã đáp ứng) |
