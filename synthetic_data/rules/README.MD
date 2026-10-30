# Quy tắc chương trình và học vụ

Thư mục `rules` chứa hai module dùng chung cho các generator trong
`synthetic_data/generators/`. Chúng không trực tiếp tạo CSV lớp học hoặc điểm;
chúng cung cấp quy tắc để generator quyết định **môn nào được mở/đăng ký** và
**điểm được mô phỏng theo độ khó nào**.

```text
academics CSV ──> curriculum_rules.py ──> generator class/enrollment
history CSV   ──> academic_rules.py   ──> generator class/enrollment
                                              │
                                              └──> generated/classes,
                                                   generated/enrollments
```

## `curriculum_rules.py` — quy tắc chương trình đào tạo

Module này đọc dữ liệu từ `synthetic_data/generated/academics/` (và `synthetic_data/rules/additional_course_rules.csv`), trả về danh sách
môn học, nhóm tự chọn, số tín chỉ và độ khó. Nó là nguồn quy tắc chung để các
generator class và enrollment dùng cùng một chương trình đào tạo.

### Dữ liệu đầu vào

| File | Vai trò |
| --- | --- |
| `courses.csv` | Danh mục 128 môn học chuẩn hóa, tên môn, số tín chỉ và khoa/bộ môn phụ trách. |
| `program_structures.csv` | Môn bắt buộc (`BB`), tự chọn (`TC`), nhóm tự chọn (`Group A/B/C/D`) theo CTĐT khóa. |
| `additional_course_rules.csv` | Môn có thể học bổ sung và điều kiện áp dụng (nằm trong `rules/`). |
| `course_prerequisites.csv` | Quan hệ môn học tiên quyết (`TQ`), học trước (`KN`), song hành (`SH`). |
| `assessment.csv` | Đề cương tỷ lệ % điểm thành phần (`quiz`, `lab`, `btl`, `giua_ky`, `cuoi_ky`). |

### Hàm quan trọng

- `curriculum_courses(semester)`: trả các môn bắt buộc của một học kỳ, theo
  `course_order`.
- `additional_courses(semester)`: trả môn có thể học thêm tại học kỳ đó; mặc
  định không lấy rule chỉ dành cho lộ trình tốt nghiệp sớm. Có thể truyền
  `early_graduation=True`, `early_graduation_only=True` và `cohort` để lấy đúng
  các môn sớm áp dụng cho một khóa.
- `free_elective_courses()`, `management_elective_courses()` và
  `group_c_elective_courses()`: trả các lựa chọn môn tự chọn tương ứng.
- `course_catalog()`: tạo ba ánh xạ `course_code → course_name`, `credits` và
  `difficulty`. Generator enrollment sử dụng `difficulty` để điều chỉnh điểm
  mô phỏng: độ khó cao hơn làm điểm thành phần có xu hướng thấp hơn.
- `get_department(course_code)`: phân môn về `Triet`, `DaiCuong` hoặc
  `ChuyenNganh`; generator class dùng kết quả này để chọn giảng viên phù hợp.

### Hằng số chính

- `MAX_CREDITS = 22`: trần tín chỉ mỗi sinh viên trong một học kỳ.
- `TUITION_BASELINE_CREDITS = 18`: mốc tín chỉ generator cố gắng bổ sung cho
  sinh viên đủ điều kiện.

## `academic_rules.py` & package `academic/` — quy tắc học vụ và điều kiện đăng ký

Để đảm bảo khả năng bảo trì, kiểm thử và mở rộng, toàn bộ quy tắc học vụ được tái cấu trúc thành package chuyên biệt `synthetic_data/rules/academic/` chia thành **6 nhóm nghiệp vụ cốt lõi**, trong khi `academic_rules.py` đóng vai trò **Facade Gateway** đảm bảo tương thích ngược 100% cho toàn bộ các file generator hiện hữu:

```text
synthetic_data/rules/
├── academic/                          # Package chứa các rule chuyên biệt
│   ├── __init__.py                    # Re-export API của package
│   ├── common.py                      # Tiện ích chung, hash seed, load lịch sử
│   ├── config.py                      # Load & validate generator_config.json
│   ├── profile_rules.py               # [Nhóm 1] Hồ sơ SV, CTXH, tiếng Anh, dropout
│   ├── scoring_rules.py               # [Nhóm 2] Điểm số thành phần, thang chữ, GPA/CPA
│   ├── standing_rules.py              # [Nhóm 3] Kỷ luật, thôi học vụ, thời gian học
│   ├── retake_rules.py                # [Nhóm 4] Trả nợ môn rớt & học cải thiện điểm
│   ├── eligibility_rules.py           # [Nhóm 5] Tiên quyết, học trước, điều kiện môn
│   └── allocation_rules.py            # [Nhóm 6] Phân bổ lớp & phân công giảng viên
│
├── academic_rules.py                  # [FACADE GATEWAY] Re-export đầy đủ API cũ
├── curriculum_rules.py                # Quy tắc chương trình khung các kỳ
└── README.MD                          # Tài liệu kiến trúc
```

