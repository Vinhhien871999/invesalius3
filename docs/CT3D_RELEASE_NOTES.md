# CT3D — Release Notes (Phase 14, Software Release Candidate)

> **⚠️ NGHIÊN CỨU / HỌC THUẬT — KHÔNG PHẢI THIẾT BỊ Y TẾ ĐÃ CHỨNG NHẬN.** Phần mềm này (InVesalius + Plugin ROI Viewer) là sản phẩm của đề tài nghiên cứu khoa học/luận văn thạc sĩ. Đây **KHÔNG phải** thiết bị y tế đã được cấp phép/chứng nhận (FDA/CE/Bộ Y tế hay bất kỳ cơ quan quản lý nào), **KHÔNG được** dùng cho chẩn đoán/điều trị lâm sàng thật, và **CHƯA qua clinical validation** (`CLINICAL_VALIDATION_COMPLETE = NO`). Chỉ dùng cho mục đích nghiên cứu, học thuật, demo kỹ thuật.

## 1. Phạm vi

Plugin `ROI Viewer` mở rộng InVesalius (phần mềm mã nguồn mở, trực quan hoá/tái tạo 3D ảnh y tế) với 1 cửa sổ bảng điều khiển tổng hợp cho việc xem, chỉnh sửa, đo lường và ghi chú vùng quan tâm (ROI) trên ảnh CT/MRI 3D — điều khiển trực tiếp các tính năng thật của InVesalius, không sao chép/giả lập.

## 2. Cơ sở upstream

- Dựa trên **InVesalius 3** (Centro de Pesquisas Renato Archer, GPL-2.0), fork `Vinhhien871999/invesalius3`, branch `thesis-ct-roi-tools`.
- Không sửa đổi phá vỡ tương thích với InVesalius gốc — plugin là extension point độc lập (`plugins/roi_viewer/`), toàn bộ `.inv3` project vẫn dùng đúng cơ chế Save/Open gốc.

## 3. Đóng góp mới (Plugin ROI Viewer)

- **Quản lý ROI tập trung**: danh sách mask theo tên tại 1 nơi, không rải rác nhiều task panel.
- **Region Growing** bán tự động từ điểm hạt giống 3D, có cảnh báo an toàn khi vùng mọc quá lớn (>20% thể tích).
- **Auto-threshold Otsu**.
- **Update 3D Surface** chủ động sau khi sửa mask (brush/eraser/undo/region growing) — không cần vào lại task panel gốc.
- **Undo/Redo** nhanh cho chỉnh sửa mask (checkpoint tường minh, `max_history=10`).
- **Sync 3D→2D và 2D→3D**: pick điểm 3D tự nhảy đúng slice 2D; ngược lại, click/kéo 2D hiển thị marker + 3 mặt phẳng bán trong suốt (Axial/Coronal/Sagital) trong khung 3D (yêu cầu người dùng tự bật công cụ native `"Slices' cross intersection"` trước — xem `CT3D_KNOWN_LIMITATIONS.md` mục 11).
- **Đo lường 3D** (khoảng cách) tích hợp với picker 3D thật; đo 2D (khoảng cách/diện tích) dùng lại đúng công cụ remote-control gốc của InVesalius.
- **Annotation** văn bản gắn vị trí cụ thể, lưu kèm project qua sidecar JSON.
- **Xuất dữ liệu**: NIfTI (đã verify), NRRD (dependency tuỳ chọn `pynrrd`), NumPy.
- **Hạ tầng đánh giá định lượng**: Dice/Jaccard/Hausdorff/HD95 (`core/evaluation.py`), validated trên phantom synthetic.

## 4. Tóm tắt các phase (08 → 14)

| Phase | Nội dung chính |
|---|---|
| 08 | D9/C7 root cause thật (surface rebuild dùng sai algorithm), sửa + verify runtime |
| 09 | Sync 2D→3D/3D→2D, annotation vị trí chính xác (F3), manual QA checklist khởi tạo |
| 10 | Data integrity forensics (Save/Open checksum), Undo/Redo memory benchmark + tối ưu |
| 11 | Sửa lại số liệu worst-case Undo/Redo, xoá dead code, chuyển bằng chứng thành pytest bền vững |
| 12 | Dataset registry (2 vendor thật), Dice/Jaccard/Hausdorff infra + synthetic validation, Region Growing full-volume |
| 13 | Đóng 7/7 Manual QA thật, benchmark hiệu năng có phương pháp, SUS protocol chuẩn bị |
| 13.5 | C8 nâng cấp trực quan: 3 mặt phẳng 2D→3D (`SlicePlanes3D`) |
| **14 (cuối)** | **Final audit, C8 reconciliation, doc consistency, CSV validation, static analysis, release-candidate closure** |

## 5. Regression / Static Analysis (Phase 14, real evidence)

