"""Generate course classes for semester HK211.

In this semester, two distinct cohorts attend classes simultaneously:
1. Cohort K20 in Term 3 (Sophomore - Năm 2):
   - Compulsory courses: CO2011 (3 TC), SP1031 (3 TC - Politics max capacity 120),
     CO2003 (4 TC), CO2007 (4 TC), LA1007 (2 TC - Standard only).
   - Course acceleration per additional_course_rules.csv:
     Eligible K20 students can accelerate MT2013 (Xác suất & Thống kê, 4 TC).
   - Retakes: K20 students who failed HK1 courses (MT1003, PH1003, CO1005, CO1023, LA1003)
     can retake with the HK1 course offerings.
2. Cohort K21 in Term 1 (Freshmen - Tân sinh viên):
   - Compulsory courses: MT1003 (4 TC), PH1003 (4 TC), CO1005 (3 TC), CO1023 (3 TC),
     LA1003 (2 TC - Standard only; CLC & Advanced 100% exempted).

Partitions all class sections strictly by educational program:
  - standard (L01, L02, ...)
  - high-quality (CC01, CC02, ...)
  - advanced (TT01, TT02, ...)
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Set, Tuple

import pandas as pd

# Path configuration
ROOT_DIR = Path(__file__).resolve().parents[2]
ACADEMICS_DIR = ROOT_DIR / "generated" / "academics"
USERS_DIR = ROOT_DIR / "generated" / "users"
RULES_DIR = ROOT_DIR / "rules"
ENROLLMENTS_DIR = ROOT_DIR / "generated" / "enrollments"
OUTPUT_DIR = ROOT_DIR / "generated" / "classes"

# Add analysis directory to import academic engine helpers
ANALYSIS_DIR = ROOT_DIR / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from analysis_helpers import get_curriculum_for_cohort_semester, get_lecturers_by_course

SEMESTER = "HK211"
REGULAR_CLASS_MAX_CAPACITY = 40
POLITICS_CLASS_MAX_CAPACITY = 120

PROGRAM_CONFIG = {
    "standard": {
        "prefix": "L",
        "name_vi": "Đại trà",
        "k21_english_exempt_rate": 0.25,
    },
    "high-quality": {
        "prefix": "CC",
        "name_vi": "Chất lượng cao",
        "k21_english_exempt_rate": 0.35,
    },
    "advanced": {
        "prefix": "TT",
        "name_vi": "Tiên tiến",
        "k21_english_exempt_rate": 0.50,
    },
}


def balanced_class_sizes(demand: int, max_size: int = REGULAR_CLASS_MAX_CAPACITY) -> List[int]:
    """Calculate balanced class section sizes to avoid tiny remainder classes."""
    if demand <= 0:
        return []
    class_count = math.ceil(demand / max_size)
    base_size, remainder = divmod(demand, class_count)
    return [base_size + 1 if i < remainder else base_size for i in range(class_count)]


def is_k21_standard_exempt_la1003(student_id: str) -> bool:
    """Determine whether a K21 Standard freshman qualifies for LA1003 exemption."""
    digest = hashlib.sha256(f"{student_id}:la1003_placement".encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    return (seed % 100) < 25


def get_k20_la1005_passed_students() -> Set[str]:
    """Retrieve K20 Standard students who passed LA1005 in HK202."""
    enr_hk202_file = ENROLLMENTS_DIR / "enrollment_hk202.csv"
    if not enr_hk202_file.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file kết quả HK202: {enr_hk202_file}. Cần chạy HK202 trước!"
        )
    df_hk202 = pd.read_csv(enr_hk202_file, encoding="utf-8-sig", dtype={"student_id": str})
    la1005_passed = df_hk202[
        (df_hk202["course_id"] == "LA1005") & (df_hk202["passed"] == True)
    ]
    return set(la1005_passed["student_id"].tolist())


def get_k20_failed_hk1_students() -> Dict[str, Set[str]]:
    """Retrieve K20 students who still have incomplete HK1 courses."""
    enr_hk201_file = ENROLLMENTS_DIR / "enrollment_hk201.csv"
    if not enr_hk201_file.exists():
        return defaultdict(set)
    df_hk201 = pd.read_csv(enr_hk201_file, encoding="utf-8-sig", dtype={"student_id": str})
    failed_by_course: Dict[str, Set[str]] = defaultdict(set)
    for _, r in df_hk201[df_hk201["passed"] == False].iterrows():
        failed_by_course[str(r["course_id"])].add(str(r["student_id"]))
    return failed_by_course


def get_k20_acceleration_students(k20_students: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K20 students taking accelerated course MT2013 (Xác suất & Thống kê)."""
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

        seed_val = int(hashlib.sha256(f"{uid}:mt2013_accel".encode()).hexdigest()[:8], 16)
        prob = seed_val % 100

        # Ưu tiên 100% cho ứng viên tốt nghiệp sớm; sinh viên khá giỏi có xác suất 35%
        if is_early_candidate or (base_score >= 7.8 and prob < 35):
            accelerating_by_prog[prog].append(uid)

    return accelerating_by_prog