### Chi tiết 6 nhóm nghiệp vụ trong `rules/academic/`:

1. **`profile_rules.py` (Đặc tính & Hồ sơ sinh viên):**
   - Sinh đặc tính cá nhân (`discipline`, `motivation`, `stress`, `social_activity`), học lực (`academic_level`), điểm gốc (`base_score`).
   - Mô phỏng tích lũy ngày CTXH (`_generate_ctxh_progress`, `ctxh_days_before_semester`).
   - Tiến trình đạt chuẩn tiếng Anh (`_generate_english_eligibility_progress`).
   - Sàng lọc ứng viên học vượt / tốt nghiệp sớm (`select_early_graduation_candidates`, `wants_acceleration`).
   - Mô phỏng thôi học tự nguyện (`_generate_voluntary_dropout`) với cơ chế miễn trừ rủi ro bỏ học vì kinh tế cho hệ CLC và Tiên tiến.

2. **`scoring_rules.py` (Mô hình điểm số & GPA):**
   - Tính điểm kỳ vọng môn học dựa trên tương quan năng lực và độ khó (`course_mean_score`).
   - Sinh điểm ngẫu nhiên có kiểm soát sai số và bonus học lại (`generate_observed_score`).
   - Quy đổi điểm 10 sang thang chữ và GPA thang 4 (`convert_score_to_grade`).
   - Chấm điểm chi tiết các cột thành phần BT, BTL, GK, CK (`score_course_components`).
   - Tổng hợp GPA học kỳ và CPA tích lũy (`add_gpa_summaries`).

3. **`standing_rules.py` (Quy chế học vụ, Kỷ luật & Buộc thôi học):**
   - Chuyển đổi và định vị chỉ mục học kỳ (`semester_index`, `semester_from_index`).
   - Kiểm soát thời gian đào tạo: chuẩn 8 kỳ (`STANDARD_SEMESTERS`), kéo dài tối đa 4 kỳ (`MAX_LATE_SEMESTERS`), quá hạn 12 kỳ (`DISMISSAL_AFTER_SEMESTERS`).
   - Xử lý thôi học vụ quá hạn (`is_academic_dismissal`, `get_academic_dismissal_semester`).
   - Xử lý tạm dừng học vụ do nợ tín chỉ liên tiếp (`academic_suspension_semesters`).

4. **`retake_rules.py` (Học lại, Trả nợ môn & Cải thiện điểm):**
   - Ràng buộc trần tín chỉ học lại (`filter_retake_demand_by_credit_limit`): tối đa 1 môn / 4.0 TC ở kỳ 1–8; tối đa 22.0 TC ở kỳ 9–12.
   - Thuật toán tự động học lại cải thiện điểm D/D+ cho sinh viên cuối khóa có GPA < 2.0 (`generate_grade_improvement_retakes`) đảm bảo tổng tải $\le 22.0$ tín chỉ.

5. **`eligibility_rules.py` (Điều kiện tiên quyết & Tiến độ môn học):**
   - Thẩm định môn tiên quyết (`TQ`), học trước (`KN`), song hành (`SH`).
   - Kiểm tra miễn giảm Anh văn 1 (`can_skip_la1003`) và chuẩn ngoại ngữ ra trường (`is_english_passed`).
   - Tính toán danh sách môn đủ điều kiện mở lớp và đăng ký (`calculate_eligibility`, `calculate_eligibility_for_schedule`).
   - Quản lý hạn ngạch môn tự chọn nhóm C (`GROUP_C_CREDIT_LIMIT = 15`) và môn tự do (`FREE_CREDIT_LIMIT = 9`).

6. **`allocation_rules.py` (Phân bổ danh sách lớp & Giảng viên):**
   - Cân bằng sĩ số các lớp học phần (`balanced_class_sizes`).
   - Phân công giảng viên bộ môn phụ trách lớp xoay vòng công bằng (`assign_balanced_lecturers`).
   - Ghép sinh viên vào từng lớp học phần theo đúng hệ (`allocate_course_rosters`).

