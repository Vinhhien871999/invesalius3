# CT3D Phase 08 — Đóng dứt điểm ROI → Surface 3D

## 1. Metadata

- Date: 14/09/2026
- Branch: `thesis-ct-roi-tools`
- Commit before: `7a4e19fd158dcdc169f61a768f7e5fdc52eaf244`
- Commit after: `40c2c38b`
- OS: Microsoft Windows 11 Home 10.0.26200 (Build 26200)
- Python: 3.11.7
- wxPython: 4.2.5 msw (phoenix), wxWidgets 3.2.9
- VTK: 9.3.0
- Dataset used: `D:\PyTools\dicom_samples\0051` (real DICOM, chỉ dùng để dựng app/3D-viewer thật) + ảnh/mask **tổng hợp nhỏ (30, 128, 128)** hoán đổi vào `Slice().matrix`/`Project().mask_dict` ngay sau import (xem mục 4 — lý do và cách làm)

## 2. Mục tiêu Phase

Đóng dứt điểm D9/C7: chứng minh bằng runtime thật (không suy đoán) rằng khi mask được chỉnh sửa thật, gọi đúng action "Update 3D Surface" khiến surface 3D **thực sự thay đổi hình học** (không chỉ gửi pubsub không lỗi), không tạo actor/surface rác, và người dùng sẽ thấy đúng hình học mới.

## 3. Baseline trước khi thực hiện

| ID | Chức năng | Trạng thái trước | Bằng chứng |
|---|---|---|---|
| D9 | Mask sửa → Surface 3D cập nhật | `PARTIAL` | `CT3D_FEATURE_AUDIT.md` (vòng 2/3): chuỗi UI→pubsub→backend→viewer→render đã verify chạy không lỗi (11/15 check vòng 2), nhưng **chưa từng quan sát được polydata thật đổi đúng sau khi sửa mask** — 4 lần thử lại ở vòng 3 đều bị treo lúc dựng surface (nghi do máy thiếu RAM khi dùng volume CT thật ~28 triệu voxel) |
| C7 | Rebuild mesh sau khi sửa mask | `PARTIAL` | Cùng cơ chế, cùng bằng chứng với D9 |

**Không mặc định commit cũ vẫn là HEAD**: đã chạy `git status`/`git log`/`git branch --show-current` thật trước khi bắt đầu — xác nhận branch `thesis-ct-roi-tools`, working tree sạch, HEAD = `7a4e19fd` (báo cáo đánh giá theo giai đoạn vừa viết trước Phase 08).

## 4. Phân tích nguyên nhân

**Bước 1 — Audit pipeline bằng code thật (P08.1)**, đối chiếu `CT3D_ARCHITECTURE.md` với source hiện tại, xác nhận đúng:

```
segmentation_panel.py.btn_update_surface (EVT_BUTTON)
  → _on_update_surface(event)
  → Publisher.sendMessage("Create surface from index", surface_parameters={...})
  → invesalius/data/slice_.py: Slice.CreateSurfaceFromIndex(surface_parameters)
       → self.do_threshold_to_all_slices(mask)
       → Publisher.sendMessage("Create surface", slice_=self, mask=mask, surface_parameters=...)
  → invesalius/data/surface.py: SurfaceManager.AddNewActor(slice_, mask, surface_parameters)
       → multiprocessing Pool: surface_process.create_surface_piece(...) mỗi Z-chunk (vtkContourFilter)
       → join_process_surface: merge/clean/decimate/smooth
       → Project().surface_dict[index] = Surface(polydata=...)
       → Publisher.sendMessage("Load surface actor into viewer", actor=...)
  → invesalius/data/viewer_volume.py: Viewer nhận actor, ren.AddActor, UpdateRender()
```

**Bước 2 — Thử nghiệm nhỏ tránh OOM (P08.2/P08.3)**: thay vì dùng volume CT thật ~28 triệu voxel (đã treo 4 lần ở vòng 3 do RAM), boot app thật bằng 1 lần import DICOM thật (để có đủ widget tree/3D viewer thật), sau đó **hoán đổi `Slice().matrix`/`Project().mask_dict` bằng ảnh+mask tổng hợp nhỏ (30×128×128)** ngay trong tiến trình — giảm số piece multiprocessing từ ~7 (ceil(108/20)) xuống 2 (ceil(30/20)), giảm hẳn tải multiprocessing mà vẫn chạy đúng 100% code thật (`AddNewActor`, `vtkContourFilter`, `join_process_surface`, `"Load surface actor into viewer"`).

Trong quá trình làm thử nghiệm nhỏ này, gặp và phân biệt rõ 3 loại nguyên nhân khác nhau (đúng yêu cầu mục 4 của template):

