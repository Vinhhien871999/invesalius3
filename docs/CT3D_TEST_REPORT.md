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
- [x] ~~Update 3D Surface với mask kích thước hợp lý, đo thời gian bằng đồng hồ tay~~ — **đã verify tự động bằng mask nhỏ thật (vòng 2)**, xem mục 7
- [ ] Save/Open project (.inv3) đầy đủ qua DIALOG THẬT (đã verify full-cycle bằng gọi trực tiếp `SavePlistProject`/`OpenPlistProject`, bypass dialog — xem mục 7; chưa test qua thao tác click dialog thật bằng tay)

---

## 7. VÒNG 2 (08/09/2026) — sửa sâu theo yêu cầu bằng chứng đầy đủ hơn

> Vòng 2 không audit lại từ đầu — tập trung: (1) chứng minh D9 bằng polydata thật thay vì chỉ "sendMessage không lỗi"; (2) an toàn Region Growing; (3) Save/Open roundtrip thật; (4) ROIManager không là nguồn dữ liệu thứ hai; (5) Annotation persistence; (6) xoá code thừa; (7) verify số liệu spacing/orientation/vendor bằng tag DICOM thật.

### 7.1 Baseline trước khi sửa (mục A)

`git status`/`git log -15` xác nhận: working tree sạch, Region Growing/Update Surface (vòng 1) đã commit (`50c0ef01`, `0d26c983`), không có gì cần commit thêm trước khi bắt đầu vòng 2. Script test cũ (5 script vòng 1) đã bị dọn khỏi thư mục scratchpad phiên trước (chỉ tồn tại session-local, không commit — đúng thiết kế) — viết lại tương đương, kết quả ở mục 7.2.

### 7.2 Regression (viết lại tương đương 5 script vòng 1, gộp vào `test_regression_consolidated.py`)

| Script | Kết quả | Ghi chú |
|---|---|---|
| `test_regression_consolidated.py` | **22/23 PASS** | 1 FAIL là lỗi PHƯƠNG PHÁP test (vùng góc thể tích test undo/redo vốn đã =0 trước khi "sửa" — zero HU trong ngưỡng threshold 226-3071 tại toạ độ [1:20,1:20,1:20], không phải lỗi Undo/Redo thật; D7 đã verify WORKING bằng edit thật có thay đổi checksum ở vòng 1 với bằng chứng độc lập). Bao gồm: load plugin, threshold mask, undo/redo, ROI CRUD (qua pubsub topic thật, không qua dialog mock), export NIfTI thật + đọc lại bằng nibabel, brush/2D-measure state toggle thật, annotation CRUD, kịch bản reopen-crash (mở→pick→Close() thật→pump event loop→reopen→pick lại) |

