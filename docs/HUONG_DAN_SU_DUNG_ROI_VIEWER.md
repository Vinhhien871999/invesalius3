# Hướng dẫn sử dụng Plugin ROI Viewer

> Tài liệu này mô tả **chính xác từng nút bấm thật** trong plugin (tên nút lấy trực tiếp từ giao diện thật, không diễn giải), theo đúng trình tự thao tác từ đầu, và **khác biệt cụ thể** so với InVesalius gốc (khi chưa cài plugin). Dùng để demo, viết báo cáo NCKH, hoặc tự thao tác kiểm tra lại.
>
> **File này mô tả 2 phạm vi khác nhau — đọc kỹ để không nhầm:**
>
> | Phạm vi | Nhánh / tag | Nội dung |
> |---|---|---|
> | **Bản ổn định (stable baseline)** | `thesis-ct-roi-tools` / tag **`ct3d-rc1`** | Phần mềm sau Phase 14 (`CT3D_P14_FINAL_AUDIT_REPORT`, 17/09/2026), gồm C8 mặt phẳng 2D→3D (`core/slice_planes_3d.SlicePlanes3D`, Phase 13.5). Mọi mục **không** gắn nhãn "chỉ nhánh `enhancement/advanced-segmentation`" thuộc phạm vi này. **Giao diện bản ổn định vẫn là tiếng Anh, 5 tab** — xem bảng đối chiếu tên nút ở mục 1.2. |
> | **Nhánh nâng cao (enhancement-only)** | `enhancement/advanced-segmentation` | Các mục gắn nhãn **"chỉ nhánh `enhancement/advanced-segmentation`"**: hiện gồm **E1–E6b** (2.3, 2.4, 2.7, 2.8, 3.1 phần Khóa/Chỉ hiện, 3.3, 4.3), sửa lỗi toạ độ 3D↔voxel (mục 8) và **giao diện tiếng Việt dạng thanh bên (sidebar) trong cửa sổ InVesalius, 4 tab sắp theo quy trình làm việc** (30/09/2026). **Tag `ct3d-rc1` KHÔNG chứa E1–E6, không chứa sửa lỗi toạ độ và không có giao diện tiếng Việt.** |
>
> **Tên nút trong tài liệu này là tên trên nhánh `enhancement/advanced-segmentation`** (tiếng Việt). Lần đầu nhắc tới một chức năng, tên tiếng Anh cũ ghi trong ngoặc, ví dụ "Phát triển vùng (Region Growing)"; sau đó chỉ dùng tên tiếng Việt.
>
> **Trạng thái E5 hiện tại: PASS (30/09/2026)** — hướng ảnh trên mặt phẳng 3D đã được chứng minh bằng test dựng hình thật (render + đọc lại điểm ảnh, cả 3 mặt phẳng). E5-A đã PASS thủ công; người vận hành báo ảnh lát cắt/cắt hiển thị cơ bản hoạt động sau khi sửa toạ độ. Các mục kiểm tra thủ công chi tiết (E5-B/C/D/E/J/K/L) vẫn chờ người vận hành kiểm tra lại trên bản đã sửa toạ độ (`7b245865`, `c9f220bd`). Xem mục 8.

---

## 0. Trước khi có plugin, InVesalius làm được gì / không làm được gì

InVesalius gốc (chưa cài `roi_viewer`) đã có sẵn: đọc DICOM, hiển thị 3 mặt cắt, dựng mô hình 3D, threshold cơ bản, brush vẽ tay, watershed, đo khoảng cách/density polygon, xuất mask/surface — **nhưng** các thao tác này nằm rải rác ở nhiều task panel khác nhau (task_slice, task_surface, data_notebook...), không có nơi nào:
- Cho biết toạ độ 3D vừa click là gì và tự động nhảy đúng slice 2D tương ứng
- Quản lý nhiều ROI đã tạo theo tên tập trung tại 1 nơi (chỉ có danh sách mask theo số thứ tự ở tab Masks)
- Phát triển vùng (Region Growing — mọc vùng bán tự động từ 1 điểm hạt giống 3D)
- Ghi chú (annotation) văn bản gắn vào một vị trí cụ thể trên ảnh, có lưu lại khi đóng/mở project
- Tự động xác định ngưỡng bằng thuật toán Otsu
- Chủ động dựng lại bề mặt 3D sau khi sửa mặt nạ (cọ vẽ/hoàn tác/phát triển vùng) mà không phải vào lại task panel gốc
- Hoàn tác/làm lại nhanh bằng 1 nút riêng cho việc chỉnh mặt nạ (InVesalius có undo/redo nhưng nằm trong luồng brush riêng, không có nút lưu điểm khôi phục tường minh)

Plugin `ROI Viewer` **không viết lại** các tính năng gốc — nó mở ra một cửa sổ riêng, đóng vai trò "bảng điều khiển tổng hợp", bấm nút trong đó sẽ **điều khiển trực tiếp** đúng tính năng thật của InVesalius (không phải bản sao/giả lập). Vì vậy mọi kết quả (mặt nạ, bề mặt, số đo...) đều hiện luôn trong giao diện chính InVesalius như bình thường, và Save/Open project vẫn dùng đúng cơ chế `.inv3` gốc.

> Thuật ngữ: **mặt nạ** = mask của InVesalius (khối voxel đánh dấu vùng); **ROI** = một mặt nạ được quản lý trong plugin; **bề mặt 3D** = surface dựng từ mặt nạ; **ROI hiện tại** = mặt nạ đang được chọn (current mask) — mọi thao tác hậu xử lý, cọ vẽ, hoàn tác đều áp dụng lên ROI này.

---

## 1. Khởi động — thao tác từ đầu

1. Mở InVesalius:
   - Cách 1: `python app.py` rồi vào **File → Import DICOM...** để chọn thư mục ảnh.
   - Cách 2 (nhanh hơn khi test): `python app.py -i <đường dẫn thư mục DICOM>` — tự import ngay khi khởi động.
2. Đợi import xong (progress bar chạy hết, 3 khung Axial/Coronal/Sagittal hiện ảnh thật).
3. Vào menu **Plugins → ROI Viewer** (tên menu là tên sản phẩm, giữ nguyên).
   - **Nhánh nâng cao**: ROI Viewer mở thành **thanh bên (sidebar) "ROI Viewer" gắn ở mép phải cửa sổ InVesalius** — không còn là cửa sổ riêng. Có thể kéo thanh tiêu đề để **tách ra thành cửa sổ nổi** hoặc gắn sang mép khác (cơ chế AUI chuẩn của InVesalius). Gồm 4 tab theo thứ tự làm việc: **Phân đoạn / ROI & 3D / Hiển thị / Công cụ** (Công cụ = Đo lường, Ghi chú, Xuất dữ liệu).
   - InVesalius chỉ nạp plugin khi bấm menu, nên thanh bên **không tự hiện khi vừa mở InVesalius**; mỗi phiên cần bấm **Plugins → ROI Viewer** một lần.
   - (Bản ổn định `ct3d-rc1`: cửa sổ riêng "ROI Viewer - CT 3D Visualization", 5 tab tiếng Anh.)
   - Có thể mở plugin **trước hay sau** khi import DICOM đều được — nếu mở SAU khi đã có sẵn mặt nạ/project, tab **ROI & 3D** sẽ **tự nạp đúng danh sách mặt nạ đã có** ngay khi cửa sổ hiện ra (không cần thao tác gì thêm).
   - Nếu bấm **Plugins → ROI Viewer** lần nữa trong khi thanh bên đang mở, plugin chỉ đưa thanh bên hiện có ra trước, không mở cái thứ hai.
4. Đóng bằng nút **[X]** trên thanh tiêu đề "ROI Viewer" — plugin dọn dẹp đầy đủ (bỏ marker/mặt phẳng 3D, dừng xử lý AI…), an toàn để mở lại nhiều lần trong cùng phiên làm việc.

### 1.1 Bố cục giao diện (chỉ nhánh `enhancement/advanced-segmentation`, 30/09/2026)

| Tab | Nội dung | Mục |
|---|---|---|
| **Phân đoạn** | Tạo mặt nạ (Ngưỡng, Phát triển vùng, Phân đoạn AI) → Xem trước / Chấp nhận → Hậu xử lý → Chỉnh sửa thủ công → Lịch sử chỉnh sửa | 2 |
| **ROI & 3D** | Quản lý ROI (danh sách, đổi tên, xóa, khóa, chỉ hiện ROI này, hiện/ẩn tất cả) và Bề mặt 3D (cập nhật bề mặt cuối, xem trước 3D thời gian thực) | 3 |
| **Hiển thị** | Đồng bộ 2D – 3D, Chọn điểm 3D, Hiển thị 3D nâng cao (ảnh lát cắt trên mặt phẳng 3D, cắt hiển thị 3D) | 4 |
| **Công cụ** | Ba phần xếp dọc (cuộn): **Đo lường**, **Ghi chú**, **Xuất dữ liệu** — như bản ổn định, chỉ đổi sang tiếng Việt | 5, 6, 7 |

