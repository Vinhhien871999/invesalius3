# Hướng dẫn sử dụng Plugin ROI Viewer

> Tài liệu này mô tả **chính xác từng nút bấm thật** trong plugin (tên nút lấy trực tiếp từ code, không diễn giải), theo đúng trình tự thao tác từ đầu, và **khác biệt cụ thể** so với InVesalius gốc (khi chưa cài plugin). Cập nhật theo mã nguồn sau vòng audit thứ 2 (08/09/2026). Dùng để demo, viết báo cáo NCKH, hoặc tự thao tác kiểm tra lại.

---

## 0. Trước khi có plugin, InVesalius làm được gì / không làm được gì

InVesalius gốc (chưa cài `roi_viewer`) đã có sẵn: đọc DICOM, hiển thị 3 mặt cắt, dựng mô hình 3D, threshold cơ bản, brush vẽ tay, watershed, đo khoảng cách/density polygon, xuất mask/surface — **nhưng** các thao tác này nằm rải rác ở nhiều task panel khác nhau (task_slice, task_surface, data_notebook...), không có nơi nào:
- Cho biết toạ độ 3D vừa click là gì và tự động nhảy đúng slice 2D tương ứng
- Quản lý nhiều ROI đã tạo theo tên tập trung tại 1 nơi (chỉ có danh sách mask theo số thứ tự ở tab Masks)
- Region Growing (mọc vùng bán tự động từ 1 điểm hạt giống 3D)
- Ghi chú (annotation) văn bản gắn vào một vị trí cụ thể trên ảnh, có lưu lại khi đóng/mở project
- Auto-threshold bằng thuật toán Otsu
- Chủ động rebuild lại surface 3D sau khi sửa mask (brush/undo/region growing) mà không phải vào lại task panel gốc
- Undo/redo nhanh bằng 1 nút riêng cho việc chỉnh mask (InVesalius có undo/redo nhưng nằm trong luồng brush riêng, không có nút "Save Checkpoint" tường minh)

Plugin `ROI Viewer` **không viết lại** các tính năng gốc — nó mở ra một cửa sổ riêng, đóng vai trò "bảng điều khiển tổng hợp", bấm nút trong đó sẽ **điều khiển trực tiếp** đúng tính năng thật của InVesalius (không phải bản sao/giả lập). Vì vậy mọi kết quả (mask, surface, số đo...) đều hiện luôn trong giao diện chính InVesalius như bình thường, và Save/Open project vẫn dùng đúng cơ chế `.inv3` gốc.

---

## 1. Khởi động — thao tác từ đầu

1. Mở InVesalius:
   - Cách 1: `python app.py` rồi vào **File → Import DICOM...** để chọn thư mục ảnh.
   - Cách 2 (nhanh hơn khi test): `python app.py -i <đường dẫn thư mục DICOM>` — tự import ngay khi khởi động.
2. Đợi import xong (progress bar chạy hết, 3 khung Axial/Coronal/Sagittal hiện ảnh thật).
3. Vào menu **Plugins → ROI Viewer** để mở cửa sổ plugin.
   - Cửa sổ có tiêu đề **"ROI Viewer - CT 3D Visualization"**, gồm 5 tab: **Interaction / Segmentation / Measurements / Annotations / Export**.
   - Có thể mở plugin **trước hay sau** khi import DICOM đều được — nếu mở SAU khi đã có sẵn mask/project, tab Segmentation sẽ **tự nạp đúng danh sách mask đã có** vào ROI List ngay khi cửa sổ hiện ra (không cần thao tác gì thêm).
   - Nếu bấm **Plugins → ROI Viewer** lần nữa trong khi cửa sổ đang mở, InVesalius chỉ đưa cửa sổ cũ ra trước (`Raise`), không mở cửa sổ thứ hai.
4. Đóng cửa sổ plugin bằng nút **[X]** như bình thường — an toàn để mở lại nhiều lần trong cùng phiên làm việc (không rò rỉ, không gây crash khi mở/đóng lặp lại).

---

## 2. Tab **Interaction** — tương tác & liên kết 2D-3D

