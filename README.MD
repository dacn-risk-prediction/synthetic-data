# Synthetic Academic Data Generator

Repository này cung cấp hệ thống sinh dữ liệu học vụ **mô phỏng** (Synthetic Data) toàn diện cho chương trình đào tạo Cử nhân Khoa học Máy tính (Computer Science - Chuẩn ABET, Trường ĐH Bách Khoa - ĐHQG-HCM). 

Hệ thống mô phỏng toàn bộ vòng đời sinh viên từ lúc nhập học (K20 đến K26) qua từng học kỳ (HK201 đến HK261), bao gồm: danh mục môn học, phân công giảng viên, đăng ký học phần, điểm thành phần theo đề cương, đánh giá tiến độ học vụ, chuẩn đầu ra (Tiếng Anh, Công tác xã hội) và xét tốt nghiệp.

> [!NOTE]
> Toàn bộ dữ liệu trong repository là **dữ liệu tổng hợp (synthetic)** phục vụ kiểm thử, phát triển thuật toán và phân tích; không chứa thông tin cá nhân hay dữ liệu học vụ thực tế của sinh viên.

---

## 1. Chức năng chính

- **Mô hình hóa chương trình đào tạo (ABET):** 7 CTĐT chính quy (K20–K26), 128 môn học, 20 khối kiến thức, phân bổ môn bắt buộc (`BB`), tự chọn nhóm (`Group A/B/C/D`), và cây tiên quyết (`TQ`, `KN`, `SH`).
- **Hồ sơ năng lực sinh viên (Student Profiles):** 11.092 sinh viên với hồ sơ năng lực ẩn đa chiều (học lực nền tảng `academic_level` 1–5, kỷ luật `discipline`, động lực `motivation`, mức độ căng thẳng `stress`, tiến độ ngày CTXH và chứng chỉ Tiếng Anh theo từng học kỳ).
- **Phân hệ đào tạo đa dạng:** Sinh viên Đại trà (Tiêu chuẩn), Chất lượng cao (CLC), Chương trình Tiên tiến. Sinh viên CLC/Tiên tiến được miễn các học phần tiếng Anh theo quy chế.
- **Mở lớp & Cân bằng tải:** Phân bổ nhóm lớp (`L01..L23` đại trà, `CC01..CC12` CLC, `TT01..TT05` Tiên tiến), phân công 100 giảng viên theo đúng bộ môn và chuyên môn, kiểm soát sĩ số.
- **Mô phỏng điểm số theo đề cương môn học:** Sinh điểm thành phần (`quiz`, `lab`, `btl`, `giua_ky`, `cuoi_ky`) theo đúng tỷ lệ % trong `assessment.csv`, tính điểm tổng kết hệ 10, quy đổi hệ 4 và điểm chữ (`A+` đến `F`). Điểm qua môn khi `final_score >= 4.0` (khác `F`).
- **Phân tích tốt nghiệp 3 trụ cột:** Đánh giá tốt nghiệp thực tế dựa trên:
  1. *Học vụ:* Hoàn thành toàn bộ môn bắt buộc, tối thiểu 128 tín chỉ, GPA $\ge 2.0$, hoàn tất Khóa luận tốt nghiệp (`CO4337`).
  2. *Ngoại ngữ:* Đạt chuẩn Tiếng Anh đầu ra theo quy chế trường.
  3. *Xã hội:* Tích lũy tối thiểu 15 ngày Công tác xã hội (CTXH).
- **Mô phỏng lộ trình linh hoạt:** Tốt nghiệp sớm (Kỳ 7 - 3.5 năm cho top 1% sinh viên xuất sắc), Tốt nghiệp đúng hạn (Kỳ 8 - 4.0 năm), và Nợ chuẩn đầu ra / Kéo dài thời gian đào tạo.

---

## 2. Cấu trúc Repository