- Đầu tab **Phân đoạn** có dòng gợi ý quy trình: *"1. Tạo / xem trước → 2. Chấp nhận → 3. Hậu xử lý → 4. Cập nhật bề mặt 3D"*, và dòng **"ROI hiện tại:"** cho biết thao tác sẽ áp dụng lên ROI nào.
- Các mục nâng cao/thử nghiệm được **thu gọn mặc định** (bấm vào tiêu đề có mũi tên để mở): *Phân đoạn AI (thử nghiệm)*, *Hậu xử lý (ROI hiện tại)*, *Chỉnh sửa thủ công (cọ vẽ)*, *Xem trước 3D thời gian thực (thử nghiệm)*, *Hiển thị 3D nâng cao (thử nghiệm)*. Khi thu gọn, tab **Phân đoạn** vừa một màn hình; khi mở, chỉ có thanh cuộn dọc (không có thanh cuộn ngang).
- Các tính năng thử nghiệm vẫn **TẮT mặc định** như trước (Xem trước, Xem trước 3D thời gian thực, ảnh lát cắt trên mặt phẳng 3D, cắt hiển thị 3D).
- Đã bỏ 2 khung **không có tác dụng thật** ở tab Interaction cũ: "Real-time Update / Update delay (ms)" (chỉ lưu giá trị, không nơi nào dùng) và "Brush Mode / Brush Size" (bản sao chỉ để tham chiếu; cọ vẽ thật nằm ở mục 2.5).
- Số hiển thị theo kiểu Việt Nam: `152.340 voxel`, `0,08 s`.

### 1.2 Bảng đối chiếu tên nút (bản ổn định tiếng Anh → nhánh nâng cao tiếng Việt)

Dùng khi đọc các tài liệu/kịch bản Manual QA cũ viết theo tên tiếng Anh:

| Tên cũ (tiếng Anh) | Tên mới (tiếng Việt) |
|---|---|
| Tab Segmentation / Interaction / Measurements / Annotations / Export | Tab Phân đoạn (+ tab mới ROI & 3D) / Hiển thị / Công cụ → Đo lường, Ghi chú, Xuất dữ liệu |
| Auto threshold (Otsu) · Min / Max · Create Mask from Threshold | Tự động xác định ngưỡng (Otsu) · Từ / đến · Tạo mặt nạ |
| Tolerance · Pick Seed Point (3D) · Preview Region Growing | Độ dung sai · Chọn điểm hạt giống (3D) · Xem trước (khung Phát triển vùng) |
| Enable Preview Workflow · Preview Otsu · Accept Preview · Cancel Preview · Preview status | Bật chế độ xem trước · Xem trước Otsu · Chấp nhận · Hủy xem trước · Trạng thái |
| Keep Largest Component · Min component size (voxels) · Remove Small Islands · Fill Holes · Smooth iterations · Smooth Mask | Giữ thành phần liên thông lớn nhất · Kích thước tối thiểu · Loại bỏ vùng nhỏ · Lấp lỗ · Số lần làm mịn · Làm mịn mặt nạ |
| Draw / Erase · Circle / Square · Brush size · Enable / Disable Brush Tool | Vẽ / Xóa · Tròn / Vuông · Kích thước cọ · Bật cọ vẽ / Tắt cọ vẽ |
| Save Checkpoint · Undo · Redo | Lưu điểm khôi phục · Hoàn tác · Làm lại |
| ROI List / Segmentation Set · Active ROI · Rename · Delete | Quản lý ROI · ROI hiện tại · Đổi tên · Xóa |
| Lock · Unlock · Solo · Show All · Hide All · `[LOCKED]` | Khóa · Mở khóa · Chỉ hiện ROI này · Hiện tất cả · Ẩn tất cả · `[Khóa]` |
| Update 3D Surface from Selected ROI | Cập nhật bề mặt 3D từ ROI hiện tại |
| Enable Live 3D Preview · Refresh 3D Preview | Bật xem trước 3D thời gian thực · Làm mới xem trước 3D |
| Sync 2D → 3D · Sync 3D → 2D · Show slice planes in 3D | Đồng bộ 2D → 3D · Đồng bộ 3D → 2D · Hiển thị mặt phẳng lát cắt trong 3D |
| Pick Point in 3D | Chọn điểm trong 3D |
| Show CT texture on slice planes | Hiển thị ảnh lát cắt trên mặt phẳng 3D |
| Enable Clipping · Plane · Invert · Target · Current ROI Final Surface · Live Preview (E4) | Bật cắt hiển thị 3D · Mặt phẳng · Đảo phía cắt · Đối tượng · Bề mặt cuối của ROI hiện tại · Bề mặt xem trước |
| Start Distance · Measure Area (2D) · Measure Volume · Clear All | Bắt đầu đo · Đo diện tích (2D) · Đo thể tích · Xóa tất cả |
| Add at Current Position · Go to · Edit · Delete · Prev / Next | Thêm tại vị trí hiện tại · Đi tới · Sửa · Xóa · Trước / Sau |
| Export Mask · Export Surface · Export Current View · Save / Save As... | Xuất mặt nạ · Xuất bề mặt · Xuất khung nhìn hiện tại · Lưu / Lưu thành… |

Giữ nguyên, không dịch (có lý do): tên định dạng tệp (NIfTI, NRRD, NumPy, STL, PLY, OBJ, VTK PolyData, PNG, JPEG, TIFF, BMP), đơn vị (mm, mm³, voxel, s), "ROI", "Otsu", "Window/Level", "2D"/"3D", tên công cụ gốc InVesalius `"Slices' cross intersection"` và tab gốc "Measures" (InVesalius không có bản dịch tiếng Việt nên người dùng sẽ thấy đúng tên tiếng Anh đó trên thanh công cụ), tên mặt nạ tự sinh "ROI Viewer N" / "Region Growing N" (là dữ liệu lưu trong project, không phải nhãn giao diện). Axial/Coronal/Sagittal giữ tên gốc kèm tiếng Việt trong ngoặc: "Axial (ngang)", "Coronal (đứng ngang)", "Sagittal (dọc)".

---

## 2. Tab **Phân đoạn** — tạo và chỉnh sửa mặt nạ (trọng tâm plugin)

### 2.1 Ngưỡng (Threshold) → tạo mặt nạ thật

1. Tick **Tự động xác định ngưỡng (Otsu)** nếu muốn plugin tự tính khoảng ngưỡng bằng thuật toán Otsu trên dữ liệu thật (điền sẵn vào 2 ô **Từ … đến …**) — **InVesalius gốc không có auto-threshold**, phải tự dò tay hoặc chọn preset có sẵn (Bone, Soft tissue...).
2. Hoặc tự nhập khoảng **Từ … đến …** thủ công (giống hệt threshold gốc của InVesalius, đơn vị HU với CT).
3. Bấm **Tạo mặt nạ** → mặt nạ thật được tạo ngay (tên tự sinh "ROI Viewer N"), xuất hiện ở tab "Masks" của InVesalius (panel bên trái) **và** trong danh sách **Quản lý ROI** ở tab **ROI & 3D** (mục 3.1).

### 2.2 Phát triển vùng (Region Growing, dựa trên điểm hạt giống) — mục hoàn toàn mới

Mọc vùng bán tự động: chọn 1 điểm hạt giống trên khối 3D, thuật toán tự lan ra các voxel lân cận có giá trị gần với điểm hạt giống (trong khoảng dung sai cho phép).

1. Nhập **Độ dung sai** (mặc định 50, có thể để **0** = chỉ lấy đúng voxel có giá trị bằng hệt điểm hạt giống).
2. Bấm **Chọn điểm hạt giống (3D)** — nút chuyển sang trạng thái "đang chờ".
3. Click chuột trái vào 1 điểm trên khối 3D (khung "Volume") để chọn làm hạt giống.
4. Plugin tự tính toán (chạy nền, không treo giao diện) rồi tạo mặt nạ mới tên **"Region Growing N"**, xuất hiện trong danh sách Quản lý ROI.
5. **An toàn**: nếu vùng mọc ra quá lớn (>20% tổng thể tích — ngưỡng có thể chỉnh trong code, không phải giá trị tuỳ tiện), plugin hiện hộp thoại **"Vùng quá lớn"** kèm số liệu thật (số voxel, % thể tích) và hỏi có vẫn tạo mặt nạ không (nút Yes/No hiển thị theo ngôn ngữ Windows) — chọn **No** để huỷ (không tạo mặt nạ), tránh tạo ra 1 "vùng quan tâm" chiếm gần hết cả khối ảnh (không còn ý nghĩa ROI).
6. Dòng chữ trạng thái ngay dưới nút luôn hiện thông tin cụ thể sau mỗi lần phát triển vùng (dạng *"Đã tạo 'Region Growing 1': 152.340 voxel (3,2% thể tích), … mm³."* — số liệu minh hoạ), kể cả khi thất bại (ví dụ *"Không tìm thấy vùng (độ dung sai 0). Hãy tăng độ dung sai."*).

> **Lưu ý dung sai**: dung sai càng lớn trên ảnh có dải giá trị rộng (ví dụ CT xương) càng dễ lan ra quá rộng — nên bắt đầu bằng dung sai nhỏ (10-30) rồi tăng dần nếu vùng chưa đủ.
>
> **Nhánh nâng cao**: điểm hạt giống chọn từ 3D giờ rơi đúng voxel (bản ổn định `ct3d-rc1` có lỗi toạ độ làm hạt giống lệch hàng coronal — xem mục 8).

