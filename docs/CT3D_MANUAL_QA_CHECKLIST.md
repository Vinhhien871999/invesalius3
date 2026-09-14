# CT3D Manual QA Checklist — 7 mục cần thao tác chuột thật

> File này liệt kê 7 mục còn lại **không thể tự động hoá được** (cần chuột/tương tác GUI thật), tồn đọng từ Phase 09 (`CT3D_P09_INTERACTION_QA_REPORT.md` mục 9), gộp lại đây theo yêu cầu Phase 12 thành 1 file checklist chính thức, độc lập, dễ dùng cho người vận hành thật.
>
> **KHÔNG mục nào trong file này đã được đánh dấu PASS.** Claude Code không tự thao tác chuột/bàn phím thật trên GUI — mọi ô "Actual Result"/"PASS/FAIL" dưới đây được để `NOT_RUN` cho đến khi một người dùng thật thực hiện đúng các bước và tự ghi lại kết quả. Không dùng pubsub injection hay giả lập sự kiện để tự tuyên bố "đã chạy chuột thật".
>
> **Chuẩn bị chung**: mở InVesalius, import dataset `D:\PyTools\dicom_samples\0051` (hoặc bất kỳ dataset CT thật nào có sẵn), mở plugin ROI Viewer từ menu Plugins.

---

## 1. P08.5 — D9/C7: Update 3D Surface qua dialog thật (không `batch_mode`)

**Preconditions**: Project đã import CT thật, đã tạo 1 mask qua tab Segmentation (Threshold).

**Exact Steps**:
1. Trong tab Segmentation của plugin, bật Brush (nút "Toggle Brush"), vẽ thêm 1 vùng nhỏ lên mask hiện tại trên khung 2D.
2. Tắt Brush.
3. Bấm nút "Update 3D Surface".
4. Quan sát dialog tiến trình build surface thật của InVesalius (KHÔNG phải `batch_mode` — dialog thật phải hiện ra).
5. Đợi dialog đóng, quan sát khung 3D.

**Expected Result**: Dialog tiến trình hiện ra và tự đóng khi xong (không treo). Surface 3D trong khung Volume đổi hình dạng, phản ánh đúng vùng vừa vẽ thêm bằng brush (không phải hình dạng cũ trước khi sửa).

**Actual Result**: `NOT_RUN`
**PASS/FAIL**: `NOT_RUN`
**Evidence**: _(điền: có build thành công không, thời gian, dialog có treo không)_
**Screenshot**: _(đính kèm ảnh trước/sau)_
**Notes**: _(bất kỳ quan sát bất thường nào)_

---

## 2. B4 — Zoom/Pan 2D

**Preconditions**: Project đã import CT thật, đang xem 1 khung 2D (Axial/Coronal/Sagittal).

**Exact Steps**:
1. Cuộn chuột (scroll wheel) trên khung 2D để zoom in/out.
2. Giữ phím giữa chuột (hoặc tổ hợp phím InVesalius quy định) kéo để pan.
3. Lặp lại trên cả 3 khung 2D.

**Expected Result**: Ảnh phóng to/thu nhỏ mượt theo con trỏ chuột; pan di chuyển đúng hướng kéo, không giật/lag, không văng ảnh ra ngoài vùng nhìn thấy được theo cách bất thường.

**Actual Result**: `NOT_RUN`
**PASS/FAIL**: `NOT_RUN`
**Evidence**: _(điền)_
**Screenshot**: _(điền)_
**Notes**: _(điền)_

---

## 3. C3 — Rotate/Pan/Zoom 3D

**Preconditions**: Project đã import CT thật, đã có ít nhất 1 surface 3D hiển thị.

**Exact Steps**:
1. Giữ chuột trái kéo trên khung 3D để xoay camera.
2. Cuộn chuột để zoom.
3. Giữ chuột giữa (hoặc Shift+chuột trái, tuỳ cấu hình InVesalius) kéo để pan.

**Expected Result**: Camera xoay/pan/zoom mượt, đúng hướng thao tác chuột, surface không biến dạng/nhấp nháy bất thường.

**Actual Result**: `NOT_RUN`
**PASS/FAIL**: `NOT_RUN`
**Evidence**: _(điền)_
**Screenshot**: _(điền)_
**Notes**: _(điền)_

---

## 4. D4 — Brush (vẽ tay)

**Preconditions**: Đã tạo 1 mask, đã bật Brush trong tab Segmentation.

**Exact Steps**:
1. Bấm "Toggle Brush" để bật.
2. Vẽ 1 đường trên khung 2D bằng cách giữ chuột trái kéo.
3. Chuyển slice, vẽ thêm 1 vùng khác.
4. Tắt Brush.

