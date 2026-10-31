# BỘ NGUYÊN TẮC SINH DỮ LIỆU HỌC THUẬT (SYNTHETIC DATA GENERATION RULES)

Tài liệu này định nghĩa toàn bộ quy chuẩn, ràng buộc nghiệp vụ học vụ và quy trình kiểm thử bắt buộc khi phát triển, sửa đổi hoặc chạy các generator trong `synthetic_data/generators/`.

---

## 1. NGUYÊN TẮC CÔNG SUẤT VÀ SĨ SỐ LỚP HỌC (CLASS CAPACITY & BALANCING)

1. **Công suất tối đa (`max_capacity`)**:
   - Lớp chuyên ngành (`CO*`), cơ sở ngành, khoa học cơ bản (`MT*`, `PH*`, `CH*`), ngoại ngữ (`LA*`), thể chất (`PE*`), quân sự (`MI*`): **`max_capacity = 40` sinh viên/lớp**.
   - Lớp Lý luận Chính trị (`SP*`): **`max_capacity = 120` sinh viên/lớp** (giảng đường lớn).
2. **Tuyệt đối KHÔNG có lớp vượt quá `max_capacity`**:
   - Mọi sinh viên khi đăng ký lớp học phần phải tuân thủ nghiêm ngặt sĩ số hiện tại $< \text{max\_capacity}$.
   - Khi xếp học cải thiện điểm hoặc học ghép, phải kiểm tra sĩ số thời gian thực (`Counter`) và chọn lớp còn chỗ trống, ưu tiên cân bằng tải.
3. **Cân bằng tải lớp học phần (`balanced_class_sizes`)**:
   - Khi có nhu cầu $N$ sinh viên, số lớp cần mở là $K = \lceil N / \text{max\_capacity} \rceil$.
   - Sinh viên phải được chia đều giữa các lớp (ví dụ: 45 sinh viên $\rightarrow$ 2 lớp sĩ số 23 và 22, không được tạo 1 lớp 40 và 1 lớp 5).
4. **Tuyệt đối KHÔNG lưu giữ lớp rỗng (0 sinh viên)**:
   - Mọi lớp học phần trong bảng `classes` bắt buộc phải có sinh viên đăng ký thực tế.
   - Bắt buộc chạy `synthetic_data/tools/prune_empty_classes.py` sau khi sinh enrollment để xóa sạch các lớp mở dự phòng nhưng không có sinh viên đăng ký.

---

## 2. NGUYÊN TẮC PHÂN BỔ DẢI LỚP ĐỘC LẬP (OFFSET CLASS SLICE ALLOCATION)

Khi có nhiều nhóm đối tượng sinh viên cùng đăng ký một môn học trong cùng một học kỳ:
- **Nguyên tắc phân chia dải lớp (Slice Partitioning)**:
  1. **Slice 1 (Đầu dải lớp)**: Sinh viên tốt nghiệp sớm / Học vượt $\rightarrow$ Lấy `class_ids[0 : N_early]`.
  2. **Slice 2 (Giữa dải lớp)**: Sinh viên chính khóa học theo kỳ / Tự chọn ngành Group C $\rightarrow$ Lấy `class_ids[N_early : N_early + N_group_c]`.
  3. **Slice 3 (Cuối dải lớp)**: Sinh viên năm cuối học tự chọn tự do (Free electives) / Sinh viên học ghép $\rightarrow$ Lấy `class_ids[-N_free:]`.
- **Cấm kỵ**: Không được sử dụng `class_ids[:len(sizes)]` hoặc `class_ids[-len(sizes):]` đồng thời cho 2 nhóm sinh viên khác nhau vì sẽ gây chồng chéo và tràn sĩ số lớp.

---

## 3. NGUYÊN TẮC ĐỊNH BIÊN VÀ TẢI GIẢNG DẠY (LECTURER ALLOCATION)

1. **Định mức giảng dạy chuẩn**:
   - Mức tải trung bình của giảng viên trong các học kỳ chính thức phải đạt từ **4 – 5 lớp / giảng viên / học kỳ**.
   - Tổng định biên toàn trường trong `generator_config.json` là **209 giảng viên** (trong đó Khoa CNTT có 150 GV để gánh ~670 lớp chuyên ngành mỗi kỳ).