### 2.3 (chỉ nhánh `enhancement/advanced-segmentation`) — Xem trước (Preview, E2)

> **Chỉ có trên nhánh `enhancement/advanced-segmentation`, KHÔNG có trên bản ổn định (`thesis-ct-roi-tools`/tag `ct3d-rc1`).** Mặc định TẮT — khi tắt, Otsu và Phát triển vùng hoạt động y hệt bản ổn định (tạo mặt nạ thật ngay lập tức), không có gì thay đổi.

**Điều kiện**: đã có ít nhất 1 mặt nạ thật đang là ROI hiện tại — đây là giới hạn thật, có sẵn của chính InVesalius (cơ chế xem trước dùng chung đường vẽ overlay thật mà InVesalius Watershed cũng dùng, đường này chỉ vẽ khi có mặt nạ hiện hành) — xem `CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md`.

**Cách dùng**:
1. Tick **"Bật chế độ xem trước"** trong khung **Xem trước**.
2. **Otsu**: bấm **"Xem trước Otsu"** (khung Ngưỡng) → xem lớp phủ màu cam bán trong suốt trên cả 3 khung 2D (Axial/Coronal/Sagittal), khác hẳn màu mặt nạ thật. Lớp phủ này **CHƯA phải mặt nạ thật** — chưa lưu vào project, chưa có trong tab Masks gốc.
3. **Phát triển vùng**: bấm **"Chọn điểm hạt giống (3D)"** như bình thường, click 1 điểm trên khối 3D — khi chế độ xem trước đang bật, thao tác này **chỉ ghi nhớ điểm hạt giống**, KHÔNG tự phát triển vùng ngay (khác chế độ thường). Chỉnh Độ dung sai nếu muốn, rồi bấm **"Xem trước"** (nút ngay dưới, trong khung Phát triển vùng) để tính và xem lớp phủ.
4. Xem dòng **"Trạng thái:"** để biết số voxel/% thể tích (và cảnh báo nếu vùng quá lớn), ví dụ *"Đã tạo xem trước Otsu: 152.340 voxel (226 đến 3071)."* (số liệu minh hoạ)
5. Bấm **"Chấp nhận"** để tạo mặt nạ thật — hoặc **"Hủy xem trước"** để huỷ, không tạo gì cả.

> **Chính xác Chấp nhận làm gì (Otsu)**: Chấp nhận dùng ĐÚNG ngưỡng mà bản xem trước đã hiển thị, và mặt nạ cuối cùng được tạo qua **pipeline threshold gốc thật của InVesalius** dùng đúng ngưỡng đó — **KHÔNG** phải "giữ nguyên không tính lại": pipeline gốc TÍNH LẠI voxel từ ảnh gốc theo ngưỡng này (giống hệt nút "Tạo mặt nạ"). Với Phát triển vùng, Chấp nhận ghi ĐÚNG mảng dữ liệu bản xem trước đã hiển thị (không tính lại).

**Lưu ý quan trọng**:
- Xem trước KHÔNG bao giờ tạo mặt nạ thật, KHÔNG lưu vào Save/Open, KHÔNG ảnh hưởng ROI đang Khóa (E1) hay trạng thái "Chỉ hiện ROI này" (E1) của ROI khác.
- Đóng project hoặc đóng cửa sổ plugin trong khi đang xem trước sẽ tự huỷ bản xem trước an toàn (không crash, không để lại lớp phủ "ma").
- Bản xem trước thứ 2 luôn thay thế bản thứ 1 (không chồng nhiều lớp phủ).

### 2.4 (chỉ nhánh `enhancement/advanced-segmentation`) — Hậu xử lý (ROI hiện tại) (Post-processing / Cleanup, E3)

> **Chỉ có trên nhánh `enhancement/advanced-segmentation`.** Mục thu gọn — bấm tiêu đề **"Hậu xử lý (ROI hiện tại)"** để mở. Thao tác trên **ROI hiện tại** (mặt nạ thật đang chọn). **Chưa hỗ trợ hậu xử lý trên bản Xem trước (E2)** — xem lý do kỹ thuật thật trong `CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md` mục "Cleanup targets" (Chấp nhận của Otsu tạo lại mặt nạ từ ngưỡng, không phải từ mảng dữ liệu, nên hậu xử lý trước rồi Chấp nhận sẽ vô tình mất kết quả hậu xử lý — quyết định hoãn lại toàn bộ mục tiêu này để tránh lỗi không nhất quán).

| Nút | Chức năng thật |
|---|---|
| **Giữ thành phần liên thông lớn nhất** | Chỉ giữ lại thành phần liên thông LỚN NHẤT của mặt nạ, xoá hết phần còn lại (nhiễu rời rạc) |
| **Kích thước tối thiểu** (voxel) + **Loại bỏ vùng nhỏ** | Xoá mọi thành phần liên thông có kích thước NHỎ HƠN số voxel nhập (đúng bằng số nhập thì GIỮ LẠI) |
| **Lấp lỗ** | Lấp đầy khoang rỗng bị bao kín hoàn toàn bên trong mặt nạ (không đụng tới nền bên ngoài) |
| **Số lần làm mịn** + **Làm mịn mặt nạ** | Làm mượt biên mặt nạ (đóng rồi mở hình thái học — thuật toán chọn qua so sánh thật, xem architecture doc), tối đa 5 lần |

> ⚠️ **Cảnh báo thật (Làm mịn mặt nạ)**: làm mịn nhị phân có thể **XOÁ HOÀN TOÀN cấu trúc rất mỏng**. Khảo sát tổng hợp thật ở E3 (`CT3D_ADVANCED_E3_CLEANUP_REPORT.md` mục "Smooth algorithm selection") cho thấy: một cấu trúc dày chỉ 1 voxel biến mất hoàn toàn ngay ở lần làm mịn đầu tiên, với CẢ 2 thuật toán từng so sánh. Dùng ít lần làm mịn và **luôn kiểm tra lại kết quả** — đặc biệt với ROI có cấu trúc mảnh (mạch máu nhỏ, thành mỏng...). Tooltip của nút cũng ghi cảnh báo này.
>
> **Đo trên dữ liệu thật 0051 (30/09/2026, 1 lần làm mịn)**: khối xương và khối mô mềm lớn chỉ mất khoảng 1,5%; nhưng **một vùng chỉ dày 2 lát trục (như vẽ tay trên vài lát) bị xoá 100%** (174.504 → 0 voxel), vì phép "mở" xoá mọi phần mỏng hơn 3 voxel theo bất kỳ trục nào (ở 0051 là 4,5 mm theo trục z). Nếu dòng trạng thái báo mất nhiều voxel, bấm **Hoàn tác**. Đây là mục đang điều tra, chưa đổi thuật toán.

**Hành vi quan trọng, giống hệt cọ vẽ/Hoàn tác/Làm lại**:
- Bị **chặn nếu ROI đang Khóa (E1)** — hiện cảnh báo, không đổi gì.
- Mỗi thao tác thật sự thay đổi mặt nạ sẽ tự **lưu 1 điểm khôi phục** (dùng đúng cơ chế Hoàn tác/Làm lại ở mục 2.6) — **Hoàn tác/Làm lại hoạt động bình thường** sau khi hậu xử lý.
- Nếu kết quả giống hệt trước đó (không có gì để dọn): KHÔNG lưu điểm khôi phục, KHÔNG đổi gì, trạng thái hiện *"Không cần thay đổi mặt nạ."*
- Kết quả hiện dạng *"Lấp lỗ: 152.340 → 153.002 voxel (+0,43%). Bề mặt 3D cuối chưa được cập nhật."* (số liệu minh hoạ)
- **KHÔNG tự dựng lại bề mặt 3D** — giống cọ vẽ/Phát triển vùng, phải tự bấm **"Cập nhật bề mặt 3D từ ROI hiện tại"** (mục 3.2) để thấy kết quả mới trên khối 3D.

### 2.5 Chỉnh sửa thủ công (cọ vẽ) (Brush Tools — trình vẽ 2D thật)

Mục thu gọn — bấm tiêu đề **"Chỉnh sửa thủ công (cọ vẽ)"** để mở.
- **Vẽ / Xóa**: chọn chế độ vẽ thêm hay xoá bớt.
- **Tròn / Vuông**: hình dạng đầu cọ.
- **Kích thước cọ** (thanh trượt): kích thước cọ (px).
- **Bật cọ vẽ**: bấm để **kích hoạt** — sau đó dùng **chuột vẽ trực tiếp trên khung 2D (Axial/Coronal/Sagittal) của InVesalius y như brush gốc**. Bấm lại (nút đổi thành **"Tắt cọ vẽ"**) để tắt.

> Quan trọng: plugin **không tự vẽ thay bạn** — nó chỉ bật đúng công cụ vẽ tay thật của InVesalius và đồng bộ kích thước/hình dạng/chế độ. Thao tác vẽ (rê chuột) vẫn làm trực tiếp trên khung 2D như dùng InVesalius bình thường. Cần chọn/tạo 1 mặt nạ trước (mục 2.1/3.1), nếu chưa có mặt nạ nào sẽ báo *"Hãy tạo hoặc chọn một mặt nạ trước."* khi bật. **(Nhánh nâng cao)** Bị chặn nếu ROI đang Khóa.

