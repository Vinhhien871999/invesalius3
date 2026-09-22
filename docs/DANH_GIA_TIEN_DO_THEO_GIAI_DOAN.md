# Đánh giá tiến độ phần mềm theo từng giai đoạn (Nội dung 1-6 của đề cương)

> Tài liệu này đối chiếu **từng mục yêu cầu cụ thể** trong `Ke_hoach_de_tai_InVesalius_CT3D.md` (mục 3 — "Bản đồ công việc cần code theo 6 nội dung") với **trạng thái thật đã kiểm chứng bằng runtime** (không phải đọc code suy đoán) trong `CT3D_FEATURE_AUDIT.md`, `CT3D_TEST_REPORT.md`, `CT3D_REMAINING_WORK.md`, `ROI_VIEWER_USER_GUIDE_VERIFICATION.md` — kết quả của 3 vòng audit (08/09/2026). Không có thay đổi code nào giữa vòng 3 và ngày viết tài liệu này (14/09/2026) — `git status` sạch, đúng commit `6fd5437b`.

**Cách đọc**: mỗi mục có 1 trong các trạng thái sau, lấy nguyên văn từ ma trận đã verify:
`WORKING` (đã chứng minh chạy đúng đầu-cuối bằng test thật) · `PARTIAL` (một phần chuỗi đã verify, phần còn lại chưa/lỗi nhỏ) · `NEEDS_RUNTIME_TEST` (có code, có UI, nhưng chưa thao tác/verify bằng runtime thật — **không phải WORKING**) · `NOT_IMPLEMENTED` (chỉ có UI/khai báo, không có logic backend) · `MISSING` (chưa có gì) · `NOT_CONNECTED` (backend tồn tại nhưng không có đường vào từ UI/pubsub) · `ĐÃ XOÁ` (quyết định kiến trúc, không phải bỏ dở).

**% hoàn thiện mỗi giai đoạn** tính theo trọng số: WORKING=100%, PARTIAL/NEEDS_RUNTIME_TEST=50%, NOT_CONNECTED=25% (có code, 0 UI-path), NOT_IMPLEMENTED/MISSING=0% — **không phải số cảm tính**, là trung bình cộng theo từng dòng trong ma trận, có ghi rõ công thức ở mỗi phần.

---

## Nội dung 1 — Nghiên cứu tổng quan (KHÔNG PHẢI CODE)

**Yêu cầu của đề cương**: tổng quan nguyên lý CT 3D (Marching Cubes, ray casting, DICOM), bảng so sánh InVesalius/3D Slicer/MITK/OsiriX/ITK-SNAP, cơ sở lý thuyết segmentation (thresholding/region growing/watershed/livewire, chọn 1-2 thuật toán + giải thích tại sao).

**Trạng thái thật**: **0% — hoàn toàn chưa làm, và đây KHÔNG PHẢI việc của phần mềm.** Đây là nội dung viết luận văn (literature review), không có dòng code nào tương ứng để kiểm chứng runtime. Phần mềm ĐÃ chọn đúng 2 thuật toán (Threshold + Region Growing — xem Nội dung 4), nên phần "giải thích tại sao chọn 2 thuật toán này" có thể viết dựa trên lý do kỹ thuật thật đã ghi trong `CT3D_ARCHITECTURE.md`/`CT3D_CHANGELOG.md` (Watershed bị loại vì trùng tính năng gốc InVesalius, không phải đóng góp nghiên cứu — xem Nội dung 4). Bảng so sánh phần mềm và tổng quan lý thuyết vẫn **cần bạn tự viết**, không có gì để "kiểm tra runtime" ở mục này.

---

## Nội dung 2 — Module quản lý và hiển thị dữ liệu CT