- `pytest tests/ct3d -q`: **183 passed, 1 skipped** (184 collected) — chạy lại **3 lần liên tiếp**, kết quả giống hệt cả 3 lần.
- `pytest tests --ignore=tests/ct3d -q` (upstream InVesalius, không đụng): **94 passed**.
- `pyflakes plugins/roi_viewer`: sạch (exit 0). `pyflakes tools/ct3d_benchmark.py`: sạch (exit 0) — báo cáo riêng biệt, không gộp lẫn.
- `python -m compileall plugins/roi_viewer` và `python -m py_compile tools/ct3d_benchmark.py`: đều PASS.
- Import smoke test (không GUI): core modules, `slice_planes_3d`, `evaluation` import sạch; `plugin.json` parse đúng; `PluginManager.find_plugins()` thật xác nhận phát hiện `"ROI Viewer"` cùng các plugin gốc khác; `--help` của benchmark tool chạy đúng.

## 6. Manual QA (thao tác chuột thật)

- **7/7 mục gốc: PASS** (P08.5, B4, C3, D4, D5, E2, E3) — người vận hành thật, dataset `0051`, 16/09/2026. Chi tiết + số liệu thật: `CT3D_MANUAL_QA_CHECKLIST.md`.
- **C8 (Visual Sync 2D→3D)**: core path đã có bằng chứng operator smoke test thật (`C8_VISUAL_OPERATOR_SMOKE = PASS`: native tool ON + Sync 2D→3D ON + click/kéo 2D → marker/mặt phẳng di chuyển đúng, surface không đổi hình học). 9 mục lettered chi tiết (TEST A-I) chưa được người vận hành itemize riêng lẻ — ghi `NOT_EXPLICITLY_MANUAL_VERIFIED`, không phải FAIL, không phải giả định PASS.

## 7. Dataset & Hiệu năng

- **Dataset thật đã dùng**: `0051` (CT, SIEMENS, 108×512×512), `0801` (CT, Philips, 162×512×512), `mri3` (MR, Philips Medical Systems, 256×256×180) — xem `CT3D_DATASET_REGISTRY.md`. Không có PHI (kiểm tra riêng, không tìm thấy giá trị PatientName/PatientID/... thật nào trong repo).
- **FPS đại diện**: **122.0–158.3 FPS** (surface rendering, 3 bộ dữ liệu). Con số "10000.0 FPS" xuất hiện trong `CT3D_P13_PERFORMANCE_RESULTS.csv` là artifact đo lường trên mesh cực nhỏ (độ phân giải tối thiểu VTK), **không đại diện**, không dùng để quảng cáo hiệu năng.
- **Surface build**: `0801` từng cho mesh rỗng (0 điểm) do threshold band benchmark hẹp — đã reclassify `BENCHMARK_INPUT_EMPTY` (không phải bug thật) và chạy lại đại diện thành công (145,772 điểm, 254,978 cell, PASS) ở Phase 14.
- Toàn bộ số liệu đo trên 1 máy phát triển, RAM hạn chế (0.55–2.35GB quan sát được lúc đo) — không đại diện mọi cấu hình phần cứng.

## 8. Cài đặt NRRD (tuỳ chọn)

```
pip install invesalius[nrrd]
# hoặc
pip install pynrrd
```
Không cài vẫn dùng được toàn bộ plugin — chỉ export NRRD sẽ bị ẩn/cảnh báo rõ ràng nếu thiếu.

## 9. Lệnh tái tạo (reproducibility)

```
# Test suite CT3D
python -m pytest tests/ct3d -q

# Test suite upstream (không đụng)
python -m pytest tests --ignore=tests/ct3d -q

# Static analysis
python -m pyflakes plugins/roi_viewer
python -m pyflakes tools/ct3d_benchmark.py

# Benchmark (cần dataset local thật, xem CT3D_DICOM_SAMPLES_DIR env var)
python tools/ct3d_benchmark.py --dataset 0051 --mode full
python tools/ct3d_benchmark.py --dataset 0051 --mode import
python tools/ct3d_benchmark.py --mode saveopen
```

## 10. Giới hạn đã biết

Xem đầy đủ, phân loại rõ ràng tại `CT3D_KNOWN_LIMITATIONS.md`. Tóm tắt: 2/4 vendor CT xác nhận thật (thiếu GE/Canon), chưa có ground-truth thật cho Dice/Jaccard/Hausdorff, chưa có khảo sát SUS người dùng thật, chưa so sánh benchmark với 3D Slicer, raycasting thuần không kết nối được (giới hạn InVesalius gốc), không export DICOM-SEG (ngoài phạm vi).

## 11. External / Clinical Validation

- `RESEARCH_EXTERNAL_VALIDATION_COMPLETE = NO`
- `CLINICAL_VALIDATION_COMPLETE = NO`

Đây là công việc **ngoài phạm vi kỹ thuật thuần túy** của roadmap phần mềm (Phase 08-14) — cần dataset có nhãn thật, người dùng thật (bác sĩ/KTV), và/hoặc phần mềm khác để so sánh, không có sẵn trong môi trường phát triển hiện tại.

---

**Trạng thái cuối cùng**: `SOFTWARE_RELEASE_CANDIDATE_READY = YES` (phần kỹ thuật). Phần mềm này là một **research prototype** — không phải thiết bị y tế, không dùng cho chẩn đoán/điều trị lâm sàng thật.
