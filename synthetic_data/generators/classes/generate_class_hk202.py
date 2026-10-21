"""Generate course classes for semester HK202 (Cohort K20 - Term 2).

Based on the updated academic catalog (curriculums.csv, program_structures.csv, courses.csv),
student user dataset (users/student.csv), previous enrollment history (enrollment_hk201.csv),
additional course rules (rules/additional_course_rules.csv), and lecturer dataset (users/lecturer.csv).

Explicitly handles:
1. Program partitioning: standard (L), high-quality (CC), advanced (TT).
2. Prerequisite tracking: English 2 (LA1005) requires passing/exempting English 1 (LA1003).
3. English 1 (LA1003) retake policy: Open a retake section only if demand >= 20 students.
4. Course acceleration (Học vượt) per additional_course_rules.csv:
   Students with under 18 credits (e.g. English-exempt) and strong academic baseline
   can accelerate CO2001 (Kỹ năng Chuyên nghiệp cho Kỹ sư, 3 credits) starting from HK2.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Set

import pandas as pd

# Path configuration
ROOT_DIR = Path(__file__).resolve().parents[2]
ACADEMICS_DIR = ROOT_DIR / "generated" / "academics"
USERS_DIR = ROOT_DIR / "generated" / "users"
RULES_DIR = ROOT_DIR / "rules"
ENROLLMENTS_DIR = ROOT_DIR / "generated" / "enrollments"
OUTPUT_DIR = ROOT_DIR / "generated" / "classes"
CONFIG_FILE = ROOT_DIR / "config" / "generator_config.json"

# Add analysis directory to import academic engine helpers
ANALYSIS_DIR = ROOT_DIR / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from analysis_helpers import get_curriculum_for_cohort_semester, get_lecturers_by_course

SEMESTER = "HK202"
COHORT = "K20"
TERM = 2
REGULAR_CLASS_MAX_CAPACITY = 40
POLITICS_CLASS_MAX_CAPACITY = 120
MIN_RETAKE_CLASS_DEMAND = 20  # Ngưỡng sĩ số tối thiểu để mở lớp học lại theo quy chế ĐHBK

PROGRAM_CONFIG = {
    "standard": {
        "prefix": "L",
        "name_vi": "Đại trà",
    },
    "high-quality": {
        "prefix": "CC",
        "name_vi": "Chất lượng cao",
    },
    "advanced": {
        "prefix": "TT",
        "name_vi": "Tiên tiến",
    },
}


def balanced_class_sizes(demand: int, max_size: int = REGULAR_CLASS_MAX_CAPACITY) -> List[int]:
    """Calculate balanced class section sizes to avoid tiny remainder classes."""
    if demand <= 0:
        return []
    class_count = math.ceil(demand / max_size)
    base_size, remainder = divmod(demand, class_count)
    return [base_size + 1 if i < remainder else base_size for i in range(class_count)]


def get_la1003_status() -> Tuple[Set[str], Set[str]]:
    """Retrieve students who passed/exempted and students who failed LA1003 in HK201."""
    enr_prev_file = ENROLLMENTS_DIR / "enrollment_hk201.csv"
    if not enr_prev_file.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file kết quả HK201: {enr_prev_file}. Hãy chạy generate_enrollment_hk201.py trước!"
        )
    df_prev = pd.read_csv(enr_prev_file, encoding="utf-8-sig", dtype={"student_id": str})
    la1003_records = df_prev[df_prev["course_id"] == "LA1003"]
    passed_uids = set(
        la1003_records[
            (la1003_records["passed"] == True) | (la1003_records["status"] == "Exempted")
        ]["student_id"].tolist()
    )
    failed_uids = set(
        la1003_records[la1003_records["passed"] == False]["student_id"].tolist()
    )
    return passed_uids, failed_uids


def get_acceleration_students(k20_students: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify students taking accelerated course CO2001 (from additional_course_rules.csv).

    Activation condition: under_18_or_eligible_acceleration.
    Applies to students with under 18 compulsory credits (e.g. English-exempt)
    and either marked as early graduation candidate OR high base score (>= 7.8) with 35% probability.
    """
    profiles_file = USERS_DIR / "student_profiles.csv"
    if not profiles_file.exists():
        return defaultdict(list)
    df_prof = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")

    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k20_students.iterrows():
        uid = str(row["user_id"])
        prog = row["program"]
        p = prof_by_id.get(uid, {})
        base_score = float(p.get("base_score", 0.0) or 0.0)
        is_early_candidate = str(p.get("early_graduation_candidate", "")).lower() == "true"

        # Deterministic check for acceleration decision
        seed_val = int(hashlib.sha256(f"{uid}:co2001_accel".encode()).hexdigest()[:8], 16)
        prob = seed_val % 100

        # Ưu tiên 100% cho ứng viên tốt nghiệp sớm
        # Sinh viên khá giỏi (base_score >= 7.8) có xác suất 35% đăng ký học vượt
        if is_early_candidate or (base_score >= 7.8 and prob < 35):
            accelerating_by_prog[prog].append(uid)

    return accelerating_by_prog


