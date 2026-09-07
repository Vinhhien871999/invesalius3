# Hướng dẫn sử dụng Plugin ROI Viewer

> Tài liệu này mô tả **chính xác từng nút bấm thật** trong plugin (tên nút lấy trực tiếp từ code, không diễn giải), và **khác biệt cụ thể** so với InVesalius gốc (khi chưa cài plugin). Dùng để demo, viết báo cáo NCKH, hoặc tự thao tác kiểm tra lại.

---

## 0. Trước khi có plugin, InVesalius làm được gì / không làm được gì

InVesalius gốc (chưa cài `roi_viewer`) đã có sẵn: đọc DICOM, hiển thị 3 mặt cắt, dựng mô hình 3D, threshold cơ bản, brush vẽ tay, đo khoảng cách/density polygon, xuất mask/surface — **nhưng** các thao tác này nằm rải rác ở nhiều task panel khác nhau (task_slice, task_surface, data_notebook...), không có nơi nào:
- Cho biết toạ độ 3D vừa click là gì và tự động nhảy đúng slice 2D tương ứng
- Quản lý nhiều ROI đã tạo theo tên (chỉ có danh sách mask theo số thứ tự)
- Ghi chú (annotation) văn bản gắn vào một vị trí cụ thể trên ảnh
- Auto-threshold bằng thuật toán Otsu
- Undo/redo nhanh bằng 1 nút riêng cho việc chỉnh mask (InVesalius có undo/redo nhưng nằm trong luồng brush riêng, không có nút "Save Checkpoint" tường minh)

Plugin `ROI Viewer` **không viết lại** các tính năng trên — nó mở ra một cửa sổ riêng, đóng vai trò "bảng điều khiển tổng hợp", bấm nút trong đó sẽ **điều khiển trực tiếp** đúng tính năng thật của InVesalius (không phải bản sao/giả lập). Vì vậy mọi kết quả (mask, surface, số đo...) đều hiện luôn trong giao diện chính InVesalius như bình thường.

---

## 1. Khởi động

1. Mở InVesalius như bình thường (`python app.py` hoặc double-click, hoặc `python app.py -i <thư mục DICOM>` để tự import).
2. Import DICOM: **File → Import DICOM...** (hoặc dùng panel "1. Load data" bên trái).
3. Vào **Plugins → ROI Viewer** để mở cửa sổ plugin. Cửa sổ có tiêu đề **"ROI Viewer - CT 3D Visualization"**, gồm 5 tab: **Interaction / Segmentation / Measurements / Annotations / Export**.

> Lưu ý: mở plugin **sau khi** đã import DICOM để các tab đọc đúng dữ liệu project hiện tại.

---

## 2. Tab **Interaction** — tương tác & liên kết 2D-3D (khác biệt: F6-F7)

| Điều khiển | Ý nghĩa | Khác gì so với InVesalius gốc |
|---|---|---|
| **Pick Point in 3D** | Bấm 1 lần để "vũ trang" chế độ pick; sau đó **click chuột trái vào khung "Volume" (3D)** ở cửa sổ chính | InVesalius gốc không có cơ chế pick điểm 3D → tự nhảy đúng slice 2D. Đây là tính năng mới hoàn toàn. |
| **Sync 3D → 2D** (checkbox, mặc định bật) | Khi pick 1 điểm 3D, 3 khung Axial/Sagittal/Coronal tự cuộn tới đúng lát cắt chứa điểm đó | Mới |
| **Sync 2D → 3D** | Cấu hình đồng bộ chiều ngược lại (đang ở mức khai báo, chưa có nút thao tác riêng) | Mới (một phần) |
| **Update delay (ms)** | Độ trễ khi đồng bộ liên tục | Mới |

**Cách dùng thực tế**: đã tạo ít nhất 1 mask/surface (xem mục 3) để có hình khối hiển thị trong khung "Volume" → bấm **Pick Point in 3D** → click vào một điểm trên khối 3D → quan sát 3 khung 2D tự nhảy tới đúng vị trí.

---

## 3. Tab **Segmentation** — phân đoạn & quản lý ROI (khác biệt: F8-F9 + "quản lý segmentation")