### 2.6 Lịch sử chỉnh sửa (ROI hiện tại) (Undo / Redo)
- **Lưu điểm khôi phục**: lưu lại trạng thái hiện tại của mặt nạ đang chọn (làm mốc để quay lại).
- **Hoàn tác / Làm lại**: khôi phục/làm lại — hoạt động trên **toàn bộ ma trận voxel thật** của mặt nạ, nên **hoàn tác được cả những gì vừa vẽ bằng brush gốc của InVesalius**, không chỉ thao tác qua plugin.
- Dòng trạng thái cuối tab (mặc định *"Sẵn sàng."*) báo kết quả: *"Đã lưu điểm khôi phục."*, *"Đã hoàn tác."*, *"Không có gì để hoàn tác."*, *"ROI đang bị khóa."*...

### 2.7 (chỉ nhánh `enhancement/advanced-segmentation`) — Phân đoạn AI (thử nghiệm) (AI segmentation, E6)

> **Chỉ có trên nhánh `enhancement/advanced-segmentation`.** Mục thu gọn, **mặc định TẮT**. Mô hình hỗ trợ: **TotalSegmentator** (E6b, xem 2.8) — plugin **không kèm** mô hình, người dùng phải tự cài. Khi bật, nếu chưa cài mô hình, giao diện báo **"Chưa có mô hình AI tương thích."** và nút "Xem trước bằng AI" bị khóa — đây là hành vi đúng, không phải lỗi. Plugin **không bao giờ tự tải mô hình hay tự cài thư viện**.

**Nguyên tắc**: kết quả AI **chỉ là bản xem trước** (lớp phủ màu cam giống mục 2.3, hiện cả trong Xem trước 3D nếu đang bật). Mặt nạ thật chỉ được tạo khi bấm **Chấp nhận** trong khung **Xem trước**, và mặt nạ đó **đúng từng voxel** với bản xem trước (không chạy lại mô hình). **Hủy xem trước** thì không tạo gì.

**Cách dùng (khi đã có mô hình)**:
1. Mở mục **"Phân đoạn AI (thử nghiệm)"**, tick **"Bật phân đoạn AI (thử nghiệm)"**, chọn **Mô hình** và **Thiết bị** (Tự động / CPU / CUDA — chỉ hiện thiết bị mô hình hỗ trợ).
2. Chọn **Kiểu điểm**: **Thuộc vùng** (điểm nằm trong cấu trúc cần tách) hoặc **Loại trừ**.
3. Thêm điểm: **"Chọn điểm (3D)"** rồi nhấp lên khối 3D, hoặc đưa con trỏ 2D tới vị trí rồi bấm **"Điểm tại con trỏ 2D"**.
4. (Tùy chọn) **Hộp giới hạn**: đưa con trỏ 2D tới một góc → **"Chọn góc 1"**, tới góc đối diện → **"Chọn góc 2"**.
5. Dòng tóm tắt cho biết số điểm và trạng thái hộp; **"Xóa điểm AI"** để làm lại. (Các ô điểm/hộp chỉ hiện khi mô hình đang chọn dùng gợi ý điểm/hộp; ô Cấu trúc/Chế độ chỉ hiện khi mô hình có các tùy chọn đó; khi chưa có mô hình chỉ hiện dòng hướng dẫn cài đặt.) Điểm nằm ngoài khối ảnh bị bỏ qua (không tự kéo vào mép).
6. Bấm **"Xem trước bằng AI"** (cần có một mặt nạ hiện hành, như mục 2.3). Mô hình chạy nền, giao diện không bị treo; **"Hủy xử lý AI"** để dừng — kết quả đến muộn sẽ bị bỏ.
7. Kiểm tra lớp phủ → **Chấp nhận** (tạo mặt nạ mới "AI Segmentation N", có thể hậu xử lý mục 2.4 như mặt nạ thường) hoặc **Hủy xem trước**.

**Lưu ý**: điểm/hộp AI chỉ tồn tại trong phiên làm việc (không lưu vào dự án, bị xóa khi đóng/mở dự án hoặc đóng plugin). ROI đang Khóa vẫn chạy AI được vì AI chỉ tạo ứng viên mới; Chấp nhận tạo ROI mới, không khóa. Ảnh lát cắt trên mặt phẳng 3D / cắt hiển thị (mục 4.3) không ảnh hưởng kết quả AI — AI đọc trực tiếp khối ảnh gốc (giá trị HU với CT). Chi tiết kỹ thuật: `CT3D_ADVANCED_E6_AI_ARCHITECTURE_REPORT.md`.

### 2.8 (chỉ nhánh `enhancement/advanced-segmentation`) — Phân đoạn tự động bằng TotalSegmentator (E6b)

> **Thử nghiệm, chưa được kiểm định lâm sàng.** TotalSegmentator được **chạy cục bộ trên máy**; ảnh CT không được gửi đi đâu (plugin còn tắt chức năng gửi thống kê sử dụng của TotalSegmentator trong lúc chạy). Thời gian chạy phụ thuộc rất nhiều vào CPU/GPU — trên CPU có thể rất lâu.

**Cài đặt (làm một lần, ngoài plugin)** — plugin **không bao giờ tự cài hay tự tải**. Nếu chưa cài: "TotalSegmentator chưa được cài đặt."; nếu thiếu trọng số: "Mô hình TotalSegmentator chưa sẵn sàng."

> ⚠️ **Không chạy `pip install TotalSegmentator` trần**: kiểm tra (pip `--dry-run`, 30/09/2026) cho thấy lệnh đó sẽ thay torch CUDA bằng torch CPU và nâng numpy lên 2.x — làm hỏng môi trường InVesalius. Dùng lệnh có ràng buộc dưới đây (đã kiểm tra bằng dry-run: không thay đổi gói nào đang có).

```bat
cd /d D:\Learns\DeAn\invesalius\invesalius3
D:\PyTools\invx-venv\Scripts\python.exe -m pip install -c tools\ct3d_ai_constraints.txt --extra-index-url https://download.pytorch.org/whl/cu118 TotalSegmentator==2.18.0
D:\PyTools\invx-venv\Scripts\python.exe -c "import torch, numpy; print(torch.__version__, torch.cuda.is_available(), numpy.__version__)"
D:\PyTools\invx-venv\Scripts\totalseg_download_weights.exe -t total
```

Dòng kiểm tra phải in `2.7.1+cu118 True 1.26.4`. `-t total` tải trọng số cho chế độ **Chính xác tiêu chuẩn** (kèm mô hình cắt vùng mà mỗi lần phân đoạn một cấu trúc cần); thêm `-t total_fast` nếu muốn chế độ **Nhanh**. Sau đó khởi động lại InVesalius. (Đường dẫn trên là môi trường của máy phát triển; máy khác thay bằng Python đang chạy InVesalius.) Chi tiết: `CT3D_ADVANCED_RC_READINESS_REPORT.md` mục 6.

**Lần chạy thật đầu tiên (30/09/2026, người vận hành)**: dữ liệu 0801 (CT cổ–ngực), cấu trúc `trachea`, CUDA, Chính xác tiêu chuẩn — **48,5 s** (chuyển dữ liệu 1,4 s, suy luận 46,8 s, ánh xạ kết quả 0,2 s), 25.953 voxel; mặt nạ "AI - trachea" nằm đúng khí quản trên cả 3 mặt cắt và bề mặt 3D có cả chỗ chia đôi phế quản. Chọn cấu trúc có trong vùng chụp: 0801 → `trachea`, `heart`, `aorta`, các thùy phổi; 0051 (**CT sọ**) → `brain`, `skull` (không chọn `spleen`/`liver` khi chúng nằm ngoài ảnh — kết quả sẽ rỗng).

> ⚠️ **Đừng kéo thanh ngưỡng (Threshold) của InVesalius khi đang chọn mặt nạ AI** (ô ngưỡng hiện "1 – 1"): InVesalius sẽ tính lại mặt nạ từ ngưỡng và **xóa kết quả AI** — đây là hành vi gốc cho mọi mặt nạ đã chỉnh sửa (cọ vẽ, phát triển vùng, AI), không riêng plugin.

**Quy trình**: tab **Phân đoạn** → mở **Phân đoạn AI (thử nghiệm)** → tick **Bật phân đoạn AI (thử nghiệm)** → **Mô hình**: TotalSegmentator → **Cấu trúc**: gõ để tìm và chọn một cấu trúc (tên gốc tiếng Anh của mô hình, ví dụ `spleen`, `liver`) → **Thiết bị**: Tự động / CPU / CUDA (CUDA chỉ hiện khi có GPU dùng được) → **Chế độ**: Chính xác tiêu chuẩn hoặc Nhanh / ít bộ nhớ hơn (kém chính xác hơn) → **Xem trước bằng AI** → kiểm tra lớp phủ trên Axial/Coronal/Sagittal và trong Xem trước 3D → **Chấp nhận** (tạo mặt nạ "AI - <cấu trúc>") → **Hậu xử lý** nếu cần → **Cập nhật bề mặt 3D từ ROI hiện tại**.

