# Dữ liệu mô phỏng quản lý đào tạo (Synthetic Academic Data)

`synthetic_data` là bộ dữ liệu mô phỏng toàn diện cho bài toán quản lý đào tạo ngành Computer Science (chuẩn ABET, Trường ĐH Bách Khoa - ĐHQG-HCM): danh mục môn học, chương trình đào tạo, sinh viên, giảng viên, lớp học phần, đăng ký, điểm thành phần và xét tốt nghiệp theo từng học kỳ. Toàn bộ dữ liệu là **dữ liệu tổng hợp (synthetic)**, không phải dữ liệu học vụ thực tế.

---

## 1. Cấu trúc thư mục

```text
synthetic_data/
├── config/      # Cấu hình hồ sơ, phổ điểm, độ khó môn và điều kiện tốt nghiệp
├── data/        # Dữ liệu phụ trợ & tra cứu
├── generated/   # Kết quả dữ liệu CSV chuẩn hóa
│   ├── academics/  # Môn học, CTĐT, khối kiến thức, tiên quyết, đề cương điểm (assessment.csv)
│   ├── users/      # Tài khoản, sinh viên, giảng viên, hồ sơ năng lực (student_profiles.csv)
│   ├── classes/    # Lớp học phần các kỳ (HK201 -> HK232)
│   ├── enrollments/# Điểm và kết quả đăng ký học phần (HK201 -> HK232)
│   └── metrics/    # Chỉ số tích lũy ngoại ngữ, CTXH
├── rules/       # Quy tắc chương trình, luật học vụ và điều kiện học vượt
├── generators/  # Script sinh CTĐT, người dùng, lớp và điểm từng học kỳ
├── analysis/    # Công cụ CLI tra cứu lộ trình và thống kê tốt nghiệp
└── tools/       # Script chạy tự động toàn bộ pipeline
```

| Thư mục | Vai trò | Tài liệu chi tiết |
| --- | --- | --- |
| `config/` | Phân phối hồ sơ/điểm, difficulty môn học và chính sách tốt nghiệp. | [config/generator_config.json](config/generator_config.json) |
| `generated/` | File CSV chuẩn hóa của toàn bộ hệ thống. | Xem mục 2 bên dưới. |
| `rules/` | Xét môn học, tiên quyết, học lại, điều kiện đồ án và mô phỏng điểm. | [rules/README.MD](rules/README.MD) |
| `generators/` | Tạo lớp, phân sinh viên vào lớp và mô phỏng điểm từ HK201 đến HK232. | [generators/README.MD](generators/README.MD) |
| `analysis/` | Tra cứu CTĐT, học bạ sinh viên và báo cáo tỷ lệ tốt nghiệp. | [analysis/run_analysis.py](analysis/run_analysis.py) |
| `tools/` | Điều phối sinh dữ liệu tự động (`run_all.py`) và tính metrics. | [tools/README.MD](tools/README.MD) |

---

## 2. Cấu trúc dữ liệu chuẩn hóa: `generated/` và `rules/`

### 1. `generated/academics/` — Chương trình đào tạo & Đề cương
- `courses.csv`: Danh mục 128 môn học chuẩn hóa (`course_code`, tên tiếng Việt/Anh, số tín chỉ, khoa phụ trách).
- `curriculums.csv`: 7 chương trình đào tạo chính quy cho các khóa từ K20 đến K26.
- `knowledge_blocks.csv`: 20 khối kiến thức chuẩn hóa (Toán - KHTN, Chính trị - Pháp luật, Cơ sở ngành, Bắt buộc ngành, Chuyên ngành, v.v.).
- `program_structures.csv`: 1,105 ánh xạ môn học theo từng CTĐT khóa học, kèm loại môn (`BB`/`TC`), nhóm tự chọn (`Group A/B/C/D`), học kỳ gợi ý.
- `course_prerequisites.csv`: Quan hệ tiên quyết môn học (`TQ`, `KN`, `SH`).
- `semester.csv`: Danh sách học kỳ chuẩn hóa từ HK201 đến HK261 kèm cờ trạng thái `is_active` (chỉ `HK261` là `True` - biểu thị học kỳ hiện tại đang diễn ra, các học kỳ trước từ HK201 đến HK252 là `False`).
- `assessment.csv`: Đề cương tỷ lệ điểm thành phần của các môn học (`quiz`, `lab`, `btl`, `giua_ky`, `cuoi_ky`).

