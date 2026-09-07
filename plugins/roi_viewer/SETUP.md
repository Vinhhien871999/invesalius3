# ROI Viewer Plugin - Setup Guide

## Giới thiệu

ROI Viewer là plugin cho InVesalius 3, cung cấp các công cụ trực quan hóa 3D CT và chỉnh sửa ROI nâng cao.

## Yêu cầu hệ thống

- **Python**: 3.12
- **Hệ điều hành**: Windows 10/11, macOS, Linux
- **RAM**: Tối thiểu 8GB (khuyến nghị 16GB)
- **GPU**: Hỗ trợ OpenGL (cho VTK)

## Cài đặt môi trường

### 1. Clone repository InVesalius

```bash
cd d:\Learns\DeAn
git clone https://github.com/invesalius/invesalius3.git
cd invesalius3
```

### 2. Cài đặt Python 3.12

Sử dụng conda hoặc pyenv:

```bash
# Sử dụng conda
conda create -n invesalius python=3.12
conda activate invesalius

# Hoặc sử dụng pyenv-win (Windows)
pyenv install 3.12
pyenv local 3.12
```

### 3. Cài đặt dependencies với uv

```bash
# Cài đặt uv nếu chưa có
pip install uv

# Cài đặt dependencies từ pyproject.toml
uv sync
```

### 4. Cài đặt với conda (thay thế)

```bash
# Sử dụng environment.yml
conda env create -f environment.yml
conda activate invesalius3
```

### 5. Cài đặt plugin ROI Viewer

Plugin đã được tạo sẵn trong `plugins/roi_viewer/`. Không cần cài đặt thêm.

## Chạy InVesalius

### Cách 1: Chạy trực tiếp

```bash
cd invesalius3
python app.py
```

### Cách 2: Sử dụng entry point

```bash
inv
```

### Cách 3: Development mode với auto-reload

```bash
python -m invesalius.app
```

## Kiểm tra cài đặt

### 1. Kiểm tra Python environment

```python
python -c "import sys; print(sys.version)"
# Output: 3.12.x
```

### 2. Kiểm tra các dependencies quan trọng

```python
python -c "
import numpy
import vtk
import wx
import scipy
import skimage
print('All dependencies OK')
"
```

### 3. Kiểm tra plugin system

```python
python -c "
from invesalius.plugins import PluginManager
pm = PluginManager()
pm.find_plugins()
print(f'Found {len(pm.plugins)} plugins')
"
```

## Cấu trúc Plugin

```
plugins/roi_viewer/
├── plugin.json           # Metadata
├── __init__.py
├── main.py              # Entry point
├── gui/
│   ├── roi_panel.py     # Main panel
│   ├── interaction_panel.py
│   ├── measurement_panel.py
│   ├── annotation_panel.py
│   └── export_panel.py
├── core/
│   ├── roi_manager.py
│   ├── picker_3d.py
│   ├── sync_2d3d.py
│   ├── segmentation.py
│   ├── mask_editor.py
│   ├── measurement.py
│   ├── annotation.py
│   └── exporters.py
└── utils/
    └── helpers.py
```

## Tài liệu tham khảo

- [InVesalius GitHub](https://github.com/invesalius/invesalius3)
- [VTK Documentation](https://vtk.org/documentation/)
- [wxPython](https://wxpython.org/)
- [scikit-image](https://scikit-image.org/)

## Troubleshooting

### Lỗi: "No module named 'vtk'"

```bash
pip install vtk==9.3.0
```

### Lỗi: "No module named 'wx'"

```bash
pip install wxpython==4.2.5
```

### Lỗi: "Permission denied" khi cài đặt

```bash
# Sử dụng conda thay vì pip
conda install vtk wxpython scipy scikit-image
```

### Lỗi: GUI không hiển thị đúng

Kiểm tra wxPython version:
```python
import wx
print(wx.version())
```

## Next Steps

Sau khi cài đặt thành công, xem:
- [docs/DE_TAI_NCKH_TONG_QUAN.md](DE_TAI_NCKH_TONG_QUAN.md) - Tài liệu tổng quan đề tài
- [Lộ trình phát triển](../Lộ%20trình%20phát%20triển.md) - Chi tiết các phase phát triển
