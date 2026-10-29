"""Generate enrollment records and course grades for semester HK242.

In this semester, five distinct cohorts attend classes simultaneously:
1. Cohort K24 in Term 2 (Freshmen - Học kỳ 2):
   - Compulsory courses: CO1007, MT1005, MT1007, PH1007, LA1005, CO1027, MI1003
   - Accelerated: CH1003 per ADD_CH1003_HK2

2. Cohort K23 in Term 4 (Sophomore - Học kỳ 4):
   - Compulsory courses: MT2013, SP1033, LA1009, CO2039, CO2017
   - Elective Group D: IM1013, IM1023, IM1025, IM1027, IM3001
   - Accelerated: CO3093 & CO2013 per ADD_CO3093_HK4 & ADD_CO2013_HK4

3. Cohort K22 in Term 6 (Junior - Học kỳ 6):
   - Compulsory courses: CH1003, SP1037, CO3093
   - Early Graduation route (18 SV K22): CO3061 & CO4029 per EARLY_CO3061_HK6 & EARLY_CO4029_HK6
   - Elective Group C for remaining K22 students

4. Cohort K21 in Term 8 (Senior - Học kỳ 8 - Tốt nghiệp chuẩn 4 năm):
   - 18 SV K21 tốt nghiệp sớm ở HK241 không tham gia.
   - 1,502 SV K21 còn lại hoàn tất tốt nghiệp chuẩn: CO4337 (Đồ án tốt nghiệp) & SP1007 (Pháp luật đại cương)

5. Cohort K20 in Term 10 (Năm 5 - Tốt nghiệp trễ hạn đợt 5.0 năm):
   - 940 SV K20 đã tốt nghiệp tính đến HK241 không tham gia.
   - 560 SV K20 chưa tốt nghiệp học trả nợ môn rớt để xét tốt nghiệp đợt 5.0 năm.

6. Lớp học lại môn lẻ/HK1 (L_HL):
   - Gán sinh viên nợ các môn lẻ vào các lớp học lại L_HL
   - Kiểm tra nghiêm ngặt điều kiện tiên quyết (TQ) và giới hạn tối đa 22 tín chỉ/học kỳ.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Set, Tuple

import numpy as np
import pandas as pd

# Path configuration
ROOT_DIR = Path(__file__).resolve().parents[2]
ACADEMICS_DIR = ROOT_DIR / "generated" / "academics"
USERS_DIR = ROOT_DIR / "generated" / "users"
CLASSES_DIR = ROOT_DIR / "generated" / "classes"
RULES_DIR = ROOT_DIR / "rules"
OUTPUT_DIR = ROOT_DIR / "generated" / "enrollments"

if str(RULES_DIR) not in sys.path:
    sys.path.insert(0, str(RULES_DIR))

ENROLLMENTS_DIR = Path(__file__).resolve().parent
if str(ENROLLMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(ENROLLMENTS_DIR))
from retake_improvement_helper import generate_grade_improvement_retakes

from curriculum_rules import (
    enroll_students_in_electives,
    get_student_specialization_map,
    get_term8_student_electives,
    select_student_group_a_course,
    select_student_group_c_course,
)

from academic_rules import (
    GENERATOR_CONFIG,
    balanced_class_sizes,
    score_course_components,
)

ANALYSIS_DIR = ROOT_DIR / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from analysis_helpers import get_curriculum_for_cohort_semester

SEMESTER = "HK242"
MAX_SEMESTER_CREDITS = 22.0
GROUP_D_COURSES = ["IM1013", "IM1023", "IM1025", "IM1027", "IM3001"]
GROUP_C_COURSES = ["CO3061", "CO3029", "CO3043", "CO3045", "CO3021", "CO3011"]


def get_top_acceleration_course_for_term(term_code: str = "HK2") -> Tuple[str, str]:
    """Retrieve top-priority acceleration course for the term."""
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


def get_k24_acceleration_students(k24_students: pd.DataFrame, df_prof: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K24 students eligible to accelerate CH1003 (HK2)."""
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


def get_k23_acceleration_students(k23_students: pd.DataFrame, df_prof: pd.DataFrame, k23_passed_mt2013: Set[str]) -> Dict[str, List[str]]:
    """Identify K23 students eligible to accelerate CO3093 and CO2013 in HK4."""
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


