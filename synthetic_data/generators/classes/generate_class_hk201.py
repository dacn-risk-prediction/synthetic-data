"""Generate course classes for semester HK201 (Cohort K20 - Term 1).

Based on the updated academic catalog (curriculums.csv, program_structures.csv, courses.csv),
student user dataset (users/student.csv), and lecturer dataset (users/lecturer.csv).

Explicitly partitions classes and student enrollments by educational program:
  - standard (Đại trà): class_group begins with 'L' (e.g. L01, L02, ...)
  - high-quality (Chất lượng cao): class_group begins with 'CC' (e.g. CC01, CC02, ...)
  - advanced (Tiên tiến): class_group begins with 'TT' (e.g. TT01, TT02, ...)
Each class section is strictly designated for students of that corresponding program.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import math
from pathlib import Path
import sys
from typing import Any, Dict, List

import pandas as pd

# Path configuration
ROOT_DIR = Path(__file__).resolve().parents[2]
ACADEMICS_DIR = ROOT_DIR / "generated" / "academics"
USERS_DIR = ROOT_DIR / "generated" / "users"
OUTPUT_DIR = ROOT_DIR / "generated" / "classes"

# Add analysis directory to import academic engine helpers
ANALYSIS_DIR = ROOT_DIR / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from analysis_helpers import get_curriculum_for_cohort_semester, get_lecturers_by_course

SEMESTER = "HK201"
COHORT = "K20"
TERM = 1
REGULAR_CLASS_MAX_CAPACITY = 40
POLITICS_CLASS_MAX_CAPACITY = 120

# Quy tắc tiền tố mã nhóm lớp theo hệ đào tạo của Trường ĐH Bách Khoa
PROGRAM_CONFIG = {
    "standard": {
        "prefix": "L",
        "name_vi": "Đại trà",
        "english_exempt_rate": 0.25,  # ~25% sinh viên đại trà có chứng chỉ hoặc qua bài kiểm tra xếp lớp
    },
    "high-quality": {
        "prefix": "CC",
        "name_vi": "Chất lượng cao",
        "english_exempt_rate": 0.35,  # ~35% sinh viên CLC đạt chuẩn miễn AV1
    },
    "advanced": {
        "prefix": "TT",
        "name_vi": "Tiên tiến",
        "english_exempt_rate": 0.50,  # ~50% sinh viên Tiên tiến (học 100% tiếng Anh) đạt chuẩn miễn AV1
    },
}


def is_student_exempt_la1003(student_id: str, program: str) -> bool:
    """Determine whether a freshman student qualifies for English 1 (LA1003) exemption.

    Simulates IELTS/TOEFL/VSTEP certificate submission or Placement Test result.
    Uses deterministic SHA-256 hash to ensure stable reproduction.
    Threshold varies by program standard.
    """
    digest = hashlib.sha256(f"{student_id}:la1003_placement".encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    rate = PROGRAM_CONFIG.get(program, {}).get("english_exempt_rate", 0.25)
    return (seed % 100) < int(rate * 100)


def balanced_class_sizes(demand: int, max_size: int = REGULAR_CLASS_MAX_CAPACITY) -> List[int]:
    """Calculate balanced class section sizes to avoid tiny remainder classes."""
    if demand <= 0:
        return []
    class_count = math.ceil(demand / max_size)
    base_size, remainder = divmod(demand, class_count)
    return [base_size + 1 if i < remainder else base_size for i in range(class_count)]


def generate_class_hk201() -> Path:
    """Generate all class sections for HK201 partitioned by program and export to class_hk201.csv."""
    print(f"=== KHỞI CHẠY SINH LỚP HỌC PHẦN CHO HỌC KỲ {SEMESTER} (PHÂN HỆ ĐÀO TẠO) ===")

    # 1. Đọc danh sách sinh viên Khóa K20
    students_file = USERS_DIR / "student.csv"
    if not students_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file danh sách sinh viên: {students_file}")

    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")]
    k20_count = len(k20_students)
    print(f"1. Tổng số sinh viên Khóa K20: {k20_count} sinh viên.")

    # Thống kê sinh viên theo hệ đào tạo
    print("\n   Phân bố sinh viên theo hệ đào tạo (program):")
    program_student_counts: Dict[str, int] = {}
    for prog, info in PROGRAM_CONFIG.items():
        count = len(k20_students[k20_students["program"] == prog])
        program_student_counts[prog] = count
        print(f"   - {info['name_vi']} ({prog}) [Tiền tố: {info['prefix']}]: {count} sinh viên")

    # 2. Lấy danh mục môn học bắt buộc của K20 trong Kỳ 1
    curriculum_data = get_curriculum_for_cohort_semester(COHORT, TERM)
    compulsory_courses = curriculum_data["compulsory_courses"]
    print(f"\n2. Số môn học bắt buộc HK1: {len(compulsory_courses)} môn:")
    for c in compulsory_courses:
        print(f"   + {c['course_code']}: {c['course_name_vi']} ({c['credits']} TC)")

    # Ưu tiên chuyên môn cho các môn thuộc Khoa KH&KT Máy tính
    course_spec_preference: Dict[str, List[str]] = {
        "CO1023": ["Kỹ thuật Máy tính"],  # Hệ thống số
        "CO1005": [  # Nhập môn Điện toán
            "Công nghệ Phần mềm",
            "Trí tuệ nhân tạo",
            "An ninh hệ thống và mạng",
            "Công nghệ dữ liệu và dữ liệu lớn",
            "Kỹ thuật Máy tính",
        ],
    }

    # 3. Phân bổ lớp học riêng biệt cho từng hệ đào tạo
    assigned_count: Dict[str, int] = defaultdict(int)
    classes: List[Dict[str, Any]] = []

    print("\n3. Tiến hành phân bổ lớp học theo từng hệ và gán giảng viên...")

    for prog, cfg in PROGRAM_CONFIG.items():
        prog_students = k20_students[k20_students["program"] == prog]
        prog_total = len(prog_students)
        prefix = cfg["prefix"]

        # Với hệ Chất lượng cao và Tiên tiến: Miễn toàn bộ 4 học phần Tiếng Anh (không mở lớp)
        # Với hệ Đại trà: Mở lớp LA1003 theo số lượng SV chưa được miễn
        if prog in ("high-quality", "advanced"):
            exempt_count = prog_total
            la1003_demand = 0
            print(f"\n* Đang tạo lớp cho hệ {cfg['name_vi']} ({prog}) - {prog_total} SV (Miễn 100% 4 môn tiếng Anh):")
        else:
            exempt_count = sum(
                is_student_exempt_la1003(uid, prog) for uid in prog_students["user_id"]
            )
            la1003_demand = prog_total - exempt_count
            print(f"\n* Đang tạo lớp cho hệ {cfg['name_vi']} ({prog}) - {prog_total} SV (Miễn AV1: {exempt_count} SV):")

        for c in compulsory_courses:
            course_code = c["course_code"]
            if course_code == "LA1003" and prog in ("high-quality", "advanced"):
                demand = 0
            elif course_code == "LA1003":
                demand = la1003_demand
            else:
                demand = prog_total

            if demand <= 0:
                continue

            is_politics = course_code.startswith("SP")
            max_cap = POLITICS_CLASS_MAX_CAPACITY if is_politics else REGULAR_CLASS_MAX_CAPACITY
            sizes = balanced_class_sizes(demand, max_size=max_cap)

            info = get_lecturers_by_course(course_code)
            eligible_gvs = info["eligible_lecturers"]
            pref_specs = course_spec_preference.get(course_code, [])

            for idx, size in enumerate(sizes, start=1):
                group_code = f"{prefix}{idx:02d}"

                # Greedy load balancing
                best_gv = min(
                    eligible_gvs,
                    key=lambda g: (
                        assigned_count[g["user_id"]],
                        0 if g.get("specialization") in pref_specs else 1,
                        g["user_id"],
                    ),
                )
                assigned_count[best_gv["user_id"]] += 1

                classes.append({
                    "class_id": f"{SEMESTER}_{course_code}_{group_code}",
                    "course_code": course_code,
                    "course_name": info["course_name_vi"],
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": max_cap,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": info["department"],
                })

            print(f"   + {course_code} ({info['course_name_vi']}): demand={demand} -> {len(sizes)} lớp ({prefix}01..{prefix}{len(sizes):02d})")

    # 4. Xuất file CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"class_{SEMESTER.lower()}.csv"
    df_classes = pd.DataFrame(classes)
    df_classes.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số lớp học phần đã mở: {len(df_classes)} lớp")

    print("\nThống kê tổng hợp số lớp theo hệ đào tạo:")
    prog_stats = df_classes.groupby(["program", "course_code"])["class_id"].count()
    print(prog_stats)

    print("\nThống kê cân bằng tải giảng viên theo từng đơn vị:")
    dept_stats: Dict[str, List[int]] = defaultdict(list)
    for gv_id, count in assigned_count.items():
        if count == 0:
            continue
        dept = df_classes[df_classes["lecturer_id"] == gv_id]["department"].iloc[0]
        dept_stats[dept].append(count)

    for dept, counts in dept_stats.items():
        ser = pd.Series(counts)
        print(f"\n* Đơn vị: {dept} (Tổng GV dạy: {len(ser)})")
        val_counts = ser.value_counts().sort_index()
        for c, gv_cnt in val_counts.items():
            print(f"  + {gv_cnt} giảng viên dạy {c} lớp/kỳ")

    return out_file


if __name__ == "__main__":
    generate_class_hk201()
