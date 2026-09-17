# CT3D Manual QA Checklist — 7 mục cần thao tác chuột thật

> File này liệt kê 7 mục **không thể tự động hoá được** (cần chuột/tương tác GUI thật), tồn đọng từ Phase 09 (`CT3D_P09_INTERACTION_QA_REPORT.md` mục 9), gộp thành checklist chính thức ở Phase 12.
>
> **Cập nhật Phase 13 (16/09/2026): 7/7 ĐÃ PASS.** Người vận hành thật đã tự thao tác chuột trên GUI InVesalius thật (dataset CT `0051`) và báo cáo kết quả — ghi lại nguyên văn bên dưới. Claude Code KHÔNG tự thao tác chuột/bàn phím, không dùng pubsub injection hay giả lập sự kiện — mọi "Actual Result"/"PASS/FAIL" dưới đây là do người vận hành tự thực hiện và tự cung cấp; Claude Code chỉ ghi lại đúng nguyên văn.
>
> **Ảnh chụp màn hình**: người vận hành xác nhận đã quan sát trực tiếp trong phiên thao tác thật, nhưng KHÔNG có file ảnh nào được đưa vào repository trong phiên báo cáo này. Mọi ô "Screenshot" bên dưới ghi đúng: *"Evidence visually supplied by operator during manual QA session; image file not stored in repository."* — không tự bịa đường dẫn ảnh.
>
> **Chuẩn bị chung đã dùng**: `python app.py -i D:\PyTools\dicom_samples\0051` (CT, SIEMENS, 108×512×512, spacing ≈ (0.4785, 0.4785, 1.5) mm), sau đó mở `Plugins → ROI Viewer`.

---

## 1. P08.5 — D9/C7: Update 3D Surface qua dialog thật

**Preconditions**: Project đã import CT thật (`0051`), đã tạo 1 mask qua tab Segmentation (Threshold/Otsu).

**Exact Steps** (tên nút thật, xác nhận qua source `segmentation_panel.py`):
1. Trong tab Segmentation, chọn radio **"Draw"**, bấm **"Enable Brush Tool"**, vẽ thêm 1 vùng mask ra ngoài biên hộp sọ trên khung 2D.
2. Chuyển radio sang **"Erase"**, xoá một phần vùng vừa vẽ.
3. Bấm **"Disable Brush Tool"**.
4. Chụp/quan sát surface 3D hiện tại (trước Update) — chưa có phần lồi tương ứng vùng mask mới.
5. Chọn đúng mask vừa sửa, bấm **"Update 3D Surface from Selected ROI"**.
6. Quan sát toàn bộ dialog tiến trình build surface thật (không dùng batch mode/test script).

**Expected Result**: Dialog tiến trình mở, GUI vẫn responsive, dialog tự đóng khi xong (không treo, không traceback). Surface 3D được cập nhật, phản ánh đúng vùng mask Brush/Eraser vừa sửa.

**Actual Result**: Người vận hành vẽ mask bằng Brush ra ngoài biên hộp sọ; trước Update, surface 3D chưa có các phần tương ứng. Sau khi bấm "Update 3D Surface from Selected ROI", surface 3D xuất hiện các phần lồi tương ứng đúng với vùng mask 2D mới vừa vẽ. Xác nhận đúng chuỗi thật: Brush/Eraser 2D → mask thay đổi → Update 3D Surface → hình học 3D thay đổi. Không crash. Không cần đóng/mở lại project mới thấy thay đổi.
**PASS/FAIL**: `PASS`
**Evidence**: Build hoàn tất không treo, không traceback; hình học surface sau Update khác hình học trước Update, đúng vị trí vùng mask vừa sửa.
**Screenshot**: Evidence visually supplied by operator during manual QA session; image file not stored in repository.
**Notes**: Đây là bằng chứng GUI thật bổ sung cho D9/C7 (đã WORKING từ Phase 08 qua evidence tự động hoá synthetic-dataset) — không đổi status D9/C7, chỉ bổ sung real-GUI evidence.

---

## 2. B4 — Zoom/Pan 2D

