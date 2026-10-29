"""Generate enrollment records and course grades for semester HK231.

In this semester, four distinct cohorts attend classes simultaneously:
1. Cohort K23 in Term 1 (Freshmen - Tân sinh viên):
   - Compulsory courses: MT1003, PH1003, CO1005, CO1023, PE1003, LA1003
   - CLC and Advanced: 100% exempted from English (LA1003, LA1005, LA1007, LA1009)
   - Standard: Placement test exemption (~25%) or class enrollment
   - Retakers from older cohorts join regular classes

2. Cohort K22 in Term 3 (Sophomore - Năm 2):
   - Compulsory courses: CO2011, SP1031, CO2003, CO2007, LA1007
   - Accelerated: MT2013 (Xác suất & Thống kê) per ADD_MT2013_HK3

3. Cohort K21 in Term 5 (Junior - Năm 3):
   - Compulsory courses: SP1035, CO2001, CO3001, CO3005,
     CO2013 (bỏ qua nếu đã hoàn thành ở HK222)
   - Elective Group C: CO3011, CO3021, CO3029, CO3043, CO3045

4. Cohort K20 in Term 7 (Senior - Năm 4):
   - Compulsory courses: SP1039, CO3335,
     CO4029 (bỏ qua nếu đã hoàn thành ở HK222)
   - Lộ trình tốt nghiệp sớm 3.5 năm (242 SV K20): CO4337 (Đồ án tốt nghiệp) & SP1007
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

ENROLLMENTS_DIR = Path(__file__).resolve().parent
if str(ENROLLMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(ENROLLMENTS_DIR))
from retake_improvement_helper import generate_grade_improvement_retakes

from curriculum_rules import (
    enroll_students_in_electives,
    get_student_specialization_map,
    get_term7_student_electives,
    get_term8_student_electives,
    select_student_group_c_course,
)

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

SEMESTER = "HK231"
K23_ENGLISH_COURSES = ["LA1003", "LA1005", "LA1007", "LA1009"]
GROUP_C_COURSES = ["CO3011", "CO3021", "CO3029", "CO3043", "CO3045"]


def is_k23_standard_exempt_la1003(student_id: str) -> bool:
    """Determine whether a K23 Standard freshman qualifies for LA1003 exemption."""
    digest = hashlib.sha256(f"{student_id}:la1003_placement".encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    return (seed % 100) < 25


def get_k22_acceleration_students(k22_students: pd.DataFrame, df_prof: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K22 students accelerating MT2013 in HK3 per additional_course_rules.csv."""
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