Module cũng cung cấp rule dùng chung để tạo hồ sơ sinh viên, tính điểm môn,
noise, grade và GPA. Tham số được đọc từ
`synthetic_data/config/generator_config.json`; generator lớp/đăng ký dùng chung
một cấu hình để điều chỉnh nhất quán giữa các học kỳ.

### Cấu hình hồ sơ và điểm

- Phân phối `family_income`, `financial_pressure`, `living_condition`,
  personality và academic level có thể chỉnh trong JSON. Các phân phối phải
  không âm và tổng bằng `1.0`.
- `academic.base_scores` ánh xạ academic level 1–5 sang điểm nền; `math_level`
  và `english_level` được sinh từ `academic_level` cộng nhiễu Normal rồi giới
  hạn trong khoảng 1–5.
- `personality_weights` là trọng số cho discipline, motivation, stress và
  social activity sau khi chuẩn hóa trait về `[-1, 1]`. Mặc định social activity
  không ảnh hưởng trực tiếp tới điểm.
- `difficulty.course_overrides` cho phép đặt difficulty từng `course_code` theo
  thang 1–5. Môn không có override dùng cột `difficulty` trong `course.csv`,
  chuẩn hóa theo `catalog_min`/`catalog_max`. Difficulty trừ điểm; mức trừ giảm
  khi academic/personality strength cao (academic level, discipline, motivation
  cao hoặc stress thấp).
- Ví dụ: đặt `"CO1005": 4` trong `course_overrides` để gán môn CO1005 mức 4
  (mức 5 là khó nhất). Để giữ mức danh mục, không thêm môn vào map override.
- `calibration_targets` chỉ là khoảng để đánh giá kết quả GPA sau khi sinh,
  không ép sinh viên vào nhóm GPA.
- `noise` điều chỉnh tỷ lệ Normal/high-deviation, sigma và hướng lệch. `seed`
  giúp hồ sơ sinh viên có thể tái tạo giữa các lần chạy.
- `grade_scale` dùng khoảng lower-inclusive, upper-exclusive; riêng mốc tối đa
  được tính vào grade cuối. F dưới 4.0 là trượt; từ 4.0 trở lên là qua môn.
  `retake_bonus` được áp dụng khi sinh viên học lại môn (bao gồm trả nợ môn F hoặc học lại cải thiện điểm D/D+), mặc định cộng +2.0 điểm kỳ vọng để mô phỏng sự tích lũy kiến thức và nỗ lực cải thiện điểm.

Chạy `python synthetic_data/tools/add_base_score.py` để tạo lại
`student_base_score.csv` cùng các trường hồ sơ. Khi thay đổi rule hoặc config,
chạy `python synthetic_data/tools/run_all.py` để sinh lại các học kỳ nhất quán.

### Điều kiện tiến độ, đồ án, CTXH và dropout

`student_progress` cấu hình các kỳ được theo dõi, kỳ bắt đầu theo khóa, ngưỡng
CTXH, xác suất tiếng Anh ban đầu/chuyển trạng thái và chính sách dropout/tốt
nghiệp. Profile xuất ra `english_pass` ban đầu,
`english_eligibility_by_semester` dạng JSON array với trạng thái tiếng Anh chỉ
chuyển từ chưa đạt sang đạt, và `ctxh_days_by_semester` dạng JSON array với
ngày CTXH cộng dồn. Xác suất tiếng Anh ban đầu và xác suất chuyển theo mỗi kỳ
cùng phụ thuộc background, English level, academic level và personality; các
trọng số được cấu hình trong `student_progress.english`.

**Tăng ngày CTXH theo hệ đào tạo (`program_expected_days_per_semester`):**
Cấu hình trong `generator_config.json` cho phép phân bổ kỳ vọng ngày CTXH tích lũy mỗi học kỳ theo hệ đào tạo:
- Đại trà (`standard`): 1.6 – 2.4 ngày/kỳ (đạt mốc 15 ngày quanh kỳ 7–8).
- Chất lượng cao (`high-quality`): 2.5 – 3.5 ngày/kỳ (đạt mốc 15 ngày sớm ở kỳ 5–6).
- Tiên tiến (`advanced`): 2.8 – 4.0 ngày/kỳ (đạt mốc 15 ngày sớm ở kỳ 5–6).
Cơ chế này đảm bảo sinh viên CLC và Tiên tiến có đủ điều kiện ngày CTXH để làm đồ án tốt nghiệp và xét tốt nghiệp sớm (lộ trình 3.5 năm).