| Yêu cầu đề cương | Mã trong ma trận | Trạng thái thật | Ghi chú |
|---|---|---|---|
| Đọc DICOM, dựng series | A1 | **WORKING** | Test thật 3 bộ dữ liệu (2 CT + 1 MRI), loading 10-16s |
| Kiểm thử đa vendor (Siemens/GE/Philips) | A2 | **NEEDS_RUNTIME_TEST** | Chỉ xác nhận được **1 vendor thật** (SIEMENS, đọc tag DICOM thật) cho 1/3 bộ dữ liệu. GE/Philips/Canon: **chưa có dataset để test** — cần tự tải thêm (TCIA/LIDC-IDRI) |
| Nhiều series trong 1 study | A4 | **NEEDS_RUNTIME_TEST** | Code InVesalius gốc, chưa thử dataset đa-series thật |
| Spacing/orientation đọc đúng | A3 | **WORKING** | Verify bằng số liệu thật: đọc trực tiếp tag DICOM (`PixelSpacing`, `ImagePositionPatient`) qua gdcm, so khớp `Slice().spacing`, sai số <0.05mm; round-trip voxel↔world 11/11 khớp tuyệt đối. **Giới hạn đã biết**: không hiệu chỉnh gantry-tilt (bản thân InVesalius gốc cũng vậy) |
| 3 view Axial/Coronal/Sagittal | B1 | **WORKING** | |
| Scroll slice đồng bộ | B2 | **WORKING** | Verify: pick 3D → slice AXIAL đổi đúng |
| Window/Level (+ preset theo mô) | B3 | **WORKING** (phần lõi) | Cơ chế Window/Level hoạt động đúng; phần "thêm preset theo mô ROI" nếu InVesalius gốc chưa có — **chưa kiểm tra riêng, không có bằng chứng đã làm thêm** |
| Zoom/Pan 2D | B4 | **NEEDS_RUNTIME_TEST** | Interactor VTK gốc, chưa test tương tác chuột thật |

**Mức hoàn thiện Nội dung 2**: (100+50+50+100+100+100+100+50) / 8 = **81%**.

**Đánh giá**: phần lõi (đọc DICOM, hiển thị, spacing) đã vững chắc, có số liệu thật. Điểm yếu rõ nhất — và đúng là điều hội đồng sẽ hỏi ngay ("đã test đa vendor CT thật chưa?") — là **A2: chỉ xác nhận 1 vendor (SIEMENS)**, chưa có GE/Philips. Đây không phải lỗi code, mà là thiếu dữ liệu thử nghiệm (cần bạn tự đi lấy dataset TCIA/LIDC-IDRI).

---

## Nội dung 3 — Tái tạo và tương tác mô hình 3D

| Yêu cầu đề cương | Mã | Trạng thái thật | Ghi chú |
|---|---|---|---|
| Pipeline Marching Cubes hoạt động tốt, đo thời gian theo kích thước dữ liệu | C1 | **WORKING** | Đo thật: Extraction ~0.1-0.3s/nhóm lát, Cleaning mesh ~900K điểm ~0.9s |
| Rotate/Pan/Zoom 3D | C3 | **NEEDS_RUNTIME_TEST** | Camera VTK gốc, chưa test thao tác chuột thật |
| Multi-view đồng bộ (camera 3D ↔ vị trí lát cắt 2D) — **"điểm mới" đề cương đề xuất** | C4, C5 | **WORKING** | Đây chính là tính năng "liên kết 2D-3D thực sự" đề cương gợi ý (mục 3, Nội dung 3) — **đã làm, có bằng chứng runtime thật**: pick 1 điểm trên mesh 3D → toạ độ world thật → slice AXIAL tự nhảy đúng lát (verify bằng số liệu, không giả lập) |
| Clipping plane điều khiển bằng lát cắt 2D hiện tại | — | **MISSING** | Không có trong plugin, không có bằng chứng đã làm |
| Đo FPS render theo độ phân giải mesh | C2 | **WORKING** (một phần) | Đo thật: 122-158 FPS trên 3 bộ dữ liệu — **nhưng chỉ đo ở 1 mức chất lượng mesh ("Optimal *")**, chưa đo theo nhiều mức phân giải khác nhau như đề cương yêu cầu |
| Volume rendering (raycasting) thuần | C6 | **NOT_CONNECTED** | Hàm `Volume.OnShowVolume()` tồn tại nhưng **0 điểm gọi trong toàn bộ InVesalius gốc** (đã grep + kiểm tra binding động, không chỉ tên hàm) — đây là hạn chế của chính InVesalius gốc, không phải do plugin. FPS đo ở trên dùng surface rendering, không phải raycasting |
| Rebuild mesh khi mask đổi (liên kết 2D-3D khi chỉnh ROI) | C7 (=D9) | **PARTIAL** | Xem chi tiết ở Nội dung 4 (D9) — đây là mục quan trọng nhất còn dang dở |

