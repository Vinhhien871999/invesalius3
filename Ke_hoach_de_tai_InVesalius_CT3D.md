# PHÂN TÍCH & KẾ HOẠCH TRIỂN KHAI
## Đề tài: Nghiên cứu xây dựng phần mềm hỗ trợ trực quan hóa và thao tác ảnh CT 3D (dựa trên InVesalius)

---

## 1. ĐÁNH GIÁ TỔNG QUAN ĐỀ TÀI

### 1.1 Điểm mạnh
- Chọn xây dựng trên InVesalius là hợp lý: đây là mã nguồn mở, đã kiểm định lâm sàng (được CTI/Bộ Y tế Brazil dùng thực tế), viết bằng Python + wxPython + VTK, kiến trúc module hóa rõ ràng (theo mô hình MVC lỏng lẻo, giao tiếp qua pubsub). Việc "đứng trên vai người khổng lồ" giúp bạn tập trung nguồn lực vào phần đóng góp mới thay vì viết lại DICOM reader hay volume renderer từ đầu — điều mà một luận văn thạc sĩ (thường 6–12 tháng) không đủ thời gian làm tốt nếu làm từ số 0.
- Phạm vi thu hẹp về "lớp tương tác + ROI" là đúng hướng: tách biệt rõ cái đã có (nền tảng InVesalius) và cái sẽ làm mới (lớp tương tác/chỉnh sửa ROI).

### 1.2 Vấn đề cần xử lý ngay (quan trọng nhất)
**Đề cương hiện tại là một "danh sách tính năng", chưa phải một "câu hỏi nghiên cứu".** Hội đồng bảo vệ thạc sĩ sẽ hỏi: *"Đóng góp khoa học/kỹ thuật mới của anh/chị là gì, khác gì so với việc cài InVesalius rồi dùng?"* Nếu không trả lời được câu này bằng một luận điểm cụ thể, đề tài sẽ bị đánh giá là "tích hợp phần mềm" chứ không phải "nghiên cứu".

Bạn cần chọn **MỘT trong các hướng đóng góp cụ thể** sau đây (khuyến nghị chọn 1–2, không dàn trải hết 10 tính năng):

| Hướng đóng góp | Câu hỏi nghiên cứu ví dụ | Độ khó |
|---|---|---|
| **A. Liên kết 2D–3D đồng bộ thời gian thực** | Làm sao đồng bộ thao tác chỉnh ROI trên lát cắt 2D với mesh 3D theo thời gian thực mà không phải render lại toàn bộ surface (incremental mesh update)? | Trung bình-Cao |
| **B. Công cụ chỉnh sửa ROI bán tự động** | So sánh hiệu quả (thời gian, độ chính xác Dice) giữa chỉnh sửa mask thủ công (brush) và có hỗ trợ (region growing/livewire/GrabCut khởi tạo từ nét vẽ người dùng) | Trung bình |
| **C. Đo lường 3D có ràng buộc giải phẫu** | Đo khoảng cách/thể tích trên mô hình 3D đã tái tạo, đánh giá sai số so với đo tay trên phim CT gốc (ground truth) | Trung bình |
| **D. Giao diện tương tác tối ưu cho quy trình lâm sàng** | Đánh giá usability (SUS score, thời gian hoàn thành tác vụ) so với 3D Slicer/quy trình hiện tại của bác sĩ | Thấp-Trung bình (nghiêng về UX) |

→ **Hành động cụ thể**: Viết lại phần "Tính cấp thiết" và "Đóng góp mới" trong đề cương, nêu rõ 1 câu hỏi nghiên cứu chính + 1–2 câu hỏi phụ, thay vì chỉ liệt kê chức năng. Phần "Nội dung nghiên cứu" và "Sản phẩm dự kiến" giữ nguyên khung sản phẩm phần mềm, nhưng thêm phần đánh giá định lượng (xem mục 4).

---