**Lưu ý**:
- Mỗi lần chỉ một cấu trúc; các lớp khác của mô hình không được dùng.
- TotalSegmentator không dùng điểm/hộp gợi ý — các nút đó bị khóa khi chọn mô hình này.
- Trạng thái chỉ hiện giai đoạn (Đang chuẩn bị dữ liệu… / Đang chạy TotalSegmentator… / Đang ánh xạ kết quả…), không có phần trăm vì mô hình không báo tiến độ.
- **Hủy xử lý AI** không dừng được mô hình đang chạy: nó chạy tiếp ở nền tới khi xong, kết quả bị bỏ qua (giao diện ghi rõ điều này).
- Chỉ hỗ trợ khối ảnh nhập từ **chuỗi DICOM lát ngang** (cần biết hướng bệnh nhân); trường hợp khác bị từ chối. Nếu đã dùng công cụ lật/đổi trục của InVesalius sau khi nhập, hướng lưu trong dự án không còn đúng.

---

## 3. Tab **ROI & 3D** — quản lý ROI và bề mặt 3D

### 3.1 Quản lý ROI (ROI List) — quản lý phân đoạn tập trung

Mọi mặt nạ tạo ra (từ Ngưỡng, Phát triển vùng, **hoặc từ tab Masks gốc của InVesalius**) đều tự động xuất hiện trong danh sách này dưới dạng `<tên> (mặt nạ #<số>)` — danh sách này **luôn đồng bộ 2 chiều thật** với dữ liệu mặt nạ thật của InVesalius (không phải bản sao riêng), kể cả khi bạn đổi tên/ẩn-hiện/xoá mặt nạ trực tiếp ở tab "Masks" gốc thay vì dùng nút dưới đây. Vẫn 100% dựa trên các mask InVesalius thật, KHÔNG phải "true multilabel" (xem `docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md`).

Cạnh nhãn **"ROI hiện tại:"** phía trên danh sách có 1 ô màu nhỏ hiển thị đúng màu thật của ROI đang chọn (chỉ để xem, không đổi màu được từ đây — muốn đổi màu, dùng tab "Masks" gốc của InVesalius). Tên ROI hiện tại cũng hiện ở đầu tab **Phân đoạn**.

| Điều khiển | Chức năng thật |
|---|---|
| Tick vào ô đánh dấu trước tên | **Ẩn/hiện** mặt nạ đó thật sự trên 2D/3D (giống nút con mắt ở tab Masks gốc) |
| Click chọn 1 dòng | **Chọn mặt nạ đó làm ROI hiện tại** — mọi lệnh cọ vẽ/hậu xử lý/đo lường/cập nhật bề mặt sau đó áp dụng lên ROI này |
| **Đổi tên** | Đổi tên — cập nhật cả trong danh sách plugin lẫn tab "Masks" gốc của InVesalius |
| **Xóa** | Xoá hẳn mặt nạ khỏi project (có hỏi xác nhận) — **(nhánh nâng cao) bị chặn nếu ROI đang Khóa** |

**(chỉ nhánh `enhancement/advanced-segmentation`) — Khóa / Chỉ hiện ROI này / Hiện tất cả / Ẩn tất cả (E1)**:

| Nút | Chức năng thật | Ghi chú |
|---|---|---|
| **Khóa** | Đánh dấu ROI đang chọn là "khoá" (`[Khóa]` xuất hiện trước tên trong danh sách) | Chặn cọ vẽ, Hoàn tác, Làm lại, Hậu xử lý, Xóa trên ROI này cho đến khi Mở khóa. KHÔNG chặn Đổi tên/ẩn-hiện/Cập nhật bề mặt (không phá huỷ dữ liệu). **Trạng thái Khóa KHÔNG được lưu vào project** — đóng/mở lại project sẽ về mở khóa (quyết định thiết kế có chủ đích, xem architecture doc) |
| **Mở khóa** | Gỡ khoá ROI đang chọn | — |
| **Chỉ hiện ROI này** (nút bật/tắt, tên cũ "Solo") | Chỉ hiện ROI đang chọn, ẩn tất cả ROI khác (`[Chỉ hiện]` trước tên); bấm lại để khôi phục đúng trạng thái ẩn/hiện trước đó (không phải "hiện hết") | Tự tắt nếu bạn tự tay tick/bỏ tick 1 dòng khác, hoặc bấm Hiện tất cả/Ẩn tất cả |
| **Hiện tất cả** | Hiện tất cả ROI | Cũng tự tắt "Chỉ hiện ROI này" nếu đang bật |
| **Ẩn tất cả** | Ẩn tất cả ROI | Cũng tự tắt "Chỉ hiện ROI này" nếu đang bật |

### 3.2 Bề mặt 3D — Cập nhật bề mặt 3D từ ROI hiện tại (Update 3D Surface from Selected ROI)

Nút **"Cập nhật bề mặt 3D từ ROI hiện tại"** dựng lại (hoặc dựng mới) mô hình 3D cho ĐÚNG mặt nạ đang chọn trong danh sách (nếu không chọn dòng nào, dùng mặt nạ hiện hành).

- Lần đầu: **thêm một bề mặt mới mang tên ROI** (ví dụ "AI - trachea"); các bề mặt khác (ví dụ bề mặt xương) **giữ nguyên**. Lần sau: thay đúng bề mặt mà nút này đã dựng cho ROI đó. Khi xong, dòng trạng thái đổi thành *"Đã cập nhật bề mặt 3D của '…'."*
- **[Sửa 30/09/2026]** Trước đó nút luôn gửi "ghi đè" cho InVesalius — mà InVesalius ghi đè lên **bề mặt được tạo/chọn gần nhất**, bất kể của mặt nạ nào → bề mặt xương có thể bị thay bằng bề mặt ROI (người vận hành gặp trên 0801). Nếu bề mặt xương đã mất, dựng lại: chọn Mask 1 → bấm nút này (hoặc Create Surface gốc, bỏ tick "Overwrite last surface").
- Bề mặt do nút "Create Surface" gốc tạo không được plugin nhận là của ROI nào, nên bấm nút này cho cùng mặt nạ sẽ tạo thêm một bề mặt mới (không xóa bề mặt gốc). Xem/ẩn/xóa bề mặt ở tab **Data → 3D surfaces** của InVesalius.

> **Vì sao cần bấm thủ công**: InVesalius gốc (kể cả không có plugin) **không tự động** cập nhật lại mô hình 3D mỗi khi mặt nạ bị sửa (cọ vẽ, hoàn tác, phát triển vùng...) — đây là hành vi thật của InVesalius, không phải hạn chế riêng của plugin. Nút này đóng vòng lặp "sửa ROI → xem lại 3D" một cách chủ động, tránh việc tự động dựng lại sau MỖI nét vẽ (sẽ làm treo giao diện vì dựng mô hình 3D là tác vụ nặng). **Sau khi sửa mặt nạ xong, luôn nhớ bấm nút này để thấy đúng kết quả mới nhất trên khối 3D** — nếu không bấm, khối 3D vẫn hiện hình dạng CŨ dù mặt nạ đã đổi.
> Việc dựng lại có thể mất vài giây đến hơn chục giây tuỳ kích thước mặt nạ — quan sát dòng trạng thái cuối tab (*"Đang dựng lại bề mặt 3D của '…'…"*).

### 3.3 (chỉ nhánh `enhancement/advanced-segmentation`) — Xem trước 3D thời gian thực (thử nghiệm) (Live 3D Preview, E4)

> **Chỉ có trên nhánh `enhancement/advanced-segmentation`.** Mục thu gọn, mặc định TẮT. Đây là một **lưới xem trước, KHÔNG PHẢI bề mặt 3D cuối cùng** — không lưu vào `Project`, không thay thế nút "Cập nhật bề mặt 3D từ ROI hiện tại" (mục 3.2), không ảnh hưởng dữ liệu Save/Open.

**Cách dùng**:
1. Mở mục **"Xem trước 3D thời gian thực (thử nghiệm)"**, tick **"Bật xem trước 3D thời gian thực"**.
2. Plugin tự dựng một lưới xem trước (không cần bấm gì thêm) theo nguồn dữ liệu ưu tiên: nếu đang có bản Xem trước (E2) sẵn sàng thì dùng bản đó; nếu không thì dùng ROI hiện tại. Dòng **"Nguồn:"** cho biết đang dùng *Xem trước Otsu*, *Xem trước phát triển vùng* hay *ROI hiện tại*; dòng **"Trạng thái:"** hiện *"Đang chờ cập nhật…"*, *"Đang dựng lưới…"* rồi *"Đã cập nhật xem trước 3D trong 0,08 s."* (số liệu minh hoạ) kèm số điểm/ô của lưới.
3. Lưới xem trước **tự cập nhật** (có độ trễ debounce ~400ms) khi: vẽ/xoá bằng cọ vẽ gốc, chạy Xem trước Otsu/Phát triển vùng (E2), Chấp nhận/Hủy xem trước, chạy các nút Hậu xử lý (E3), Hoàn tác/Làm lại, hoặc chuyển ROI hiện tại.
4. Có thể bấm **"Làm mới xem trước 3D"** để cập nhật ngay lập tức, không cần chờ debounce.
5. Bỏ tick để tắt — lưới xem trước biến mất ngay, không còn tự cập nhật.