def generate_enrollment_hk242() -> Path:
    """Execute enrollment generation for semester HK242 and export to enrollment_hk242.csv."""
    print(f"=== KHỞI CHẠY SINH DỮ LIỆU ĐĂNG KÝ HỌC PHẦN CHO {SEMESTER} (ĐA KHÓA: K20, K21, K22, K23, K24) ===")

    # 1. Đọc sinh viên 5 khóa
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    k21_students = df_students[df_students["user_id"].str.startswith("21")].copy()
    k22_students = df_students[df_students["user_id"].str.startswith("22")].copy()
    k23_students = df_students[df_students["user_id"].str.startswith("23")].copy()
    k24_students = df_students[df_students["user_id"].str.startswith("24")].copy()
    print(f"1. Tổng SV: K20: {len(k20_students)} | K21: {len(k21_students)} | K22: {len(k22_students)} | K23: {len(k23_students)} | K24: {len(k24_students)}")

    # 2. Đọc danh sách lớp học phần HK242
    classes_file = CLASSES_DIR / "class_hk242.csv"
    if not classes_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file lớp: {classes_file}. Hãy chạy generate_class_hk242.py trước!")
    df_classes = pd.read_csv(classes_file, encoding="utf-8-sig")
    print(f"2. Tổng số lớp học phần đã mở cho HK242: {len(df_classes)} lớp.")

    # 3. Đọc lịch sử học tập các kỳ trước: HK201 -> HK241
    prior_sems = ["hk201", "hk202", "hk211", "hk212", "hk221", "hk222", "hk231", "hk232", "hk241"]
    prev_dfs = [
        pd.read_csv(OUTPUT_DIR / f"enrollment_{s}.csv", encoding="utf-8-sig", dtype={"student_id": str})
        for s in prior_sems
    ]
    total_past_enrollments = sum(len(df) for df in prev_dfs)

    # Lịch sử môn đạt của từng sinh viên
    history_passed: Dict[str, Dict[str, float]] = defaultdict(dict)
    all_attempted: Dict[str, Set[str]] = defaultdict(set)
    for df_prev in prev_dfs:
        for _, r in df_prev.iterrows():
            sid = str(r["student_id"])
            cid = str(r["course_id"])
            all_attempted[sid].add(cid)
            score = r["final_score"]
            gpa4 = r["gpa_4"]
            if r["passed"] == True or str(r.get("status", "")).lower() in ["pass", "exempted"]:
                history_passed[sid][cid] = float(gpa4) if (pd.notna(gpa4) and not (pd.notna(score) and float(score) == 12.0)) else 0.0

    # Đọc profiles
    profiles_file = USERS_DIR / "student_profiles.csv"
    df_profiles = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    student_profiles: Dict[str, Dict[str, Any]] = df_profiles.set_index("student_id").to_dict(orient="index")

    # K21: Đã tốt nghiệp sớm ở HK241 (18 SV)
    k21_graduated_uids = {uid for uid in k21_students["user_id"] if "CO4337" in history_passed[uid] and "SP1007" in history_passed[uid]}
    k21_active_students = k21_students[~k21_students["user_id"].isin(k21_graduated_uids)].copy()
    print(f"3. K21 đã tốt nghiệp sớm sau HK241: {len(k21_graduated_uids)} SV -> K21 còn lại học HK242 (Chuẩn 4 năm): {len(k21_active_students)} SV.")

    # K20: Loại trừ SV đã tốt nghiệp tính đến HK241 (940 SV)
    k20_graduated_uids = set()
    for uid in k20_students["user_id"]:
        if "CO4337" in history_passed[uid] and "SP1007" in history_passed[uid]:
            p = student_profiles.get(uid, {})
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
    print(f"   K20 đã tốt nghiệp: {len(k20_graduated_uids)} SV -> K20 còn lại học HK242: {len(k20_active_students)} SV.")

    # K22 đã học vượt CH1003 hoặc CO3093
    k22_passed_ch1003 = {uid for uid in k22_students["user_id"] if "CH1003" in history_passed[uid]}
    k22_passed_co3093 = {uid for uid in k22_students["user_id"] if "CO3093" in history_passed[uid]}

    # K23 đã học vượt MT2013 ở HK241
    k23_passed_mt2013 = {uid for uid in k23_students["user_id"] if "MT2013" in history_passed[uid]}

    # K23 Đại trà đạt LA1007 ở HK241 -> đủ điều kiện học LA1009
    k23_passed_la1007 = {uid for uid in k23_students["user_id"] if "LA1007" in history_passed[uid]}

    # K24 Đại trà đạt/miễn LA1003 ở HK241 -> đủ điều kiện học LA1005
    k24_passed_la1003 = {uid for uid in k24_students["user_id"] if "LA1003" in history_passed[uid]}

    # Nhu cầu học lại từ các kỳ trước (chỉ tính SV chưa tốt nghiệp)
    all_prev_enrollments = pd.concat(prev_dfs)
    retake_demand: Dict[str, List[str]] = defaultdict(list)
    for _, r in all_prev_enrollments[all_prev_enrollments["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        if sid not in k20_graduated_uids and sid not in k21_graduated_uids and cid not in history_passed[sid] and sid not in retake_demand[cid]:
            retake_demand[cid].append(sid)

    # 4. Đọc đánh giá và tín chỉ
    assessment_file = ACADEMICS_DIR / "assessment.csv"
    df_assessment = pd.read_csv(assessment_file, encoding="utf-8-sig")
    component_columns = ["quiz", "lab", "btl", "giua_ky", "cuoi_ky"]
    course_assessments: Dict[str, List[Tuple[str, float]]] = {}
    for _, row in df_assessment.iterrows():
        c_code = row["course_id"]
        comps = []
        for col in component_columns:
            if col in df_assessment.columns:
                val = row[col]
                if pd.notna(val) and float(val) > 0:
                    comps.append((col, float(val) / 100.0))
        course_assessments[c_code] = comps

    courses_file = ACADEMICS_DIR / "courses.csv"
    df_courses = pd.read_csv(courses_file, encoding="utf-8-sig")
    credits_map: Dict[str, float] = dict(zip(df_courses["course_code"], df_courses["credits"].astype(float)))

    # Điều kiện tiên quyết (TQ)
    prereqs_file = ACADEMICS_DIR / "course_prerequisites.csv"
    df_prereqs = pd.read_csv(prereqs_file, encoding="utf-8-sig")
    tq_map: Dict[str, Set[str]] = defaultdict(set)
    for _, r in df_prereqs[df_prereqs["relation_type"] == "TQ"].iterrows():
        tq_map[r["course_code"]].add(r["prerequisite_course_code"])

    # Theo dõi số tín chỉ đăng ký thực tế của từng sinh viên trong HK242 (tối đa 22 TC)
    student_credits: Dict[str, float] = defaultdict(float)

    def can_enroll(uid: str, course_code: str) -> bool:
        """Kiểm tra điều kiện đăng ký môn học: Tiên quyết (TQ) & Giới hạn tối đa 22 tín chỉ."""
        tc = credits_map.get(course_code, 0.0)
        if tc > 0 and (student_credits[uid] + tc > MAX_SEMESTER_CREDITS):
            return False

        # Đối với CO4337: Bắt buộc đã hoàn thành Thực tập CO3335 và Đồ án CN CO4029
        for req in tq_map.get(course_code, set()):
            if req not in history_passed[uid]:
                return False
        return True

    k24_accel = get_k24_acceleration_students(k24_students, df_profiles)
    k23_accel = get_k23_acceleration_students(k23_students, df_profiles, k23_passed_mt2013)
    k23_group_d = get_k23_group_d_distribution(k23_students)

    k24_compulsory = get_curriculum_for_cohort_semester("K24", 2)["compulsory_courses"]
    k24_core_courses = [c["course_code"] for c in k24_compulsory if not c["course_code"].startswith("LA")]

    k23_compulsory = get_curriculum_for_cohort_semester("K23", 4)["compulsory_courses"]
    k23_core_courses = [c["course_code"] for c in k23_compulsory if not c["course_code"].startswith("LA") and c["course_code"] != "MT2013"]

    k22_compulsory = get_curriculum_for_cohort_semester("K22", 6)["compulsory_courses"]
    k22_core_courses = [c["course_code"] for c in k22_compulsory if c["course_code"] not in ("CH1003", "CO3093")]

    k21_compulsory = get_curriculum_for_cohort_semester("K21", 8)["compulsory_courses"]

    enrollment_records: List[Dict[str, Any]] = []
    enrollment_id = total_past_enrollments + 1

    classes_by_prog_course: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, r in df_classes.iterrows():
        classes_by_prog_course[(r["program"], r["course_code"])].append(r["class_id"])

    def record_grade(uid: str, course_code: str, class_id: Any, is_retake: bool, seed_suffix: str = ""):
        nonlocal enrollment_id
        profile = student_profiles[uid]
        student_data = {"student_id": uid, **profile}

        seed_str = f"{uid}:{course_code}:{SEMESTER}{seed_suffix}"
        rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

        comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])
        component_scores, final_score, letter, gpa = score_course_components(
            student=student_data,
            course_code=course_code,
            components=comps,
            catalog_difficulty=0.5,
            rng=rng,
            config=GENERATOR_CONFIG,
            retaken=is_retake,
            student_id=uid,
        )

        tc = credits_map.get(course_code, 0.0)
        student_credits[uid] += tc

        rec = {
            "enrollment_id": enrollment_id,
            "student_id": uid,
            "class_id": class_id,
            "course_id": course_code,
            "semester": SEMESTER,
            "retaken": is_retake,
            "quiz": component_scores.get("quiz", np.nan),
            "lab": component_scores.get("lab", np.nan),
            "btl": component_scores.get("btl", np.nan),
            "giua_ky": component_scores.get("giua_ky", np.nan),
            "cuoi_ky": component_scores.get("cuoi_ky", np.nan),
            "final_score": final_score,
            "letter_grade": letter,
            "gpa_4": gpa,
            "passed": letter != "F",
            "status": "Pass" if letter != "F" else "Fail",
        }
        enrollment_records.append(rec)
        enrollment_id += 1

    # -------------------------------------------------------------------------
    # A. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K24 (HỌC KỲ 2)
    # -------------------------------------------------------------------------
    print("\n4. Đang xử lý đăng ký và điểm cho KHÓA K24 (Học kỳ 2)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k24 = k24_students[k24_students["program"] == prog].copy()
        student_ids = p_k24["user_id"].tolist()
        print(f"\n* K24 hệ {prog} ({len(student_ids)} sinh viên)")

        for course_code in k24_core_courses:
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            retakers = [
                uid for uid in retake_demand.get(course_code, [])
                if uid in set(df_students[df_students["program"] == prog]["user_id"])
            ]
            all_candidates = student_ids + retakers
            valid_uids = [uid for uid in all_candidates if can_enroll(uid, course_code)]
            sizes = balanced_class_sizes(len(valid_uids), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_uids[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(retakers)))

            print(f"   -> Đã gán {len(valid_uids)} SV vào môn {course_code} ({len(class_ids)} lớp)")

        # Môn Ngoại ngữ LA1005 cho K24
        if prog == "standard":
            course_code = "LA1005"
            eligible_uids = [uid for uid in student_ids if uid in k24_passed_la1003]
            retakers_la1005 = [
                uid for uid in retake_demand.get("LA1005", [])
                if uid in set(df_students[df_students["program"] == "standard"]["user_id"])
            ]
            all_la1005 = eligible_uids + retakers_la1005
            valid_la1005 = [uid for uid in all_la1005 if can_enroll(uid, course_code)]
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_la1005), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_la1005[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(retakers_la1005)))

            print(f"   -> Đã gán {len(valid_la1005)} SV vào môn LA1005 ({len(class_ids)} lớp)")

        # Môn học vượt K24: CH1003
        accel_uids = k24_accel.get(prog, [])
        valid_accel = [uid for uid in accel_uids if can_enroll(uid, "CH1003")]
        if valid_accel:
            course_code = "CH1003"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_accel), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_accel[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=False, seed_suffix="_accel")

            print(f"   -> [K24 Học vượt] {len(valid_accel)} SV học vượt CH1003 vào {len(class_ids)} lớp.")

    # -------------------------------------------------------------------------
    # B. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K23 (HỌC KỲ 4)
    # -------------------------------------------------------------------------
    print("\n5. Đang xử lý đăng ký và điểm cho KHÓA K23 (Học kỳ 4)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k23 = k23_students[k23_students["program"] == prog].copy()
        student_ids = p_k23["user_id"].tolist()
        print(f"\n* K23 hệ {prog} ({len(student_ids)} sinh viên)")

        for course_code in k23_core_courses:
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            is_politics = course_code.startswith("SP")
            max_cap = 120 if is_politics else 40
            retakers = [
                uid for uid in retake_demand.get(course_code, [])
                if uid in set(df_students[df_students["program"] == prog]["user_id"])
            ]
            all_candidates = student_ids + retakers
            valid_uids = [uid for uid in all_candidates if can_enroll(uid, course_code)]
            sizes = balanced_class_sizes(len(valid_uids), max_size=max_cap)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_uids[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(retakers)))

            print(f"   -> Đã gán {len(valid_uids)} SV vào môn {course_code} ({len(class_ids)} lớp)")

        # MT2013 cho K23 (bỏ qua nếu đã học vượt ở HK241)
        k23_mt2013_learners = [uid for uid in student_ids if uid not in k23_passed_mt2013]
        retakers_mt2013 = [
            uid for uid in retake_demand.get("MT2013", [])
            if uid in set(df_students[df_students["program"] == prog]["user_id"])
        ]
        all_mt2013 = k23_mt2013_learners + retakers_mt2013
        valid_mt2013 = [uid for uid in all_mt2013 if can_enroll(uid, "MT2013")]
        if valid_mt2013:
            course_code = "MT2013"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_mt2013), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_mt2013[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(retakers_mt2013)))

            print(f"   -> Đã gán {len(valid_mt2013)} SV vào môn MT2013 ({len(class_ids)} lớp)")

        # Môn Ngoại ngữ LA1009 cho K23 Đại trà
        if prog == "standard":
            course_code = "LA1009"
            eligible_uids = [uid for uid in student_ids if uid in k23_passed_la1007]
            retakers_la1009 = [
                uid for uid in retake_demand.get("LA1009", [])
                if uid in set(df_students[df_students["program"] == "standard"]["user_id"])
            ]
            all_la1009 = eligible_uids + retakers_la1009
            valid_la1009 = [uid for uid in all_la1009 if can_enroll(uid, course_code)]
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_la1009), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_la1009[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(retakers_la1009)))

            print(f"   -> Đã gán {len(valid_la1009)} SV vào môn LA1009 ({len(class_ids)} lớp)")

        # Tự chọn Quản lý Kỹ thuật Group D cho K23
        for g_course in GROUP_D_COURSES:
            g_uids = k23_group_d.get((prog, g_course), [])
            valid_g_uids = [uid for uid in g_uids if can_enroll(uid, g_course)]
            if not valid_g_uids:
                continue
            class_ids = classes_by_prog_course.get((prog, g_course), [])
            sizes = balanced_class_sizes(len(valid_g_uids), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_g_uids[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, g_course, class_id, is_retake=False)

        # Môn học vượt K23: CO3093 & CO2013
        accel_uids = k23_accel.get(prog, [])
        for accel_code in ["CO3093", "CO2013"]:
            valid_accel = [uid for uid in accel_uids if can_enroll(uid, accel_code)]
            if not valid_accel:
                continue
            class_ids = classes_by_prog_course.get((prog, accel_code), [])
            sizes = balanced_class_sizes(len(valid_accel), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_accel[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, accel_code, class_id, is_retake=False, seed_suffix="_accel")

            print(f"   -> [K23 Học vượt] {len(valid_accel)} SV học vượt {accel_code} vào {len(class_ids)} lớp.")

    # -------------------------------------------------------------------------
    # C. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K22 (HỌC KỲ 6)
    # -------------------------------------------------------------------------
    print("\n6. Đang xử lý đăng ký và điểm cho KHÓA K22 (Học kỳ 6)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k22 = k22_students[k22_students["program"] == prog].copy()
        student_ids = p_k22["user_id"].tolist()
        print(f"\n* K22 hệ {prog} ({len(student_ids)} sinh viên)")

        # SP1037 (Tư tưởng Hồ Chí Minh)
        course_code = "SP1037"
        class_ids = classes_by_prog_course.get((prog, course_code), [])
        retakers = [
            uid for uid in retake_demand.get(course_code, [])
            if uid in set(df_students[df_students["program"] == prog]["user_id"])
        ]
        all_candidates = student_ids + retakers
        valid_uids = [uid for uid in all_candidates if can_enroll(uid, course_code)]
        sizes = balanced_class_sizes(len(valid_uids), max_size=120)
        offset = 0
        for class_id, size in zip(class_ids, sizes):
            assigned_chunk = valid_uids[offset : offset + size]
            offset += size
            for uid in assigned_chunk:
                record_grade(uid, course_code, class_id, is_retake=(uid in set(retakers)))
        print(f"   -> Đã gán {len(valid_uids)} SV vào môn {course_code} ({len(class_ids)} lớp)")

        # CH1003 cho K22 (bỏ qua nếu đã học vượt)
        k22_ch1003_learners = [uid for uid in student_ids if uid not in k22_passed_ch1003]
        retakers_ch1003 = [
            uid for uid in retake_demand.get("CH1003", [])
            if uid in set(df_students[df_students["program"] == prog]["user_id"])
        ]
        all_ch1003 = k22_ch1003_learners + retakers_ch1003
        valid_ch1003 = [uid for uid in all_ch1003 if can_enroll(uid, "CH1003")]
        if valid_ch1003:
            course_code = "CH1003"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_ch1003), max_size=40)
            offset = 0
            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_ch1003[offset : offset + size]
                offset += size
                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(retakers_ch1003)))
            print(f"   -> Đã gán {len(valid_ch1003)} SV vào môn CH1003 ({len(class_ids)} lớp)")

        # CO3093 cho K22 (bỏ qua nếu đã học vượt)
        k22_co3093_learners = [uid for uid in student_ids if uid not in k22_passed_co3093]
        retakers_co3093 = [
            uid for uid in retake_demand.get("CO3093", [])
            if uid in set(df_students[df_students["program"] == prog]["user_id"])
        ]
        all_co3093 = k22_co3093_learners + retakers_co3093
        valid_co3093 = [uid for uid in all_co3093 if can_enroll(uid, "CO3093")]
        if valid_co3093:
            course_code = "CO3093"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_co3093), max_size=40)
            offset = 0
            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_co3093[offset : offset + size]
                offset += size
                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(retakers_co3093)))
            print(f"   -> Đã gán {len(valid_co3093)} SV vào môn CO3093 ({len(class_ids)} lớp)")

        # Lộ trình sớm 3.5 năm & Tự chọn Group C cho K22 (Hệ Tiên tiến học chung với CLC)
        if prog == "advanced":
            print(f"   -> [K22 Lộ trình sớm]: Đã ghép học chung lớp với hệ Chất lượng cao (CC)")
            print(f"   -> [K22 Tự chọn ngành - Group C]: Đã ghép học chung lớp với hệ Chất lượng cao (CC)")
        else:
            if prog == "high-quality":
                k22_adv_uids = k22_students[k22_students["program"] == "advanced"]["user_id"].tolist()
                combined_student_ids = student_ids + k22_adv_uids
            else:
                combined_student_ids = student_ids

            early_candidates = [
                uid for uid in combined_student_ids
                if str(student_profiles.get(uid, {}).get("early_graduation_candidate", "")).lower() == "true"
            ]
            if early_candidates:
                for early_code in ["CO3061", "CO4029"]:
                    valid_early = [uid for uid in early_candidates if can_enroll(uid, early_code)]
                    if not valid_early:
                        continue
                    class_ids = classes_by_prog_course.get((prog, early_code), [])
                    sizes = balanced_class_sizes(len(valid_early), max_size=40)
                    offset = 0
                    for class_id, size in zip(class_ids, sizes):
                        assigned_chunk = valid_early[offset : offset + size]
                        offset += size
                        for uid in assigned_chunk:
                            record_grade(uid, early_code, class_id, is_retake=False, seed_suffix="_early")
                    suffix_note = " (CLC+TT)" if prog == "high-quality" else ""
                    print(f"   -> [K22 Lộ trình sớm] {len(valid_early)} SV hoàn tất {early_code}{suffix_note} ({len(class_ids)} lớp)")

            # Tự chọn ngành Group C cho các SV K22 còn lại (chọn 2 môn theo chuyên ngành)
            remaining_uids = [uid for uid in combined_student_ids if uid not in set(early_candidates)]
            if remaining_uids:
                spec_map = get_student_specialization_map()
                student_c_choices: Dict[str, List[str]] = defaultdict(list)
                for uid in remaining_uids:
                    spec = spec_map.get(uid, "Khoa học Máy tính")
                    prev_passed = set(history_passed.get(uid, {}).keys())
                    c1 = select_student_group_c_course(uid, "K22", spec, seed_salt="k22_group_c_1_hk242", exclude_courses=prev_passed)
                    c2 = select_student_group_c_course(uid, "K22", spec, seed_salt="k22_group_c_2_hk242", exclude_courses=prev_passed | {c1})
                    c_ga = select_student_group_a_course(spec)
                    if can_enroll(uid, c1):
                        student_c_choices[c1].append(uid)
                    if can_enroll(uid, c2):
                        student_c_choices[c2].append(uid)
                    if can_enroll(uid, c_ga):
                        student_c_choices[c_ga].append(uid)

                for g_course, valid_g in student_c_choices.items():
                    if not valid_g:
                        continue
                    class_ids = classes_by_prog_course.get((prog, g_course), [])
                    sizes = balanced_class_sizes(len(valid_g), max_size=40)
                    offset = 0
                    for class_id, size in zip(class_ids, sizes):
                        assigned_chunk = valid_g[offset : offset + size]
                        offset += size
                        for uid in assigned_chunk:
                            record_grade(uid, g_course, class_id, is_retake=False)

    # -------------------------------------------------------------------------
    # D. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K21 (HỌC KỲ 8 - TỐT NGHIỆP CHUẨN 4 NĂM) & K20 TRẢ NỢ
    # -------------------------------------------------------------------------
    print("\n7. Đang xử lý đăng ký và điểm cho KHÓA K21 (Học kỳ 8 - Chuẩn 4 năm) & K20 TRẢ NỢ...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k21 = k21_active_students[k21_active_students["program"] == prog].copy()
        student_ids = p_k21["user_id"].tolist()
        print(f"\n* K21 hệ {prog} ({len(student_ids)} sinh viên)")

        # K20 trả nợ CO4337 và SP1007
        k20_prog_retakers_co4337 = [
            uid for uid in retake_demand.get("CO4337", [])
            if uid in set(k20_active_students[k20_active_students["program"] == prog]["user_id"])
        ]
        k20_prog_retakers_sp1007 = [
            uid for uid in retake_demand.get("SP1007", [])
            if uid in set(k20_active_students[k20_active_students["program"] == prog]["user_id"])
        ]

        # CO4337 (Khóa luận tốt nghiệp)
        all_co4337 = student_ids + k20_prog_retakers_co4337
        valid_co4337 = [uid for uid in all_co4337 if can_enroll(uid, "CO4337")]
        class_ids = classes_by_prog_course.get((prog, "CO4337"), [])
        sizes = balanced_class_sizes(len(valid_co4337), max_size=40)
        offset = 0
        for class_id, size in zip(class_ids, sizes):
            assigned_chunk = valid_co4337[offset : offset + size]
            offset += size
            for uid in assigned_chunk:
                record_grade(uid, "CO4337", class_id, is_retake=(uid in set(k20_prog_retakers_co4337)), seed_suffix="_grad")
        print(f"   -> [CO4337] {len(valid_co4337)} SV hoàn tất đăng ký ({len(class_ids)} lớp)")

        # SP1007 (Pháp luật Việt Nam Đại cương)
        all_sp1007 = student_ids + k20_prog_retakers_sp1007
        valid_sp1007 = [uid for uid in all_sp1007 if can_enroll(uid, "SP1007")]
        class_ids = classes_by_prog_course.get((prog, "SP1007"), [])
        sizes = balanced_class_sizes(len(valid_sp1007), max_size=120)
        offset = 0
        for class_id, size in zip(class_ids, sizes):
            assigned_chunk = valid_sp1007[offset : offset + size]
            offset += size
            for uid in assigned_chunk:
                record_grade(uid, "SP1007", class_id, is_retake=(uid in set(k20_prog_retakers_sp1007)), seed_suffix="_grad")
        print(f"   -> [SP1007] {len(valid_sp1007)} SV hoàn tất đăng ký ({len(class_ids)} lớp)")

        # Tự chọn tự do (2 môn) cho K21
        if prog == "advanced":
            print(f"   -> [K21 Tự chọn tự do]: Đã ghép học chung lớp với hệ Chất lượng cao (CC)")
        else:
            if prog == "high-quality":
                k21_adv_uids = set(k21_active_students[k21_active_students["program"] == "advanced"]["user_id"])
                combined_student_ids = student_ids + [uid for uid in k21_adv_uids if uid not in set(student_ids)]
            else:
                combined_student_ids = student_ids

            if combined_student_ids:
                student_c_choices: Dict[str, List[str]] = defaultdict(list)
                for uid in combined_student_ids:
                    prev_passed = set(history_passed[uid].keys())
                    elecs = get_term8_student_electives(uid, "K21", prev_passed)
                    for ec in elecs:
                        student_c_choices[ec].append(uid)

                enrollment_id = enroll_students_in_electives(
                    student_choices=student_c_choices,
                    prog=prog,
                    classes_by_prog_course=classes_by_prog_course,
                    course_assessments=course_assessments,
                    student_profiles=student_profiles,
                    semester=SEMESTER,
                    config=GENERATOR_CONFIG,
                    enrollment_records=enrollment_records,
                    start_enrollment_id=enrollment_id,
                    max_cap=40,
                )
                suffix_note = " (CLC+TT)" if prog == "high-quality" else ""
                print(f"   -> [K21 Tự chọn tự do]{suffix_note}: Đã phân bổ {len(combined_student_ids)} SV vào {len(student_c_choices)} môn học.")

    # -------------------------------------------------------------------------
    # E. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO LỚP HỌC LẠI MÔN LẺ/HK1 (L_HL)
    # -------------------------------------------------------------------------
    print("\n8. Đang xử lý đăng ký cho các LỚP HỌC LẠI MÔN LẺ/HK1 (L_HL)...")
    odd_courses_retake = [
        "SP1035", "CO3001", "CO1005", "CO2011", "SP1031", "CO2001", "CO3005",
        "MT1003", "CO1023", "PH1003", "CO2003", "SP1039", "CO2007", "LA1003",
        "CO4029",
    ]
    for retake_code in odd_courses_retake:
        uids = retake_demand.get(retake_code, [])
        valid_retakers = [uid for uid in uids if can_enroll(uid, retake_code)]
        if len(valid_retakers) < 15:
            continue
        class_ids = classes_by_prog_course.get(("standard", retake_code), [])
        hl_classes = [c for c in class_ids if "L_HL" in c]
        if not hl_classes:
            continue
        sizes = balanced_class_sizes(len(valid_retakers), max_size=40)
        offset = 0

        for class_id, size in zip(hl_classes, sizes):
            assigned_chunk = valid_retakers[offset : offset + size]
            offset += size

            for uid in assigned_chunk:
                record_grade(uid, retake_code, class_id, is_retake=True, seed_suffix="_retake")

        print(f"   -> [Lớp học lại L_HL] {retake_code}: {len(valid_retakers)} SV vào {len(hl_classes)} lớp")

    # -------------------------------------------------------------------------
    # HỌC LẠI CẢI THIỆN ĐIỂM (D, D+) CHO SINH VIÊN KỲ 7+ CÓ GPA DỰ KIẾN < 2.0
    # -------------------------------------------------------------------------
    improvement_records = generate_grade_improvement_retakes(
        semester=SEMESTER,
        prev_enrollments=all_prev_enrollments,
        df_classes=df_classes,
        course_assessments=course_assessments,
        credits_map=credits_map,
        student_profiles=student_profiles,
        df_students=df_students,
        current_records=enrollment_records,
        start_enrollment_id=enrollment_id,
        max_courses_per_student=2,
    )
    if improvement_records:
        enrollment_records.extend(improvement_records)
        enrollment_id += len(improvement_records)
        print(f"   -> [Học cải thiện điểm] Đã xếp {len(improvement_records)} lượt học cải thiện cho sinh viên có GPA < 2.0.")

    # -------------------------------------------------------------------------
    # F. TÍNH GPA HỌC KỲ VÀ TÍCH LŨY
    # -------------------------------------------------------------------------
    print("\n9. Đang tính điểm trung bình học kỳ cho cả 5 khóa...")
    df_enrollment = pd.DataFrame(enrollment_records)

    semester_gpas: Dict[str, float] = {}
    for uid, attempts in df_enrollment.groupby("student_id"):
        hk_points = 0.0
        hk_credits = 0.0
        for _, att in attempts.iterrows():
            score = att["final_score"]
            gpa4 = att["gpa_4"]
            if pd.isna(score) or float(score) == 12.0 or pd.isna(gpa4):
                continue
            tc = credits_map.get(att["course_id"], 0.0)
            hk_points += float(gpa4) * tc
            hk_credits += tc

        semester_gpas[str(uid)] = round(hk_points / hk_credits, 2) if hk_credits > 0 else np.nan

    # Xuất file kết quả
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"enrollment_{SEMESTER.lower()}.csv"
    df_enrollment.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số bản ghi đăng ký trong {SEMESTER}: {len(df_enrollment):,} dòng.")

    # Thống kê chi tiết
    for ch in ["20", "21", "22", "23", "24"]:
        cnt = len(df_enrollment[df_enrollment["student_id"].str.startswith(ch)])
        print(f"- Bản ghi K{ch}: {cnt:,} lượt học.")

    passed_cnt = len(df_enrollment[df_enrollment["passed"] == True])
    failed_cnt = len(df_enrollment[df_enrollment["passed"] == False])
    print(f"- Tỷ lệ đạt: {passed_cnt:,} ({passed_cnt/len(df_enrollment)*100:.1f}%) | Rớt: {failed_cnt:,} ({failed_cnt/len(df_enrollment)*100:.1f}%)")

    valid_gpas = [g for g in semester_gpas.values() if pd.notna(g)]
    mean_hk_gpa = np.mean(valid_gpas) if valid_gpas else 0.0
    print(f"- GPA trung bình học kỳ {SEMESTER}: {mean_hk_gpa:.2f}/4.0")

    return out_file


if __name__ == "__main__":
    generate_enrollment_hk242()