```text
.
├── README.MD                               # Tài liệu tổng quan dự án
├── requirements.txt                        # Thư viện phụ thuộc
└── synthetic_data/
    ├── config/
    │   └── generator_config.json           # Cấu hình trọng số, phổ điểm, độ khó, chuẩn tốt nghiệp
    ├── generated/                          # Bộ dữ liệu CSV chuẩn hóa
    │   ├── academics/                      # Môn học, CTĐT, tiên quyết, đề cương thành phần điểm
    │   ├── users/                          # User, Sinh viên, Giảng viên, Hồ sơ năng lực (profiles)
    │   ├── classes/                        # Danh sách lớp học phần theo học kỳ (HK201 -> HK261)
    │   ├── enrollments/                    # Điểm và kết quả đăng ký theo học kỳ (HK201 -> HK261)
    │   └── metrics/                        # Thống kê tiến độ ngoại ngữ, CTXH
    ├── rules/
    │   ├── academic_rules.py               # Luật học vụ, mô phỏng điểm số, miễn giảm ngoại ngữ
    │   ├── curriculum_rules.py             # Ràng buộc chương trình đào tạo & tín chỉ tự chọn
    │   └── additional_course_rules.csv     # Quy tắc học vượt cấp (CO3061, CO4029, CO4337)
    ├── generators/
    │   ├── academics/                      # Sinh danh mục môn, học kỳ, CTĐT
    │   ├── users/                          # Sinh sinh viên, giảng viên, hồ sơ năng lực
    │   ├── classes/                        # Sinh lớp học phần từng học kỳ
    │   └── enrollments/                    # Sinh điểm số và đăng ký từng học kỳ
    ├── analysis/
    │   ├── run_analysis.py                 # CLI tra cứu CTĐT, tiến độ sinh viên & tỷ lệ tốt nghiệp
    │   └── analysis_helpers.py             # Hàm nghiệp vụ phân tích học bạ & tốt nghiệp
    ├── tools/
    │   ├── run_all.py                      # Pipeline sinh toàn bộ dữ liệu tự động
    │   └── generate_academic_metrics.py    # Tổng hợp chỉ số học vụ toàn khóa
    └── tests/                              # Bộ kiểm thử tự động (Pytest)
```

---

## 3. Bắt đầu nhanh

### Cài đặt môi trường
Khuyến nghị sử dụng Python 3.10+:

```bash
# Tạo và kích hoạt môi trường ảo
python3 -m venv .venv
source .venv/bin/activate       # Trên Linux/macOS
# .venv\Scripts\activate        # Trên Windows

# Cài đặt dependencies
pip install -r requirements.txt
```

### Sinh toàn bộ dữ liệu (Pipeline Execution)
Chạy toàn bộ pipeline từ việc tạo hồ sơ, danh mục đến lớp học phần và điểm số từ HK201 đến HK261:

```bash
python synthetic_data/tools/run_all.py
```

---

## 4. Hướng dẫn thay đổi dữ liệu mô phỏng (Data Customization Guide)

Khi nhận được số liệu khảo sát thực tế từ giảng viên hoặc nhà trường, bạn có thể dễ dàng điều chỉnh dữ liệu bằng cách sửa các file cấu hình tương ứng dưới đây:

### 4.1. Đổi tỷ lệ % điểm thành phần của từng môn
* **File:** [`synthetic_data/generated/academics/assessment.csv`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/generated/academics/assessment.csv)
* **Mô tả:** Chứa tỷ lệ % của từng cột điểm: `quiz`, `lab`, `btl` (Bài tập lớn), `giua_ky`, `cuoi_ky`.
* **Ví dụ:** Muốn môn Cấu trúc dữ liệu (`CO2003`) có 20% Lab, 30% BTL, 50% Cuối kỳ:
  ```csv
  course_id,course_name,credits,course_category,quiz,lab,btl,giua_ky,cuoi_ky
  CO2003,Cấu trúc dữ liệu và giải thuật,4,Specialized,0,20,30,0,50
  ```
  *(Lưu ý: Tổng các cột thành phần của một môn phải bằng 100)*.

---

### 4.2. Đổi độ khó của từng môn cụ thể (Môn "sát thủ" / Môn dễ)
* **File:** [`synthetic_data/config/generator_config.json`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/config/generator_config.json) tại mục `"difficulty" -> "course_overrides"`:
  ```json
  "course_overrides": {
    "MT1003": 0.5,    // Trừ 0.5 điểm nền (Giải tích 1 - môn khó, rớt nhiều)
    "PH1003": 0.5,    // Trừ 0.5 điểm nền (Vật lý 1)
    "CO2003": 0.4,    // Trừ 0.4 điểm nền (DSA)
    "SP1007": -0.3    // Cộng 0.3 điểm nền (Môn kéo điểm)
  }
  ```
* **Tinh chỉnh theo khối môn:** Trong [`synthetic_data/rules/academic_rules.py`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/rules/academic_rules.py) tại hàm `course_mean_score()`, có thể điều chỉnh độ lệch điểm theo tính chất môn (`is_math`, `is_programming`, `is_politics`, `is_english`).

---