## 2. KIẾN TRÚC INVESALIUS LIÊN QUAN (để bạn biết code ở đâu)

InVesalius3 (Python, wxPython, VTK, pubsub) có cấu trúc chính như sau (tên module có thể lệch nhẹ giữa các phiên bản, cần đối chiếu với clone thực tế của bạn):

```
invesalius/
├── reader/
│   └── dicom_reader.py, dicom.py     # Đọc DICOM, dựng series
├── data/
│   ├── slice_.py                     # Quản lý dữ liệu slice 2D, window/level
│   ├── viewer_slice.py               # Canvas hiển thị Axial/Coronal/Sagittal (VTK)
│   ├── viewer_volume.py              # Canvas hiển thị volume rendering + surface 3D
│   ├── mask.py                       # Đối tượng Mask (nhị phân, dùng cho segmentation)
│   ├── surface.py                    # Tạo mesh 3D từ mask (Marching Cubes/vtkContour)
│   ├── measures.py                   # Công cụ đo lường (nếu có)
│   ├── styles.py                     # Interactor styles (brush, pan, zoom...)
│   └── volume.py                     # Volume rendering (transfer function, presets)
├── gui/
│   ├── frame.py                      # Cửa sổ chính
│   ├── task_slice.py, task_surface.py # Panel công cụ theo tab
│   └── dialogs.py                    # Hộp thoại
├── project.py                        # Quản lý project (.inv3), lưu/mở
└── pubsub_messages / pubsub.py       # Cơ chế giao tiếp giữa các module (Publisher/Subscriber)
```

**Điểm mấu chốt cần hiểu trước khi code:**
1. InVesalius dùng **pattern pubsub** (pubsub.pub.sendMessage / subscribe) để các module giao tiếp lỏng lẻo — bạn PHẢI theo đúng pattern này khi thêm tính năng mới, không nên gọi trực tiếp chéo module vì sẽ phá vỡ kiến trúc và gây lỗi khó debug.
2. **Slice 2D và Volume 3D là hai pipeline VTK riêng biệt**, đồng bộ qua object `Mask` và các message pubsub (ví dụ khi mask thay đổi → gửi message → surface.py rebuild mesh → viewer_volume.py render lại). Đây chính là chỗ bạn sẽ động vào nhiều nhất cho phần "liên kết 2D-3D".
3. **Mask** là ảnh nhị phân 3D (numpy array) lưu vùng đã phân đoạn — chỉnh sửa ROI thực chất là chỉnh sửa mảng numpy này rồi trigger rebuild mesh.
4. **Surface = Marching Cubes (vtkDiscreteMarchingCubes hoặc vtkContourFilter) trên Mask** — mỗi lần mask đổi mà rebuild toàn bộ mesh sẽ rất chậm với volume lớn → đây chính là bài toán kỹ thuật cho hướng đóng góp A ở trên (incremental/partial remesh, hoặc dùng đa luồng/threading để không đơ giao diện).

→ **Hành động cụ thể**: Trước khi viết code mới, hãy dành 1–2 tuần đọc kỹ `data/slice_.py`, `data/mask.py`, `data/surface.py`, `data/viewer_volume.py`, `data/styles.py` và vẽ lại sơ đồ luồng dữ liệu (data flow diagram) — sơ đồ này chính là một phần bắt buộc phải có trong chương "Phân tích hệ thống" của luận văn.

---

## 3. BẢN ĐỒ CÔNG VIỆC CẦN CODE (theo 6 nội dung đã đề ra)

### Nội dung 1 — Nghiên cứu tổng quan (không code, viết luận văn)
- Tổng quan ảnh CT 3D: nguyên lý tái tạo (Marching Cubes, volume rendering ray casting), định dạng DICOM.
- Khảo sát phần mềm hiện có: InVesalius, 3D Slicer, MITK, OsiriX/Horos, ITK-SNAP — **bảng so sánh tính năng** là bắt buộc, hội đồng sẽ hỏi "tại sao không dùng 3D Slicer".
- Cơ sở lý thuyết segmentation: thresholding, region growing, watershed, livewire — chọn 1–2 thuật toán sẽ dùng và giải thích tại sao.