def generate_class_hk202() -> Path:
    """Generate all class sections for HK202 partitioned by program and export to class_hk202.csv."""
    print(f"=== KHỞI CHẠY SINH LỚP HỌC PHẦN CHO HỌC KỲ {SEMESTER} (PHÂN HỆ ĐÀO TẠO) ===")

    # 1. Đọc danh sách sinh viên Khóa K20
    students_file = USERS_DIR / "student.csv"
    if not students_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file danh sách sinh viên: {students_file}")

    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")]
    k20_count = len(k20_students)
    print(f"1. Tổng số sinh viên Khóa K20: {k20_count} sinh viên.")

    # 2. Đọc kết quả tiên quyết & học rớt LA1003 từ HK201
    la1003_passed_uids, la1003_failed_uids = get_la1003_status()
    print(f"2. Sinh viên K20 đạt/miễn LA1003: {len(la1003_passed_uids)} SV | Rớt LA1003: {len(la1003_failed_uids)} SV.")

    # Kiểm tra điều kiện mở lớp học lại LA1003
    retake_la1003_open = len(la1003_failed_uids) >= MIN_RETAKE_CLASS_DEMAND
    if retake_la1003_open:
        print(f"   [!] Số lượng rớt LA1003 ({len(la1003_failed_uids)} SV) >= {MIN_RETAKE_CLASS_DEMAND} SV -> Đủ điều kiện MỞ LỚP HỌC LẠI LA1003 trong HK202.")
    else:
        print(f"   [*] Số lượng rớt LA1003 ({len(la1003_failed_uids)} SV) < {MIN_RETAKE_CLASS_DEMAND} SV -> Chưa đủ sĩ số tối thiểu mở lớp riêng, SV sẽ đợi học ghép kỳ sau.")

    # 3. Đọc quy tắc học vượt (additional_course_rules.csv)
    accel_students = get_acceleration_students(k20_students)
    total_accel = sum(len(uids) for uids in accel_students.values())
    print(f"3. Sinh viên đủ điều kiện và đăng ký HỌC VƯỢT CO2001: {total_accel} sinh viên.")

    # 4. Lấy danh mục môn học bắt buộc của K20 trong Kỳ 2
    curriculum_data = get_curriculum_for_cohort_semester(COHORT, TERM)
    compulsory_courses = curriculum_data["compulsory_courses"]
    print(f"\n4. Số môn học bắt buộc HK2: {len(compulsory_courses)} môn:")
    for c in compulsory_courses:
        print(f"   + {c['course_code']}: {c['course_name_vi']} ({c['credits']} TC) - TQ: {c['prerequisites_display']}")

    # Ưu tiên chuyên môn cho các môn thuộc Khoa KH&KT Máy tính
    course_spec_preference: Dict[str, List[str]] = {
        "CO1007": ["Khoa học Máy tính", "Toán ứng dụng", "Trí tuệ nhân tạo"],
        "CO1027": ["Công nghệ Phần mềm", "Khoa học Máy tính", "Kỹ thuật Máy tính"],
        "CO2001": ["Công nghệ Phần mềm", "Khoa học Máy tính", "Kỹ thuật Máy tính"],
    }

    # 5. Phân bổ lớp học riêng biệt cho từng hệ đào tạo
    assigned_count: Dict[str, int] = defaultdict(int)
    classes: List[Dict[str, Any]] = []

    print("\n5. Tiến hành phân bổ lớp học theo từng hệ và gán giảng viên...")

    for prog, cfg in PROGRAM_CONFIG.items():
        prog_students = k20_students[k20_students["program"] == prog]
        prog_total = len(prog_students)
        prefix = cfg["prefix"]

        if prog in ("high-quality", "advanced"):
            la1005_demand = 0
            print(f"\n* Đang tạo lớp cho hệ {cfg['name_vi']} ({prog}) - {prog_total} SV (Đã miễn toàn bộ Anh văn):")
        else:
            prog_uids = set(prog_students["user_id"].tolist())
            eligible_la1005 = prog_uids.intersection(la1003_passed_uids)
            la1005_demand = len(eligible_la1005)
            not_eligible_count = prog_total - la1005_demand
            print(
                f"\n* Đang tạo lớp cho hệ {cfg['name_vi']} ({prog}) - {prog_total} SV "
                f"(Đủ điều kiện học LA1005: {la1005_demand} SV, chưa đủ điều kiện: {not_eligible_count} SV):"
            )

        # A. Các môn bắt buộc theo lộ trình chuẩn
        for c in compulsory_courses:
            course_code = c["course_code"]
            if course_code == "LA1005":
                demand = la1005_demand
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

            print(f"   + [Bắt buộc] {course_code} ({info['course_name_vi']}): demand={demand} -> {len(sizes)} lớp ({prefix}01..{prefix}{len(sizes):02d})")

        # B. Môn học vượt CO2001 (theo additional_course_rules.csv)
        accel_uids_prog = accel_students.get(prog, [])
        if accel_uids_prog:
            accel_code = "CO2001"
            accel_demand = len(accel_uids_prog)
            sizes = balanced_class_sizes(accel_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
            info = get_lecturers_by_course(accel_code)
            eligible_gvs = info["eligible_lecturers"]
            pref_specs = course_spec_preference.get(accel_code, [])

            for idx, size in enumerate(sizes, start=1):
                group_code = f"{prefix}{idx:02d}"
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
                    "class_id": f"{SEMESTER}_{accel_code}_{group_code}",
                    "course_code": accel_code,
                    "course_name": info["course_name_vi"],
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": info["department"],
                })

            print(f"   + [Học vượt] {accel_code} ({info['course_name_vi']}): demand={accel_demand} SV -> {len(sizes)} lớp ({prefix}01..{prefix}{len(sizes):02d})")

        # C. Môn học lại LA1003 (nếu đủ điều kiện >= 20 SV)
        if retake_la1003_open and prog == "standard":
            retake_code = "LA1003"
            retake_demand = len(la1003_failed_uids)
            sizes = balanced_class_sizes(retake_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
            info = get_lecturers_by_course(retake_code)
            eligible_gvs = info["eligible_lecturers"]

            for idx, size in enumerate(sizes, start=1):
                group_code = f"L_HL{idx:02d}"  # Nhóm học lại
                best_gv = min(
                    eligible_gvs,
                    key=lambda g: (assigned_count[g["user_id"]], g["user_id"]),
                )
                assigned_count[best_gv["user_id"]] += 1

                classes.append({
                    "class_id": f"{SEMESTER}_{retake_code}_{group_code}",
                    "course_code": retake_code,
                    "course_name": f"{info['course_name_vi']} (Học lại)",
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": info["department"],
                })

            print(f"   + [Học lại] {retake_code}: demand={retake_demand} SV -> {len(sizes)} lớp ({group_code})")

    # 6. Xuất file CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"class_{SEMESTER.lower()}.csv"
    df_classes = pd.DataFrame(classes)
    df_classes.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số lớp học phần đã mở cho {SEMESTER}: {len(df_classes)} lớp")

    print("\nThống kê tổng hợp số lớp theo hệ đào tạo:")
    prog_stats = df_classes.groupby(["program", "course_code"])["class_id"].count()
    print(prog_stats)

    return out_file


if __name__ == "__main__":
    generate_class_hk202()
