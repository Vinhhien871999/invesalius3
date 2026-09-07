# Tài liệu Tổng quan - Đề tài NCKH
# Nghiên cứu và xây dựng phần mềm hỗ trợ trực quan hóa và thao tác ảnh CT 3D
# Tập trung vào chỉnh sửa vùng quan tâm (ROI)

## 1. Tổng quan về InVesalius

### 1.1 Giới thiệu
- **Tên**: InVesalius
- **Nhà phát triển**: CTI Brazil (Centro de Pesquisas Renato Archer)
- **License**: GNU GPL 2
- **Ngôn ngữ**: Python 3.12
- **Repository**: https://github.com/invesalius/invesalius3

### 1.2 Công nghệ sử dụng
| Thành phần | Công nghệ |
|------------|-----------|
| GUI Framework | wxPython 4.2.5 |
| Visualization | VTK 9.3.0 |
| DICOM | GDCM 3.0.24, pydicom |
| Image Processing | scikit-image 0.24, scipy 1.14, numpy 1.26 |
| Deep Learning | PyTorch 2.3+, ONNX Runtime 1.23 |
| Build System | maturin (Rust), uv |
| Testing | pytest |

### 1.3 Cấu trúc thư mục
```
invesalius3/
├── invesalius/                    # Core package
│   ├── reader/                    # DICOM, bitmap readers
│   │   ├── dicom_reader.py        # Đọc file DICOM
│   │   ├── dicom_grouper.py       # Nhóm series
│   │   └── bitmap_reader.py       # Đọc bitmap
│   ├── gui/                       # GUI components
│   │   ├── frame.py               # Main frame (115KB)
│   │   ├── dialogs.py             # Dialogs (304KB)
│   │   ├── task_slice.py          # Slice viewer
│   │   ├── task_surface.py        # Surface creation
│   │   └── widgets/               # Custom widgets
│   │       ├── canvas_renderer.py # 2D canvas
│   │       ├── gradient.py         # Window/Level
│   │       └── clut_raycasting.py # Volume rendering
│   ├── segmentation/              # Segmentation algorithms
│   │   └── deep_learning/        # AI segmentation
│   ├── data/                      # Data management
│   ├── navigation/                # Neuronavigation
│   └── plugins.py                 # Plugin system
├── plugins/                        # Plugin directory
│   ├── mask_morphology/          # Plugin mẫu
│   └── ...
├── app.py                         # Entry point
└── pyproject.toml                 # Project config
```

---

## 2. Kiến trúc hệ thống

### 2.1 Mô hình kiến trúc

```
┌─────────────────────────────────────────────────────────────┐
│                      wxPython GUI                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐│
│  │ Main Frame  │  │  Dialogs    │  │  Task Panels        ││
│  │ (frame.py)  │  │ (dialogs.py)│  │ (task_*.py)        ││
│  └─────────────┘  └─────────────┘  └─────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                    Publisher/Subscriber Pattern
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Controller (control.py)               │
│  - Quản lý project lifecycle                               │
│  - Xử lý events từ GUI                                     │
│  - Điều phối các module khác                               │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Reader Module   │  │  Slice Module   │  │  Surface Module │
│ (dicom_reader) │  │  (data/slice_)  │  │ (data/surface)  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  VTK Pipeline   │
                    │  - 2D Rendering │
                    │  - 3D Volume    │
                    │  - Surface      │
                    └─────────────────┘
```

### 2.2 PubSub Pattern (Event Bus)
InVesalius sử dụng `pypubsub` cho communication giữa các components:

```python
from invesalius.pubsub import pub as Publisher

# Subscribe
Publisher.subscribe(self.handler, "Topic name")

# Publish
Publisher.sendMessage("Topic name", arg1=value1, arg2=value2)
```

### 2.3 Các PubSub topics quan trọng

#### DICOM Import
- `Import directory` - Import folder DICOM
- `Open DICOM group` - Mở một series
- `Load dicom preview` - Hiển thị preview

#### Visualization
- `Load slice to viewer` - Load slice data
- `Set scroll position` - Di chuyển slice
- `Bright and contrast adjustment` - Window/Level
- `Render volume viewer` - Render lại 3D view

#### Segmentation
- `Create new mask` - Tạo mask mới
- `Add mask` - Thêm mask vào project
- `Update mask` - Cập nhật mask
- `Create surface from index` - Tạo surface từ mask

#### Project
- `Save project` / `Open project` - Lưu/Mở project
- `Close Project` - Đóng project

---

## 3. Các Module chính

### 3.1 Reader Module (`invesalius/reader/`)

#### dicom_reader.py
- Class chính: `LoadDicom`
- Chức năng: Đọc và parse file DICOM
- Sử dụng GDCM library
- Trích xuất: patient info, series info, image data, spacing, orientation

#### dicom_grouper.py
- Class chính: `DicomGrouper`, `DicomGroup`
- Chức năng: Nhóm các file DICOM theo patient/series
- Hỗ trợ: ACR-NEMA, DICOM 3.0, JPEG, RLE

### 3.2 GUI Module (`invesalius/gui/`)

#### frame.py (115KB)
- Class chính: `Frame`
- Quản lý: Menu, toolbar, AUI panels
- Layout: Notebook với 3 view (Axial/Coronal/Sagittal) + 3D

#### task_slice.py (51KB)
- Class chính: `SliceTaskPanel`
- Chức năng: Tạo và quản lý slice view
- Toolbar: Zoom, pan, scroll, measure

#### task_surface.py (25KB)
- Class chính: `TaskPanel`
- Chức năng: Tạo 3D surface từ mask
- Options: Quality, decimation, smoothing

