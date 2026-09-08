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

**Phát hiện thật (vòng 2), quan trọng — "lazy threshold sentinel" bẫy cả mask tạo qua ghi trực tiếp**: `Slice.do_threshold_to_all_slices()` (bên trong `CreateSurfaceFromIndex`, chạy MỖI LẦN build surface) duyệt từng lát cắt axial `n`; nếu `mask.matrix[n, 0, 0] == 0` ("chưa từng threshold"), nó **ghi đè** `mask.matrix[n, 1:, 1:]` bằng kết quả threshold MỚI từ ảnh gốc theo `mask.threshold_range`, bất kể trước đó đã có dữ liệu gì trong mask. Một mask tạo qua `"Create new mask"` với `thresh` chỉ là placeholder (như Region Growing dùng `thresh=(1,1)` rồi ghi trực tiếp `matrix[1:,1:,1:]`) có sentinel = 0 ở MỌI lát cắt — nghĩa là **lần build surface ĐẦU TIÊN sẽ âm thầm xoá/ghi đè toàn bộ dữ liệu tay đã ghi**, thay bằng kết quả threshold(1,1) vô nghĩa trên ảnh thật. Đã verify bằng `test_surface_update_small_roi.py` (mask test tự ghi cube, bị ghi đè y hệt). **Đã sửa** trong `segmentation_panel.py._on_region_grown()`: sau khi ghi dữ liệu region-growing thật vào mask, chủ động đặt `new_mask.matrix[1:, 0, 0] = 1` (đánh dấu "đã xử lý" cho mọi lát) để `do_threshold_to_all_slices` bỏ qua, không ghi đè. Đây là cách dùng ĐÚNG cơ chế thật của InVesalius (không sửa core), chỉ là gọi đúng "hợp đồng" (contract) của nó mà code cũ (kể cả vòng 1) chưa biết tới.

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
│   ├── roi_manager.py           # ROIManager/ROI — CACHE/VIEW theo `Project().mask_dict` thật (xem mục 4.1)
│   ├── picker_3d.py             # PointPicker3D — bọc vtkCellPicker thật
│   ├── sync_2d3d.py             # SyncManager2D3D — quy đổi voxel↔world (đã verify đúng trục, có test số liệu — mục 5)
│   ├── segmentation.py          # SegmentationManager — threshold, Otsu, REGION GROWING (vector hoá) + validate_seed/region_stats (an toàn — vòng 2)
│   ├── mask_editor.py           # UndoRedoManager — snapshot ma trận mask cho Undo/Redo
│   ├── measurement.py           # MeasurementManager — tính khoảng cách/diện tích/thể tích theo spacing thật
│   ├── annotation.py            # AnnotationManager + sidecar JSON persistence (xem mục 4.2)
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

## 4. ROIManager — cache/view, không phải nguồn dữ liệu thứ hai (vòng 2)

**Nguyên tắc**: `Project().mask_dict` (dữ liệu `Mask` thật — `name`/`colour`/`is_shown`/`index`, đã có sẵn cơ chế save/load riêng qua `Mask.SavePlist`/`OpenPList`) là **nguồn sự thật duy nhất**. `core/roi_manager.ROIManager` **không giữ bản sao độc lập** — mỗi `ROI` object chỉ mirror đúng 4 trường đó từ mask tương ứng.

`ROIManager.rebuild_from_project_masks()` (mới, vòng 2) resync toàn bộ cache từ `Project().mask_dict` thật — gọi khi:
- plugin mở / project load (`roi_panel.py.on_project_load()`),
- mask tạo/đổi tên/ẩn-hiện/xoá — **kể cả khi làm qua tab Masks gốc của InVesalius**, không chỉ qua nút của plugin (`main.py` subscribe thêm `"Change mask name"`, `"Show mask"`, `"Remove masks"` — xem `CT3D_TEST_REPORT.md`, `test_roi_rebuild_after_project_load.py`).

**Trước vòng 2**: `ROI` object tự giữ `name`/`color`/`visible` riêng, đồng bộ 1 chiều (plugin → mask) mỗi khi bấm nút — nếu sửa mask qua tab Masks gốc thì ROI List không biết. Cũng có `points`/`bounds`/`locked`/`annotations` + `add_point()`/`contains_point()`/`get_center()`/`get_dimensions()`/`find_roi_at_point()` — **0 lời gọi ở bất kỳ đâu trong toàn bộ plugin** (grep xác nhận) — đã xoá vì là dead code thật, không phải "có thể dùng sau".

**Hệ quả cho Save/Open**: không cần serialize `ROIManager` riêng — `rebuild_from_project_masks()` sau khi mở lại project tái tạo đúng ROI List từ mask thật đã được InVesalius gốc lưu/load sẵn (verify: `test_project_roundtrip.py`, `test_roi_rebuild_after_project_load.py`).

---

## 5. Annotation — persistence qua sidecar JSON (vòng 2)

