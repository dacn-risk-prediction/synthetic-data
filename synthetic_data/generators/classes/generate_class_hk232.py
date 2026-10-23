"""Generate course classes for semester HK232.

In this semester, four distinct cohorts attend classes simultaneously:
1. Cohort K23 in Term 2 (Freshmen - Học kỳ 2):
   - Compulsory courses:
     * CO1007: Cấu trúc Rời rạc cho Khoa học Máy tính (4 TC)
     * MT1005: Giải tích 2 (4 TC)
     * MT1007: Đại số Tuyến tính (3 TC)
     * PH1007: Thí nghiệm Vật lý (1 TC)
     * CO1027: Kỹ thuật Lập trình (3 TC)
     * LA1005: Anh văn 2 (2 TC - Standard only, SV đã đạt/miễn LA1003)
     * PE1005: Giáo dục Thể chất 2 (0 TC)
     * MI1003: Giáo dục Quốc phòng (0 TC)
   - Môn học vượt theo additional_course_rules.csv:
     * CH1003 (Hóa đại cương - priority 15 per ADD_CH1003_HK2)
   - Sinh viên khóa trước nợ môn HK2 học ghép vào các lớp này.

2. Cohort K22 in Term 4 (Sophomore - Học kỳ 4):
   - Compulsory courses:
     * SP1033: Kinh tế Chính trị Mác - Lênin (2 TC, Giảng đường lớn max capacity 120)
     * CO2039: Lập trình Nâng cao (3 TC)
     * CO2017: Hệ điều hành (3 TC)
     * MT2013: Xác suất và Thống kê (4 TC) - SV K22 chưa học vượt ở HK231 (1282 SV)
     * LA1009: Anh văn 4 (2 TC - Standard only, SV đã đạt LA1007 ở HK231)
   - Tự chọn Khối Quản lý Kỹ thuật (Group D - 3 TC):
     * IM1013, IM1023, IM1025, IM1027, IM3001
   - Môn học vượt theo additional_course_rules.csv:
     * CO3093: Mạng máy tính (3 TC per ADD_CO3093_HK4)
     * CO2013: Hệ cơ sở Dữ liệu (4 TC per ADD_CO2013_HK4)
   - Sinh viên khóa trước nợ môn HK4 học ghép vào các lớp này.

3. Cohort K21 in Term 6 (Junior - Học kỳ 6):
   - Compulsory courses:
     * CH1003: Hóa đại cương (3 TC) - SV K21 chưa học vượt ở HK212/HK222
     * SP1037: Tư tưởng Hồ Chí Minh (2 TC, Giảng đường lớn max capacity 120)
     * CO3093: Mạng máy tính (3 TC) - SV K21 chưa học vượt ở HK222
   - Lộ trình tốt nghiệp sớm (242 SV tốt nghiệp sớm 3.5 năm):
     * CO3061: Nhập môn Trí tuệ Nhân tạo (3 TC per EARLY_CO3061_HK6)
     * CO4029: Đồ án Chuyên ngành (2 TC per EARLY_CO4029_HK6)
   - Tự chọn ngành cho các sinh viên K21 còn lại:
     * Đăng ký 2 môn thuộc Group C: CO3061, CO3029, CO3043, CO3045, CO3021, CO3011

4. Cohort K20 in Term 8 (Senior - Học kỳ 8 - Tốt nghiệp chuẩn 4 năm):
   - 242 sinh viên tốt nghiệp sớm 3.5 năm đã hoàn thành CO4337 và SP1007 ở HK231 nên ĐÃ TỐT NGHIỆP (không học HK232).
   - 1,258 sinh viên K20 còn lại hoàn tất tốt nghiệp chuẩn 4 năm:
     * CO4337: Đồ án Tốt nghiệp (4 TC)
     * SP1007: Pháp luật Việt Nam Đại cương (2 TC, Giảng đường lớn max capacity 120)

5. Lớp học lại cho các môn HK1/lẻ có số lượng rớt >= 20 sinh viên:
   - MT1003, PH1003, CO1005, CO1023, CO2011, CO2003, CO2007, SP1031 -> Lớp L_HL
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

SEMESTER = "HK232"
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
GROUP_C_COURSES = ["CO3061", "CO3029", "CO3043", "CO3045", "CO3021", "CO3011"]


def get_all_passed_courses_up_to_hk231() -> Dict[str, Set[str]]:
    """Retrieve all courses passed by each student across all prior semesters."""
    passed_map: Dict[str, Set[str]] = defaultdict(set)
    for sem in ["hk201", "hk202", "hk211", "hk212", "hk221", "hk222", "hk231"]:
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


def get_k23_acceleration_students(k23_students: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K23 students eligible to accelerate CH1003 (HK2)."""
    profiles_file = USERS_DIR / "student_profiles.csv"
    if not profiles_file.exists():
        return defaultdict(list)
    df_prof = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")

    top_code, _ = get_top_acceleration_course_for_term("HK2")
    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k23_students.iterrows():
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