| Điều khiển | Ý nghĩa | Khác gì so với InVesalius gốc |
|---|---|---|
| **Sync 3D → 2D** (checkbox, mặc định bật) | Khi pick 1 điểm 3D, 3 khung Axial/Sagittal/Coronal tự cuộn tới đúng lát cắt chứa điểm đó | InVesalius gốc không có cơ chế này |
| **Sync 2D → 3D** (checkbox) | Chỉ lưu 1 cờ bật/tắt trong bộ nhớ — **chưa có bất kỳ code nào đọc lại cờ này**, tick vào không có tác dụng quan sát được nào cả (xác nhận qua chạy thật + grep code, không phải suy đoán) | **CHƯA TRIỂN KHAI (NOT_IMPLEMENTED)** |
| **Pick Point in 3D** | Bấm 1 lần để "vũ trang" chế độ pick | Mới hoàn toàn |
| Ô toạ độ (X/Y/Z, chỉ đọc) | Hiện toạ độ thật (mm) của điểm vừa click | Mới |
| **Update delay (ms)** (slider) | Độ trễ khi đồng bộ liên tục | Mới |
| **Brush Size** / **Circle / Square** (ở tab này) | Cấu hình nhanh brush — **lưu ý**: cấu hình thật sự dùng khi vẽ nằm ở tab Segmentation mục 3.4, mục này chỉ hiển thị tham chiếu | — |

**Cách dùng thực tế**:
1. Cần đã có ít nhất 1 mask + 1 surface 3D hiển thị trong khung "Volume" ở cửa sổ chính (xem mục 3 để tạo).
2. Bấm **Pick Point in 3D**.
3. Click chuột trái vào một điểm trên khối 3D trong khung "Volume".
4. Quan sát: ô toạ độ cập nhật, 3 khung 2D tự nhảy tới đúng lát cắt chứa điểm đó (nếu **Sync 3D → 2D** đang bật).

---

## 3. Tab **Segmentation** — phân đoạn & quản lý ROI (trọng tâm plugin)

### 3.1 Threshold → tạo mask thật

1. Tick **Auto threshold (Otsu)** nếu muốn plugin tự tính khoảng ngưỡng bằng thuật toán Otsu trên dữ liệu thật (điền sẵn vào ô Min/Max) — **InVesalius gốc không có auto-threshold**, phải tự dò tay hoặc chọn preset có sẵn (Bone, Soft tissue...).
2. Hoặc tự nhập **Min / Max** thủ công (giống hệt threshold gốc của InVesalius, đơn vị HU với CT).
3. Bấm **Create Mask from Threshold** → mask thật được tạo, xuất hiện ngay ở tab "Masks" của InVesalius (panel bên trái) **và** trong **ROI List** bên dưới (mục 3.3).

### 3.2 Region Growing (seed-based) — mục hoàn toàn mới

Mọc vùng bán tự động: chọn 1 điểm hạt giống trên khối 3D, thuật toán tự lan ra các voxel lân cận có giá trị gần với điểm hạt giống (trong khoảng dung sai cho phép).

1. Nhập **Tolerance** (dung sai, mặc định 50, có thể để **0** = chỉ lấy đúng voxel có giá trị bằng hệt điểm hạt giống).
2. Bấm **Pick Seed Point (3D)** — nút chuyển sang trạng thái "đang chờ".
3. Click chuột trái vào 1 điểm trên khối 3D (khung "Volume") để chọn làm hạt giống.
4. Plugin tự tính toán (chạy nền, không treo giao diện) rồi tạo mask mới tên **"Region Growing N"**, xuất hiện trong ROI List.
5. **An toàn**: nếu vùng mọc ra quá lớn (>20% tổng thể tích — ngưỡng có thể chỉnh trong code, không phải giá trị tuỳ tiện), plugin hiện hộp thoại cảnh báo kèm số liệu thật (giá trị hạt giống, dung sai, số voxel, % thể tích, thể tích mm³) và hỏi **Yes/No** — chọn **No** để huỷ (không tạo mask), tránh tạo ra 1 "vùng quan tâm" chiếm gần hết cả khối ảnh (không còn ý nghĩa ROI).
6. Dòng chữ trạng thái ngay dưới nút luôn hiện thông tin cụ thể (số voxel, dung sai, % thể tích) sau mỗi lần grow, kể cả khi thất bại (ví dụ "không tìm thấy vùng nào, thử tăng dung sai").

> **Lưu ý dung sai**: dung sai càng lớn trên ảnh có dải giá trị rộng (ví dụ CT xương) càng dễ lan ra quá rộng — nên bắt đầu bằng dung sai nhỏ (10-30) rồi tăng dần nếu vùng grow chưa đủ.