### Nội dung 2 — Module quản lý và hiển thị dữ liệu CT
Đã có sẵn phần lớn trong InVesalius (`reader/dicom_reader.py`, `data/slice_.py`, `data/viewer_slice.py`). Việc cần làm:
- [ ] Kiểm thử với bộ DICOM đa dạng (khác vendor máy CT: Siemens, GE, Philips) để đảm bảo tương thích — ghi nhận vào luận văn như một phần "đánh giá tính ổn định".
- [ ] Nếu cần: cải tiến UI quản lý series (danh sách study/series, thumbnail preview) nếu bản gốc chưa đủ trực quan cho quy trình lâm sàng của bạn.
- [ ] Window/Level: có sẵn — chỉ cần thêm preset theo mô ROI (bone, soft tissue, lung...) nếu chưa có, đây là việc nhỏ, code nhanh.

### Nội dung 3 — Tái tạo và tương tác mô hình 3D
- [ ] Xác nhận pipeline Marching Cubes hiện có (`data/surface.py`) hoạt động tốt với volume lớn (đo thời gian dựng mesh theo kích thước dữ liệu — số liệu này cần cho chương đánh giá).
- [ ] **Tương tác 3D**: xoay, pan, zoom, clip plane — kiểm tra VTK interactor style hiện có; nếu muốn "điểm mới", thêm:
  - Multi-view đồng bộ (camera 3D đồng bộ với vị trí lát cắt 2D đang xem — dùng crosshair 3D).
  - Clipping plane tương tác được điều khiển bằng lát cắt 2D hiện tại (liên kết 2D-3D thực sự, không chỉ hiển thị song song).
- [ ] Đo hiệu năng render (FPS) với các mức độ phân giải mesh khác nhau — cần cho phần đánh giá kỹ thuật.

### Nội dung 4 — Phân đoạn và chỉnh sửa vùng quan tâm (ROI) — **TRỌNG TÂM CỦA ĐỀ TÀI**
Đây là phần cần đầu tư code nhiều nhất và cũng là nơi thể hiện đóng góp khoa học:
- [ ] **Segmentation cơ bản** (đã có sẵn phần threshold trong InVesalius) — kiểm tra, tinh chỉnh ngưỡng theo loại mô.
- [ ] **Công cụ chỉnh sửa mask (brush/eraser)** — đã có sẵn `data/styles.py` (EditorTool), cần review và có thể mở rộng: brush hình tròn/vuông có thể điều chỉnh kích thước, undo/redo nhiều bước (kiểm tra xem có sẵn hay cần code thêm — undo/redo cho thao tác trên mảng 3D lớn cần thiết kế cẩn thận, tránh copy toàn bộ mảng mỗi bước → dùng diff/patch thay vì snapshot).
- [ ] **Liên kết 2D–3D khi chỉnh ROI** (nếu chọn hướng A): khi người dùng vẽ trên lát cắt 2D, mesh 3D cập nhật theo. Cách làm thực tế:
  - Cách đơn giản: rebuild toàn bộ mesh sau mỗi lần chỉnh (dễ code, nhưng chậm với volume lớn — chấp nhận được nếu chỉ để demo prototype).
  - Cách nâng cao (điểm cộng học thuật): chỉ rebuild vùng bounding-box bị thay đổi (partial marching cubes) — đây là phần có thể viết thành "thuật toán cải tiến" trong luận văn, kèm benchmark thời gian trước/sau cải tiến.