def generate_class_hk211() -> Path:
    """Generate all class sections for HK211 and export to class_hk211.csv."""
    print(f"=== KHỞI CHẠY SINH LỚP HỌC PHẦN CHO HỌC KỲ {SEMESTER} (ĐA KHÓA: K20 & K21) ===")

    # 1. Đọc sinh viên K20 và K21
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")]
    k21_students = df_students[df_students["user_id"].str.startswith("21")]
    print(f"1. Sinh viên K20 (Năm 2 - HK3): {len(k20_students)} SV | K21 (Năm 1 - HK1): {len(k21_students)} SV.")

    # 2. Đọc điều kiện tiên quyết và học lại của K20
    k20_la1005_passed = get_k20_la1005_passed_students()
    k20_failed_hk1 = get_k20_failed_hk1_students()
    k20_accel = get_k20_acceleration_students(k20_students)
    total_accel = sum(len(uids) for uids in k20_accel.values())
    print(f"2. K20 đạt LA1005: {len(k20_la1005_passed)} SV | K20 đăng ký học vượt MT2013: {total_accel} SV.")

    # 3. Lấy danh mục môn học của K21 (HK1) và K20 (HK3)
    k21_curriculum = get_curriculum_for_cohort_semester("K21", 1)["compulsory_courses"]
    k20_curriculum = get_curriculum_for_cohort_semester("K20", 3)["compulsory_courses"]

    print("\n3. Môn học K21 (Học kỳ 1):", ", ".join(c["course_code"] for c in k21_curriculum))
    print("   Môn học K20 (Học kỳ 3):", ", ".join(c["course_code"] for c in k20_curriculum))

    # Cấu hình chuyên môn ưu tiên
    course_spec_preference: Dict[str, List[str]] = {
        "CO1005": ["Công nghệ Phần mềm", "Khoa học Máy tính"],
        "CO1023": ["Kỹ thuật Máy tính"],
        "CO2011": ["Khoa học Máy tính", "Toán ứng dụng"],
        "CO2003": ["Khoa học Máy tính", "Công nghệ Phần mềm"],
        "CO2007": ["Kỹ thuật Máy tính"],
    }

    assigned_count: Dict[str, int] = defaultdict(int)
    classes: List[Dict[str, Any]] = []

    print("\n4. Phân bổ lớp học theo từng hệ đào tạo cho cả 2 khóa...")

    # -------------------------------------------------------------------------
    # A. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K21 (HỌC KỲ 1)
    # -------------------------------------------------------------------------
    print("\n--- [A] TẠO LỚP HỌC CHO KHÓA K21 (TÂN SINH VIÊN - KỲ 1) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k21 = k21_students[k21_students["program"] == prog]
        p_total = len(p_k21)
        prefix = cfg["prefix"]

        if prog in ("high-quality", "advanced"):
            la1003_demand = 0
            print(f"* K21 {cfg['name_vi']} ({prog}) - {p_total} SV (Miễn toàn bộ Anh văn)")
        else:
            exempt_count = sum(is_k21_standard_exempt_la1003(uid) for uid in p_k21["user_id"])
            la1003_demand = p_total - exempt_count
            print(f"* K21 {cfg['name_vi']} ({prog}) - {p_total} SV (Học LA1003: {la1003_demand} SV, Miễn: {exempt_count} SV)")

        for c in k21_curriculum:
            course_code = c["course_code"]
            # Thêm nhu cầu học lại từ K20 (nếu có sinh viên K20 rớt môn này)
            k20_retake_count = len(k20_failed_hk1.get(course_code, set()).intersection(
                set(k20_students[k20_students["program"] == prog]["user_id"])
            ))

            if course_code == "LA1003":
                demand = la1003_demand + k20_retake_count
            else:
                demand = p_total + k20_retake_count

            if demand <= 0:
                continue

            sizes = balanced_class_sizes(demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
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
                    "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": info["department"],
                })

            retake_str = f" (+{k20_retake_count} K20 học ghép)" if k20_retake_count > 0 else ""
            print(f"   + [K21] {course_code} ({info['course_name_vi']}): demand={demand}{retake_str} -> {len(sizes)} lớp ({prefix}01..{prefix}{len(sizes):02d})")

    # -------------------------------------------------------------------------
    # B. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K20 (HỌC KỲ 3)
    # -------------------------------------------------------------------------
    print("\n--- [B] TẠO LỚP HỌC CHO KHÓA K20 (NĂM 2 - KỲ 3) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k20 = k20_students[k20_students["program"] == prog]
        p_total = len(p_k20)
        prefix = cfg["prefix"]

        # Với môn Tiếng Anh 3 (LA1007):
        # Hệ CLC và Tiên tiến đã được miễn 100%
        # Hệ Đại trà: những SV đã đạt LA1005 ở HK202
        if prog in ("high-quality", "advanced"):
            la1007_demand = 0
            print(f"* K20 {cfg['name_vi']} ({prog}) - {p_total} SV (Miễn toàn bộ Anh văn)")
        else:
            prog_uids = set(p_k20["user_id"].tolist())
            eligible_la1007 = prog_uids.intersection(k20_la1005_passed)
            la1007_demand = len(eligible_la1007)
            print(f"* K20 {cfg['name_vi']} ({prog}) - {p_total} SV (Đủ điều kiện học LA1007: {la1007_demand} SV)")

        for c in k20_curriculum:
            course_code = c["course_code"]
            if course_code == "LA1007":
                demand = la1007_demand
            else:
                demand = p_total

            if demand <= 0:
                continue

            # Môn Triết học Mác - Lênin (SP1031) dùng giảng đường lớn 120 SV/lớp
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

            cap_note = " [Giảng đường lớn 120]" if is_politics else ""
            print(f"   + [K20] {course_code} ({info['course_name_vi']}): demand={demand} -> {len(sizes)} lớp ({prefix}01..{prefix}{len(sizes):02d}){cap_note}")

        # Môn học vượt K20: MT2013 (Xác suất & Thống kê per additional_course_rules.csv)
        accel_k20_prog = k20_accel.get(prog, [])
        if accel_k20_prog:
            accel_code = "MT2013"
            accel_demand = len(accel_k20_prog)
            sizes = balanced_class_sizes(accel_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
            info = get_lecturers_by_course(accel_code)
            eligible_gvs = info["eligible_lecturers"]

            for idx, size in enumerate(sizes, start=1):
                group_code = f"{prefix}{idx:02d}"
                best_gv = min(
                    eligible_gvs,
                    key=lambda g: (assigned_count[g["user_id"]], g["user_id"]),
                )
                assigned_count[best_gv["user_id"]] += 1

                classes.append({
                    "class_id": f"{SEMESTER}_{accel_code}_{group_code}",
                    "course_code": accel_code,
                    "course_name": f"{info['course_name_vi']} (Học vượt)",
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": info["department"],
                })

            print(f"   + [K20 Học vượt] {accel_code}: demand={accel_demand} SV -> {len(sizes)} lớp ({prefix}01..{prefix}{len(sizes):02d})")

    # 5. Xuất file CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"class_{SEMESTER.lower()}.csv"
    df_classes = pd.DataFrame(classes)
    df_classes.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số lớp học phần đã mở cho {SEMESTER} (Cả K20 và K21): {len(df_classes)} lớp")

    print("\nThống kê tổng hợp số lớp theo hệ đào tạo:")
    prog_stats = df_classes.groupby(["program", "course_code"])["class_id"].count()
    print(prog_stats)

    return out_file


if __name__ == "__main__":
    generate_class_hk211()