**Mức hoàn thiện Nội dung 3**: (100+50+100+0+50+25+50) / 7 = **54%**.

**Đánh giá**: điểm mạnh thật sự — "multi-view đồng bộ 2D-3D" (C4/C5), đúng "điểm mới" đề cương gợi ý ở mục 3, **đã làm và verify được bằng số liệu thật**, đáng đưa vào luận văn như 1 đóng góp cụ thể. Điểm yếu: raycasting thuần không hoạt động được kể cả từ UI gốc (không phải việc plugin cần sửa), và **rebuild mesh khi sửa ROI (C7/D9) — chính là hướng đóng góp "A" mà đề cương khuyến nghị chọn — vẫn ở trạng thái PARTIAL**, chưa xác nhận runtime đầy đủ (xem Nội dung 4).

---

## Nội dung 4 — Phân đoạn và chỉnh sửa ROI (TRỌNG TÂM ĐỀ TÀI)

Đây là phần đề cương xác định là **quan trọng nhất**, cũng là phần plugin đầu tư nhiều code nhất. Đánh giá chi tiết từng yêu cầu:

### 4.1 Segmentation cơ bản (threshold, tinh chỉnh theo mô)
| Mã | Trạng thái | Ghi chú |
|---|---|---|
| D1 Threshold tạo mask | **WORKING** | mask_dict tăng đúng, mask thật xuất hiện |
| D2 Auto-threshold Otsu | **WORKING** | Test trên cả 3 bộ dữ liệu |
| D3 Chọn mask hiện tại | **WORKING** | |

### 4.2 Công cụ chỉnh sửa mask (brush/eraser, undo/redo)
| Mã | Trạng thái | Ghi chú |
|---|---|---|
| D4 Brush vẽ tay | **NEEDS_RUNTIME_TEST** | Chỉ verify được việc BẬT đúng chế độ vẽ (`Slice().state` đổi đúng) — **chưa verify bằng thao tác rê chuột thật vẽ lên ảnh**. Đây là giới hạn của phương pháp test tự động, không phải nghi ngờ code sai |
| D5 Eraser | **NEEDS_RUNTIME_TEST** | Tương tự D4 |
| D6 Kích thước brush | **WORKING** | |
| D7 Undo/Redo | **WORKING** | Verify bằng checksum: sửa → đổi → undo → khớp y hệt ban đầu |

**Lưu ý quan trọng đề cương yêu cầu**: "undo/redo dùng diff/patch thay vì snapshot toàn mảng để tránh tốn RAM". **Thực tế**: `core/mask_editor.py` (UndoRedoManager) dùng **snapshot toàn bộ mảng mỗi bước**, không phải diff/patch — đây là cách làm đơn giản hơn đề cương đề xuất, **hoạt động đúng** (đã verify) nhưng **chưa tối ưu theo đúng gợi ý kỹ thuật của đề cương**. Nếu muốn thể hiện "đóng góp kỹ thuật" ở phần này cho luận văn, đây là chỗ có thể cải tiến thêm (chưa làm).

