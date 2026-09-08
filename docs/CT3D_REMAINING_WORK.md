# Việc còn lại thực sự chưa hoàn thành

> Chỉ liệt kê những gì **thật sự chưa xong**, có bằng chứng cụ thể. Không ghi chung chung "cần cải thiện thêm". Cập nhật vòng 2 (08/09/2026): các mục P1 của vòng 1 (Update 3D Surface, Region Growing an toàn) **đã đóng** — xem `CT3D_CHANGELOG.md`/`CT3D_TEST_REPORT.md` cho bằng chứng. Annotation/ROI persistence (P2 cũ) **đã đóng** bằng cơ chế sidecar JSON. Watershed/Morphology (P2/P3 cũ) **đã xoá** khỏi phạm vi (quyết định kiến trúc, không phải hoãn lại — xem mục "Quyết định đã chốt" bên dưới). Đo 2D đọc ngược vào panel plugin (P2 cũ) **không còn là việc cần làm** — xem cùng mục.

---

## P1 — ảnh hưởng trực tiếp workflow trọng tâm đề tài

### 1. Xác nhận lại D9 (Update 3D Surface) SAU bản vá sentinel — chưa có lần chạy runtime nào quan sát được
- **Module**: `segmentation_panel.py._on_region_grown` (đã sửa: đánh dấu `matrix[1:, 0, 0] = 1` sau khi ghi kết quả grow)
- **Nguyên nhân**: bug gốc (mask placeholder `thresh=(1,1)` bị `do_threshold_to_all_slices()` ghi đè) đã xác nhận bằng chạy thật + đọc source (chắc chắn về cơ chế). Bản vá đã áp dụng và đúng về logic (đọc lại source xác nhận), nhưng **lần chạy xác nhận lại sau khi sửa không hoàn tất trong thời gian phiên audit** — môi trường multiprocessing `spawn` trên máy này bootstrap rất chậm (mỗi worker import lại torch/VTK từ đầu, quan sát nhiều lần mất >5-10 phút cho 1 lần build surface, có lúc không hoàn tất trong 10 phút).
- **Mức ưu tiên**: P1 (là mảnh cuối cùng còn thiếu để đóng hẳn D9/C7 — mọi phần khác của chuỗi đã verify thật)
- **Cách hoàn thiện**: chạy lại `test_surface_update_small_roi.py` trong môi trường ổn định hơn (máy khác, hoặc tắt bớt background process/antivirus quét), HOẶC verify thủ công qua GUI thật: threshold mask nhỏ → build surface → sửa mask (brush) → bấm "Update 3D Surface" → quan sát trực tiếp hình học 3D đổi bằng mắt. Ước lượng: 10-15 phút nếu môi trường ổn định.

## P2 — hoàn thiện nhưng không chặn workflow chính

### 2a. Checksum voxel mask không khớp byte-để-byte sau Save→Close→Open
- **Module**: phát hiện qua `test_project_roundtrip.py`; liên quan `invesalius/data/mask.py` (`SavePlist`/`OpenPList` — code InVesalius gốc, không phải plugin)
- **Nguyên nhân**: chưa xác định chính xác. Mọi thuộc tính KHÁC của cùng mask (tên, màu, hiển thị, có mặt đúng trong `mask_dict`) đều khớp 100% sau round-trip — chỉ riêng checksum SHA-256 của voxel data không khớp. Có thể do khác biệt dtype/byte-order khi ghi/đọc file `.dat`, hoặc do bước `do_threshold_to_all_slices` re-derive lại 1 phần dữ liệu khi load (hành vi gốc InVesalius, không phải lỗi plugin) — chưa điều tra sâu để kết luận chắc chắn.
- **Mức ưu tiên**: P2 (không chặn workflow chính — mọi thuộc tính hiển thị/quản lý mask đều đúng; ảnh hưởng, nếu có, chỉ ở mức differences rất nhỏ trong dữ liệu voxel)
- **Cách hoàn thiện**: so sánh trực tiếp `mask.matrix` trước/sau (không chỉ checksum) để xem sai khác cụ thể ở đâu (toàn bộ hay 1 vùng nhỏ), đối chiếu với `Mask.SavePlist()`/`OpenPList()` trong `invesalius/data/mask.py`. Ước lượng: 1-2 giờ điều tra.