**Preconditions**: Project đã import CT thật, đang xem 3 khung 2D (Axial/Coronal/Sagittal).

**Exact Steps**:
1. Cuộn chuột (scroll wheel) trên từng khung 2D để zoom in/out.
2. Giữ phím giữ tương ứng kéo để pan.
3. Lặp lại trên cả 3 khung.

**Expected Result**: Ảnh phóng to/thu nhỏ mượt theo con trỏ chuột; pan di chuyển đúng hướng kéo; không giật/lag; sau nhiều thao tác vẫn scroll slice bình thường.

**Actual Result**: Zoom/Pan thực hiện thật trên cả 3 khung 2D, hoạt động đúng như mong đợi.
**PASS/FAIL**: `PASS`
**Evidence**: Zoom in/out và pan hoạt động đúng trên Axial/Coronal/Sagittal, không crash, không hành vi camera bất thường.
**Screenshot**: Evidence visually supplied by operator during manual QA session; image file not stored in repository.
**Notes**: —

---

## 3. C3 — Rotate/Pan/Zoom 3D

**Preconditions**: Project đã import CT thật, đã có surface 3D hiển thị (tạo ở bước chuẩn bị chung/mục 1).

**Exact Steps**:
1. Giữ chuột trái kéo trên khung 3D để xoay camera.
2. Cuộn chuột để zoom in/out.
3. Giữ phím tương ứng kéo để pan.

**Expected Result**: Camera xoay/pan/zoom mượt, đúng hướng thao tác chuột; surface không biến dạng/nhấp nháy bất thường; vẫn pick/render bình thường sau khi thao tác.

**Actual Result**: Rotate/Pan/Zoom thực hiện thật trên viewport 3D, hoạt động đúng như mong đợi.
**PASS/FAIL**: `PASS`
**Evidence**: Camera xoay/zoom/pan đúng hướng thao tác chuột, surface không biến dạng, không crash.
**Screenshot**: Evidence visually supplied by operator during manual QA session; image file not stored in repository.
**Notes**: —

---

## 4. D4 — Brush (vẽ tay)

**Preconditions**: Đã chọn 1 mask trong ROI List.

**Exact Steps** (tên nút thật):
1. Chọn radio **"Draw"**.
2. Bấm **"Enable Brush Tool"**.
3. Trên khung Axial, giữ chuột trái vẽ 1 nét đủ lớn, dễ nhận biết.
4. Chuyển sang slice gần đó, vẽ thêm 1 vùng khác.
5. Quay lại slice đầu, kiểm tra vùng đã vẽ còn nguyên.
6. Bấm **"Disable Brush Tool"**.

**Expected Result**: Mask xuất hiện đúng dưới đường chuột (không lệch/offset); vùng brush còn tồn tại sau khi đổi slice; Disable Brush Tool dừng edit; không crash.

**Actual Result**: Brush vẽ đúng vị trí con trỏ chuột; giữ lại đúng khi đổi slice; Disable Brush Tool dừng chỉnh sửa đúng như mong đợi. Không phát hiện hiện tượng lệch toạ độ (BRUSH COORDINATE OFFSET).
**PASS/FAIL**: `PASS`
**Evidence**: Vùng vẽ đúng vị trí, giữ nguyên qua đổi slice, không crash.
**Screenshot**: Evidence visually supplied by operator during manual QA session; image file not stored in repository.
**Notes**: —

---

## 5. D5 — Eraser (tẩy tay)

**Preconditions**: Mask đã có vùng vẽ sẵn (dùng chính vùng vừa vẽ ở mục 4).

**Exact Steps**:
1. Chọn radio **"Erase"** (Brush Tool bật lại nếu đang tắt).
2. Kéo chuột qua khoảng một nửa vùng vừa vẽ ở mục 4.
3. Tắt Brush Tool sau khi xoá.

**Expected Result**: Chỉ vùng đi qua eraser bị xoá; phần còn lại của ROI còn nguyên; không xoá nhầm toàn mask hay mask khác; không crash.