- [ ] **Region growing bán tự động**: người dùng click 1 điểm hạt giống (seed) trên lát cắt, thuật toán tự lan ra vùng có cường độ tương đồng — VTK có `vtkImageConnectivityFilter` hoặc dùng SimpleITK (`sitk.ConnectedThreshold`) tích hợp thêm vào InVesalius. Đây là điểm mới rõ ràng, dễ chứng minh hiệu quả bằng số liệu (so sánh thời gian thao tác thủ công vs. bán tự động).
- [ ] **Quản lý nhiều mask/segmentation** (đặt tên, ẩn/hiện, xóa, gộp) — review UI hiện có trong InVesalius, có thể đã đủ.

### Nội dung 5 — Đo lường và Annotation (bạn có nêu trong phần bổ sung nhưng chưa có trong 5 nội dung gốc — CẦN THÊM VÀO ĐỀ CƯƠNG CHÍNH THỨC, xem mục 4)
- [ ] Đo khoảng cách 2 điểm trên 2D và 3D (`vtkDistanceWidget` hoặc tự tính Euclidean distance theo spacing thực từ DICOM header).
- [ ] Đo diện tích (trên lát cắt 2D — polygon area) và thể tích (đếm voxel trong mask × spacing — công thức đơn giản nhưng cần validate).
- [ ] Annotation: text label, mũi tên, điểm đánh dấu gắn vào tọa độ 3D, lưu kèm project.
- [ ] **Quan trọng**: mọi phép đo phải được validate độ chính xác (xem mục 4.2) — đây là yêu cầu bắt buộc cho phần mềm y tế, kể cả prototype.

### Nội dung 6 — Thiết kế giao diện và đánh giá phần mềm
- [ ] Redesign/tối ưu panel công cụ cho quy trình: chọn series → xem 2D/3D → segment → chỉnh ROI → đo lường → xuất kết quả (workflow-oriented UI, không chỉ bê nguyên giao diện gốc).
- [ ] Wireframe/mockup trước khi code (Figma hoặc vẽ tay) — đưa vào luận văn như một phần thiết kế UX có phương pháp.
- [ ] **Đánh giá phần mềm** — đây là phần đề cương đang thiếu nhất, xem chi tiết mục 4.

---

## 4. NHỮNG GÌ ĐỀ CƯƠNG ĐANG THIẾU — CẦN BỔ SUNG ĐỂ HOÀN THIỆN LUẬN VĂN THẠC SĨ

Đây là phần quan trọng nhất của phân tích này. Một luận văn thạc sĩ kỹ thuật/CNTT y sinh **không thể chỉ nộp source code + báo cáo mô tả tính năng**. Hội đồng chấm sẽ đánh giá dựa trên các tiêu chí sau mà đề cương hiện chưa đề cập:

### 4.1 Dữ liệu thử nghiệm (Dataset)
- Đề cương chưa nói sẽ lấy dữ liệu CT ở đâu để thử nghiệm. Cần:
  - Dùng bộ dữ liệu công khai đã được ẩn danh, có sẵn ground-truth segmentation để dùng: **LIDC-IDRI, TCIA (The Cancer Imaging Archive), Medical Segmentation Decathlon** — các bộ này hợp pháp, không vướng vấn đề đạo đức/pháp lý dữ liệu bệnh nhân thật.
  - Nếu có điều kiện hợp tác bệnh viện: cần **giấy phép đạo đức nghiên cứu (IRB/Hội đồng đạo đức)** và ẩn danh hóa dữ liệu (de-identification) — nêu rõ trong đề cương nếu dự định dùng dữ liệu thật, vì đây thường là yêu cầu bắt buộc của hội đồng.

