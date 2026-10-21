"""Generate course classes for semester HK212.

In this semester, two distinct cohorts attend classes simultaneously:
1. Cohort K20 in Term 4 (Sophomore - Học kỳ 4):
   - Compulsory courses:
     * SP1033: Kinh tế Chính trị Mác - Lênin (2 TC, Giảng đường lớn max capacity 120)
     * CO2039: Lập trình Nâng cao (3 TC)
     * CO2017: Hệ điều hành (3 TC)
     * MT2013: Xác suất và Thống kê (4 TC) - chỉ dành cho sinh viên CHƯA học/đạt ở HK211 (1,258 SV)
     * LA1009: Anh văn 4 (2 TC) - chỉ sinh viên hệ Đại trà đã đạt LA1007 ở HK211 (881 SV)
   - Tự chọn Khối Quản lý Kỹ thuật (Group D - 3 TC):
     * IM1013: Kinh tế học Đại cương
     * IM1023: Quản lý Sản xuất cho Kỹ sư
     * IM1025: Quản lý Dự án cho Kỹ sư
     * IM1027: Kinh tế Kỹ thuật
     * IM3001: Quản trị Kinh doanh cho Kỹ sư
     (Mỗi SV K20 đăng ký 1 môn, phân bổ đều theo nhu cầu)
   - Môn học vượt theo additional_course_rules.csv:
     * CO3093: Mạng máy tính (3 TC)
     * CO2013: Hệ cơ sở Dữ liệu (4 TC)
     (Dành cho sinh viên trong diện tốt nghiệp sớm 3.5 năm đã vượt MT2013 thành công)

2. Cohort K21 in Term 2 (Freshmen - Học kỳ 2):
   - Compulsory courses:
     * CO1007: Cấu trúc Rời rạc cho Khoa học Máy tính (4 TC)
     * MT1005: Giải tích 2 (4 TC)
     * MT1007: Đại số Tuyến tính (3 TC)
     * PH1007: Thí nghiệm Vật lý (1 TC)
     * CO1027: Kỹ thuật Lập trình (3 TC)
     * LA1005: Anh văn 2 (2 TC) - dành cho sinh viên Đại trà đã đạt/miễn LA1003 ở HK211 (905 SV)
   - Môn học vượt theo additional_course_rules.csv:
     * CO2001: Kỹ năng Chuyên nghiệp cho Kỹ sư (3 TC) per ADD_CO2001_HK2 (~271 SV)
   - Ghép sinh viên K20 học lại các môn HK2 còn nợ (CO1007, MT1005, MT1007, PH1007, CO1027, LA1005).

3. Lớp học lại cho các môn HK1 có số lượng rớt >= 20 sinh viên:
   - MT1003 (27 SV rớt) -> Mở lớp L_HL01
   - CO1005 (24 SV rớt) -> Mở lớp L_HL01
   - CO1023 (23 SV rớt) -> Mở lớp L_HL01
   (PH1003 có 19 SV và LA1003 có 11 SV < 20 nên chưa mở kỳ này).
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

# Add analysis & rules directory
ANALYSIS_DIR = ROOT_DIR / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))
if str(RULES_DIR) not in sys.path:
    sys.path.insert(0, str(RULES_DIR))

from academic_rules import balanced_class_sizes
from analysis_helpers import (
    get_curriculum_for_cohort_semester,
    get_lecturers_by_course,
    load_lecturers_table,
)

SEMESTER = "HK212"
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

GROUP_D_COURSES = ["IM1013", "IM1023", "IM1025", "IM1027", "IM3001"]


def get_all_passed_courses_up_to_hk211() -> Dict[str, Set[str]]:
    """Retrieve all courses passed by each student across HK201, HK202, HK211."""
    passed_map: Dict[str, Set[str]] = defaultdict(set)
    for sem in ["hk201", "hk202", "hk211"]:
        enr_file = ENROLLMENTS_DIR / f"enrollment_{sem}.csv"
        if enr_file.exists():
            df_enr = pd.read_csv(enr_file, encoding="utf-8-sig", dtype={"student_id": str})
            for _, r in df_enr[df_enr["passed"] == True].iterrows():
                passed_map[str(r["student_id"])].add(str(r["course_id"]))
    return passed_map


def get_top_acceleration_course_for_term(term_code: str = "HK2") -> Tuple[str, str]:
    """Retrieve top-priority acceleration course for the term from additional_course_rules.csv."""
    rules_file = RULES_DIR / "additional_course_rules.csv"
    if rules_file.exists():
        df_rules = pd.read_csv(rules_file)
        valid_rules = df_rules[
            (df_rules["available_from_semester"] == term_code)
            & (df_rules["activation_condition"] == "under_18_or_eligible_acceleration")
        ].sort_values("priority")
        if not valid_rules.empty:
            top_row = valid_rules.iloc[0]
            return str(top_row["course_code"]), str(top_row["course_name"])
    return "CH1003", "Hóa đại cương"


def get_k21_acceleration_students(k21_students: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K21 students eligible to accelerate course from additional_course_rules.csv (HK2)."""
    profiles_file = USERS_DIR / "student_profiles.csv"
    if not profiles_file.exists():
        return defaultdict(list)
    df_prof = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")

    top_code, _ = get_top_acceleration_course_for_term("HK2")
    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k21_students.iterrows():
        uid = str(row["user_id"])
        prog = row["program"]
        p = prof_by_id.get(uid, {})
        base_score = float(p.get("base_score", 0.0) or 0.0)
        is_early_candidate = str(p.get("early_graduation_candidate", "")).lower() == "true"

        seed_val = int(hashlib.sha256(f"{uid}:{top_code.lower()}_accel".encode()).hexdigest()[:8], 16)
        prob = seed_val % 100

        if is_early_candidate or (base_score >= 7.8 and prob < 35):
            accelerating_by_prog[prog].append(uid)

    return accelerating_by_prog