**Quy định đồ án và tốt nghiệp:**
Các môn đồ án trong `thesis_course_codes` bị loại khỏi eligibility nếu tiếng
Anh chưa đạt hoặc CTXH tích lũy trước kỳ học chưa đủ 12 ngày. Tốt nghiệp yêu cầu
đủ 128 tín chỉ, $\ge 15$ ngày CTXH, chuẩn tiếng Anh, điểm trung bình tích lũy $\text{GPA}_4 \ge 2.0$, các môn `required` trong curriculum và mã đồ án tốt
nghiệp cấu hình. Nếu đến kỳ có môn đồ án nhưng chưa đủ điều kiện, profile có
xác suất cấu hình được (mặc định 80%) không đăng ký môn nào trong kỳ đó, mô
phỏng việc phải chờ và tốt nghiệp trễ.

**Chính sách thôi học (Dropout):**
- **Buộc thôi học do học vụ / quá hạn:** Khi sinh viên học vượt quá thời gian tối đa (12 học kỳ) hoặc có hai kỳ liên tiếp dưới 10 tín chỉ pass.
- **Thôi học tự nguyện (`_generate_voluntary_dropout`):** Dùng xác suất trong nhóm background khó khăn / học lực thấp. **Đặc biệt, sinh viên thuộc hệ Chất lượng cao (`high-quality`) và Tiên tiến (`advanced`) được miễn trừ hoàn toàn nguy cơ thôi học tự nguyện do kinh tế** (hàm trả về `None, None`), phản ánh đúng thực tế gia đình có điều kiện kinh tế vững vàng khi theo học các hệ này. Nhờ đó, tỷ lệ thôi học ở CLC và Tiên tiến được giữ ở mức cực thấp (0% ở các khóa bình thường).

### Cơ chế học lại cải thiện điểm (Grade Improvement Retake)

Nhằm đảm bảo chuẩn đầu ra $\text{GPA}_4 \ge 2.0$ để tốt nghiệp:
- **Điều kiện kích hoạt:** Ở các học kỳ muộn (Kỳ 7, 8 hoặc giai đoạn kéo dài Kỳ 9–12), nếu sinh viên có GPA 4 tích lũy dự kiến $< 2.0$, hệ thống tự động cho phép sinh viên đăng ký học lại 1–2 môn đã đạt nhưng có điểm thấp nhất (điểm D hệ 1.0 hoặc D+ hệ 1.5) với cờ `retaken = True`.
- **Cộng điểm học lại:** Lần học cải thiện được hưởng `retake_bonus = 2.0` giúp điểm số mới cao hơn rõ rệt (thường đạt B, B+, A).
- **Cập nhật CPA:** Điểm thang 4 cao nhất giữa các lần học sẽ thay thế điểm cũ, kéo GPA tích lũy của sinh viên vượt mốc 2.0 để tốt nghiệp hợp lệ.
- **Ràng buộc trần tín chỉ (`filter_retake_demand_by_credit_limit`):**
  * Trong các kỳ học chính khóa (Kỳ 1–8): Sinh viên đã có 14–18 tín chỉ môn chính khóa, do đó môn học lại được giới hạn tối đa 1 môn / 4.0 tín chỉ nhằm đảm bảo tổng tải học tập mỗi kỳ không vượt trần quy chế ($\le 22.0$ tín chỉ).
  * Trong các kỳ kéo dài (Kỳ 9–12): Sinh viên không còn môn chính khóa theo lớp nên được phép đăng ký học lại tối đa 22.0 tín chỉ (lên đến 6 môn) để kịp hoàn tất trả nợ tốt nghiệp.
  * Trong hàm `generate_grade_improvement_retakes` (`academic_rules.py`): Kiểm tra tải tín chỉ hiện có của sinh viên trong kỳ (`current_credits`), chỉ cho phép đăng ký cải thiện nếu `current_credits + candidate_credits <= 22.0`.

`generate_academic_metrics.py` tạo tiến độ từng kỳ, metric từng sinh viên (bổ sung cột `gpa_10` tích lũy),
phân phối điểm theo course/toàn trường và tổng hợp dropout/tốt nghiệp. Mẫu số
chỉ gồm sinh viên có enrollment trong các kỳ đã sinh; điểm chưa chấm ở kỳ đang
diễn ra bị loại khỏi phân phối điểm.