### 4.2 Phương pháp đánh giá định lượng (hiện đề cương hoàn toàn thiếu)
Không thể chỉ nói "đã xây dựng chức năng X" mà cần **đo lường được**:
- **Độ chính xác segmentation/chỉnh sửa ROI**: chỉ số Dice Similarity Coefficient, Jaccard Index, Hausdorff Distance so với ground truth.
- **Độ chính xác đo lường**: so sánh khoảng cách/thể tích đo trên phần mềm với giá trị tham chiếu (phantom đã biết kích thước, hoặc so với 3D Slicer làm baseline).
- **Hiệu năng hệ thống**: thời gian load DICOM series, thời gian dựng mesh 3D, FPS khi tương tác, thời gian rebuild mesh khi chỉnh ROI — theo các kích thước dữ liệu khác nhau (512×512×N slice).
- **Usability**: nếu có thể tiếp cận vài bác sĩ/kỹ thuật viên hình ảnh y khoa, dùng thang đo **System Usability Scale (SUS)** hoặc phỏng vấn có cấu trúc, đo thời gian hoàn thành tác vụ chuẩn (ví dụ: "khoanh vùng khối u và đo thể tích trong X phút").

→ **Đây chính là chương "Thực nghiệm và đánh giá" bắt buộc phải có, và là phần quyết định điểm số nhiều nhất.**

### 4.3 So sánh với hệ thống hiện có
Bảng so sánh định tính + định lượng giữa: InVesalius gốc / phần mềm của bạn / 3D Slicer (hoặc MITK) — về tốc độ, độ chính xác, mức độ dễ dùng cho tác vụ ROI.

### 4.4 Vấn đề pháp lý/đạo đức cần nêu rõ (dù chỉ là prototype)
- Tuyên bố rõ: phần mềm là **prototype nghiên cứu, không phải thiết bị y tế được cấp phép (not for clinical diagnostic use)** — cần ghi rõ trong luận văn để tránh hiểu nhầm về phạm vi ứng dụng.
- Nếu dùng dữ liệu bệnh nhân thật: cam kết bảo mật, ẩn danh hóa.

### 4.5 Kiểm thử phần mềm (Software Testing) — thường bị bỏ qua
- Unit test cho các module tính toán (đo lường, tính thể tích, region growing) — dùng `pytest`.
- Test tích hợp: quy trình end-to-end (load DICOM → segment → export).
- Ghi log lỗi/crash khi test với dữ liệu bất thường (thiếu slice, sai spacing...).

### 4.6 Quản lý phiên bản & tài liệu kỹ thuật
- Repo Git riêng (fork từ invesalius3), commit rõ ràng, CHANGELOG ghi lại phần code mới so với bản gốc — hội đồng có thể yêu cầu chứng minh phần nào là của bạn viết.
- **Bắt buộc**: tách rõ trong báo cáo/code phần nào kế thừa nguyên bản, phần nào chỉnh sửa, phần nào viết mới hoàn toàn (ví dụ bằng comment `# NEW:` hoặc tài liệu riêng liệt kê diff).
- Tuân thủ giấy phép GPL của InVesalius khi công bố/nộp báo cáo (InVesalius dùng GPLv2) — nêu rõ trong luận văn để tránh vấn đề bản quyền.

### 4.7 Định dạng xuất kết quả
- Đề cương có nêu "xuất mô hình 3D định dạng phù hợp" — cần cụ thể hóa: **STL, OBJ, PLY** (in 3D/CAD), **VRML** (đã hỗ trợ sẵn trong InVesalius). Với mask/segmentation: xuất **DICOM-SEG** hoặc **NIfTI** để tương thích các phần mềm y tế khác — đây là điểm cộng vì thể hiện hiểu biết chuẩn tương tác dữ liệu y tế (interoperability).

---

## 5. LỘ TRÌNH TRIỂN KHAI ĐỀ XUẤT (giả định luận văn ~6-9 tháng)

