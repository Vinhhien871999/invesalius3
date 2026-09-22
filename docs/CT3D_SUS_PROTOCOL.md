# CT3D SUS (System Usability Scale) Protocol

> **Trạng thái**: `SUS_PROTOCOL_READY = YES`, `SUS_REAL_PARTICIPANTS_COMPLETE = NO`. File này là **protocol/kế hoạch khảo sát**, KHÔNG chứa kết quả khảo sát thật — chưa có người tham gia thật nào thực hiện. Không tạo participant giả, không tạo SUS score giả, không kết luận usability tốt/xấu khi chưa khảo sát.

## 1. Mục tiêu khảo sát

Đo lường usability chủ quan (System Usability Scale — thang đo chuẩn, 10 câu, Brooke 1996) của plugin ROI Viewer khi dùng thật trong quy trình xem/chỉnh sửa ROI trên ảnh CT/MRI, theo đúng yêu cầu tài liệu kế hoạch đề tài (`Ke_hoach_de_tai_InVesalius_CT3D.md` mục 4.2) — phần **chưa thực hiện được** vì cần người dùng thật, ngoài phạm vi kỹ thuật thuần của các phase audit trước đó.

## 2. Đối tượng dự kiến tham gia

- Bác sĩ chẩn đoán hình ảnh (Radiologist).
- Kỹ thuật viên CT/MRI (Radiologic Technologist).
- Sinh viên/nghiên cứu sinh ngành Kỹ thuật Y sinh hoặc Chẩn đoán hình ảnh có kinh nghiệm dùng phần mềm xem ảnh y tế (PACS, 3D Slicer, InVesalius, OsiriX, v.v.).

**Số lượng khuyến nghị — Phase 14 làm rõ, tách 2 khái niệm KHÔNG được gộp lẫn nhau**:
- **Phát hiện vấn đề usability nghiêm trọng (qualitative, formative)**: theo heuristic của Nielsen, ~5 người tham gia đã đủ để phát hiện phần lớn (~85%) các vấn đề usability nghiêm trọng qua quan sát/task-based testing. Đây là ngưỡng cho **phát hiện vấn đề định tính**, KHÔNG phải ngưỡng cho điểm SUS trung bình có ý nghĩa thống kê.
- **Điểm SUS trung bình cho khảo sát định lượng khám phá (exploratory quantitative)**: **10-20 người** là mục tiêu thực tế (practical target) cho quy mô luận văn thạc sĩ này — KHÔNG phải một ngưỡng tự động đảm bảo "đủ ý nghĩa thống kê". Báo cáo SUS phải luôn ghi rõ **n (cỡ mẫu), mean (trung bình), SD (độ lệch chuẩn)**, và nên có khoảng tin cậy (confidence interval) nếu tính được. Độ chính xác thống kê thật sự phụ thuộc vào thiết kế nghiên cứu, độ biến thiên (variability) quan sát được, và độ bất định (uncertainty) mong muốn — **không có cỡ mẫu cố định nào tự động đảm bảo một ước lượng SUS đủ ý nghĩa thống kê**. **[Sửa 22/09/2026, Post-Phase-14 Release Closure]**: wording trước đó ("10-20 người để điểm SUS trung bình đủ tin cậy") quá tuyệt đối — đã sửa lại đúng bản chất thống kê.
- Hai mục tiêu này **độc lập**: một buổi khảo sát 5 người có thể phát hiện vấn đề usability nghiêm trọng thật, nhưng KHÔNG được dùng điểm SUS trung bình từ 5 người đó để kết luận "phần mềm có usability tốt/xấu" theo nghĩa thống kê.

## 3. Điều kiện tham gia

- Đủ 18 tuổi trở lên.
- Có kinh nghiệm chuyên môn hoặc học thuật liên quan đến hình ảnh y tế (không bắt buộc là chuyên gia, nhưng phải hiểu khái niệm CT/MRI/segmentation cơ bản).
- Tự nguyện tham gia, có thể dừng bất kỳ lúc nào không cần lý do.
- Đồng ý với điều khoản ở mục 9 (Consent/Privacy) trước khi bắt đầu.

## 4. Task Scenario (kịch bản thao tác trước khi trả lời khảo sát)

Người tham gia thực hiện đúng trình tự sau trên 1 dataset CT thật — dataset `0051` (xem `CT3D_DATASET_REGISTRY.md` cho chi tiết vendor/modality/kích thước; đường dẫn cục bộ cụ thể tuỳ máy chạy khảo sát, ví dụ `<DICOM_DATASET_DIR>/0051`, xem `CT3D_INSTALL_AND_RUN.md` mục 8 cho cách trỏ dataset qua biến môi trường `CT3D_DICOM_SAMPLES_DIR`) — có người hướng dẫn (không phải tự học), trước khi điền SUS:

1. Import CT, mở plugin ROI Viewer.
2. Tạo 1 mask bằng Threshold (Otsu tự động hoặc tay).
3. Dựng surface 3D từ mask vừa tạo.
4. Sửa mask bằng Brush, xoá 1 phần bằng Eraser.
5. Cập nhật lại surface 3D ("Update 3D Surface from Selected ROI"), quan sát thay đổi.
6. Thêm 1 annotation tại 1 vị trí đã pick trên khung 3D hoặc 2D.
7. Đo 1 khoảng cách 2D và 1 diện tích 2D.
8. Lưu project, đóng, mở lại — xác nhận mask/annotation còn nguyên.
9. Export mask ra 1 định dạng bất kỳ (NIfTI/NumPy).