### 2. `generated/users/` — Người dùng & Hồ sơ năng lực
- `user.csv`: Danh sách tài khoản người dùng của toàn hệ thống (11,270 tài khoản).
- `admin.csv`: 10 quản trị viên.
- `lecturer.csv`: Danh sách 209 giảng viên với đơn vị (`department`) và chuyên môn (`specialization`).
- `student.csv`: 11,051 sinh viên trải dài các khóa K20–K26, kèm phân hệ đào tạo (`standard`, `high-quality`, `advanced`).
- `student_profiles.csv`: Hồ sơ năng lực ẩn của 11,051 sinh viên (`academic_level`, `base_score`, `discipline`, `motivation`, `stress`, `english_pass`, `ctxh_days_by_semester`).

### 3. `rules/` — Luật học vụ & Chương trình
- `rules/academic/eligibility_rules.py`:
  - **Điều kiện đăng ký Đồ án tốt nghiệp (`CO4337`):** Tích lũy $\ge 105$ tín chỉ, Đồ án chuyên ngành `CO4029` đạt điểm $\ge 5.5$, điểm trung bình tích lũy $\text{CPA} \ge 2.00$, hoàn thành $\ge 12$ ngày CTXH, đạt chuẩn Ngoại ngữ theo quy định, và đã hoàn thành môn tiên quyết `CO3335` (Thực tập ngoài trường - ngoại trừ diện tốt nghiệp sớm làm đồ án song hành).
  - **Điều kiện xét tốt nghiệp:** Hoàn thành $\ge 128$ tín chỉ CTĐT, $\text{CPA} \ge 2.00$ và đạt $\ge 15$ ngày CTXH.
- `rules/academic/retake_rules.py`:
  - Cơ chế học lại môn rớt (`passed == False`) và học cải thiện điểm (`retaken = True`, `retake_bonus = +2.0`).
  - Tự động kích hoạt đăng ký học cải thiện điểm cho sinh viên có $\text{CPA} < 2.00$ hoặc sinh viên có điểm Đồ án Chuyên ngành `CO4029 < 5.5` (cho phép học cải thiện `CO4029` để đủ chuẩn làm ĐATN).
- `rules/academic/curriculum_rules.py`: Các quy tắc ràng buộc chương trình, cấu trúc tự chọn (Group A/B/C) và lộ trình tốt nghiệp sớm 3.5 năm.

### 4. `generated/classes/` & `generated/enrollments/`
- `classes/class_hk*.csv`: 10,883 lớp học phần mở thực tế theo học kỳ từ HK201 đến HK261 (đã tự động lược bỏ các lớp rỗng qua `prune_empty_classes.py`), phân tách rõ nhóm lớp (`L01..L23` đại trà, `CC01..CC12` chất lượng cao, `TT01..TT05` tiên tiến), mở rộng lớp ĐATN và trả nợ cho các khóa trên tại kỳ trễ hạn.
- `enrollments/enrollment_hk*.csv`: 447,645 bản ghi đăng ký học phần và kết quả học tập chi tiết (điểm thành phần, `final_score`, `gpa_4`, `letter_grade`, `status`). Sinh viên CLC và Tiên tiến được miễn toàn bộ 4 học phần tiếng Anh theo điểm 12.0.

---

## 3. Quy trình tạo dữ liệu (Pipeline)

```text
academics/generate_semester.py + generate_curriculum.py ──> generated/academics/
users/generate_users.py ──> student.csv + lecturer.csv
users/generate_student_profiles.py ──> student_profiles.csv
classes/generate_class_hk*.py ──> class_hk*.csv
enrollments/generate_enrollment_hk*.py ──> enrollment_hk*.csv
```

Chạy toàn bộ pipeline từ thư mục gốc dự án:

```bash
source .venv/bin/activate
python synthetic_data/tools/run_all.py
```