### 3.1 Threshold → tạo mask thật
- **Auto threshold (Otsu)** (checkbox): tự tính khoảng ngưỡng bằng thuật toán Otsu trên dữ liệu thật, điền sẵn vào ô Min/Max — **InVesalius gốc không có auto-threshold**, phải tự dò tay hoặc chọn preset có sẵn (Bone, Soft tissue...).
- **Min / Max**: khoảng ngưỡng thủ công (giống hệt threshold gốc của InVesalius).
- **Create Mask from Threshold**: tạo mask thật (xuất hiện luôn ở tab "Masks" của InVesalius, panel bên trái).

### 3.2 ROI List — mục hoàn toàn mới, "quản lý segmentation"
Mỗi lần tạo mask ở trên, nó tự động xuất hiện trong danh sách này dưới dạng `<tên> (mask #<số>)`.

| Nút | Chức năng thật |
|---|---|
| Tick vào ô checkbox trước tên | **Ẩn/hiện** mask đó thật sự trên 2D/3D (giống nút con mắt ở tab Masks gốc) |
| Click chọn 1 dòng | **Chọn mask đó làm mask đang thao tác** (current mask) — mọi lệnh brush/đo lường sau đó áp dụng lên mask này |
| **Rename** | Đổi tên — cập nhật cả trong danh sách plugin lẫn tab "Masks" gốc của InVesalius |
| **Delete** | Xoá hẳn mask khỏi project (có hỏi xác nhận) |

> InVesalius gốc chỉ có danh sách mask đơn giản (tên, threshold, nguồn gốc) ở tab "Masks" — không có khái niệm "ROI" độc lập với tên/màu/hiển thị quản lý tập trung như trên.

### 3.3 Brush Tools (real 2D editor)
- **Draw / Erase**: chọn chế độ vẽ hay xoá
- **Circle / Square**: hình dạng đầu cọ
- **Brush size**: kích thước cọ (px)
- **Enable Brush Tool**: bấm để **kích hoạt** — sau đó dùng **chuột vẽ trực tiếp trên khung 2D (Axial/Coronal/Sagittal) của InVesalius y như brush gốc**. Bấm lại để tắt.

> Quan trọng: panel này **không tự vẽ thay bạn** — nó chỉ bật đúng công cụ vẽ tay thật của InVesalius và đồng bộ size/hình dạng/chế độ. Thao tác vẽ (rê chuột) vẫn làm trực tiếp trên khung 2D như dùng InVesalius bình thường.

### 3.4 Undo / Redo (current mask)
- **Save Checkpoint**: lưu lại trạng thái hiện tại của mask đang chọn (làm mốc để quay lại)
- **Undo / Redo**: khôi phục/làm lại — hoạt động trên **toàn bộ ma trận voxel thật** của mask, nên **undo được cả những gì vừa vẽ bằng brush gốc của InVesalius**, không chỉ thao tác qua plugin.

---

## 4. Tab **Measurements** — đo lường (khác biệt: F10-F11)

| Điều khiển | Cách dùng | Ghi chú |
|---|---|---|
| **3D** + **Start Distance** | Bấm, sau đó click 2 điểm liên tiếp trên khối 3D (khung Volume) | Kết quả (mm) hiện ngay trong ô "Result" của plugin **và** được lưu vào danh sách "Saved Measurements" bên dưới |
| **2D** + **Start Distance** | Bấm — kích hoạt công cụ đo khoảng cách 2D **gốc** của InVesalius | Bạn thao tác (click 2 điểm) trực tiếp trên khung 2D; **kết quả hiện ở tab "Measures" gốc của InVesalius** (chưa đọc ngược vào danh sách của plugin — xem mục Giới hạn) |
| **Measure Area (2D)** | Bấm — kích hoạt công cụ vẽ polygon đo diện tích/mật độ gốc | Vẽ polygon trực tiếp trên khung 2D; kết quả hiện ở tab "Measures" gốc |
| **Measure Volume** | Bấm 1 lần, không cần thao tác gì thêm | Tính thể tích thật của mask đang chọn (voxel count × spacing), hiện ngay trong ô "Result" |
| **Clear All** | Xoá danh sách đo lường của plugin | |