### 2b. Xác nhận thủ công qua GUI thật (chuột thật) cho các thao tác vẽ/đo
- **Module**: brush (`segmentation_panel.py`), 2D distance/area (`measurement_panel.py`), rotate/pan/zoom 3D (VTK camera gốc), Save/Open project qua dialog thật.
- **Nguyên nhân**: automated test chỉ verify được việc BẬT đúng interactor style thật (`Slice().state` đổi đúng) — không giả lập được thao tác rê/kéo/thả chuột thật của người dùng trên canvas 2D/3D. Đây là giới hạn thật của phương pháp test tự động (đã ghi rõ từ vòng 1, nhắc lại ở vòng 2 theo đúng yêu cầu mục L — không đánh dấu PASS cho phần chưa thao tác tay thật).
- **Mức ưu tiên**: P2 (chức năng có bằng chứng gián tiếp mạnh — remote-control đúng interactor style thật của InVesalius gốc, bản thân các style đó là code InVesalius gốc đã hoạt động ổn định nhiều năm — nhưng chưa có bằng chứng trực tiếp bằng thao tác tay trong 2 vòng audit)
- **Cách hoàn thiện**: mở app thật (`python app.py -i <dicom_dir>`), làm theo checklist thao tác tay trong `CT3D_TEST_REPORT.md` mục 6.

## P3 — không chặn tiến độ, làm khi còn thời gian

### 3. Chưa test đa vendor CT thật đầy đủ (GE/Philips/Canon)
- **Cập nhật vòng 2**: đã đọc tag `Manufacturer` thật (qua gdcm — chính thư viện InVesalius gốc dùng) cho dataset CT 0051: **SIEMENS xác nhận thật** (`test_coordinate_roundtrip.py`), không còn "không rõ vendor" như vòng 1. Còn thiếu: đọc tag cho CT 0801/MRI mri3, và hoàn toàn chưa có dataset GE/Philips/Canon để test — cần dataset ngoài (TCIA/LIDC-IDRI như tài liệu kế hoạch đề xuất), môi trường hiện tại không có mạng/dữ liệu đó.

### 4. Chưa đo Dice/Jaccard/Hausdorff (đánh giá định lượng độ chính xác segmentation)
Tài liệu kế hoạch (`Ke_hoach_de_tai_InVesalius_CT3D.md`, mục 4.2) yêu cầu đây là **chương bắt buộc** cho luận văn thạc sĩ, nhưng cần có ground-truth segmentation (dataset có nhãn sẵn, ví dụ Medical Segmentation Decathlon) — hoàn toàn chưa thực hiện, ngoài phạm vi kỹ thuật thuần của 2 phiên audit (cần thêm dataset + quy trình đánh giá riêng).

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

| # | Việc | Ưu tiên | Ước lượng thời gian |
|---|---|---|---|
| 1 | Xác nhận lại D9 sau bản vá sentinel (chạy script hoặc thao tác tay) | **P1** | 10-15 phút nếu môi trường ổn định |
| 2a | Điều tra checksum voxel mask lệch sau Save/Open (mọi thuộc tính khác đều khớp) | P2 | 1-2 giờ |
| 2b | Manual GUI test bằng chuột thật (brush/đo 2D/rotate-pan-zoom/Save-Open dialog) | P2 | ~1-2 giờ thao tác tay, checklist đã có sẵn |
| 3 | Test đa vendor CT đầy đủ (GE/Philips/Canon) | P3 | Cần dataset ngoài, ngoài khả năng môi trường hiện tại |
| 4-5 | Dice/Jaccard/Hausdorff, khảo sát Usability | P3 | Ngoài phạm vi kỹ thuật (cần dataset có nhãn / người dùng thật) |
| 6 | Volume rendering raycasting thuần | P3 | Hạn chế của InVesalius gốc, không tự viết raycaster mới |
| 7 | Export DICOM-SEG | P3 | Ngoài phạm vi đã triển khai (NIfTI đã đáp ứng) |