### 4.3 Liên kết 2D-3D khi chỉnh ROI (hướng đóng góp A đề cương khuyến nghị)
| Mã | Trạng thái | Ghi chú |
|---|---|---|
| D9/C7 Rebuild mesh sau khi sửa mask | **PARTIAL** | Đây là mục **quan trọng nhất chưa đóng hẳn** trong toàn bộ đề tài. Đã làm: nút "Update 3D Surface" gọi đúng API thật (`"Create surface from index"`), chuỗi UI→pubsub→backend→viewer→render đã verify **11/15 check PASS** (actor thật vào renderer, render thành công, không tạo trùng). Đã tìm và sửa 1 bug thật (sentinel bị `do_threshold_to_all_slices()` ghi đè). **Chưa xác nhận được**: sau bản vá, polydata (hình dạng mesh) có thực sự đổi đúng theo mask mới hay không — 4 lần thử lại đều treo do máy thiếu RAM khi build surface (multiprocessing), không phải lỗi logic (0 crash) |
| Cách đơn giản (rebuild toàn bộ) | **Đã chọn** | Không làm "partial marching cubes" (cách nâng cao đề cương gợi ý) — quyết định đúng đắn cho thời gian có hạn, đã ghi rõ lý do (rebuild từng nét vẽ sẽ treo UI) |

**Đây là rủi ro lớn nhất cho buổi bảo vệ**: nếu hội đồng hỏi "chỉnh ROI xong 3D có tự cập nhật không, cho xem", bạn cần **tự thao tác tay xác nhận trước** (mở app thật, threshold mask nhỏ → build surface → vẽ brush → bấm Update 3D Surface → quan sát bằng mắt) — chưa có bằng chứng runtime tự động nào xác nhận việc này 100% từ máy này.

### 4.4 Region Growing bán tự động (điểm mới rõ ràng nhất theo đề cương)
| Mã | Trạng thái | Ghi chú |
|---|---|---|
| D10 Region Growing | **WORKING** | Pick seed 3D thật → mask thật tạo ra (16.264.693 voxel, verify runtime thật vòng 1). Tối ưu hiệu năng BFS Python (>15s) → `scipy.ndimage.label` (500ms, ~30 lần nhanh hơn) — có số liệu cho luận văn. Đã audit an toàn: validate seed, tolerance≥0, cảnh báo khi vùng >20% thể tích (Yes/No, có huỷ), thread-safety (không gọi GUI/VTK trực tiếp từ background thread) — verify 16/16 test thuật toán thuần. **Riêng lần chạy lại trên volume CT thật đầy đủ ở vòng 3 bị treo do máy thiếu RAM** (không phải lỗi) — bằng chứng vòng 1 (mask thật 16 triệu voxel) vẫn còn giá trị |

**Đây là mục mạnh nhất của đề tài** — đúng "điểm mới rõ ràng, dễ chứng minh hiệu quả bằng số liệu" như đề cương mô tả, có sẵn số liệu benchmark (30x speedup) để đưa vào luận văn.

### 4.5 Quản lý nhiều mask/segmentation
| Mã | Trạng thái | Ghi chú |
|---|---|---|
| D8 ROI List (đặt tên/ẩn-hiện/xoá) | **WORKING** | Đã refactor thành cache/view của `Project().mask_dict` thật (không giữ bản sao riêng — tránh 2 nguồn dữ liệu lệch nhau), tự đồng bộ kể cả khi sửa qua tab Masks gốc |
| G3 Giữ đúng ROI List sau Save/Open | **WORKING** | Tự rebuild đúng tên/màu/hiển thị sau mở lại project |

**Mức hoàn thiện Nội dung 4** (D1-D10, không tính D11/D12 đã xoá theo quyết định kiến trúc): (100+100+100+50+50+100+100+100+50+100) / 10 = **85%**.

**Đánh giá tổng thể Nội dung 4**: nền tảng (threshold/undo-redo/quản lý mask) vững, Region Growing là điểm sáng có số liệu tốt. Điểm yếu số 1 rõ ràng: **D9 (rebuild 3D sau khi sửa ROI) — chính là "hướng đóng góp A" đề cương khuyến nghị chọn — chưa xác nhận runtime 100%**, cần bạn tự tay verify trước khi bảo vệ.