---

## 5. Tab **Annotations** — ghi chú (khác biệt: F12, thuộc "điểm mới")

1. Gõ nội dung vào ô **Text**, chọn màu (bảng màu hoặc 5 nút màu nhanh).
2. Bấm **Add at Current Position** → ghi chú được gắn vào **vị trí 3D vừa pick gần nhất** (nếu chưa pick điểm nào, vị trí mặc định là gốc toạ độ — nên **pick 1 điểm ở tab Interaction trước** để ghi chú có toạ độ đúng).
3. Danh sách bên dưới hiện tất cả ghi chú. Chọn 1 dòng rồi dùng:
   - **Go to**: nhảy đúng slice 2D chứa ghi chú đó
   - **Edit**: sửa nội dung text
   - **Delete**: xoá
   - **Prev / Next**: duyệt qua lại giữa các ghi chú

> InVesalius gốc **không có** tính năng annotation dạng text gắn theo vị trí — đây là tính năng mới hoàn toàn của plugin.

---

## 6. Tab **Export** — lưu/xuất kết quả (khác biệt: F13-F14)

| Nút | Kết quả | So với InVesalius gốc |
|---|---|---|
| **Export Mask** (chọn định dạng NIfTI/NRRD/MetaImage) | Mở đúng dialog "Export Mask as NIfTI" **gốc** của InVesalius, tự động điền sẵn đúng mask đang chọn | InVesalius gốc yêu cầu tự vào menu và tự chọn mask trong danh sách; ở đây tự lấy đúng mask hiện hành |
| **Export Surface** (STL Binary/ASCII, PLY, OBJ, VTK PolyData) | Xuất file surface 3D thật (đã tạo ở "3D surfaces" trong InVesalius) | STL/PLY/OBJ dùng đúng pipeline VTK gốc; **VTK PolyData** là định dạng thêm ngoài 3 định dạng gốc InVesalius hỗ trợ |
| **Export Current View** (PNG/JPG/TIFF/BMP, có Scale phóng to) | Xuất ảnh lát cắt 2D hiện tại, **đã áp dụng đúng Window/Level đang xem** | Mới — InVesalius gốc không có nút xuất nhanh 1 lát cắt ra ảnh |
| **Save / Save As...** | Lưu project `.inv3` — gọi đúng dialog lưu gốc của InVesalius | Giống hệt InVesalius gốc, chỉ là truy cập nhanh hơn |

---

## 7. Giới hạn đã biết (nói rõ để không hiểu nhầm là bug)

1. **Đo khoảng cách/diện tích 2D**: kết quả hiện ở tab "Measures" gốc của InVesalius, **chưa** được đọc ngược vào danh sách riêng của plugin.
2. **Brush vẽ tay**: việc rê chuột vẽ vẫn phải làm trực tiếp trên khung 2D — plugin chỉ bật/tắt và cấu hình công cụ, không tự động vẽ hộ.
3. Annotation lấy vị trí 3D từ điểm pick **gần nhất** — cần pick trước ở tab Interaction để có toạ độ chính xác, nếu không sẽ là `(0, 0, 0)`.

---

## 8. Trình tự demo đề xuất (cho báo cáo/bảo vệ)

1. Import DICOM (mẫu `samples/Cranium.inv3` hoặc bộ CT/MRI bất kỳ) → mở **Plugins → ROI Viewer**
2. Tab **Segmentation**: tick *Auto threshold (Otsu)* → **Create Mask from Threshold** → thấy mask mới trong **ROI List**
3. Bấm **Create Surface** ở panel gốc InVesalius (hoặc dùng threshold task gốc) để có hình khối 3D hiển thị
4. Tab **Interaction**: **Pick Point in 3D** → click vào khối 3D → quan sát 3 khung 2D tự nhảy
5. Tab **Measurements**: chọn **3D** → **Start Distance** → click 2 điểm trên khối 3D → xem kết quả mm
6. Tab **Annotations**: **Add at Current Position** → thấy ghi chú xuất hiện đúng vị trí vừa pick
7. Tab **Export**: **Export Surface** → chọn STL → lưu file → mở bằng phần mềm xem STL bất kỳ để kiểm chứng
