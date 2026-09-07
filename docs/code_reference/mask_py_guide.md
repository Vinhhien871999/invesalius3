# Hướng dẫn tham khảo code: `invesalius/data/mask.py`

> File nguồn: `invesalius/data/mask.py` (578 dòng)
> Tác giả gốc: Centro de Pesquisas Renato Archer
> License: GNU GPL 2

## Mục lục

1. [Tổng quan](#1-tổng-quan)
2. [Lớp EditionHistoryNode](#2-lớp-editionhistorynode)
3. [Lớp EditionHistory](#3-lớp-editionhistory)
4. [Lớp Mask](#4-lớp-mask)
5. [Mask Encoding](#5-mask-encoding)
6. [Padding +1 và Dirty Flags](#6-padding-1-và-dirty-flags)
7. [Tương tác với hệ thống khác](#7-tương-tác-với-hệ-thống-khác)
8. [Ví dụ sử dụng](#8-ví-dụ-sử-dụng)

---

## 1. Tổng quan

File `mask.py` chứa hệ thống **Mask/ROI (Region of Interest)** — lớp trung tâm cho segmentation trong InVesalius. Nó cung cấp:

- **Lưu trữ mask**: numpy memmap 3D với semantic encoding (uint8)
- **Undo/Redo**: hệ thống snapshot-based với file tạm
- **Chỉnh sửa**: brush, fill holes, threshold
- **Preview 3D**: tích hợp với VolumeMask để hiển thị ray-cast
- **Persistence**: lưu/đọc mask qua plist + binary data

### Vị trí trong kiến trúc

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   GUI       │────▶│   Slice_     │────▶│   Mask      │
│  (wxPython) │     │   (Slice)    │     │  (data)     │
└─────────────┘     └──────────────┘     └─────────────┘
                           │                    │
                           │              ┌─────┴─────┐
                           │              │           │
                     ┌─────┴─────┐  ┌─────┴────┐ ┌───┴───┐
                     │ PubSub    │  │VolumeMask│ │Rust   │
                     │ (events)  │  │(preview) │ │ext    │
                     └───────────┘  └──────────┘ └───────┘
```

---

## 2. Lớp EditionHistoryNode

**Vị trí**: Dòng 40-76

Mỗi node lưu trữ một snapshot trạng thái mask tại một thời điểm, dùng cho hệ thống undo/redo.

### 2.1 Thuộc tính

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `index` | int | Chỉ số slice (0-based) |
| `orientation` | str | "AXIAL", "CORONAL", "SAGITAL", "VOLUME" |
| `fd` | int | File descriptor từ mkstemp |
| `filename` | str | Đường dẫn file .npy tạm |
| `clean` | bool | Flag đánh dấu thao tác đã clean |

### 2.2 Phương thức

#### `__init__(self, index, orientation, array, clean=False)`

```python
def __init__(self, index, orientation, array, clean=False):
    self.index = index
    self.orientation = orientation
    self.fd, self.filename = tempfile.mkstemp(suffix=".npy")
    self.clean = clean
    self._save_array(array)
```

- Tạo file tạm `.npy` để lưu trạng thái numpy array
- Lưu trạng thái vào file qua `_save_array()`

#### `_save_array(self, array)`

```python
def _save_array(self, array):
    np.save(self.filename, array)
    print("Saving history", self.index, self.orientation, ...)
```

- Lưu numpy array ra file `.npy` bằng `np.save()`
- Dùng file tạm thay vì RAM để hỗ trợ history dài

#### `commit_history(self, mvolume)`

Áp trạng thái từ file `.npy` vào mask volume chính:

```python
def commit_history(self, mvolume):
    array = np.load(self.filename)
    if self.orientation == "AXIAL":
        mvolume[self.index + 1, 1:, 1:] = array
        if self.clean:
            mvolume[self.index + 1, 0, 0] = 1
    elif self.orientation == "CORONAL":
        mvolume[1:, self.index + 1, 1:] = array
        if self.clean:
            mvolume[0, self.index + 1, 0] = 1
    elif self.orientation == "SAGITAL":
        mvolume[1:, 1:, self.index + 1] = array
        if self.clean:
            mvolume[0, 0, self.index + 1] = 1
    elif self.orientation == "VOLUME":
        mvolume[:] = array
```

**Lưu ý**: 
- Offset `+1` do padding +1 voxel mỗi chiều
- Khi `clean=True`, đánh dấu dirty flag ở boundary voxel

#### `__del__(self)`

```python
def __del__(self):
    os.close(self.fd)
    os.remove(self.filename)
```

Dọn file tạm khi node bị garbage collected.

---

## 3. Lớp EditionHistory

**Vị trí**: Dòng 78-203

Quản lý stack undo/redo với cơ chế snapshot-to-disk.

### 3.1 Thuộc tính

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `history` | list | Stack các EditionHistoryNode |
| `index` | int | Vị trí hiện tại trong history (-1 = chưa có gì) |
| `size` | int | Kích thước tối đa (mặc định 100) |

### 3.2 Phương thức chính

#### `new_node(self, index, orientation, array, p_array, clean)`

Tạo 2 node cho mỗi thao tác chỉnh sửa:

```python
def new_node(self, index, orientation, array, p_array, clean):
    # Node cho trạng thái TRƯỚC (dùng khi undo)
    p_node = EditionHistoryNode(index, orientation, p_array, clean)
    self.add(p_node)
    
    # Node cho trạng thái SAU (dùng khi redo)
    node = EditionHistoryNode(index, orientation, array, clean)
    self.add(node)
```

#### `add(self, node)`

Thêm node vào history:

```python
def add(self, node):
    # Xóa phần tử đầu tiên nếu đầy
    if self.index == self.size:
        self.history.pop(0)
        self.index -= 1
    
    # Cắt bỏ phần phía sau nếu đang ở giữa history
    if self.index < len(self.history):
        self.history = self.history[: self.index + 1]
    
    self.history.append(node)
    self.index += 1
    
    Publisher.sendMessage("Enable undo", value=True)
    Publisher.sendMessage("Enable redo", value=False)
```

#### `undo(self, mvolume, actual_slices=None)` / `redo(self, mvolume, actual_slices=None)`

Logic phức tạp với nhiều nhánh xử lý:

1. **VOLUME**: Undo/redo 1 bước đơn giản
2. **Slice không liên quan**: Chỉ reload slice, không commit
3. **Slice hiện tại**: Commit 1 hoặc 2 lần tùy trường hợp

**Nguyên nhân logic phức tạp**: Khi undo/redo trên slice hiện tại, cần commit trạng thái trước rồi reload để UI cập nhật đúng.

#### `_reload_slice(self, index)`

Gửi message PubSub để reload slice về đúng vị trí:

```python
def _reload_slice(self, index):
    Publisher.sendMessage(
        ("Set scroll position", self.history[index].orientation),
        index=self.history[index].index,
    )
```

---

## 4. Lớp Mask

**Vị trí**: Dòng 206-578

Class chính đại diện cho một mask/ROI.

### 4.1 Thuộc tính chính

| Thuộc tính | Kiểu | Mô tả | Giá trị mặc định |
|------------|------|-------|------------------|
| `matrix` | np.memmap | Dữ liệu mask 3D (uint8) | None |
| `spacing` | tuple | Khoảng cách voxel (dz, dy, dx) mm | (1.0, 1.0, 1.0) |
| `colour` | tuple | Màu RGB | random.choice(const.MASK_COLOUR) |
| `opacity` | float | Độ trong suốt | const.MASK_OPACITY |
| `threshold_range` | list | Ngưỡng HU [min, max] | const.THRESHOLD_RANGE |
| `edition_threshold_range` | list | [out_value, in_value] cho brush | [THRESHOLD_OUTVALUE, THRESHOLD_INVALUE] |
| `volume` | VolumeMask | Preview 3D | None |
| `history` | EditionHistory | Stack undo/redo | EditionHistory() |
| `index` | int | ID của mask | auto-increment |
| `name` | str | Tên hiển thị | "Mask %d" |
| `is_shown` | bool | Hiển thị/ẩn | 1 |
| `was_edited` | bool | Đã chỉnh sửa thủ công | False |
| `modified_time` | float | Thời gian chỉnh sửa cuối | 0 |
| `auto_update_mask` | bool | Tự động cập nhật preview | True |

### 4.2 Phương thức khởi tạo

#### `create_mask(self, shape)`

Tạo mask mới với numpy memmap:

```python
def create_mask(self, shape):
    self.temp_fd, self.temp_file = tempfile.mkstemp()
    # Shape thực = shape + 1 (padding mỗi chiều)
    shape = shape[0] + 1, shape[1] + 1, shape[2] + 1
    self.matrix = np.memmap(self.temp_file, mode="w+", dtype="uint8", shape=shape)
```

**Quan trọng**: Shape lưu trữ = (dz+1, dy+1, dx+1) với 1 voxel padding mỗi chiều.

### 4.3 Phương thức persistence

#### `SavePlist(self, dir_temp, filelist, save_temp_files=None)`

Lưu mask ra file:

```python
def SavePlist(self, dir_temp, filelist, save_temp_files=None):
    mask = {}
    filename = f"mask_{self.index}"
    mask_filename = f"{filename}.dat"
    
    # Map file tạm vào archive
    filelist[self.temp_file] = mask_filename
    
    mask["index"] = self.index
    mask["name"] = self.name
    mask["colour"] = self.colour[:3]
    mask["opacity"] = self.opacity
    mask["threshold_range"] = self.threshold_range
    mask["edition_threshold_range"] = self.edition_threshold_range
    mask["visible"] = self.is_shown
    mask["mask_file"] = mask_filename
    mask["mask_shape"] = self.matrix.shape
    mask["edited"] = self.was_edited
    mask["derived_from"] = self.derived_from
    
    # Lưu plist
    plist_filename = filename + ".plist"
    ...
    return plist_filename
```

#### `OpenPList(self, filename)`

Đọc mask từ file plist:

```python
def OpenPList(self, filename):
    with open(filename, "r+b") as f:
        mask = plistlib.load(f, fmt=plistlib.FMT_XML)
    
    self.index = mask["index"]
    self.name = mask["name"]
    # ... các thuộc tính khác ...
    
    # Đọc binary data thành memmap
    self._open_mask(path, tuple(shape))
```

### 4.4 Phương thức chỉnh sửa

#### `modified(self, all_volume=False)`

Callback pattern khi mask thay đổi:

```python
def modified(self, all_volume=False):
    # Đánh dấu dirty flags ở boundary
    if all_volume:
        self.matrix[0] = 1
        self.matrix[:, 0, :] = 1
        self.matrix[:, :, 0] = 1
    
    # Cập nhật VTK preview nếu cần
    if session.GetConfig("auto_reload_preview"):
        self._update_imagedata()
    
    # Gọi callbacks
    for callback in self._modified_callbacks:
        if callback() is not None:
            callback()()
```

#### `add_modified_callback(self, callback)` / `remove_modified_callback(self, callback)`

Đăng ký/hủy callback khi mask thay đổi:

```python
def add_modified_callback(self, callback):
    ref = weakref.WeakMethod(callback)
    self._modified_callbacks.append(ref)

def remove_modified_callback(self, callback):
    # So sánh bằng weakref
    for cb in self._modified_callbacks:
        if cb() == callback:
            # remove
            pass
```

**Lưu ý**: Dùng `weakref.WeakMethod` để tránh circular reference và memory leak.

### 4.5 Phương thức segmentation

#### `fill_holes_auto(self, target, conn, orientation, index, size)`

Thuật toán fill holes tự động (gọi Rust extension):

```python
def fill_holes_auto(self, target, conn, orientation, index, size):
    CON2D = {4: 1, 8: 2}      # 4-connectivity, 8-connectivity
    CON3D = {6: 1, 18: 2, 26: 3}  # 6, 18, 26-connectivity
    
    if target == "3D":
        # Fill holes 3D trong toàn bộ volume
        matrix = self.matrix[1:, 1:, 1:]
        imask = ~(matrix > 127)  # Đảo ngược: holes = True
        labels, nlabels = ndimage.label(imask, bstruct, output=np.uint32)
        labels = np.asarray(labels, dtype=np.uint32, order="C")
        ret = floodfill.fill_holes_automatically(matrix, labels, nlabels, size)
        if ret:
            self.save_history(index, orientation, self.matrix.copy(), cp_mask)
    else:
        # Fill holes 2D trên slice cụ thể
        ...
```

**Tham số**:
- `target`: "2D" hoặc "3D"
- `conn`: Connectivity (2D: 4 hoặc 8; 3D: 6, 18 hoặc 26)
- `orientation`: "AXIAL", "CORONAL", "SAGITAL"
- `index`: Chỉ số slice (cho 2D)
- `size`: Kích thước tối đa của hole cần fill

### 4.6 Các phương thức khác

#### `as_vtkimagedata(self)`

Chuyển numpy array sang VTK ImageData:

```python
def as_vtkimagedata(self):
    vimg = converters.to_vtk_mask(self.matrix, self.spacing)
    return vimg
```

#### `create_3d_preview(self)`

Tạo preview 3D từ mask:

```python
def create_3d_preview(self):
    if self.volume is None:
        if self.imagedata is None:
            self.imagedata = self.as_vtkimagedata()
        self.volume = VolumeMask(self)
        self.volume.create_volume()
```

#### `copy(self, copy_name)`

Tạo bản copy của mask:

```python
def copy(self, copy_name):
    new_mask = Mask()
    new_mask.name = copy_name
    new_mask.colour = self.colour
    # ... copy các thuộc tính ...
    new_mask.create_mask(shape=[i - 1 for i in self.matrix.shape])
    new_mask.matrix[:] = self.matrix[:]
    return new_mask
```

#### `clean(self)`

Reset mask về 0:

```python
def clean(self):
    self.matrix[1:, 1:, 1:] = 0
    self.modified(all_volume=True)
```

#### `on_show(self)`

Xử lý khi mask được hiển thị/ẩn:

```python
def on_show(self):
    self.history._config_undo_redo(self.is_shown)
    if session.mask_3d_preview:
        Publisher.sendMessage("Show mask preview", index=self.index, flag=bool(self.is_shown))
```

---

## 5. Mask Encoding

Trong InVesalius, giá trị `uint8` trong mask mang **ngữ nghĩa đa lớp**:

| Giá trị | Ký hiệu | Mô tả |
|---------|---------|-------|
| `0` | BG | Background (không thuộc ROI) |
| `1` | MF | Manual / Floodfill (vẽ tay / region growing) |
| `2` | WS | Watershed (phân đoạn watershed) |
| `253` | TM | Threshold marker (marker cho watershed) |
| `254` | MF2 | Manual Fill (điền thủ công) |
| `255` | TH | Threshold (ngưỡng) |

### Mã nguồn tham khảo

```python
# invesalius/constants.py
THRESHOLD_OUTVALUE = 253
THRESHOLD_INVALUE = 255
# Mask values
MASK_EDGE_VALUE = 1
MASK_FLOODFILL = 1
MASK_THRESHOLD = 255
MASK_ERASE = 0
```

---

## 6. Padding +1 và Dirty Flags

### Tại sao có padding +1?

Mask matrix được lưu với shape `(dz+1, dy+1, dx+1)` thay vì `(dz, dy, dx)` để:

1. **Dirty flags**: Đánh dấu slice nào đã được chỉnh sửa
   - `matrix[index+1, 0, 0]` cho AXIAL
   - `matrix[0, index+1, 0]` cho CORONAL  
   - `matrix[0, 0, index+1]` cho SAGITAL

2. **Lazy evaluation**: VTK và các module khác có thể kiểm tra dirty flags để quyết định có cập nhật hay không

### Boundary voxels

```python
# Đánh dấu tất cả boundary là dirty
self.matrix[0] = 1           # z=0 plane
self.matrix[:, 0, :] = 1     # y=0 plane  
self.matrix[:, :, 0] = 1     # x=0 plane
```

---

## 7. Tương tác với hệ thống khác

### 7.1 PubSub (Event Bus)

```python
# Đăng ký events
Publisher.subscribe(self.OnFlipVolume, "Flip volume")
Publisher.subscribe(self.OnSwapVolumeAxes, "Swap volume axes")

# Gửi events
Publisher.sendMessage("Enable undo", value=True)
Publisher.sendMessage("Enable redo", value=False)
Publisher.sendMessage("Show mask preview", index=self.index, flag=bool(self.is_shown))
Publisher.sendMessage("Render volume viewer")
```

### 7.2 VolumeMask (Preview 3D)

```python
from invesalius.data.volume_mask import VolumeMask

# Tạo preview
self.volume = VolumeMask(self)
self.volume.create_volume()

# Cập nhật khi chỉnh sửa
self._update_imagedata()
self.volume._actor.Update()
```

### 7.3 Rust Extension

```python
import invesalius_rs as floodfill

# Fill holes
ret = floodfill.fill_holes_automatically(matrix, labels, nlabels, size)
```

### 7.4 Session (Singleton)

```python
import invesalius.session as ses

session = ses.Session()
session.ChangeProject()  # Đánh dấu project đã thay đổi
if session.GetConfig("auto_reload_preview"):
    self._update_imagedata()
```

---

## 8. Ví dụ sử dụng

### 8.1 Tạo mask mới

```python
from invesalius.data.mask import Mask

# Tạo mask
mask = Mask()
mask.create_mask(shape=(100, 200, 200))  # dz=100, dy=200, dx=200
mask.spacing = (1.0, 0.5, 0.5)  # mm/voxel

# Đặt tên và màu
mask.name = "Tumor ROI"
mask.colour = (1.0, 0.0, 0.0)  # Đỏ
mask.opacity = 0.5
```

### 8.2 Đọc/ghi giá trị voxels

```python
# Mask thực (bỏ qua padding)
actual_data = mask.matrix[1:, 1:, 1:]

# Gán giá trị
actual_data[50, 100, 100] = 255  # Threshold
actual_data[50, 101, 101] = 1    # Manual

# Flush để lưu vào memmap
mask.matrix.flush()

# Đánh dấu đã chỉnh sửa
mask.modified()
```

### 8.3 Undo/Redo

```python
# Trước khi chỉnh sửa - lưu trạng thái
current_slice = mask.matrix[51, 1:, 1:].copy()
# ... thực hiện chỉnh sửa ...
new_slice = mask.matrix[51, 1:, 1:].copy()

# Lưu vào history
mask.save_history(
    index=50,  # Slice index (sẽ được +1 khi ghi)
    orientation="AXIAL",
    array=new_slice,
    p_array=current_slice,
    clean=True
)

# Gọi undo/redo khi cần
mask.undo_history(actual_slices={"AXIAL": 50, "CORONAL": 100, "SAGITAL": 100})
mask.redo_history(actual_slices={"AXIAL": 50, "CORONAL": 100, "SAGITAL": 100})
```

### 8.4 Fill holes

```python
# Fill holes 2D trên slice hiện tại
mask.fill_holes_auto(
    target="2D",
    conn=8,           # 8-connectivity
    orientation="AXIAL",
    index=50,         # Slice 50
    size=100          # Holes nhỏ hơn 100 voxels
)

# Fill holes 3D toàn bộ volume
mask.fill_holes_auto(
    target="3D",
    conn=26,          # 26-connectivity
    orientation="AXIAL",
    index=0,
    size=500
)
```

### 8.5 Tạo preview 3D

```python
# Tạo preview 3D
mask.create_3d_preview()

# Cập nhật khi chỉnh sửa
mask.modified()
```

### 8.6 Persistence

```python
# Lưu
filelist = {}
mask.save_plist(dir_temp=".", filelist=filelist)

# Đọc
new_mask = Mask()
new_mask.open_plist("path/to/mask.plist")
```

---

## 9. Các hằng số liên quan

Tham khảo `invesalius/constants.py`:

```python
# Màu mask mặc định
MASK_COLOUR = [
    (1.0, 0.0, 0.0),      # Đỏ
    (0.0, 1.0, 0.0),      # Xanh lá
    (0.0, 0.0, 1.0),      # Xanh dương
    (1.0, 1.0, 0.0),      # Vàng
    (1.0, 0.0, 1.0),      # Tím
    (0.0, 1.0, 1.0),      # Cyan
    (1.0, 0.5, 0.0),      # Cam
    (0.5, 0.0, 1.0),      # Tím nhạt
]

# Ngưỡng mặc định
THRESHOLD_RANGE = [-1024, 3071]
THRESHOLD_OUTVALUE = 253
THRESHOLD_INVALUE = 255

# Tên mask pattern
MASK_NAME_PATTERN = "Mask %d"

# Độ trong suốt
MASK_OPACITY = 1.0
```

---

## 10. Troubleshooting

### Lỗi thường gặp

#### 1. "Mask data file not found"

```python
# Khi đọc mask từ plist, file .dat không tồn tại
# Nguyên nhân: InVesalius bị đóng đột ngột, file tạm bị xóa
# Giải pháp: Tạo mask mới
```

#### 2. Shape không khớp

```python
# Khi tạo mask mới, shape thực = shape + 1
# Lưu ý: Khi đọc từ plist, shape trong file đã bao gồm padding
mask_shape_saved = mask["mask_shape"]  # Đã có +1
```

#### 3. Undo/Redo không hoạt động

```python
# Kiểm tra actual_slices có đúng format không
actual_slices = {
    "AXIAL": current_axial_index,
    "CORONAL": current_coronal_index,
    "SAGITAL": current_sagittal_index
}
mask.undo_history(actual_slices)
```

---

## 11. Liên kết với các file khác

| File | Mô tả |
|------|-------|
| `invesalius/data/volume_mask.py` | Preview 3D của mask |
| `invesalius/data/slice_.py` | Slice viewer (sử dụng mask) |
| `invesalius/data/mask3d_editor_state.py` | Trạng thái editor 3D |
| `invesalius/data/volume.py` | Volume chính (chứa mask) |
| `invesalius/data/converters.py` | Chuyển đổi numpy ↔ VTK |
| `invesalius/segmentation/watershed_process.py` | Watershed segmentation |
| `invesalius/pubsub.py` | PubSub event system |
| `invesalius/constants.py` | Hằng số |

---

## Changelog

| Ngày | Mô tả |
|------|-------|
| 2026-08-20 | Tạo tài liệu ban đầu |

---

*Document generated for InVesalius 3 research and development.*