def generate_enrollment_hk231() -> Path:
    """Execute enrollment generation for semester HK231 and export to enrollment_hk231.csv."""
    print(f"=== KHỞI CHẠY SINH DỮ LIỆU ĐĂNG KÝ HỌC PHẦN CHO {SEMESTER} (ĐA KHÓA: K20, K21, K22, K23) ===")

    # 1. Đọc sinh viên 4 khóa
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    k21_students = df_students[df_students["user_id"].str.startswith("21")].copy()
    k22_students = df_students[df_students["user_id"].str.startswith("22")].copy()
    k23_students = df_students[df_students["user_id"].str.startswith("23")].copy()
    print(f"1. Tổng SV: K20: {len(k20_students)} | K21: {len(k21_students)} | K22: {len(k22_students)} | K23: {len(k23_students)}")

    # 2. Đọc danh sách lớp học phần HK231
    classes_file = CLASSES_DIR / "class_hk231.csv"
    if not classes_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file lớp: {classes_file}. Hãy chạy generate_class_hk231.py trước!")
    df_classes = pd.read_csv(classes_file, encoding="utf-8-sig")
    print(f"2. Tổng số lớp học phần đã mở cho HK231: {len(df_classes)} lớp.")

    # 3. Đọc lịch sử học tập các kỳ trước: HK201 -> HK222
    prior_sems = ["hk201", "hk202", "hk211", "hk212", "hk221", "hk222"]
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
            if r["passed"] == True or str(r.get("status", "")).lower() in ["pass", "exempted"]:
                history_passed[sid][cid] = float(gpa4) if (pd.notna(gpa4) and not (pd.notna(score) and float(score) == 12.0)) else 0.0

    # K20 đã học vượt CO4029 ở HK222
    k20_passed_co4029 = {uid for uid in k20_students["user_id"] if "CO4029" in history_passed[uid]}

    # K21 đã học vượt CO2013 ở HK222
    k21_passed_co2013 = {uid for uid in k21_students["user_id"] if "CO2013" in history_passed[uid]}

    # K22 Đại trà đạt LA1005 ở HK222 -> đủ điều kiện học LA1007
    k22_passed_la1005 = {uid for uid in k22_students["user_id"] if "LA1005" in history_passed[uid]}

    # Sinh viên khóa trước còn nợ môn cần học lại
    all_prev_enrollments = pd.concat(prev_dfs)
    retake_demand: Dict[str, List[str]] = defaultdict(list)
    for _, r in all_prev_enrollments[all_prev_enrollments["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        if cid not in history_passed[sid] and sid not in retake_demand[cid]:
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

    profiles_file = USERS_DIR / "student_profiles.csv"
    df_profiles = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    student_profiles: Dict[str, Dict[str, Any]] = df_profiles.set_index("student_id").to_dict(orient="index")

    k22_accel = get_k22_acceleration_students(k22_students, df_profiles)
    k21_group_c = get_k21_group_c_distribution(k21_students)

    k23_compulsory = get_curriculum_for_cohort_semester("K23", 1)["compulsory_courses"]
    k23_core_courses = [c["course_code"] for c in k23_compulsory if not c["course_code"].startswith("LA")]

    k22_compulsory = get_curriculum_for_cohort_semester("K22", 3)["compulsory_courses"]
    k22_core_courses = [c["course_code"] for c in k22_compulsory if not c["course_code"].startswith("LA")]

    k21_compulsory = get_curriculum_for_cohort_semester("K21", 5)["compulsory_courses"]
    k21_core_courses = [c["course_code"] for c in k21_compulsory if c["course_code"] != "CO2013"]

    k20_compulsory = get_curriculum_for_cohort_semester("K20", 7)["compulsory_courses"]
    k20_core_courses = [c["course_code"] for c in k20_compulsory if c["course_code"] != "CO4029"]

    enrollment_records: List[Dict[str, Any]] = []
    enrollment_id = total_past_enrollments + 1

    classes_by_prog_course: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, r in df_classes.iterrows():
        classes_by_prog_course[(r["program"], r["course_code"])].append(r["class_id"])

    # -------------------------------------------------------------------------
    # A. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K23 (HỌC KỲ 1)
    # -------------------------------------------------------------------------
    print("\n4. Đang xử lý đăng ký và điểm cho KHÓA K23 (Học kỳ 1)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k23 = k23_students[k23_students["program"] == prog].copy()
        student_ids = p_k23["user_id"].tolist()
        print(f"\n* K23 hệ {prog} ({len(student_ids)} sinh viên)")

        for course_code in k23_core_courses:
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

        # Môn Tiếng Anh 1 (LA1003) cho K23
        if prog in ("high-quality", "advanced"):
            for eng_course in K23_ENGLISH_COURSES:
                for uid in student_ids:
                    rec = {
                        "enrollment_id": enrollment_id,
                        "student_id": uid,
                        "class_id": np.nan,
                        "course_id": eng_course,
                        "semester": SEMESTER,
                        "retaken": False,
                        "quiz": np.nan,
                        "lab": np.nan,
                        "btl": np.nan,
                        "giua_ky": np.nan,
                        "cuoi_ky": np.nan,
                        "final_score": 12.0,
                        "letter_grade": np.nan,
                        "gpa_4": np.nan,
                        "passed": True,
                        "status": "Exempted",
                    }
                    enrollment_records.append(rec)
                    enrollment_id += 1
        else:
            course_code = "LA1003"
            exempt_uids = [uid for uid in student_ids if is_k23_standard_exempt_la1003(uid)]
            take_uids = [uid for uid in student_ids if uid not in set(exempt_uids)]
            retakers_la1003 = [
                uid for uid in retake_demand.get("LA1003", [])
                if uid in set(df_students[df_students["program"] == "standard"]["user_id"])
            ]

            for uid in exempt_uids:
                rec = {
                    "enrollment_id": enrollment_id,
                    "student_id": uid,
                    "class_id": np.nan,
                    "course_id": course_code,
                    "semester": SEMESTER,
                    "retaken": False,
                    "quiz": np.nan,
                    "lab": np.nan,
                    "btl": np.nan,
                    "giua_ky": np.nan,
                    "cuoi_ky": np.nan,
                    "final_score": 12.0,
                    "letter_grade": np.nan,
                    "gpa_4": np.nan,
                    "passed": True,
                    "status": "Exempted",
                }
                enrollment_records.append(rec)
                enrollment_id += 1

            all_la1003 = take_uids + retakers_la1003
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(all_la1003), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = all_la1003[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    is_retake = uid in set(retakers_la1003)
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

            print(f"   -> Đã gán {len(all_la1003)} SV học LA1003 ({len(class_ids)} lớp) và {len(exempt_uids)} SV miễn.")

    # -------------------------------------------------------------------------
    # B. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K22 (HỌC KỲ 3)
    # -------------------------------------------------------------------------
    print("\n5. Đang xử lý đăng ký và điểm cho KHÓA K22 (Học kỳ 3)...")
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
            is_politics = course_code.startswith("SP")
            max_cap = 120 if is_politics else 40
            sizes = balanced_class_sizes(len(all_assigned_uids), max_size=max_cap)
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

            retake_str = f" (+{len(retakers)} SV học ghép)" if retakers else ""
            print(f"   -> Đã gán {len(all_assigned_uids)} SV{retake_str} vào môn {course_code} ({len(class_ids)} lớp)")

        # LA1007 cho K22 Đại trà
        if prog == "standard":
            course_code = "LA1007"
            k22_take_la1007 = [uid for uid in student_ids if uid in k22_passed_la1005]
            retakers_la1007 = [
                uid for uid in retake_demand.get("LA1007", [])
                if uid in set(df_students[df_students["program"] == "standard"]["user_id"])
            ]
            all_la1007 = k22_take_la1007 + retakers_la1007

            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(all_la1007), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = all_la1007[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    is_retake = uid in set(retakers_la1007)
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

            print(f"   -> Đã gán {len(all_la1007)} SV vào môn LA1007 ({len(class_ids)} lớp)")

        # Môn học vượt K22: MT2013
        accel_uids = k22_accel.get(prog, [])
        if accel_uids:
            course_code = "MT2013"
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

            print(f"   -> [K22 Học vượt] {len(accel_uids)} SV học vượt MT2013 vào {len(class_ids)} lớp.")

    # -------------------------------------------------------------------------
    # C. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K21 (HỌC KỲ 5)
    # -------------------------------------------------------------------------
    print("\n6. Đang xử lý đăng ký và điểm cho KHÓA K21 (Học kỳ 5)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k21 = k21_students[k21_students["program"] == prog].copy()
        student_ids = p_k21["user_id"].tolist()
        print(f"\n* K21 hệ {prog} ({len(student_ids)} sinh viên)")

        for course_code in k21_core_courses:
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            is_politics = course_code.startswith("SP")
            max_cap = 120 if is_politics else 40
            sizes = balanced_class_sizes(len(student_ids), max_size=max_cap)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
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

            print(f"   -> Đã gán {len(student_ids)} SV vào môn {course_code} ({len(class_ids)} lớp)")

        # CO2013 cho K21 (bỏ qua nếu đã học vượt ở HK222)
        k21_co2013_learners = [uid for uid in student_ids if uid not in k21_passed_co2013]
        if k21_co2013_learners:
            course_code = "CO2013"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(k21_co2013_learners), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = k21_co2013_learners[offset : offset + size]
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

            print(f"   -> Đã gán {len(k21_co2013_learners)} SV vào môn CO2013 ({len(class_ids)} lớp, miễn {len(student_ids)-len(k21_co2013_learners)} SV)")

        # Tự chọn Group C cho K21
        if prog == "advanced":
            print(f"   -> [K21 Tự chọn ngành - Group C]: Đã ghép học chung lớp với hệ Chất lượng cao (CC)")
        elif prog == "high-quality":
            print(f"   -> Phân bổ SV vào Tự chọn Nhóm C (Group C - Ghép CLC + Tiên tiến):")
            all_group_c = sorted(list({c for (p, c) in k21_group_c.keys() if p in ("high-quality", "advanced")}))
            for g_course in all_group_c:
                g_uids = k21_group_c.get(("high-quality", g_course), []) + k21_group_c.get(("advanced", g_course), [])
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

                print(f"      * {g_course}: {len(g_uids)} SV (CLC+TT) -> {len(class_ids)} lớp")
        else:
            print(f"   -> Phân bổ SV vào Tự chọn Nhóm C (Group C):")
            all_group_c = sorted(list({c for (p, c) in k21_group_c.keys() if p == prog}))
            for g_course in all_group_c:
                g_uids = k21_group_c.get((prog, g_course), [])
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

    # -------------------------------------------------------------------------
    # D. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K20 (HỌC KỲ 7 - TỐT NGHIỆP SỚM)
    # -------------------------------------------------------------------------
    print("\n7. Đang xử lý đăng ký và điểm cho KHÓA K20 (Học kỳ 7 - Tốt nghiệp sớm 3.5 năm)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k20 = k20_students[k20_students["program"] == prog].copy()
        student_ids = p_k20["user_id"].tolist()
        print(f"\n* K20 hệ {prog} ({len(student_ids)} sinh viên)")

        # SP1039, CO3335
        for course_code in k20_core_courses:
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            is_politics = course_code.startswith("SP")
            max_cap = 120 if is_politics else 40
            sizes = balanced_class_sizes(len(student_ids), max_size=max_cap)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
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

            print(f"   -> Đã gán {len(student_ids)} SV vào môn {course_code} ({len(class_ids)} lớp)")

        # CO4029 (Đồ án chuyên ngành): chỉ SV K20 chưa hoàn thành ở HK222
        k20_co4029_learners = [uid for uid in student_ids if uid not in k20_passed_co4029]
        if k20_co4029_learners:
            course_code = "CO4029"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            # Lọc các lớp chuẩn của K20
            k20_classes = [c for c in class_ids if "Tốt nghiệp sớm" not in c] or class_ids
            sizes = balanced_class_sizes(len(k20_co4029_learners), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(k20_classes, sizes):
                assigned_chunk = k20_co4029_learners[offset : offset + size]
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

            print(f"   -> Đã gán {len(k20_co4029_learners)} SV vào môn CO4029 ({len(k20_classes)} lớp, miễn {len(student_ids)-len(k20_co4029_learners)} SV tốt nghiệp sớm)")

        # Lộ trình tốt nghiệp sớm 3.5 năm: CHỈ DÀNH RIÊNG cho early_graduation_candidate đã hoàn thành CO4029
        early_candidates = [
            uid for uid in student_ids
            if str(student_profiles.get(uid, {}).get("early_graduation_candidate", "")).lower() == "true"
            and uid in k20_passed_co4029
        ]
        if early_candidates:
            for early_code in ["CO4337", "SP1007"]:
                class_ids = classes_by_prog_course.get((prog, early_code), [])
                is_politics = early_code.startswith("SP")
                max_cap = 120 if is_politics else 40
                sizes = balanced_class_sizes(len(early_candidates), max_size=max_cap)
                offset = 0
                comps = course_assessments.get(early_code, [("cuoi_ky", 1.0)])

                for class_id, size in zip(class_ids, sizes):
                    assigned_chunk = early_candidates[offset : offset + size]
                    offset += size

                    for uid in assigned_chunk:
                        profile = student_profiles[uid]
                        student_data = {"student_id": uid, **profile}

                        seed_str = f"{uid}:{early_code}:{SEMESTER}_grad"
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

                print(f"   -> [K20 Tốt nghiệp sớm 3.5 năm] {len(early_candidates)} SV hoàn tất môn {early_code} ({len(class_ids)} lớp).")

        # Tự chọn Group C, Free & Group B cho K20
        if prog == "advanced":
            print(f"   -> [K20 Tự chọn ngành - Group C, Free & B]: Đã ghép học chung lớp với hệ Chất lượng cao (CC)")
        else:
            if prog == "high-quality":
                k20_adv_uids = set(k20_students[k20_students["program"] == "advanced"]["user_id"])
                combined_student_ids = student_ids + [uid for uid in k20_adv_uids if uid not in set(student_ids)]
            else:
                combined_student_ids = student_ids

            regular_k20_uids = combined_student_ids
            if regular_k20_uids:
                spec_map = get_student_specialization_map()
                student_c_choices: Dict[str, List[str]] = defaultdict(list)
                for uid in regular_k20_uids:
                    spec = spec_map.get(uid, "Khoa học Máy tính")
                    prev_passed = set(history_passed[uid].keys())
                    elecs = get_term7_student_electives(uid, "K20", spec, prev_passed)
                    if uid in set(early_candidates):
                        elecs += get_term8_student_electives(uid, "K20", prev_passed | set(elecs))
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
                print(f"   -> [K20 Tự chọn ngành - Group C, Free & B]{suffix_note}: Đã phân bổ {len(regular_k20_uids)} SV vào {len(student_c_choices)} môn học.")

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
    # E. TÍNH GPA HỌC KỲ VÀ TÍCH LŨY
    # -------------------------------------------------------------------------
    print("\n8. Đang tính điểm trung bình học kỳ và GPA tích lũy cho cả 4 khóa (K20, K21, K22, K23)...")
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
    k23_count = len(df_enrollment[df_enrollment["student_id"].str.startswith("23")])
    print(f"- Bản ghi K20 (Học kỳ 7): {k20_count:,} lượt học.")
    print(f"- Bản ghi K21 (Học kỳ 5): {k21_count:,} lượt học.")
    print(f"- Bản ghi K22 (Học kỳ 3): {k22_count:,} lượt học.")
    print(f"- Bản ghi K23 (Học kỳ 1): {k23_count:,} lượt học.")

    pass_count = len(df_enrollment[df_enrollment["passed"] == True])
    fail_count = len(df_enrollment[df_enrollment["passed"] == False])
    print(f"- Tỷ lệ đạt: {pass_count:,} ({pass_count/len(df_enrollment):.1%}) | Rớt: {fail_count:,} ({fail_count/len(df_enrollment):.1%})")

    avg_sem_gpa = df_enrollment.drop_duplicates(subset=["student_id"])["semester_gpa"].mean()
    avg_cum_gpa = df_enrollment.drop_duplicates(subset=["student_id"])["cumulative_gpa"].mean()
    print(f"- GPA trung bình học kỳ {SEMESTER}: {avg_sem_gpa:.2f}/4.0")
    print(f"- GPA tích lũy trung bình toàn trường: {avg_cum_gpa:.2f}/4.0")

    return out_file


if __name__ == "__main__":
    generate_enrollment_hk231()