def get_k20_acceleration_students(k20_students: pd.DataFrame, k20_passed_mt2013: Set[str]) -> Dict[str, List[str]]:
    """Identify K20 students eligible to accelerate CO3093 and CO2013 in HK4.

    Students who successfully passed MT2013 early in HK211 have credit space
    and qualify to accelerate CO3093 (Computer Networks) & CO2013 (Database Systems).
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
        is_early_candidate = str(p.get("early_graduation_candidate", "")).lower() == "true"

        # Students who completed MT2013 early are fast-track candidates
        if uid in k20_passed_mt2013 or is_early_candidate:
            accelerating_by_prog[prog].append(uid)

    return accelerating_by_prog


def get_k20_group_d_distribution(k20_students: pd.DataFrame) -> Dict[Tuple[str, str], List[str]]:
    """Distribute K20 students among the 5 Group D elective courses."""
    choice_map: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, row in k20_students.iterrows():
        uid = str(row["user_id"])
        prog = row["program"]
        seed_val = int(hashlib.sha256(f"{uid}:group_d".encode()).hexdigest()[:8], 16)
        c_code = GROUP_D_COURSES[seed_val % len(GROUP_D_COURSES)]
        choice_map[(prog, c_code)].append(uid)
    return choice_map


def get_all_lecturers_with_fallback(course_code: str, all_lecturers: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], str, str]:
    """Retrieve eligible lecturers for a course, with safe fallback if department has none."""
    info = get_lecturers_by_course(course_code)
    eligible = info["eligible_lecturers"]
    dept = info["department"]
    c_name = info["course_name_vi"]

    if not eligible:
        # Fallback to CSE lecturers for courses whose faculty has no standalone lecturer pool in DB
        cse_lecturers = [
            l for l in all_lecturers
            if "Khoa học và Kỹ thuật Máy tính" in l["department"]
        ]
        eligible = cse_lecturers if cse_lecturers else all_lecturers

    return eligible, dept, c_name


def generate_class_hk212() -> Path:
    """Generate all class sections for HK212 and export to class_hk212.csv."""
    print(f"=== KHỞI CHẠY SINH LỚP HỌC PHẦN CHO HỌC KỲ {SEMESTER} (ĐA KHÓA: K20 & K21) ===")

    # 1. Đọc sinh viên K20 và K21
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    k21_students = df_students[df_students["user_id"].str.startswith("21")].copy()
    print(f"1. Sinh viên K20 (Năm 2 - HK4): {len(k20_students)} SV | K21 (Năm 1 - HK2): {len(k21_students)} SV.")

    # 2. Đọc lịch sử các môn đã đạt của sinh viên qua các kỳ
    passed_map = get_all_passed_courses_up_to_hk211()

    # K20 đã học và đạt MT2013 ở HK211
    enr_hk211_file = ENROLLMENTS_DIR / "enrollment_hk211.csv"
    df_hk211 = pd.read_csv(enr_hk211_file, encoding="utf-8-sig", dtype={"student_id": str})
    k20_passed_mt2013 = set(
        df_hk211[(df_hk211["course_id"] == "MT2013") & (df_hk211["passed"] == True)]["student_id"].tolist()
    )
    print(f"2. K20 đã hoàn thành MT2013 từ HK211: {len(k20_passed_mt2013)} SV (miễn học lại ở HK212).")

    # K20 sinh viên Đại trà đạt LA1007 ở HK211 -> đủ điều kiện học LA1009
    k20_passed_la1007 = set(
        df_hk211[(df_hk211["course_id"] == "LA1007") & (df_hk211["passed"] == True)]["student_id"].tolist()
    )
    print(f"   K20 Đại trà đạt LA1007: {len(k20_passed_la1007)} SV -> đủ điều kiện học LA1009.")

    # K21 sinh viên Đại trà đạt/miễn LA1003 ở HK211 -> đủ điều kiện học LA1005
    k21_passed_la1003 = set(
        df_hk211[(df_hk211["course_id"] == "LA1003") & (df_hk211["passed"] == True)]["student_id"].tolist()
    )
    print(f"   K21 Đại trà đạt/miễn LA1003: {len(k21_passed_la1003)} SV -> đủ điều kiện học LA1005.")

    # 3. K20 còn nợ môn HK2 cần học lại ghép cùng K21
    enr_hk202_file = ENROLLMENTS_DIR / "enrollment_hk202.csv"
    df_hk202 = pd.read_csv(enr_hk202_file, encoding="utf-8-sig", dtype={"student_id": str})
    k20_need_retake_hk2: Dict[str, Set[str]] = defaultdict(set)
    for _, r in df_hk202[df_hk202["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        if cid not in passed_map[sid]:
            k20_need_retake_hk2[cid].add(sid)

    # 4. Học sinh cần học lại môn HK1 (ngưỡng >= 20 SV)
    hk1_candidates = ["MT1003", "CO1005", "CO1023", "PH1003", "LA1003"]
    hk1_retake_demand: Dict[str, List[str]] = {}
    for c in hk1_candidates:
        failed_records = pd.concat([
            df_hk211[(df_hk211["course_id"] == c) & (df_hk211["passed"] == False)],
            df_hk202[(df_hk202["course_id"] == c) & (df_hk202["passed"] == False)] if "course_id" in df_hk202 else pd.DataFrame(),
        ])
        unresolved = [
            sid for sid in failed_records["student_id"].unique()
            if c not in passed_map[sid]
        ]
        if len(unresolved) >= 20:
            hk1_retake_demand[c] = unresolved
            print(f"   [Mở lớp học lại] {c}: {len(unresolved)} SV (>= 20 SV).")
        else:
            print(f"   [Chưa đủ mở lớp] {c}: {len(unresolved)} SV (< 20 SV).")

    # 5. Môn học K21 (HK2) và K20 (HK4) từ CTĐT chuẩn
    k21_curriculum = get_curriculum_for_cohort_semester("K21", 2)["compulsory_courses"]
    k20_curriculum = get_curriculum_for_cohort_semester("K20", 4)["compulsory_courses"]

    print("\n3. Môn học K21 (Học kỳ 2):", ", ".join(c["course_code"] for c in k21_curriculum))
    print("   Môn học K20 (Học kỳ 4):", ", ".join(c["course_code"] for c in k20_curriculum))

    # Sinh viên học vượt
    k21_accel = get_k21_acceleration_students(k21_students)
    k20_accel = get_k20_acceleration_students(k20_students, k20_passed_mt2013)
    k20_group_d = get_k20_group_d_distribution(k20_students)

    all_lecturers = load_lecturers_table()
    assigned_count: Dict[str, int] = defaultdict(int)
    classes: List[Dict[str, Any]] = []

    # Cấu hình chuyên môn ưu tiên cho giảng viên CSE
    course_spec_preference: Dict[str, List[str]] = {
        "CO1007": ["Khoa học Máy tính"],
        "CO1027": ["Công nghệ Phần mềm", "Khoa học Máy tính"],
        "CO2039": ["Công nghệ Phần mềm"],
        "CO2017": ["Hệ thống và Mạng máy tính", "Kỹ thuật Máy tính"],
        "CO3093": ["Hệ thống và Mạng máy tính", "An ninh mạng"],
        "CO2013": ["Khoa học Dữ liệu", "Khoa học Máy tính"],
    }

    print("\n4. Phân bổ lớp học theo từng hệ đào tạo cho cả 2 khóa...")

    # -------------------------------------------------------------------------
    # A. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K21 (HỌC KỲ 2)
    # -------------------------------------------------------------------------
    print("\n--- [A] TẠO LỚP HỌC CHO KHÓA K21 (TÂN SINH VIÊN - KỲ 2) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k21 = k21_students[k21_students["program"] == prog]
        p_total = len(p_k21)
        prefix = cfg["prefix"]

        # Với LA1005: CLC và TT đã được miễn; Đại trà cần đạt/miễn LA1003
        if prog in ("high-quality", "advanced"):
            la1005_demand = 0
            print(f"* K21 {cfg['name_vi']} ({prog}) - {p_total} SV (Đã miễn toàn bộ Anh văn)")
        else:
            prog_uids = set(p_k21["user_id"].tolist())
            eligible_la1005 = prog_uids.intersection(k21_passed_la1003)
            la1005_demand = len(eligible_la1005)
            print(f"* K21 {cfg['name_vi']} ({prog}) - {p_total} SV (Đủ điều kiện học LA1005: {la1005_demand} SV)")

        for c in k21_curriculum:
            course_code = c["course_code"]
            # K20 nợ môn HK2 học ghép
            k20_retake_uids = [
                uid for uid in k20_need_retake_hk2.get(course_code, set())
                if uid in set(k20_students[k20_students["program"] == prog]["user_id"])
            ]
            k20_retake_count = len(k20_retake_uids)

            if course_code == "LA1005":
                demand = la1005_demand + k20_retake_count
            else:
                demand = p_total + k20_retake_count

            if demand <= 0:
                continue

            sizes = balanced_class_sizes(demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(course_code, all_lecturers)
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
                    "course_name": c_name,
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": dept,
                })

            retake_str = f" (+{k20_retake_count} K20 học ghép)" if k20_retake_count > 0 else ""
            print(f"   + [K21] {course_code} ({c_name}): demand={demand}{retake_str} -> {len(sizes)} lớp ({prefix}01..{prefix}{len(sizes):02d})")

        # Môn học vượt K21 theo additional_course_rules.csv (ví dụ CH1003 hoặc CO2001 theo priority)
        accel_k21_prog = k21_accel.get(prog, [])
        if accel_k21_prog:
            accel_code, accel_rule_name = get_top_acceleration_course_for_term("HK2")
            accel_demand = len(accel_k21_prog)
            sizes = balanced_class_sizes(accel_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(accel_code, all_lecturers)

            # Bắt đầu đánh số lớp học vượt tiếp nối sau các lớp thường
            existing_count = sum(1 for cl in classes if cl["course_code"] == accel_code and cl["program"] == prog)
            for idx, size in enumerate(sizes, start=existing_count + 1):
                group_code = f"{prefix}{idx:02d}"
                best_gv = min(
                    eligible_gvs,
                    key=lambda g: (assigned_count[g["user_id"]], g["user_id"]),
                )
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

            print(f"   + [K21 Học vượt] {accel_code}: demand={accel_demand} SV -> {len(sizes)} lớp")

    # -------------------------------------------------------------------------
    # B. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K20 (HỌC KỲ 4)
    # -------------------------------------------------------------------------
    print("\n--- [B] TẠO LỚP HỌC CHO KHÓA K20 (NĂM 2 - KỲ 4) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k20 = k20_students[k20_students["program"] == prog]
        p_total = len(p_k20)
        prefix = cfg["prefix"]

        # LA1009: CLC/TT miễn; Đại trà: SV đạt LA1007
        if prog in ("high-quality", "advanced"):
            la1009_demand = 0
            print(f"* K20 {cfg['name_vi']} ({prog}) - {p_total} SV (Đã miễn toàn bộ Anh văn)")
        else:
            prog_uids = set(p_k20["user_id"].tolist())
            eligible_la1009 = prog_uids.intersection(k20_passed_la1007)
            la1009_demand = len(eligible_la1009)
            print(f"* K20 {cfg['name_vi']} ({prog}) - {p_total} SV (Đủ điều kiện học LA1009: {la1009_demand} SV)")

        # MT2013 demand: chỉ những SV chưa đạt ở HK211
        prog_uids = set(p_k20["user_id"].tolist())
        mt2013_demand = len(prog_uids - k20_passed_mt2013)

        for c in k20_curriculum:
            course_code = c["course_code"]
            if course_code == "LA1009":
                demand = la1009_demand
            elif course_code == "MT2013":
                demand = mt2013_demand
            else:
                demand = p_total

            if demand <= 0:
                continue

            is_politics = course_code.startswith("SP")
            max_cap = POLITICS_CLASS_MAX_CAPACITY if is_politics else REGULAR_CLASS_MAX_CAPACITY
            sizes = balanced_class_sizes(demand, max_size=max_cap)

            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(course_code, all_lecturers)
            pref_specs = course_spec_preference.get(course_code, [])

            # Đánh số nhóm lớp: tính số lớp đã có cho môn này trong hệ (nếu có)
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

        # Tự chọn Khối Quản lý Kỹ thuật (Group D) cho K20
        print(f"   + [K20 Tự chọn Quản lý - Group D]:")
        for g_course in GROUP_D_COURSES:
            g_uids = k20_group_d.get((prog, g_course), [])
            if not g_uids:
                continue
            g_demand = len(g_uids)
            sizes = balanced_class_sizes(g_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(g_course, all_lecturers)

            existing_count = sum(1 for cl in classes if cl["course_code"] == g_course and cl["program"] == prog)
            for idx, size in enumerate(sizes, start=existing_count + 1):
                group_code = f"{prefix}{idx:02d}"
                best_gv = min(
                    eligible_gvs,
                    key=lambda g: (assigned_count[g["user_id"]], g["user_id"]),
                )
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

        # Môn học vượt K20: CO3093 (Mạng máy tính) và CO2013 (Hệ cơ sở Dữ liệu)
        accel_k20_prog = k20_accel.get(prog, [])
        if accel_k20_prog:
            accel_demand = len(accel_k20_prog)
            for accel_code in ["CO3093", "CO2013"]:
                sizes = balanced_class_sizes(accel_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
                eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(accel_code, all_lecturers)
                pref_specs = course_spec_preference.get(accel_code, [])

                existing_count = sum(1 for cl in classes if cl["course_code"] == accel_code and cl["program"] == prog)
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

                print(f"   + [K20 Học vượt] {accel_code} ({c_name}): demand={accel_demand} SV -> {len(sizes)} lớp")

    # -------------------------------------------------------------------------
    # C. PHÂN BỔ LỚP HỌC LẠI CHO CÁC MÔN HK1 (NGƯỠNG >= 20 SV)
    # -------------------------------------------------------------------------
    print("\n--- [C] TẠO LỚP HỌC LẠI CHO CÁC MÔN HK1 (NHU CẦU >= 20 SV) ---")
    for retake_code, uids in hk1_retake_demand.items():
        retake_demand = len(uids)
        sizes = balanced_class_sizes(retake_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
        eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(retake_code, all_lecturers)

        for idx, size in enumerate(sizes, start=1):
            group_code = f"L_HL{idx:02d}"
            best_gv = min(
                eligible_gvs,
                key=lambda g: (assigned_count[g["user_id"]], g["user_id"]),
            )
            assigned_count[best_gv["user_id"]] += 1

            classes.append({
                "class_id": f"{SEMESTER}_{retake_code}_{group_code}",
                "course_code": retake_code,
                "course_name": f"{c_name} (Học lại)",
                "semester": SEMESTER,
                "class_group": group_code,
                "program": "standard",
                "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                "lecturer_id": best_gv["user_id"],
                "lecturer_name": best_gv["name"],
                "department": dept,
            })

        print(f"   + [Lớp học lại] {retake_code} ({c_name}): demand={retake_demand} SV -> {len(sizes)} lớp ({group_code})")

    # 6. Xuất file CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"class_{SEMESTER.lower()}.csv"
    df_classes = pd.DataFrame(classes)
    df_classes.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số lớp học phần đã mở cho {SEMESTER} (Cả K20 và K21): {len(df_classes)} lớp")

    print("\nThống kê số lớp theo môn học:")
    print(df_classes.groupby(["course_code", "program"])["class_id"].count())

    return out_file


if __name__ == "__main__":
    generate_class_hk212()