**Expected Result**: Vùng vẽ xuất hiện đúng màu mask, đúng vị trí con trỏ chuột, lưu lại đúng khi chuyển slice, không mất khi tắt Brush.

**Actual Result**: `NOT_RUN`
**PASS/FAIL**: `NOT_RUN`
**Evidence**: _(điền)_
**Screenshot**: _(điền)_
**Notes**: _(điền)_

---

## 5. D5 — Eraser (tẩy tay)

**Preconditions**: Mask đã có vùng vẽ sẵn (làm mục 4 trước).

**Exact Steps**:
1. Chuyển công cụ sang Eraser (nếu có nút riêng) hoặc dùng đúng cơ chế InVesalius quy định để xoá.
2. Kéo chuột trên vùng mask đã vẽ để xoá một phần.

**Expected Result**: Vùng bị xoá biến mất đúng theo đường kéo chuột, phần còn lại của mask không bị ảnh hưởng.

**Actual Result**: `NOT_RUN`
**PASS/FAIL**: `NOT_RUN`
**Evidence**: _(điền)_
**Screenshot**: _(điền)_
**Notes**: _(điền)_

---

## 6. E2 — Đo khoảng cách 2D (Distance)

**Preconditions**: Project đã import CT thật, biết trước spacing thật của dataset (xem `CT3D_DATASET_REGISTRY.md` — ví dụ dataset `0051`: spacing ≈ (0.4785, 0.4785, 1.5) mm).

**Exact Steps**:
1. Trong tab Measurements, bấm nút bật công cụ đo khoảng cách 2D.
2. Trên khung Axial, click điểm đầu, click điểm cuối cách nhau đúng N pixel theo 1 trục đã biết (ví dụ kéo ngang đúng 20 pixel theo trục X màn hình).
3. Đọc kết quả đo hiện ra trong tab "Measures" gốc của InVesalius.

**Expected Result (công thức đối chiếu)**: khoảng cách vật lý mong đợi = N × spacing_theo_trục_đó (mm). Ví dụ 20 pixel theo trục X trên dataset `0051` (spacing X ≈ 0.4785mm) → khoảng cách mong đợi ≈ 9.57mm. Sai số cho phép: ±1 pixel tương đương (do khó click chính xác tuyệt đối bằng tay).

**Actual Result**: `NOT_RUN` _(điền số đo thật hiện ra)_
**PASS/FAIL**: `NOT_RUN`
**Evidence**: _(điền: N pixel đã kéo, kết quả đo, sai số tính được)_
**Screenshot**: _(điền)_
**Notes**: _(điền)_

---

## 7. E3 — Đo diện tích 2D (Area)

**Preconditions**: Project đã import CT thật, biết trước spacing thật.

**Exact Steps**:
1. Trong tab Measurements, bấm nút bật công cụ đo diện tích (vẽ polygon) 2D.
2. Trên khung Axial, vẽ 1 hình chữ nhật đơn giản có kích thước biết trước theo pixel (ví dụ N=20 pixel × M=15 pixel).
3. Đóng polygon, đọc kết quả diện tích hiện ra trong tab "Measures" gốc.

**Expected Result (công thức đối chiếu)**: diện tích vật lý mong đợi = (N × spacing_x) × (M × spacing_y) mm². Ví dụ N=20, M=15 trên dataset `0051` (spacing X=Y≈0.4785mm) → diện tích mong đợi ≈ 9.57 × 7.18 ≈ 68.7mm². Sai số cho phép: theo đúng sai số vẽ tay ±1 pixel mỗi cạnh.

**Actual Result**: `NOT_RUN` _(điền số đo thật hiện ra)_
**PASS/FAIL**: `NOT_RUN`
**Evidence**: _(điền: N×M pixel đã vẽ, kết quả đo, sai số tính được)_
**Screenshot**: _(điền)_
**Notes**: _(điền)_

---

## Tổng kết

| # | Mục | PASS/FAIL |
|---|---|---|
| 1 | P08.5 (D9/C7 dialog thật) | `NOT_RUN` |
| 2 | B4 (Zoom/Pan 2D) | `NOT_RUN` |
| 3 | C3 (Rotate/Pan/Zoom 3D) | `NOT_RUN` |
| 4 | D4 (Brush) | `NOT_RUN` |
| 5 | D5 (Eraser) | `NOT_RUN` |
| 6 | E2 (Distance 2D) | `NOT_RUN` |
| 7 | E3 (Area 2D) | `NOT_RUN` |

**MANUAL_QA_COMPLETE: NO** cho đến khi cả 7 mục trên có kết quả thật do người dùng tự thao tác và tự điền.
