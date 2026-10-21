"""Generate enrollment records and course grades for semester HK222.

In this semester, three distinct cohorts attend classes simultaneously:
1. Cohort K22 in Term 2 (Freshmen - Học kỳ 2):
   - Compulsory courses: CO1007, MT1005, MT1007, PH1007, CO1027, LA1005
   - Accelerated: CH1003 (Hóa đại cương per additional_course_rules.csv priority 15)
   - K21 & K20 retakers join regular classes

2. Cohort K21 in Term 4 (Sophomore - Năm 2):
   - Compulsory courses: SP1033, CO2039, CO2017, LA1009,
     MT2013 (bỏ qua nếu đã hoàn thành ở HK221)
   - Tự chọn Khối Quản lý Kỹ thuật (Group D): IM1013, IM1023, IM1025, IM1027, IM3001
   - Accelerated: CO3093 (Mạng máy tính) & CO2013 (Hệ cơ sở Dữ liệu)

3. Cohort K20 in Term 6 (Junior - Năm 3):
   - Compulsory courses: CH1003, SP1037, CO3093 (bỏ qua nếu đã hoàn thành ở HK212)
   - Lộ trình tốt nghiệp sớm 3.5 năm (242 SV): CO3061 (Nhập môn AI) & CO4029 (Đồ án Chuyên ngành)

4. Lớp học lại cho các môn HK1 có số lượng rớt >= 20 sinh viên:
   - MT1003 (21 SV) -> L_HL01
   - PH1003 (37 SV) -> L_HL01
   - CO1005 (32 SV) -> L_HL01
   - CO1023 (23 SV) -> L_HL01
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
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

from academic_rules import (
    GENERATOR_CONFIG,
    balanced_class_sizes,
    convert_score_to_grade,
    score_course_components,
)

ANALYSIS_DIR = ROOT_DIR / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from analysis_helpers import get_curriculum_for_cohort_semester

SEMESTER = "HK222"
GROUP_D_COURSES = ["IM1013", "IM1023", "IM1025", "IM1027", "IM3001"]


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


def get_k22_acceleration_students(k22_students: pd.DataFrame, df_prof: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K22 students eligible to accelerate course (HK2)."""
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")
    top_code, _ = get_top_acceleration_course_for_term("HK2")
    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k22_students.iterrows():
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


def get_k21_acceleration_students(
    k21_students: pd.DataFrame, df_prof: pd.DataFrame, k21_passed_mt2013: Set[str]
) -> Dict[str, List[str]]:
    """Identify K21 students eligible to accelerate CO3093 and CO2013 in HK4."""
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")
    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k21_students.iterrows():
        uid = str(row["user_id"])
        prog = row["program"]
        p = prof_by_id.get(uid, {})
        is_early_candidate = str(p.get("early_graduation_candidate", "")).lower() == "true"

        if uid in k21_passed_mt2013 or is_early_candidate:
            accelerating_by_prog[prog].append(uid)

    return accelerating_by_prog


def get_k21_group_d_distribution(k21_students: pd.DataFrame) -> Dict[Tuple[str, str], List[str]]:
    """Distribute K21 students among Group D elective courses."""
    choice_map: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, row in k21_students.iterrows():
        uid = str(row["user_id"])
        prog = row["program"]
        seed_val = int(hashlib.sha256(f"{uid}:group_d".encode()).hexdigest()[:8], 16)
        c_code = GROUP_D_COURSES[seed_val % len(GROUP_D_COURSES)]
        choice_map[(prog, c_code)].append(uid)
    return choice_map