def get_k22_acceleration_students(k22_students: pd.DataFrame, k22_passed_mt2013: Set[str]) -> Dict[str, List[str]]:
    """Identify K22 students eligible to accelerate CO3093 and CO2013 in HK4."""
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
        is_early_candidate = str(p.get("early_graduation_candidate", "")).lower() == "true"

        if uid in k22_passed_mt2013 or is_early_candidate:
            accelerating_by_prog[prog].append(uid)

    return accelerating_by_prog


def get_k22_group_d_distribution(k22_students: pd.DataFrame) -> Dict[Tuple[str, str], List[str]]:
    """Distribute K22 students among Group D elective courses."""
    choice_map: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, row in k22_students.iterrows():
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
        cse_lecturers = [
            l for l in all_lecturers
            if "Khoa học và Kỹ thuật Máy tính" in l["department"]
        ]
        eligible = cse_lecturers if cse_lecturers else all_lecturers

    return eligible, dept, c_name


def generate_class_hk232() -> Path:
    """Generate all class sections for HK232 and export to class_hk232.csv."""
    print(f"=== KHỞI CHẠY SINH LỚP HỌC PHẦN CHO HỌC KỲ {SEMESTER} (ĐA KHÓA: K20, K21, K22, K23) ===")

    # 1. Đọc sinh viên K20, K21, K22, K23
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    k21_students = df_students[df_students["user_id"].str.startswith("21")].copy()
    k22_students = df_students[df_students["user_id"].str.startswith("22")].copy()
    k23_students = df_students[df_students["user_id"].str.startswith("23")].copy()
    print(f"1. Tổng SV danh nghĩa: K20: {len(k20_students)} | K21: {len(k21_students)} | K22: {len(k22_students)} | K23: {len(k23_students)}")

    # 2. Lịch sử các môn đã đạt
    passed_map = get_all_passed_courses_up_to_hk231()

    # K20 tốt nghiệp sớm ở HK231 (đã hoàn thành CO4337 và SP1007)
    k20_graduated_uids = {uid for uid in k20_students["user_id"] if "CO4337" in passed_map[uid] and "SP1007" in passed_map[uid]}
    k20_active_students = k20_students[~k20_students["user_id"].isin(k20_graduated_uids)].copy()
    print(f"2. K20 đã tốt nghiệp sớm sau HK231: {len(k20_graduated_uids)} SV -> K20 còn lại học HK232 (Học kỳ 8): {len(k20_active_students)} SV.")

    # K21 đã học vượt CH1003 hoặc CO3093 ở các kỳ trước
    k21_passed_ch1003 = {uid for uid in k21_students["user_id"] if "CH1003" in passed_map[uid]}
    k21_passed_co3093 = {uid for uid in k21_students["user_id"] if "CO3093" in passed_map[uid]}
    print(f"   K21 đã hoàn thành CH1003 sớm: {len(k21_passed_ch1003)} SV | CO3093 sớm: {len(k21_passed_co3093)} SV.")

    # K22 đã học vượt MT2013 ở HK231
    k22_passed_mt2013 = {uid for uid in k22_students["user_id"] if "MT2013" in passed_map[uid]}
    print(f"   K22 đã hoàn thành MT2013 sớm: {len(k22_passed_mt2013)} SV (miễn học ở HK232).")

    # K22 Đại trà đạt LA1007 ở HK231 -> đủ điều kiện học LA1009
    k22_passed_la1007 = {uid for uid in k22_students["user_id"] if "LA1007" in passed_map[uid]}

    # K23 Đại trà đạt/miễn LA1003 ở HK231 -> đủ điều kiện học LA1005
    k23_passed_la1003 = {uid for uid in k23_students["user_id"] if "LA1003" in passed_map[uid]}

    # 3. Nhu cầu học lại
    all_prev_enrollments = pd.concat([
        pd.read_csv(ENROLLMENTS_DIR / f"enrollment_{sem}.csv", encoding="utf-8-sig", dtype={"student_id": str})
        for sem in ["hk201", "hk202", "hk211", "hk212", "hk221", "hk222", "hk231"]
    ])
    retake_demand: Dict[str, Set[str]] = defaultdict(set)
    for _, r in all_prev_enrollments[all_prev_enrollments["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        if cid not in passed_map[sid]:
            retake_demand[cid].add(sid)

    # Học lại các môn HK1/lẻ (ngưỡng >= 20)
    hk1_candidates = ["MT1003", "PH1003", "CO1005", "CO1023", "CO2011", "CO2003", "CO2007", "SP1031"]
    hk1_retake_demand: Dict[str, List[str]] = {}
    for c in hk1_candidates:
        uids = list(retake_demand.get(c, set()))
        if len(uids) >= 20:
            hk1_retake_demand[c] = uids
            print(f"   [Mở lớp học lại] {c}: {len(uids)} SV (>= 20 SV).")
        else:
            print(f"   [Chưa đủ mở lớp riêng] {c}: {len(uids)} SV (< 20 SV).")

    # 4. CTĐT chuẩn các khóa
    k23_curriculum = get_curriculum_for_cohort_semester("K23", 2)["compulsory_courses"]
    k22_curriculum = get_curriculum_for_cohort_semester("K22", 4)["compulsory_courses"]
    k21_curriculum = get_curriculum_for_cohort_semester("K21", 6)["compulsory_courses"]
    k20_curriculum = get_curriculum_for_cohort_semester("K20", 8)["compulsory_courses"]

    print("\n3. Môn học K23 (HK2):", ", ".join(c["course_code"] for c in k23_curriculum))
    print("   Môn học K22 (HK4):", ", ".join(c["course_code"] for c in k22_curriculum))
    print("   Môn học K21 (HK6):", ", ".join(c["course_code"] for c in k21_curriculum))
    print("   Môn học K20 (HK8):", ", ".join(c["course_code"] for c in k20_curriculum))

    k23_accel = get_k23_acceleration_students(k23_students)
    k22_accel = get_k22_acceleration_students(k22_students, k22_passed_mt2013)
    k22_group_d = get_k22_group_d_distribution(k22_students)

    all_lecturers = load_lecturers_table()
    assigned_count: Dict[str, int] = defaultdict(int)
    classes: List[Dict[str, Any]] = []

    course_spec_preference: Dict[str, List[str]] = {
        "CO1007": ["Khoa học Máy tính"],
        "CO1027": ["Công nghệ Phần mềm", "Khoa học Máy tính"],
        "CO2039": ["Công nghệ Phần mềm"],
        "CO2017": ["Hệ thống và Mạng máy tính", "Kỹ thuật Máy tính"],
        "CO3093": ["Hệ thống và Mạng máy tính", "An ninh mạng"],
        "CO2013": ["Khoa học Dữ liệu", "Khoa học Máy tính"],
        "CO3061": ["Trí tuệ Nhân tạo", "Khoa học Dữ liệu"],
        "CO4029": ["Công nghệ Phần mềm", "Khoa học Máy tính"],
        "CO4337": ["Khoa học Máy tính", "Hệ thống và Mạng máy tính", "Công nghệ Phần mềm", "Khoa học Dữ liệu", "Trí tuệ Nhân tạo"],
    }

    # -------------------------------------------------------------------------
    # A. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K23 (TÂN SINH VIÊN - KỲ 2)
    # -------------------------------------------------------------------------
    print("\n--- [A] TẠO LỚP HỌC CHO KHÓA K23 (TÂN SINH VIÊN - KỲ 2) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k23 = k23_students[k23_students["program"] == prog]
        p_total = len(p_k23)
        prefix = cfg["prefix"]

        if prog in ("high-quality", "advanced"):
            la1005_demand = 0
            print(f"* K23 {cfg['name_vi']} ({prog}) - {p_total} SV (Đã miễn toàn bộ Anh văn)")
        else:
            prog_uids = set(p_k23["user_id"].tolist())
            eligible_la1005 = prog_uids.intersection(k23_passed_la1003)
            la1005_demand = len(eligible_la1005)
            print(f"* K23 {cfg['name_vi']} ({prog}) - {p_total} SV (Đủ điều kiện học LA1005: {la1005_demand} SV)")

        for c in k23_curriculum:
            course_code = c["course_code"]
            retakers = [
                uid for uid in retake_demand.get(course_code, set())
                if uid in set(df_students[df_students["program"] == prog]["user_id"])
            ]
            retake_count = len(retakers)

            if course_code == "LA1005":
                demand = la1005_demand + retake_count
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

            retake_str = f" (+{retake_count} SV học ghép)" if retake_count > 0 else ""
            print(f"   + [K23] {course_code} ({c_name}): demand={demand}{retake_str} -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d})")

        # Môn học vượt K23 per additional_course_rules.csv (CH1003 priority 15)
        accel_k23_prog = k23_accel.get(prog, [])
        if accel_k23_prog:
            accel_code, _ = get_top_acceleration_course_for_term("HK2")
            accel_demand = len(accel_k23_prog)
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

            print(f"   + [K23 Học vượt] {accel_code}: demand={accel_demand} SV -> {len(sizes)} lớp")

    # -------------------------------------------------------------------------
    # B. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K22 (NĂM 2 - KỲ 4)
    # -------------------------------------------------------------------------
    print("\n--- [B] TẠO LỚP HỌC CHO KHÓA K22 (NĂM 2 - KỲ 4) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k22 = k22_students[k22_students["program"] == prog]
        p_total = len(p_k22)
        prefix = cfg["prefix"]
        prog_uids = set(p_k22["user_id"].tolist())

        if prog in ("high-quality", "advanced"):
            la1009_demand = 0
            print(f"* K22 {cfg['name_vi']} ({prog}) - {p_total} SV (Đã miễn toàn bộ Anh văn)")
        else:
            eligible_la1009 = prog_uids.intersection(k22_passed_la1007)
            la1009_demand = len(eligible_la1009)
            print(f"* K22 {cfg['name_vi']} ({prog}) - {p_total} SV (Đủ điều kiện học LA1009: {la1009_demand} SV)")

        mt2013_demand = len(prog_uids - k22_passed_mt2013)

        for c in k22_curriculum:
            course_code = c["course_code"]
            retakers = [
                uid for uid in retake_demand.get(course_code, set())
                if uid in set(k21_students[k21_students["program"] == prog]["user_id"])
            ]
            retake_count = len(retakers)

            if course_code == "LA1009":
                demand = la1009_demand + retake_count
            elif course_code == "MT2013":
                demand = mt2013_demand + retake_count
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

            retake_str = f" (+{retake_count} K21 học ghép)" if retake_count > 0 else ""
            cap_note = " [Giảng đường lớn 120]" if is_politics else ""
            print(f"   + [K22] {course_code} ({c_name}): demand={demand}{retake_str} -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d}){cap_note}")

        # Tự chọn Quản lý Kỹ thuật (Group D) cho K22
        print(f"   + [K22 Tự chọn Quản lý - Group D]:")
        for g_course in GROUP_D_COURSES:
            g_uids = k22_group_d.get((prog, g_course), [])
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

        # Môn học vượt K22: CO3093 và CO2013
        accel_k22_prog = k22_accel.get(prog, [])
        if accel_k22_prog:
            accel_demand = len(accel_k22_prog)
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

                print(f"   + [K22 Học vượt] {accel_code} ({c_name}): demand={accel_demand} SV -> {len(sizes)} lớp")

    # -------------------------------------------------------------------------
    # C. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K21 (NĂM 3 - KỲ 6)
    # -------------------------------------------------------------------------
    print("\n--- [C] TẠO LỚP HỌC CHO KHÓA K21 (NĂM 3 - KỲ 6) ---")
    profiles_file = USERS_DIR / "student_profiles.csv"
    df_prof = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")

    for prog, cfg in PROGRAM_CONFIG.items():
        p_k21 = k21_students[k21_students["program"] == prog]
        p_total = len(p_k21)
        prefix = cfg["prefix"]
        prog_uids = set(p_k21["user_id"].tolist())

        # SV K21 chưa học CH1003 hoặc CO3093 ở các kỳ trước
        ch1003_demand = len(prog_uids - k21_passed_ch1003)
        co3093_demand = len(prog_uids - k21_passed_co3093)

        for c in k21_curriculum:
            course_code = c["course_code"]
            if course_code == "CO3093":
                demand = co3093_demand
            elif course_code == "CH1003":
                demand = ch1003_demand
            else:
                demand = p_total

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

        # Lộ trình tốt nghiệp sớm 3.5 năm: CHỈ DÀNH RIÊNG CHO early_graduation_candidate (Hệ Tiên tiến học chung với CLC)
        if prog == "advanced":
            print(f"   + [K21 Tốt nghiệp sớm]: Ghép học chung lớp với hệ Chất lượng cao (CC)")
            print(f"   + [K21 Tự chọn ngành - Group C]: Ghép học chung lớp với hệ Chất lượng cao (CC)")
        else:
            if prog == "high-quality":
                k21_adv_uids = set(k21_students[k21_students["program"] == "advanced"]["user_id"])
                combined_prog_uids = prog_uids | k21_adv_uids
                early_candidates = [
                    uid for uid in combined_prog_uids
                    if str(prof_by_id.get(uid, {}).get("early_graduation_candidate", "")).lower() == "true"
                ]
            else:
                combined_prog_uids = prog_uids
                early_candidates = [
                    uid for uid in prog_uids
                    if str(prof_by_id.get(uid, {}).get("early_graduation_candidate", "")).lower() == "true"
                ]

            if early_candidates:
                for early_code in ["CO3061", "CO4029"]:
                    sizes = balanced_class_sizes(len(early_candidates), max_size=REGULAR_CLASS_MAX_CAPACITY)
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
                            "course_name": f"{c_name} (Học sớm)",
                            "semester": SEMESTER,
                            "class_group": group_code,
                            "program": prog,
                            "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                            "lecturer_id": best_gv["user_id"],
                            "lecturer_name": best_gv["name"],
                            "department": dept,
                        })

                    suffix_note = " (CLC+TT)" if prog == "high-quality" else ""
                    print(f"   + [K21 Tốt nghiệp sớm] {early_code} ({c_name}): demand={len(early_candidates)} SV{suffix_note} -> {len(sizes)} lớp")

            # Tự chọn ngành Group C cho sinh viên K21 thông thường (chọn 2 môn theo chuyên ngành)
            regular_k21_uids = [uid for uid in combined_prog_uids if uid not in set(early_candidates)]
            if regular_k21_uids:
                spec_map = get_student_specialization_map()
                c_demand_map: Dict[str, int] = defaultdict(int)
                for uid in regular_k21_uids:
                    spec = spec_map.get(uid, "Khoa học Máy tính")
                    prev_passed = passed_map.get(uid, set())
                    c1 = select_student_group_c_course(uid, "K21", spec, seed_salt="k21_group_c_1_hk232", exclude_courses=prev_passed)
                    c2 = select_student_group_c_course(uid, "K21", spec, seed_salt="k21_group_c_2_hk232", exclude_courses=prev_passed | {c1})
                    c_demand_map[c1] += 1
                    c_demand_map[c2] += 1

                suffix_note = " (CLC+TT)" if prog == "high-quality" else ""
                print(f"   + [K21 Tự chọn ngành - Group C ({len(c_demand_map)} môn)]{suffix_note} ({len(regular_k21_uids)} SV):")
                for c_code, c_demand in c_demand_map.items():
                    if c_demand <= 0:
                        continue
                    sizes = balanced_class_sizes(c_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
                    eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(c_code, all_lecturers)
                    pref_specs = course_spec_preference.get(c_code, [])

                    existing_count = sum(1 for cl in classes if cl["course_code"] == c_code and cl["program"] == prog)
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
                            "class_id": f"{SEMESTER}_{c_code}_{group_code}",
                            "course_code": c_code,
                            "course_name": c_name,
                            "semester": SEMESTER,
                            "class_group": group_code,
                            "program": prog,
                            "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                            "lecturer_id": best_gv["user_id"],
                            "lecturer_name": best_gv["name"],
                            "department": dept,
                        })

    # -------------------------------------------------------------------------
    # D. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K20 (NĂM 4 - KỲ 8 - TỐT NGHIỆP CHUẨN)
    # -------------------------------------------------------------------------
    print("\n--- [D] TẠO LỚP HỌC CHO KHÓA K20 (NĂM 4 - KỲ 8 - TỐT NGHIỆP CHUẨN 4 NĂM) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k20 = k20_active_students[k20_active_students["program"] == prog]
        p_total = len(p_k20)
        prefix = cfg["prefix"]

        if p_total <= 0:
            continue

        for c in k20_curriculum:
            course_code = c["course_code"]
            is_politics = course_code.startswith("SP")
            max_cap = POLITICS_CLASS_MAX_CAPACITY if is_politics else REGULAR_CLASS_MAX_CAPACITY
            sizes = balanced_class_sizes(p_total, max_size=max_cap)

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
            print(f"   + [K20 Chuẩn 4 năm] {course_code} ({c_name}): demand={p_total} SV -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d}){cap_note}")

    # -------------------------------------------------------------------------
    # E. PHÂN BỔ LỚP HỌC LẠI CHO CÁC MÔN HK1/LẺ (NHU CẦU >= 20 SV)
    # -------------------------------------------------------------------------
    print("\n--- [E] TẠO LỚP HỌC LẠI CHO CÁC MÔN LẺ/HK1 (NHU CẦU >= 20 SV) ---")
    for retake_code, uids in hk1_retake_demand.items():
        retake_demand_cnt = len(uids)
        sizes = balanced_class_sizes(retake_demand_cnt, max_size=REGULAR_CLASS_MAX_CAPACITY)
        eligible_gvs, dept, c_name = get_all_lecturers_with_fallback(retake_code, all_lecturers)

        for idx, size in enumerate(sizes, start=1):
            group_code = f"L_HL{idx:02d}"
            best_gv = min(eligible_gvs, key=lambda g: (assigned_count[g["user_id"]], g["user_id"]))
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

        print(f"   + [Lớp học lại] {retake_code} ({c_name}): demand={retake_demand_cnt} SV -> {len(sizes)} lớp ({group_code})")

    # 5. Xuất file CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"class_{SEMESTER.lower()}.csv"
    df_classes = pd.DataFrame(classes)
    df_classes.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số lớp học phần đã mở cho {SEMESTER} (Cả K20, K21, K22, K23): {len(df_classes)} lớp")
    return out_file


if __name__ == "__main__":
    generate_class_hk232()