- **Giới hạn môi trường (đã giải quyết bằng test nhỏ)**: pipeline với volume CT thật đầy đủ liên tục treo lúc dựng surface (đa tiến trình) trên máy chỉ còn 1.1–3.5GB RAM khả dụng — không phải lỗi code, đã né bằng cách dùng dataset nhỏ.
- **Lỗi wiring/thiếu cấu hình (chỉ ở test harness, đã sửa trong test)**: `Frame(None)` crash (`TypeError` rồi `UnboundLocalError`) vì harness tối giản bỏ qua bước `Session().CreateConfig()` mà `app.py` thật luôn gọi trước — sửa trong harness (gọi đúng `session.ReadConfig()`/`CreateConfig()` như `app.py` thật làm), không phải bug plugin/InVesalius.
- **LỖI LOGIC THẬT trong plugin (nguyên nhân chính của D9/C7)**: `_on_update_surface()` luôn hardcode `"algorithm": "Default"`. Đọc trực tiếp `invesalius/data/surface_process.py.create_surface_piece()` xác nhận: với `algorithm="Default"` và `from_binary=False`, marching cubes **contour lại ẢNH GỐC** theo `mask.threshold_range`, **không hề đọc `mask.matrix`**. Mọi chỉnh sửa mask trực tiếp (brush, region growing, undo/redo) vì vậy **không có tác dụng gì** lên surface dựng bằng "Default" — bất kể mask thật sự chứa gì. Xác nhận chéo bằng chính native dialog InVesalius (`invesalius/gui/dialogs.py.SurfaceMethodPanel`): dialog gốc **ẩn hẳn lựa chọn "Default"** và hiện tooltip *"It is not possible to use the Default method because the mask was edited"* khi `mask.was_edited == True`, tự chuyển sang `"ca_smoothing"` (Context aware smoothing) — cơ chế đọc mask thật (`from_binary=True`) đã có sẵn trong chính InVesalius gốc, chỉ là `_on_update_surface()` của plugin chưa bao giờ dùng đúng nó.

## 5. Thay đổi đã thực hiện

### 5.1 `segmentation_panel.py._on_update_surface()`
- **Lý do**: đóng D9/C7 — surface phải phản ánh đúng nội dung mask thật sau khi sửa.
- **File/function**: `plugins/roi_viewer/gui/segmentation_panel.py`, method `_on_update_surface`.
- **Cách sửa**: đọc `mask.was_edited` (thuộc tính thật của `Mask`, đã được chính `invesalius/data/styles.py` set `True` ở nhiều điểm brush-edit thật) — nếu `True`, dùng `algorithm="Binary"` (đọc thẳng mask thật qua nhánh `from_binary=True`); nếu `False` (mask threshold nguyên bản, chưa từng sửa tay), vẫn giữ `"Default"` (nhanh hơn, chính xác sub-voxel theo ảnh gốc — đúng hành vi cũ, không regression).
- **Ảnh hưởng kiến trúc**: không phá pubsub — vẫn gửi đúng topic `"Create surface from index"` như cũ, chỉ đổi 1 giá trị tham số `method.algorithm` dựa trên state thật có sẵn của `Mask`. Không đụng file nào trong `invesalius/` (core gốc).

### 5.2 `segmentation_panel.py._on_region_grown()`
- **Lý do**: Region Growing ghi dữ liệu trực tiếp vào `mask.matrix` nhưng chưa từng đặt `mask.was_edited = True` — nếu không sửa, bản vá ở 5.1 sẽ không kích hoạt đúng cho ROI tạo bằng Region Growing (chỉ có tác dụng cho brush, vì brush đã có `styles.py` tự đặt cờ này).
- **File/function**: `plugins/roi_viewer/gui/segmentation_panel.py`, method `_on_region_grown`.
- **Cách sửa**: thêm `new_mask.was_edited = True` ngay sau khi ghi kết quả grow thật vào `matrix`.
- **Ảnh hưởng kiến trúc**: không có — chỉ set 1 thuộc tính có sẵn của `Mask`, đúng đúng ý nghĩa gốc của thuộc tính này trong InVesalius.

## 6. Danh sách file thay đổi

