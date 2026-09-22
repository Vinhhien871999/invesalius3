# CT3D Dataset Registry

> Quét filesystem thật (`D:\PyTools\dicom_samples\`), đọc tag DICOM thật bằng đúng DICOM stack InVesalius sử dụng (`invesalius.reader.dicom_reader.GetDicomGroups()` → gdcm), và import thật qua pipeline thật (`Publisher.sendMessage("Import directory", ...)`). Cập nhật Phase 12 (CT3D_P12_QUANTITATIVE_VALIDATION, 14/09/2026).
>
> **KHÔNG ghi PatientName/PatientID/BirthDate/accession number hay PHI khác trong file này** — `Dataset ID` là tên thư mục local dùng làm định danh nội bộ, không phải danh tính bệnh nhân thật. `Series Description` chỉ được ghi khi nội dung rõ ràng là mô tả protocol chụp (ví dụ "Extremety Ph1", "3DT1 7.5min256"), không phải tên người.

## Datasets tìm thấy thật trên filesystem

| Dataset ID | Modality | Manufacturer | Series Count | Dimensions (voxels) | Spacing (mm) | Slice Count | Ground Truth | Usage |
|---|---|---|---:|---|---|---:|---|---|
| `0051` | CT | SIEMENS | 1 | 108×512×512 | (0.4785, 0.4785, 1.5) | 108 | Không có | Dataset chính, dùng xuyên suốt Phase 08-11 (surface rebuild, sync 2D-3D, save/open forensics, v.v.) |
| `0801` | CT | Philips | 1 | 162×512×512 | (0.9766, 0.9766, 1.0) | 162 | Không có | Phase 12 — xác nhận vendor thứ 2 (import thật end-to-end PASS) |
| `mri3` | MR | Philips Medical Systems | 1 | 256×256×180 (orientation SAGITTAL — thứ tự trục matrix khác CT do hướng chụp) | (0.9993, 1.0, 1.0) | 180 | Không có | Phase 12 — xác nhận modality MR + vendor Philips (import thật end-to-end PASS) |

## Phương pháp

1. **Quét tag-level** (không cần import pixel data đầy đủ, không cần wx): `invesalius.reader.dicom_reader.GetDicomGroups(directory, recursive=True)` — hàm thật, đồng bộ, hỗ trợ `gui=False`, dùng chính `dicom_grouper.DicomPatientGrouper` + `dicom.Parser`/`dicom.Dicom` (bọc gdcm) mà pipeline import thật dùng. Với mỗi patient/series group tìm được, đọc `dcm.acquisition.modality`, `dcm.parser.GetManufacturerName()` (Manufacturer không được lưu sẵn trên object `Acquisition`, phải gọi trực tiếp trên `parser` — xác nhận qua đọc source `invesalius/reader/dicom.py`), `dcm.acquisition.series_description`, `dcm.image.orientation_label`, số lượng file trong `group.GetList()`.
2. **Xác nhận end-to-end thật** (import pixel data đầy đủ, cần wx + full app bootstrap giống Phase 08-11): `Publisher.sendMessage("Import directory", directory=<path>, use_gui=False)`, đợi `Slice().matrix` khác `None`, đọc `Project().modality`/`.spacing`/`Slice().matrix.shape`/`.dtype`/`.original_orientation`. **Mỗi dataset chạy trong 1 tiến trình Python riêng** — phát hiện thật (không phải suy đoán): reset singleton `Project.instance = None`/`Slice.instance = None` giữa 2 lần import KHÔNG tương đương với `Controller.CloseProject()` thật, gây `KeyError` thật trong `Slice.SetMaskEditionThreshold()` ở lần import thứ 2 khi thử import 3 dataset liên tiếp trong cùng 1 tiến trình — không phải bug InVesalius, là giới hạn phương pháp test (ghi nhận, không phải lỗi phần mềm — xem `CT3D_P12_QUANTITATIVE_VALIDATION_REPORT.md` mục 8).

## Kết luận cho A2 (đa vendor)

**3/3 dataset local xác nhận import thật thành công, 2 vendor thật khác nhau** (SIEMENS, Philips), 2 modality (CT, MR). Đây là bằng chứng thật, không suy đoán từ tên file — mọi giá trị đọc trực tiếp từ tag DICOM thật bằng đúng DICOM stack InVesalius dùng. Xem `CT3D_P12_QUANTITATIVE_VALIDATION_REPORT.md` mục 8 để biết cách trạng thái A2 được cập nhật.

**Vẫn còn thiếu**: GE, Canon — không có dataset local nào của 2 vendor này. `BLOCKED_EXTERNAL_DATA` — không tự động tải dataset ngoài (TCIA/LIDC-IDRI) trong phase này.

## Kết luận cho A4 (multi-series)

Cả 3 dataset đều chỉ có **1 patient, 1 series** (xác nhận qua `DicomPatientGrouper` thật — không có study nào chứa >1 series trong dữ liệu local hiện có). A4 (multi-series trong 1 study) **không có dữ liệu thật để test** — `BLOCKED_EXTERNAL_DATA`, giữ `NEEDS_RUNTIME_TEST`. Không tạo dataset multi-series giả rồi báo A4 WORKING (theo đúng chỉ đạo — synthetic multi-series chỉ hợp lệ để unit-test riêng logic grouping, không thay được bằng chứng runtime từ DICOM thật).
