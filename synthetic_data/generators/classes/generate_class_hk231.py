"""Generate course classes for semester HK231.

In this semester, four distinct cohorts attend classes simultaneously:
1. Cohort K23 in Term 1 (Freshmen - Tân sinh viên):
   - Compulsory courses:
     * MT1003: Giải tích 1 (4 TC)
     * PH1003: Vật lý 1 (4 TC)
     * CO1005: Nhập môn Điện toán (3 TC)
     * CO1023: Hệ thống số (3 TC)
     * PE1003: Giáo dục thể chất 1 (0 TC)
     * LA1003: Anh văn 1 (2 TC - Standard only; CLC & Advanced 100% exempted)
   - K22, K21, K20 retakers join regular classes for HK1 courses.

2. Cohort K22 in Term 3 (Sophomore - Năm 2):
   - Compulsory courses:
     * CO2011: Mô hình hóa Toán học (3 TC)
     * SP1031: Triết học Mác - Lênin (3 TC, Giảng đường lớn max capacity 120)
     * CO2003: Cấu trúc Dữ liệu và Giải Thuật (4 TC)
     * CO2007: Kiến trúc Máy tính (4 TC)
     * LA1007: Anh văn 3 (2 TC - Standard students who passed LA1005 in HK222)
   - Course acceleration per additional_course_rules.csv:
     * MT2013: Xác suất và Thống kê (4 TC, ADD_MT2013_HK3)
   - K21 & K20 retakers join regular classes for HK3 courses.

3. Cohort K21 in Term 5 (Junior - Năm 3):
   - Compulsory courses:
     * SP1035: Chủ nghĩa Xã hội Khoa học (2 TC, Giảng đường lớn max capacity 120)
     * CO2001: Kỹ năng Chuyên nghiệp cho Kỹ sư (3 TC)
     * CO2013: Hệ cơ sở Dữ liệu (4 TC) - SV K21 chưa học vượt ở HK222
     * CO3001: Công nghệ Phần mềm (3 TC)
     * CO3005: Nguyên lý Ngôn ngữ Lập trình (4 TC)
   - Elective Group C (Tự chọn ngành - 3 TC per ADD_GROUP_C_HK5):
     * CO3011, CO3021, CO3029, CO3043, CO3045

4. Cohort K20 in Term 7 (Senior - Năm 4):
   - Compulsory courses:
     * SP1039: Lịch sử Đảng Cộng sản Việt Nam (2 TC, Giảng đường lớn max capacity 120)
     * CO3335: Thực tập Ngoài trường (2 TC)
     * CO4029: Đồ án Chuyên ngành (2 TC) - SV K20 chưa hoàn thành ở HK222
   - Lộ trình tốt nghiệp sớm 3.5 năm (242 SV K20 tốt nghiệp sớm):
     * CO4337: Đồ án Tốt nghiệp (4 TC per EARLY_CO4337_HK7)
     * SP1007: Pháp luật Việt Nam Đại cương (2 TC per EARLY_SP1007_HK7)
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
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

ANALYSIS_DIR = ROOT_DIR / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))
if str(RULES_DIR) not in sys.path:
    sys.path.insert(0, str(RULES_DIR))

from curriculum_rules import select_student_group_c_course, get_student_specialization_map

from academic_rules import balanced_class_sizes
from analysis_helpers import (
    get_curriculum_for_cohort_semester,
    get_lecturers_by_course,
    load_lecturers_table,
)

SEMESTER = "HK231"
REGULAR_CLASS_MAX_CAPACITY = 40
POLITICS_CLASS_MAX_CAPACITY = 120

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

GROUP_C_COURSES = ["CO3011", "CO3021", "CO3029", "CO3043", "CO3045"]


def is_k23_standard_exempt_la1003(student_id: str) -> bool:
    """Determine whether a K23 Standard freshman qualifies for LA1003 exemption."""
    digest = hashlib.sha256(f"{student_id}:la1003_placement".encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    return (seed % 100) < 25


def get_all_passed_courses_up_to_hk222() -> Dict[str, Set[str]]:
    """Retrieve all courses passed by each student across all prior semesters."""
    passed_map: Dict[str, Set[str]] = defaultdict(set)
    for sem in ["hk201", "hk202", "hk211", "hk212", "hk221", "hk222"]:
        enr_file = ENROLLMENTS_DIR / f"enrollment_{sem}.csv"
        if enr_file.exists():
            df_enr = pd.read_csv(enr_file, encoding="utf-8-sig", dtype={"student_id": str})
            for _, r in df_enr[df_enr["passed"] == True].iterrows():
                passed_map[str(r["student_id"])].add(str(r["course_id"]))
    return passed_map


def get_k22_acceleration_students(k22_students: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K22 students accelerating MT2013 in HK3 per additional_course_rules.csv."""
    profiles_file = USERS_DIR / "student_profiles.csv"
    if not profiles_file.exists():
        return defaultdict(list)
    df_prof = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")

    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k22_students.iterrows():
        uid = str(row["user_id"])
        prog = row["program"]
        p = prof_by_id.get(uid, {})
        base_score = float(p.get("base_score", 0.0) or 0.0)
        is_early_candidate = str(p.get("early_graduation_candidate", "")).lower() == "true"

        seed_val = int(hashlib.sha256(f"{uid}:mt2013_accel".encode()).hexdigest()[:8], 16)
        prob = seed_val % 100

        if is_early_candidate or (base_score >= 7.8 and prob < 35):
            accelerating_by_prog[prog].append(uid)

    return accelerating_by_prog