Khi tạo profile, `add_base_score.py` đánh dấu 5% số sinh viên có điểm cao nhất
trong top 1% của các khóa K23–K26 theo academic level và personality đã chuẩn
hóa. Việc chọn ổn định theo seed và được lưu ở `early_graduation_candidate`.
Profile được đánh dấu có thể học các môn bổ sung theo lộ trình HK6–HK7; việc
tốt nghiệp sớm vẫn phụ thuộc vào qua môn và đủ điều kiện tiếng Anh/CTXH.

### Lịch sử học tập

`load_history(semesters)` đọc các cặp file sau, sau đó ghép theo `class_id` để
bổ sung `course_code` cho mỗi đăng ký:

- `synthetic_data/generated/enrollments/enrollment_hk*.csv`
- `synthetic_data/generated/classes/class_hk*.csv`

Vì vậy, khi chạy theo thứ tự thời gian, học kỳ trước phải được sinh xong trước
học kỳ sau. `tools/run_all.py` đã thực hiện đúng thứ tự này.

### Hàm xét môn chính

`calculate_eligibility_for_schedule(...)` là hàm được các generator học kỳ
sau sử dụng nhiều nhất. Với từng sinh viên, hàm:

1. Tách môn đã đậu và môn trượt từ lịch sử điểm.
2. Đưa môn trượt cần học lại vào ưu tiên đầu tiên.
3. Bổ sung môn theo kế hoạch của khóa (`scheduled_courses`).
4. Chỉ chọn môn thỏa tiên quyết (`relation_type = "TQ"` trong
   `course_prerequisite.csv`) và không vượt 22 tín chỉ.
5. Hoàn thành yêu cầu tín chỉ tự chọn bắt buộc, nếu generator truyền các nhóm
   và mốc tín chỉ vào.
6. Có thể thêm môn quản lý, tự chọn tự do hoặc nhóm C để tiến gần mốc 18 tín
   chỉ, với lựa chọn xác định theo mã sinh viên.

Hàm trả về:

```python
eligibility, failed
```

- `eligibility`: `{student_id: [course_code, ...]}` — danh sách môn được phép
  đăng ký ở học kỳ đang sinh.
- `failed`: `{student_id: {course_code, ...}}` — các môn trượt, dùng để xác
  định học lại và điều chỉnh cách sinh điểm ở một số generator.

`calculate_eligibility(...)` là phiên bản cũ, chuyên cho bối cảnh HK241; các
generator mới nên ưu tiên `calculate_eligibility_for_schedule(...)`.

### Các ngoại lệ và tính lặp lại

- Sinh viên có thể được miễn `LA1003` theo `can_skip_la1003()` dựa trên điểm
  nền và một giá trị băm từ mã sinh viên.
- `wants_acceleration()` xác định sinh viên có xu hướng học nhanh khi
  `base_score` từ 8.0 trở lên.
- Các hàm chọn môn tự chọn sử dụng SHA-256 từ `student_id`; vì thế cùng dữ liệu
  đầu vào sẽ tạo lựa chọn ổn định qua các lần chạy, không thay đổi ngẫu nhiên.

## Liên hệ với tạo lớp và sinh điểm

| Giai đoạn | Rule được dùng | Kết quả |
| --- | --- | --- |
| Tạo class | Cả hai module | Chọn môn cần mở theo chương trình và sinh viên đủ điều kiện; phân bộ môn để gán giảng viên. |
| Tạo enrollment | Cả hai module | Chọn sinh viên/môn, kiểm tra học lại, tiên quyết và tín chỉ. |
| Sinh điểm | `academic_rules.py` và `generator_config.json` | Dùng profile academic/personality, subject ability, difficulty đã chuẩn hóa, noise cấu hình được, grade scale và trạng thái học lại. |

Enrollment mới bổ sung `course_id`, `semester`, `retaken`, `letter_grade`,
`gpa_4`, `passed`, `semester_gpa_4` và `final_gpa_4`; `status` vẫn được giữ để
các rule lịch sử tiếp tục hoạt động. GPA học kỳ được tính theo tín chỉ đăng ký;
GPA tích lũy chỉ tính môn đã qua, theo tín chỉ và không đếm lặp course_code.
HK261 đang diễn ra nên grade/GPA học kỳ để trống, GPA tích lũy vẫn phản ánh các
học kỳ đã hoàn tất.

Khi thay đổi CSV danh mục, file config hoặc logic trong hai module này, hãy chạy lại
`python synthetic_data/tools/run_all.py` để tái tạo dữ liệu class và enrollment
nhất quán.