### 4.3. Đổi phổ điểm & Phân phối học lực toàn trường
* **File:** [`synthetic_data/config/generator_config.json`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/config/generator_config.json) tại mục `"academic"`:
  ```json
  "academic": {
    "base_scores": [4.0, 5.5, 6.5, 7.8, 9.0],
    "distribution": [0.015, 0.207, 0.302, 0.426, 0.050],
    "subject_sigma": 0.45,
    "score_noise_sigma": 0.35
  }
  ```
  * `base_scores`: Điểm trung bình kỳ vọng ứng với 5 mức năng lực: `[Kém, Yếu/TB, Khá, Giỏi, Xuất sắc]`.
  * `distribution`: Tỷ lệ % sinh viên phân bổ vào 5 mức tương ứng (tổng bằng 1.0).
  * `subject_sigma` & `score_noise_sigma`: Độ phân tán điểm thi quanh điểm kỳ vọng (tăng lên nếu muốn điểm rải rác rộng hơn).

---

### 4.4. Đổi thang điểm chữ & Quy đổi hệ 4 (Grade Scale)
* **File:** [`synthetic_data/config/generator_config.json`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/config/generator_config.json) tại mục `"grade_scale"`:
  ```json
  "grade_scale": {
    "A+": { "min": 9.0, "max": 10.0, "gpa": 4.0 },
    "A":  { "min": 8.5, "max": 8.9,  "gpa": 4.0 },
    "B+": { "min": 8.0, "max": 8.4,  "gpa": 3.5 },
    "B":  { "min": 7.0, "max": 7.9,  "gpa": 3.0 },
    "C+": { "min": 6.0, "max": 6.9,  "gpa": 2.5 },
    "C":  { "min": 5.0, "max": 5.9,  "gpa": 2.0 },
    "D":  { "min": 4.0, "max": 4.9,  "gpa": 1.0 },
    "F":  { "min": 0.0, "max": 3.9,  "gpa": 0.0 }
  }
  ```

---

### 4.5. Đổi chuẩn đầu ra & Tỷ lệ hoàn thành (Tiếng Anh, CTXH, Tốt nghiệp)
* **Ngưỡng xét tốt nghiệp:** Sửa trong [`synthetic_data/config/generator_config.json`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/config/generator_config.json) tại mục `"student_progress" -> "graduation"`:
  * `minimum_for_graduation`: Số tín chỉ tích lũy tối thiểu (mặc định 128 tín chỉ).
  * `min_gpa_for_graduation`: Điểm GPA hệ 4 tối thiểu (mặc định 2.0).
  * `min_ctxh_for_graduation`: Số ngày CTXH tối thiểu (15 ngày).
* **Tỷ lệ đạt Tiếng Anh & tiến độ ngày CTXH theo từng học kỳ:** Sửa trong [`synthetic_data/generators/users/generate_student_profiles.py`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/generators/users/generate_student_profiles.py) tại các bảng xác suất `p_english` và bước cộng ngày CTXH cho từng hệ đào tạo.

---

### 4.6. Đổi danh mục môn học, Số tín chỉ & Điều kiện tiên quyết
* **Danh sách môn & số tín chỉ:** [`synthetic_data/generated/academics/courses.csv`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/generated/academics/courses.csv) (`course_code`, `course_name_vi`, `credits`, `department`).
* **Tiên quyết & Điểm chuẩn qua môn:** [`synthetic_data/generated/academics/course_prerequisites.csv`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/generated/academics/course_prerequisites.csv) (`course_code`, `prerequisite_course_code`, `relation_type`, `min_grade`).

---

### 4.7. Quản lý Danh mục học kỳ & Trạng thái học kỳ hiện tại (`is_active`)
* **File danh mục:** [`synthetic_data/generated/academics/semester.csv`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/generated/academics/semester.csv) (`semester_id`, `semester_code`, `academic_year`, `is_active`).
* **Kỳ hiện tại:** Cờ `is_active = True` được gán duy nhất cho học kỳ hiện tại (**`HK261`**). Tất cả các học kỳ đã hoàn tất (từ `HK201` đến `HK252`) có `is_active = False`.
* **Quy tắc tính GPA kỳ active:** Đối với học kỳ đang hoạt động (`is_active = True`), học kỳ chưa kết thúc nên điểm trung bình học kỳ (`semester_gpa_4`) và CPA tích lũy (`final_gpa_4`) được gán giá trị trống (`NaN`/`NULL`). Khi sang kỳ tiếp theo, hệ thống mới tiến hành chốt GPA học kỳ.

---

## 5. Quy trình chạy cập nhật & Kiểm tra kết quả