---

## Nội dung 5 — Đo lường và Annotation

| Yêu cầu đề cương | Mã | Trạng thái | Ghi chú |
|---|---|---|
| Đo khoảng cách 2 điểm — 3D | E1 | **WORKING** | Verify: 2 điểm pick thật → 59.56mm |
| Đo khoảng cách 2 điểm — 2D | E2 | **NEEDS_RUNTIME_TEST** | Bật đúng công cụ đo gốc InVesalius; **chưa verify thao tác chuột thật click 2 điểm**. Quyết định kiến trúc: không tạo danh sách đo lường thứ 2 trong plugin (dùng tab Measures gốc) — tránh 2 nguồn dữ liệu lệch nhau |
| Đo diện tích 2D (polygon) | E3 | **NEEDS_RUNTIME_TEST** | Tương tự E2 |
| Đo thể tích (voxel × spacing) | E4 | **WORKING** | **Phát hiện + sửa 1 bug thật (vòng 3)**: công thức trước đó đếm nhầm cả viền đệm kỹ thuật của mask vào kết quả, lệch 0.01% (9575.83 → sửa còn 9574.80mm³, khớp tuyệt đối với tính tay) |
| Validate độ chính xác phép đo (đề cương mục 5, bắt buộc) | — | **CHƯA LÀM** | Đã đo được số liệu (E1/E4) nhưng **chưa so sánh với ground-truth/phantom đã biết kích thước hoặc phần mềm khác** như đề cương yêu cầu — đây là việc bắt buộc còn thiếu |
| Annotation (text, gắn toạ độ 3D) | F1, F2 | **WORKING** | Add/Edit/Goto/Prev/Next/Delete đều verify runtime thật |
| Vị trí annotation chính xác | F3 | **PARTIAL** | Lấy theo điểm pick 3D gần nhất — nếu chưa pick lần nào, mặc định về gốc toạ độ (0,0,0), không phải lỗi nhưng cần biết trước khi dùng |
| Lưu annotation kèm project | F4 | **WORKING** | Đã điều tra kỹ: core InVesalius có sẵn chỗ trống `project["annotations"]` trong định dạng `.inv3` nhưng **chưa từng được cài đặt** (ghi rỗng cứng, không đọc lại) — không phải extension point dùng được. Giải pháp: sidecar JSON riêng cạnh file `.inv3`. Verify full-cycle: add → save → close → open → khớp 100% |

**Mức hoàn thiện Nội dung 5**: (100+50+50+100+100+100+50+100) / 8 = **81%** (không tính riêng mục "validate độ chính xác" vì đó là yêu cầu Nội dung 5 nhưng thuộc phạm trù đánh giá — gộp vào Nội dung 6 bên dưới).

**Đánh giá**: annotation là điểm mạnh (tính năng mới hoàn toàn của plugin, có cả cơ chế lưu trữ đúng đắn). Điểm yếu: **chưa có bước validate độ chính xác phép đo với ground-truth** — đề cương ghi rõ đây là "yêu cầu bắt buộc cho phần mềm y tế, kể cả prototype" (mục 5 cuối).

---

## Nội dung 6 — Thiết kế giao diện và đánh giá phần mềm

### 6.1 Giao diện theo workflow
Plugin tổ chức theo đúng luồng đề cương mô tả (chọn/tạo mask → xem 2D/3D → chỉnh ROI → đo lường → ghi chú → xuất) qua 5 tab (Interaction/Segmentation/Measurements/Annotations/Export) — **đã làm, hợp lý**, nhưng **không có bằng chứng đã làm wireframe/mockup trước khi code** như đề cương yêu cầu (mục 6, "đưa vào luận văn như 1 phần thiết kế UX có phương pháp") — nếu chưa có, đây là việc cần bổ sung cho luận văn (không phải việc sửa phần mềm).

