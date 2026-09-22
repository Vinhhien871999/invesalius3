# Changelog — phần code mới/sửa so với InVesalius gốc

> Điểm chia tách với upstream: commit `ca9aef76` (Merge PR #1446, upstream InVesalius). Mọi commit sau đó trên branch `thesis-ct-roi-tools` là công việc của đề tài. Liệt kê theo thứ tự thời gian, mỗi mục ghi rõ **sửa gì / lý do / có phải phần mới của đề tài không**.

---

## `56424653` — Convert plugins/ submodule to regular tracked directory
**Lý do**: `plugins/` là git submodule trỏ tới repo InVesalius gốc; code plugin `roi_viewer` (đề tài) nằm bên trong submodule đó ở dạng **hoàn toàn untracked** — không được Git bảo vệ, rủi ro mất trắng nếu submodule bị reset.
**Loại**: Hạ tầng/bảo vệ dữ liệu, không phải chức năng.

## `54a396cb` — Fix roi_viewer plugin bugs found via real end-to-end testing
**Sửa**: 2 lỗi crash thật (sai pubsub topic `"Set scroll position"` — dùng chuỗi phẳng thay vì tuple `("Set scroll position", plane)`; `_on_project_load` thiếu tham số bắt buộc theo pypubsub MDS), 5 lỗi import VTK sai module, 1 lỗi dùng `vtkPolyLine` thay vì `vtkTriangle` khi xuất surface, 1 lỗi đọc thuộc tính `Project().dicom_sample` không tồn tại, lỗi chính tả `"SAGITTAL"` (2 chữ T) khi thực tế InVesalius dùng `"SAGITAL"` (1 chữ T), lỗi double-dialog + hardcode mask index khi export.
**Loại**: 100% bugfix trên code plugin (đề tài), không đụng InVesalius gốc.

## `ebb81262` — Wire roi_viewer UI to core/ managers and real InVesalius data
**Sửa**: `roi_panel.py` trước đó tự định nghĩa panel rỗng trùng tên thay vì dùng các file panel đã hoàn thiện (`interaction_panel.py`, `measurement_panel.py`, `annotation_panel.py`, `export_panel.py`) — khiến ~1900 dòng logic trong `core/` không bao giờ được gọi. Viết mới `gui/segmentation_panel.py`. Nối toàn bộ 5 tab vào dữ liệu InVesalius thật.
**Loại**: 100% code mới của đề tài (`plugins/roi_viewer/`), không sửa file InVesalius gốc.

## `cf9873b1` — Wire brush painting and 2D measurement to InVesalius's real tools
**Sửa**: nối Brush/Eraser và đo 2D vào đúng interactor style thật của InVesalius (`SLICE_STATE_EDITOR`, `STATE_MEASURE_DISTANCE`, `STATE_MEASURE_DENSITY_POLYGON`) qua `"Enable style"/"Disable style"` — không tự viết lại brush/đo lường, không phá kiến trúc pubsub.
**Loại**: code mới của đề tài.

## `8c5a814c` — Fix real crash in destroy-time cleanup (deleted VTK interactor)
**Sửa**: `_on_destroy` handler gọi vào đối tượng VTK đã bị huỷ trong lúc thoát app (`RuntimeError: wrapped C/C++ object ... has been deleted`) — bọc try/except đúng chuẩn cho code dọn dẹp lúc thoát.
**Loại**: bugfix code plugin.

## `4d3470a2` — Remove build artifacts and unrelated upstream docs from the repo
**Sửa**: xoá `invesalius_rs/target/` (cache build Rust, ~210MB, đã gitignore), `__pycache__/`, user guide PDF gốc InVesalius (~57MB, không liên quan đề tài, đã verify menu Help dùng link web chứ không đọc file local).
**Loại**: dọn dẹp, giữ nguyên toàn bộ tính năng InVesalius gốc (navigation, AI segmentation, plugin mẫu khác) theo quyết định của người dùng đề tài.

## `b472e1d7` — Close real testing gaps: verify F6/F7/F10/F14 with actual data
**Sửa**: không phải bugfix — bổ sung test thật cho pick 3D/đo khoảng cách 3D/xuất surface (trước đó chỉ test trạng thái, chưa test dữ liệu thật).
**Loại**: test, không sửa code chức năng.

## `64a72686` — Commit planning docs and update roadmap with verified progress
**Sửa**: bảo vệ các tài liệu kế hoạch/đề cương trước đó chưa từng commit; cập nhật checklist tiến độ với bằng chứng thật (không tick khi chưa verify).
**Loại**: tài liệu.

## `d574bf43` — Wire ROIManager into UI (segmentation management) + verify real mask export
**Sửa**: `core/roi_manager.py` (127 dòng) tồn tại từ đầu nhưng **chưa từng được gọi** ngoài `.clear()` — nối vào UI (ROI List: chọn/đổi tên/ẩn-hiện/xoá), verify bằng cách gọi thẳng `"Export masks to nifti"` (bypass dialog modal) để xác nhận file NIfTI thật được ghi ra với voxel thật.
**Loại**: code mới của đề tài, đóng gap "quản lý segmentation".

## `dbfde7d0` — Add user guide for the ROI Viewer plugin
**Loại**: tài liệu (`docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md`).

## `25257a70` — Fix real crash from stale VTK picker observer across plugin reopens
**Sửa**: lỗi thật do người dùng tự phát hiện khi thao tác trực tiếp (không phải qua test tự động) — mở/đóng/mở lại plugin nhiều lần làm rò rỉ VTK observer, gây crash `TextCtrl has been deleted` lặp lại nhiều lần. Sửa 3 lớp: gỡ observer đúng cách khi đóng (`EVT_CLOSE`), chặn mở trùng cửa sổ, phòng vệ tại điểm crash.
**Loại**: bugfix nghiêm trọng, phát hiện qua sử dụng thực tế — minh chứng giá trị của việc để người dùng thật thao tác song song với test tự động.

## `50c0ef01` / `0d26c983` — Wire Region Growing to real UI; add manual 3D surface rebuild; audit docs (VÒNG 1)
**Sửa/thêm**:
1. **Region Growing (bán tự động, seed-based)** — `core/segmentation.py.region_growing()` tồn tại từ đầu (BFS Python thuần) nhưng **hoàn toàn chưa được gọi** (DEAD_CODE). Nối vào UI mới trong `segmentation_panel.py` (pick seed 3D → grow → tạo mask thật, chạy nền bằng `threading.Thread` để không treo GUI). Verify: mask thật 16.264.693 voxel.
2. **Tối ưu hiệu năng Region Growing**: BFS Python thuần mất >15s (timeout) trên volume CT thật — thay bằng `scipy.ndimage.label` (đã là dependency sẵn có), cho **kết quả toán học tương đương** (6-connectivity) nhưng chạy 500ms (nhanh hơn ~30 lần).
3. **Nút "Update 3D Surface from Selected ROI"** — đóng gap D9 (mask sửa không tự cập nhật surface — hành vi thật của InVesalius gốc, đã verify `invesalius/data/surface.py` không subscribe topic sửa-mask nào). Rebuild thủ công theo yêu cầu, tránh rebuild tự động mỗi nét vẽ (rủi ro treo GUI đã được tài liệu kế hoạch cảnh báo trước).
4. **Sửa 5 chỗ `except:` trần** trong `interface/project_interface.py` — nuốt lỗi im lặng kể cả bug thật, đổi thành `except Exception as e: print(...)`.
5. Tài liệu audit: `CT3D_FEATURE_AUDIT.md`, `CT3D_ARCHITECTURE.md`, `CT3D_TEST_REPORT.md`, `CT3D_CHANGELOG.md`, `CT3D_REMAINING_WORK.md`.

## (VÒNG 2, 08/09/2026, chưa có mã commit tại thời điểm viết log này) — sửa sâu theo yêu cầu bằng chứng đầy đủ hơn

**Không audit lại từ đầu** — tập trung sửa các chỗ vòng 1 còn thiếu bằng chứng, hoàn thiện P1/P2 thật cần thiết, xoá code thừa, kiểm tra Save/Open, đảm bảo mask sửa cập nhật được 3D, test lại end-to-end.

1. **Bug thật phát hiện + sửa — "lazy threshold sentinel" ghi đè dữ liệu Region Growing khi build surface**: mask tạo qua placeholder `thresh=(1,1)` (Region Growing) có sentinel `matrix[n,0,0]=0` mọi lát → `Slice.do_threshold_to_all_slices()` (chạy trong MỖI lần build surface) âm thầm ghi đè dữ liệu tay-ghi bằng threshold(1,1) vô nghĩa trên ảnh gốc. Sửa tại `segmentation_panel.py._on_region_grown`: đánh dấu `matrix[1:, 0, 0] = 1` sau khi ghi kết quả grow thật.
2. **Bug thật phát hiện + sửa — ROI List không nạp mask đã tồn tại khi plugin mở SAU khi project đã load** (kịch bản phổ biến nhất): `roi_panel.py.ROIViewerFrame.__init__` giờ gọi `self.on_roi_source_changed()` ngay khi tạo cửa sổ, không chỉ chờ event tương lai.
3. **Region Growing an toàn**: `core/segmentation.py` thêm `validate_seed()`, tolerance ≥ 0 (raise `ValueError` nếu âm), `region_stats()` (voxel count/% volume/mm³), `max_region_fraction` (mặc định 20%, cấu hình được). `segmentation_panel.py._on_region_grown` cảnh báo Yes/No (có Cancel) nếu vùng grow vượt ngưỡng, luôn hiện seed value/tolerance/voxel count/mm³. Audit thread-safety xác nhận worker thread chỉ đụng numpy/scipy, mọi wx/dialog qua `wx.CallAfter`.
4. **ROIManager refactor thành cache/view** (`core/roi_manager.py`): không còn giữ bản sao `name`/`color`/`visible` độc lập — `rebuild_from_project_masks()` resync từ `Project().mask_dict` thật, gọi khi mask tạo/đổi tên/ẩn-hiện/xoá (kể cả qua tab Masks GỐC của InVesalius — `main.py` thêm subscribe `"Change mask name"`/`"Show mask"`/`"Remove masks"`). Xoá `points`/`bounds`/`locked`/`annotations`/`add_point()`/`contains_point()`/`get_center()`/`get_dimensions()`/`find_roi_at_point()` — 0 call-site (dead code thật).
5. **Annotation persistence** (`core/annotation.py`): điều tra `invesalius/project.py` xác nhận `project["annotations"]` là placeholder rỗng chưa hoàn thiện trong core (ghi cứng `{}`, không đọc lại khi load) — chọn sidecar JSON (`save_sidecar`/`load_sidecar`) theo đúng thứ tự ưu tiên yêu cầu, không sửa core. Wire vào `export_panel.py` (save, ngay sau khi dialog save thật đồng bộ trả về) và `roi_panel.py.on_project_load` (load, qua `wx.CallAfter` vì thời điểm event bắn ra path project chưa cập nhật).
6. **Xoá dead code thật** (không phải "có thể dùng sau"): `core/segmentation.py.watershed()`/`_simple_watershed()`/`morphological_op()`/`remove_small_objects()`/`fill_holes()` (trùng Watershed thật của InVesalius gốc, gọi thư viện chuẩn không phải nghiên cứu, 0 test/call-site), `interface/task_panel.py` (282 dòng, UI trùng lặp, 0 call-site), toàn bộ `utils/` (334 dòng, bản `world_to_voxel` thứ 3 SAI quy ước trục, 0 call-site). Tổng **-841/+496 dòng**.
7. **Save/Open roundtrip thật lần đầu tiên được test full-cycle**: `test_project_roundtrip.py` (19/20 PASS) — save→close (verify state reset thật)→open→so khớp mask/annotation/ROI List với baseline.
8. **Spacing/orientation/vendor verify bằng số liệu thật**: `test_coordinate_roundtrip.py` (11/11 PASS) — đọc tag DICOM thật qua gdcm (bộ đọc thật của InVesalius, không dùng `pydicom` — không phải dependency), so khớp `Slice().spacing`, round-trip voxel↔world tại 3 điểm, vendor thật xác nhận SIEMENS.
9. **D9/C7 (Update 3D Surface)**: test với mask NHỎ thật (không phải 16,2 triệu voxel như vòng 1) — verify polydata thật, tìm ra + sửa bug #1 ở trên. Thử `batch_mode: True` (tưởng an toàn hơn về lý thuyết) nhưng THỬ THẬT cho thấy treo 2/2 lần — revert về bản mặc định (có bằng chứng chạy được thật).
10. Tài liệu cập nhật: cả 5 file `CT3D_*.md` theo yêu cầu vòng 2.

## `498a71c7` — Fix real crash in InVesalius CORE (styles.py) — lần đầu tiên đụng vào `invesalius/`

**Bối cảnh**: người dùng tự phát hiện khi thao tác thật (xoá hết mask → import lại DICOM), gửi kèm traceback đầy đủ. Traceback 100% nằm trong code core (`control.py`, `slice_.py`, `viewer_slice.py`, `styles.py`) — **không có dòng nào của plugin**.

**Nguyên nhân thật**: `Viewer.CloseProject()` (`viewer_slice.py`) đặt `self.canvas = None` khi đóng project (xảy ra khi import DICOM mới, đóng project cũ trước). `DensityMeasureStyle.CleanUp()` (`styles.py` — lớp xử lý công cụ đo diện tích/mật độ polygon 2D, đúng công cụ nút "Measure Area (2D)" của plugin điều khiển, và cũng là công cụ đo mật độ gốc của InVesalius) không kiểm tra `None` trước khi gọi `self.viewer.canvas.unsubscribe_event(...)` — trong khi `viewer_slice.py` đã tự phòng vệ đúng chỗ này ở 4 nơi khác (`if self.canvas: ...`). Tìm thêm 2 chỗ khác cùng lỗi trong `styles.py` (window-level style, crop-rectangle style) — sửa cả 3.

**Verify thật**: viết script tái hiện đúng kịch bản (bật style → đóng project thật → bật lại style mặc định) — xác nhận **crash y hệt lỗi thật** (`AttributeError: 'NoneType' object has no attribute 'unsubscribe_event'`) trên code CHƯA sửa (2/3 check FAIL), rồi xác nhận PASS (3/3) sau khi sửa — kiểm chứng bằng `git stash`/`stash pop` để so sánh trực tiếp.

**Vì sao lần này đụng vào core**: nguyên tắc "không sửa `invesalius/`" trong suốt dự án là để bảo vệ kiến trúc plugin (remote-control qua pubsub, không viết lại tính năng gốc) — không phải cấm tuyệt đối sửa bug thật khi người dùng gặp phải trong lúc dùng app. Đây là 1 bug core có thật, độc lập với plugin (tái hiện được mà không cần cài plugin), sửa tối thiểu (thêm 3 chỗ kiểm tra `None` theo đúng pattern đã có sẵn trong cùng file), không đổi kiến trúc/hành vi gì khác.

## `40c2c38b` — Phase 08 (CT3D_P08_ROI3D_CLOSURE): tìm ra + sửa nguyên nhân gốc thật sự của D9/C7

**Bối cảnh**: 3 vòng audit trước đều xác nhận D9 (mask sửa → surface 3D cập nhật) ở trạng thái PARTIAL — pubsub gửi đúng, không exception, nhưng chưa từng quan sát được polydata thật đổi sau khi sửa mask. Giả thuyết trước đó (vòng 3) nghi do máy thiếu RAM khi build surface với volume CT thật ~28 triệu voxel.

**Nguyên nhân thật tìm ra ở Phase 08**: hoàn toàn không phải RAM/timing. Đọc trực tiếp `invesalius/data/surface_process.py.create_surface_piece()` xác nhận: `_on_update_surface()` của plugin luôn hardcode `"algorithm": "Default"`. Với `algorithm="Default"` và `from_binary=False`, marching cubes contour lại ẢNH GỐC theo `mask.threshold_range` — **không hề đọc `mask.matrix`**. Mọi chỉnh sửa mask trực tiếp (brush, region growing, undo/redo) do đó không có tác dụng gì lên surface dựng bằng "Default", bất kể mask thật sự chứa gì.

**Xác nhận chéo bằng chính InVesalius gốc**: `invesalius/gui/dialogs.py.SurfaceMethodPanel` — dialog gốc thật của InVesalius **tự ẩn hẳn lựa chọn "Default"** và hiện tooltip *"It is not possible to use the Default method because the mask was edited"* khi `mask.was_edited == True`, tự chuyển sang `"ca_smoothing"`. Cơ chế đọc mask thật (`from_binary=True`) đã có sẵn trong chính InVesalius gốc từ trước — plugin chỉ chưa bao giờ dùng đúng nó.

**Đã sửa**: `_on_update_surface()` chọn `algorithm="Binary"` (đọc mask thật) khi `mask.was_edited == True`, giữ `"Default"` khi mask chưa từng sửa tay (không regression cho luồng threshold thông thường). `_on_region_grown()` bổ sung `new_mask.was_edited = True` (trước đó thiếu, khiến bản vá không kích hoạt cho ROI tạo bằng Region Growing).

**Verify runtime thật (P08.2 — dataset tổng hợp nhỏ tránh treo do RAM)**: boot app thật bằng 1 lần import DICOM thật, hoán đổi `Slice().matrix`/`Project().mask_dict` bằng ảnh+mask tổng hợp (30×128×128) ngay trong tiến trình để giảm tải multiprocessing (2 piece thay vì ~7) mà vẫn chạy 100% code thật. Kết quả: **36/36 check PASS** — 3 chu kỳ sửa mask (mô phỏng brush) → Update 3D Surface liên tiếp, polydata thật đổi đúng mỗi lần (points 7296→13440→16368→18720, cells 14588→26876→32732→37436, bounds giãn đúng hướng), không tạo surface/actor trùng, `Render()` thành công mỗi lần, 0 crash report mới.

**D9 và C7 chính thức chuyển PARTIAL → WORKING**, có bằng chứng runtime đầy đủ, có thể tái lập — xem `CT3D_P08_ROI3D_CLOSURE_REPORT.md`.

**Loại**: bugfix logic thật trên code plugin (đề tài), không đụng file nào trong `invesalius/` (core gốc).

## `d366a635` — Phase 09 (CT3D_P09_INTERACTION_QA): triển khai Sync 2D→3D thật, sửa F3, phát hiện + sửa bug `project_loaded`

### Goal
Đóng các mục có UI/code nhưng chưa chứng minh runtime (B4/C3/D4/D5/E2/E3/F3), triển khai thật Sync 2D→3D thay vì gỡ bỏ, regression cho C4/C5/C7/D9/D7/I2.

### Added
- `core/marker_3d.py` (`CrosshairMarker3D`) — actor VTK hình cầu nhỏ đại diện vị trí crosshair 2D trong khung 3D. Thuần VTK, không phụ thuộc wx/invesalius, cùng quy ước với `core/picker_3d.py`.
- Sync 2D→3D triển khai đầy đủ: `main.py` subscribe topic thật `"Set cross focal point"` (InVesalius gốc gửi khi người dùng click/kéo trên khung 2D thật — xác nhận qua grep `invesalius/data/styles.py`, không phải cơ chế tự bịa), forward tới `roi_panel.py.ROIViewerFrame.on_cross_focal_point_changed()`, cập nhật marker theo đúng cờ `sync_mgr.sync_2d_3d` mà checkbox đã có từ trước (trước đây không ai đọc cờ này).

### Changed
- `annotation_panel.py._on_add_annotation()`: không còn fallback `(0,0,0)` khi chưa có vị trí — dùng `roi_panel.py.get_current_reference_position()` (ưu tiên pick 3D, sau đó crosshair 2D thật, cuối cùng từ chối + cảnh báo). Tính `voxel_position` thật qua `sync_mgr.world_to_voxel()` thay vì hardcode `(0,0,0)`.

### Fixed
- **Bug thật MỚI phát hiện qua test Phase 09** (không phải tính năng Phase 09, một lỗ hổng có từ trước bị phơi bày): `ROIViewerFrame.project_loaded` không đồng bộ ngược từ state thật khi plugin mở SAU khi project đã load — chỉ set `True` phản ứng sự kiện tương lai, giống lớp bug đã sửa cho ROI List ở vòng 2 nhưng bị bỏ sót cho cờ này. Ảnh hưởng thật: `on_slice_change()`, `on_mask_update()`, và Sync 2D→3D mới đều bị vô hiệu hoá âm thầm trong đúng kịch bản phổ biến nhất (import DICOM trước, mở plugin sau — workflow đã test hàng chục lần trong suốt dự án). Sửa bằng cách khởi tạo `project_loaded` từ `ProjectInterface().is_project_loaded()` thật ngay trong `__init__`.

### Tests
Verify runtime thật (không giả lập chuột — `"Set cross focal point"` là đúng topic InVesalius gốc gửi khi thao tác 2D thật): 28/28 check PASS — Sync 2D→3D (SYNC-T1 đến T6, 8 check: checkbox OFF không đổi vị trí, checkbox ON marker khớp tuyệt đối với world coordinate thật, không tăng actor count qua nhiều lần cập nhật, không gây event recursion — đếm được đúng 1 lần gọi/1 message, pick 3D vẫn hoạt động, đóng/mở lại không rò rỉ actor), F3 (F3-T1 đến T3, 5 check: từ chối đúng khi không có vị trí + cảnh báo hiện ra, toạ độ khớp tuyệt đối với pick, Go to không lỗi), regression C4/C5/D7/C7-D9(light)/I2 (15 check, không thoái lui). 0 crash report mới.

### Documentation
`docs/CT3D_P09_INTERACTION_QA_REPORT.md` (mới, đầy đủ template), cập nhật `CT3D_MASTER_PROGRESS.md`/`CT3D_FEATURE_AUDIT.md`/`CT3D_REMAINING_WORK.md`.

### Known Issues
B4/C3/D4/D5/E2/E3 và P08.5 (D9/C7 qua dialog mặc định) — 7 mục cần thao tác chuột thật, môi trường tự động hoá không thực hiện được. Checklist đầy đủ (kèm công thức đối chiếu sai số cho E2/E3) ở `CT3D_P09_INTERACTION_QA_REPORT.md` mục 9 — không đánh dấu WORKING cho các mục này.

### Phase Gate
`PHASE_GATE: PASS`

## `0e51bcf9` — Phase 10 (CT3D_P10_DATA_INTEGRITY): điều tra dứt điểm checksum Save/Open, đo + tối ưu bộ nhớ Undo/Redo

### Goal
Điều tra dứt điểm phát hiện "checksum voxel mask lệch sau Save/Open" còn tồn đọng từ Vòng 2/3 (`CT3D_REMAINING_WORK.md` mục 2a), và đo + (nếu có căn cứ) tối ưu bộ nhớ Undo/Redo. Không làm lại Phase 08 (D9/C7), không làm lại Phase 09 (Sync 2D→3D/F3), không thêm tính năng UI mới.

### Added
- `docs/CT3D_P10_DATA_INTEGRITY_REPORT.md` (mới, đầy đủ 25 mục theo template).

### Changed
- `plugins/roi_viewer/core/mask_editor.py`: `UndoRedoManager.__init__`'s `max_history` mặc định 20 → 10 (kèm comment giải thích số đo thật).

### Fixed
Không có bug thật nào trong Save/Open (kết luận **CASE A**, xem "Investigated" bên dưới). Không có bug chức năng nào khác được phát hiện phase này.

### Investigated (điều tra dứt điểm, không phải bug thật)
Đọc lại toàn bộ chuỗi gọi thật Save→Compress→Extract→Open (`invesalius/project.py`, `invesalius/data/mask.py`, `invesalius/control.py`) — xác nhận **không có bước biến đổi byte nào** ở bất kỳ đâu trong pipeline (`SavePlist`/`Compress`/`tarfile`/`Extract`/`OpenPList`/`_open_mask` đều là byte-pass-through thuần; `LoadProject()`'s `"Load slice to viewer"`/`"Add mask"` chỉ là wiring GUI/hiển thị, không đụng `mask.matrix`). Test runtime thật 5 kịch bản (RT-A: mask tay chính xác; RT-B: mask threshold thật; RT-C: mask đã sửa tay `was_edited=True`; RT-D: cùng 3 mask với gzip; RT-E: xoá mask giữa danh sách tạo lỗ hổng index) = **30/30 PASS**, checksum SHA-256 khớp tuyệt đối 100% (cả ma trận đầy đủ lẫn phần dữ liệu logic `matrix[1:,1:,1:]`) trong mọi trường hợp. RT-E chứng minh cụ thể cơ chế nhiều khả năng gây ra phát hiện cũ: `OpenPlistProject()` gán lại `index` liên tục theo thứ tự chèn (`m.index = len(self.mask_dict)`), nên nếu mask bị xoá trước khi lưu, `index` cũ không còn khớp sau khi mở lại — một phép so sánh theo `index` cũ (thay vì theo tên/identity) có thể so nhầm 2 mask khác nhau hoặc không tìm thấy mask, trông giống hệt "checksum lệch" mà không phải bug dữ liệu thật. Kết luận: **CASE A — không có bug thật, không cần sửa code Save/Open**.

Bộ nhớ Undo/Redo: benchmark thật (`copy.deepcopy(mask.matrix)` — memmap thật materialize thành mảng RAM thật mỗi checkpoint) — đo được đúng 27.36MB/checkpoint ở quy mô CT thật (109×513×513, khớp tuyệt đối lý thuyết 1 byte/voxel). Worst case cũ (`max_history=20` cả undo lẫn redo) ≈1.07GB — không phải lý thuyết suông: máy test quan sát được RAM trống thấp tới ~540-880MB ngay trong chính phiên test này. Đã xem xét và LOẠI bỏ phương án nén bit (`np.packbits`) vì `mask.matrix` không đảm bảo nhị phân tuyệt đối (cột đệm mang giá trị sentinel `1` phân biệt với `255`, dùng bởi cơ chế threshold lazy — nén bit có nguy cơ làm hỏng đúng phân biệt này mỗi lần undo/redo, đánh đổi hiệu năng lấy 1 lỗi dữ liệu thật mới — đi ngược mục đích chính của Phase 10). Chọn phương án tối thiểu, an toàn tuyệt đối: hạ `max_history` mặc định 20→10 (worst case còn ≈547MB), không đổi biểu diễn/ngữ nghĩa snapshot.

### Tests
`p10_saveopen_forensics.py`: 30/30 PASS (RT-A/B/C/D/E). `p10b_undoredo_benchmark.py`: benchmark thật (không phải PASS/FAIL, số đo). `p10c_undoredo_functional_tests.py`: 20/20 PASS (UR-T1 đến UR-T9 — deep-copy độc lập, undo/redo push/pop đúng, redo_stack bị xoá khi có action mới, eviction FIFO đúng ở `maxlen=10` mới, `clear()`, RSS thật ở quy mô CT thật). Regression (Section XIX, xem báo cáo mục 15): D1/D8/G1/G2/G3 re-verify trực tiếp qua RT-A/B/C/E; D9/C7/C8/F3 xác nhận KHÔNG bị đụng code (`git diff --stat` phase này chỉ có 1 file, `mask_editor.py`) nên không có nguy cơ thoái lui; D10/E4/F4 không re-run (không liên quan thay đổi 1 dòng của phase này, bằng chứng các vòng trước vẫn giữ nguyên). 0 crash report mới.

### Performance
Undo/Redo worst-case memory: ~1.07GB → ~547MB ở quy mô CT thật (giảm ~50%), không đổi tốc độ/độ chính xác undo-redo.

### Documentation
`docs/CT3D_P10_DATA_INTEGRITY_REPORT.md` (mới). Cập nhật `CT3D_MASTER_PROGRESS.md` (baseline Phase 10, D7/G1 rows), `CT3D_FEATURE_AUDIT.md` (G1/D7 rows), `CT3D_REMAINING_WORK.md` (xoá mục 2a, cập nhật bảng tổng kết), `HUONG_DAN_SU_DUNG_ROI_VIEWER.md` (sửa mục "Giới hạn đã biết" — bỏ tham chiếu `(0,0,0)` cũ đã lỗi thời từ Phase 09, bỏ mục checksum đã đóng, thêm ghi chú giới hạn Undo/Redo 10 bước).

### Known Issues
7 mục manual-QA từ Phase 09 (P08.5, B4, C3, D4, D5, E2, E3) **giữ nguyên `NEEDS_MANUAL_QA`**, không đụng tới, không tự nâng cấp. `MaskEditor.draw_point_2d/draw_point_3d/interpolate_slices` là dead code (phát hiện phase này, ngoài phạm vi — brush thật dùng `SLICE_STATE_EDITOR` gốc).

### Phase Gate
`PHASE_GATE: PASS`

## `36dc59ba` — Phase 11 (CT3D_P11_TEST_AUTOMATION): bộ pytest bền vững + sửa số liệu Undo/Redo + dọn dead code

### Goal
Chuyển bằng chứng quan trọng của Phase 08-10 (từng nằm trong script scratchpad tạm thời, đã mất) thành bộ `pytest` thật, nằm trong repository, chạy lại được bằng 1 lệnh. Kiểm chứng lại invariant bộ nhớ Undo/Redo của Phase 10 bằng code/test thật (không chỉ suy luận tay). Dọn dead code `MaskEditor` nếu và chỉ nếu 0 call-site thật. Không thêm tính năng UI mới. Không tự nâng 7 mục Manual QA.

### Added
`tests/ct3d/` (mới, 11 file, 109 test): `conftest.py` (cô lập `XDG_CONFIG_HOME`, reset singleton `Project()`/`Slice()` sau mỗi test, session-scoped `wx.App`), `test_segmentation.py` (RG-U1..U8, D10/D2), `test_measurement.py` (M-U1..U4, E1/E3/E4 — M-U4 là regression trực tiếp cho bug padding đã sửa ở Vòng 3), `test_coordinates.py` (voxel↔world, công thức tham chiếu viết độc lập), `test_undo_redo.py` (UR11-T1..T9 + investigation invariant bộ nhớ — xem mục "Undo/Redo memory" bên dưới), `test_annotation.py` (F1/F2/F4, sidecar round-trip qua `tmp_path`), `test_roi_manager.py` (D8, invariant "không ROI mồ côi"), `test_sync_2d3d.py` (C8 + F3, marker VTK thật qua `vtkRenderer()` không cần wx), `test_serialization.py` (G1/G2, thay thế `p10_saveopen_forensics.py` đã mất — RT-A/B/C/E của Phase 10 thành pytest thật), `test_exporters.py` (H1/H2-H5, NRRD tự `skip` khi thiếu `pynrrd`), `test_surface_policy.py` (D9/C7, dùng hàm `choose_surface_algorithm()` mới tách ra).

`pyproject.toml`: thêm `[tool.pytest.ini_options]` với 5 marker (`unit`/`integration`/`gui`/`slow`/`dataset`) — mục cấu hình pytest đầu tiên của repo, không ảnh hưởng bộ test `tests/` gốc (upstream, không dùng marker).

`plugins/roi_viewer/gui/segmentation_panel.py`: hàm thuần `choose_surface_algorithm(mask)` tách từ biểu thức inline trong `_on_update_surface()` — hành vi giữ nguyên 100%, chỉ để test được không cần dựng `wx.Frame`.

### Changed (sửa số liệu, không phải sửa code)
**Undo/Redo memory - sửa số liệu Phase 10 (KHÔNG đổi quyết định `max_history=10`)**: Phase 10 tính worst case `1.07GB → 547MB` dựa trên giả định `len(undo_stack)==max_history` VÀ `len(redo_stack)==max_history` có thể xảy ra đồng thời. Test invariant thật (`test_undo_redo_memory_invariant_*`, 6 chuỗi xác định theo đúng đặc tả + 300 chuỗi ngẫu nhiên seed cố định `20260914`, chỉ gọi public API `save/undo/redo/clear`) chứng minh điều này **SAI**: `save_state()` luôn xoá sạch `redo_stack` ngay khi thêm nội dung mới vào `undo_stack`, nên `len(undo_stack)+len(redo_stack)` không bao giờ vượt `max_history` (không phải `2×max_history`) qua bất kỳ chuỗi thao tác hợp lệ nào. Worst case thật đúng ở `max_history=10`: `10×27.36MB ≈ 273.6MB` — Phase 10 ước lượng cao gấp đúng 2 lần. Đã sửa lại: `CT3D_P10_DATA_INTEGRITY_REPORT.md` (thêm note "Phase 11 correction" ở đầu file, GIỮ NGUYÊN văn bản gốc bên dưới — không sửa lịch sử kiểu che giấu), `CT3D_MASTER_PROGRESS.md`, `CT3D_FEATURE_AUDIT.md`, `HUONG_DAN_SU_DUNG_ROI_VIEWER.md`.

### Fixed (static-quality, bằng chứng cụ thể, rủi ro thấp)
Cài `pyflakes` (nhẹ, không rủi ro) audit `plugins/roi_viewer/`: xoá import thật sự không dùng (`main.py`: `os` + 6 import module dư thừa vì `roi_panel.py` đã tự import trực tiếp 4 panel GUI và 2 module interface được import cục bộ ở nơi cần; `exporters.py`: `os`/`typing.List`/`tempfile`; `mask_editor.py`: `typing.List`; `measurement.py`: `time`; `sync_2d3d.py`: `typing.Optional`; `annotation_panel.py`: `datetime`; `export_panel.py`: `os`; `roi_panel.py`: `wx.lib.scrolledpanel as scrolled`; `picker_3d.py`: `vtkPointPicker`/`vtkInteractorStyleRubberBandPick`/`vtkCoordinate`). Xoá biến cục bộ chết `total_mean` trong `segmentation.py.auto_threshold_otsu()` (công thức between-class-variance thật sự dùng không cần biến này — không phải bug tính toán, chỉ là tính toán thừa còn sót). Phát hiện nhưng CỐ Ý chưa sửa: `global _roi_viewer_window` dư thừa (chỉ đọc) ở 10 chỗ trong `main.py` — style nit vô hại, không sửa để tránh diff lớn chỉ vì style.

### Cleanup (dead code, đã chứng minh 0 call-site trước khi xoá)
`plugins/roi_viewer/core/mask_editor.py` — grep toàn bộ repository (call trực tiếp, `getattr`/dynamic dispatch, event binding, callback, import, subclass override, tham chiếu tài liệu) xác nhận **0 call-site thật** cho: `draw_point_2d`, `erase_point_2d`, `draw_point_3d`, `interpolate_slices` (3 method Phase 10 đã phát hiện), và thêm `_get_brush_mask`, `set_brush_size`, `set_brush_shape`, `get_mask`, `set_mask`, `get_mask_slice`, và **`undo()`/`redo()`/`clear_mask()`** (wrapper method riêng của `MaskEditor` — GUI thật gọi thẳng `editor.undo_manager.undo(mask.matrix)`/`.redo(...)`, bỏ qua các wrapper này hoàn toàn). **Đã xoá: 175 dòng xoá / 29 dòng thêm (net -146 dòng)**. `UndoRedoManager` GIỮ NGUYÊN theo đúng chỉ đạo. Chạy lại toàn bộ `tests/ct3d` sau khi xoá: không có regression (109 passed, 1 skipped, giống hệt trước khi xoá). Thêm test bảo vệ (`test_mask_editor_surviving_surface_after_dead_code_removal`) để các method đã xoá không bao giờ vô tình quay lại. Chưa đụng tới `MaskEditorManager.set_current_mask/get_current_editor/delete_editor` (`NOT_PROVEN_DEAD`, chưa điều tra kỹ như trên, ghi nhận trong `CT3D_REMAINING_WORK.md`).

### Tests
`tests/ct3d`: **109 passed, 1 skipped** (lý do skip: `pynrrd` không cài, optional dependency), 3 lần chạy liên tiếp đều PASS giống hệt nhau (0.52-0.62s mỗi lần), không phụ thuộc thứ tự test, không rò rỉ state singleton giữa các test, không ghi vào config người dùng thật, không để lại temp file. `tests/` gốc (upstream, không đụng): **94 passed** (188.7s) — xác nhận không bị ảnh hưởng bởi thay đổi của phase này. Phân theo marker: `-m unit` 75 passed (0.14s); `-m integration` 33 passed + 1 skipped (0.45s).

### Performance/Memory Clarification
Xem mục "Changed" ở trên — worst case Undo/Redo thật đúng ở `max_history=10`: **~273.6MB** (không phải ~547MB như Phase 10 đã tính).

### Documentation
`docs/CT3D_P11_TEST_AUTOMATION_REPORT.md` (mới, 25 mục đầy đủ). Cập nhật `CT3D_MASTER_PROGRESS.md` (baseline Phase 11, sửa số liệu D7, thêm bằng chứng persistent test cho D9/D10/E4/F4/G1/H1/H5/Sync 2D→3D), `CT3D_FEATURE_AUDIT.md` (sửa số liệu D7), `CT3D_REMAINING_WORK.md` (xoá mục dead code đã đóng, thêm mục `NOT_PROVEN_DEAD` mới), `CT3D_P10_DATA_INTEGRITY_REPORT.md` (thêm note "Phase 11 correction" ở đầu file, không sửa văn bản gốc), `HUONG_DAN_SU_DUNG_ROI_VIEWER.md` (sửa số liệu 547MB→273.6MB, header lên Phase 11).

### Known Issues
7 mục manual-QA từ Phase 09 (P08.5, B4, C3, D4, D5, E2, E3) **giữ nguyên `NEEDS_MANUAL_QA`**, không đụng tới, không tự nâng cấp. `MaskEditorManager` có 3 method `NOT_PROVEN_DEAD` chưa điều tra kỹ. `global _roi_viewer_window` dư thừa ở 10 chỗ trong `main.py`, cố ý chưa sửa (style nit vô hại).

### Phase Gate
`PHASE_GATE: PASS`

## `52004e28` — Phase 12 (CT3D_P12_QUANTITATIVE_VALIDATION): chốt kỹ thuật + hạ tầng đánh giá định lượng

### Goal
Chốt các vấn đề kỹ thuật nhỏ còn sót sau Phase 11 (`MaskEditorManager` dead code, NRRD packaging), xây hạ tầng Dice/Jaccard/Hausdorff thật có unit test toán học + phantom biết trước, lập dataset registry thật, xác nhận đa vendor/multi-series trong giới hạn dữ liệu local, thử lại Region Growing full-volume có kiểm soát RAM, tạo manual-QA checklist chính thức. Không thêm tính năng UI mới, không bịa dataset/vendor/ground-truth/thao tác GUI.

### Added
- `plugins/roi_viewer/core/evaluation.py` (mới): `dice_coefficient()`, `jaccard_index()`, `hausdorff_distance()`, `hausdorff_distance_95()` — thuần numpy/scipy, quy ước trục/spacing tường minh (`spacing_zyx`, không mặc định `(x,y,z)`), dùng `scipy.ndimage.distance_transform_edt(sampling=...)` cho Hausdorff đúng đơn vị vật lý kể cả spacing anisotropic.
- `tests/ct3d/test_evaluation_metrics.py` (30 test), `tests/ct3d/test_phantom_validation.py` (12 test — Phantom A cuboid chính xác, Phantom B dịch chuyển biết trước, sphere xấp xỉ có ghi rõ sai số discretization), `tests/ct3d/test_dicom_grouping.py` (4 test — logic grouping DICOM đa-series, dùng object giả, không thay bằng chứng runtime thật).
- `docs/CT3D_DATASET_REGISTRY.md` (mới) — quét thật 3 dataset local bằng đúng DICOM stack InVesalius (`dicom_reader.GetDicomGroups()` → gdcm), không ghi PHI.
- `docs/CT3D_MANUAL_QA_CHECKLIST.md` (mới) — 7 mục, Preconditions/Exact Steps/Expected Result/công thức sai số cho E2/E3, tất cả `NOT_RUN`.
- `docs/CT3D_P12_QUANTITATIVE_RESULTS.csv` (mới) — bảng kết quả định lượng đầy đủ Test_ID/Expected/Actual/Error.
- `[project.optional-dependencies]` extra `nrrd = ["pynrrd>=1.0.0"]` trong `pyproject.toml`.

### Changed
- `plugins/roi_viewer/gui/export_panel.py`: dropdown "Format:" tự phát hiện `pynrrd` có cài hay không (`_is_nrrd_available()`) — nếu thiếu, hiện rõ "NRRD (.nrrd) - library not installed" + tooltip, và bấm Export báo lỗi rõ ràng NGAY (trước khi chọn file) thay vì chỉ báo sau khi export thất bại.

### Fixed / Cleanup (dead code, đã chứng minh 0 call-site trước khi xoá)
`plugins/roi_viewer/core/mask_editor.py.MaskEditorManager`: `get_current_editor()`/`set_current_mask()`/`delete_editor()` xác nhận `CONFIRMED_DEAD_CODE` (grep toàn repo — direct call/getattr/callback/pubsub/GUI binding/subclass/test/doc — 0 kết quả thật) — đã xoá (17 dòng xoá/11 dòng thêm, net -6). `self.current_index` (ghi bởi `create_editor()`, method còn sống) giữ nguyên dù giờ không còn ai đọc — không sửa hành vi của method đang sống chỉ vì dọn dead code. `plugins/roi_viewer/main.py`: 10 chỗ `global _roi_viewer_window` dư thừa (chỉ đọc, không gán trong scope đó — xác nhận qua `pyflakes`) đã xoá — `pyflakes` giờ sạch tuyệt đối cho toàn bộ `plugins/roi_viewer/`.

### Dataset Validation
Quét thật 3 dataset local (`0051`/`0801`/`mri3`) bằng `invesalius.reader.dicom_reader.GetDicomGroups()` (đúng DICOM stack InVesalius, không phải suy đoán từ tên file): `0051`=CT/SIEMENS, `0801`=CT/Philips (phát hiện MỚI — trước đây chưa từng đọc tag dataset này), `mri3`=MR/Philips Medical Systems (phát hiện MỚI). Import thật end-to-end (không chỉ đọc tag) PASS cả 3 — mỗi dataset 1 tiến trình riêng (phát hiện thật: reset singleton `Project.instance=None` giữa 2 lần import trong CÙNG tiến trình không tương đương `CloseProject()` thật, gây `KeyError` thật ở lần import thứ 2 — giới hạn phương pháp test, không phải bug InVesalius). A2 nâng NEEDS_RUNTIME_TEST → **PARTIAL** (2 vendor thật, chưa đủ WORKING — còn thiếu GE/Canon). A4: cả 3 dataset chỉ 1 series/study — `BLOCKED_EXTERNAL_DATA`, giữ NEEDS_RUNTIME_TEST.

### Quantitative Metrics
Dice/Jaccard: edge case empty/empty=1.0, empty/non-empty=0.0 (document rõ, không rơi ngẫu nhiên từ công thức); quan hệ Dice=2J/(1+J) verify đúng ở 3 mức overlap. Hausdorff: dùng `spacing_zyx` tường minh, verify đúng với spacing anisotropic (dịch 1 voxel theo trục spacing 3mm → Hausdorff=3mm chính xác, KHÔNG PHẢI 1 nếu tính sai theo voxel-index thuần); empty/empty=0.0, một mask rỗng → raise `ValueError` rõ ràng (không trả `inf`/`nan` ngầm). HD95 verify là metric KHÁC HD max (luôn ≤ HD max, khác nhau rõ khi có outlier). Phantom A (cuboid chính xác, không dùng sphere cho test volume exact) verify volume khớp tuyệt đối công thức tay. Phantom B (cuboid dịch chuyển biết trước) verify Dice/Jaccard/Hausdorff khớp tuyệt đối công thức tay ở 3 mức dịch chuyển.

### Tests
`tests/ct3d`: **158 passed, 1 skipped (159 collected)** sau khi thêm `test_dicom_grouping.py` và các test NRRD/MaskEditorManager mới — xem báo cáo mục 19 cho bảng đầy đủ, xác nhận lại 3 lần chạy liên tiếp. `tests/` gốc (upstream): 94 passed, không đổi.

### Performance
Region Growing full-volume CT thật (0051, 28.311.552 voxel): runtime 0.30s, RSS +28.5MB — đóng dứt điểm nghi vấn "treo do giới hạn thuật toán" từ vòng 3 (xác nhận là do RAM máy lúc đó thấp, machine-state-dependent).

### Documentation
`docs/CT3D_P12_QUANTITATIVE_VALIDATION_REPORT.md` (mới, 30 mục). Cập nhật `CT3D_MASTER_PROGRESS.md` (baseline Phase 12, A2/A4/D10/Sync rows, xoá mục "bộ pytest độc lập" stale), `CT3D_FEATURE_AUDIT.md` (header 14/09/2026, thêm `NEEDS_MANUAL_QA`/`BLOCKED_EXTERNAL_DATA` vào status vocabulary, A2/A4/D10 rows), `CT3D_REMAINING_WORK.md` (đóng mục 1b/9, cập nhật bảng tổng kết), `HUONG_DAN_SU_DUNG_ROI_VIEWER.md` (NRRD UI behavior, header Phase 12).

### Known Issues
7 mục manual-QA (P08.5, B4, C3, D4, D5, E2, E3) **giữ nguyên `NEEDS_MANUAL_QA`/`NOT_RUN`**, không tự nâng cấp — checklist chính thức ở `CT3D_MANUAL_QA_CHECKLIST.md`. GE/Canon và ground-truth THẬT cho Dice/Jaccard/Hausdorff vẫn `BLOCKED_EXTERNAL_DATA`.

### Release Readiness
`AUTOMATED_TECHNICAL_READY`: xem báo cáo mục 25. `MANUAL_QA_COMPLETE`: NO. `EXTERNAL_VALIDATION_COMPLETE`: NO. `RELEASE_CANDIDATE_READY`: xem báo cáo mục 25.

### Phase Gate
`PHASE_GATE: PASS`

## `787fad80` — Phase 13 (CT3D_P13_PERFORMANCE_COMPARISON): đóng Manual QA + benchmark hiệu năng + chuẩn bị comparison/SUS

### Goal
Đóng chính thức Manual QA 7/7 (bằng chứng thật từ người vận hành). Sửa documentation drift/hygiene còn sót (test count ambiguous, CSV lỗi quote, câu văn stale về đa vendor/Dice-Jaccard-Hausdorff). Benchmark hiệu năng có phương pháp trên dataset local thật. Chuẩn bị comparison methodology (InVesalius gốc vs plugin, 3D Slicer) và SUS protocol — không bịa dữ liệu.

### Added
- `tools/ct3d_benchmark.py` (mới) — benchmark tool tracked trong repo, không phải ad-hoc, không nhét vào GUI. Output CSV machine-readable.
- `docs/CT3D_P13_PERFORMANCE_COMPARISON_REPORT.md` (mới, 27 mục).
- `docs/CT3D_P13_PERFORMANCE_RESULTS.csv` (mới, 29 dòng dữ liệu benchmark thật).
- `docs/CT3D_SUS_PROTOCOL.md` (mới) — protocol SUS chuẩn (Brooke 1996), chưa có người tham gia thật.

### Changed
- `docs/CT3D_MANUAL_QA_CHECKLIST.md`: viết lại tại chỗ với evidence thật 7/7 PASS từ người vận hành (không tạo file mới/duplicate).
- `docs/CT3D_MASTER_PROGRESS.md`, `docs/CT3D_FEATURE_AUDIT.md`: B4/C3/D4/D5/E2/E3 nâng `NEEDS_MANUAL_QA` → `WORKING`; D9/C7 KHÔNG đổi status, chỉ bổ sung ghi chú GUI evidence.
- `docs/CT3D_REMAINING_WORK.md`: đóng mục "1c" (Manual QA), sửa câu văn stale về đa vendor ("chưa đọc 0801/mri3") và Dice/Jaccard/Hausdorff ("hoàn toàn chưa thực hiện").
- `docs/CT3D_CHANGELOG.md`: sửa câu mập mờ "158 passed → 159" thành rõ ràng "158 passed, 1 skipped (159 collected)".

### Fixed
`docs/CT3D_P12_QUANTITATIVE_RESULTS.csv`: 1 dòng (`AREA-M-U-scaled`) có dấu phẩy trong cột Notes chưa quote đúng chuẩn CSV, làm dòng thành 11 field thay vì 10. Đã sửa bằng cách quote đúng — verify lại bằng `csv` module + `pandas.read_csv()`, không sửa số liệu metric nào.

### Tests
`tests/ct3d`: 158 passed, 1 skipped (159 collected), 3 lần chạy liên tiếp đều giống nhau. `tests/` gốc (upstream): 94 passed. `pyflakes plugins/roi_viewer`: 0 finding.

### Performance
Benchmark thật trên dataset local (`0051`/`0801`/`mri3`): Import DICOM ~8.2s (`0051`, 28.3M voxel); Otsu threshold ~0.44-0.65s; Region Growing ~0.4-0.7s (kết quả nhất quán với Phase 12); Surface build (quality "Low", 1 lần/dataset — phát hiện thật: build lặp lại 3 lần trên máy RAM thấp chậm hơn 6-7 lần mỗi lần lặp, không an toàn để lặp) ~10-13s; Project Save/Open (small controlled) <0.15s mỗi thao tác. Chi tiết đầy đủ + phát hiện thật về RAM/multiprocessing: `CT3D_P13_PERFORMANCE_COMPARISON_REPORT.md` mục 8-15.

### Documentation
Xem mục "Changed" ở trên, và toàn bộ file mới liệt kê ở mục "Added".

### Known Issues
GE/Canon, ground-truth thật cho Dice/Jaccard/Hausdorff, và người tham gia SUS thật vẫn `BLOCKED_EXTERNAL_DATA`/chưa có — không bịa.

### Release Readiness
`AUTOMATED_TECHNICAL_READY`: YES. `MANUAL_QA_COMPLETE`: YES (7/7 PASS thật). `SOFTWARE_TECHNICAL_COMPLETE`: YES. `EXTERNAL_VALIDATION_COMPLETE`: NO. Chi tiết: `CT3D_P13_PERFORMANCE_COMPARISON_REPORT.md` mục 24.

### Phase Gate
`PHASE_GATE: PASS`

## `3d070f7c` — Pre-Phase-14: Visual 2D→3D Slice Synchronization

### Goal
Hoàn thiện trực quan cho C8 (Sync 2D→3D, đã WORKING từ Phase 09) theo yêu cầu UX thật của người dùng: khi click/kéo crosshair trên 2D, khung Volume thể hiện rõ hơn vị trí 3 mặt cắt hiện tại, không chỉ 1 marker nhỏ. KHÔNG phải feature ID mới (không phải C9). KHÔNG tự động bật native tool `"Slices' cross intersection"` — người dùng tự bật khi cần.

### Added
- `plugins/roi_viewer/core/slice_planes_3d.py` (mới): `SlicePlanes3D` — 3 vtkActor (Axial/Coronal/Sagital) bán trong suốt, không texture ảnh CT (out of scope phase này), tạo actor 1 lần, chỉ update geometry mỗi lần crosshair đổi. API: `attach()`/`detach()`/`set_bounds()`/`update_position()`/`set_visible()`. Non-pickable (`SetPickable(False)`) — không cản Pick 3D/Region Growing seed/Distance 3D.
- Checkbox `"Show slice planes in 3D"` (mặc định ON) trong tab Interaction — độc lập với checkbox `"Sync 2D -> 3D"` đã có.
- Help text prerequisite trong UI: `Requires InVesalius "Slices' cross intersection" tool to be active.`
- `tests/ct3d/test_slice_planes_3d.py` (16 test, unit-adjacent/integration — VTK renderer thật).
- Mở rộng `tests/ct3d/test_sync_2d3d.py` (+9 test SYNC3D-T1..T9, qua đúng `on_cross_focal_point_changed()` thật).
- `docs/CT3D_P13_5_VISUAL_SYNC_REPORT.md` (mới).

### Changed
- `plugins/roi_viewer/gui/roi_panel.py`: `on_cross_focal_point_changed()` mở rộng — cùng event, cùng cờ `sync_mgr.sync_2d_3d`, thêm cập nhật `slice_planes_3d` song song với `marker_3d` đã có. Thêm `_compute_volume_bounds()` (tái sử dụng `ProjectInterface().voxel_to_world()` thật, đã test — không hardcode dimensions/spacing/origin). `on_project_load()`/`on_project_close()`/`_on_close()` cập nhật để refresh bounds/detach đúng lifecycle, cùng pattern đã có với `marker_3d`.
- `plugins/roi_viewer/gui/interaction_panel.py`: thêm checkbox + handler cho "Show slice planes in 3D".

### Tests
`tests/ct3d`: 184 collected, 183 passed, 1 skipped, 0 failed (3 lần chạy liên tiếp giống nhau). Upstream `tests/`: 94 passed. `pyflakes plugins/roi_viewer tools`: 0 finding. `python -m compileall plugins/roi_viewer`: sạch.

### Manual QA Required
Mục mới "C8 — Visual Sync 2D → 3D Slice Planes" (9 bước A-I) trong `CT3D_MANUAL_QA_CHECKLIST.md` — tất cả `NOT_RUN`, chờ người dùng tự thao tác chuột thật.

### Known Behavior
`"Slices' cross intersection"` vẫn là công cụ native, người dùng tự bật/tắt trên toolbar InVesalius gốc — plugin không bao giờ tự động bật/tắt tool này. Mặt phẳng chỉ mang tính trực quan vị trí (không texture ảnh CT). Crosshair di chuyển KHÔNG rebuild surface 3D (surface chỉ dựng lại khi bấm "Update 3D Surface from Selected ROI" — tránh biến thao tác crosshair thành operation nặng ~10-13s theo Phase 13). Camera không tự động rotate/zoom/pan/reset khi crosshair đổi.

### Phase Gate
`PHASE_GATE: PASS` (automated); manual GUI evidence cho mục C8 Visual Sync: `NOT_RUN`.

---

## `bed0c624` — Phase 14 Final Audit & Software Release Candidate

### Goal
Phase CUỐI của roadmap phần mềm (Phase 08→14). Không thêm feature mới, không refactor lớn, không đổi kiến trúc ổn định nếu không có bug thật. Audit toàn diện + đóng gói release-candidate: reconcile C8, sửa doc drift, đối chiếu benchmark, static analysis riêng biệt plugin/tool, regression 3x, không dữ liệu/bằng chứng giả.

### Final audit
Git lineage xác nhận linear (không branch/merge). Worktree pre-existing: 3 file `.md` kế hoạch gốc ở root (`Ke_hoach_de_tai_InVesalius_CT3D.md`, `Lộ trình phát triển.md`, `Đề cương NCKH.md`) đã bị di chuyển vật lý vào `docs/` từ trước Phase 08 nhưng chưa bao giờ được `git` hoàn tất — verify nội dung byte-identical (chỉ khác CRLF/LF) giữa bản gốc (qua `git show HEAD:`) và bản `docs/`, hoàn tất rename thật qua 1 commit riêng (`54f2f479`) trước khi bắt đầu audit Phase 14. `docs/Phan_tich_tien_do_tong_the.md` (progress snapshot mồ côi, không có bản gốc ở root) cũng được commit cùng lúc.

### C8 closure
Grep xác nhận `"Create surface from index"` chỉ xuất hiện đúng 1 lần trong plugin (`segmentation_panel.py`, luồng Update Surface chủ động) — KHÔNG có trong `on_cross_focal_point_changed()` (crosshair path), khớp đúng docstring "does NOT rebuild any surface". Người vận hành thật đã tự chạy 1 phiên smoke test core path cho C8 (native tool ON + Sync 2D→3D ON + click/kéo 2D) — báo cáo PASS, ghi lại trung thực thành `C8_VISUAL_OPERATOR_SMOKE = PASS` trong `CT3D_MANUAL_QA_CHECKLIST.md`. 9 mục lettered A-I KHÔNG được nâng cấp thành PASS (không có bằng chứng itemize riêng) — ghi đúng `NOT_EXPLICITLY_MANUAL_VERIFIED`, tách rõ khỏi 25/25 automated regression PASS (`SYNC3D-T1..T9` + `SP3D-T` + extras).

### Documentation consistency
`CT3D_FEATURE_AUDIT.md`: sửa top metadata (14/09→17/09/2026, Phase 12→Phase 14), sửa inconsistency Status-vs-Runtime cho B4/C3/D4/D5/E2/E3 (Runtime `NEEDS_MANUAL_QA`→`✓ (manual)`), C8 Runtime→`✓ automated + operator visual smoke`, làm rõ lịch sử baseline test theo từng phase (không gộp lẫn 109/159/184). `HUONG_DAN_SU_DUNG_ROI_VIEWER.md`: sửa header còn ghi "Phase 12" dù đã có nội dung Phase 13.5. `CT3D_MANUAL_QA_CHECKLIST.md`: cập nhật C8 trung thực theo đúng phạm vi bằng chứng operator thật.

### Benchmark reconciliation
`CT3D_P13_PERFORMANCE_RESULTS.csv`: sửa nhãn `Run` trùng lặp cho `0051` Import DICOM (2 dòng cùng `Run=1` từ 2 tiến trình thật riêng biệt → sửa thành `Run=1`/`Run=2`, KHÔNG đụng số liệu đo). Reclassify kết quả `0801` surface build rỗng (0 điểm) thành `BENCHMARK_INPUT_EMPTY` (threshold band benchmark hẹp tình cờ chọn trúng vùng rỗng, không phải bug thật) — chạy lại đại diện thật với threshold data-derived (full Otsu range, asserted `foreground_count > 0` trước khi build): **PASS thật, 145,772 điểm, 254,978 cell**, RAM 1.82GB khả dụng lúc build — thêm dòng mới (`Run=2`), không ghi đè lịch sử. "10000.0 FPS" xác nhận là artifact đo lường tối thiểu VTK trên mesh cực nhỏ — loại khỏi mọi tuyên bố hiệu năng đại diện; con số đại diện thật dùng lại: **122.0-158.3 FPS** (đã verify trước đó, `CT3D_FEATURE_AUDIT.md` mục C2).

### Static analysis
`pyflakes plugins/roi_viewer`: sạch (exit 0, báo cáo riêng). `pyflakes tools/ct3d_benchmark.py`: sạch (exit 0, báo cáo riêng — không gộp lẫn 2 kết quả). `python -m compileall plugins/roi_viewer` + `python -m py_compile tools/ct3d_benchmark.py`: PASS riêng biệt. Sửa `tools/ct3d_benchmark.py`: `REPO_ROOT` hardcode tuyệt đối (`D:\Learns\...`) → derive từ `__file__` thật (portable, hành vi không đổi trên máy hiện tại); `DATASETS` root path → override được qua env var `CT3D_DICOM_SAMPLES_DIR` (default giữ nguyên) — không phải feature mới, là path-portability fix tối thiểu cho 1 dev tool.

### Regression
`tests/ct3d -q`: **183 passed, 1 skipped** (184 collected) — chạy **3 lần liên tiếp**, kết quả giống hệt cả 3 lần. `tests --ignore=tests/ct3d -q` (upstream): **94 passed**, không đổi. Import smoke test thật (không GUI): core modules sạch, `slice_planes_3d`/`evaluation` import OK, `plugin.json` parse đúng, `PluginManager.find_plugins()` thật xác nhận phát hiện "ROI Viewer" cùng 7 plugin gốc khác, benchmark tool `--help` chạy đúng.

### Manual evidence
7/7 mục gốc PASS (Phase 13) giữ nguyên, không đụng. C8 core path: `C8_VISUAL_OPERATOR_SMOKE = PASS` (Phase 14, evidence thật). Không có mục nào bị nâng cấp thành PASS khi thiếu bằng chứng cụ thể.

### Known limitations
Tài liệu hoá đầy đủ 14 mục, phân loại `SOFTWARE_LIMITATION`/`ENVIRONMENT_DEPENDENCY`/`EXTERNAL_VALIDATION_GAP`/`OUT_OF_SCOPE` — xem `CT3D_KNOWN_LIMITATIONS.md` (mới).

### Release readiness
`docs/CT3D_RELEASE_NOTES.md` (mới) — bao gồm disclaimer research-prototype rõ ràng, KHÔNG phải thiết bị y tế, chưa clinical validation.

### External validation
`RESEARCH_EXTERNAL_VALIDATION_COMPLETE = NO`, `CLINICAL_VALIDATION_COMPLETE = NO` — không đổi, không giả lập.

### Phase Gate
`PHASE_GATE: PASS` — xem `CT3D_P14_FINAL_AUDIT_REPORT.md` cho chi tiết đầy đủ 27 tiêu chí. **SOFTWARE ROADMAP PHASE 08–14: COMPLETE. KHÔNG CÓ PHASE 15.**

---

## `c43fa569` — Post-Phase-14 Release Closure (22/09/2026)

### Goal
KHÔNG phải Phase 15. Chỉ sửa consistency cuối cùng, khoá tài liệu release, xác minh Git history, chạy final regression, xác minh worktree sạch. Không thêm feature, không sửa thuật toán đang WORKING, không refactor lớn, không đổi architecture.

### Git reconciliation
Xác định lại chính xác: main Phase 14 commit = `bed0c624`, hash-fill-in follow-up = `6dae0922` (= HEAD thật tại thời điểm bắt đầu phiên này). Phase 14 report trước đó ghi "HEAD after this phase = bed0c624" — không sai về commit chính nhưng thiếu rõ ràng vì không nhắc tới follow-up commit đứng sau nó. Đã sửa đồng nhất trong `CT3D_P14_FINAL_AUDIT_REPORT.md`, `CT3D_MASTER_PROGRESS.md`. Không rewrite/reset/amend lịch sử Git.

### Documentation fixes
- `CT3D_MASTER_PROGRESS.md`: sửa mis-attribution "Phase 11 = 158 test" (đúng: Phase 11 ~109 test, 158 là Phase 12/13); sửa "Phase 14+" → "post-roadmap external research work"; tách rõ OPTIONAL_INTERNAL (C8 A-I, ca_smoothing) khỏi EXTERNAL trong "Next phase".
- `CT3D_REMAINING_WORK.md`: thêm cột "Loại" (EXTERNAL_VALIDATION/OUT_OF_SCOPE/OPTIONAL_INTERNAL) vào bảng P3; thêm mục 9 (`ca_smoothing`); sửa 3 chỗ "Phase 14+".
- `HUONG_DAN_SU_DUNG_ROI_VIEWER.md`: sửa wording ngưỡng RAM cố định "~5GB" (không có bằng chứng) thành wording evidence-based (memory-sensitive, phụ thuộc nhiều yếu tố, dẫn chứng thật: `0801` build thành công với chỉ 1.82GB khả dụng).
- `CT3D_SUS_PROTOCOL.md`: làm mềm wording "10-20 người đủ tin cậy" thành "practical target", yêu cầu báo cáo n/mean/SD/CI, không có cỡ mẫu nào tự động đảm bảo ý nghĩa thống kê.
- `CT3D_KNOWN_LIMITATIONS.md`: sửa taxonomy NRRD (`SOFTWARE_LIMITATION` → `ENVIRONMENT_DEPENDENCY`).
- `CT3D_P14_FINAL_AUDIT_REPORT.md`: sửa §24 (DICOM-SEG từng bị liệt kê đồng thời ở cả `SOFTWARE_LIMITATION` và `OUT_OF_SCOPE` — sửa còn `OUT_OF_SCOPE` duy nhất; NRRD đồng bộ theo `CT3D_KNOWN_LIMITATIONS.md`); thêm section "Post-Phase-14 Release Closure Corrections" (addendum, không xoá nội dung gốc).

### Regression (re-run)
`tests/ct3d -q`: 183 passed, 1 skipped (184 collected) — giống hệt baseline Phase 14, không có drift. Upstream: 94 passed. `pyflakes` plugin + benchmark tool: đều exit 0 (báo cáo riêng). `compileall`/`py_compile`: PASS. CSV P12 (34 rows/10 cols) + P13 (30 rows/11 cols): đều valid, 0 duplicate key. Production path scan `plugins/roi_viewer`: 0 hardcoded machine path.

### Worktree
`git status` sạch trước và sau khi commit closure pass này.

### Phase Gate
`RELEASE_CLOSURE_GATE: PASS`. KHÔNG PHẢI Phase 15. Không thêm feature/thuật toán/architecture. Roadmap phần mềm Phase 08-14 vẫn COMPLETE.

---

## Final Release Freeze (22/09/2026)

- **Không phải Phase 15.** Không có thay đổi chức năng/thuật toán/UI/architecture.
- Sửa cấu trúc self-referencing HEAD metadata (không còn 1 file nào hard-code "current HEAD" tự tham chiếu chính commit đang được tạo) — thay bằng "release baseline commit" cố định (`c43fa569`) + hướng dẫn dùng `git rev-parse HEAD` cho tip thật. Xem `CT3D_P14_FINAL_AUDIT_REPORT.md` mục "Final Release Freeze Note" và `CT3D_MASTER_PROGRESS.md`.
- Tạo `docs/CT3D_RELEASE_MANIFEST.md` (bản đồ release tổng thể, mọi commit hash đã verify thật qua `git log`) và `docs/CT3D_INSTALL_AND_RUN.md` (hướng dẫn cài đặt/chạy đặc thù CT3D — README gốc chỉ trỏ tới wiki upstream, không có hướng dẫn riêng cho plugin/test/benchmark tool).
- Sửa `CT3D_SUS_PROTOCOL.md`: bỏ đường dẫn Windows cục bộ của máy phát triển (`D:\PyTools\dicom_samples\0051`) khỏi Task Scenario — không portable cho protocol khảo sát thật với người tham gia bên ngoài; thay bằng tham chiếu dataset kỹ thuật (`0051`) + biến môi trường.
- Final verification only: regression re-run (183 passed/1 skipped/184 collected, upstream 94 passed — không đổi), CSV re-check (P12 34 rows/10 cols, P13 30 rows/11 cols, 0 duplicate key), production-path scan sạch, `git status` sạch trước/sau commit.
- **Release candidate frozen after regression.** Git tag khuyến nghị sau commit này: `ct3d-rc1` — KHÔNG tự tạo/tự push, chờ operator xác nhận.

`RELEASE_FREEZE_GATE: PASS`. Roadmap phần mềm Phase 08-14 vẫn COMPLETE. KHÔNG CÓ PHASE 15.

---

## Tổng kết: phần nào của đề tài, phần nào của InVesalius gốc

- **100% code mới của đề tài**: toàn bộ `plugins/roi_viewer/` (main.py, gui/, core/, interface/) — ~4700+ dòng.
- **Không sửa file nào trong `invesalius/` (core gốc) trong suốt quá trình phát triển plugin** — đúng nguyên tắc "remote-control qua pubsub", không phá kiến trúc. **1 ngoại lệ duy nhất**: commit `498a71c7` sửa 1 bug crash thật trong `invesalius/data/styles.py` (không liên quan kiến trúc plugin, tái hiện được độc lập không cần plugin, sửa tối thiểu 3 dòng theo đúng pattern phòng vệ đã có sẵn trong file) — xem chi tiết ở mục commit đó.
- **Tài liệu đề tài** (`docs/CT3D_*.md`, `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md`, `docs/NCKH/`, `docs/DE_TAI_NCKH_TONG_QUAN.md`, `Lộ trình phát triển.md`, `Đề cương NCKH.md`) — 100% viết mới cho đề tài.
