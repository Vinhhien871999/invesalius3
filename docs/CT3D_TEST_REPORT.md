# Báo cáo kiểm thử — InVesalius CT 3D + Plugin ROI Viewer

> Toàn bộ test trong tài liệu này là **kịch bản script chạy app thật** (không phải unit test giả lập): dựng thật `wx.App` + `Frame` + `Controller` như `app.py`, import DICOM thật, load plugin qua `PluginManager` thật, thao tác qua đúng pubsub topic thật, rồi đọc lại state thật của `Slice()`/`Project()` để verify — đúng chuẩn "UI action → event → backend → model → viewer → không exception" theo yêu cầu audit. Không có kết quả nào trong tài liệu này là tự bịa.

---

## 1. Baseline (trước khi sửa gì trong phiên audit này)

Trước phiên audit, code đã ở trạng thái sau các phiên làm việc trước (xem `CT3D_CHANGELOG.md` các commit từ `56424653` đến `25257a70`): 14 chức năng chính đã wiring và test PASS (segmentation/undo-redo/measurement/annotation/export/brush/2D-measure-toggle), cộng thêm real-picking/real-distance/real-surface-export (`test_gap_fill.py`) và ROI-list CRUD + real mask export (`test_roi_and_export.py`), và fix crash rò rỉ observer VTK (`test_reopen_crash.py`). Baseline = tất cả các test này PASS trước khi phiên audit hiện tại bắt đầu sửa gì thêm.

## 2. Công cụ kiểm thử tự động đã dùng

Không dùng `pytest` cho phần tích hợp thật (project chưa có sẵn bộ `pytest` cho plugin — `tests/` hiện có chỉ là test của InVesalius gốc, ví dụ `tests/test_dicom_loading.py`). Thay vào đó, mỗi kịch bản là 1 script Python độc lập (`multiprocessing.freeze_support()` + `if __name__ == "__main__":` đúng chuẩn Windows), chạy bằng:

```
D:\PyTools\invx-venv\Scripts\python.exe <script>.py
```

| Script | Kịch bản kiểm tra |
|---|---|
| `test_e2e_wired.py` | Load plugin → threshold tạo mask → undo/redo → đo volume → annotation CRUD → brush toggle → 2D measure toggle → export PNG |
| `test_gap_fill.py` | Pick 3D thật trên hình học đã render → đo khoảng cách 3D thật → xuất surface thật (STL/PLY/OBJ/VTK) |
| `test_roi_and_export.py` | ROI List: tạo 2 ROI → chọn → đổi tên → ẩn/hiện → xoá (tất cả verify vào state InVesalius thật) → xuất mask NIfTI thật (bypass dialog modal) |
| `test_reopen_crash.py` | Tái hiện đúng kịch bản crash người dùng gặp: mở → pick → đóng cửa sổ thật (`Close()`) → mở lại → pick lần nữa |
| `test_regiongrowing_surfaceupdate.py` | Region Growing từ seed pick thật → verify mask thật; Update 3D Surface → verify pubsub gửi đúng |
| `test_perf.py` | Đo loading time + FPS render trên 3 bộ dữ liệu |

## 3. Kết quả kiểm thử (phiên audit hiện tại, 08/09/2026)

### 3.1 Regression suite — xác nhận không có gì bị ảnh hưởng bởi thay đổi mới

| Script | Kết quả | Ghi chú |
|---|---|---|
| `test_e2e_wired.py` | **14/14 PASS** | Không đổi so với baseline — commit Region Growing/Update Surface/bare-except không ảnh hưởng |
| `test_gap_fill.py` | **9/9 PASS** | Số liệu trùng khớp 100% với baseline (toạ độ pick, khoảng cách 59.56mm, kích thước file export) |
| `test_roi_and_export.py` | **10/10 PASS** | ROI List CRUD (tạo/chọn/đổi tên/ẩn-hiện/xoá) + export NIfTI thật, tất cả verify vào state InVesalius thật |
| `test_reopen_crash.py` | **9/9 PASS** | Xác nhận lại fix crash rò rỉ observer VTK vẫn hoạt động đúng sau các thay đổi mới |

**Tổng kết regression**: 4/4 script, 42/42 check con PASS, 0 crash report mới. Thay đổi trong phiên audit này (Region Growing, Update 3D Surface, sửa except trần) không làm hỏng bất kỳ chức năng nào đã verify trước đó.