**Lưu ý quan trọng**:
- Lưới xem trước **không thể click/pick được** (không ảnh hưởng đến chọn điểm 3D cho Phát triển vùng, đo lường, hay các thao tác chọn khác).
- Không bao giờ tự động di chuyển camera.
- Đóng project hoặc đóng cửa sổ plugin trong khi đang bật sẽ tự dọn dẹp lưới an toàn (không crash, không để lại lưới "ma").
- Nếu mặt nạ rỗng: *"Không có voxel thuộc vùng phân đoạn."*
- Tắt tính năng này hoàn toàn không ảnh hưởng quy trình cổ điển (Ngưỡng/Otsu/Phát triển vùng/cọ vẽ/Hoàn tác/Làm lại/Cập nhật bề mặt 3D vẫn y hệt bản ổn định).

---

## 4. Tab **Hiển thị** — liên kết 2D – 3D

### 4.1 Đồng bộ 2D – 3D

| Điều khiển | Ý nghĩa | Khác gì so với InVesalius gốc |
|---|---|---|
| **Đồng bộ 2D → 3D** (ô đánh dấu, mặc định bật) | Khi bạn click/kéo chuột trên khung 2D bất kỳ (Axial/Coronal/Sagittal — dùng đúng crosshair thật của InVesalius gốc), một quả cầu nhỏ màu vàng xuất hiện/di chuyển trong khung 3D (Volume) tới đúng vị trí tương ứng. Tắt ô này thì quả cầu đứng yên, không cập nhật nữa | **Đã triển khai (Phase 09, 14/09/2026)** — trước đó chỉ lưu cờ, không có tác dụng |
| **Đồng bộ 3D → 2D** (ô đánh dấu, mặc định bật) | Khi chọn 1 điểm 3D, 3 khung Axial/Sagittal/Coronal tự cuộn tới đúng lát cắt chứa điểm đó | InVesalius gốc không có cơ chế này |
| **Hiển thị mặt phẳng lát cắt trong 3D** (ô đánh dấu, mặc định bật) | **Mới ở Phase 13.5 (16/09/2026)**: thêm 3 mặt phẳng bán trong suốt (đỏ=Sagittal, xanh lá=Coronal, xanh dương=Axial) trong khung Volume, thể hiện trực quan vị trí 3 mặt cắt hiện tại (bên cạnh quả cầu marker) — dễ hình dung vị trí lát cắt hơn so với chỉ 1 điểm nhỏ. Tắt ô này chỉ ẩn 3 mặt phẳng, quả cầu marker không bị ảnh hưởng. **Quan trọng**: để click/kéo chuột 2D thật sự cập nhật được, bạn phải **tự bật** công cụ gốc **`"Slices' cross intersection"`** trên thanh công cụ InVesalius trước (dòng gợi ý ngay dưới ô cũng nhắc điều này) — plugin **không tự động bật** công cụ này (không chiếm quyền Brush/Eraser/Distance/Area hay đổi trạng thái toolbar gốc). Mặt phẳng chỉ mang tính trực quan vị trí — **không dựng lại bề mặt 3D** khi bạn kéo crosshair (bề mặt chỉ dựng lại khi bạn chủ động bấm "Cập nhật bề mặt 3D từ ROI hiện tại") | Mới hoàn toàn |

Dòng trạng thái cuối tab cho biết hướng đồng bộ đang bật (*"Đang đồng bộ: 2D → 3D, 3D → 2D."*) hoặc *"Đã tắt đồng bộ."*

### 4.2 Chọn điểm 3D (3D point picking)

| Điều khiển | Ý nghĩa |
|---|---|
| **Chọn điểm trong 3D** | Bấm 1 lần để "vũ trang" chế độ chọn điểm (*"Nhấp một điểm trong khung 3D…"*) |
| Ô toạ độ (chỉ đọc) | Hiện toạ độ thật `X: …, Y: …, Z: … mm` của điểm vừa click. **Nhánh nâng cao**: toạ độ hiển thị trong **cùng hệ toạ độ với khung 2D của InVesalius** (gốc 0, Y dương) — không còn là toạ độ khung 3D đã lật trục Y như bản ổn định |

**Cách dùng thực tế**:
1. Cần đã có ít nhất 1 mặt nạ + 1 bề mặt 3D hiển thị trong khung "Volume" ở cửa sổ chính (mục 2.1 và 3.2).
2. Bấm **Chọn điểm trong 3D**.
3. Click chuột trái vào một điểm trên khối 3D trong khung "Volume".
4. Quan sát: ô toạ độ cập nhật, 3 khung 2D tự nhảy tới đúng lát cắt chứa điểm đó (nếu **Đồng bộ 3D → 2D** đang bật).

### 4.3 (chỉ nhánh `enhancement/advanced-segmentation`) — Hiển thị 3D nâng cao (thử nghiệm) (E5): ảnh lát cắt trên mặt phẳng 3D + cắt hiển thị 3D

> **Chỉ có trên nhánh `enhancement/advanced-segmentation`.** Mục thu gọn **"Hiển thị 3D nâng cao (thử nghiệm)"** nằm ngay dưới khung "Chọn điểm 3D". Mặc định TẮT cả hai — khi tắt, hành vi giống hệt trước khi có E5 (3 mặt phẳng màu C8 như mục 4.1).

**Ảnh lát cắt trên mặt phẳng 3D (E5A, tên cũ "Show CT texture on slice planes")**:
1. Tick **"Hiển thị ảnh lát cắt trên mặt phẳng 3D"**.
2. 3 mặt phẳng màu (C8) biến mất, thay bằng 3 mặt phẳng hiển thị **ảnh lát cắt gốc của InVesalius** (CT sau Window/Level hiện tại, **cộng** màu mặt nạ hiện hành và lớp phủ Xem trước nếu đang bật — plugin tái dùng đúng ảnh InVesalius dùng để vẽ khung 2D, không tự tính lại; xem tooltip của ô). Ảnh xuất hiện đúng tại vị trí 3 mặt phẳng màu đang đứng.
3. Di chuyển crosshair 2D (cần bật công cụ gốc `"Slices' cross intersection"` như mục 4.1) — cả 3 mặt phẳng tự cập nhật nội dung theo lát cắt mới.
4. Đổi Window/Level bằng công cụ gốc của InVesalius — ảnh tự làm mới ngay, **không cần** di chuyển crosshair.
5. Bỏ tick để quay lại 3 mặt phẳng màu C8 như cũ.

**Ô "Hiển thị mặt phẳng lát cắt trong 3D" là công tắc chính cho cả 2 loại mặt phẳng** — ô ảnh lát cắt chỉ chọn loại nào được hiện, không bao giờ vượt qua công tắc chính:

| Hiển thị mặt phẳng lát cắt trong 3D | Hiển thị ảnh lát cắt trên mặt phẳng 3D | Mặt phẳng màu C8 | Mặt phẳng ảnh lát cắt |
|---|---|---|---|
| Tắt | Tắt | ẩn | ẩn |
| Bật | Tắt | **hiện** | ẩn |
| Bật | Bật | ẩn | **hiện** |
| Tắt | Bật | ẩn | ẩn |

Di chuyển crosshair chỉ cập nhật vị trí/nội dung, không làm thay đổi bảng trên. *(Sửa 29/09/2026: trước đó, khi bật ảnh lát cắt rồi di chuyển crosshair, mặt phẳng màu C8 bị hiện lại chồng lên — lỗi thật do người vận hành phát hiện, đã sửa; người vận hành đã kiểm tra lại E5-A: PASS.)*

> ⚠️ **Lưu ý thật (hướng ảnh)**: hình học của mặt phẳng ảnh đã được chứng minh thật (khớp chính xác với công thức hình học C8, và khớp đúng giá trị voxel ảnh thật ở từng góc, kiểm chứng bằng test tự động). Từ 30/09/2026, hướng ảnh **đã được kiểm chứng bằng ảnh dựng thật**: test tự động dựng mặt phẳng, đọc lại điểm ảnh và so với voxel tại đúng vị trí 3D, cả 3 mặt phẳng, với spacing không đẳng hướng như `0051` — không lệch, không lật; bản cố ý lật ảnh thì test phát hiện (xem `CT3D_ADVANCED_E5_VISUALIZATION_REPORT.md`, mục "E5 closure"). Việc người vận hành so sánh bằng mắt (E5-B/C/D) vẫn là mục kiểm tra thủ công riêng.

**Cắt hiển thị 3D (Clipping / Cutaway, E5B)**:
1. Dựng bề mặt 3D thật cho 1 ROI trước (mục 3.2, nút "Cập nhật bề mặt 3D từ ROI hiện tại").
2. Tick **"Bật cắt hiển thị 3D"**, chọn **Mặt phẳng:** Axial (ngang) / Coronal (đứng ngang) / Sagittal (dọc), tick **"Đảo phía cắt"** nếu muốn lật phía bị cắt.
3. Chọn **Đối tượng:** "Bề mặt cuối của ROI hiện tại" (mặc định) hoặc "Bề mặt xem trước" (lưới E4, mục 3.3).
4. Di chuyển crosshair 2D — mặt cắt 3D di chuyển theo, **không dựng lại bề mặt**, không đổi dữ liệu mặt nạ/bề mặt gốc (chỉ ẩn/hiện phần hình học lúc render — tắt cắt hiển thị là bề mặt hiện lại y hệt ban đầu).
5. Đổi ROI đang chọn hoặc bấm dựng lại bề mặt — chức năng cắt tự tìm đúng bề mặt mới (hoặc báo *"ROI hiện tại chưa có bề mặt 3D cuối."* nếu ROI chưa có bề mặt).

