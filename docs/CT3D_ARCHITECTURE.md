# Kiến trúc thực tế — InVesalius CT 3D + plugin ROI Viewer

> Tài liệu này mô tả kiến trúc **thật**, đối chiếu trực tiếp với source code (tên file/class/function lấy nguyên văn, không suy diễn), sau khi đã làm việc trực tiếp và test thật trong toàn bộ các module liên quan. Không dùng tên module giả định từ tài liệu kế hoạch.

---

## 1. Sơ đồ tổng quan

```
DICOM files
   │
   ▼
invesalius/reader/dicom_reader.py (LoadDicom)
   │  đọc metadata, dựng series
   ▼
invesalius/reader/dicom_grouper.py (DicomGrouper/DicomGroup)
   │  nhóm slice theo patient/series/orientation
   ▼
Publisher.sendMessage("Import directory", directory=..., use_gui=...)
   │
   ▼
invesalius/control.py (Controller)  ← chủ thể điều phối chính, subscribe hầu hết pubsub topic cấp cao
   │
   ├──▶ invesalius/project.py (Project, singleton)      — metadata project, mask_dict, surface_dict, spacing
   ├──▶ invesalius/data/slice_.py (Slice, singleton)     — ma trận voxel 3D thật (self.matrix), current_mask,
   │        window_width/level, các phép biến đổi (threshold, brush, undo/redo qua Mask.history)
   ├──▶ invesalius/data/mask.py (Mask)                   — 1 mask = 1 numpy array nhị phân + threshold_range + colour
   ├──▶ invesalius/data/viewer_slice.py (Viewer)          — canvas VTK cho Axial/Coronal/Sagittal (2D)
   ├──▶ invesalius/data/viewer_volume.py (Viewer)         — canvas VTK cho Volume/Surface (3D)
   ├──▶ invesalius/data/styles.py / styles_3d.py          — interactor style theo state (brush, watershed, đo lường...)
   └──▶ invesalius/data/surface.py (SurfaceManager)       — Marching Cubes (vtkContourFilter) trên Mask → vtkPolyData
```

**Cơ chế giao tiếp**: `pypubsub` (`invesalius.pubsub.pub`, wrap `pubsub.pub`), đúng như tài liệu kế hoạch mô tả. Đã verify thật (không chỉ đọc source) rằng:
- Nhiều topic là **hierarchical/tuple** (vd. `("Set scroll position", "AXIAL")`), không phải string phẳng — sai chỗ này sẽ crash hoặc không nhận được message (đã phát hiện + sửa nhiều lỗi loại này trong plugin, xem `CT3D_CHANGELOG.md`).
- pypubsub xác định **message data spec (MDS)** của 1 topic từ subscriber ĐẦU TIÊN — mọi subscriber sau phải tương thích chữ ký đó, kể cả tham số optional (đã phát hiện lỗi `ListenerMismatchError` thật vì thiếu tham số).

---

## 2. Pipeline Mask → Surface → 3D Viewer (đã verify thật, không chỉ đọc code)

```
Mask.matrix (numpy 3D, nhị phân, có padding index-0 mỗi trục + sentinel
             matrix[n,0,0] đánh dấu "slice n đã lazy-threshold")
   │
   │  Publisher.sendMessage("Create surface from index", surface_parameters={...})
   ▼
invesalius/data/slice_.py: Slice.CreateSurfaceFromIndex(surface_parameters)
   │  gọi self.do_threshold_to_all_slices(mask)  ← LAZY THRESHOLD:
   │     chỉ áp threshold cho slice n nếu mask.matrix[n,0,0] == 0
   │     (nghĩa là: ghi trực tiếp vào matrix mà xoá luôn ô sentinel này
   │      sẽ bị InVesalius tự động "sửa lại" theo threshold_range gốc —
   │      đã verify bằng test thật, xem CT3D_TEST_REPORT.md)
   │  Publisher.sendMessage("Create surface", slice_=self, mask=mask, surface_parameters=...)
   ▼
invesalius/data/surface.py: SurfaceManager.AddNewActor(...)
   │  vtkContourFilter (Marching Cubes) → PolyData → gộp/làm sạch mesh
   │  (đã đo thật: [PERF] Extraction (vtkContourFilter) ~0.1-0.3s/lát cắt-nhóm,
   │   Cleaning merged surface ~0.9-1.0s cho mesh ~900K điểm)
   │  Project().surface_dict[index] = Surface(polydata=...)
   │  Publisher.sendMessage("Load surface actor into viewer", actor=...)
   ▼
invesalius/data/viewer_volume.py: Viewer.AddSurface(actor)
   │  ren.AddActor(actor); ren.ResetCamera() (lần đầu); UpdateRender()
   ▼
Người dùng thấy surface 3D
```

**Phát hiện quan trọng (verify bằng grep + test thật)**: `invesalius/data/surface.py` **không subscribe vào bất kỳ topic sửa-mask nào** (`"Reload actual slice"`, `"Create new mask"`, brush events...). Nghĩa là: **sửa mask (brush/undo/region growing) KHÔNG tự động cập nhật surface 3D đã tạo trước đó** — người dùng/plugin phải chủ động gọi lại `"Create surface from index"`. Đây là hành vi THẬT của InVesalius gốc, không phải giới hạn riêng của plugin.

---

## 3. Nơi plugin `roi_viewer` gắn vào (không viết lại InVesalius, chỉ remote-control)