**Actual Result**: Eraser xoá đúng vùng đã vẽ bằng Brush; phần còn lại của mask giữ nguyên đúng như mong đợi.
**PASS/FAIL**: `PASS`
**Evidence**: So sánh trước/sau erase — hình dạng thay đổi đúng vị trí đã kéo chuột, không ảnh hưởng phần còn lại của mask.
**Screenshot**: Evidence visually supplied by operator during manual QA session; image file not stored in repository.
**Notes**: —

---

## 6. E2 — Đo khoảng cách 2D (Distance)

**Preconditions**: Project đã import CT thật (`0051`, spacing ≈ 0.4785 mm/pixel trong mặt phẳng Axial).

**Exact Steps**:
1. Trong tab Measurements, bật công cụ đo khoảng cách 2D (công cụ Linear thật của InVesalius).
2. Trên khung Axial, chọn 2 điểm — thực hiện 2 lần đo với khoảng cách khác nhau.
3. Đọc kết quả trong tab "Measures" gốc.

**Expected Result**: Tool được kích hoạt; measurement thật xuất hiện trong Measures; đường dài hơn cho giá trị lớn hơn; không crash.

**Actual Result**:
- Axial Linear **M1 = 143.951 mm**
- Axial Linear **M2 = 189.741 mm**
- Đường dài hơn (M2) cho giá trị lớn hơn — đúng quan hệ vật lý mong đợi.
- Measurement xuất hiện thật trong tab Measures. Không crash.

**PASS/FAIL**: `PASS`
**Evidence**: 2 measurement Linear thật (M1=143.951mm, M2=189.741mm), quan hệ độ dài-giá trị đúng chiều, xuất hiện đúng trong Measures.
**Screenshot**: Evidence visually supplied by operator during manual QA session; image file not stored in repository.
**Notes**: Loại measurement: Linear. Location: Axial.

---

## 7. E3 — Đo diện tích 2D (Area)

**Preconditions**: Project đã import CT thật.

**Exact Steps**:
1. Trong tab Measurements, bấm **"Measure Area (2D)"**.
2. Vẽ 1 polygon trên khung Sagittal, đóng polygon.
3. Vẽ 1 polygon khác (lớn hơn) trên khung Coronal, đóng polygon.
4. Đọc Area từ overlay/tab Measures thật.

**Expected Result**: Polygon tạo thành công; Area hiển thị đúng trong Measures/overlay; polygon lớn hơn cho Area lớn hơn; không crash.

**Actual Result**:
- Sagittal polygon: **Area = 2674.851 mm²**
- Coronal polygon: **Area = 5367.750 mm²**
- Polygon lớn hơn (Coronal) cho Area lớn hơn — đúng quan hệ vật lý mong đợi.
- Overlay hiển thị đầy đủ Area/Min/Max/Mean/Std/Perimeter thật. Không crash.

**PASS/FAIL**: `PASS`
**Evidence**: 2 polygon thật (Sagittal=2674.851mm², Coronal=5367.750mm²), quan hệ kích thước-diện tích đúng chiều, overlay số liệu đầy đủ.
**Screenshot**: Evidence visually supplied by operator during manual QA session; image file not stored in repository.
**Notes**: Giá trị Area lấy từ overlay thật (không nhầm với cột Value của Density Polygon).

---

## C8 — Visual Sync 2D → 3D Slice Planes

> **Phase 13.5 (pre-Phase-14)**: nâng cấp trực quan cho C8 (Sync 2D→3D, đã `WORKING` từ Phase 09/11) — thêm 3 mặt phẳng bán trong suốt (`core/slice_planes_3d.SlicePlanes3D`) trong khung Volume, thể hiện đúng vị trí 3 mặt cắt Axial/Coronal/Sagittal hiện tại, bên cạnh marker nhỏ đã có sẵn. **KHÔNG phải feature ID mới (không phải C9)** — chỉ là visual enhancement của C8.
>
> **KHÔNG mục nào dưới đây đã PASS.** Claude Code không tự thao tác chuột thật — mọi kết quả để `NOT_RUN` cho đến khi người dùng tự thao tác và tự điền, giống các mục 1-7 ở trên trước khi có bằng chứng thật.