2. **Phân công đúng Khoa / Bộ môn và Chuyên môn**:
   - Giảng viên Khoa KH&KT Máy tính chỉ giảng dạy môn `CO*`.
   - Các môn đại cương Toàn ngành chia đều cho toàn bộ giảng viên trong khoa.
   - Các môn tự chọn chuyên sâu (Group C) ưu tiên phân công cho giảng viên có `specialization` khớp với chuyên ngành của môn học.
   - Giảng viên Toán, Lý, Hóa, Ngoại ngữ, Triết, Thể chất thuộc Khoa/Bộ môn tương ứng chịu trách nhiệm môn học của đơn vị mình.
3. **Cân bằng tải xoay vòng**:
   - Sử dụng thuật toán xoay vòng dựa trên `assigned_count` để ưu tiên giảng viên đang có ít lớp nhất trong học kỳ:
     `min(eligible_gvs, key=lambda g: (assigned_count[g["user_id"]], ...))`

---

## 4. BẢO TOÀN DANH TÍNH VÀ HỒ SƠ SINH VIÊN (STUDENT INTEGRITY)

1. **Bảo toàn 11,051 sinh viên trong `student.csv`**:
   - Khi chỉnh sửa cấu hình nhân sự, giảng viên hoặc lớp học, **tuyệt đối không được làm thay đổi hoặc xáo trộn danh sách sinh viên hiện hữu trong `student.csv`**.
   - Mọi `user_id`, `name`, `email`, `program`, `specialization` của sinh viên phải được giữ nguyên vẹn.
2. **Đồng bộ với `student_profiles.csv`**:
   - Tất cả dữ liệu sinh viên trong `student.csv` phải khớp 100% với hồ sơ năng lực ẩn trong `student_profiles.csv` (`academic_level`, `base_score`, `discipline`, `motivation`, `stress`, `voluntary_dropout_semester`).
3. **Chặn sinh viên đã thôi học / kỷ luật**:
   - Sinh viên đã thôi học tự nguyện (`voluntary_dropout_semester`) hoặc bị kỷ luật thôi học vụ (`is_academic_dismissal`) tuyệt đối không được phát sinh bản ghi đăng ký môn học ở các học kỳ sau thời điểm thôi học.

---

## 5. QUY CHẾ HỌC VỤ VÀ ĐIỀU KIỆN ĐĂNG KÝ (14 ACADEMIC RULES)

1. **Môn Tiên quyết (`TQ`)**: Bắt buộc sinh viên phải học và đạt (`passed == True` và `final_score >= 4.0`) môn tiên quyết ở các học kỳ trước mới được đăng ký môn học sau.
2. **Môn Học trước (`KN`)**: Bắt buộc sinh viên phải từng đăng ký môn học trước ở các kỳ trước (kể cả rớt) mới được đăng ký môn học sau.
3. **Môn Song hành (`SH`)**: Bắt buộc sinh viên phải đăng ký đồng thời trong cùng học kỳ (hoặc đã tích lũy từ các kỳ trước).
4. **Trần tín chỉ tối đa**: Mỗi sinh viên chỉ được đăng ký tối đa **22.0 tín chỉ / học kỳ**.
5. **Thứ tự ưu tiên đăng ký môn trong học kỳ**:
   - **Ưu tiên 1**: Các môn nợ / trả nợ môn rớt (`retaken = True`).
   - **Ưu tiên 2**: Các môn học chuẩn theo tiến độ CTĐT của học kỳ đó.
   - **Ưu tiên 3**: Môn học vượt (Accelerated) — chỉ được đăng ký nếu tổng tín chỉ sau ưu tiên 1 và 2 còn dư cách trần 22 TC từ 2–4 TC và sinh viên có học lực khá/giỏi.
