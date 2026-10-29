# Công cụ chuẩn bị và sinh dữ liệu

Thư mục `tools` chứa các script hỗ trợ chuẩn bị dữ liệu nguồn và chạy chuỗi
sinh lớp học/phân công đăng ký học phần. Chạy lệnh từ thư mục gốc dự án để các
đường dẫn tương đối và môi trường ảo được sử dụng nhất quán.

```bash
source .venv/bin/activate
python synthetic_data/tools/<ten_file>.py
```

Trên Windows, kích hoạt môi trường bằng `.venv\\Scripts\\activate`.

## Quy trình sử dụng

1. Chạy toàn bộ quy trình sinh dữ liệu mẫu:
   ```bash
   python synthetic_data/tools/run_all.py
   ```
2. Xuất báo cáo Excel tổng hợp chỉ số học vụ:
   ```bash
   python synthetic_data/tools/export_excel_report.py
   ```

## Các công cụ chính

### 1. `run_all.py` — Pipeline điều phối trung tâm

Tự động thực thi toàn bộ chuỗi sinh dữ liệu theo đúng thứ tự:
- **Học vụ**: `generators/academics/generate_semester.py` $\rightarrow$ `generate_curriculum.py`
- **Người dùng**: `generators/users/generate_users.py` $\rightarrow$ `generate_student_profiles.py`
- **Lớp & Điểm**: Tự động phát hiện và chạy tuần tự các file `classes/generate_class_hk*.py` và `enrollments/generate_enrollment_hk*.py` hiện có.
- **Thống kê**: Tính toán các chỉ số học vụ tự động thông qua `tools/generate_academic_metrics.py`.

```bash
python synthetic_data/tools/run_all.py
```

### 2. `generate_academic_metrics.py` — Đo lường & Thống kê học vụ

Đọc dữ liệu hồ sơ sinh viên, lớp học phần và kết quả đăng ký điểm số để tính toán các chỉ số chất lượng đào tạo:
- `student_progress.csv`: Tiến độ tích lũy tín chỉ và ngày CTXH theo từng học kỳ của từng sinh viên.
- `student_metrics.csv`: Lưu trữ chi tiết từng sinh viên:
  - Điểm trung bình tích lũy hệ 4 (`final_gpa_4`) và hệ 10 (`gpa_10`).
  - Trạng thái điều kiện tốt nghiệp: Đủ 128 tín chỉ, $\ge 15$ ngày CTXH, chuẩn tiếng Anh, đồ án tốt nghiệp và **điểm $\text{GPA}_4 \ge 2.0$**.
  - Xếp loại tốt nghiệp chuẩn hóa: Xuất sắc ($\ge 3.6$), Giỏi ($3.2 \le \text{GPA}_4 < 3.6$), Khá ($2.5 \le \text{GPA}_4 < 3.2$), Trung bình ($2.0 \le \text{GPA}_4 < 2.5$).
  - Ghi nhận chi tiết trạng thái thôi học (`voluntary_economic` hoặc `academic_exceeded_max_terms`).
- `university_metrics.csv`: Tỷ lệ thôi học, tỷ lệ đạt tiếng Anh, tỷ lệ tốt nghiệp đúng hạn/trễ hạn và phân loại bằng toàn trường.
- `score_distribution.csv` & `letter_grade_distribution.csv`: Phân phối phổ điểm (hệ 10, hệ 4 và điểm chữ A+ đến F) theo từng môn và toàn trường.

```bash
python synthetic_data/tools/generate_academic_metrics.py
python synthetic_data/tools/generate_academic_metrics.py --cohort 20
```

### 3. `export_excel_report.py` — Xuất báo cáo nghiệm thu Excel

Đọc các file số liệu thống kê từ `synthetic_data/generated/metrics/` và tổng hợp thành file Excel trực quan, đa trang (`academic_validation_report.xlsx`):
- Sheet **Tổng quan**: Các chỉ số KPI trọng yếu của trường.
- Sheet **Phân phối điểm**: Phổ điểm theo môn học và toàn trường.
- Sheet **Phân phối điểm chữ**: Tỷ lệ A+, A, B+, B, C+, C, D+, D, F.
- Sheet **Tiến độ & Tốt nghiệp**: Tích hợp 3 bảng phân tích đa chiều và biểu đồ trực quan:
  * **Bảng 1 (Toàn trường theo khóa K20–K26):** Tổng số SV, Tốt nghiệp đúng hạn, Trễ hạn, Tổng tốt nghiệp (tỷ lệ %), Thôi học kinh tế, Thôi học học vụ, Tổng thôi học (tỷ lệ %), Chưa tốt nghiệp.
  * **Bảng 2 (Chi tiết Khóa K20 theo Hệ đào tạo):** Phân tích riêng rẽ hệ Đại trà (`standard`), Chất lượng cao (`high-quality`), và Tiên tiến (`advanced`).
  * **Bảng 3 (Phân loại tốt nghiệp K20 theo Hệ đào tạo):** Thống kê số lượng và tỷ lệ % tốt nghiệp Xuất sắc, Giỏi, Khá, Trung bình theo từng hệ.
  * **Biểu đồ trực quan:** Biểu đồ cột chồng (Stacked Column Chart) minh họa phân phối trạng thái học vụ K20 theo hệ đào tạo.

```bash
python synthetic_data/tools/export_excel_report.py
```