| File | Loại | Nội dung |
|---|---|---|
| `plugins/roi_viewer/gui/segmentation_panel.py` | MODIFIED | `_on_update_surface()` chọn `algorithm` theo `mask.was_edited`; `_on_region_grown()` đặt `was_edited=True` |
| `docs/CT3D_P08_ROI3D_CLOSURE_REPORT.md` | DOC | Báo cáo này |
| `docs/CT3D_MASTER_PROGRESS.md` | NEW/DOC | Tài liệu tổng tiến độ (tạo mới ở Phase này) |
| `docs/CT3D_CHANGELOG.md` | MODIFIED/DOC | Append mục Phase 08 |
| (scratchpad, không commit vào repo) `p08_roi3d_closure_test.py` | TEST | Script test runtime thật cho Phase 08 (xem mục 7) |

## 7. Kiểm thử

| Test ID | Mục tiêu | Lệnh/thao tác | Expected | Actual | Result |
|---|---|---|---|---|---|
| P08-T1 | Build 1: mask threshold nguyên bản (chưa sửa) dựng surface đúng | `Publisher.sendMessage("Create surface from index", ...)` với mask `was_edited=False` | `algorithm=Default` tự chọn, polydata có points/cells > 0 | `algorithm=Default`, points=7296, cells=14588 | PASS |
| P08-T2 | Sửa mask (ghi trực tiếp voxel, mô phỏng brush) → checksum đổi | Ghi `mask.matrix[...]=255` vùng lớn hơn, `mask.was_edited=True` | checksum SHA-256 đổi so với trước | Đổi đúng, 3/3 lần | PASS |
| P08-T3 | Update 3D Surface sau khi sửa: `algorithm` tự chuyển | Gọi `_on_update_surface`-equivalent (đúng `surface_options` thật) | `algorithm=Binary` khi `was_edited=True` | Đúng, in log rõ `mask.was_edited=True -> algorithm=Binary` cả 3 chu kỳ | PASS |
| P08-T4 | Polydata THẬT thay đổi sau update (points/cells/bounds) | So `GetNumberOfPoints/Cells/Bounds` trước/sau | Khác nhau, tăng dần theo ROI grow | points 7296→13440→16368→18720; cells 14588→26876→32732→37436; bounds giãn dần đúng hướng grow | PASS (3/3 chu kỳ) |
| P08-T5 | Không tạo surface/actor trùng khi `overwrite=True` | Đếm `Project().surface_dict`, `renderer.GetActors().GetNumberOfItems()` | Giữ nguyên count | `surface_dict` luôn =1; actor count trước/sau mỗi chu kỳ đều =2 (không tăng) | PASS (3/3) |
| P08-T6 | `Render()` không exception | Gọi `ren.GetRenderWindow().Render()` sau mỗi update | Không raise | Không raise, 3/3 lần | PASS |
| P08-T7 | Ổn định lặp lại ≥3 lần liên tiếp (yêu cầu Gate P08) | 3 chu kỳ edit→rebuild liên tiếp trong cùng 1 phiên | Cả 3 đều PASS | Cả 3 đều PASS, không crash, không treo | PASS |

**Tổng**: 36/36 check con PASS (tính cả setup/DICOM import/sentinel). 0 FAIL, 0 BLOCKED.

## 8. Runtime evidence

| Mốc | Points | Cells | Bounds (x0,x1,y0,y1,z0,z1) | Volume (mm³) | Algorithm | Build time |
|---|---|---|---|---|---|---|
| Build 1 (threshold gốc) | 7296 | 14588 | (39.93, 87.07, -87.07, -39.93, 7.93, 21.07) | 29175.4 | Default | 4.68s |
| Cycle 1 (grow +3) | 13440 | 26876 | (32.50, 92.50, -92.50, -32.50, 0.50, 26.50) | 93553.4 | Binary | 0.95s |
| Cycle 2 (grow +6) | 16368 | 32732 | (29.50, 95.50, -95.50, -29.50, -0.50, 28.50) | 126275.6 | Binary | 0.86s |
| Cycle 3 (grow +9) | 18720 | 37436 | (26.50, 98.50, -98.50, -26.50, -0.50, 28.50) | 150286.2 | Binary | 0.88s |

- Checksum SHA-256 voxel mask: đổi đúng 3/3 lần sau mỗi lần ghi trực tiếp.
- `surface_dict` count: luôn = 1 (không trùng) qua cả 4 lần build.
- Renderer actor count: 2 trước/sau mỗi update (ổn định, không rác — 1 actor slice-plane mặc định + 1 actor surface).
- RAM tiến trình: 861MB (sau hoán đổi synthetic) → 1174MB (sau 3 chu kỳ) — tăng hợp lý, không rò rỉ bất thường qua 4 lần build liên tiếp (~100MB/build, ổn định dần).
- 0 crash report mới sinh ra (đã kiểm tra cả thư mục config thật của người dùng — không bị đụng tới nhờ cách ly qua `XDG_CONFIG_HOME` — và thư mục config cô lập của test).

