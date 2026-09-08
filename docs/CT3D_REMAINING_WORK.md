# Việc còn lại thực sự chưa hoàn thành

> Chỉ liệt kê những gì **thật sự chưa xong**, có bằng chứng cụ thể. Không ghi chung chung "cần cải thiện thêm". Cập nhật vòng 2 (08/09/2026): các mục P1 của vòng 1 (Update 3D Surface, Region Growing an toàn) **đã đóng** — xem `CT3D_CHANGELOG.md`/`CT3D_TEST_REPORT.md` cho bằng chứng. Annotation/ROI persistence (P2 cũ) **đã đóng** bằng cơ chế sidecar JSON. Watershed/Morphology (P2/P3 cũ) **đã xoá** khỏi phạm vi (quyết định kiến trúc, không phải hoãn lại — xem mục "Quyết định đã chốt" bên dưới). Đo 2D đọc ngược vào panel plugin (P2 cũ) **không còn là việc cần làm** — xem cùng mục.

---

## P1 — ảnh hưởng trực tiếp workflow trọng tâm đề tài

### 1. Xác nhận lại D9 (Update 3D Surface) SAU bản vá sentinel — chưa có lần chạy runtime nào quan sát được
- **Module**: `segmentation_panel.py._on_region_grown` (đã sửa: đánh dấu `matrix[1:, 0, 0] = 1` sau khi ghi kết quả grow)
- **Nguyên nhân**: bug gốc (mask placeholder `thresh=(1,1)` bị `do_threshold_to_all_slices()` ghi đè) đã xác nhận bằng chạy thật + đọc source (chắc chắn về cơ chế). Bản vá đã áp dụng và đúng về logic (đọc lại source xác nhận), nhưng **lần chạy xác nhận lại sau khi sửa vẫn chưa hoàn tất** — đã thử lại 4 lần nữa ở vòng 3 (08/09/2026), cả 4 lần đều treo ở bước dựng surface (multiprocessing). **Nguyên nhân cụ thể hơn xác định được ở vòng 3**: RAM khả dụng trên máy chỉ còn 3.5-4.8GB/16.44GB trong suốt phiên (đo bằng `psutil`, nhiều lần) — không đủ cho các worker process (mỗi worker import lại torch/VTK từ đầu) chạy trơn tru. 0 crash report mới trong toàn bộ 4 lần thử (xác nhận đây là treo do thiếu tài nguyên, không phải crash/lỗi logic).
- **Mức ưu tiên**: P1 (là mảnh cuối cùng còn thiếu để đóng hẳn D9/C7 — mọi phần khác của chuỗi đã verify thật ở vòng 2: `"Load surface actor into viewer"` bắn ra thật, actor thật, render thành công, 11/15 check)
- **Cách hoàn thiện**: đóng bớt ứng dụng khác đang chiếm RAM trên máy (trình duyệt nhiều tab, VS Code...) rồi chạy lại `test_surface_update_small_roi.py`, HOẶC chạy trên máy khác có RAM rộng hơn, HOẶC verify thủ công qua GUI thật: threshold mask nhỏ → build surface → sửa mask (brush) → bấm "Update 3D Surface" → quan sát trực tiếp hình học 3D đổi bằng mắt (thao tác tay không cần nhiều RAM cho automation harness nên có thể ít bị ảnh hưởng hơn). Ước lượng: 10-15 phút nếu môi trường đủ RAM.

### 1b. Xác nhận lại Region Growing với volume CT thật đầy đủ (vòng 3) — cũng treo do cùng nguyên nhân RAM
- **Module**: không phải bug code — `core/segmentation.py.region_growing()` đã verify đúng 16/16 bằng thuật toán thuần (mảng tổng hợp nhỏ, vòng 2). Phần CHƯA re-test được ở vòng 3 là chạy trên volume CT thật ~28 triệu voxel (seed pick thật, 4 mức tolerance).
- **Nguyên nhân**: 2/2 lần thử ở vòng 3 đều treo, CPU tăng tới ~14-15s rồi dừng hẳn (lặp lại gần giống hệt nhau giữa 2 lần chạy độc lập) — nghi vấn `scipy.ndimage.label()` trên mảng ~28 triệu phần tử (bình thường ~500ms theo baseline vòng 1) bị chậm nghiêm trọng do thiếu RAM (swap/thrashing), nhưng **chưa chứng minh chắc chắn 100%** — mức độ lặp lại chính xác giữa 2 lần chạy độc lập cũng đáng chú ý, cần điều tra thêm khi có điều kiện.
- **Mức ưu tiên**: P2 (đã có bằng chứng thật từ vòng 1: mask 16.264.693 voxel tạo thành công qua seed pick thật; phần cảnh báo vùng lớn — tính năng mới nhất — ĐÃ verify PASS đầy đủ ở vòng 3 bằng cách gọi thẳng `_on_region_grown()` không qua surface, xem `ROI_VIEWER_USER_GUIDE_VERIFICATION.md`)
- **Cách hoàn thiện**: tương tự mục 1 — cần máy/thời điểm có RAM rộng hơn để chạy lại `test_regiongrowing_surfaceupdate.py`-style full test.

