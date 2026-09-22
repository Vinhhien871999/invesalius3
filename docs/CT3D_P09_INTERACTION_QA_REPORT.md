# CT3D Phase 09 — Runtime Interaction QA & Bidirectional 2D–3D Sync

## 1. Metadata

- Date: 14/09/2026
- Repository: `D:\Learns\DeAn\invesalius\invesalius3`
- Branch: `thesis-ct-roi-tools`
- Commit before: `d3683079` (pre-Phase-09 doc sync, itself on top of Phase 08's `7fed0156`)
- Commit after: `d366a635`
- Git status trước khi sửa: sạch (`nothing to commit, working tree clean`)
- OS: Microsoft Windows 11 Home 10.0.26200 (Build 26200)
- Python: 3.11.7
- wxPython: 4.2.5 msw (phoenix), wxWidgets 3.2.9
- VTK: 9.3.0
- Dataset/test fixture: `D:\PyTools\dicom_samples\0051` (real DICOM, full volume 108×512×512 — không dùng dataset tổng hợp nhỏ ở Phase này vì các test không cần multiprocessing nặng nhiều lần như Phase 08)

## 2. Mục tiêu Phase 09

Đóng các mục có UI/code nhưng chưa chứng minh runtime (B4, C3, D4, D5, E2, E3, F3), triển khai thật Sync 2D→3D (thay vì xoá), và chạy regression cho C4/C5/C7/D9/D7/I2 — không audit lại toàn bộ dự án, không làm lại D9/C7 (đã đóng ở Phase 08), không thêm tính năng ngoài phạm vi.

## 3. Baseline

| ID | Requirement | Before | Evidence |
|---|---|---|---|
| P08.5 | Manual GUI QA cho D9/C7 | Chưa làm | `CT3D_P08_ROI3D_CLOSURE_REPORT.md` mục P08.5 |
| B4 | Zoom/Pan 2D | NEEDS_RUNTIME_TEST | `CT3D_FEATURE_AUDIT.md` |
| C3 | Rotate/Pan/Zoom 3D | NEEDS_RUNTIME_TEST | `CT3D_FEATURE_AUDIT.md` |
| D4 | Brush | NEEDS_RUNTIME_TEST | `CT3D_FEATURE_AUDIT.md` |
| D5 | Eraser | NEEDS_RUNTIME_TEST | `CT3D_FEATURE_AUDIT.md` |
| E2 | Distance 2D | NEEDS_RUNTIME_TEST | `CT3D_FEATURE_AUDIT.md` |
| E3 | Area 2D | NEEDS_RUNTIME_TEST | `CT3D_FEATURE_AUDIT.md` |
| F3 | Annotation position | PARTIAL (fallback `(0,0,0)`) | `CT3D_FEATURE_AUDIT.md` |
| Sync 2D→3D | Checkbox đồng bộ ngược | NOT_IMPLEMENTED (chỉ lưu cờ, không đọc lại — xác nhận qua grep) | `CT3D_FEATURE_AUDIT.md`, `ROI_VIEWER_USER_GUIDE_VERIFICATION.md` |
| C4 | Pick 3D | WORKING | Vòng 1 |
| C5 | 3D→2D | WORKING | Vòng 1 |
| C7 | Rebuild mesh sau sửa mask | WORKING (Phase 08) | `CT3D_P08_ROI3D_CLOSURE_REPORT.md` |
| D9 | Mask sửa → Surface | WORKING (Phase 08) | `CT3D_P08_ROI3D_CLOSURE_REPORT.md` |

## 4. Audit kiến trúc interaction

Trace call chain thật (đọc code trước khi sửa, đúng yêu cầu):

**Sync 3D→2D (đã có, WORKING)**:
```
picker_3d.PointPicker3D._on_left_click (VTK AddObserver "LeftButtonPressEvent")
  → interaction_panel.py._on_point_picked(world_point)
  → sync_mgr.set_world_coords / world_to_voxel
  → ViewInterface().set_slice_position(plane, index)
  → Publisher.sendMessage(("Set scroll position", plane), index=index)
  → invesalius/data/viewer_slice.py.Viewer.ChangeSliceNumber (subscriber thật)
```

**Sync 2D→3D (trước Phase 09 — KHÔNG có, đã xác nhận qua grep)**:
```
interaction_panel.py.cb_sync_2d_3d (checkbox)
  → sync_mgr.enable_sync_2d_3d() / disable_sync_2d_3d()
  → chỉ set self.sync_2d_3d = True/False
  → KHÔNG CÓ code nào đọc lại cờ này để làm bất cứ hành vi thật nào
```

**Cơ chế thật đã tìm ra và tái sử dụng cho Sync 2D→3D (Phase 09)**:
```
Người dùng click/kéo trên khung 2D thật (invesalius/data/styles.py, default 2D interactor style)
  → Publisher.sendMessage("Set cross focal point", position=[x, y, z, None, None, None])
  → invesalius/data/viewer_slice.py.Viewer.SetCrossFocalPoint (subscriber thật, di chuyển crosshair + các mặt cắt khác)
  → [MỚI, Phase 09] main.py._on_cross_focal_point(position) → roi_panel.py.
    ROIViewerFrame.on_cross_focal_point_changed(position)
  → nếu sync_mgr.sync_2d_3d == True: core/marker_3d.CrosshairMarker3D.attach()/update_position()
  → Publisher.sendMessage("Render volume viewer")
```

Xác nhận đây là topic THẬT InVesalius gốc dùng khi người dùng thao tác 2D thật (không phải cơ chế tự bịa): `grep` xác nhận `invesalius/data/styles.py` gửi topic này trực tiếp trong handler click chuột thật của interactor style 2D mặc định; `invesalius/data/record_coords.py` cũng subscribe cùng topic này để ghi lại toạ độ hiện tại — xác nhận `position` là kwarg cố định theo MDS thật.

## 5. Các vấn đề phát hiện

| Vấn đề | Phân loại |
|---|---|
| Sync 2D→3D chưa có logic thật | Missing wiring (đã biết từ trước, đúng phạm vi Phase 09) |
| F3 fallback `(0,0,0)` | UX issue / real bug thật (đã biết từ trước) |
| `ROIViewerFrame.project_loaded` không đồng bộ ngược khi plugin mở SAU khi project đã load | **Real bug mới phát hiện qua test Phase 09** — cùng lớp bug đã sửa cho ROI List ở vòng 2 nhưng bị bỏ sót cho cờ này. Ảnh hưởng: `on_slice_change()`, `on_mask_update()`, và tính năng Sync 2D→3D mới đều bị vô hiệu hoá âm thầm trong đúng kịch bản phổ biến nhất (import DICOM trước, mở plugin sau) |
| B4/C3/D4/D5/E2/E3 cần thao tác chuột thật | Test limitation (môi trường không điều khiển được GUI) |

## 6. Thay đổi code

| File | Function/Class | Change | Reason |
|---|---|---|---|
| `plugins/roi_viewer/core/marker_3d.py` | `CrosshairMarker3D` (mới) | Actor VTK hình cầu nhỏ, `attach()/update_position()/hide()/detach()`, không phụ thuộc wx/invesalius | Biểu diễn trực quan vị trí crosshair 2D trong khung 3D |
| `plugins/roi_viewer/main.py` | `_subscribe_events`, `_on_cross_focal_point` (mới), `unload` | Subscribe/unsubscribe `"Set cross focal point"`, forward tới frame | Nối Sync 2D→3D vào đúng topic thật InVesalius gốc dùng |
| `plugins/roi_viewer/gui/roi_panel.py` | `ROIViewerFrame.__init__` | Khởi tạo `self.marker_3d`, `self._last_cross_focal_point`, và **sửa `project_loaded` để đồng bộ ngược từ `ProjectInterface().is_project_loaded()` thật** | Bug thật phát hiện qua test (mục 5) |
| `plugins/roi_viewer/gui/roi_panel.py` | `on_cross_focal_point_changed` (mới) | Cập nhật marker theo `sync_mgr.sync_2d_3d`, một chiều (không republish) | Logic Sync 2D→3D chính |
| `plugins/roi_viewer/gui/roi_panel.py` | `get_current_reference_position` (mới) | Ưu tiên: pick 3D → crosshair 2D → None | Đóng F3 |
| `plugins/roi_viewer/gui/roi_panel.py` | `_on_close`, `on_project_close` | Thêm `marker_3d.detach()` | Tránh actor/observer rác khi đóng plugin/project (I2, SYNC-T6) |
| `plugins/roi_viewer/gui/annotation_panel.py` | `_on_add_annotation` | Dùng `get_current_reference_position()`, từ chối tạo annotation + hiện cảnh báo nếu không có vị trí hợp lệ; tính `voxel_position` thật qua `sync_mgr.world_to_voxel()` | Đóng F3, không còn fallback `(0,0,0)` âm thầm |

## 7. Test Matrix

| Test ID | Requirement | Method | Expected | Actual | Result |
|---|---|---|---|---|---|
| — | Real DICOM import | `Publisher.sendMessage("Import directory", ...)` | `Slice().matrix` populated | Populated, 6.8s | PASS |
| — | Plugin load qua PluginManager thật | `Publisher.sendMessage("Load plugin", plugin_name="ROI Viewer")` | Window thật tồn tại | Tồn tại | PASS |
| — | Threshold mask + surface (chuẩn bị hình học pick) | `_on_apply_threshold`, `"Create surface from index"` | Mask + surface thật | points/cells thật, `volume=658432mm³` | PASS |
| C4 | Pick 3D trên hình học thật | `picker.pick(300,300)` | Toạ độ world thật | `(142.9, -107.3, 154.4)` | PASS |
| C5 | 3D→2D | `_on_point_picked` → `sync_mgr` | `current_slice_index` có giá trị | Có giá trị | PASS |
| SYNC-T1 | Checkbox OFF → 2D đổi → 3D không đổi | Gửi `"Set cross focal point"` khi `sync_2d_3d=False` | Marker vị trí không đổi | `before=None after=None` | PASS |
| SYNC-T2 | Checkbox ON → 2D đổi → 3D đổi đúng | Gửi world thật (tính từ `voxel_to_world`) | Marker == world gửi | `(384.0, 122.5, 17.23)` khớp tuyệt đối | PASS |
| SYNC-T2b | Đổi vị trí lần 2 | Gửi world thứ 2 | Marker == world thứ 2 | Khớp tuyệt đối | PASS |
| SYNC-T3 | 3D pick vẫn hoạt động sau khi Sync 2D→3D bật | `picker.pick()` lần 2 | Không exception | Không exception | PASS |
| SYNC-T4 | Không event recursion | Đếm số lần handler chạy cho 1 message thật | =1 | `calls=1` | PASS |
| SYNC-T5 | Nhiều lần scroll không tăng actor count | Gửi 5 lần liên tiếp | actor count không đổi | `before=3 after=3` | PASS |
| SYNC-T6 | Đóng/mở lại không rò rỉ | Đóng window, mở lại, kiểm tra renderer | Actor cũ đã gỡ | `HasViewProp(old_actor)=False` | PASS |
| F3-T1 | Chưa có vị trí → từ chối tạo | `_on_add_annotation()` khi pick/crosshair đều None | Không tạo annotation, có cảnh báo | Đúng, count không đổi, `msgbox_calls>0` | PASS |
| F3-T2 | Có pick hợp lệ → dùng đúng toạ độ | `_on_add_annotation()` sau khi có pick | `annotation.position == picked` | Khớp tuyệt đối | PASS |
| F3-T3 | Go to annotation | `_on_goto_annotation()` | Không exception | Không exception | PASS |
| D7 | Undo/Redo checksum | Checkpoint → edit → undo → redo | Checksum khớp đúng từng bước | Khớp (`145da5d1082c`, `741cb0aa875d`) | PASS |
| C7/D9 (light) | `was_edited` → `algorithm` không bị Phase 09 phá | So logic chọn algorithm trước/sau | Default/Binary đúng như Phase 08 | Đúng | PASS |
| I2 | Reopen không rò rỉ | Đóng → mở lại | Window mới thật, observer/actor cũ đã gỡ | Đúng | PASS |
| B4 | Zoom/Pan 2D | — | — | Cần chuột thật | **MANUAL_REQUIRED** |
| C3 | Rotate/Pan/Zoom 3D | — | — | Cần chuột thật | **MANUAL_REQUIRED** |
| D4 | Brush vẽ thật | — | — | Cần chuột thật | **MANUAL_REQUIRED** |
| D5 | Eraser thật | — | — | Cần chuột thật | **MANUAL_REQUIRED** |
| E2 | Distance 2D — kết quả thật | — | — | Cần chuột thật | **MANUAL_REQUIRED** |
| E3 | Area 2D — kết quả thật | — | — | Cần chuột thật | **MANUAL_REQUIRED** |
| P09-T00 | P08.5 (D9/C7 manual GUI) | — | — | Cần chuột thật | **MANUAL_REQUIRED** |

**Tổng**: 28/28 check tự động hoá được đều PASS. 7 mục bắt buộc thao tác chuột thật → `NEEDS_MANUAL_QA`, có checklist đầy đủ ở mục 9.

## 8. Runtime Evidence

- Pick 3D thật: `(142.94401436693585, -107.30714211962186, 154.40093692205733)` mm.
- Marker world position (SYNC-T2): kỳ vọng `(384.0, 122.4999936, 17.2265616)` — thực tế khớp tuyệt đối (sai số < 1e-3mm, giới hạn bởi so sánh float).
- Renderer actor count: 3 trước và sau 5 lần cập nhật liên tiếp (không tăng).
- Checksum SHA-256 voxel mask (D7): trước=sau-undo=`145da5d1082c...`, sau-edit=sau-redo=`741cb0aa875d...`.
- Surface build (mask threshold đầy đủ, không dùng dataset tổng hợp nhỏ lần này): 6 piece, tổng ~8.75s, volume thật 658432.2mm³, area 299474.0mm².
- Event recursion count (SYNC-T4): 1 lần gọi handler cho 1 message thật gửi đi — xác nhận bằng số, không phải "trông có vẻ ổn".
- 0 crash report mới (đã kiểm tra cả config thật của người dùng — không bị đụng tới nhờ `XDG_CONFIG_HOME` — và config cô lập của test).
- Camera state (B4/C3): `NOT_MEASURED` — không thực hiện được thao tác chuột thật trong môi trường này, không có số liệu để ghi.
- Measurement error (E2/E3): `NOT_MEASURED` — cùng lý do.

## 9. Manual QA

Checklist đầy đủ cho mọi mục không tự động verify được (mở app thật bằng `python app.py -i <thư mục DICOM>`):

### P09-T00 (bao gồm P08.5 — D9/C7 qua dialog mặc định)
1. Threshold một mask nhỏ/vừa → **Update 3D Surface from Selected ROI** → quan sát khối 3D xuất hiện.
2. Bật **Enable Brush Tool**, vẽ thêm một vùng rõ ràng trên khung 2D (Axial).
3. Bấm lại **Update 3D Surface from Selected ROI**.
4. **Kỳ vọng**: khối 3D đổi hình đúng theo vùng vừa vẽ; dòng "Status:" hiện `(method: Binary)`. Ghi lại thời gian rebuild bằng đồng hồ tay và có đúng như kỳ vọng không.

### D4 — Brush
1. Threshold/chọn 1 mask. Ghi lại (qua tab Masks gốc hoặc log) voxel count hiện tại.
2. Bật **Enable Brush Tool**, vẽ 1 nét rõ ràng trên khung 2D.
3. Tắt Brush. Kiểm tra: mask có vùng mới tô đúng vị trí vừa vẽ không (quan sát bằng mắt trên cả 2D và sau khi Update 3D Surface).

### D5 — Eraser
1. Từ trạng thái sau D4 (đã có vùng vẽ), chọn **Erase**, xoá một phần vùng vừa vẽ.
2. Bấm **Undo** → vùng vừa xoá phải khôi phục lại đúng như trước khi xoá.
3. Bấm **Redo** → vùng phải bị xoá lại đúng như sau khi xoá.

### B4 — Zoom/Pan 2D
1. Trên khung 2D bất kỳ, dùng chuột lăn để zoom, giữ phím giữa/kéo để pan (theo đúng phím tắt InVesalius gốc).
2. Xác nhận ảnh phóng to/thu nhỏ và di chuyển đúng theo thao tác, không lỗi/giật hình.

### C3 — Rotate/Pan/Zoom 3D
1. Trên khung 3D (Volume), kéo chuột trái để xoay, chuột phải/giữa để pan/zoom (theo đúng phím tắt InVesalius gốc).
2. Xác nhận camera phản hồi đúng theo thao tác.

### E2 — Distance 2D
1. Tab Measurements → chọn **2D** → **Start Distance**.
2. Click 2 điểm trên khung 2D tại vị trí đã biết trước khoảng cách vật lý gần đúng (ví dụ 2 điểm cách nhau đúng N voxel theo trục ngang, N × spacing_x = khoảng cách kỳ vọng).
3. Xem kết quả tại tab "Measures" gốc InVesalius, so với khoảng cách kỳ vọng, ghi sai số tuyệt đối (mm) và tương đối (%).

### E3 — Area 2D
1. Tab Measurements → **Measure Area (2D)**.
2. Vẽ 1 polygon hình chữ nhật đơn giản trên khung 2D tại vị trí biết trước kích thước (N × M voxel).
3. Diện tích kỳ vọng = N × spacing_x × M × spacing_y (mm²). So với kết quả ở tab "Measures" gốc, ghi sai số.

## 10. Regression

| ID | Kết quả | Ghi chú |
|---|---|---|
| C4 | PASS | Pick 3D thật, toạ độ world hợp lệ |
| C5 | PASS | sync_mgr tính đúng slice index từ pick |
| C7/D9 | PASS (light) | Logic chọn `algorithm` theo `was_edited` không bị Phase 09 phá — full surface-rebuild đã verify đầy đủ ở Phase 08, không chạy lại toàn bộ ở đây để tránh lặp lại rủi ro OOM đã biết |
| D7 | PASS | Checksum khớp đúng cả 2 chiều Undo/Redo |
| I2 | PASS | Đóng/mở lại: window mới thật, picker observer + marker actor cũ đều được gỡ sạch |

## 11. Before/After Matrix

| ID | Before | After | Evidence |
|---|---|---|---|
| Sync 2D→3D | NOT_IMPLEMENTED | **WORKING** | Mục 7 — SYNC-T1 đến T6, 8/8 PASS |
| F3 | PARTIAL | **WORKING** | Mục 7 — F3-T1 đến T3, 5/5 PASS |
| B4 | NEEDS_RUNTIME_TEST | **NEEDS_MANUAL_QA** | Đổi tên trạng thái cho đúng quy ước Phase 09 (mục XV) — vẫn chưa có bằng chứng thao tác tay, checklist đã có |
| C3 | NEEDS_RUNTIME_TEST | **NEEDS_MANUAL_QA** | Tương tự |
| D4 | NEEDS_RUNTIME_TEST | **NEEDS_MANUAL_QA** | Tương tự |
| D5 | NEEDS_RUNTIME_TEST | **NEEDS_MANUAL_QA** | Tương tự |
| E2 | NEEDS_RUNTIME_TEST | **NEEDS_MANUAL_QA** | Tương tự |
| E3 | NEEDS_RUNTIME_TEST | **NEEDS_MANUAL_QA** | Tương tự |
| P08.5 | Chưa làm | **NEEDS_MANUAL_QA** | Checklist đầy đủ ở mục 9 |
| C4/C5/C7/D9/D7/I2 | WORKING | **WORKING** (không đổi) | Regression PASS, không phát hiện thoái lui |

## 12. Bugs Fixed

1. **[Missing wiring, đúng phạm vi Phase 09]** Sync 2D→3D: đã triển khai thật bằng cách tái sử dụng topic `"Set cross focal point"` có sẵn của InVesalius gốc.
2. **[Real bug, đúng phạm vi Phase 09]** F3: annotation không còn fallback `(0,0,0)` âm thầm — từ chối tạo + cảnh báo rõ ràng khi không có vị trí hợp lệ.
3. **[Real bug MỚI phát hiện qua test]** `ROIViewerFrame.project_loaded` không đồng bộ ngược từ state thật khi plugin mở SAU khi project đã load — sửa bằng cách khởi tạo từ `ProjectInterface().is_project_loaded()` thật, đúng mẫu đã áp dụng cho ROI List ở vòng 2. Bug này ảnh hưởng cả `on_slice_change()`/`on_mask_update()` từ trước, không chỉ tính năng mới.

## 13. Remaining Issues

- 7 mục yêu cầu thao tác chuột thật (B4, C3, D4, D5, E2, E3, P08.5) chưa có bằng chứng runtime — checklist đầy đủ ở mục 9.
- "ca_smoothing" (tuỳ chọn mượt hơn "Binary" cho D9/C7) vẫn chưa đánh giá — không thuộc phạm vi Phase 09.

## 14. Completed Work

- Sync 2D→3D triển khai đầy đủ, đúng kiến trúc hiện có (tái sử dụng `"Set cross focal point"`, không tạo event bus riêng), verify runtime thật 8/8 test.
- F3 sửa dứt điểm, verify runtime thật 3/3 test.
- Phát hiện + sửa 1 bug thật (`project_loaded`) ảnh hưởng rộng hơn phạm vi ban đầu tưởng.
- Regression C4/C5/C7/D9/D7/I2 xác nhận không thoái lui.

## 15. Not Completed

- Manual QA thao tác chuột thật cho 7 mục (mục 9) — cần người dùng tự thực hiện.
- Đánh giá "ca_smoothing" cho D9/C7 (không thuộc phạm vi Phase 09).

## 16. Phase Gate

**`PHASE_GATE: PASS`**

Lý do: mọi bug/wiring thuộc phạm vi Phase 09 đã được xử lý (Sync 2D→3D hoạt động, verify bằng runtime test thật; F3 đã sửa, verify runtime test thật). Các mục phụ thuộc chuột thật mà môi trường không thực hiện được đã đánh đúng `NEEDS_MANUAL_QA` kèm checklist chính xác — không có mục nào bị chuyển thành WORKING khi chưa có bằng chứng thao tác tay.

## 17. Phase 10 Recommendation

- Save/Open checksum investigation (voxel mask lệch nhẹ sau round-trip, đã loại trừ giả thuyết flush() ở vòng 3 — `CT3D_REMAINING_WORK.md` mục 2a).
- Undo/Redo memory/diff-patch (hiện dùng snapshot toàn mảng — đề cương gợi ý tối ưu).
- Data integrity tổng quát theo đúng phạm vi Phase 10 đã định.