**Điều tra trước khi chọn giải pháp** (đúng thứ tự ưu tiên yêu cầu): đọc `invesalius/project.py` (`SavePlistProject`/`load_from_folder`) — phát hiện `project["annotations"] = {}` được ghi **cứng, luôn rỗng** khi save, và **không có bất kỳ code nào đọc lại** key này khi load (`load_from_folder` không có dòng nào tham chiếu `project["annotations"]` ngoài lúc save). Đây là placeholder chưa từng hoàn thiện trong CHÍNH InVesalius gốc, không phải cơ chế extension thật sự dùng được. Grep toàn bộ `invesalius/project.py` + `invesalius/control.py` cho `plugin`/`custom_data`/`extension`: **0 kết quả** — không có cơ chế plugin-persistence chính thức nào.

→ Theo đúng thứ tự ưu tiên (1. tái dùng object đã serialize — không có; 2. extension point chính thức — tồn tại dạng key nhưng hoàn toàn không hoạt động, dùng nó nghĩa là phải viết THÊM code load mới vào core; 3. plugin persistence riêng — không tồn tại; 4. sidecar file): chọn **sidecar JSON** (`<đường dẫn .inv3>.roi_annotations.json`, cùng thư mục), không sửa `invesalius/project.py`.

**Cơ chế** (`core/annotation.py.AnnotationManager.save_sidecar()`/`.load_sidecar()`):
- **Save**: `export_panel.py._on_save_project`/`_on_save_as_project`, ngay sau khi `Publisher.sendMessage("Show save dialog", ...)` trả về (topic này xử lý ĐỒNG BỘ — dialog thật + `SaveProject()` thật + `Session().SetState("project_path", ...)` đều chạy xong trước khi `sendMessage()` return — verify qua đọc code `Controller.OnShowDialogSaveProject`/`ShowDialogSaveProject`), đọc `Session().GetState("project_path")` rồi ghi sidecar.
- **Load**: `roi_panel.py.on_project_load()`, qua `wx.CallAfter` (bắt buộc — "Load project data" bắn ra TỪ BÊN TRONG `Controller.OpenProject()`, TRƯỚC dòng `session.OpenProject(path)` cập nhật `project_path` — đọc đồng bộ ngay lúc đó sẽ ra đường dẫn project CŨ; `CallAfter` chạy sau khi `OpenProject()` đã return hoàn toàn).

Verify thật: `test_project_roundtrip.py` (add annotation → save → close → open → so annotation text/count khớp baseline).

---

## 6. Đồng bộ toạ độ 2D ↔ 3D (đã verify + sửa lỗi thật)

**Quy ước trục đã xác nhận qua code thật** (`invesalius/data/slice_.py`, phần swap-axis logic):
- `Slice.spacing` **index-aligned** với `Slice.matrix.shape`: trục 0 = AXIAL (số lát cắt), trục 1 = CORONAL, trục 2 = SAGITAL.
- VTK world coordinate theo quy ước chuẩn y khoa: world X = trục biến đổi nhanh nhất (SAGITAL, `matrix` trục 2), world Y = CORONAL (trục 1), world Z = AXIAL — trục lát cắt (trục 0).

→ `core/sync_2d3d.py` và `interface/project_interface.py` đã được sửa để **thống nhất** quy ước này (trước đó 2 file tự mâu thuẫn nhau, phát hiện qua test thật, xem `CT3D_CHANGELOG.md`).

**Giới hạn đã biết**: quy đổi chỉ dùng spacing (voxel size), **không hiệu chỉnh gantry-tilt/xoay** — đủ chính xác cho volume dựng thẳng trục (trường hợp phổ biến), nêu rõ như một giả định đã biết, không giấu. **Vòng 2**: verify bằng số liệu thật (không chỉ "trông hợp lý") — xem `CT3D_TEST_REPORT.md`, `test_coordinate_roundtrip.py` (11/11 check, sai số spacing < 0.05mm so với tag DICOM thật, round-trip voxel↔world khớp tuyệt đối tại origin/center/near-end).

---

## 7. File/module KHÔNG động vào (đúng nguyên tắc "không viết lại cái đang chạy tốt")

Các phần này InVesalius gốc đã hoạt động tốt và plugin **remote-control** thay vì viết lại: `invesalius/data/styles.py` (brush/watershed/measure interactor states), `invesalius/data/measures.py` (lưu trữ measurement gốc), `invesalius/data/volume.py` (raycasting preset — **không có điểm nối pubsub công khai để kích hoạt từ ngoài GUI**, ghi nhận là giới hạn, xem `CT3D_REMAINING_WORK.md`), toàn bộ `invesalius/reader/`, `invesalius/gui/frame.py`.

**Vòng 2**: đã xoá `core/segmentation.py.watershed()`/`_simple_watershed()` (custom, trùng lặp `SLICE_STATE_WATERSHED` thật của InVesalius gốc, 0 call-site, 0 test — không phải đóng góp nghiên cứu) và `morphological_op()`/`remove_small_objects()`/`fill_holes()` (0 call-site, không nằm trong phạm vi tài liệu kế hoạch) — xem `CT3D_CHANGELOG.md`. Cũng xoá `interface/task_panel.py` (UI trùng lặp với `roi_panel.py`, 0 call-site) và toàn bộ `utils/` (implementation `world_to_voxel` thứ 3, SAI quy ước trục so với 2 bản thật đã verify, 0 call-site).