## P2 — hoàn thiện nhưng không chặn workflow chính

### 2a. Checksum voxel mask không khớp byte-để-byte sau Save→Close→Open
- **Module**: phát hiện qua `test_project_roundtrip.py` (vòng 2); liên quan `invesalius/data/mask.py` (`SavePlist`/`OpenPList` — code InVesalius gốc, không phải plugin)
- **Nguyên nhân**: chưa xác định chính xác. Mọi thuộc tính KHÁC của cùng mask (tên, màu, hiển thị, có mặt đúng trong `mask_dict`) đều khớp 100% sau round-trip — chỉ riêng checksum SHA-256 của voxel data không khớp.
- **Cập nhật vòng 3**: xác nhận lại đúng bug này với mask/kịch bản KHÁC (`test_guide_saveopen.py`) — cùng hiện tượng, cùng kết luận. Đã thử và LOẠI TRỪ giả thuyết "chưa gọi `flush()` trước khi Save": gọi `matrix.flush()` thêm ngay trước `SavePlistProject()` không làm checksum lúc đó đổi (dữ liệu vốn đã flush từ bước tạo mask/threshold) — nghĩa là dữ liệu TRONG BỘ NHỚ lúc save đã đúng/ổn định, vấn đề nằm ở bước ghi-ra-đĩa hoặc đọc-lại, không phải bộ nhớ chưa đồng bộ.
- **Mức ưu tiên**: P2 (không chặn workflow chính — mọi thuộc tính hiển thị/quản lý mask đều đúng; ảnh hưởng, nếu có, chỉ ở mức differences rất nhỏ trong dữ liệu voxel)
- **Cách hoàn thiện**: so sánh trực tiếp từng voxel khác nhau ở đâu (không chỉ checksum tổng — code so sánh voxel-by-voxel đã viết sẵn trong `test_guide_saveopen.py` ở scratchpad, chưa kịp chạy lại để lấy kết quả chi tiết) để khoanh vùng, đối chiếu với `Mask.SavePlist()`/`OpenPList()` trong `invesalius/data/mask.py`. Ước lượng: 1-2 giờ điều tra.

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
| 1 | Xác nhận lại D9 sau bản vá sentinel (chạy script hoặc thao tác tay) — 4 lần thử vòng 3 đều treo do RAM thấp (3.5-4.8GB khả dụng) | **P1** | 10-15 phút nếu đủ RAM |
| 1b | Xác nhận lại Region Growing tren volume CT that (~28M voxel) — 2 lần thử vòng 3 cũng treo cùng nguyên nhân | P2 | 10-15 phút nếu đủ RAM |
| 2a | Điều tra checksum voxel mask lệch sau Save/Open (mọi thuộc tính khác đều khớp, đã loại trừ giả thuyết flush()) | P2 | 1-2 giờ |
| 2b | Manual GUI test bằng chuột thật (brush/đo 2D/rotate-pan-zoom/Save-Open dialog) | P2 | ~1-2 giờ thao tác tay, checklist đã có sẵn |
| 3 | Test đa vendor CT đầy đủ (GE/Philips/Canon) | P3 | Cần dataset ngoài, ngoài khả năng môi trường hiện tại |
| 4-5 | Dice/Jaccard/Hausdorff, khảo sát Usability | P3 | Ngoài phạm vi kỹ thuật (cần dataset có nhãn / người dùng thật) |
| 6 | Volume rendering raycasting thuần | P3 | Hạn chế của InVesalius gốc, không tự viết raycaster mới |
| 7 | Export DICOM-SEG | P3 | Ngoài phạm vi đã triển khai (NIfTI đã đáp ứng) |