### 3.3 ROI List — quản lý segmentation tập trung

Mọi mask tạo ra (từ Threshold, Region Growing, **hoặc từ tab Masks gốc của InVesalius**) đều tự động xuất hiện trong danh sách này dưới dạng `<tên> (mask #<số>)` — danh sách này **luôn đồng bộ 2 chiều thật** với dữ liệu mask thật của InVesalius (không phải bản sao riêng), kể cả khi bạn đổi tên/ẩn-hiện/xoá mask trực tiếp ở tab "Masks" gốc thay vì dùng nút dưới đây.

| Nút | Chức năng thật |
|---|---|
| Tick vào ô checkbox trước tên | **Ẩn/hiện** mask đó thật sự trên 2D/3D (giống nút con mắt ở tab Masks gốc) |
| Click chọn 1 dòng | **Chọn mask đó làm mask đang thao tác** (current mask) — mọi lệnh brush/đo lường/Update Surface sau đó áp dụng lên mask này |
| **Rename** | Đổi tên — cập nhật cả trong danh sách plugin lẫn tab "Masks" gốc của InVesalius |
| **Delete** | Xoá hẳn mask khỏi project (có hỏi xác nhận) |
| **Update 3D Surface from Selected ROI** | Dựng lại (hoặc dựng mới) mô hình 3D cho ĐÚNG mask đang chọn trong danh sách (nếu không chọn dòng nào, dùng mask hiện hành) — xem mục quan trọng bên dưới |

> **Vì sao cần bấm "Update 3D Surface" thủ công**: InVesalius gốc (kể cả không có plugin) **không tự động** cập nhật lại mô hình 3D mỗi khi mask bị sửa (vẽ brush, undo, region growing...) — đây là hành vi thật của InVesalius, không phải hạn chế riêng của plugin. Nút này đóng vòng lặp "sửa ROI → xem lại 3D" một cách chủ động, tránh việc tự động rebuild sau MỖI nét vẽ (sẽ làm treo giao diện vì dựng mô hình 3D là tác vụ nặng). **Sau khi sửa mask xong, luôn nhớ bấm nút này để thấy đúng kết quả mới nhất trên khối 3D** — nếu không bấm, khối 3D vẫn hiện hình dạng CŨ dù mask đã đổi.
> Việc dựng lại có thể mất vài giây đến hơn chục giây tuỳ kích thước mask — quan sát dòng "Status:" phía dưới cùng panel để biết đang xử lý.

### 3.4 Brush Tools (real 2D editor)
- **Draw / Erase**: chọn chế độ vẽ hay xoá.
- **Circle / Square**: hình dạng đầu cọ.
- **Brush size** (slider): kích thước cọ (px).
- **Enable Brush Tool**: bấm để **kích hoạt** — sau đó dùng **chuột vẽ trực tiếp trên khung 2D (Axial/Coronal/Sagittal) của InVesalius y như brush gốc**. Bấm lại (nút đổi thành "Disable Brush Tool") để tắt.

> Quan trọng: panel này **không tự vẽ thay bạn** — nó chỉ bật đúng công cụ vẽ tay thật của InVesalius và đồng bộ size/hình dạng/chế độ. Thao tác vẽ (rê chuột) vẫn làm trực tiếp trên khung 2D như dùng InVesalius bình thường. Cần chọn/tạo 1 mask trước (mục 3.1/3.3), nếu chưa có mask nào sẽ báo lỗi khi bật.

### 3.5 Undo / Redo (current mask)
- **Save Checkpoint**: lưu lại trạng thái hiện tại của mask đang chọn (làm mốc để quay lại).
- **Undo / Redo**: khôi phục/làm lại — hoạt động trên **toàn bộ ma trận voxel thật** của mask, nên **undo được cả những gì vừa vẽ bằng brush gốc của InVesalius**, không chỉ thao tác qua plugin.

---

## 4. Tab **Measurements** — đo lường