Lệnh trên tạo danh mục và hồ sơ sinh viên trước, sau đó chạy tuần tự từng cặp `class_hk*` → `enrollment_hk*` theo thứ tự từ **HK201 đến HK261**, đảm bảo lịch sử học tập của kỳ trước là cơ sở xét tiên quyết cho kỳ sau.

---

## 4. Hướng dẫn thay đổi dữ liệu theo số liệu cụ thể

Khi cần tinh chỉnh số liệu theo thông số thực tế do giảng viên hoặc phòng đào tạo cung cấp:

### 4.1. Đổi tỷ lệ % điểm thành phần của từng môn
* **Vị trí:** [`synthetic_data/generated/academics/assessment.csv`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/generated/academics/assessment.csv)
* **Cột chỉnh:** `quiz`, `lab`, `btl`, `giua_ky`, `cuoi_ky` (tổng luôn bằng 100).
* **Công thức tính điểm tổng kết:**
  $$\text{final\_score} = \frac{\sum (\text{điểm thành phần} \times \text{tỷ lệ})}{100}$$

### 4.2. Đổi độ khó & Điều chỉnh điểm môn học (Course Difficulty Overrides)
* **Vị trí:** [`synthetic_data/config/generator_config.json`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/config/generator_config.json) tại mục `"difficulty" -> "course_overrides"`:
  * Thang đo `[-1.0, 1.0]`:
    * **Giá trị dương (`> 0`)**: Môn dễ $\rightarrow$ **Cộng thêm điểm** (ví dụ `"SP1007": 0.4`, `"PE1003": 0.5`).
    * **Giá trị âm (`< 0`)**: Môn khó $\rightarrow$ **Trừ bớt điểm** (ví dụ `"MT1003": -0.5`, `"CO2003": -0.5`).
    * **Giá trị `0.0` (Mặc định)**: Môn chuẩn trung bình (không cộng không trừ).
* **Quy tắc theo khối môn:** Điều chỉnh trong hàm `course_mean_score()` tại [`synthetic_data/rules/academic_rules.py`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/rules/academic_rules.py).

### 4.3. Đổi phân phối phổ điểm & Học lực toàn trường
* **Vị trí:** [`synthetic_data/config/generator_config.json`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/config/generator_config.json) tại mục `"academic"`:
  * `base_scores`: `[4.0, 5.5, 6.5, 7.8, 9.0]` (điểm trung bình kỳ vọng ứng với 5 mức năng lực).
  * `distribution`: `[0.015, 0.207, 0.302, 0.426, 0.050]` (tỷ lệ sinh viên mỗi mức, tổng bằng 1.0).
  * `score_noise_sigma`: Độ biến thiên ngẫu nhiên của điểm thi.

### 4.4. Đổi thang điểm chữ & Hệ 4 (Grade Scale)
* **Vị trí:** [`synthetic_data/config/generator_config.json`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/config/generator_config.json) tại mục `"grade_scale"`:
  * Điểm đạt (Pass): `final_score >= 4.0` (khác F). Rớt môn: `final_score < 4.0` (điểm F).

### 4.5. Đổi chuẩn đầu ra tốt nghiệp & Tiến độ Tiếng Anh / CTXH
* **Điều kiện tốt nghiệp:** Cấu hình trong `generator_config.json` mục `"student_progress" -> "graduation"`:
  * `minimum_for_graduation`: Tối thiểu 128 tín chỉ.
  * `min_gpa_for_graduation`: Tối thiểu 2.0 GPA hệ 4.
  * `min_ctxh_for_graduation`: Tối thiểu 15 ngày CTXH.