#### dialogs.py (304KB)
- Dialog chính:
  - `ImportDirDialog` - Import DICOM folder
  - `SurfaceCreationDialog` - Tạo surface
  - `ThresholdDialog` - Threshold settings

### 3.3 Widgets Module (`invesalius/gui/widgets/`)

#### canvas_renderer.py (49KB)
- Class chính: `SLCanvas`
- Canvas 2D cho hiển thị slice
- Tích hợp VTK cho rendering
- Hỗ trợ: Pan, zoom, draw mask

#### gradient.py (31KB)
- Class chính: `GradientWindow`
- Control Window/Level
- Preview gradient bar

#### clut_raycasting.py (29KB)
- Class chính: `CLNTringCast`
- Volume rendering với ray casting
- Presets cho different tissues

---

## 4. Plugin System

### 4.1 Cấu trúc Plugin
```
plugins/
└── <plugin_name>/
    ├── plugin.json          # Metadata
    ├── __init__.py
    ├── main.py              # Entry point
    ├── gui.py              # GUI (optional)
    └── ...
```

### 4.2 Plugin.json format
```json
{
    "name": "Plugin Name",
    "description": "Description text",
    "enable-startup": false
}
```

### 4.3 main.py template
```python
import wx

def load():
    top_window = wx.GetApp().GetTopWindow()
    window = gui.PluginGUI(top_window)
    window.Show()

def get_plugin_info():
    return {
        "name": "Plugin Name",
        "description": "...",
        "version": "1.0.0",
        "author": "...",
        "contact": "..."
    }
```

### 4.4 Ví dụ: mask_morphology plugin
- Location: `plugins/mask_morphology/`
- Chức năng: Erosion/dilation trên mask
- GUI: Dialog với parameters

---

## 5. Điểm mới của đề tài

### 5.1 Các tính năng đã có trong InVesalius (tái sử dụng)
1. Đọc DICOM - Module `reader/dicom_reader.py`
2. Quản lý series - Module `reader/dicom_grouper.py`
3. Hiển thị 3 view 2D - `task_slice.py` + `canvas_renderer.py`
4. Volume rendering 3D - `clut_raycasting.py`
5. Window/Level - `widgets/gradient.py`
6. Segmentation cơ bản - Threshold, region growing
7. Tạo surface từ mask - `task_surface.py`
8. Lưu project (.inv3) - `project.py`

### 5.2 Các tính năng phát triển mới (plugin roi_viewer)

#### A. Tương tác 2D-3D
- **F6**: Click trên 3D -> sync cursor 2D
- **F7**: Brush trên 2D -> cập nhật 3D real-time

#### B. ROI/Mask Editing
- **F8**: Segmentation enhanced (threshold + region growing + watershed)
- **F9**: Brush/Eraser tool, undo/redo, interpolation

#### C. Đo lường
- **F10**: Đo khoảng cách 3D
- **F11**: Đo diện tích/thể tích

#### D. Annotation
- **F12**: Gắn nhãn, text note, color tags

#### E. Export
- **F13**: Lưu mask (.nii.gz, .nrrd)
- **F14**: Xuất surface (.stl, .ply, .obj)

---

## 6. Cấu trúc Plugin ROI Viewer (đề xuất)

```
invesalius3/plugins/roi_viewer/
├── plugin.json
├── __init__.py
├── main.py
├── gui/
│   ├── __init__.py
│   ├── roi_panel.py           # Panel chính cho ROI
│   ├── interaction_panel.py   # Tools tương tác
│   ├── measurement_panel.py   # Tools đo lường
│   ├── annotation_panel.py    # Annotation
│   └── export_panel.py        # Export options
├── core/
│   ├── __init__.py
│   ├── roi_manager.py         # Quản lý ROI
│   ├── picker_3d.py           # 3D point picking
│   ├── sync_2d3d.py           # 2D-3D synchronization
│   ├── segmentation.py        # Segmentation algorithms
│   ├── mask_editor.py         # Mask editing
│   ├── measurement.py         # Measurements
│   ├── annotation.py          # Annotations
│   └── exporters.py           # Export functions
└── utils/
    ├── __init__.py
    └── helpers.py
```

---

## 7. Key Implementation Notes

### 7.1 Pubsub Topics cần subscribe
```python
# 2D-3D interaction
Publisher.subscribe(self.OnSliceChange, "Set scroll position")
Publisher.subscribe(self.OnMaskUpdate, "Reload actual slice")
Publisher.subscribe(self.OnPointPicked3D, "Point picked in 3D")

# Project events
Publisher.subscribe(self.OnProjectLoad, "Load project data")
Publisher.subscribe(self.OnProjectClose, "Close project data")

# Mask events
Publisher.subscribe(self.OnMaskCreated, "Create new mask")
Publisher.subscribe(self.OnMaskSelected, "Change mask selected")
```

### 7.2 VTK Integration
- Sử dụng `vtkRenderWindowInteractor` cho 3D
- Pick function: `vtkCellPicker` hoặc `vtkPointPicker`
- Callback: `AddObserver(vtkCommand::PickEvent, callback)`

### 7.3 Data Flow
```
User Action (2D/3D)
    │
    ▼
Widget Event Handler
    │
    ▼
Update Slice/Mask Data
    │
    ├──► Publisher.sendMessage("Reload actual slice")
    │
    └──► Publisher.sendMessage("Render volume viewer")
```

---

## 8. Tham khảo

1. InVesalius GitHub: https://github.com/invesalius/invesalius3
2. DICOM Standard: https://dicom.nema.org/
3. VTK Documentation: https://vtk.org/documentation/
4. wxPython: https://wxpython.org/
5. scikit-image: https://scikit-image.org/