| Điều khiển | Cách dùng | Ghi chú |
|---|---|---|
| **3D** + **Start Distance** | Bấm, sau đó click 2 điểm liên tiếp trên khối 3D (khung Volume) | Kết quả (mm) hiện ngay trong ô "Result" của plugin **và** được lưu vào danh sách "Saved Measurements" bên dưới |
| **2D** + **Start Distance** | Bấm — kích hoạt công cụ đo khoảng cách 2D **gốc** của InVesalius | Bạn thao tác (click 2 điểm) trực tiếp trên khung 2D; **kết quả hiện ở tab "Measures" gốc của InVesalius** — plugin **cố tình không** tạo thêm 1 danh sách đo lường thứ hai cho phần này (xem mục 7) |
| **Measure Area (2D)** | Bấm — kích hoạt công cụ vẽ polygon đo diện tích/mật độ gốc | Vẽ polygon trực tiếp trên khung 2D; kết quả hiện ở tab "Measures" gốc |
| **Measure Volume** | Bấm 1 lần, không cần thao tác gì thêm | Tính thể tích thật của mask đang chọn (voxel count × spacing thật từ DICOM), hiện ngay trong ô "Result" |
| **Clear All** | Xoá danh sách đo lường (3D + volume) của plugin | |

---

## 5. Tab **Annotations** — ghi chú

1. Gõ nội dung vào ô **Text**, chọn màu (bảng màu hoặc 5 nút màu nhanh).
2. Bấm **Add at Current Position** → ghi chú được gắn vào **vị trí 3D vừa pick gần nhất** (ở tab Interaction hoặc lúc pick seed Region Growing) — nếu chưa pick điểm nào, vị trí mặc định là gốc toạ độ `(0,0,0)`, nên **pick 1 điểm trước** để ghi chú có toạ độ đúng.
3. Danh sách bên dưới hiện tất cả ghi chú. Chọn 1 dòng rồi dùng:
   - **Go to**: nhảy đúng slice 2D chứa ghi chú đó.
   - **Edit**: sửa nội dung text.
   - **Delete**: xoá.
   - **Prev / Next**: duyệt qua lại giữa các ghi chú.
4. **Annotation được lưu lại khi Save project** (xem mục 6) — đóng/mở lại `.inv3` sẽ thấy đúng danh sách ghi chú cũ, không mất.

> InVesalius gốc **không có** tính năng annotation dạng text gắn theo vị trí — đây là tính năng mới hoàn toàn của plugin.

---

## 6. Tab **Export** — lưu/xuất kết quả

| Nút | Kết quả | So với InVesalius gốc |
|---|---|---|
| **Export Mask** — chọn **NIfTI**: mở đúng dialog "Export Mask as NIfTI" **gốc** của InVesalius, tự động điền sẵn đúng mask đang chọn | File `.nii.gz` thật, đọc lại được bằng bất kỳ phần mềm NIfTI nào | InVesalius gốc yêu cầu tự vào menu và tự chọn mask trong danh sách; ở đây tự lấy đúng mask hiện hành |
| **Export Mask** — chọn **NumPy**: dùng dialog lưu file riêng của plugin | File `.npy` thật, đọc lại bằng `numpy.load()` | Mới — InVesalius gốc không xuất được NumPy |
| **Export Mask** — chọn **NRRD**: dùng dialog lưu file riêng của plugin | ⚠️ Máy chưa cài thư viện `pynrrd` → hiện thông báo lỗi rõ ràng, **chưa xuất được file thật** trên máy demo hiện tại. Cài `pip install pynrrd` để dùng được | Cơ chế đã nối đúng (`core/exporters.py`), chỉ thiếu thư viện |
| **Export Surface** (STL Binary/ASCII, PLY, OBJ, VTK PolyData) | Xuất file surface 3D thật (đã tạo ở mục 3.1/3.2, hoặc dựng lại ở 3.3) | STL/PLY/OBJ dùng đúng pipeline VTK gốc; **VTK PolyData** là định dạng thêm ngoài 3 định dạng gốc InVesalius hỗ trợ |
| **Export Current View** (PNG/JPG/TIFF/BMP, có Scale phóng to) | Xuất ảnh lát cắt 2D hiện tại, **đã áp dụng đúng Window/Level đang xem** | Mới — InVesalius gốc không có nút xuất nhanh 1 lát cắt ra ảnh |
| **Save / Save As...** | Lưu project `.inv3` — gọi đúng dialog lưu gốc của InVesalius, **và tự động lưu kèm toàn bộ Annotation** (file `.roi_annotations.json` cùng thư mục, cùng tên với `.inv3`) | Giống hệt InVesalius gốc cho phần mask/surface (đã có sẵn), **cộng thêm** annotation được lưu tự động (InVesalius gốc không lưu annotation vì đây là tính năng riêng của plugin) |

