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
- `student_progress.csv`: Tiến độ tích lũy tín chỉ và ngày CTXH theo từng học kỳ.
- `student_metrics.csv`: GPA tích lũy, trạng thái điều kiện tốt nghiệp, xếp loại bằng tốt nghiệp hoặc nguyên nhân thôi học/cảnh cáo học vụ.
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
- Sheet **Tiến độ & Tốt nghiệp**: Thống kê chi tiết tiến độ sinh viên theo khóa.

```bash
python synthetic_data/tools/export_excel_report.py
```