---

## 5. Tab **Công cụ** → phần **Đo lường** (Measurements)

| Điều khiển | Cách dùng | Ghi chú |
|---|---|---|
| **3D** + **Bắt đầu đo** (khung "Đo khoảng cách") | Bấm, sau đó click 2 điểm liên tiếp trên khối 3D (khung Volume) | Kết quả (mm) hiện ngay ở dòng "Kết quả:" của plugin **và** được lưu vào danh sách "Kết quả đã lưu" bên dưới |
| **2D** + **Bắt đầu đo** | Bấm — kích hoạt công cụ đo khoảng cách 2D **gốc** của InVesalius | Bạn thao tác (click 2 điểm) trực tiếp trên khung 2D; **kết quả hiện ở tab "Measures" gốc của InVesalius** — plugin **cố tình không** tạo thêm 1 danh sách đo lường thứ hai cho phần này (xem mục 8) |
| **Đo diện tích (2D)** | Bấm — kích hoạt công cụ vẽ đa giác đo diện tích/mật độ gốc | Vẽ đa giác trực tiếp trên khung 2D; kết quả hiện ở tab "Measures" gốc |
| **Đo thể tích** | Bấm 1 lần, không cần thao tác gì thêm | Tính thể tích thật của mặt nạ đang chọn (số voxel × spacing thật từ DICOM), hiện ngay ở dòng "Kết quả:" |
| **Xóa tất cả** | Xoá danh sách đo lường (3D + thể tích) của plugin | |

---

## 6. Tab **Công cụ** → phần **Ghi chú** (Annotations)

1. Gõ nội dung vào ô **Nội dung:**, chọn **Màu:** (bảng màu hoặc 5 ô màu nhanh: Đỏ, Xanh lá, Xanh dương, Cam, Tím — rê chuột để xem tên).
2. Bấm **Thêm tại vị trí hiện tại** → ghi chú được gắn vào vị trí thật gần nhất bạn đã tương tác: ưu tiên điểm chọn 3D (tab Hiển thị hoặc lúc chọn hạt giống Phát triển vùng), nếu chưa chọn điểm 3D lần nào thì dùng vị trí crosshair 2D gần nhất (click/kéo chuột trên khung 2D). **Nếu chưa có vị trí hợp lệ nào cả**, plugin **từ chối tạo ghi chú** và hiện thông báo *"Chưa chọn vị trí"* yêu cầu chọn vị trí trước — không còn tạo nhầm ghi chú tại gốc toạ độ `(0,0,0)` như trước (đã sửa ở Phase 09, 14/09/2026).
3. Danh sách bên dưới hiện tất cả ghi chú. Chọn 1 dòng rồi dùng:
   - **Đi tới**: nhảy đúng slice 2D chứa ghi chú đó.
   - **Sửa**: sửa nội dung.
   - **Xóa**: xoá.
   - **Trước / Sau** (khung "Điều hướng nhanh"): duyệt qua lại giữa các ghi chú.
4. **Ghi chú được lưu lại khi Lưu project** (xem mục 7) — đóng/mở lại `.inv3` sẽ thấy đúng danh sách ghi chú cũ, không mất.

> InVesalius gốc **không có** tính năng ghi chú dạng văn bản gắn theo vị trí — đây là tính năng mới hoàn toàn của plugin.

---

## 7. Tab **Công cụ** → phần **Xuất dữ liệu** (Export) — lưu/xuất kết quả

| Nút | Kết quả | So với InVesalius gốc |
|---|---|---|
| **Xuất mặt nạ** — chọn **NIfTI**: mở đúng dialog "Export Mask as NIfTI" **gốc** của InVesalius, tự động điền sẵn đúng mặt nạ đang chọn | File `.nii.gz` thật, đọc lại được bằng bất kỳ phần mềm NIfTI nào | InVesalius gốc yêu cầu tự vào menu và tự chọn mask trong danh sách; ở đây tự lấy đúng mặt nạ hiện hành |
| **Xuất mặt nạ** — chọn **NumPy**: dùng dialog lưu file riêng của plugin | File `.npy` thật, đọc lại bằng `numpy.load()` | Mới — InVesalius gốc không xuất được NumPy |
| **Xuất mặt nạ** — chọn **NRRD**: dùng dialog lưu file riêng của plugin | Thư viện `pynrrd` là dependency **optional** (`pip install pynrrd`, hoặc cài extra chính thức `pip install invesalius[nrrd]`). **Từ Phase 12**: nếu chưa cài, ô **Định dạng:** tự hiện rõ *"NRRD (.nrrd) - chưa cài thư viện"* + tooltip giải thích, và bấm Xuất sẽ báo ngay (trước khi chọn tên file) thay vì để người dùng chọn xong mới báo lỗi | Cơ chế đã nối đúng (`core/exporters.py`); UI không ngụ ý NRRD chắc chắn chạy khi thiếu thư viện |
| **Xuất bề mặt** (STL Binary/ASCII, PLY, OBJ, VTK PolyData) | Xuất file bề mặt 3D thật (đã tạo ở mục 3.2) | STL/PLY/OBJ dùng đúng pipeline VTK gốc; **VTK PolyData** là định dạng thêm ngoài 3 định dạng gốc InVesalius hỗ trợ |
| **Xuất khung nhìn hiện tại** (PNG/JPEG/TIFF/BMP, có **Tỉ lệ:** phóng to) | Xuất ảnh lát cắt 2D hiện tại, **đã áp dụng đúng Window/Level đang xem** | Mới — InVesalius gốc không có nút xuất nhanh 1 lát cắt ra ảnh |
| **Lưu / Lưu thành…** (khung "Dự án", tuỳ chọn "Nén dự án") | Lưu project `.inv3` — gọi đúng dialog lưu gốc của InVesalius, **và tự động lưu kèm toàn bộ Ghi chú** (file `.roi_annotations.json` cùng thư mục, cùng tên với `.inv3`) | Giống hệt InVesalius gốc cho phần mặt nạ/bề mặt, **cộng thêm** ghi chú được lưu tự động |

> **Danh sách ROI không cần lưu riêng**: tên/màu/hiển thị trong danh sách Quản lý ROI (mục 3.1) chính là dữ liệu thật của mặt nạ, đã tự động nằm trong `.inv3` khi Lưu — mở lại project sẽ thấy danh sách tự dựng lại đúng như cũ, không cần thao tác gì thêm. (Trạng thái Khóa/Chỉ hiện ROI này của nhánh nâng cao là trạng thái phiên làm việc, không lưu.)

---

## 8. Giới hạn đã biết / quyết định thiết kế (nói rõ để không hiểu nhầm là bug)

**Còn thật sự chưa hoàn thiện**:
1. **Cọ vẽ & đo lường 2D**: việc rê chuột vẽ/đo vẫn phải làm trực tiếp trên khung 2D — plugin chỉ bật/tắt và cấu hình đúng công cụ gốc, không tự động thao tác hộ (đúng bản chất, không phải lỗi).
2. **Cập nhật bề mặt 3D**: với mặt nạ rất lớn (gần hết thể tích ảnh), việc dựng lại 3D có thể mất khá lâu — nên dùng cho mặt nạ kích thước vừa phải (ROI thật sự "quan tâm", không phải toàn bộ ảnh). **Việc dựng bề mặt nhạy cảm với bộ nhớ và phụ thuộc vào kích thước volume, ngưỡng đã chọn, thuật toán và chất lượng (quality) — không có một ngưỡng RAM cố định đúng cho mọi dataset.** Trên máy có RAM khả dụng thấp, bước này có thể chậm hoặc không hoàn tất — đóng bớt ứng dụng khác và/hoặc giảm quality xuống nếu gặp tình trạng "treo". **[Sửa 22/09/2026, Post-Phase-14 Release Closure]**: trước đó ghi ngưỡng cố định "~5GB" — không có bằng chứng thật cho một ngưỡng cụ thể như vậy; thực tế Phase 14 đã build thành công surface đại diện (145,772 điểm) khi RAM khả dụng chỉ 1.82GB (dataset `0801`, quality "Low", threshold phù hợp) — chứng minh không tồn tại ngưỡng cố định, mà phụ thuộc tổ hợp nhiều yếu tố.
3. **Ghi chú lấy vị trí** (đã sửa ở Phase 09 — không còn fallback `(0, 0, 0)`): ưu tiên điểm chọn 3D gần nhất; nếu chưa chọn, dùng vị trí crosshair 2D thật (click/kéo trên khung Axial/Coronal/Sagittal); nếu **chưa có vị trí hợp lệ nào cả** thì plugin **từ chối tạo ghi chú** và hiện cảnh báo yêu cầu chọn vị trí trước — không còn âm thầm ghi `(0, 0, 0)`.
4. **Phát triển vùng** trên mặt nạ lớn/thể tích CT thật cũng cần đủ RAM tương tự mục 2 (tính toán trên hàng chục triệu voxel).
5. **Lịch sử Hoàn tác/Làm lại bị giới hạn 10 bước** (mỗi mặt nạ riêng) — thiết kế cố ý, không phải thiếu sót: mỗi bước lưu toàn bộ ma trận mặt nạ thật trong RAM (không phải diff); với thể tích CT thật cỡ 512×512×108 mỗi bước tốn khoảng 27MB. Tổng dung lượng giữ lại tối đa qua thao tác bình thường (đã chứng minh bằng test, xem `CT3D_P11_TEST_AUTOMATION_REPORT.md` mục 11) là **10 bước ≈ 273.6MB** — không phải "10 bước undo + 10 bước redo cùng lúc" (điều đó không bao giờ xảy ra được: mỗi lần lưu thao tác mới sẽ luôn xoá sạch lịch sử redo).

