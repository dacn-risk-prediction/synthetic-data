"""Generate course classes for semester HK251.

In this semester, six distinct cohorts attend classes simultaneously:
1. Cohort K25 in Term 1 (Freshmen - Tân sinh viên):
   - Compulsory courses: MT1003, PH1003, CO1005, CO1023, LA1003, PE1003
   - CLC & Advanced: 100% exempted from English
   - Standard: Placement test exemption (~25%) or class enrollment
   - Older cohort retakers join regular classes for HK1 courses

2. Cohort K24 in Term 3 (Sophomore - Năm 2):
   - Compulsory courses: CO2011, SP1031, CO2003, CO2007, LA1007
   - Course acceleration per additional_course_rules.csv: MT2013 (ADD_MT2013_HK3)
   - Older cohort retakers join regular classes for HK3 courses

3. Cohort K23 in Term 5 (Junior - Năm 3):
   - Compulsory courses: SP1035, CO2001, CO2013 (nếu chưa học vượt), CO3001, CO3005
   - Elective Group C: CO3011, CO3021, CO3029, CO3043, CO3045
   - Older cohort retakers join regular classes for HK5 courses

4. Cohort K22 in Term 7 (Senior - Năm 4):
   - Compulsory courses: SP1039, CO3335, CO4029 (nếu chưa hoàn thành ở HK6)
   - Early graduation route 3.5 years (19 SV K22 early candidates): CO4337 & SP1007

5. Cohort K21 in Term 9 (Năm 5 - Tốt nghiệp trễ hạn 4.5 năm):
   - 726 SV K21 đã tốt nghiệp ở HK241/HK242 không tham gia.
   - 794 SV K21 chưa tốt nghiệp học trả nợ các môn rớt (kể cả CO4337, SP1007) để xét tốt nghiệp 4.5 năm.

6. Cohort K20 in Term 11 (Năm 6 - Tốt nghiệp trễ hạn 5.5 năm):
   - 1,124 SV K20 đã tốt nghiệp tính đến HK242 không tham gia.
   - 376 SV K20 còn lại tiếp tục trả nợ môn để xét tốt nghiệp đợt 5.5 năm.

7. Lớp học lại cho các môn chẵn/HK2 có số lượng nợ >= 15 sinh viên -> Lớp L_HL
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
    get_term7_student_electives,
    select_student_group_c_course,
)

from academic_rules import balanced_class_sizes
from analysis_helpers import (
    get_curriculum_for_cohort_semester,
    get_lecturers_by_course,
    load_lecturers_table,
)

SEMESTER = "HK251"
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


def is_k25_standard_exempt_la1003(student_id: str) -> bool:
    """Determine whether a K25 Standard freshman qualifies for LA1003 exemption."""
    digest = hashlib.sha256(f"{student_id}:la1003_placement".encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    return (seed % 100) < 25


def get_all_passed_courses_up_to_hk242() -> Dict[str, Set[str]]:
    """Retrieve all courses passed by each student across all prior semesters."""
    passed_map: Dict[str, Set[str]] = defaultdict(set)
    for sem in ["hk201", "hk202", "hk211", "hk212", "hk221", "hk222", "hk231", "hk232", "hk241", "hk242"]:
        enr_file = ENROLLMENTS_DIR / f"enrollment_{sem}.csv"
        if enr_file.exists():
            df_enr = pd.read_csv(enr_file, encoding="utf-8-sig", dtype={"student_id": str})
            for _, r in df_enr[df_enr["passed"] == True].iterrows():
                passed_map[str(r["student_id"])].add(str(r["course_id"]))
    return passed_map


def get_k24_acceleration_students(k24_students: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K24 students accelerating MT2013 in HK3 per additional_course_rules.csv."""
    profiles_file = USERS_DIR / "student_profiles.csv"
    if not profiles_file.exists():
        return defaultdict(list)
    df_prof = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")

    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k24_students.iterrows():
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


def get_k23_group_c_distribution(
    k23_students: pd.DataFrame,
    passed_map: Optional[Dict[str, Set[str]]] = None,
    enrolled_map: Optional[Dict[str, Set[str]]] = None,
    retake_demand: Optional[Dict[str, Any]] = None,
    profiles: Optional[Dict[str, Dict[str, Any]]] = None,
    credits_map: Optional[Dict[str, float]] = None,
) -> Dict[Tuple[str, str], List[str]]:
    """Distribute K23 students among Group C elective courses based on specialization and acceleration."""
    from curriculum_rules import get_term5_group_c_distribution
    return get_term5_group_c_distribution(
        cohort_students=k23_students,
        cohort="K23",
        semester="HK251",
        passed_map=passed_map,
        enrolled_map=enrolled_map,
        retake_demand=retake_demand,
        profiles=profiles,
        credits_map=credits_map,
    )


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


