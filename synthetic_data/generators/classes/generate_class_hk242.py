"""Generate course classes for semester HK242.

In this semester, five distinct cohorts attend classes simultaneously:
1. Cohort K24 in Term 2 (Freshmen - Học kỳ 2):
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

2. Cohort K23 in Term 4 (Sophomore - Học kỳ 4):
   - Compulsory courses:
     * SP1033: Kinh tế Chính trị Mác - Lênin (2 TC, Giảng đường lớn max capacity 120)
     * CO2039: Lập trình Nâng cao (3 TC)
     * CO2017: Hệ điều hành (3 TC)
     * MT2013: Xác suất và Thống kê (4 TC) - SV K23 chưa học vượt ở HK241
     * LA1009: Anh văn 4 (2 TC - Standard only, SV đã đạt LA1007 ở HK241)
   - Tự chọn Khối Quản lý Kỹ thuật (Group D - 3 TC):
     * IM1013, IM1023, IM1025, IM1027, IM3001
   - Môn học vượt theo additional_course_rules.csv:
     * CO3093: Mạng máy tính (3 TC per ADD_CO3093_HK4)
     * CO2013: Hệ cơ sở Dữ liệu (4 TC per ADD_CO2013_HK4)
   - Sinh viên khóa trước nợ môn HK4 học ghép vào các lớp này.

3. Cohort K22 in Term 6 (Junior - Học kỳ 6):
   - Compulsory courses:
     * CH1003: Hóa đại cương (3 TC) - SV K22 chưa học vượt ở HK2/HK4
     * SP1037: Tư tưởng Hồ Chí Minh (2 TC, Giảng đường lớn max capacity 120)
     * CO3093: Mạng máy tính (3 TC) - SV K22 chưa học vượt ở HK4/HK5
   - Lộ trình tốt nghiệp sớm (18 SV K22 tốt nghiệp sớm 3.5 năm):
     * CO3061: Nhập môn Trí tuệ Nhân tạo (3 TC per EARLY_CO3061_HK6)
     * CO4029: Đồ án Chuyên ngành (2 TC per EARLY_CO4029_HK6)
   - Tự chọn ngành cho các sinh viên K22 còn lại:
     * Đăng ký 2 môn thuộc Group C: CO3061, CO3029, CO3043, CO3045, CO3021, CO3011

4. Cohort K21 in Term 8 (Senior - Học kỳ 8 - Tốt nghiệp chuẩn 4 năm):
   - 18 sinh viên K21 tốt nghiệp sớm 3.5 năm ở HK241 ĐÃ TỐT NGHIỆP (không học HK242).
   - 1,502 sinh viên K21 còn lại hoàn tất tốt nghiệp chuẩn 4 năm:
     * CO4337: Đồ án Tốt nghiệp (4 TC)
     * SP1007: Pháp luật Việt Nam Đại cương (2 TC, Giảng đường lớn max capacity 120)

5. Cohort K20 in Term 10 (Năm 5 - Tốt nghiệp trễ hạn đợt 5.0 năm):
   - 940 SV K20 đã tốt nghiệp tính đến HK241 không tham gia.
   - 560 SV K20 chưa tốt nghiệp học trả nợ các môn còn thiếu (ghép lớp hoặc lớp học lại).

6. Lớp học lại cho các môn HK1/lẻ có số lượng rớt >= 15 sinh viên:
   - SP1035, CO3001, CO1005, CO2011, SP1031, CO2001, CO3005, MT1003, CO1023, PH1003, CO2003, SP1039, CO2007, LA1003, CO3335, CO4029 -> Lớp L_HL
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
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

from curriculum_rules import (
    create_elective_classes_for_program,
    get_student_specialization_map,
    get_term8_student_electives,
    select_student_group_a_course,
    select_student_group_c_course,
)

from academic_rules import balanced_class_sizes
from analysis_helpers import (
    get_curriculum_for_cohort_semester,
    get_lecturers_by_course,
    load_lecturers_table,
)

SEMESTER = "HK242"
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


def get_all_passed_courses_up_to_hk241() -> Dict[str, Set[str]]:
    """Retrieve all courses passed by each student across all prior semesters."""
    passed_map: Dict[str, Set[str]] = defaultdict(set)
    for sem in ["hk201", "hk202", "hk211", "hk212", "hk221", "hk222", "hk231", "hk232", "hk241"]:
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


def get_k24_acceleration_students(k24_students: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K24 students eligible to accelerate CH1003 (HK2)."""
    profiles_file = USERS_DIR / "student_profiles.csv"
    if not profiles_file.exists():
        return defaultdict(list)
    df_prof = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")

    top_code, _ = get_top_acceleration_course_for_term("HK2")
    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k24_students.iterrows():
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