Sau khi chỉnh sửa các thông số, thực hiện các lệnh sau để cập nhật lại dữ liệu:

1. **Nếu sửa chuẩn Tiếng Anh / Ngày CTXH / Hồ sơ sinh viên:**
   ```bash
   python synthetic_data/generators/users/generate_student_profiles.py
   ```
2. **Nếu sửa điểm thành phần (`assessment.csv`) hoặc độ khó môn / phổ điểm:**
   Chạy lại các học kỳ cần cập nhật hoặc toàn bộ pipeline:
   ```bash
   python synthetic_data/tools/run_all.py
   ```
3. **Kiểm tra báo cáo tỷ lệ tốt nghiệp (Ví dụ cho khóa K20):**
   ```bash
   python synthetic_data/analysis/run_analysis.py -c K20 -grad
   ```
4. **Chạy kiểm thử đảm bảo tính toàn vẹn của dữ liệu:**
   ```bash
   pytest synthetic_data/tests/
   ```

---

## 6. Kết quả mô phỏng mẫu (Benchmark Khóa K20)

Dữ liệu mô phỏng khóa K20 (1.500 sinh viên) sau khi hoàn tất 8 học kỳ chính thức (HK201 đến HK232):

```text
================================================================================================
============== BÁO CÁO THỐNG KÊ TIẾN ĐỘ & TỶ LỆ TỐT NGHIỆP - KHÓA K20 (KHMT_K20) ===============
================================================================================================
 Khóa tuyển sinh: K20 | Ngành: Cử nhân Khoa học Máy tính | Tổng số sinh viên: 1,500 SV
 Dữ liệu mô phỏng hiện tại: Đến Học kỳ 8 (HK232)
 Đã tốt nghiệp: 714 SV (47.60%) | Chưa tốt nghiệp / Đang nợ chuẩn đầu ra: 786 SV (52.40%)
------------------------------------------------------------------------------------------------
 I. BẢNG PHÂN BỐ TỶ LỆ TỐT NGHIỆP THEO TIẾN ĐỘ HỌC VỤ:
  ★ Tốt nghiệp sớm (Kỳ 7 - 3.5 năm)      HK231    3.5 năm     18 SV      1.20%     Đã mô phỏng
  ● Tốt nghiệp đúng hạn (Kỳ 8 - 4.0 năm) HK232    4.0 năm     696 SV     46.40%    Đã mô phỏng
  ▲ Tốt nghiệp trễ hạn (Kỳ 9 - Kỳ 12)    HK241+   4.5-6.0 năm  -         -         Chưa mô phỏng
  --------------------------------------------------------------------------------------------
  ⚠ Chưa tốt nghiệp / Đang nợ chuẩn đầu ra (tính đến HK232):   786 SV     52.40%
    (Gồm: nợ Khóa luận/môn bắt buộc, nợ chuẩn Tiếng Anh, hoặc thiếu 15 ngày CTXH)
------------------------------------------------------------------------------------------------
 II. THỐNG KÊ CHI TIẾT THEO HỆ ĐÀO TẠO:
  - Đại trà (Tiêu chuẩn):   895 SV  | Tốt nghiệp sớm:  9 (1.01%) | Đúng hạn: 373 (41.68%) | Nợ chuẩn: 513 (57.32%)
  - Chất lượng cao (CLC):   443 SV  | Tốt nghiệp sớm:  6 (1.35%) | Đúng hạn: 243 (54.85%) | Nợ chuẩn: 194 (43.79%)
  - Chương trình Tiên tiến: 162 SV  | Tốt nghiệp sớm:  3 (1.85%) | Đúng hạn:  80 (49.38%) | Nợ chuẩn:  79 (48.77%)
================================================================================================
```

Tỷ lệ tốt nghiệp đúng hạn **46.40%** (và tổng tốt nghiệp đến hết năm 4 là **47.60%**) phản ánh sát với thực tế đào tạo đại học khối ngành kỹ thuật/công nghệ tại ĐHQG-HCM (khoảng 40% – 50% đúng hạn).

---

## 7. Tài liệu chi tiết các phân hệ

- [Cấu trúc chi tiết bộ dữ liệu synthetic_data](synthetic_data/README.md)
- [Quy tắc chương trình và luật học vụ](synthetic_data/rules/README.MD)
- [Tài liệu Generator các học kỳ](synthetic_data/generators/README.MD)
- [Tài liệu Công cụ hỗ trợ & Pipeline](synthetic_data/tools/README.MD)