**PRECONDITION**:
1. Import `0051`.
2. Có surface 3D (Threshold/Otsu → Create Mask → Update 3D Surface).
3. Mở ROI Viewer → tab Interaction.
4. Người dùng **tự** bật công cụ native trên toolbar InVesalius: **`"Slices' cross intersection"`** (plugin KHÔNG tự bật công cụ này).
5. Tick **`Sync 2D -> 3D`**.
6. Tick **`Show slice planes in 3D`** (mặc định đã ON sẵn khi mở plugin).

### TEST A — Axial
Click/kéo crosshair trên khung Axial.
**Expected**: marker di chuyển; mặt phẳng axial di chuyển; mặt phẳng sagittal/coronal vẫn giao đúng tại cùng điểm.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST B — Sagittal
Click/kéo trên khung Sagittal.
**Expected**: cả 3 mặt phẳng cập nhật đúng.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST C — Coronal
Click/kéo trên khung Coronal.
**Expected**: cả 3 mặt phẳng cập nhật đúng.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST D — Continuous drag
Kéo crosshair liên tục (giữ chuột kéo qua nhiều vị trí).
**Expected**: mặt phẳng di chuyển mượt; không tạo actor trùng lặp; không crash.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E — Show planes OFF
Bỏ tick **`Show slice planes in 3D`**.
**Expected**: 3 mặt phẳng biến mất; marker vẫn tiếp tục di chuyển theo crosshair.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST F — Sync OFF
Bỏ tick **`Sync 2D -> 3D`**.
**Expected**: marker và mặt phẳng đứng yên, không cập nhật nữa dù có click/kéo 2D.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST G — Sync ON trở lại
Tick lại **`Sync 2D -> 3D`** (và **`Show slice planes in 3D`** nếu đã tắt ở TEST E).
**Expected**: cập nhật tiếp tục hoạt động, mặt phẳng hiện đúng vị trí hiện tại (không phải vị trí cũ trước khi tắt).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST H — Camera giữ nguyên
Xoay/zoom/pan khung 3D bằng tay, sau đó kéo crosshair trên khung 2D.
**Expected**: mặt phẳng/marker di chuyển đúng; **hướng camera KHÔNG tự đổi** (plugin không tự rotate/zoom/pan/reset camera).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST I — Đóng/mở lại plugin
Đóng cửa sổ ROI Viewer, mở lại từ menu Plugins, lặp lại TEST A.
**Expected**: không có actor trùng lặp (đúng 1 marker + 3 mặt phẳng, không phải 2+6).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

**C8 Visual Sync tổng kết**: `NOT_RUN` (9/9 mục A-I chưa chạy — người dùng tự chạy sau khi Claude hoàn thành phần code/test tự động).

---

## Tổng kết

| # | Mục | PASS/FAIL |
|---|---|---|
| 1 | P08.5 (D9/C7 dialog thật) | `PASS` |
| 2 | B4 (Zoom/Pan 2D) | `PASS` |
| 3 | C3 (Rotate/Pan/Zoom 3D) | `PASS` |
| 4 | D4 (Brush) | `PASS` |
| 5 | D5 (Eraser) | `PASS` |
| 6 | E2 (Distance 2D) | `PASS` |
| 7 | E3 (Area 2D) | `PASS` |
| 8 | C8 Visual Sync (mặt phẳng 2D→3D, Phase 13.5, mục A-I) | `NOT_RUN` |

**MANUAL_QA_COMPLETE (7 mục gốc): YES** — 7/7 PASS, xác nhận bằng phiên thao tác chuột thật của người vận hành trên GUI InVesalius thật (dataset `0051`, 16/09/2026). Xem `CT3D_P13_PERFORMANCE_COMPARISON_REPORT.md` mục 4 cho closure đầy đủ và cập nhật status matrix liên quan.

**C8 Visual Sync (Phase 13.5): `NOT_RUN`** — chờ người dùng tự thao tác chuột thật theo checklist ở mục "C8 — Visual Sync 2D → 3D Slice Planes" phía trên.