def get_k23_acceleration_students(k23_students: pd.DataFrame, k23_passed_mt2013: Set[str]) -> Dict[str, List[str]]:
    """Identify K23 students eligible to accelerate CO3093 and CO2013 in HK4."""
    profiles_file = USERS_DIR / "student_profiles.csv"
    if not profiles_file.exists():
        return defaultdict(list)
    df_prof = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")

    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k23_students.iterrows():
        uid = str(row["user_id"])
        prog = row["program"]
        p = prof_by_id.get(uid, {})
        is_early_candidate = str(p.get("early_graduation_candidate", "")).lower() == "true"

        if uid in k23_passed_mt2013 or is_early_candidate:
            accelerating_by_prog[prog].append(uid)

    return accelerating_by_prog


def get_k23_group_d_distribution(k23_students: pd.DataFrame) -> Dict[Tuple[str, str], List[str]]:
    """Distribute K23 students among Group D elective courses."""
    choice_map: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, row in k23_students.iterrows():
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


def generate_class_hk242() -> Path:
    """Generate all class sections for HK242 and export to class_hk242.csv."""
    print(f"=== KHỞI CHẠY SINH LỚP HỌC PHẦN CHO HỌC KỲ {SEMESTER} (ĐA KHÓA: K20, K21, K22, K23, K24) ===")

    # 1. Đọc sinh viên 5 khóa
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    k21_students = df_students[df_students["user_id"].str.startswith("21")].copy()
    k22_students = df_students[df_students["user_id"].str.startswith("22")].copy()
    k23_students = df_students[df_students["user_id"].str.startswith("23")].copy()
    k24_students = df_students[df_students["user_id"].str.startswith("24")].copy()
    print(f"1. Tổng SV danh nghĩa: K20: {len(k20_students)} | K21: {len(k21_students)} | K22: {len(k22_students)} | K23: {len(k23_students)} | K24: {len(k24_students)}")

    # 2. Lịch sử các môn đã đạt
    passed_map = get_all_passed_courses_up_to_hk241()

    # Đọc profiles
    profiles_file = USERS_DIR / "student_profiles.csv"
    df_prof = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")

    # K21 đã tốt nghiệp sớm sau HK241 (đã hoàn thành CO4337 và SP1007 ở HK241)
    k21_graduated_uids = {uid for uid in k21_students["user_id"] if "CO4337" in passed_map[uid] and "SP1007" in passed_map[uid]}
    k21_active_students = k21_students[~k21_students["user_id"].isin(k21_graduated_uids)].copy()
    print(f"2. K21 đã tốt nghiệp sớm sau HK241: {len(k21_graduated_uids)} SV -> K21 còn lại học HK242 (Học kỳ 8 - Chuẩn 4 năm): {len(k21_active_students)} SV.")

    # K20 đã tốt nghiệp tính đến HK241 (940 SV)
    k20_graduated_uids = set()
    for uid in k20_students["user_id"]:
        if "CO4337" in passed_map[uid] and "SP1007" in passed_map[uid]:
            p = prof_by_id.get(uid, {})
            is_eng = str(p.get("english_pass", "")).lower() == "true"
            if not is_eng:
                try:
                    eng_l = json.loads(p.get("english_eligibility_by_semester", "[]"))
                    is_eng = any(x.get("eligible", False) for x in eng_l if x.get("semester") in ["HK231", "HK232", "HK241"])
                except Exception:
                    pass
            ctxh_ok = False
            try:
                ctxh_l = json.loads(p.get("ctxh_days_by_semester", "[]"))
                ctxh_by_s = {x.get("semester"): x.get("cumulative_days", 0) for x in ctxh_l}
                ctxh_ok = ctxh_by_s.get("HK241", 0) >= 15
            except Exception:
                pass
            if is_eng and ctxh_ok:
                k20_graduated_uids.add(uid)

    k20_active_students = k20_students[~k20_students["user_id"].isin(k20_graduated_uids)].copy()
    print(f"   K20 đã tốt nghiệp: {len(k20_graduated_uids)} SV -> K20 còn lại học HK242 (Kỳ 10 - 5.0 năm): {len(k20_active_students)} SV.")

    # K22 đã học vượt CH1003 hoặc CO3093 ở các kỳ trước
    k22_passed_ch1003 = {uid for uid in k22_students["user_id"] if "CH1003" in passed_map[uid]}
    k22_passed_co3093 = {uid for uid in k22_students["user_id"] if "CO3093" in passed_map[uid]}
    print(f"   K22 đã hoàn thành CH1003 sớm: {len(k22_passed_ch1003)} SV | CO3093 sớm: {len(k22_passed_co3093)} SV.")

    # K23 đã học vượt MT2013 ở HK241
    k23_passed_mt2013 = {uid for uid in k23_students["user_id"] if "MT2013" in passed_map[uid]}
    print(f"   K23 đã hoàn thành MT2013 sớm: {len(k23_passed_mt2013)} SV (miễn học ở HK242).")

    # K23 Đại trà đạt LA1007 ở HK241 -> đủ điều kiện học LA1009
    k23_passed_la1007 = {uid for uid in k23_students["user_id"] if "LA1007" in passed_map[uid]}

    # K24 Đại trà đạt/miễn LA1003 ở HK241 -> đủ điều kiện học LA1005
    k24_passed_la1003 = {uid for uid in k24_students["user_id"] if "LA1003" in passed_map[uid]}

    # 3. Nhu cầu học lại
    all_prev_enrollments = pd.concat([
        pd.read_csv(ENROLLMENTS_DIR / f"enrollment_{sem}.csv", encoding="utf-8-sig", dtype={"student_id": str})
        for sem in ["hk201", "hk202", "hk211", "hk212", "hk221", "hk222", "hk231", "hk232", "hk241"]
    ])
    retake_demand: Dict[str, Set[str]] = defaultdict(set)
    for _, r in all_prev_enrollments[all_prev_enrollments["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        if sid not in k20_graduated_uids and sid not in k21_graduated_uids and cid not in passed_map[sid]:
            retake_demand[cid].add(sid)

    # 4. CTĐT chuẩn
    k24_curriculum = get_curriculum_for_cohort_semester("K24", 2)["compulsory_courses"]
    k23_curriculum = get_curriculum_for_cohort_semester("K23", 4)["compulsory_courses"]
    k22_curriculum = get_curriculum_for_cohort_semester("K22", 6)["compulsory_courses"]
    k21_curriculum = get_curriculum_for_cohort_semester("K21", 8)["compulsory_courses"]

    print("\n3. Môn học K24 (HK2):", ", ".join(c["course_code"] for c in k24_curriculum))
    print("   Môn học K23 (HK4):", ", ".join(c["course_code"] for c in k23_curriculum))
    print("   Môn học K22 (HK6):", ", ".join(c["course_code"] for c in k22_curriculum))
    print("   Môn học K21 (HK8):", ", ".join(c["course_code"] for c in k21_curriculum))

    k24_accel = get_k24_acceleration_students(k24_students)
    k23_accel = get_k23_acceleration_students(k23_students, k23_passed_mt2013)
    k23_group_d = get_k23_group_d_distribution(k23_students)

    all_lecturers = load_lecturers_table()
    assigned_count: Dict[str, int] = defaultdict(int)
    classes: List[Dict[str, Any]] = []

    course_spec_preference: Dict[str, List[str]] = {
        "CO1007": ["Khoa học Máy tính"],
        "CO1027": ["Khoa học Máy tính", "Công nghệ Phần mềm"],
        "CO2039": ["Công nghệ Phần mềm"],
        "CO2017": ["Hệ thống và Mạng máy tính", "Kỹ thuật Máy tính"],
        "CO3093": ["Hệ thống và Mạng máy tính"],
        "CO3061": ["Khoa học Dữ liệu", "Khoa học Máy tính"],
        "CO4029": ["Công nghệ Phần mềm", "Khoa học Máy tính"],
        "CO4337": ["Công nghệ Phần mềm", "Khoa học Máy tính", "Hệ thống và Mạng máy tính"],
    }

    # -------------------------------------------------------------------------
    # A. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K24 (HỌC KỲ 2)
    # -------------------------------------------------------------------------
    print("\n--- [A] TẠO LỚP HỌC CHO KHÓA K24 (HỌC KỲ 2) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k24 = k24_students[k24_students["program"] == prog]
        p_total = len(p_k24)
        prefix = cfg["prefix"]

        if prog in ("high-quality", "advanced"):
            la1005_demand = 0
            print(f"* K24 {cfg['name_vi']} ({prog}) - {p_total} SV (Đã miễn toàn bộ Anh văn)")
        else:
            prog_uids = set(p_k24["user_id"].tolist())
            eligible_la1005 = prog_uids.intersection(k24_passed_la1003)
            la1005_demand = len(eligible_la1005)
            print(f"* K24 {cfg['name_vi']} ({prog}) - {p_total} SV (Đủ điều kiện học LA1005: {la1005_demand} SV)")

        for c in k24_curriculum:
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

            retake_str = f" (+{retake_count} SV khóa trước học ghép)" if retake_count > 0 else ""
            print(f"   + [K24] {course_code} ({c_name}): demand={demand}{retake_str} -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d})")

        # Môn học vượt CH1003 cho K24
        accel_uids = k24_accel.get(prog, [])
        if accel_uids:
            ch1003_demand = len(accel_uids)
            sizes = balanced_class_sizes(ch1003_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback("CH1003", all_lecturers)

            existing_count = sum(1 for cl in classes if cl["course_code"] == "CH1003" and cl["program"] == prog)
            for idx, size in enumerate(sizes, start=existing_count + 1):
                group_code = f"{prefix}{idx:02d}"
                best_gv = min(eligible_gvs, key=lambda g: (assigned_count[g["user_id"]], g["user_id"]))
                assigned_count[best_gv["user_id"]] += 1

                classes.append({
                    "class_id": f"{SEMESTER}_CH1003_{group_code}",
                    "course_code": "CH1003",
                    "course_name": c_name,
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": dept,
                })
            print(f"   + [K24 Học vượt] CH1003 ({c_name}): demand={ch1003_demand} -> {len(sizes)} lớp")

    # -------------------------------------------------------------------------
    # B. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K23 (HỌC KỲ 4)
    # -------------------------------------------------------------------------
    print("\n--- [B] TẠO LỚP HỌC CHO KHÓA K23 (HỌC KỲ 4) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k23 = k23_students[k23_students["program"] == prog]
        p_total = len(p_k23)
        prefix = cfg["prefix"]
        prog_uids = set(p_k23["user_id"].tolist())

        if prog in ("high-quality", "advanced"):
            la1009_demand = 0
            print(f"* K23 {cfg['name_vi']} ({prog}) - {p_total} SV (Đã miễn toàn bộ Anh văn)")
        else:
            eligible_la1009 = prog_uids.intersection(k23_passed_la1007)
            la1009_demand = len(eligible_la1009)
            print(f"* K23 {cfg['name_vi']} ({prog}) - {p_total} SV (Đủ điều kiện học LA1009: {la1009_demand} SV)")

        mt2013_demand = len(prog_uids - k23_passed_mt2013)

        for c in k23_curriculum:
            course_code = c["course_code"]
            retakers = [
                uid for uid in retake_demand.get(course_code, set())
                if uid in set(df_students[df_students["program"] == prog]["user_id"])
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

            cap_note = " [Giảng đường lớn 120]" if is_politics else ""
            retake_str = f" (+{retake_count} SV khóa trước học ghép)" if retake_count > 0 else ""
            print(f"   + [K23] {course_code} ({c_name}): demand={demand}{retake_str} -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d}){cap_note}")

        # Tự chọn Quản lý Kỹ thuật (Group D) cho K23
        print(f"   + [K23 Tự chọn Quản lý Kỹ thuật - Group D]:")
        for g_course in GROUP_D_COURSES:
            g_uids = k23_group_d.get((prog, g_course), [])
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

        # Môn học vượt cho K23: CO3093 và CO2013
        accel_uids = k23_accel.get(prog, [])
        if accel_uids:
            for accel_code in ["CO3093", "CO2013"]:
                accel_demand = len(accel_uids)
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
                        "course_name": c_name,
                        "semester": SEMESTER,
                        "class_group": group_code,
                        "program": prog,
                        "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                        "lecturer_id": best_gv["user_id"],
                        "lecturer_name": best_gv["name"],
                        "department": dept,
                    })
                print(f"   + [K23 Học vượt] {accel_code} ({c_name}): demand={accel_demand} -> {len(sizes)} lớp")

    # -------------------------------------------------------------------------
    # C. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K22 (HỌC KỲ 6)
    # -------------------------------------------------------------------------
    print("\n--- [C] TẠO LỚP HỌC CHO KHÓA K22 (HỌC KỲ 6) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k22 = k22_students[k22_students["program"] == prog]
        p_total = len(p_k22)
        prefix = cfg["prefix"]
        prog_uids = set(p_k22["user_id"].tolist())

        ch1003_demand = len(prog_uids - k22_passed_ch1003)
        co3093_demand = len(prog_uids - k22_passed_co3093)

        for c in k22_curriculum:
            course_code = c["course_code"]
            retakers = [
                uid for uid in retake_demand.get(course_code, set())
                if uid in set(df_students[df_students["program"] == prog]["user_id"])
            ]
            retake_count = len(retakers)

            if course_code == "CH1003":
                demand = ch1003_demand + retake_count
            elif course_code == "CO3093":
                demand = co3093_demand + retake_count
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

            cap_note = " [Giảng đường lớn 120]" if is_politics else ""
            retake_str = f" (+{retake_count} SV khóa trước học ghép)" if retake_count > 0 else ""
            print(f"   + [K22] {course_code} ({c_name}): demand={demand}{retake_str} -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d}){cap_note}")

        # Lộ trình tốt nghiệp sớm 3.5 năm & Tự chọn Group C cho K22 (Hệ Tiên tiến học chung với CLC)
        if prog == "advanced":
            print(f"   + [K22 Lộ trình sớm]: Ghép học chung lớp với hệ Chất lượng cao (CC)")
            print(f"   + [K22 Tự chọn ngành - Group C]: Ghép học chung lớp với hệ Chất lượng cao (CC)")
        else:
            if prog == "high-quality":
                k22_adv_uids = set(k22_students[k22_students["program"] == "advanced"]["user_id"])
                combined_prog_uids = prog_uids | k22_adv_uids
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
                            "course_name": f"{c_name} (Lộ trình sớm)",
                            "semester": SEMESTER,
                            "class_group": group_code,
                            "program": prog,
                            "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                            "lecturer_id": best_gv["user_id"],
                            "lecturer_name": best_gv["name"],
                            "department": dept,
                        })
                    suffix_note = " (CLC+TT)" if prog == "high-quality" else ""
                    print(f"   + [K22 Lộ trình sớm] {early_code} ({c_name}): {len(early_candidates)} SV{suffix_note} -> {len(sizes)} lớp")

            # Tự chọn ngành Group C cho sinh viên K22 thông thường (chọn 2 môn theo chuyên ngành)
            regular_k22_uids = [uid for uid in combined_prog_uids if uid not in set(early_candidates)]
            if regular_k22_uids:
                spec_map = get_student_specialization_map()
                c_demand_map: Dict[str, int] = defaultdict(int)
                for uid in regular_k22_uids:
                    spec = spec_map.get(uid, "Khoa học Máy tính")
                    prev_passed = passed_map.get(uid, set())
                    c1 = select_student_group_c_course(uid, "K22", spec, seed_salt="k22_group_c_1_hk242", exclude_courses=prev_passed)
                    c2 = select_student_group_c_course(uid, "K22", spec, seed_salt="k22_group_c_2_hk242", exclude_courses=prev_passed | {c1})
                    c_ga = select_student_group_a_course(spec)
                    c_demand_map[c1] += 1
                    c_demand_map[c2] += 1
                    c_demand_map[c_ga] += 1

                suffix_note = " (CLC+TT)" if prog == "high-quality" else ""
                print(f"   + [K22 Tự chọn ngành - Group C ({len(c_demand_map)} môn có SV đăng ký)]{suffix_note} ({len(regular_k22_uids)} SV):")
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
                    print(f"     * {c_code} ({c_name}): demand={c_demand}{suffix_note} -> {len(sizes)} lớp")

    # -------------------------------------------------------------------------
    # D. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K21 (HỌC KỲ 8 - TỐT NGHIỆP CHUẨN 4 NĂM) & K20 TRẢ NỢ
    # -------------------------------------------------------------------------
    print("\n--- [D] TẠO LỚP HỌC CHO KHÓA K21 (HỌC KỲ 8 - TỐT NGHIỆP CHUẨN 4 NĂM) & K20 TRẢ NỢ ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k21 = k21_active_students[k21_active_students["program"] == prog]
        p_total = len(p_k21)
        prefix = cfg["prefix"]

        # K20 trả nợ CO4337 hoặc SP1007
        k20_prog_retakers_co4337 = [
            uid for uid in retake_demand.get("CO4337", set())
            if uid in set(k20_active_students[k20_active_students["program"] == prog]["user_id"])
        ]
        k20_prog_retakers_sp1007 = [
            uid for uid in retake_demand.get("SP1007", set())
            if uid in set(k20_active_students[k20_active_students["program"] == prog]["user_id"])
        ]

        for c in k21_curriculum:
            course_code = c["course_code"]
            retakers_cnt = len(k20_prog_retakers_co4337) if course_code == "CO4337" else len(k20_prog_retakers_sp1007)
            demand = p_total + retakers_cnt

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
            retake_str = f" (+{retakers_cnt} SV K20 trả nợ)" if retakers_cnt > 0 else ""
            print(f"   + [K21 Chuẩn 4 năm] {course_code} ({c_name}): demand={demand}{retake_str} -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d}){cap_note}")

        # Tự chọn tự do (2 môn) cho K21
        if prog == "advanced":
            print(f"   + [K21 Tự chọn tự do]: Ghép học chung lớp với hệ Chất lượng cao (CC)")
        else:
            if prog == "high-quality":
                k21_adv_uids = set(k21_active_students[k21_active_students["program"] == "advanced"]["user_id"])
                combined_k21_uids = set(p_k21["user_id"]) | k21_adv_uids
            else:
                combined_k21_uids = set(p_k21["user_id"])

            if combined_k21_uids:
                c_demand_map: Dict[str, int] = defaultdict(int)
                for uid in combined_k21_uids:
                    prev_passed = passed_map.get(uid, set())
                    elecs = get_term8_student_electives(uid, "K21", prev_passed)
                    for ec in elecs:
                        c_demand_map[ec] += 1

                suffix_note = " (CLC+TT)" if prog == "high-quality" else ""
                print(f"   + [K21 Tự chọn tự do ({len(c_demand_map)} môn)]{suffix_note} ({len(combined_k21_uids)} SV):")
                create_elective_classes_for_program(
                    prog=prog,
                    prefix=prefix,
                    course_demand_map=c_demand_map,
                    classes=classes,
                    all_lecturers=all_lecturers,
                    assigned_count=assigned_count,
                    semester=SEMESTER,
                    get_all_lecturers_with_fallback=get_all_lecturers_with_fallback,
                    course_spec_preference=course_spec_preference,
                    max_cap=REGULAR_CLASS_MAX_CAPACITY,
                )

    # -------------------------------------------------------------------------
    # E. PHÂN BỔ LỚP HỌC LẠI CHO CÁC MÔN LẺ/HK1 (NHU CẦU >= 15 SV)
    # -------------------------------------------------------------------------
    print("\n--- [E] TẠO LỚP HỌC LẠI CHO CÁC MÔN LẺ/HK1 (NHU CẦU >= 15 SV) ---")
    odd_courses_retake = [
        "SP1035", "CO3001", "CO1005", "CO2011", "SP1031", "CO2001", "CO3005",
        "MT1003", "CO1023", "PH1003", "CO2003", "SP1039", "CO2007", "LA1003",
        "CO3335", "CO4029",
    ]
    for retake_code in odd_courses_retake:
        uids = retake_demand.get(retake_code, set())
        if len(uids) < 15:
            continue
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
    print(f"Tổng số lớp học phần mở trong {SEMESTER}: {len(df_classes)} lớp.")

    return out_file


if __name__ == "__main__":
    generate_class_hk242()