### 6.2 Lưu/Xuất kết quả
| Mã | Trạng thái | Ghi chú |
|---|---|---|
| G1 Save/Open project (.inv3) | **WORKING** | Full-cycle thật: Save → Close → Open → so khớp mask count/tên/màu/hiển thị/annotation/ROI List — đúng 100% |
| G2 Mask/Surface serialize đúng | **WORKING** | |
| H1 Export Mask (NIfTI/NRRD/NumPy) | **WORKING** (đã sửa bug vòng 3) | **Bug tìm thấy**: dropdown chọn định dạng trước đó hoàn toàn không có tác dụng (luôn ra NIfTI dù chọn gì) — đã sửa để dropdown điều khiển đúng, đã xoá "MetaImage" khỏi lựa chọn (không có hàm ghi file nào cho định dạng đó tồn tại) |
| H2-H4 Export Surface (STL/PLY/OBJ) | **WORKING** | File thật, đọc lại xác nhận có vertex/face |
| H5 Export Surface VTK PolyData | **WORKING** | Định dạng plugin tự thêm, ngoài danh sách gốc InVesalius |
| H6 Export ảnh slice (PNG/JPG/TIFF/BMP) | **WORKING** | |
| H7 Export DICOM-SEG | **MISSING** | Ngoài phạm vi — NIfTI đã đáp ứng nhu cầu tương tác cơ bản, nhưng DICOM-SEG mới là chuẩn PACS thật sự dùng trong lâm sàng |

**Còn 1 vấn đề chưa giải quyết**: checksum voxel của mask lệch nhẹ sau Save→Open (mọi thuộc tính khác đều khớp) — đã điều tra, loại trừ được 1 giả thuyết (chưa flush dữ liệu), nhưng **chưa tìm ra nguyên nhân gốc**.

### 6.3 Đánh giá phần mềm (đề cương tự nhận "đây là phần đang thiếu nhất" — mục 4 tài liệu kế hoạch)

**Đây là phần có tỷ lệ hoàn thành THẤP NHẤT trong toàn bộ đề tài — cần đọc kỹ mục này.**

| Yêu cầu đề cương (mục 4) | Trạng thái thật |
|---|---|
| Dataset thử nghiệm công khai có ground-truth (LIDC-IDRI/TCIA/Medical Segmentation Decathlon) | **CHƯA CÓ** — mới dùng 3 bộ mẫu chính thức đi kèm InVesalius (không có ground-truth segmentation) |
| Dice/Jaccard/Hausdorff so với ground-truth | **CHƯA LÀM** — không có ground-truth nên chưa đo được |
| Độ chính xác đo lường so với phantom/3D Slicer | **CHƯA LÀM** |
| Hiệu năng hệ thống (loading, dựng mesh, FPS, thời gian rebuild) | **ĐÃ CÓ MỘT PHẦN** — loading 10-16s (3 bộ dữ liệu), FPS 122-158, Region Growing 500ms (sau tối ưu). **Thiếu**: thời gian rebuild mesh khi chỉnh ROI (phụ thuộc D9 chưa xong), đo theo nhiều kích thước dữ liệu khác nhau |
| Usability (SUS score, người dùng thật) | **CHƯA LÀM** — cần tiếp cận bác sĩ/KTV thật, ngoài phạm vi kỹ thuật |
| Bảng so sánh InVesalius/plugin/3D Slicer | **CHƯA LÀM** |
| Tuyên bố pháp lý (prototype, không phải thiết bị y tế được cấp phép) | **CHƯA CÓ trong tài liệu nào** — cần bổ sung vào luận văn |
| Unit test bằng `pytest` cho module tính toán | **CHƯA CÓ** — toàn bộ test hiện tại là **script tích hợp chạy app thật** (không dùng framework pytest), không có bộ unit test độc lập cho từng hàm tính toán (đo lường, region growing...) như đề cương yêu cầu cụ thể |
| Quản lý phiên bản, CHANGELOG tách rõ code mới/kế thừa | **ĐÃ LÀM TỐT** — có `CT3D_CHANGELOG.md` ghi rõ từng commit, tách bạch phần plugin (100% mới) và phần lõi InVesalius (chỉ 1 bug fix nhỏ, có ghi lý do) |
| Định dạng xuất (STL/OBJ/PLY/NIfTI) | **ĐÃ LÀM** — xem H1-H6 ở trên. DICOM-SEG (chuẩn PACS) còn thiếu |