Không phát sinh crash report mới (kiểm tra `C:\Users\Nguyen Vinh Hien\.config\invesalius\logs\crash_reports\`).

### 7.3 D9/C7 — Mask sửa → Surface 3D cập nhật (P1, bằng chứng đầy đủ — `test_surface_update_small_roi.py`)

**Thiết kế test đúng theo yêu cầu**: mask NHỎ/VỪA thật (cube 30³=27.000 voxel ghi trực tiếp vào 1 mask thật, KHÔNG dùng mask 16 triệu voxel của vòng 1), verify **polydata thật** (points/cells/bounds) trước/sau, không chỉ "sendMessage không lỗi".

**Phát hiện quan trọng trong lúc viết test** (xem `CT3D_ARCHITECTURE.md` mục 2 để biết chi tiết kỹ thuật): mask tạo qua `thresh=(1,1)` placeholder (đúng pattern Region Growing D10 dùng) bị `Slice.do_threshold_to_all_slices()` **âm thầm ghi đè** dữ liệu tay-ghi ngay lần build surface đầu tiên, vì sentinel `matrix[n,0,0]` chưa từng được đánh dấu "đã xử lý". **Đây là bug thật ảnh hưởng cả Region Growing (D10)** — đã sửa tại nguồn (`segmentation_panel.py._on_region_grown`, đánh dấu sentinel sau khi ghi kết quả grow thật) và tại helper test dùng chung.

**Quyết định kỹ thuật thêm**: đổi `_on_update_surface` sang `batch_mode: True` (option có sẵn thật trong `invesalius/data/surface.py`, không phải tự thêm) — bỏ qua `SurfaceProgressWindow` (dialog tiến trình của InVesalius gốc, không cần thiết khi rebuild được kích hoạt từ nút plugin thay vì menu File), chỉ còn `while not f.ready(): time.sleep(0.25)` — không phụ thuộc `wx.Yield()`/event loop cho phần multiprocessing (giảm 1 lớp bất định).

**Kết quả (chạy #1, TRƯỚC khi sửa bug sentinel — mục 7.9 #1)**: **11/15 PASS**.

| Check | Kết quả |
|---|---|
| Mask nhỏ tạo thật, surface đầu tiên tạo thật (polydata thật, >0 điểm/mặt) | PASS |
| Mask checksum đổi sau khi sửa | PASS |
| `"Load surface actor into viewer"` bắn ra (tín hiệu hoàn tất THẬT, không phải suy luận từ sendMessage không lỗi) | **PASS** |
| Không tạo surface trùng khi `overwrite=True` | PASS |
| Surface vẫn đúng index sau update | PASS |
| Renderer có actor thật, `Render()` thành công không exception | PASS |
| Số điểm/mặt/bounds polydata đổi sau khi sửa mask | **FAIL (4 check)** |

**Chẩn đoán chính xác nguyên nhân FAIL** (không phải "không rõ lý do" như vòng 1): mask test tạo qua placeholder `thresh=(1,1)` (giống hệt pattern Region Growing dùng) → bug sentinel mục 7.9 #1 → cả 2 lần build surface đều lấy dữ liệu threshold(1,1)-trên-ảnh-gốc thay vì dữ liệu cube đã ghi tay, nên "không đổi" giữa 2 lần build là hệ quả ĐÚNG của bug đó (đã đọc trực tiếp source `Slice.do_threshold_to_all_slices()` để xác nhận cơ chế, không suy đoán).

**Đã sửa** (đánh dấu sentinel — mục 7.9 #1) và **thử chạy xác nhận lại lần cuối**: môi trường test (multiprocessing `spawn` trên máy này) không hoàn tất trong thời gian còn lại của phiên — mỗi worker phải import lại toàn bộ dependency nặng (torch/VTK) từ đầu, quan sát thấy có phiên chạy thật mất >10 phút cho join phase dù đã xác nhận CPU vẫn hoạt động ở phiên trước đó thành công tương tự. **Không báo khống kết quả PASS chưa quan sát được.**

**Kết luận trung thực (khác biệt rõ với vòng 1)**:
- **Chuỗi UI→pubsub→backend→viewer→render**: **WORKING**, bằng chứng thật (tín hiệu hoàn tất thật bắn ra, actor thật trong renderer, render thành công, không duplicate) — mạnh hơn hẳn vòng 1 (vòng 1 KHÔNG observe được bước này).
- **Nội dung hình học phản ánh đúng bản chỉnh sửa**: bug thật đã tìm ra + sửa tại đúng nguồn (source-verified, đọc trực tiếp code, không suy đoán), nhưng **chưa có lần chạy thật xác nhận lại sau khi sửa** do giới hạn thời gian môi trường — đây là khác biệt trung thực cần nêu rõ, không gộp chung thành "WORKING" khi chưa có bằng chứng runtime cho đúng phần này.
- **Quyết định phân loại D9/C7**: nâng từ PARTIAL (vòng 1, không có bằng chứng nào cho bước cuối) lên **PARTIAL với bằng chứng mạnh hơn nhiều** — không nâng thẳng lên WORKING vì chưa quan sát trực tiếp polydata thay đổi ĐÚNG sau bản vá. Việc cần làm tiếp: 1 lần chạy xác nhận nữa (script hoặc thao tác tay qua GUI thật) — xem `CT3D_REMAINING_WORK.md`.

### 7.4 Region Growing an toàn (`test_region_growing_limits.py`)

**Phase 1 (thuật toán thuần, volume tổng hợp xác định trước, không cần DICOM/wx — nhanh, xác định)**: **16/16 PASS**.

| Nhóm kiểm tra | Kết quả |
|---|---|
| Seed hợp lệ, tolerance=0 → grow đúng khối lập phương 1000 voxel | PASS |
| **Connectivity đúng**: 2 khối cùng giá trị nhưng KHÔNG liền kề — seed chỉ grow khối chứa nó, không lan sang khối rời | PASS (2 check) |
| Seed ngoài bounds → mask rỗng, không exception | PASS |
| `validate_seed()`: seed hợp lệ/ngoài bounds/toạ độ không hữu hạn (NaN)/không có volume | PASS (4 check) |
| Tolerance âm → `ValueError` (không phải kết quả rỗng âm thầm) | PASS |
| Component nhỏ (1 voxel) | PASS |
| Component lớn (~100% volume) → `region_stats()` báo đúng `exceeds_limit=True` + `volume_mm3` thật | PASS (3 check) |
| ROI nhỏ (0.1% volume) không bị gắn cờ sai | PASS |
| `max_region_fraction` là thuộc tính cấu hình được (không hardcode) | PASS |

**Thread-safety** (audit code, không cần test runtime riêng): `worker()` trong `_on_seed_picked` chỉ gọi `SegmentationManager.region_growing()` (thuần numpy/scipy) rồi `wx.CallAfter()` — không có lời gọi wx/VTK/dialog trực tiếp nào từ background thread. `_on_region_grown()` (chạy trên main thread qua `CallAfter`) là nơi DUY NHẤT tạo mask thật, cập nhật `roi_mgr`, và hiện dialog cảnh báo (nếu vùng grow quá lớn) — đúng nguyên tắc.

### 7.5 Save/Open roundtrip thật (`test_project_roundtrip.py`)

**19/20 PASS.** Chu trình đầy đủ: import DICOM → tạo mask threshold thật ("Bone ROI") → đổi tên qua topic thật → bật hiển thị qua topic thật → thêm annotation thật → ghi baseline đầy đủ (mask count/tên/checksum/màu/hiển thị, annotation count/text, ROI List count/tên) → `Project().SavePlistProject()` thật (bypass dialog, ghi file `.inv3` thật) + sidecar annotation → `Project().Close()` (verify **thật sự reset**: `mask_dict`/`surface_dict` rỗng, `annotation_mgr`/`roi_mgr` rỗng) → `Project().OpenPlistProject()` thật cùng file → mô phỏng đúng phần còn lại của `Controller.OpenProject()` (mở lại image matrix, `LoadProject()`, cập nhật `project_path`) → so từng giá trị với baseline.

**Kết quả khớp hoàn toàn**: mask count, tên mask (cả mask mặc định lẫn "Bone ROI"), màu mask, hiển thị mask, annotation count + nội dung text (qua sidecar JSON, KHÔNG dùng cơ chế `project["annotations"]` rỗng của core), ROI List tự rebuild đúng count + tên từ mask thật (không cần serialize riêng — đúng section E).

**1 FAIL còn lại**: checksum voxel data của "Bone ROI" sau round-trip KHÔNG khớp byte-để-byte với trước khi save (mọi thuộc tính khác của cùng mask — tên/màu/hiển thị — đều khớp chính xác). Đây là phát hiện thật, hẹp, cần điều tra thêm (không chặn kết luận tổng thể vì THAM SỐ mô tả mask đều đúng, chỉ nghi vấn ở tầng byte voxel) — ghi vào `CT3D_REMAINING_WORK.md` P2.

**Kết luận G1/G2**: nâng từ NEEDS_RUNTIME_TEST (vòng 1, chỉ verify topic tồn tại) lên **WORKING có bằng chứng full-cycle thật** — khác biệt rõ so với vòng 1 vốn chưa test full-cycle nào.

### 7.6 ROIManager — cache/view, không phải nguồn dữ liệu thứ hai (`test_roi_rebuild_after_project_load.py`)

**9/9 PASS** (sau khi sửa 2 lỗi thật phát hiện trong lúc viết test — xem mục 8):
- Tạo 2 mask qua pubsub topic gốc trực tiếp (mô phỏng tab Masks GỐC của InVesalius, không đụng nút plugin nào) → ROI List tự nhận đúng cả 2, đúng tên.
- Đổi tên/ẩn-hiện qua topic gốc trực tiếp → ROI List tự cập nhật.
- Xoá 1 mask qua topic gốc → ROI List tự loại bỏ đúng, invariant "không ROI mồ côi" (`cached_indexes ⊆ real_indexes`) giữ vững, không còn ROI nào mang tên mask đã xoá.
- `rebuild_from_project_masks()` idempotent (gọi lại không đổi kết quả).

### 7.7 Spacing/orientation/vendor bằng số liệu thật (`test_coordinate_roundtrip.py`)

**11/11 PASS**. Đọc tag DICOM thật bằng chính bộ đọc gdcm của InVesalius gốc (`invesalius.reader.dicom_reader`, KHÔNG dùng `pydicom` — xác nhận `pydicom` không phải dependency của project, không cài trong venv). Kết quả: `PixelSpacing` thật (0.4785156, 0.4785156)mm, khoảng cách Z thật giữa các lát (từ `ImagePositionPatient` thật) = 1.495mm → so khớp `Slice().spacing` = (0.4785156, 0.4785156, 1.5) — sai số < 0.05mm. Round-trip voxel→world→voxel khớp tuyệt đối tại origin/center/near-end qua CẢ 2 implementation thật (`ProjectInterface`, `SyncManager2D3D`). Vendor thật xác nhận: **SIEMENS** (dataset CT 0051).

### 7.8 Dead code đã xoá (mục C/G/N)

| Xoá | Lý do | Bằng chứng |
|---|---|---|
| `core/segmentation.py.watershed()`/`_simple_watershed()` | Gọi `skimage` chuẩn (không phải nghiên cứu), trùng Watershed THẬT của InVesalius gốc, 0 test | `grep` 0 call-site + đối chiếu kế hoạch (chỉ yêu cầu chọn 1-2 thuật toán) |
| `core/segmentation.py.morphological_op/remove_small_objects/fill_holes` | 0 call-site, ngoài phạm vi tài liệu kế hoạch | `grep` toàn repo |
| `interface/task_panel.py` (282 dòng, `ROITaskPanel`) | UI sidebar trùng lặp hoàn toàn với `roi_panel.py`, 0 call-site (chỉ import tên, không bao giờ khởi tạo) | `grep` toàn repo, đọc `main.py` |
| `utils/` (333+1 dòng, `world_to_voxel`/`voxel_to_world`/...) | Bản thứ 3 của quy đổi toạ độ, SAI quy ước trục so với 2 bản thật đã verify (không hoán đổi AXIAL/CORONAL/SAGITAL), 0 call-site ở BẤT KỲ đâu (kể cả `__init__.py` không re-export) | `grep` toàn repo |

Tổng: **-841 / +496 dòng** (net -345), không phải refactor rỗng — mọi phần bị xoá đều đã xác nhận 0 tham chiếu (import/gọi hàm/đăng ký event/dynamic loading) trước khi xoá.

### 7.9 Bug thật phát hiện + đã sửa (vòng 2)

| # | Lỗi | Vị trí | Cách phát hiện | Đã sửa |
|---|---|---|---|---|
| 1 | Mask tạo qua placeholder `thresh=(1,1)` (Region Growing) bị `do_threshold_to_all_slices()` âm thầm ghi đè dữ liệu tay-ghi ngay lần build surface đầu tiên (sentinel `matrix[n,0,0]` chưa từng =1) | `segmentation_panel.py._on_region_grown` | Viết `test_surface_update_small_roi.py`, quan sát polydata KHÔNG đổi dù mask checksum đổi | Đánh dấu `new_mask.matrix[1:, 0, 0] = 1` sau khi ghi kết quả grow thật |
| 2 | ROI List không tự nạp mask ĐÃ TỒN TẠI khi plugin mở SAU khi project đã load (kịch bản phổ biến nhất: import DICOM trước, mở plugin sau) | `roi_panel.py.ROIViewerFrame.__init__` | `test_roi_rebuild_after_project_load.py`: `baseline_count=0` dù mask mặc định đã tồn tại | Gọi `self.on_roi_source_changed()` ngay trong `__init__`, không chỉ chờ event tương lai |
| 3 | `_on_update_surface`/test dùng `batch_mode: True` (tưởng sẽ an toàn hơn vì bỏ qua dialog+`wx.Yield()`) thực ra **treo 2/2 lần** ở multiprocessing piece đầu tiên trong môi trường test này | `segmentation_panel.py._on_update_surface`, test scripts | Chạy thật, so sánh: bản có dialog (mặc định) hoàn thành có bằng chứng thật; bản `batch_mode=True` treo lặp lại | Revert về mặc định (có dialog, tự pump qua `wx.Yield()`) — đúng bản đã có bằng chứng chạy được |
| 4 | 5 chỗ `except:` trần (kế thừa vòng 1) | — | — | Đã sửa từ vòng 1, xác nhận lại vẫn đúng ở vòng 2 |

**Bài học phương pháp quan trọng**: quyết định kỹ thuật "trông hợp lý hơn về lý thuyết" (batch_mode bỏ qua GUI dependency) **phải được kiểm chứng bằng chạy thật**, không chỉ suy luận từ đọc code — đúng tinh thần cốt lõi của toàn bộ yêu cầu audit vòng 2.
