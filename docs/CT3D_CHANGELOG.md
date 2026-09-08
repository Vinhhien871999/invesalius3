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

---

## Tổng kết: phần nào của đề tài, phần nào của InVesalius gốc

- **100% code mới của đề tài**: toàn bộ `plugins/roi_viewer/` (main.py, gui/, core/, interface/) — ~4700+ dòng.
- **Không sửa bất kỳ file nào trong `invesalius/` (core gốc)** trong suốt quá trình phát triển plugin — đúng nguyên tắc "remote-control qua pubsub", không phá kiến trúc.
- **Tài liệu đề tài** (`docs/CT3D_*.md`, `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md`, `docs/NCKH/`, `docs/DE_TAI_NCKH_TONG_QUAN.md`, `Lộ trình phát triển.md`, `Đề cương NCKH.md`) — 100% viết mới cho đề tài.