**Mức hoàn thiện phần "Đánh giá phần mềm" (mục 4 đề cương)**: ước tính **~15-20%** — chỉ có phần hiệu năng hệ thống (đo được nhờ tác dụng phụ của việc test kỹ thuật) và quản lý phiên bản là đạt; toàn bộ phần định lượng độ chính xác (Dice/Jaccard/Hausdorff/validate đo lường), usability, so sánh phần mềm, dataset chuẩn, tuyên bố pháp lý, và unit test `pytest` **đều chưa làm**.

---

## TỔNG HỢP: mục nào đã làm ĐẦY ĐỦ / làm nhưng CHƯA ĐẦY ĐỦ / CHƯA LIÊN KẾT / CHƯA LÀM

### Đã làm đầy đủ, có bằng chứng runtime thật (WORKING, tin cậy để demo)
Đọc DICOM (A1) · Spacing/toạ độ chính xác (A3) · 3 view 2D (B1-B3) · Marching Cubes (C1) · Render 3D + FPS (C2) · Pick 3D → nhảy đúng 2D (C4/C5, chính là "liên kết 2D-3D" điểm mới) · Threshold + Otsu (D1-D3) · Brush size + Undo/Redo (D6-D7, verify bằng checksum) · **Region Growing an toàn có cảnh báo** (D10, điểm mạnh nhất) · Quản lý ROI List 2 chiều thật (D8) · Đo khoảng cách 3D + thể tích (E1, E4 — vừa sửa 1 bug) · Annotation đầy đủ vòng đời + lưu trữ (F1-F2, F4) · Save/Open project full-cycle (G1-G3) · Export Mask/Surface/Ảnh (H1-H6, vừa sửa 1 bug).

### Đã làm nhưng CHƯA ĐẦY ĐỦ / còn PARTIAL — cần làm tiếp hoặc tự tay verify
1. **D9/C7 — Rebuild 3D sau khi sửa ROI**: đây là mục **quan trọng nhất chưa xong** (đúng hướng đóng góp trọng tâm đề cương). Code đúng theo đọc source, nhưng **chưa quan sát được kết quả cuối (hình dạng mesh đổi đúng) bằng runtime** — 4 lần thử tự động đều bị treo do máy thiếu RAM. **Bắt buộc tự tay kiểm tra trước khi bảo vệ.**
2. **F3 — Vị trí annotation**: đúng nhưng phụ thuộc đã pick điểm 3D trước đó chưa, dễ gây hiểu nhầm nếu người dùng không biết.
3. **Undo/Redo dùng snapshot thay vì diff/patch**: hoạt động đúng nhưng chưa theo đúng gợi ý tối ưu RAM của đề cương.

### Có code/UI nhưng CHƯA LIÊN KẾT hoặc CHƯA XÁC NHẬN được bằng thao tác thật
1. **D4/D5 — Brush/Eraser**: bật đúng chế độ, nhưng **chưa từng verify bằng thao tác rê chuột vẽ thật** — chỉ verify state chuyển đúng.
2. **E2/E3 — Đo 2D**: tương tự, bật đúng công cụ nhưng chưa verify click chuột thật.
3. **C3, B4 — Rotate/pan/zoom 3D và Zoom/Pan 2D**: interactor VTK gốc, chưa test thao tác chuột thật trong 2 vòng audit.
4. **Sync 2D → 3D** (checkbox tồn tại ở tab Interaction): **xác nhận CHẮC CHẮN chưa làm** — chỉ lưu 1 cờ bật/tắt, không có code nào đọc lại cờ này để làm bất cứ điều gì (đã grep toàn bộ plugin để xác nhận, không phải suy đoán).