def generate_enrollment_hk222() -> Path:
    """Execute enrollment generation for semester HK222 and export to enrollment_hk222.csv."""
    print(f"=== KHỞI CHẠY SINH DỮ LIỆU ĐĂNG KÝ HỌC PHẦN CHO {SEMESTER} (ĐA KHÓA: K20, K21, K22) ===")

    # 1. Đọc sinh viên K20, K21, K22
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    k21_students = df_students[df_students["user_id"].str.startswith("21")].copy()
    k22_students = df_students[df_students["user_id"].str.startswith("22")].copy()
    print(f"1. Tổng SV: K20: {len(k20_students)} | K21: {len(k21_students)} | K22: {len(k22_students)}")

    # 2. Đọc danh sách lớp học phần HK222
    classes_file = CLASSES_DIR / "class_hk222.csv"
    if not classes_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file lớp: {classes_file}. Hãy chạy generate_class_hk222.py trước!")
    df_classes = pd.read_csv(classes_file, encoding="utf-8-sig")
    print(f"2. Tổng số lớp học phần đã mở cho HK222: {len(df_classes)} lớp.")

    # 3. Đọc lịch sử học tập các kỳ trước: HK201 -> HK221
    prior_sems = ["hk201", "hk202", "hk211", "hk212", "hk221"]
    prev_dfs = [
        pd.read_csv(OUTPUT_DIR / f"enrollment_{s}.csv", encoding="utf-8-sig", dtype={"student_id": str})
        for s in prior_sems
    ]
    total_past_enrollments = sum(len(df) for df in prev_dfs)

    # Lịch sử môn đạt của từng sinh viên
    history_passed: Dict[str, Dict[str, float]] = defaultdict(dict)
    for df_prev in prev_dfs:
        for _, r in df_prev.iterrows():
            sid = str(r["student_id"])
            cid = str(r["course_id"])
            score = r["final_score"]
            gpa4 = r["gpa_4"]
            if pd.isna(score) or float(score) == 12.0 or pd.isna(gpa4):
                continue
            if r["passed"] == True:
                history_passed[sid][cid] = float(gpa4)

    # K20 đã học vượt CO3093 ở HK212
    k20_passed_co3093 = {uid for uid in k20_students["user_id"] if "CO3093" in history_passed[uid]}

    # K21 đã học vượt MT2013 ở HK221
    k21_passed_mt2013 = {uid for uid in k21_students["user_id"] if "MT2013" in history_passed[uid]}

    # K21 đạt LA1007 ở HK221 -> đủ điều kiện học LA1009
    k21_passed_la1007 = {uid for uid in k21_students["user_id"] if "LA1007" in history_passed[uid]}

    # K22 đạt/miễn LA1003 ở HK221 -> đủ điều kiện học LA1005
    k22_passed_la1003 = {uid for uid in k22_students["user_id"] if "LA1003" in history_passed[uid]}

    # Sinh viên khóa trước còn nợ môn cần học lại
    all_prev_enrollments = pd.concat(prev_dfs)
    retake_demand: Dict[str, List[str]] = defaultdict(list)
    for _, r in all_prev_enrollments[all_prev_enrollments["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        if cid not in history_passed[sid] and sid not in retake_demand[cid]:
            retake_demand[cid].append(sid)

    # Lớp học lại môn HK1 (ngưỡng >= 20)
    hk1_candidates = ["MT1003", "PH1003", "CO1005", "CO1023"]
    hk1_retake_students: Dict[str, List[str]] = {}
    for c in hk1_candidates:
        uids = [sid for sid in retake_demand.get(c, []) if c not in history_passed[sid]]
        if len(uids) >= 20:
            hk1_retake_students[c] = uids

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

    profiles_file = USERS_DIR / "student_profiles.csv"
    df_profiles = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    student_profiles: Dict[str, Dict[str, Any]] = df_profiles.set_index("student_id").to_dict(orient="index")

    k22_accel = get_k22_acceleration_students(k22_students, df_profiles)
    k21_accel = get_k21_acceleration_students(k21_students, df_profiles, k21_passed_mt2013)
    k21_group_d = get_k21_group_d_distribution(k21_students)

    k22_compulsory = get_curriculum_for_cohort_semester("K22", 2)["compulsory_courses"]
    k22_core_courses = [c["course_code"] for c in k22_compulsory if not c["course_code"].startswith("LA")]

    k21_compulsory = get_curriculum_for_cohort_semester("K21", 4)["compulsory_courses"]
    k21_core_courses = [c["course_code"] for c in k21_compulsory if not c["course_code"].startswith("LA") and c["course_code"] != "MT2013"]

    k20_compulsory = get_curriculum_for_cohort_semester("K20", 6)["compulsory_courses"]
    k20_core_courses = [c["course_code"] for c in k20_compulsory if c["course_code"] != "CO3093"]

    enrollment_records: List[Dict[str, Any]] = []
    enrollment_id = total_past_enrollments + 1

    classes_by_prog_course: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, r in df_classes.iterrows():
        classes_by_prog_course[(r["program"], r["course_code"])].append(r["class_id"])

    # -------------------------------------------------------------------------
    # A. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K22 (HỌC KỲ 2)
    # -------------------------------------------------------------------------
    print("\n4. Đang xử lý đăng ký và điểm cho KHÓA K22 (Học kỳ 2)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k22 = k22_students[k22_students["program"] == prog].copy()
        student_ids = p_k22["user_id"].tolist()
        print(f"\n* K22 hệ {prog} ({len(student_ids)} sinh viên)")

        for course_code in k22_core_courses:
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            retakers = [
                uid for uid in retake_demand.get(course_code, [])
                if uid in set(df_students[df_students["program"] == prog]["user_id"])
            ]
            all_assigned_uids = student_ids + retakers
            sizes = balanced_class_sizes(len(all_assigned_uids), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = all_assigned_uids[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    is_retake = uid in set(retakers)
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{course_code}:{SEMESTER}"
                    rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

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

            retake_info = f" (+{len(retakers)} SV học ghép)" if retakers else ""
            print(f"   -> Đã gán {len(all_assigned_uids)} SV{retake_info} vào môn {course_code} ({len(class_ids)} lớp)")

        # Môn Tiếng Anh 2 (LA1005) cho K22 Đại trà
        if prog == "standard":
            course_code = "LA1005"
            k22_take_la1005 = [uid for uid in student_ids if uid in k22_passed_la1003]
            retakers_la1005 = [
                uid for uid in retake_demand.get("LA1005", [])
                if uid in set(df_students[df_students["program"] == "standard"]["user_id"])
            ]
            all_la1005 = k22_take_la1005 + retakers_la1005

            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(all_la1005), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = all_la1005[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    is_retake = uid in set(retakers_la1005)
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{course_code}:{SEMESTER}"
                    rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

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

            print(f"   -> Đã gán {len(all_la1005)} SV vào môn LA1005 ({len(class_ids)} lớp)")

        # Môn học vượt K22: CH1003 per additional_course_rules.csv priority 15
        accel_uids = k22_accel.get(prog, [])
        if accel_uids:
            course_code, _ = get_top_acceleration_course_for_term("HK2")
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(accel_uids), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = accel_uids[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{course_code}:{SEMESTER}_accel"
                    rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

                    component_scores, final_score, letter, gpa = score_course_components(
                        student=student_data,
                        course_code=course_code,
                        components=comps,
                        catalog_difficulty=0.5,
                        rng=rng,
                        config=GENERATOR_CONFIG,
                        retaken=False,
                        student_id=uid,
                    )

                    rec = {
                        "enrollment_id": enrollment_id,
                        "student_id": uid,
                        "class_id": class_id,
                        "course_id": course_code,
                        "semester": SEMESTER,
                        "retaken": False,
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

            print(f"   -> [K22 Học vượt] {len(accel_uids)} SV học vượt {course_code} vào {len(class_ids)} lớp.")

    # -------------------------------------------------------------------------
    # B. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K21 (HỌC KỲ 4)
    # -------------------------------------------------------------------------
    print("\n5. Đang xử lý đăng ký và điểm cho KHÓA K21 (Học kỳ 4)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k21 = k21_students[k21_students["program"] == prog].copy()
        student_ids = p_k21["user_id"].tolist()
        print(f"\n* K21 hệ {prog} ({len(student_ids)} sinh viên)")

        # SP1033, CO2039, CO2017
        for course_code in k21_core_courses:
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            k20_retakers = [
                uid for uid in retake_demand.get(course_code, [])
                if uid in set(k20_students[k20_students["program"] == prog]["user_id"])
            ]
            all_assigned_uids = student_ids + k20_retakers
            is_politics = course_code.startswith("SP")
            max_cap = 120 if is_politics else 40
            sizes = balanced_class_sizes(len(all_assigned_uids), max_size=max_cap)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = all_assigned_uids[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    is_retake = uid in set(k20_retakers)
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{course_code}:{SEMESTER}"
                    rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

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

            retake_str = f" (+{len(k20_retakers)} K20 học ghép)" if k20_retakers else ""
            print(f"   -> Đã gán {len(all_assigned_uids)} SV{retake_str} vào môn {course_code} ({len(class_ids)} lớp)")

        # MT2013 (chỉ SV K21 chưa hoàn thành ở HK221)
        k21_mt2013_learners = [uid for uid in student_ids if uid not in k21_passed_mt2013]
        if k21_mt2013_learners:
            course_code = "MT2013"
            k20_retakers = [
                uid for uid in retake_demand.get(course_code, [])
                if uid in set(k20_students[k20_students["program"] == prog]["user_id"])
            ]
            all_mt2013 = k21_mt2013_learners + k20_retakers
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(all_mt2013), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = all_mt2013[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    is_retake = uid in set(k20_retakers)
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{course_code}:{SEMESTER}"
                    rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

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

            print(f"   -> Đã gán {len(all_mt2013)} SV vào môn MT2013 ({len(class_ids)} lớp, miễn {len(student_ids)-len(k21_mt2013_learners)} SV)")

        # LA1009 cho K21 Đại trà
        if prog == "standard":
            course_code = "LA1009"
            k21_take_la1009 = [uid for uid in student_ids if uid in k21_passed_la1007]
            k20_retakers_la1009 = [
                uid for uid in retake_demand.get("LA1009", [])
                if uid in set(k20_students[k20_students["program"] == "standard"]["user_id"])
            ]
            all_la1009 = k21_take_la1009 + k20_retakers_la1009

            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(all_la1009), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = all_la1009[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    is_retake = uid in set(k20_retakers_la1009)
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{course_code}:{SEMESTER}"
                    rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

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

            print(f"   -> Đã gán {len(all_la1009)} SV vào môn LA1009 ({len(class_ids)} lớp)")

        # Tự chọn Group D cho K21
        print(f"   -> Phân bổ SV vào Tự chọn Quản lý Kỹ thuật (Group D):")
        for g_course in GROUP_D_COURSES:
            g_uids = k21_group_d.get((prog, g_course), [])
            if not g_uids:
                continue
            class_ids = classes_by_prog_course.get((prog, g_course), [])
            sizes = balanced_class_sizes(len(g_uids), max_size=40)
            offset = 0
            comps = course_assessments.get(g_course, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = g_uids[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{g_course}:{SEMESTER}"
                    rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

                    component_scores, final_score, letter, gpa = score_course_components(
                        student=student_data,
                        course_code=g_course,
                        components=comps,
                        catalog_difficulty=0.5,
                        rng=rng,
                        config=GENERATOR_CONFIG,
                        retaken=False,
                        student_id=uid,
                    )

                    rec = {
                        "enrollment_id": enrollment_id,
                        "student_id": uid,
                        "class_id": class_id,
                        "course_id": g_course,
                        "semester": SEMESTER,
                        "retaken": False,
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

            print(f"      * {g_course}: {len(g_uids)} SV -> {len(class_ids)} lớp")

        # Môn học vượt K21: CO3093 và CO2013
        accel_k21_prog = k21_accel.get(prog, [])
        if accel_k21_prog:
            for accel_code in ["CO3093", "CO2013"]:
                class_ids = classes_by_prog_course.get((prog, accel_code), [])
                sizes = balanced_class_sizes(len(accel_k21_prog), max_size=40)
                offset = 0
                comps = course_assessments.get(accel_code, [("cuoi_ky", 1.0)])

                for class_id, size in zip(class_ids, sizes):
                    assigned_chunk = accel_k21_prog[offset : offset + size]
                    offset += size

                    for uid in assigned_chunk:
                        profile = student_profiles[uid]
                        student_data = {"student_id": uid, **profile}

                        seed_str = f"{uid}:{accel_code}:{SEMESTER}_accel"
                        rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

                        component_scores, final_score, letter, gpa = score_course_components(
                            student=student_data,
                            course_code=accel_code,
                            components=comps,
                            catalog_difficulty=0.5,
                            rng=rng,
                            config=GENERATOR_CONFIG,
                            retaken=False,
                            student_id=uid,
                        )

                        rec = {
                            "enrollment_id": enrollment_id,
                            "student_id": uid,
                            "class_id": class_id,
                            "course_id": accel_code,
                            "semester": SEMESTER,
                            "retaken": False,
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

                print(f"   -> [K21 Học vượt] {len(accel_k21_prog)} SV học vượt {accel_code} vào {len(class_ids)} lớp.")

    # -------------------------------------------------------------------------
    # C. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K20 (HỌC KỲ 6)
    # -------------------------------------------------------------------------
    print("\n6. Đang xử lý đăng ký và điểm cho KHÓA K20 (Học kỳ 6)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k20 = k20_students[k20_students["program"] == prog].copy()
        student_ids = p_k20["user_id"].tolist()
        print(f"\n* K20 hệ {prog} ({len(student_ids)} sinh viên)")

        # CH1003 và SP1037
        for course_code in k20_core_courses:
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            # Lọc các lớp dành cho K20 (tránh lớp học vượt K22 nếu cùng mã)
            k20_classes = [c for c in class_ids if not c.endswith("01") or len(class_ids) == 1]
            if not k20_classes:
                k20_classes = class_ids

            is_politics = course_code.startswith("SP")
            max_cap = 120 if is_politics else 40
            sizes = balanced_class_sizes(len(student_ids), max_size=max_cap)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(k20_classes, sizes):
                assigned_chunk = student_ids[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{course_code}:{SEMESTER}"
                    rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

                    component_scores, final_score, letter, gpa = score_course_components(
                        student=student_data,
                        course_code=course_code,
                        components=comps,
                        catalog_difficulty=0.5,
                        rng=rng,
                        config=GENERATOR_CONFIG,
                        retaken=False,
                        student_id=uid,
                    )

                    rec = {
                        "enrollment_id": enrollment_id,
                        "student_id": uid,
                        "class_id": class_id,
                        "course_id": course_code,
                        "semester": SEMESTER,
                        "retaken": False,
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

            print(f"   -> Đã gán {len(student_ids)} SV vào môn {course_code} ({len(k20_classes)} lớp)")

        # CO3093 (chỉ SV K20 chưa học vượt ở HK212)
        k20_co3093_learners = [uid for uid in student_ids if uid not in k20_passed_co3093]
        if k20_co3093_learners:
            course_code = "CO3093"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            # Lọc các lớp dành cho K20
            k20_classes = [c for c in class_ids if "Học vượt" not in c] or class_ids
            sizes = balanced_class_sizes(len(k20_co3093_learners), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(k20_classes, sizes):
                assigned_chunk = k20_co3093_learners[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{course_code}:{SEMESTER}"
                    rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

                    component_scores, final_score, letter, gpa = score_course_components(
                        student=student_data,
                        course_code=course_code,
                        components=comps,
                        catalog_difficulty=0.5,
                        rng=rng,
                        config=GENERATOR_CONFIG,
                        retaken=False,
                        student_id=uid,
                    )

                    rec = {
                        "enrollment_id": enrollment_id,
                        "student_id": uid,
                        "class_id": class_id,
                        "course_id": course_code,
                        "semester": SEMESTER,
                        "retaken": False,
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

            print(f"   -> Đã gán {len(k20_co3093_learners)} SV vào môn CO3093 ({len(k20_classes)} lớp, miễn {len(student_ids)-len(k20_co3093_learners)} SV)")

        # Lộ trình tốt nghiệp sớm 3.5 năm: CHỈ DÀNH RIÊNG CHO early_graduation_candidate
        early_candidates = [
            uid for uid in student_ids
            if str(student_profiles.get(uid, {}).get("early_graduation_candidate", "")).lower() == "true"
        ]
        if early_candidates:
            for early_code in ["CO3061", "CO4029"]:
                class_ids = classes_by_prog_course.get((prog, early_code), [])
                sizes = balanced_class_sizes(len(early_candidates), max_size=40)
                offset = 0
                comps = course_assessments.get(early_code, [("cuoi_ky", 1.0)])

                for class_id, size in zip(class_ids, sizes):
                    assigned_chunk = early_candidates[offset : offset + size]
                    offset += size

                    for uid in assigned_chunk:
                        profile = student_profiles[uid]
                        student_data = {"student_id": uid, **profile}

                        seed_str = f"{uid}:{early_code}:{SEMESTER}_early"
                        rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

                        component_scores, final_score, letter, gpa = score_course_components(
                            student=student_data,
                            course_code=early_code,
                            components=comps,
                            catalog_difficulty=0.5,
                            rng=rng,
                            config=GENERATOR_CONFIG,
                            retaken=False,
                            student_id=uid,
                        )

                        rec = {
                            "enrollment_id": enrollment_id,
                            "student_id": uid,
                            "class_id": class_id,
                            "course_id": early_code,
                            "semester": SEMESTER,
                            "retaken": False,
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

                print(f"   -> [K20 Tốt nghiệp sớm] {len(early_candidates)} SV học {early_code} vào {len(class_ids)} lớp.")

    # -------------------------------------------------------------------------
    # D. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO LỚP HỌC LẠI MÔN HK1
    # -------------------------------------------------------------------------
    print("\n7. Đang xử lý đăng ký cho các LỚP HỌC LẠI MÔN HK1 (Nhu cầu >= 20 SV)...")
    for retake_code, uids in hk1_retake_students.items():
        class_ids = classes_by_prog_course.get(("standard", retake_code), [])
        hl_classes = [c for c in class_ids if "L_HL" in c]
        if not hl_classes:
            continue
        sizes = balanced_class_sizes(len(uids), max_size=40)
        offset = 0
        comps = course_assessments.get(retake_code, [("cuoi_ky", 1.0)])

        for class_id, size in zip(hl_classes, sizes):
            assigned_chunk = uids[offset : offset + size]
            offset += size

            for uid in assigned_chunk:
                profile = student_profiles[uid]
                student_data = {"student_id": uid, **profile}

                seed_str = f"{uid}:{retake_code}:{SEMESTER}_retake"
                rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

                component_scores, final_score, letter, gpa = score_course_components(
                    student=student_data,
                    course_code=retake_code,
                    components=comps,
                    catalog_difficulty=0.5,
                    rng=rng,
                    config=GENERATOR_CONFIG,
                    retaken=True,
                    student_id=uid,
                )

                rec = {
                    "enrollment_id": enrollment_id,
                    "student_id": uid,
                    "class_id": class_id,
                    "course_id": retake_code,
                    "semester": SEMESTER,
                    "retaken": True,
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

        print(f"   -> [Học lại] {len(uids)} SV học lại {retake_code} vào {len(hl_classes)} lớp ({hl_classes}).")

    # -------------------------------------------------------------------------
    # E. TÍNH GPA HỌC KỲ VÀ TÍCH LŨY
    # -------------------------------------------------------------------------
    print("\n8. Đang tính điểm trung bình học kỳ và GPA tích lũy cho cả K20, K21 và K22...")
    df_enrollment = pd.DataFrame(enrollment_records)

    semester_gpas: Dict[str, float] = {}
    final_gpas: Dict[str, float] = {}

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

        semester_gpas[uid] = round(hk_points / hk_credits, 2) if hk_credits > 0 else np.nan

        all_passed = dict(history_passed[uid])
        for _, att in attempts.iterrows():
            if att["passed"] and pd.notna(att["gpa_4"]) and float(att["final_score"]) != 12.0:
                cid = att["course_id"]
                all_passed[cid] = float(att["gpa_4"])

        tot_pts = 0.0
        tot_creds = 0.0
        for cid, g4 in all_passed.items():
            tc = credits_map.get(cid, 0.0)
            tot_pts += g4 * tc
            tot_creds += tc

        final_gpas[uid] = round(tot_pts / tot_creds, 2) if tot_creds > 0 else np.nan

    df_enrollment["semester_gpa"] = df_enrollment["student_id"].map(semester_gpas)
    df_enrollment["cumulative_gpa"] = df_enrollment["student_id"].map(final_gpas)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"enrollment_{SEMESTER.lower()}.csv"
    df_enrollment.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số bản ghi đăng ký trong {SEMESTER}: {len(df_enrollment):,} dòng.")

    k20_count = len(df_enrollment[df_enrollment["student_id"].str.startswith("20")])
    k21_count = len(df_enrollment[df_enrollment["student_id"].str.startswith("21")])
    k22_count = len(df_enrollment[df_enrollment["student_id"].str.startswith("22")])
    print(f"- Bản ghi K20 (Học kỳ 6): {k20_count:,} lượt học.")
    print(f"- Bản ghi K21 (Học kỳ 4): {k21_count:,} lượt học.")
    print(f"- Bản ghi K22 (Học kỳ 2): {k22_count:,} lượt học.")

    pass_count = len(df_enrollment[df_enrollment["passed"] == True])
    fail_count = len(df_enrollment[df_enrollment["passed"] == False])
    print(f"- Tỷ lệ đạt: {pass_count:,} ({pass_count/len(df_enrollment):.1%}) | Rớt: {fail_count:,} ({fail_count/len(df_enrollment):.1%})")

    avg_sem_gpa = df_enrollment.drop_duplicates(subset=["student_id"])["semester_gpa"].mean()
    avg_cum_gpa = df_enrollment.drop_duplicates(subset=["student_id"])["cumulative_gpa"].mean()
    print(f"- GPA trung bình học kỳ {SEMESTER}: {avg_sem_gpa:.2f}/4.0")
    print(f"- GPA tích lũy trung bình toàn trường: {avg_cum_gpa:.2f}/4.0")

    return out_file


if __name__ == "__main__":
    generate_enrollment_hk222()

