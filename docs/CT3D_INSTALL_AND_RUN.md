# CT3D — Install & Run (Plugin ROI Viewer)

> Tài liệu này CHỈ bổ sung phần đặc thù của đề tài CT3D (plugin `ROI Viewer`, test suite `tests/ct3d`, benchmark tool). Cài đặt InVesalius gốc (đa nền tảng: Linux/Mac/Windows) đã có hướng dẫn chính thức trên wiki upstream — xem `README.md` mục "Development" (`Running InVesalius 3 in Linux/Mac/Windows`), KHÔNG lặp lại ở đây. Mọi lệnh dưới đây đã được xác minh thật khớp với cấu trúc repo hiện tại (không tự bịa lệnh).

## 1. Môi trường Python đã dùng để verify (Phase 08-14)

- Python **3.11.7**, venv riêng tại `D:\PyTools\invx-venv` (máy phát triển của đề tài — không phải đường dẫn trong repo, chỉ ghi lại để tái tạo).
- **Lưu ý thật, không giấu**: `pyproject.toml` khai báo `requires-python = "==3.12.*"` (dòng 46), khác với Python 3.11.7 đã dùng để verify toàn bộ CT3D trong các phase 08-14. Đây là một khác biệt thật giữa metadata packaging và môi trường verify thực tế — tài liệu này không tự sửa `pyproject.toml` (ngoài phạm vi audit tài liệu, có thể ảnh hưởng đến packaging/CI khác) — chỉ ghi nhận trung thực để người dùng biết môi trường nào đã thật sự được kiểm chứng.

## 2. Cài đặt

```
git clone https://github.com/Vinhhien871999/invesalius3.git
cd invesalius3
git checkout thesis-ct-roi-tools

python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

pip install -r requirements.txt
```

`requirements.txt` tồn tại thật ở gốc repo (xác nhận qua `ls`). Với các dependency nền tảng-đặc thù (VTK/wxPython build, GPU PyTorch...) hoặc lỗi cài đặt hệ thống, xem hướng dẫn upstream theo từng OS trong `README.md`.

## 3. Chạy InVesalius

```
python app.py
```

hoặc import DICOM ngay khi khởi động:

```
python app.py -i <đường dẫn thư mục DICOM>
```

`app.py` tồn tại thật ở gốc repo (xác nhận qua `ls`).

## 4. Mở Plugin ROI Viewer

Sau khi InVesalius mở: menu **Plugins → ROI Viewer**.

Plugin được `invesalius.plugins.PluginManager` phát hiện thật qua `plugins/roi_viewer/plugin.json` (xác nhận nội dung thật: `{"name": "ROI Viewer", "description": "...", "enable-startup": true}`) — `enable-startup: true` nghĩa là plugin sẵn sàng dùng ngay, không cần bật thủ công trong config. Bấm lại **Plugins → ROI Viewer** lần nữa chỉ đưa cửa sổ cũ ra trước (không mở cửa sổ thứ 2) — xem `HUONG_DAN_SU_DUNG_ROI_VIEWER.md` mục 1 cho hướng dẫn thao tác đầy đủ.

## 5. Cài đặt tuỳ chọn: NRRD export

```
pip install invesalius[nrrd]
# hoặc
pip install pynrrd
```

Extra `nrrd` xác nhận thật tồn tại trong `pyproject.toml` (mục `[project.optional-dependencies]`, `nrrd = ["pynrrd>=1.0.0"]`). Không cài vẫn dùng được toàn bộ plugin — chỉ export định dạng NRRD sẽ bị ẩn/cảnh báo rõ trong UI nếu thiếu.

## 6. Chạy test CT3D

```
# Test suite CT3D (plugin ROI Viewer)
python -m pytest tests/ct3d -q

# Test suite upstream InVesalius (không đụng, để xác nhận không phá gì)
python -m pytest tests --ignore=tests/ct3d -q
```

Baseline hiện tại (verify lại nhiều lần qua Phase 13.5/14, ổn định): `tests/ct3d` = 184 collected / 183 passed / 1 skipped (tuỳ chọn, không phải lỗi). Upstream = 94 passed.

## 7. Static analysis (tuỳ chọn, dùng khi phát triển)

```
python -m pyflakes plugins/roi_viewer
python -m pyflakes tools/ct3d_benchmark.py

python -m compileall plugins/roi_viewer
python -m py_compile tools/ct3d_benchmark.py
```

## 8. Benchmark tool (tuỳ chọn — cần dataset DICOM thật, KHÔNG kèm trong repo)

**Dataset DICOM KHÔNG được đóng gói kèm repository** (dữ liệu ảnh y tế thật, cố ý loại khỏi version control — xem `CT3D_DATASET_REGISTRY.md`). Muốn chạy `tools/ct3d_benchmark.py`, cần tự chuẩn bị dataset cục bộ và trỏ qua biến môi trường:

```
# Windows PowerShell
$env:CT3D_DICOM_SAMPLES_DIR = "C:\path\to\your\dicom_samples"

# Linux/Mac
export CT3D_DICOM_SAMPLES_DIR="/path/to/your/dicom_samples"

python tools/ct3d_benchmark.py --dataset 0051 --mode full
python tools/ct3d_benchmark.py --dataset 0051 --mode import
python tools/ct3d_benchmark.py --mode saveopen
```

Thư mục trỏ tới phải chứa các thư mục con `0051/`, `0801/`, `mri3/` (mỗi thư mục là 1 series DICOM thật của cùng dataset đã dùng để verify CT3D — xem `CT3D_DATASET_REGISTRY.md` cho vendor/modality/kích thước từng bộ). Không có `CT3D_DICOM_SAMPLES_DIR` → mặc định dùng đường dẫn cục bộ của máy phát triển gốc (`D:\PyTools\dicom_samples`), sẽ không tồn tại trên máy khác. `--mode saveopen` không cần dataset thật (dùng project tổng hợp nhỏ).

## 9. Tài liệu liên quan

- `docs/CT3D_RELEASE_MANIFEST.md` — bản đồ tổng thể release.
- `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md` — hướng dẫn thao tác từng nút bấm thật trong plugin.
- `docs/CT3D_RELEASE_NOTES.md` — release notes đầy đủ + research-prototype disclaimer.
- `docs/CT3D_KNOWN_LIMITATIONS.md` — giới hạn đã biết.