> **ROI List không cần lưu riêng**: tên/màu/hiển thị trong ROI List (mục 3.3) chính là dữ liệu thật của mask, đã tự động nằm trong `.inv3` khi Save — mở lại project sẽ thấy ROI List tự dựng lại đúng như cũ, không cần thao tác gì thêm.

---

## 7. Giới hạn đã biết / quyết định thiết kế (nói rõ để không hiểu nhầm là bug)

**Còn thật sự chưa hoàn thiện**:
1. **Brush vẽ tay & đo lường 2D**: việc rê chuột vẽ/đo vẫn phải làm trực tiếp trên khung 2D — plugin chỉ bật/tắt và cấu hình đúng công cụ gốc, không tự động thao tác hộ (đúng bản chất, không phải lỗi).
2. **Update 3D Surface**: với mask rất lớn (gần hết thể tích ảnh), việc dựng lại 3D có thể mất khá lâu — nên dùng cho mask kích thước vừa phải (ROI thật sự "quan tâm", không phải toàn bộ ảnh). **Trên máy ít RAM khả dụng (dưới ~5GB trống), bước này có thể mất rất lâu hoặc không hoàn tất** — đóng bớt các ứng dụng khác trước khi dùng chức năng này nếu gặp tình trạng "treo".
3. Annotation lấy vị trí 3D từ điểm pick **gần nhất** — cần pick trước ở tab Interaction để có toạ độ chính xác, nếu không sẽ là `(0, 0, 0)`.
4. **Region Growing** trên mask lớn/thể tích CT thật cũng cần đủ RAM tương tự mục 2 (tính toán trên hàng chục triệu voxel).
5. Sau khi **Save → đóng → mở lại** project, nội dung voxel của mask có sai khác rất nhỏ (đã xác nhận bằng checksum, không nhìn thấy bằng mắt) so với trước khi lưu — tên/màu/hiển thị/số lượng mask vẫn đúng 100%. Đang điều tra nguyên nhân (thuộc code gốc InVesalius, không phải plugin).

**Quyết định thiết kế (không phải thiếu sót)**:
1. **Đo khoảng cách/diện tích 2D không có danh sách riêng trong plugin** — cố ý remote-control công cụ đo gốc thay vì tạo thêm 1 nguồn dữ liệu đo lường thứ hai (tránh 2 danh sách lệch nhau). Kết quả luôn xem đúng ở tab "Measures" gốc của InVesalius.
2. **Watershed và các phép toán hình thái học (dilate/erode/mở-đóng vùng) không có trong plugin** — InVesalius gốc đã có Watershed thật riêng (dùng qua UI gốc), không cần plugin làm lại.

---

## 8. Trình tự demo đề xuất (cho báo cáo/bảo vệ)

1. Import DICOM (`python app.py -i <thư mục DICOM>`) → mở **Plugins → ROI Viewer**.
2. Tab **Segmentation** (3.1): tick *Auto threshold (Otsu)* → **Create Mask from Threshold** → thấy mask mới trong **ROI List**.
3. Tab **Segmentation** (3.3): bấm **Update 3D Surface from Selected ROI** → thấy khối 3D hiện ra ở khung "Volume".
4. Tab **Interaction**: **Pick Point in 3D** → click vào khối 3D → quan sát toạ độ + 3 khung 2D tự nhảy.
5. Tab **Segmentation** (3.2): nhập dung sai vừa phải (vd. 30) → **Pick Seed Point (3D)** → click 1 điểm khác trên khối 3D → thấy mask "Region Growing 1" mới xuất hiện trong ROI List.
6. Tab **Segmentation** (3.4): **Enable Brush Tool** → vẽ thêm/xoá bớt vài nét trên khung 2D → **Update 3D Surface from Selected ROI** lần nữa → quan sát khối 3D đổi hình theo đúng nét vừa vẽ.
7. Tab **Measurements**: chọn **3D** → **Start Distance** → click 2 điểm trên khối 3D → xem kết quả mm.
8. Tab **Annotations**: **Add at Current Position** → thấy ghi chú xuất hiện đúng vị trí vừa pick.
9. Tab **Export**: **Save** project → đóng InVesalius → mở lại, **File → Open Project** đúng file vừa lưu → mở lại **Plugins → ROI Viewer** → kiểm chứng: ROI List còn nguyên, ghi chú còn nguyên.
10. Tab **Export**: **Export Surface** → chọn STL → lưu file → mở bằng phần mềm xem STL bất kỳ để kiểm chứng.