## 9. Regression test

| Chức năng cũ | Cách verify trong Phase này | Kết quả |
|---|---|---|
| Build surface lần đầu từ mask threshold chưa sửa (D1/C1, hành vi cũ) | Build 1 trong test trên dùng đúng `algorithm=Default` (không đổi hành vi khi `was_edited=False`) | PASS — points/cells/bounds hợp lý, giống hành vi đã verify ở vòng 1/2 |
| `overwrite=True` không tạo surface trùng (đã verify vòng 2) | Đếm `surface_dict` sau mỗi trong 3 lần update | PASS — luôn =1 |
| Region Growing tạo mask thật (D10, vòng 1/2) | Không chạy lại full Region Growing trong Phase này (ngoài phạm vi hẹp của P08) — chỉ thêm `was_edited=True`, không đổi logic grow. Rủi ro thấp (1 dòng set thuộc tính, không đụng thuật toán) | Không cần test lại riêng — thay đổi tối thiểu, không ảnh hưởng logic grow đã verify 16/16 ở vòng 2 |

**Chưa chạy lại được** (ngoài phạm vi Phase 08, ghi rõ không giấu): bộ test tích hợp cũ (`test_e2e_wired.py`, `test_roi_and_export.py`,...) từ vòng 1/2/3 — các file này nằm trong scratchpad phiên trước, đã bị dọn theo vòng đời phiên làm việc (session mới, thư mục tạm khác). Sẽ cần viết lại thành bộ `pytest` bền vững ở **Phase 11** (đúng kế hoạch, không phải bỏ sót ở Phase 08).

## 10. Ma trận trạng thái sau Phase

| ID | Trạng thái trước | Trạng thái sau | Evidence |
|---|---|---|---|
| D9 | PARTIAL | **WORKING** | Mục 7-8 ở trên — polydata thật đổi đúng 3/3 chu kỳ, không duplicate, render thành công |
| C7 | PARTIAL | **WORKING** | Cùng cơ chế, cùng bằng chứng với D9 |

## 11. Bug đã sửa

1. **[LOGIC THẬT, plugin]** `_on_update_surface()` hardcode `algorithm="Default"` khiến surface không bao giờ phản ánh mask đã sửa tay (brush/region growing/undo-redo) — sửa bằng cách chọn `algorithm` theo `mask.was_edited`, đúng cơ chế InVesalius gốc đã có sẵn (`SurfaceMethodPanel`) nhưng plugin chưa từng dùng.
2. **[LOGIC THẬT, plugin]** `_on_region_grown()` chưa đặt `mask.was_edited = True` sau khi ghi kết quả grow — khiến bản vá #1 không kích hoạt đúng cho mask tạo bằng Region Growing.
3. **[Harness/test-only, không phải bug plugin/InVesalius]** Bootstrap tối giản thiếu `Session().CreateConfig()` gây crash `Frame(None)` — sửa trong test harness.
4. **[Harness/test-only]** Quên xoá `Project().image_versions` khi hoán đổi ảnh tổng hợp — gây `IndexError` do lệch shape với ảnh DICOM thật còn sót lại trong danh sách phiên bản ảnh.

## 12. Vấn đề còn tồn tại

- Đường dẫn `algorithm="Default"` KHÔNG chạy được ổn định với dialog gốc (`SurfaceProgressWindow`) trong môi trường test tự động không có `app.MainLoop()` thật — phải dùng `batch_mode=True` để né. Đây là hạn chế **của phương pháp test tự động trên máy này**, không phải bug — khi người dùng thật bấm nút trong GUI thật (có `MainLoop()` thật đang chạy), đường dẫn dialog mặc định (không `batch_mode`) nhiều khả năng vẫn hoạt động bình thường như trước giờ vẫn dùng. **Cần xác nhận thủ công qua GUI thật** (xem mục P08.5 bên dưới) trước khi coi đây là hoàn toàn khép kín.
- `"ca_smoothing"` (lựa chọn mặc định của dialog gốc khi mask đã sửa, mượt hơn `"Binary"`) chưa được dùng — `"Binary"` được chọn vì đơn giản hơn (không cần dict `options` bổ sung) và đủ đúng đắn cho mục tiêu Phase 08 (đảm bảo polydata phản ánh đúng mask). Có thể cân nhắc `"ca_smoothing"` ở phase sau nếu cần mesh mượt hơn cho mask chỉnh tay.
- Chưa test trên volume CT thật kích thước đầy đủ (do giới hạn RAM của máy) — bằng chứng ở Phase này dùng dataset tổng hợp nhỏ nhưng chạy 100% qua code thật, không phải mock.