| Giai đoạn | Thời gian | Công việc |
|---|---|---|
| 1. Nghiên cứu & thiết lập | 3-4 tuần | Đọc kiến trúc InVesalius, setup môi trường dev, build lại từ source, đọc tài liệu CT/segmentation, hoàn thiện đề cương với câu hỏi nghiên cứu rõ ràng |
| 2. Thiết kế | 2-3 tuần | Vẽ kiến trúc hệ thống, sơ đồ luồng dữ liệu 2D-3D, wireframe UI, chọn thuật toán segmentation/region growing cụ thể |
| 3. Phát triển lõi | 6-8 tuần | Code module quản lý/hiển thị CT (kiểm thử + cải tiến nhỏ), tái tạo & tương tác 3D |
| 4. Phát triển trọng tâm (ROI) | 6-8 tuần | Chỉnh sửa ROI, liên kết 2D-3D, region growing bán tự động, đo lường, annotation |
| 5. Hoàn thiện UI + tích hợp | 3-4 tuần | Thiết kế lại giao diện theo workflow, quản lý mask, xuất/lưu kết quả |
| 6. Thực nghiệm & đánh giá | 4-5 tuần | Thu thập dataset, chạy benchmark định lượng (Dice, thời gian, FPS), khảo sát usability nếu có thể |
| 7. Viết báo cáo | 3-4 tuần | Hoàn thiện luận văn, chuẩn bị bảo vệ |

---

## 6. RỦI RO KỸ THUẬT CẦN LƯỜNG TRƯỚC

1. **wxPython + VTK** là stack khá cũ, cài đặt môi trường có thể gặp vấn đề tương thích Python version — nên dùng đúng phiên bản Python mà repo InVesalius yêu cầu (kiểm tra `requirements.txt`/`pyproject.toml` của repo, thường Python 3.9-3.11 tùy nhánh).
2. **Rebuild mesh mỗi lần chỉnh ROI trên volume lớn** dễ làm giao diện đơ (block main thread) — cần đưa vào thread riêng hoặc debounce (chỉ rebuild sau khi người dùng ngừng thao tác một khoảng thời gian ngắn).
3. **Undo/redo trên mảng numpy 3D lớn**: nếu snapshot toàn bộ mảng mỗi thao tác sẽ tốn RAM nhanh — cân nhắc lưu diff (chỉ vùng thay đổi) thay vì toàn bộ mảng.
4. **Không có quyền truy cập dữ liệu bệnh viện thật**: dùng dataset công khai (mục 4.1) để không bị chặn tiến độ vì thủ tục đạo đức nghiên cứu.
5. **Phạm vi quá rộng**: nếu làm hết cả 6 nội dung ở mức "đầy đủ tính năng như InVesalius gốc" sẽ không kịp thời gian — hãy làm nội dung 2,3 ở mức "kế thừa + kiểm thử", dồn lực cho nội dung 4,5 (ROI, đo lường) là phần đóng góp chính.

---

## 7. TÓM TẮT VIỆC CẦN LÀM NGAY (checklist ưu tiên)

- [ ] Viết lại phần "đóng góp mới" của đề cương theo 1 câu hỏi nghiên cứu cụ thể (mục 1.2)
- [ ] Thêm hẳn "Nội dung 5: Đo lường & Annotation" và "Nội dung: Thực nghiệm & Đánh giá" vào danh sách nội dung nghiên cứu chính thức (hiện đang ẩn trong phần bổ sung)
- [ ] Xác định nguồn dataset thử nghiệm cụ thể (LIDC-IDRI/TCIA) và trích dẫn
- [ ] Clone repo, build thành công, đọc kỹ `data/slice_.py`, `data/mask.py`, `data/surface.py`, `data/viewer_volume.py`, `data/styles.py`
- [ ] Vẽ sơ đồ kiến trúc + luồng dữ liệu hệ thống (đưa vào đề cương)
- [ ] Thiết kế phương pháp đánh giá định lượng (Dice, thời gian, độ chính xác đo lường) trước khi bắt đầu code, không để tới cuối mới nghĩ đến
- [ ] Thiết lập Git riêng, quy ước đánh dấu code mới vs. code kế thừa