### Chưa làm / ngoài phạm vi kỹ thuật (cần cho luận văn nhưng phần mềm chưa/không cần code)
1. **Toàn bộ Nội dung 1** (tổng quan lý thuyết, bảng so sánh phần mềm) — việc viết luận văn, không phải code.
2. **C6 — Volume rendering raycasting thuần**: không hoạt động được kể cả từ UI gốc InVesalius (hạn chế của chính InVesalius, đã xác nhận kỹ — không phải việc plugin sửa).
3. **Toàn bộ phần "Đánh giá phần mềm" (mục 4 đề cương)**: Dice/Jaccard/Hausdarff, validate đo lường với ground-truth, khảo sát Usability, bảng so sánh với 3D Slicer, dataset chuẩn TCIA/LIDC-IDRI, tuyên bố pháp lý, bộ unit test `pytest` độc lập — **đây là phần cần đầu tư thời gian nhiều nhất trong giai đoạn còn lại**, vì đề cương tự xác định đây là phần quyết định điểm số nhiều nhất và hiện là phần yếu nhất.
4. **H7 — Export DICOM-SEG**: chưa làm, NIfTI đã tạm đáp ứng.
5. **Kiểm thử đa vendor CT đầy đủ** (mới xác nhận 1/nhiều vendor).

---

## Bảng tổng kết % hoàn thiện theo giai đoạn (tính từ ma trận, không ước lượng cảm tính)

| Giai đoạn | % hoàn thiện | Điểm mạnh nhất | Điểm yếu nhất |
|---|---|---|---|
| Nội dung 1 — Tổng quan lý thuyết | 0% | — | Chưa viết (việc của luận văn, không phải code) |
| Nội dung 2 — Quản lý/hiển thị CT | 81% | Đọc DICOM + spacing chính xác, có số liệu | Đa vendor mới xác nhận 1/nhiều |
| Nội dung 3 — Tái tạo & tương tác 3D | 54% | Liên kết 2D-3D (pick 3D → nhảy đúng 2D) | Raycasting không dùng được (hạn chế InVesalius gốc); rebuild mesh (C7) còn PARTIAL |
| Nội dung 4 — Segmentation & ROI (TRỌNG TÂM) | 85% | Region Growing an toàn, có benchmark 30x | D9 (rebuild 3D sau sửa ROI) chưa xác nhận runtime xong |
| Nội dung 5 — Đo lường & Annotation | 81% | Annotation đầy đủ vòng đời + lưu trữ đúng | Chưa validate độ chính xác với ground-truth |
| Nội dung 6a — UI/Save-Load/Export | ~90% | Save/Open full-cycle đúng 100% (trừ 1 checksum nhỏ) | DICOM-SEG chưa có |
| Nội dung 6b — Đánh giá phần mềm (mục 4) | **~15-20%** | Hiệu năng hệ thống đã có số liệu | Dice/Jaccard/Usability/so sánh/pytest/dataset chuẩn — hầu như chưa làm |

**Kết luận ngắn gọn cho việc lập kế hoạch thời gian còn lại**: phần **code chức năng** (Nội dung 2-5) đã ở mức khá tốt (**54-85%**, phần lớn có bằng chứng runtime thật), chỉ còn 1 việc kỹ thuật quan trọng cần đóng dứt điểm (D9 — rebuild 3D). Phần **quyết định điểm số nhiều nhất theo chính đề cương tự nhận** — chương "Thực nghiệm & Đánh giá" (Nội dung 6b) — mới đạt khoảng 15-20%, nên đây phải là **ưu tiên số 1 cho giai đoạn tiếp theo**, không phải viết thêm tính năng mới.