def generate_class_hk251() -> Path:
    """Generate all class sections for HK251 and export to class_hk251.csv."""
    print(f"=== KHỞI CHẠY SINH LỚP HỌC PHẦN CHO HỌC KỲ {SEMESTER} (ĐA KHÓA: K20 -> K25) ===")

    # 1. Đọc sinh viên 6 khóa
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    k21_students = df_students[df_students["user_id"].str.startswith("21")].copy()
    k22_students = df_students[df_students["user_id"].str.startswith("22")].copy()
    k23_students = df_students[df_students["user_id"].str.startswith("23")].copy()
    k24_students = df_students[df_students["user_id"].str.startswith("24")].copy()
    k25_students = df_students[df_students["user_id"].str.startswith("25")].copy()
    print(f"1. Tổng SV danh nghĩa: K20: {len(k20_students)} | K21: {len(k21_students)} | K22: {len(k22_students)} | K23: {len(k23_students)} | K24: {len(k24_students)} | K25: {len(k25_students)}")

    # 2. Lịch sử các môn đã đạt
    passed_map = get_all_passed_courses_up_to_hk242()

    profiles_file = USERS_DIR / "student_profiles.csv"
    df_prof = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")

    # Loại trừ K20 đã tốt nghiệp (1,124 SV)
    k20_graduated_uids = set()
    for uid in k20_students["user_id"]:
        if "CO4337" in passed_map[uid] and "SP1007" in passed_map[uid]:
            p = prof_by_id.get(uid, {})
            is_eng = str(p.get("english_pass", "")).lower() == "true"
            if not is_eng:
                try:
                    eng_l = json.loads(p.get("english_eligibility_by_semester", "[]"))
                    is_eng = any(x.get("eligible", False) for x in eng_l if x.get("semester") in ["HK231", "HK232", "HK241", "HK242"])
                except Exception:
                    pass
            ctxh_ok = False
            try:
                ctxh_l = json.loads(p.get("ctxh_days_by_semester", "[]"))
                ctxh_by_s = {x.get("semester"): x.get("cumulative_days", 0) for x in ctxh_l}
                ctxh_ok = ctxh_by_s.get("HK242", 0) >= 15
            except Exception:
                pass
            if is_eng and ctxh_ok:
                k20_graduated_uids.add(uid)

    k20_active_students = k20_students[~k20_students["user_id"].isin(k20_graduated_uids)].copy()
    print(f"2. K20 đã tốt nghiệp: {len(k20_graduated_uids)} SV -> K20 còn lại học HK251: {len(k20_active_students)} SV.")

    # Loại trừ K21 đã tốt nghiệp (726 SV)
    k21_graduated_uids = set()
    for uid in k21_students["user_id"]:
        if "CO4337" in passed_map[uid] and "SP1007" in passed_map[uid]:
            p = prof_by_id.get(uid, {})
            is_eng = str(p.get("english_pass", "")).lower() == "true"
            if not is_eng:
                try:
                    eng_l = json.loads(p.get("english_eligibility_by_semester", "[]"))
                    is_eng = any(x.get("eligible", False) for x in eng_l if x.get("semester") in ["HK241", "HK242"])
                except Exception:
                    pass
            ctxh_ok = False
            try:
                ctxh_l = json.loads(p.get("ctxh_days_by_semester", "[]"))
                ctxh_by_s = {x.get("semester"): x.get("cumulative_days", 0) for x in ctxh_l}
                ctxh_ok = ctxh_by_s.get("HK242", 0) >= 15
            except Exception:
                pass
            if is_eng and ctxh_ok:
                k21_graduated_uids.add(uid)

    k21_active_students = k21_students[~k21_students["user_id"].isin(k21_graduated_uids)].copy()
    print(f"   K21 đã tốt nghiệp: {len(k21_graduated_uids)} SV -> K21 còn lại học HK251 (Kỳ 9 - 4.5 năm): {len(k21_active_students)} SV.")

    # K22 đã hoàn thành CO4029 ở HK242 (nhóm sớm)
    k22_passed_co4029 = {uid for uid in k22_students["user_id"] if "CO4029" in passed_map[uid]}
    print(f"   K22 đã hoàn thành CO4029 sớm: {len(k22_passed_co4029)} SV.")

    # K23 đã học vượt CO2013 ở HK242
    k23_passed_co2013 = {uid for uid in k23_students["user_id"] if "CO2013" in passed_map[uid]}
    print(f"   K23 đã hoàn thành CO2013 sớm: {len(k23_passed_co2013)} SV (miễn học ở HK251).")

    # K24 Đại trà đạt LA1005 ở HK242 -> đủ điều kiện học LA1007
    k24_passed_la1005 = {uid for uid in k24_students["user_id"] if "LA1005" in passed_map[uid]}

    # 3. Nhu cầu học lại
    all_prev_enrollments = pd.concat([
        pd.read_csv(ENROLLMENTS_DIR / f"enrollment_{sem}.csv", encoding="utf-8-sig", dtype={"student_id": str})
        for sem in ["hk201", "hk202", "hk211", "hk212", "hk221", "hk222", "hk231", "hk232", "hk241", "hk242"]
    ])
    retake_demand: Dict[str, Set[str]] = defaultdict(set)
    graduated_all = k20_graduated_uids.union(k21_graduated_uids)
    for _, r in all_prev_enrollments[all_prev_enrollments["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        if sid not in graduated_all and cid not in passed_map[sid]:
            retake_demand[cid].add(sid)

    # 4. CTĐT chuẩn
    k25_curriculum = get_curriculum_for_cohort_semester("K25", 1)["compulsory_courses"]
    k24_curriculum = get_curriculum_for_cohort_semester("K24", 3)["compulsory_courses"]
    k23_curriculum = get_curriculum_for_cohort_semester("K23", 5)["compulsory_courses"]
    k22_curriculum = get_curriculum_for_cohort_semester("K22", 7)["compulsory_courses"]

    print("\n3. Môn học K25 (HK1):", ", ".join(c["course_code"] for c in k25_curriculum))
    print("   Môn học K24 (HK3):", ", ".join(c["course_code"] for c in k24_curriculum))
    print("   Môn học K23 (HK5):", ", ".join(c["course_code"] for c in k23_curriculum))
    print("   Môn học K22 (HK7):", ", ".join(c["course_code"] for c in k22_curriculum))

    enrolled_map: Dict[str, Set[str]] = defaultdict(set)
    for _, r in all_prev_enrollments.iterrows():
        enrolled_map[str(r["student_id"])].add(str(r["course_id"]))

    k24_accel = get_k24_acceleration_students(k24_students)
    k23_group_c = get_k23_group_c_distribution(k23_students, passed_map, enrolled_map, retake_demand=retake_demand)

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
    # A. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K25 (TÂN SINH VIÊN - KỲ 1)
    # -------------------------------------------------------------------------
    print("\n--- [A] TẠO LỚP HỌC CHO KHÓA K25 (TÂN SINH VIÊN - KỲ 1) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k25 = k25_students[k25_students["program"] == prog]
        p_total = len(p_k25)
        prefix = cfg["prefix"]

        if prog in ("high-quality", "advanced"):
            la1003_demand = 0
            print(f"* K25 {cfg['name_vi']} ({prog}) - {p_total} SV (Miễn toàn bộ Anh văn)")
        else:
            exempt_count = sum(is_k25_standard_exempt_la1003(uid) for uid in p_k25["user_id"])
            la1003_demand = p_total - exempt_count
            print(f"* K25 {cfg['name_vi']} ({prog}) - {p_total} SV (Học LA1003: {la1003_demand} SV, Miễn: {exempt_count} SV)")

        for c in k25_curriculum:
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
            print(f"   + [K25] {course_code} ({c_name}): demand={demand}{retake_str} -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d})")

    # -------------------------------------------------------------------------
    # B. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K24 (NĂM 2 - KỲ 3)
    # -------------------------------------------------------------------------
    print("\n--- [B] TẠO LỚP HỌC CHO KHÓA K24 (NĂM 2 - KỲ 3) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k24 = k24_students[k24_students["program"] == prog]
        p_total = len(p_k24)
        prefix = cfg["prefix"]

        if prog in ("high-quality", "advanced"):
            la1007_demand = 0
            print(f"* K24 {cfg['name_vi']} ({prog}) - {p_total} SV (Đã miễn toàn bộ Anh văn)")
        else:
            prog_uids = set(p_k24["user_id"].tolist())
            eligible_la1007 = prog_uids.intersection(k24_passed_la1005)
            la1007_demand = len(eligible_la1007)
            print(f"* K24 {cfg['name_vi']} ({prog}) - {p_total} SV (Đủ điều kiện học LA1007: {la1007_demand} SV)")

        for c in k24_curriculum:
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

            cap_note = " [Giảng đường lớn 120]" if is_politics else ""
            retake_str = f" (+{retake_count} SV khóa trước học ghép)" if retake_count > 0 else ""
            print(f"   + [K24] {course_code} ({c_name}): demand={demand}{retake_str} -> {len(sizes)} lớp ({prefix}{existing_count+1:02d}..{prefix}{existing_count+len(sizes):02d}){cap_note}")

        # Môn học vượt MT2013 cho K24
        accel_uids = k24_accel.get(prog, [])
        if accel_uids:
            mt2013_demand = len(accel_uids)
            sizes = balanced_class_sizes(mt2013_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback("MT2013", all_lecturers)

            existing_count = sum(1 for cl in classes if cl["course_code"] == "MT2013" and cl["program"] == prog)
            for idx, size in enumerate(sizes, start=existing_count + 1):
                group_code = f"{prefix}{idx:02d}"
                best_gv = min(eligible_gvs, key=lambda g: (assigned_count[g["user_id"]], g["user_id"]))
                assigned_count[best_gv["user_id"]] += 1

                classes.append({
                    "class_id": f"{SEMESTER}_MT2013_{group_code}",
                    "course_code": "MT2013",
                    "course_name": c_name,
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": dept,
                })
            print(f"   + [K24 Học vượt] MT2013 ({c_name}): demand={mt2013_demand} -> {len(sizes)} lớp")

    # -------------------------------------------------------------------------
    # C. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K23 (NĂM 3 - KỲ 5)
    # -------------------------------------------------------------------------
    print("\n--- [C] TẠO LỚP HỌC CHO KHÓA K23 (NĂM 3 - KỲ 5) ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k23 = k23_students[k23_students["program"] == prog]
        p_total = len(p_k23)
        prefix = cfg["prefix"]
        prog_uids = set(p_k23["user_id"].tolist())

        co2013_demand = len(prog_uids - k23_passed_co2013)

        for c in k23_curriculum:
            course_code = c["course_code"]
            retakers = [
                uid for uid in retake_demand.get(course_code, set())
                if uid in set(df_students[df_students["program"] == prog]["user_id"])
            ]
            retake_count = len(retakers)

            demand = (co2013_demand if course_code == "CO2013" else p_total) + retake_count

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

        # Tự chọn Group C cho K23 theo chuyên ngành (Hệ Tiên tiến học chung với CLC)
        if prog == "advanced":
            print(f"   + [K23 Tự chọn ngành - Group C]: Ghép học chung lớp với hệ Chất lượng cao (CC)")
        else:
            print(f"   + [K23 Tự chọn ngành - Group C]:")
            if prog == "high-quality":
                all_group_c = sorted(list({c for (p, c) in k23_group_c.keys() if p in ("high-quality", "advanced")}))
                for g_course in all_group_c:
                    g_uids = k23_group_c.get(("high-quality", g_course), []) + k23_group_c.get(("advanced", g_course), [])
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
                all_group_c = sorted(list({c for (p, c) in k23_group_c.keys() if p == prog}))
                for g_course in all_group_c:
                    g_uids = k23_group_c.get((prog, g_course), [])
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
    # D. PHÂN BỔ LỚP HỌC PHẦN CHO KHÓA K22 (NĂM 4 - KỲ 7) & K21/K20 TRẢ NỢ
    # -------------------------------------------------------------------------
    print("\n--- [D] TẠO LỚP HỌC CHO KHÓA K22 (NĂM 4 - KỲ 7) & K21/K20 TRẢ NỢ ---")
    for prog, cfg in PROGRAM_CONFIG.items():
        p_k22 = k22_students[k22_students["program"] == prog]
        p_total = len(p_k22)
        prefix = cfg["prefix"]
        prog_uids = set(p_k22["user_id"].tolist())

        co4029_demand = len(prog_uids - k22_passed_co4029)

        for c in k22_curriculum:
            course_code = c["course_code"]
            retakers = [
                uid for uid in retake_demand.get(course_code, set())
                if uid in set(df_students[df_students["program"] == prog]["user_id"])
            ]
            retake_count = len(retakers)

            demand = (co4029_demand if course_code == "CO4029" else p_total) + retake_count

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

        # Lộ trình tốt nghiệp sớm 3.5 năm K22: CO4337 và SP1007
        early_candidates = [
            uid for uid in prog_uids
            if str(prof_by_id.get(uid, {}).get("early_graduation_candidate", "")).lower() == "true"
            and uid in k22_passed_co4029
        ]
        retakers_co4337 = [
            uid for uid in retake_demand.get("CO4337", set())
            if uid in set(df_students[df_students["program"] == prog]["user_id"])
        ]
        retakers_sp1007 = [
            uid for uid in retake_demand.get("SP1007", set())
            if uid in set(df_students[df_students["program"] == prog]["user_id"])
        ]

        total_co4337_demand = len(early_candidates) + len(retakers_co4337)
        total_sp1007_demand = len(early_candidates) + len(retakers_sp1007)

        if total_co4337_demand > 0:
            sizes = balanced_class_sizes(total_co4337_demand, max_size=REGULAR_CLASS_MAX_CAPACITY)
            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback("CO4337", all_lecturers)
            pref_specs = course_spec_preference.get("CO4337", [])

            existing_count = sum(1 for cl in classes if cl["course_code"] == "CO4337" and cl["program"] == prog)
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
                    "class_id": f"{SEMESTER}_CO4337_{group_code}",
                    "course_code": "CO4337",
                    "course_name": c_name,
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": REGULAR_CLASS_MAX_CAPACITY,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": dept,
                })
            print(f"   + [CO4337 Đồ án tốt nghiệp ({prog})]: {len(early_candidates)} K22 sớm + {len(retakers_co4337)} trả nợ -> {len(sizes)} lớp")

        if total_sp1007_demand > 0:
            sizes = balanced_class_sizes(total_sp1007_demand, max_size=POLITICS_CLASS_MAX_CAPACITY)
            eligible_gvs, dept, c_name = get_all_lecturers_with_fallback("SP1007", all_lecturers)

            existing_count = sum(1 for cl in classes if cl["course_code"] == "SP1007" and cl["program"] == prog)
            for idx, size in enumerate(sizes, start=existing_count + 1):
                group_code = f"{prefix}{idx:02d}"
                best_gv = min(eligible_gvs, key=lambda g: (assigned_count[g["user_id"]], g["user_id"]))
                assigned_count[best_gv["user_id"]] += 1
                classes.append({
                    "class_id": f"{SEMESTER}_SP1007_{group_code}",
                    "course_code": "SP1007",
                    "course_name": c_name,
                    "semester": SEMESTER,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": POLITICS_CLASS_MAX_CAPACITY,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": dept,
                })
            print(f"   + [SP1007 Pháp luật ({prog})]: {len(early_candidates)} K22 sớm + {len(retakers_sp1007)} trả nợ -> {len(sizes)} lớp")

        # Tự chọn ngành Group C (2 môn), Tự do (1 môn), Group B (1 môn) cho K22
        if prog == "advanced":
            print(f"   + [K22 Tự chọn ngành - Group C, Free & B]: Ghép học chung lớp với hệ Chất lượng cao (CC)")
        else:
            if prog == "high-quality":
                k22_adv_uids = set(k22_students[k22_students["program"] == "advanced"]["user_id"])
                combined_k22_uids = prog_uids | k22_adv_uids
            else:
                combined_k22_uids = prog_uids

            regular_k22_uids = list(combined_k22_uids)
            if regular_k22_uids:
                spec_map = get_student_specialization_map()
                c_demand_map: Dict[str, int] = defaultdict(int)
                for uid in regular_k22_uids:
                    spec = spec_map.get(uid, "Khoa học Máy tính")
                    prev_passed = passed_map.get(uid, set())
                    prev_enrolled = enrolled_map.get(uid, set())
                    elecs = get_term7_student_electives(uid, "K22", spec, prev_passed, prev_enrolled)
                    for ec in elecs:
                        c_demand_map[ec] += 1

                suffix_note = " (CLC+TT)" if prog == "high-quality" else ""
                print(f"   + [K22 Tự chọn ngành - Group C, Free & B ({len(c_demand_map)} môn)]{suffix_note} ({len(regular_k22_uids)} SV):")
                create_elective_classes_for_program(
                    prog=prog,
                    prefix=prefix,
                    course_demand_map=c_demand_map,
                    classes=classes,
                    all_lecturers=all_lecturers,
                    assigned_count=assigned_count,
                    semester=SEMESTER,
                    course_spec_preference=course_spec_preference,
                    get_all_lecturers_with_fallback=get_all_lecturers_with_fallback,
                )

    # -------------------------------------------------------------------------
    # E. PHÂN BỔ LỚP HỌC LẠI CHO CÁC MÔN CHẴN/HK2 (NHU CẦU >= 15 SV)
    # -------------------------------------------------------------------------
    print("\n--- [E] TẠO LỚP HỌC LẠI CHO CÁC MÔN CHẴN/HK2 (NHU CẦU >= 15 SV) ---")
    even_courses_retake = [
        "CO1027", "PH1007", "CO2017", "CO1007", "MT1007", "MT1005",
        "CO2039", "SP1033", "CO3093", "CH1003", "SP1037", "MI1003",
    ]
    for retake_code in even_courses_retake:
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
    generate_class_hk251()

