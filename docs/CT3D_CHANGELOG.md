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

## (phiên hiện tại, chưa có mã commit tại thời điểm viết log này)
**Sửa/thêm**:
1. **Region Growing (bán tự động, seed-based)** — `core/segmentation.py.region_growing()` tồn tại từ đầu (BFS Python thuần) nhưng **hoàn toàn chưa được gọi** (DEAD_CODE). Nối vào UI mới trong `segmentation_panel.py` (pick seed 3D → grow → tạo mask thật, chạy nền bằng `threading.Thread` để không treo GUI). Verify: mask thật 16.264.693 voxel.
2. **Tối ưu hiệu năng Region Growing**: BFS Python thuần mất >15s (timeout) trên volume CT thật — thay bằng `scipy.ndimage.label` (đã là dependency sẵn có), cho **kết quả toán học tương đương** (6-connectivity) nhưng chạy 500ms (nhanh hơn ~30 lần).
3. **Nút "Update 3D Surface from Selected ROI"** — đóng gap D9 (mask sửa không tự cập nhật surface — hành vi thật của InVesalius gốc, đã verify `invesalius/data/surface.py` không subscribe topic sửa-mask nào). Rebuild thủ công theo yêu cầu, tránh rebuild tự động mỗi nét vẽ (rủi ro treo GUI đã được tài liệu kế hoạch cảnh báo trước).
4. **Sửa 5 chỗ `except:` trần** trong `interface/project_interface.py` — nuốt lỗi im lặng kể cả bug thật, đổi thành `except Exception as e: print(...)`.
5. Tài liệu audit: `CT3D_FEATURE_AUDIT.md`, `CT3D_ARCHITECTURE.md`, `CT3D_TEST_REPORT.md`, `CT3D_CHANGELOG.md`, `CT3D_REMAINING_WORK.md`.

---

## Tổng kết: phần nào của đề tài, phần nào của InVesalius gốc

- **100% code mới của đề tài**: toàn bộ `plugins/roi_viewer/` (main.py, gui/, core/, interface/) — ~4700+ dòng.
- **Không sửa bất kỳ file nào trong `invesalius/` (core gốc)** trong suốt quá trình phát triển plugin — đúng nguyên tắc "remote-control qua pubsub", không phá kiến trúc.
- **Tài liệu đề tài** (`docs/CT3D_*.md`, `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md`, `docs/NCKH/`, `docs/DE_TAI_NCKH_TONG_QUAN.md`, `Lộ trình phát triển.md`, `Đề cương NCKH.md`) — 100% viết mới cho đề tài.