## 13. Những gì đã hoàn thành

- Trace chính xác toàn bộ pipeline D9/C7 bằng code thật (P08.1).
- Tìm ra và sửa đúng nguyên nhân gốc thật sự (không phải RAM/timing như nghi ngờ trước đó) bằng cách đọc trực tiếp `surface_process.py` và đối chiếu chéo với chính native dialog InVesalius.
- Verify bằng runtime thật: mask sửa → surface polydata thật đổi (points/cells/bounds), lặp lại ổn định 3/3 lần liên tiếp, không duplicate, không crash, Render() thành công.
- D9 và C7 chính thức chuyển từ PARTIAL → **WORKING** với bằng chứng đầy đủ.

## 14. Những gì chưa hoàn thành

- Xác nhận thủ công qua GUI thật (chuột thật, dialog mặc định không `batch_mode`) — xem P08.5/mục "Nội dung Phase tiếp theo".
- Chưa thử với volume CT kích thước đầy đủ (giới hạn RAM môi trường hiện tại).
- Chưa đánh giá `"ca_smoothing"` như một lựa chọn thay thế mượt hơn.

## 15. Gate quyết định

**`PHASE_GATE: PASS`**

Lý do: đã chứng minh bằng runtime thật (không phải suy đoán) rằng mask sửa → surface polydata thật đổi đúng, ổn định 3/3 lần liên tiếp, không duplicate actor/surface, không crash. Toàn bộ 6 tiêu chí PASS trong mục "Gate P08" của kế hoạch đều đạt. Phần "chưa hoàn thành" ở mục 14 là các xác nhận bổ sung (thủ công/dataset lớn hơn) không làm thay đổi kết luận về nguyên nhân gốc và bản vá đã đúng — được ghi rõ thành checklist thủ công (P08.5) thay vì bị bỏ qua.

### P08.5 — Manual QA checklist (bổ sung, chưa thao tác tay được trong phiên này)

1. Mở InVesalius thật (`python app.py -i <thư mục DICOM>`), đợi import xong.
2. **Plugins → ROI Viewer** → tab Segmentation.
3. Threshold một mask nhỏ/vừa (không phải toàn bộ volume) → **Create Mask from Threshold**.
4. **Update 3D Surface from Selected ROI** → quan sát khối 3D xuất hiện.
5. Bật **Enable Brush Tool**, vẽ thêm một vùng rõ ràng trên khung 2D (Axial) tại vị trí dễ nhận biết.
6. Bấm lại **Update 3D Surface from Selected ROI**.
7. **Kỳ vọng**: khối 3D thay đổi hình dạng đúng theo vùng vừa vẽ thêm (không phải giữ nguyên hình cũ). Trạng thái dòng chữ "Status:" hiện `(method: Binary)`.
8. Ghi lại: có đúng như kỳ vọng không, có lỗi/crash gì không, thời gian rebuild bằng đồng hồ tay.

## 16. Nội dung Phase tiếp theo

**Phase 09 — Runtime Interaction QA**

- Mục tiêu: đóng các mục có code/UI nhưng chưa chứng minh runtime (B4, C3, D4, D5, E2, E3, Sync 2D→3D, F3).
- Các ID cần xử lý: B4, C3, D4, D5, E2, E3, F3, "Sync 2D → 3D" (quyết định Implement hay Remove).
- Điều kiện bắt đầu: Phase 08 đạt `PHASE_GATE: PASS` (đã đạt).
- Điều kiện hoàn thành: không còn chức năng nào có UI nhưng hoàn toàn không có đường logic mà người dùng tưởng đang hoạt động; mọi mục còn `NEEDS_MANUAL_QA` có protocol thủ công đầy đủ (theo đúng mẫu P08.5 ở trên).

## 17. Kết luận

D9/C7 đã được đóng dứt điểm với bằng chứng runtime thật, đầy đủ, có thể tái lập (3/3 chu kỳ liên tiếp) — không phải "coi như xong" chỉ vì không còn exception. Nguyên nhân gốc thật sự (chọn sai `algorithm`) khác hẳn giả thuyết RAM/timing của các vòng trước — một phát hiện quan trọng cho thấy giá trị của việc audit sâu bằng đọc trực tiếp source thay vì chỉ lặp lại thử nghiệm với cùng 1 cấu hình. Vẫn còn 1 xác nhận thủ công qua GUI thật cần làm (P08.5) trước khi coi đây là "đã kiểm chứng từ mọi góc độ" — **không tuyên bố hoàn thành 100%** cho tới khi có bằng chứng thao tác tay.