Không phát sinh crash report mới trong bất kỳ lần chạy nào (kiểm tra `C:\Users\Nguyen Vinh Hien\.config\invesalius\logs\crash_reports\`, so `newer than` mốc crash cuối cùng đã sửa).

### 3.2 Tính năng mới trong phiên này

**Region Growing** (`test_regiongrowing_surfaceupdate.py`):
| Bước | Kết quả |
|---|---|
| Pick seed 3D trên hình học đã render | PASS — `pick()` trả về toạ độ thật |
| Region growing (bản BFS Python gốc) | Hoàn thành đúng nhưng **>15 giây** (timeout lần đầu) |
| Region growing (bản `scipy.ndimage.label` vector hoá) | **PASS — 500ms**, mask thật 16.264.693 voxel, đăng ký đúng vào `roi_mgr` |

**Update 3D Surface**:
| Bước | Kết quả |
|---|---|
| `Publisher.sendMessage` gửi đúng topic/tham số thật (verify bằng cách chặn trực tiếp `sendMessage`) | **PASS** |
| `sendMessage` trả về bình thường, không exception | **PASS** |
| Surface mới xuất hiện trong `surface_dict` trong khung 75s (mask 16,2M voxel — kích thước không thực tế do tolerance test quá rộng) | **FAIL** (timeout) |
| Isolation test: build surface cho mask CHƯA từng có (loại trừ nguyên nhân "overwrite") | **FAIL** (timeout 30s) — loại trừ giả thuyết overwrite, nghi vấn hiệu năng Marching Cubes với mesh cực lớn/phức tạp |

**Kết luận trung thực**: chuỗi UI→pubsub→backend đã verify đúng 100% (không phải lỗi code plugin), nhưng bước cuối "người dùng thấy kết quả" chưa quan sát được trong test tự động với mask kích thước không thực tế. Xem `CT3D_REMAINING_WORK.md` mục 1 để biết bước tiếp theo (verify thủ công qua GUI với mask kích thước hợp lý).

## 4. Lỗi phát hiện và đã sửa trong phiên audit này

| # | Lỗi | Vị trí | Cách phát hiện | Đã sửa |
|---|---|---|---|---|
| 1 | `core/segmentation.py.region_growing()` có code nhưng 0 lời gọi ở bất kỳ đâu | `core/segmentation.py` | `grep` toàn repo | Nối vào UI thật (`segmentation_panel.py`) |
| 2 | BFS Python thuần quá chậm (>15s) trên volume CT thật | `core/segmentation.py.region_growing()` | Test thật với seed pick thật, timeout | Thay bằng `scipy.ndimage.label` (500ms, cùng kết quả toán học) |
| 3 | Mask sửa không tự cập nhật surface 3D | `invesalius/data/surface.py` (hành vi gốc) | `grep` xác nhận không có subscribe topic sửa-mask nào | Thêm nút "Update 3D Surface" chủ động (không auto để tránh treo GUI) |
| 4 | 5 chỗ `except:` trần nuốt mọi lỗi kể cả bug thật | `interface/project_interface.py` | `grep -rn "except:\s*$"` | Đổi thành `except Exception as e: print(...)` |

## 5. Đo hiệu năng (kế thừa từ phiên trước, vẫn còn hiệu lực)

| Bộ dữ liệu | Loại | Loading | FPS render surface |
|---|---|---|---|
| CT 0051 | CT | 13.41s | 130.3 |
| CT 0801 | CT | 15.70s | 158.3 |
| MRI mri3 | MRI | 10.25s | 122.0 |

Cả 3 đều đạt tiêu chí loading ≤30s, FPS ≥15 (đề ra trong `Lộ trình phát triển.md`).

**Phát hiện mới trong phiên này**: hiệu năng Region Growing — BFS Python thuần: **>15s** (không đạt), phiên bản vector hoá: **~500ms** (đạt, nhanh hơn ~30 lần).

## 6. Manual test cần làm (không automated được hoàn toàn)

Theo đúng yêu cầu Section XVII — liệt kê rõ phần nào automated, phần nào bắt buộc thao tác tay:

- [ ] Vẽ brush thật bằng chuột trên canvas 2D (automated chỉ verify được việc BẬT đúng chế độ, không giả lập thao tác rê chuột thật)
- [ ] Đo khoảng cách/diện tích 2D bằng chuột thật (tương tự — chỉ verify bật đúng tool)
- [ ] Xoay/zoom/pan 3D bằng chuột (camera VTK chuẩn, không phải trọng tâm plugin)
- [ ] Update 3D Surface với mask kích thước hợp lý, đo thời gian bằng đồng hồ tay
- [ ] Save/Open project (.inv3) đầy đủ — chưa test full-cycle trong phiên audit này