6. **Lộ trình Tốt nghiệp sớm (3.5 năm)**:
   - Chỉ áp dụng cho các sinh viên được đánh dấu `early_graduation_candidate == True` trong `student_profiles.csv`.
   - Sinh viên tốt nghiệp sớm được học vượt môn chuyên ngành từ Kỳ 5, làm Khóa luận tốt nghiệp (`CO4337`) ở Kỳ 7 và tốt nghiệp sau Kỳ 7.
7. **Điều kiện làm Khóa luận tốt nghiệp (`CO4337`)**:
   - Phải đạt chuẩn ngoại ngữ ra trường (`is_english_passed == True`).
   - Phải tích lũy tối thiểu **12 ngày CTXH** tính đến đầu học kỳ làm khóa luận.
   - Tích lũy tối thiểu 110+ tín chỉ chuyên ngành.
8. **Học lại môn rớt & Học cải thiện điểm (`retake_rules.py`)**:
   - Sinh viên rớt môn (`F`) bắt buộc phải học lại: học ghép với khóa dưới nếu môn đang mở, hoặc học lớp `L_HL` nếu là môn lệch kỳ (nhu cầu $\ge 15$ SV).
   - Sinh viên năm cuối (Kỳ 7–12) có CPA tích lũy $< 2.0$ được hệ thống tự động đăng ký học cải thiện điểm D/D+ để kéo CPA $\ge 2.0$.
   - Khi học lại, sinh viên được hưởng điểm thưởng nỗ lực `retake_bonus = +2.0` điểm kỳ vọng, cờ `retaken = True`.
9. **Thang điểm chuẩn ĐHQG**:
   - Điểm tổng kết $\ge 4.0$ là qua môn (`status = 'Pass'`, điểm chữ khác `F`).
   - Thang chữ: A+ (9.0-10.0: 4.0), A (8.0-8.9: 4.0), B+ (7.0-7.9: 3.5), B (6.0-6.9: 3.0), C+ (5.5-5.9: 2.5), C (5.0-5.4: 2.0), D+ (4.5-4.9: 1.5), D (4.0-4.4: 1.0), F (< 4.0: 0.0).

---

## 6. QUY TRÌNH KIỂM THỬ VÀ NGHIỆM THU BẮT BUỘC (VERIFICATION CHECKLIST)

Bất kỳ thay đổi nào trong `synthetic_data/generators/` hoặc `synthetic_data/rules/` phải thực hiện đầy đủ 4 bước kiểm thử trước khi xác nhận hoàn thành:

```bash
# Bước 1: Chạy toàn bộ pipeline sinh dữ liệu và prune lớp rỗng
.venv/bin/python3 synthetic_data/tools/run_all.py

# Bước 2: Kiểm tra công suất và lớp rỗng (Bắt buộc: 0 lớp vượt, 0 lớp rỗng)
.venv/bin/python3 -c "
import pandas as pd
from collections import Counter
sems = ['HK201','HK202','HK211','HK212','HK221','HK222','HK231','HK232','HK241','HK242','HK251','HK252','HK261']
for s in sems:
    c = pd.read_csv(f'synthetic_data/generated/classes/class_{s.lower()}.csv')
    e = pd.read_csv(f'synthetic_data/generated/enrollments/enrollment_{s.lower()}.csv', low_memory=False)
    caps = dict(zip(c['class_id'], c['max_capacity']))
    cnts = Counter(e['class_id'].dropna())
    over = [cid for cid, count in cnts.items() if count > caps.get(cid, 40)]
    empty = [cid for cid in c['class_id'] if cnts.get(cid, 0) == 0]
    assert len(over) == 0, f'{s} có {len(over)} lớp vượt max_capacity!'
    assert len(empty) == 0, f'{s} có {len(empty)} lớp rỗng!'
print('[✓] PASS: 0 lớp vượt công suất và 0 lớp rỗng!')
"

# Bước 3: Kiểm tra toàn diện 14 quy chế học vụ (Bắt buộc: 0 vi phạm)
.venv/bin/python3 -c "
# Chạy script audit_generated_rules.py để kiểm tra 14 quy chế học vụ
"

# Bước 4: Kiểm tra toàn vẹn CSDL (Bắt buộc: 100% Khóa ngoại hợp lệ)
.venv/bin/python3 database/push_data.py --dry-run
```