* **Tiến độ tích lũy Tiếng Anh & CTXH:** Tinh chỉnh các bảng xác suất trong [`synthetic_data/generators/users/generate_student_profiles.py`](file:///home/nhan/Documents/DACN/synthetic-data/synthetic_data/generators/users/generate_student_profiles.py).

---

## 5. Quy trình chạy cập nhật & Kiểm tra kết quả

Sau khi chỉnh sửa, thực hiện:

1. **Cập nhật lại hồ sơ sinh viên (nếu sửa Tiếng Anh / CTXH / năng lực nền):**
   ```bash
   python synthetic_data/generators/users/generate_student_profiles.py
   ```
2. **Cập nhật lớp và điểm toàn bộ các kỳ:**
   ```bash
   python synthetic_data/tools/run_all.py
   ```
3. **Xem báo cáo phân tích tốt nghiệp (Khóa K20):**
   ```bash
   python synthetic_data/analysis/run_analysis.py -c K20 -grad
   ```
4. **Chạy kiểm thử hệ thống:**
   ```bash
   pytest synthetic_data/tests/
   ```

---

## 6. Kết quả mô phỏng thực tế (Khóa K20 sau 12 học kỳ đào tạo)

```text
================================================================================================
============== BÁO CÁO THỐNG KÊ TIẾN ĐỘ & TỶ LỆ TỐT NGHIỆP - KHÓA K20 (KHMT_K20) ===============
================================================================================================
 Khóa tuyển sinh: K20 | Tổng số sinh viên: 1,500 SV | Học kỳ quan sát: HK201 -> HK252 (12 kỳ)
 Đã tốt nghiệp: 1,402 SV (93.47%) | Thôi học / Quá hạn 12 kỳ: 98 SV (6.53%) | Đang học: 0 SV
------------------------------------------------------------------------------------------------
 ★ Tốt nghiệp sớm (Kỳ 7 - 3.5 năm):       18 SV  (1.20%)  - Nhóm học vượt KLTN (CO4337), đạt 128 TC
 ● Tốt nghiệp đúng hạn (Kỳ 8 - 4.0 năm): 1056 SV (70.40%) - Hoàn tất CTĐT + Tiếng Anh + >= 15 ngày CTXH
 ▲ Tốt nghiệp trễ hạn (Kỳ 9–12):         328 SV (21.87%)  - Trả nợ môn, tích lũy đủ CTXH & học cải thiện GPA
   - Trễ 1 kỳ (HK241):                   162 SV (10.80%)
   - Trễ 2 kỳ (HK242):                    94 SV  (6.27%)
   - Trễ 3 kỳ (HK251):                    53 SV  (3.53%)
   - Trễ 4 kỳ (HK252):                    19 SV  (1.27%)
 ✖ Buộc thôi học / Quá hạn đào tạo:       98 SV  (6.53%)  - Không kịp đạt chuẩn GPA/tín chỉ sau 6 năm
------------------------------------------------------------------------------------------------
 Chi tiết Khóa K20 Hệ Đại trà (Standard - 894 SV):
  - Tốt nghiệp sớm:        5 SV (0.56%)
  - Tốt nghiệp đúng hạn: 511 SV (57.16%)
  - Trễ 1 kỳ:            154 SV (17.23%)
  - Trễ 2 kỳ:             91 SV (10.18%)
  - Trễ 3 kỳ:             53 SV  (5.93%)
  - Trễ 4 kỳ:             19 SV  (2.13%)
  - Không tốt nghiệp:     61 SV  (6.82%)  (gồm 53 SV quá hạn 12 kỳ và 8 SV thôi học giữa chừng)
------------------------------------------------------------------------------------------------
 Chi tiết theo hệ đào tạo:
  - Đại trà (Tiêu chuẩn):   894 SV  | Tốt nghiệp: 833 (93.18%) | Thôi học / Quá hạn: 61 (6.82%)
  - Chất lượng cao (CLC):   466 SV  | Tốt nghiệp: 432 (92.70%) | Thôi học / Quá hạn: 34 (7.30%)
  - Chương trình Tiên tiến: 140 SV  | Tốt nghiệp: 137 (97.86%) | Thôi học / Quá hạn:  3 (2.14%)
------------------------------------------------------------------------------------------------
 Chất lượng tốt nghiệp: 100% sinh viên tốt nghiệp có GPA_4 >= 2.0 (không có sinh viên dưới chuẩn)
 Phân loại bằng K20: Xuất sắc: 6.0% | Giỏi: 20.3% | Khá: 42.1% | Trung bình: 31.6%
================================================================================================
```

Tỷ lệ tốt nghiệp chung đạt **93.47%**, phân bổ tiến độ tốt nghiệp bám sát thực tế đào tạo và 100% sinh viên tốt nghiệp đạt chuẩn $\text{GPA}_4 \ge 2.0$.