```
plugins/roi_viewer/
├── plugin.json                  # enable-startup, tên hiện trong menu Plugins
├── main.py                      # load()/unload(), subscribe pubsub cấp cao (project load/close, mask events...)
├── gui/
│   ├── roi_panel.py             # ROIViewerFrame — cửa sổ chính, sở hữu các manager dùng chung
│   ├── segmentation_panel.py    # Threshold, Region Growing, ROI List, Brush (remote), Undo/Redo, Update Surface
│   ├── interaction_panel.py     # Pick 3D, sync 2D-3D
│   ├── measurement_panel.py     # Đo khoảng cách 3D (thật) + 2D/diện tích (remote công cụ gốc)
│   ├── annotation_panel.py      # Ghi chú gắn toạ độ
│   └── export_panel.py          # Xuất mask/surface/ảnh
├── core/                        # Logic thuần Python, KHÔNG phụ thuộc wx/InVesalius (unit-test được)
│   ├── roi_manager.py           # ROIManager/ROI — quản lý danh sách ROI theo tên/màu/hiển thị
│   ├── picker_3d.py             # PointPicker3D — bọc vtkCellPicker thật
│   ├── sync_2d3d.py             # SyncManager2D3D — quy đổi voxel↔world (đã verify đúng trục)
│   ├── segmentation.py          # SegmentationManager — threshold, Otsu, REGION GROWING (vector hoá), watershed helper, morphology
│   ├── mask_editor.py           # UndoRedoManager — snapshot ma trận mask cho Undo/Redo
│   ├── measurement.py           # MeasurementManager — tính khoảng cách/diện tích/thể tích theo spacing thật
│   ├── annotation.py            # AnnotationManager
│   └── exporters.py             # Ghi file STL/PLY/OBJ/VTK/NIfTI/PNG bằng VTK/nibabel/PIL
└── interface/                   # Lớp cầu nối duy nhất được phép chạm vào invesalius.* trực tiếp
    ├── project_interface.py     # ProjectInterface (singleton) — đọc Project()/Slice() thật
    └── view_interface.py        # ViewInterface (singleton) — tìm Viewer 3D thật qua widget tree, gửi pubsub điều hướng
```

**Nguyên tắc kiến trúc đã tuân thủ** (đúng yêu cầu "không phá kiến trúc pubsub"):
- `core/*.py` **không import `invesalius.*` hay `wx`** — thuần logic, unit-test được độc lập.
- `gui/*.py` chỉ gọi vào InVesalius thật qua `invesalius.pubsub.pub` (đúng topic/đúng chữ ký đã verify), **không bao giờ gọi trực tiếp method của module khác** (vd. không tự viết code brush riêng — kích hoạt đúng `SLICE_STATE_EDITOR` có sẵn).
- `interface/*.py` là nơi DUY NHẤT phép `import invesalius.project`, `import invesalius.data.slice_` trực tiếp để ĐỌC state — mọi thay đổi state vẫn đi qua pubsub.

### 3.1 Cơ chế "remote-control" (điểm thiết kế cốt lõi)

Thay vì viết lại brush/đo lường/watershed, plugin **kích hoạt đúng interactor style thật** của InVesalius qua `"Enable style"`/`"Disable style"`:

| Tính năng | Style kích hoạt | File InVesalius gốc xử lý |
|---|---|---|
| Brush vẽ/xoá tay | `const.SLICE_STATE_EDITOR` | `invesalius/data/styles.py` (`EditorInteractorStyle`) |
| Đo khoảng cách 2D | `const.STATE_MEASURE_DISTANCE` | `invesalius/data/styles.py`, `invesalius/data/measures.py` |
| Đo diện tích/density polygon | `const.STATE_MEASURE_DENSITY_POLYGON` | `invesalius/data/styles.py` |

Việc vẽ/đo bằng chuột vẫn diễn ra **trực tiếp trên canvas 2D thật của InVesalius** — plugin không chặn/giả lập sự kiện chuột, tránh xung đột với interactor style gốc.

---

## 4. Đồng bộ toạ độ 2D ↔ 3D (đã verify + sửa lỗi thật)

**Quy ước trục đã xác nhận qua code thật** (`invesalius/data/slice_.py`, phần swap-axis logic):
- `Slice.spacing` **index-aligned** với `Slice.matrix.shape`: trục 0 = AXIAL (số lát cắt), trục 1 = CORONAL, trục 2 = SAGITAL.
- VTK world coordinate theo quy ước chuẩn y khoa: world X = trục biến đổi nhanh nhất (SAGITAL, `matrix` trục 2), world Y = CORONAL (trục 1), world Z = AXIAL — trục lát cắt (trục 0).

→ `core/sync_2d3d.py` và `interface/project_interface.py` đã được sửa để **thống nhất** quy ước này (trước đó 2 file tự mâu thuẫn nhau, phát hiện qua test thật, xem `CT3D_CHANGELOG.md`).

**Giới hạn đã biết**: quy đổi chỉ dùng spacing (voxel size), **không hiệu chỉnh gantry-tilt/xoay** — đủ chính xác cho volume dựng thẳng trục (trường hợp phổ biến), nêu rõ như một giả định đã biết, không giấu.

---

## 5. File/module KHÔNG động vào (đúng nguyên tắc "không viết lại cái đang chạy tốt")

Các phần này InVesalius gốc đã hoạt động tốt và plugin **remote-control** thay vì viết lại: `invesalius/data/styles.py` (brush/watershed/measure interactor states), `invesalius/data/measures.py` (lưu trữ measurement gốc), `invesalius/data/volume.py` (raycasting preset — **không có điểm nối pubsub công khai để kích hoạt từ ngoài GUI**, ghi nhận là giới hạn, xem `CT3D_REMAINING_WORK.md`), toàn bộ `invesalius/reader/`, `invesalius/gui/frame.py`.