def get_k21_group_c_distribution(k21_students: pd.DataFrame) -> Dict[Tuple[str, str], List[str]]:
    """Distribute K21 students among Group C elective courses based on specialization."""
    spec_map = get_student_specialization_map()
    choice_map: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, row in k21_students.iterrows():
        uid = str(row["user_id"])
        prog = row["program"]
        spec = spec_map.get(uid, "Khoa học Máy tính")
        c_code = select_student_group_c_course(uid, "K21", spec, seed_salt="k21_group_c_hk231")
        choice_map[(prog, c_code)].append(uid)
    return choice_map


def get_all_lecturers_with_fallback(course_code: str, all_lecturers: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], str, str]:
    """Retrieve eligible lecturers for a course, with safe fallback if department has none."""
    info = get_lecturers_by_course(course_code)
    eligible = info["eligible_lecturers"]
    dept = info["department"]
    c_name = info["course_name_vi"]

    if not eligible:
        cse_lecturers = [
            l for l in all_lecturers
            if "Khoa học và Kỹ thuật Máy tính" in l["department"]
        ]
        eligible = cse_lecturers if cse_lecturers else all_lecturers

    return eligible, dept, c_name


def generate_class_hk231() -> Path:
    """Generate all class sections for HK231 and export to class_hk231.csv."""
    print(f"=== KHỞI CHẠY SINH LỚP HỌC PHẦN CHO HỌC KỲ {SEMESTER} (ĐA KHÓA: K20, K21, K22, K23) ===")

    # 1. Đọc sinh viên 4 khóa
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    k21_students = df_students[df_students["user_id"].str.startswith("21")].copy()
    k22_students = df_students[df_students["user_id"].str.startswith("22")].copy()
    k23_students = df_students[df_students["user_id"].str.startswith("23")].copy()
    print(f"1. Tổng SV: K20: {len(k20_students)} | K21: {len(k21_students)} | K22: {len(k22_students)} | K23: {len(k23_students)}")

    # 2. Lịch sử các môn đã đạt
    passed_map = get_all_passed_courses_up_to_hk222()

    # K20 đã hoàn thành CO4029 ở HK222 (242 SV tốt nghiệp sớm)
    k20_passed_co4029 = {uid for uid in k20_students["user_id"] if "CO4029" in passed_map[uid]}
    print(f"2. K20 đã hoàn thành CO4029 sớm: {len(k20_passed_co4029)} SV (thuộc diện tốt nghiệp sớm 3.5 năm).")

    # K21 đã học vượt CO2013 ở HK222
    k21_passed_co2013 = {uid for uid in k21_students["user_id"] if "CO2013" in passed_map[uid]}
    print(f"   K21 đã hoàn thành CO2013 sớm: {len(k21_passed_co2013)} SV (miễn học ở HK231).")

    # K22 Đại trà đạt LA1005 ở HK222 -> đủ điều kiện học LA1007
    k22_passed_la1005 = {uid for uid in k22_students["user_id"] if "LA1005" in passed_map[uid]}

    # 3. Nhu cầu học lại
    all_prev_enrollments = pd.concat([
        pd.read_csv(ENROLLMENTS_DIR / f"enrollment_{sem}.csv", encoding="utf-8-sig", dtype={"student_id": str})
        for sem in ["hk201", "hk202", "hk211", "hk212", "hk221", "hk222"]
    ])
    retake_demand: Dict[str, Set[str]] = defaultdict(set)
    for _, r in all_prev_enrollments[all_prev_enrollments["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        if cid not in passed_map[sid]:
            retake_demand[cid].add(sid)

    # 4. CTĐT chuẩn
    k23_curriculum = get_curriculum_for_cohort_semester("K23", 1)["compulsory_courses"]
    k22_curriculum = get_curriculum_for_cohort_semester("K22", 3)["compulsory_courses"]
    k21_curriculum = get_curriculum_for_cohort_semester("K21", 5)["compulsory_courses"]
    k20_curriculum = get_curriculum_for_cohort_semester("K20", 7)["compulsory_courses"]

    print("\n3. Môn học K23 (HK1):", ", ".join(c["course_code"] for c in k23_curriculum))
    print("   Môn học K22 (HK3):", ", ".join(c["course_code"] for c in k22_curriculum))
    print("   Môn học K21 (HK5):", ", ".join(c["course_code"] for c in k21_curriculum))
    print("   Môn học K20 (HK7):", ", ".join(c["course_code"] for c in k20_curriculum))

    k22_accel = get_k22_acceleration_students(k22_students)
    k21_group_c = get_k21_group_c_distribution(k21_students)

    profiles_file = USERS_DIR / "student_profiles.csv"
    df_prof = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")

    all_lecturers = load_lecturers_table()
    assigned_count: Dict[str, int] = defaultdict(int)
    classes: List[Dict[str, Any]] = []

    course_spec_preference: Dict[str, List[str]] = {
        "CO1005": ["Công nghệ Phần mềm", "Khoa học Máy tính"],
        "CO1023": ["Kỹ thuật Máy tính"],
        "CO2011": ["Khoa học Máy tính", "Toán ứng dụng"],
        "CO2003": ["Khoa học Máy tính", "Công nghệ Phần mềm"],
        "CO2007": ["Kỹ thuật Máy tính"],
        "CO3001": ["Công nghệ Phần mềm"],
        "CO3005": ["Khoa học Máy tính"],
        "CO2013": ["Khoa học Dữ liệu", "Khoa học Máy tính"],
        "CO2001": ["Công nghệ Phần mềm", "Khoa học Máy tính"],
        "CO4029": ["Công nghệ Phần mềm", "Khoa học Máy tính"],
        "CO4337": ["Công nghệ Phần mềm", "Khoa học Máy tính", "Hệ thống và Mạng máy tính"],
    }

    # -------------------------------------------------------------------------
    # A. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K23 (TÂN SINH VIÊN - KỲ 1)
    # -------------------------------------------------------------------------
    print("\n--- [A] TẠO LỚP HỌC CHO KHÓA K23 (TÂN SINH VIÊN - KỲ 1) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k23 = k23_students[k23_students["program"] == prog]
        p_total = len(p_k23)
        prefix = cfg["prefix"]

        if prog in ("high-quality", "advanced"):
            la1003_demand = 0
            print(f"* K23 {cfg['name_vi']} ({prog}) - {p_total} SV (Miễn toàn bộ Anh văn)")
        else:
            exempt_count = sum(is_k23_standard_exempt_la1003(uid) for uid in p_k23["user_id"])
            la1003_demand = p_total - exempt_count
            print(f"* K23 {cfg['name_vi']} ({prog}) - {p_total} SV (Học LA1003: {la1003_demand} SV, Miễn: {exempt_count} SV)")

        for c in k23_curriculum:
            course_code = c["course_code"]
            retakers = [
                uid for uid in retake_demand.get(course_code, set())
                if uid in set(df_students[df_students["program"] == prog]["user_id"])
            ]
            retake_count = len(retakers)

            if course_code == "LA1003":
                demand = la1003_demand + retake_count
            else:
                demand = p_total + retake_count

            if demand <= 0:
                continue

            sizes = balanced_class_sizes(demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(course_code, all_lecturers)
            pref_specs = course_spec_preference.get(course_code, [])

            existing_count = sum(1 for cl in classes if cl["course_code"] == course_code and cl["program"] == prog)
            for idx, size in enumerate(sizes, start=existing_count + 1):
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
                    "course_name": c_name,
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": dept,
                })

            retake_str = f" (+{retake_count} SV khóa trước học ghép)" if retake_count > 0 else ""
            print(f"   + [K23] {course_code} ({c_name}): demand={demand}{retake_str} -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d})")

    # -------------------------------------------------------------------------
    # B. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K22 (NĂM 2 - KỲ 3)
    # -------------------------------------------------------------------------
    print("\n--- [B] TẠO LỚP HỌC CHO KHÓA K22 (NĂM 2 - KỲ 3) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k22 = k22_students[k22_students["program"] == prog]
        p_total = len(p_k22)
        prefix = cfg["prefix"]

        if prog in ("high-quality", "advanced"):
            la1007_demand = 0
            print(f"* K22 {cfg['name_vi']} ({prog}) - {p_total} SV (Đã miễn toàn bộ Anh văn)")
        else:
            prog_uids = set(p_k22["user_id"].tolist())
            eligible_la1007 = prog_uids.intersection(k22_passed_la1005)
            la1007_demand = len(eligible_la1007)
            print(f"* K22 {cfg['name_vi']} ({prog}) - {p_total} SV (Đủ điều kiện học LA1007: {la1007_demand} SV)")

        for c in k22_curriculum:
            course_code = c["course_code"]
            retakers = [
                uid for uid in retake_demand.get(course_code, set())
                if uid in set(df_students[df_students["program"] == prog]["user_id"])
            ]
            retake_count = len(retakers)

            if course_code == "LA1007":
                demand = la1007_demand + retake_count
            else:
                demand = p_total + retake_count

            if demand <= 0:
                continue

            is_politics = course_code.startswith("SP")
            max_cap = POLITICS_CLASS_MAX_CAPACITY if is_politics else REGULAR_CLASS_MAX_CAPACITY
            sizes = balanced_class_sizes(demand, max_size=max_cap)

            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(course_code, all_lecturers)
            pref_specs = course_spec_preference.get(course_code, [])

            existing_count = sum(1 for cl in classes if cl["course_code"] == course_code and cl["program"] == prog)
            for idx, size in enumerate(sizes, start=existing_count + 1):
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
                    "course_name": c_name,
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": max_cap,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": dept,
                })

            retake_str = f" (+{retake_count} SV học ghép)" if retake_count > 0 else ""
            cap_note = " [Giảng đường lớn 120]" if is_politics else ""
            print(f"   + [K22] {course_code} ({c_name}): demand={demand}{retake_str} -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d}){cap_note}")

        # Môn học vượt K22: MT2013 per ADD_MT2013_HK3
        accel_k22_prog = k22_accel.get(prog, [])
        if accel_k22_prog:
            accel_code = "MT2013"
            accel_demand = len(accel_k22_prog)
            sizes = balanced_class_sizes(accel_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(accel_code, all_lecturers)

            existing_count = sum(1 for cl in classes if cl["course_code"] == accel_code and cl["program"] == prog)
            for idx, size in enumerate(sizes, start=existing_count + 1):
                group_code = f"{prefix}{idx:02d}"
                best_gv = min(eligible_gvs, key=lambda g: (assigned_count[g["user_id"]], g["user_id"]))
                assigned_count[best_gv["user_id"]] += 1

                classes.append({
                    "class_id": f"{SEMESTER}_{accel_code}_{group_code}",
                    "course_code": accel_code,
                    "course_name": f"{c_name} (Học vượt)",
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": dept,
                })

            print(f"   + [K22 Học vượt] {accel_code}: demand={accel_demand} SV -> {len(sizes)} lớp")

    # -------------------------------------------------------------------------
    # C. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K21 (NĂM 3 - KỲ 5)
    # -------------------------------------------------------------------------
    print("\n--- [C] TẠO LỚP HỌC CHO KHÓA K21 (NĂM 3 - KỲ 5) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k21 = k21_students[k21_students["program"] == prog]
        p_total = len(p_k21)
        prefix = cfg["prefix"]
        prog_uids = set(p_k21["user_id"].tolist())

        co2013_demand = len(prog_uids - k21_passed_co2013)

        for c in k21_curriculum:
            course_code = c["course_code"]
            demand = co2013_demand if course_code == "CO2013" else p_total

            if demand <= 0:
                continue

            is_politics = course_code.startswith("SP")
            max_cap = POLITICS_CLASS_MAX_CAPACITY if is_politics else REGULAR_CLASS_MAX_CAPACITY
            sizes = balanced_class_sizes(demand, max_size=max_cap)

            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(course_code, all_lecturers)
            pref_specs = course_spec_preference.get(course_code, [])

            existing_count = sum(1 for cl in classes if cl["course_code"] == course_code and cl["program"] == prog)
            for idx, size in enumerate(sizes, start=existing_count + 1):
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
                    "course_name": c_name,
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": max_cap,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": dept,
                })

            cap_note = " [Giảng đường lớn 120]" if is_politics else ""
            print(f"   + [K21] {course_code} ({c_name}): demand={demand} -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d}){cap_note}")

        # Tự chọn Nhóm C cho K21 (Hệ Tiên tiến học chung với CLC)
        if prog == "advanced":
            print(f"   + [K21 Tự chọn ngành - Group C]: Ghép học chung lớp với hệ Chất lượng cao (CC)")
        else:
            print(f"   + [K21 Tự chọn ngành - Group C]:")
            if prog == "high-quality":
                all_group_c = sorted(list({c for (p, c) in k21_group_c.keys() if p in ("high-quality", "advanced")}))
                for g_course in all_group_c:
                    g_uids = k21_group_c.get(("high-quality", g_course), []) + k21_group_c.get(("advanced", g_course), [])
                    if not g_uids:
                        continue
                    g_demand = len(g_uids)
                    sizes = balanced_class_sizes(g_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
                    eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(g_course, all_lecturers)

                    existing_count = sum(1 for cl in classes if cl["course_code"] == g_course and cl["program"] == prog)
                    for idx, size in enumerate(sizes, start=existing_count + 1):
                        group_code = f"{prefix}{idx:02d}"
                        best_gv = min(eligible_gvs, key=lambda g: (assigned_count[g["user_id"]], g["user_id"]))
                        assigned_count[best_gv["user_id"]] += 1

                        classes.append({
                            "class_id": f"{SEMESTER}_{g_course}_{group_code}",
                            "course_code": g_course,
                            "course_name": c_name,
                            "semester": SEMESTER,
                            "class_group": group_code,
                            "program": prog,
                            "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                            "lecturer_id": best_gv["user_id"],
                            "lecturer_name": best_gv["name"],
                            "department": dept,
                        })

                    print(f"     * {g_course} ({c_name}): demand={g_demand} (CLC+TT) -> {len(sizes)} lớp")
            else:
                all_group_c = sorted(list({c for (p, c) in k21_group_c.keys() if p == prog}))
                for g_course in all_group_c:
                    g_uids = k21_group_c.get((prog, g_course), [])
                    if not g_uids:
                        continue
                    g_demand = len(g_uids)
                    sizes = balanced_class_sizes(g_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
                    eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(g_course, all_lecturers)

                    existing_count = sum(1 for cl in classes if cl["course_code"] == g_course and cl["program"] == prog)
                    for idx, size in enumerate(sizes, start=existing_count + 1):
                        group_code = f"{prefix}{idx:02d}"
                        best_gv = min(eligible_gvs, key=lambda g: (assigned_count[g["user_id"]], g["user_id"]))
                        assigned_count[best_gv["user_id"]] += 1

                        classes.append({
                            "class_id": f"{SEMESTER}_{g_course}_{group_code}",
                            "course_code": g_course,
                            "course_name": c_name,
                            "semester": SEMESTER,
                            "class_group": group_code,
                            "program": prog,
                            "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                            "lecturer_id": best_gv["user_id"],
                            "lecturer_name": best_gv["name"],
                            "department": dept,
                        })

                    print(f"     * {g_course} ({c_name}): demand={g_demand} -> {len(sizes)} lớp")

    # -------------------------------------------------------------------------
    # D. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K20 (NĂM 4 - KỲ 7)
    # -------------------------------------------------------------------------
    print("\n--- [D] TẠO LỚP HỌC CHO KHÓA K20 (NĂM 4 - KỲ 7) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k20 = k20_students[k20_students["program"] == prog]
        p_total = len(p_k20)
        prefix = cfg["prefix"]
        prog_uids = set(p_k20["user_id"].tolist())

        # CO4029 demand: SV K20 chưa hoàn thành ở HK222
        co4029_demand = len(prog_uids - k20_passed_co4029)

        for c in k20_curriculum:
            course_code = c["course_code"]
            demand = co4029_demand if course_code == "CO4029" else p_total

            if demand <= 0:
                continue

            is_politics = course_code.startswith("SP")
            max_cap = POLITICS_CLASS_MAX_CAPACITY if is_politics else REGULAR_CLASS_MAX_CAPACITY
            sizes = balanced_class_sizes(demand, max_size=max_cap)

            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(course_code, all_lecturers)
            pref_specs = course_spec_preference.get(course_code, [])

            existing_count = sum(1 for cl in classes if cl["course_code"] == course_code and cl["program"] == prog)
            for idx, size in enumerate(sizes, start=existing_count + 1):
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
                    "course_name": c_name,
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": max_cap,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": dept,
                })

            cap_note = " [Giảng đường lớn 120]" if is_politics else ""
            print(f"   + [K20] {course_code} ({c_name}): demand={demand} -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d}){cap_note}")

        # Lộ trình tốt nghiệp sớm 3.5 năm: CHỈ DÀNH RIÊNG cho early_graduation_candidate đã hoàn thành CO4029
        early_candidates = [
            uid for uid in prog_uids
            if str(prof_by_id.get(uid, {}).get("early_graduation_candidate", "")).lower() == "true"
            and uid in k20_passed_co4029
        ]
        if early_candidates:
            for early_code in ["CO4337", "SP1007"]:
                is_politics = early_code.startswith("SP")
                max_cap = POLITICS_CLASS_MAX_CAPACITY if is_politics else REGULAR_CLASS_MAX_CAPACITY
                sizes = balanced_class_sizes(len(early_candidates), max_size=max_cap)
                eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(early_code, all_lecturers)
                pref_specs = course_spec_preference.get(early_code, [])

                existing_count = sum(1 for cl in classes if cl["course_code"] == early_code and cl["program"] == prog)
                for idx, size in enumerate(sizes, start=existing_count + 1):
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
                        "class_id": f"{SEMESTER}_{early_code}_{group_code}",
                        "course_code": early_code,
                        "course_name": f"{c_name} (Tốt nghiệp sớm)",
                        "semester": SEMESTER,
                        "class_group": group_code,
                        "program": prog,
                        "max_capacity": max_cap,
                        "lecturer_id": best_gv["user_id"],
                        "lecturer_name": best_gv["name"],
                        "department": dept,
                    })

                print(f"   + [K20 Tốt nghiệp sớm 3.5 năm] {early_code} ({c_name}): demand={len(early_candidates)} SV -> {len(sizes)} lớp")

    # 5. Xuất file CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"class_{SEMESTER.lower()}.csv"
    df_classes = pd.DataFrame(classes)
    df_classes.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số lớp học phần đã mở cho {SEMESTER} (Cả K20, K21, K22, K23): {len(df_classes)} lớp")
    return out_file


if __name__ == "__main__":
    generate_class_hk231()