**Quyết định thiết kế (không phải thiếu sót)**:
1. **Đo khoảng cách/diện tích 2D không có danh sách riêng trong plugin** — cố ý điều khiển công cụ đo gốc thay vì tạo thêm 1 nguồn dữ liệu đo lường thứ hai (tránh 2 danh sách lệch nhau). Kết quả luôn xem đúng ở tab "Measures" gốc của InVesalius.
2. **Watershed và các phép toán hình thái học (dilate/erode/mở-đóng vùng) không có trong plugin** — InVesalius gốc đã có Watershed thật riêng (dùng qua UI gốc), không cần plugin làm lại. *(Đúng với bản ổn định `ct3d-rc1`. Trên nhánh `enhancement/advanced-segmentation`, E3 có thêm "Làm mịn mặt nạ" dùng đóng→mở hình thái học — xem mục 2.4.)*
3. **(Nhánh nâng cao) Giao diện tiếng Việt dùng bộ dịch riêng của plugin** (`plugins/roi_viewer/locale_vi.py`), vì InVesalius không có bản dịch tiếng Việt. Giao diện gốc InVesalius (menu, thanh công cụ, tab Masks/Measures, hộp thoại hệ thống) vẫn theo ngôn ngữ InVesalius đang chọn — plugin không sửa phần dịch của InVesalius. Thông báo in ra console (dùng khi gỡ lỗi) vẫn là tiếng Anh.

**Lỗi đã biết của bản ổn định `ct3d-rc1` — sai toạ độ 3D↔voxel (đã sửa trên nhánh `enhancement/advanced-segmentation`, 30/09/2026)**:
Bản ổn định dùng sai thứ tự spacing (`Slice().spacing` thực chất là (x, y, z)) và không đổi dấu trục y giữa khung 2D và khung 3D (InVesalius lật trục Y cho surface/volume trong khung 3D). Hệ quả trên bản ổn định: mặt phẳng C8 và quả cầu marker nằm **lệch/đối xứng qua trục y**, không cắt xuyên qua surface; mặt phẳng Axial sai kích thước với dữ liệu không đẳng hướng (ví dụ `0051`: 0.4785/0.4785/1.5 mm); **Chọn điểm 3D → 2D và hạt giống Phát triển vùng chọn từ 3D rơi sai voxel** (hàng coronal luôn bị kẹp về 0). Tag `ct3d-rc1` **không** được sửa; nhánh nâng cao đã sửa (`7b245865`, `c9f220bd`) — xem `CT3D_COORDINATE_SPACING_FIX_REPORT.md`. Trên nhánh nâng cao, mặt phẳng C8 giờ cắt **xuyên qua** surface đúng vị trí crosshair 2D, và ô toạ độ "Chọn điểm trong 3D" hiện toạ độ cùng hệ với khung 2D.

**Lỗi đã biết của bản ổn định `ct3d-rc1` — đọc/ghi mặt nạ chưa theo đúng quy ước của InVesalius (đã sửa trên nhánh `enhancement/advanced-segmentation`, 30/09/2026)**:
InVesalius tính mặt nạ ngưỡng "lười" (chỉ tính lát cắt khi khung 2D hiển thị lần đầu) và coi voxel bị cọ Xóa (giá trị 1) là nền. Trên bản ổn định: mặt nạ Phát triển vùng có thể **mất voxel** khi lần đầu cuộn tới một lát Coronal/Sagittal chưa xem; Đo thể tích và Xuất mặt nạ NumPy/NRRD chỉ tính các lát đã được tính và vẫn đếm voxel đã bị Xóa bằng cọ. Nhánh nâng cao đã sửa (một module chung `core/native_mask.py`, áp dụng cho Phát triển vùng, Chấp nhận xem trước, Hậu xử lý, Xem trước 3D, Đo thể tích, Xuất NumPy/NRRD) — xem `CT3D_NATIVE_MASK_CONTRACT_FIX_REPORT.md`.

**Chỉ nhánh `enhancement/advanced-segmentation` — giới hạn E5 hiện tại (trạng thái thật, không phải lỗi bị giấu)**:
1. **Hướng ảnh lát cắt trên mặt phẳng 3D (E5A)**: đã chứng minh bằng test dựng hình thật (30/09/2026) — mọi khối mẫu hiển thị đúng voxel của nó ở cả 3 mặt phẳng. Kiểm tra bằng mắt của người vận hành (Manual QA E5-B/C/D) vẫn là mục riêng, phải làm trên bản đã có sửa lỗi toạ độ `c9f220bd` (kết quả trước đó không dùng được, vì ảnh từng lấy sai lát cắt và nằm đối xứng qua trục y).
2. **Cắt hiển thị với đối tượng "Bề mặt cuối của ROI hiện tại" chỉ tự tìm được bề mặt do chính nút "Cập nhật bề mặt 3D từ ROI hiện tại" của plugin dựng ra trong phiên làm việc hiện tại.** Bề mặt mở từ project đã lưu, hoặc dựng qua tab Surface gốc của InVesalius, sẽ báo *"ROI hiện tại chưa có bề mặt 3D cuối."* — plugin **cố ý không đoán** mặt nạ nào ứng với bề mặt nào, vì mã nguồn InVesalius không lưu liên kết này (chỉ số surface ≠ chỉ số mask). Hãy bấm "Cập nhật bề mặt 3D từ ROI hiện tại" một lần cho ROI đó.
3. **Ảnh trên mặt phẳng dùng lại đúng ảnh lát cắt đã được InVesalius tổng hợp để hiển thị 2D** — không phải "CT thô": gồm CT sau Window/Level hiện tại, **cộng màu mặt nạ hiện hành** và **lớp phủ Xem trước (E2) nếu đang bật**. Đây là chủ đích (tái dùng dữ liệu hiển thị thật, không tự tính lại Window/Level).
4. **Window/Level**: đổi W/L bằng công cụ gốc thì ảnh tự làm mới ngay (không cần di chuyển crosshair) — tối đa 1 lần làm mới mỗi vòng sự kiện khi đang kéo chuột W/L. Ảnh luôn làm mới **tại vị trí mặt phẳng đang đứng**, kể cả khi đã tắt "Đồng bộ 2D → 3D" (mặt phẳng không bị dịch chuyển).

---

## 9. Trình tự demo đề xuất (cho báo cáo/bảo vệ)

1. Import DICOM (`python app.py -i <thư mục DICOM>`) → mở **Plugins → ROI Viewer**.
2. Tab **Phân đoạn** (2.1): tick *Tự động xác định ngưỡng (Otsu)* → **Tạo mặt nạ** → thấy mặt nạ mới ở tab **ROI & 3D**, danh sách **Quản lý ROI**.
3. Tab **ROI & 3D** (3.2): bấm **Cập nhật bề mặt 3D từ ROI hiện tại** → thấy khối 3D hiện ra ở khung "Volume".
4. Tab **Hiển thị** (4.2): **Chọn điểm trong 3D** → click vào khối 3D → quan sát toạ độ + 3 khung 2D tự nhảy.
5. Tab **Phân đoạn** (2.2): nhập độ dung sai vừa phải (vd. 30) → **Chọn điểm hạt giống (3D)** → click 1 điểm khác trên khối 3D → thấy mặt nạ "Region Growing 1" mới xuất hiện trong danh sách Quản lý ROI.
6. Tab **Phân đoạn** (2.5): mở *Chỉnh sửa thủ công (cọ vẽ)* → **Bật cọ vẽ** → vẽ thêm/xoá bớt vài nét trên khung 2D → tab **ROI & 3D** → **Cập nhật bề mặt 3D từ ROI hiện tại** lần nữa → quan sát khối 3D đổi hình theo đúng nét vừa vẽ.
7. Tab **Công cụ** → **Đo lường**: chọn **3D** → **Bắt đầu đo** → click 2 điểm trên khối 3D → xem kết quả mm.
8. Tab **Công cụ** → **Ghi chú**: **Thêm tại vị trí hiện tại** → thấy ghi chú xuất hiện đúng vị trí vừa chọn.
9. Tab **Công cụ** → **Xuất dữ liệu**: **Lưu** project → đóng InVesalius → mở lại, **File → Open Project** đúng file vừa lưu → mở lại **Plugins → ROI Viewer** → kiểm chứng: danh sách ROI còn nguyên, ghi chú còn nguyên.
10. Tab **Công cụ** → **Xuất dữ liệu**: **Xuất bề mặt** → chọn STL → lưu file → mở bằng phần mềm xem STL bất kỳ để kiểm chứng.

> Trên bản ổn định `ct3d-rc1` các bước trên giống hệt, chỉ khác tên tab/nút tiếng Anh (bảng mục 1.2) và không có tab "ROI & 3D" (danh sách ROI và nút Update 3D Surface nằm trong tab Segmentation).