**Thời gian dự kiến**: 15-20 phút thao tác + 5 phút điền khảo sát.

## 5. 10 câu SUS chuẩn (nguyên văn, không sửa đổi — Brooke 1996)

1. I think that I would like to use this system frequently.
2. I found the system unnecessarily complex.
3. I thought the system was easy to use.
4. I think that I would need the support of a technical person to be able to use this system.
5. I found the various functions in this system were well integrated.
6. I thought there was too much inconsistency in this system.
7. I would imagine that most people would learn to use this system very quickly.
8. I found the system very cumbersome to use.
9. I felt very confident using the system.
10. I needed to learn a lot of things before I could get going with this system.

*(Bản dịch tiếng Việt có thể cung cấp song song cho người tham gia không thông thạo tiếng Anh, nhưng điểm số phải tính theo đúng thang gốc — không đổi nội dung câu hỏi.)*

## 6. Thang Likert

Mỗi câu trả lời theo thang 5 điểm chuẩn:

`1 = Strongly Disagree` … `5 = Strongly Agree`

## 7. Công thức tính điểm (SUS scoring — chuẩn, không tự chế)

Cho mỗi người tham gia, với điểm trả lời `x1..x10` (1-5):

- Với câu **lẻ** (1,3,5,7,9 — câu tích cực): điểm đóng góp = `x - 1`
- Với câu **chẵn** (2,4,6,8,10 — câu tiêu cực): điểm đóng góp = `5 - x`
- **SUS score (1 người) = (tổng 10 điểm đóng góp) × 2.5** → thang 0-100.

**SUS score cuối (nhiều người) = trung bình cộng SUS score của tất cả người tham gia.**

Tham chiếu diễn giải chuẩn (Bangor et al. 2009 — chỉ dùng để diễn giải, không tự suy ra kết luận khi chưa có dữ liệu thật):
- ≥ 80.3: Excellent (grade A)
- 68-80.3: Good (grade B/C)
- 51-68: OK (grade D)
- < 51: Poor (grade F)

## 8. Cách lưu kết quả (anonymized)

- Mỗi người tham gia được gán 1 mã ẩn danh (ví dụ `P01`, `P02`, …) — **không lưu tên thật, không lưu thông tin định danh cá nhân nào** trong file kết quả.
- Kết quả lưu dạng CSV riêng (ví dụ `CT3D_SUS_RESULTS.csv`, **chưa tạo — chỉ tạo khi có dữ liệu thật**), cột tối thiểu: `Participant_ID, Q1..Q10, SUS_Score, Date, Role (Radiologist/Technologist/Student/Other), Notes`.
- Không lưu audio/video buổi khảo sát trừ khi người tham gia đồng ý riêng và có cơ chế lưu trữ bảo mật phù hợp (ngoài phạm vi file này).
- File kết quả (khi có) không commit kèm thông tin định danh — chỉ mã participant ẩn danh.

## 9. Consent / Privacy Note

Trước khi bắt đầu, người tham gia phải được thông báo và đồng ý (bằng lời hoặc văn bản, tuỳ quy trình đạo đức nghiên cứu áp dụng của cơ sở):

> "Bạn đang tham gia khảo sát usability tự nguyện cho phần mềm ROI Viewer (plugin InVesalius) trong khuôn khổ đề tài nghiên cứu khoa học. Dữ liệu thu thập là ẩn danh (không lưu tên/thông tin định danh cá nhân), chỉ dùng cho mục đích đánh giá usability của phần mềm. Bạn có thể dừng tham gia bất kỳ lúc nào mà không cần lý do và không ảnh hưởng gì đến bạn. Bạn có đồng ý tham gia không?"

Nếu cơ sở nghiên cứu yêu cầu quy trình IRB/đạo đức nghiên cứu chính thức, phải hoàn tất quy trình đó **trước khi** thực hiện khảo sát thật — file này chỉ là protocol kỹ thuật, không thay thế phê duyệt đạo đức nghiên cứu.

## 10. Trạng thái

| Field | Value |
|---|---|
| `SUS_PROTOCOL_READY` | **YES** |
| `SUS_REAL_PARTICIPANTS_COMPLETE` | **NO** |
| Số người tham gia thật tính đến nay | 0 |
| File kết quả | Chưa tạo — sẽ tạo `CT3D_SUS_RESULTS.csv` khi có dữ liệu thật |

Không kết luận usability tốt/xấu (theo nghĩa thống kê, dựa trên điểm SUS trung bình) cho đến khi có dữ liệu khảo sát thật, với **10-20 người** tham gia đủ điều kiện (mục 3) là mục tiêu thực tế cho khảo sát định lượng khám phá của luận văn này — xem phân biệt rõ ở mục 2 giữa mục tiêu phát hiện vấn đề định tính (~5 người, Nielsen) và mục tiêu thực tế cho điểm SUS trung bình (10-20 người, không phải ngưỡng thống kê tự động đảm bảo). Mọi báo cáo SUS thật phải ghi rõ n/mean/SD (và CI nếu có) — không chỉ 1 con số điểm trung bình đơn lẻ. Một buổi khảo sát nhỏ hơn (kể cả chỉ 5 người) vẫn có giá trị để phát hiện vấn đề usability nghiêm trọng cụ thể, nhưng không được dùng để báo cáo điểm SUS trung bình như một kết luận định lượng độc lập.
