"""Generate student course enrollments and academic grades for semester HK211 (Multi-cohort: K20 Term 3 & K21 Term 1).

Complies with HCMUT academic credit regulations:
1. Cohort K21 (Freshmen - HK1):
   - High-quality and Advanced students are granted 4 English exemptions (LA1003..LA1009, score 12.0).
   - Standard students: ~25% exempt from LA1003 (score 12.0), remaining ~75% enroll normally.
   - All K21 students enroll in 4 compulsory courses: MT1003, PH1003, CO1005, CO1023.
2. Cohort K20 (Sophomores - HK3):
   - Enrolls in compulsory courses: CO2011, SP1031 (Politics lecture hall), CO2003, CO2007.
   - Eligible Standard students who passed LA1005 enroll in LA1007 (English 3).
   - Eligible students accelerate MT2013 (Xác suất & Thống kê, 4 credits per additional_course_rules.csv).
   - Retake enrollments for K20 students repeating HK1 courses with K21 sections.
3. Accurate cumulative GPA (final_gpa_4):
   - K21: GPA of Term 1.
   - K20: Cumulative GPA aggregated across all 3 terms: HK201 + HK202 + HK211.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

# Paths
ROOT_DIR = Path(__file__).resolve().parents[2]
ACADEMICS_DIR = ROOT_DIR / "generated" / "academics"
USERS_DIR = ROOT_DIR / "generated" / "users"
CLASSES_DIR = ROOT_DIR / "generated" / "classes"
OUTPUT_DIR = ROOT_DIR / "generated" / "enrollments"
CONFIG_FILE = ROOT_DIR / "config" / "generator_config.json"

# Import academic rules
RULES_DIR = ROOT_DIR / "rules"
if str(RULES_DIR) not in sys.path:
    sys.path.insert(0, str(RULES_DIR))

from academic_rules import (
    GENERATOR_CONFIG,
    balanced_class_sizes,
    convert_score_to_grade,
    score_course_components,
)

# Add analysis directory to import academic engine helpers
ANALYSIS_DIR = ROOT_DIR / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from analysis_helpers import get_curriculum_for_cohort_semester

SEMESTER = "HK211"
K21_ENGLISH_COURSES = ["LA1003", "LA1005", "LA1007", "LA1009"]


def is_k21_standard_exempt_la1003(student_id: str) -> bool:
    """Determine whether a K21 Standard freshman qualifies for LA1003 exemption."""
    digest = hashlib.sha256(f"{student_id}:la1003_placement".encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    return (seed % 100) < 25


def get_k20_acceleration_students(k20_students: pd.DataFrame, df_prof: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K20 students taking accelerated course MT2013."""
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

        if is_early_candidate or (base_score >= 7.8 and prob < 35):
            accelerating_by_prog[prog].append(uid)

    return accelerating_by_prog


def generate_enrollment_hk211() -> Path:
    """Execute enrollment generation for semester HK211 and export to enrollment_hk211.csv."""
    print(f"=== KHỞI CHẠY SINH DỮ LIỆU ĐĂNG KÝ HỌC PHẦN (ENROLLMENT) CHO {SEMESTER} (ĐA KHÓA: K20 & K21) ===")

    # 1. Đọc sinh viên K20 và K21
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    k21_students = df_students[df_students["user_id"].str.startswith("21")].copy()
    print(f"1. Tổng số sinh viên K20: {len(k20_students)} SV | K21: {len(k21_students)} SV.")

    # 2. Đọc danh sách lớp học phần HK211
    classes_file = CLASSES_DIR / "class_hk211.csv"
    if not classes_file.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file lớp: {classes_file}. Hãy chạy generate_class_hk211.py trước!"
        )
    df_classes = pd.read_csv(classes_file, encoding="utf-8-sig")
    print(f"2. Tổng số lớp học phần đã mở cho HK211: {len(df_classes)} lớp.")

    # 3. Đọc lịch sử học tập HK201 và HK202 của K20
    enr_hk201_file = OUTPUT_DIR / "enrollment_hk201.csv"
    enr_hk202_file = OUTPUT_DIR / "enrollment_hk202.csv"
    if not enr_hk201_file.exists() or not enr_hk202_file.exists():
        raise FileNotFoundError("Thiếu dữ liệu học kỳ trước (HK201 hoặc HK202). Hãy kiểm tra lại!")

    df_hk201 = pd.read_csv(enr_hk201_file, encoding="utf-8-sig", dtype={"student_id": str})
    df_hk202 = pd.read_csv(enr_hk202_file, encoding="utf-8-sig", dtype={"student_id": str})

    # Lịch sử các môn đạt của K20 từ HK201 và HK202
    k20_history_passed: Dict[str, Dict[str, float]] = defaultdict(dict)
    for df_prev in [df_hk201, df_hk202]:
        for _, r in df_prev.iterrows():
            sid = str(r["student_id"])
            cid = str(r["course_id"])
            score = r["final_score"]
            gpa4 = r["gpa_4"]
            if r["passed"] == True or str(r.get("status", "")).lower() in ["pass", "exempted"]:
                k20_history_passed[sid][cid] = float(gpa4) if (pd.notna(gpa4) and not (pd.notna(score) and float(score) == 12.0)) else 0.0

    # Sinh viên K20 đủ điều kiện học LA1007 (đạt LA1005 ở HK202)
    k20_la1005_passed = set(
        df_hk202[
            (df_hk202["course_id"] == "LA1005") & (df_hk202["passed"] == True)
        ]["student_id"].tolist()
    )

    # Sinh viên K20 còn nợ môn HK1 cần học lại
    k20_failed_hk1: Dict[str, List[str]] = defaultdict(list)
    for _, r in df_hk201[df_hk201["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        # Nếu ở HK202 chưa học lại hoặc chưa đạt
        if cid not in k20_history_passed[sid]:
            k20_failed_hk1[cid].append(sid)

    # 4. Đọc cấu trúc đánh giá môn học (assessment.csv)
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

    # 5. Đọc số tín chỉ môn học (courses.csv)
    courses_file = ACADEMICS_DIR / "courses.csv"
    df_courses = pd.read_csv(courses_file, encoding="utf-8-sig")
    credits_map: Dict[str, float] = dict(
        zip(df_courses["course_code"], df_courses["credits"].astype(float))
    )

    # 6. Đọc hồ sơ năng lực học tập cố định (student_profiles.csv)
    profiles_file = USERS_DIR / "student_profiles.csv"
    df_profiles = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    student_profiles: Dict[str, Dict[str, Any]] = df_profiles.set_index("student_id").to_dict(
        orient="index"
    )

    # 7. Danh sách K20 học vượt MT2013
    k20_accel = get_k20_acceleration_students(k20_students, df_profiles)
    total_accel = sum(len(uids) for uids in k20_accel.values())
    print(f"3. K20 đủ điều kiện học LA1007: {len(k20_la1005_passed)} SV | K20 học vượt MT2013: {total_accel} SV.")

    # Đọc danh mục môn học trực tiếp từ CTĐT của K21 (HK1) và K20 (HK3)
    k21_compulsory = get_curriculum_for_cohort_semester("K21", 1)["compulsory_courses"]
    k21_core_courses = [c["course_code"] for c in k21_compulsory if not c["course_code"].startswith("LA")]

    k20_compulsory = get_curriculum_for_cohort_semester("K20", 3)["compulsory_courses"]
    k20_core_courses = [c["course_code"] for c in k20_compulsory if not c["course_code"].startswith("LA")]

    enrollment_records: List[Dict[str, Any]] = []
    enrollment_id = len(df_hk201) + len(df_hk202) + 1

    # Map classes by (program, course_code)
    classes_by_prog_course: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, r in df_classes.iterrows():
        classes_by_prog_course[(r["program"], r["course_code"])].append(r["class_id"])

    # -------------------------------------------------------------------------
    # 8. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K21 (HỌC KỲ 1)
    # -------------------------------------------------------------------------
    print("\n4. Đang xử lý đăng ký và điểm cho KHÓA K21 (Học kỳ 1)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k21 = k21_students[k21_students["program"] == prog].copy()
        student_ids = p_k21["user_id"].tolist()
        print(f"\n* K21 hệ {prog} ({len(student_ids)} sinh viên)")

        # Các môn bắt buộc chung HK1 theo CTĐT K21
        for course_code in k21_core_courses:
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            # Gom cả sinh viên K20 học lại môn này (nếu có)
            k20_retake_uids = [
                uid for uid in k20_failed_hk1.get(course_code, [])
                if uid in set(k20_students[k20_students["program"] == prog]["user_id"])
            ]
            all_assigned_uids = student_ids + k20_retake_uids

            sizes = balanced_class_sizes(len(all_assigned_uids), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = all_assigned_uids[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    is_retake = uid in set(k20_retake_uids)
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{course_code}:{SEMESTER}"
                    rng = np.random.default_rng(
                        int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
                    )

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

        # Môn Tiếng Anh cho K21
        if prog in ("high-quality", "advanced"):
            # CLC và Tiên tiến: Miễn luôn 4 học phần tiếng Anh ngay từ HK1
            for eng_course in K21_ENGLISH_COURSES:
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
            # Hệ Đại trà K21
            course_code = "LA1003"
            exempt_uids = [uid for uid in student_ids if is_k21_standard_exempt_la1003(uid)]
            take_uids = [uid for uid in student_ids if uid not in set(exempt_uids)]
            # K20 học lại LA1003
            k20_retake_la1003 = [
                uid for uid in k20_failed_hk1.get("LA1003", [])
                if uid in set(k20_students[k20_students["program"] == "standard"]["user_id"])
            ]

            # Bản ghi miễn LA1003 (điểm 12)
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

            # Lớp học thường + học ghép K20
            all_la1003_learners = take_uids + k20_retake_la1003
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(all_la1003_learners), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = all_la1003_learners[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    is_retake = uid in set(k20_retake_la1003)
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{course_code}:{SEMESTER}"
                    rng = np.random.default_rng(
                        int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
                    )

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

    # -------------------------------------------------------------------------
    # 9. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K20 (HỌC KỲ 3)
    # -------------------------------------------------------------------------
    print("\n5. Đang xử lý đăng ký và điểm cho KHÓA K20 (Học kỳ 3)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k20 = k20_students[k20_students["program"] == prog].copy()
        student_ids = p_k20["user_id"].tolist()
        print(f"\n* K20 hệ {prog} ({len(student_ids)} sinh viên)")

        # Các môn bắt buộc chung HK3 theo CTĐT K20
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
                    rng = np.random.default_rng(
                        int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
                    )

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

        # Môn Anh văn 3 (LA1007) - Chỉ áp dụng cho hệ Đại trà đủ điều kiện
        if prog == "standard":
            course_code = "LA1007"
            eligible_uids = [uid for uid in student_ids if uid in k20_la1005_passed]
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(eligible_uids), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = eligible_uids[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{course_code}:{SEMESTER}"
                    rng = np.random.default_rng(
                        int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
                    )

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

            print(f"   -> [K20 Đại trà] {len(eligible_uids)} SV học LA1007 vào {len(class_ids)} lớp.")

        # Môn học vượt MT2013 (Xác suất & Thống kê per additional_course_rules.csv)
        accel_uids = k20_accel.get(prog, [])
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
                    rng = np.random.default_rng(
                        int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
                    )

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

            print(f"   -> [K20 Học vượt] {len(accel_uids)} SV học vượt MT2013 vào {len(class_ids)} lớp.")

    # -------------------------------------------------------------------------
    # 10. TÍNH GPA HỌC KỲ VÀ TÍCH LŨY (PHÂN TÁCH K21 VÀ K20)
    # -------------------------------------------------------------------------
    print("\n6. Đang tính điểm trung bình học kỳ và GPA tích lũy cho cả K20 và K21...")
    df_enrollment = pd.DataFrame(enrollment_records)

    semester_gpas: Dict[str, float] = {}
    final_gpas: Dict[str, float] = {}

    for uid, attempts in df_enrollment.groupby("student_id"):
        # GPA của học kỳ HK211
        hk3_points = 0.0
        hk3_credits = 0.0
        for _, att in attempts.iterrows():
            score = att["final_score"]
            gpa4 = att["gpa_4"]
            if pd.isna(score) or float(score) == 12.0 or pd.isna(gpa4):
                continue
            tc = credits_map.get(att["course_id"], 0.0)
            hk3_points += float(gpa4) * tc
            hk3_credits += tc

        semester_gpas[uid] = (
            round(hk3_points / hk3_credits, 2) if hk3_credits > 0 else np.nan
        )

        # GPA tích lũy
        if str(uid).startswith("21"):
            # Sinh viên K21: GPA tích lũy = GPA kỳ 1
            passed_points = 0.0
            passed_credits = 0.0
            for _, att in attempts.iterrows():
                if att["passed"] and pd.notna(att["gpa_4"]) and float(att["final_score"]) != 12.0:
                    tc = credits_map.get(att["course_id"], 0.0)
                    passed_points += float(att["gpa_4"]) * tc
                    passed_credits += tc
            final_gpas[uid] = (
                round(passed_points / passed_credits, 2) if passed_credits > 0 else np.nan
            )
        else:
            # Sinh viên K20: GPA tích lũy gồm các môn đạt HK201 + HK202 + HK211
            all_passed = dict(k20_history_passed[uid])
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
            final_gpas[uid] = (
                round(tot_pts / tot_creds, 2) if tot_creds > 0 else np.nan
            )

    df_enrollment["semester_gpa_4"] = df_enrollment["student_id"].map(semester_gpas)
    df_enrollment["final_gpa_4"] = df_enrollment["student_id"].map(final_gpas)

    # 11. Sắp xếp thứ tự cột chuẩn hóa
    base_cols = [
        "enrollment_id",
        "student_id",
        "class_id",
        "course_id",
        "semester",
        "retaken",
    ]
    comp_cols = ["quiz", "lab", "btl", "giua_ky", "cuoi_ky"]
    end_cols = [
        "final_score",
        "letter_grade",
        "gpa_4",
        "passed",
        "semester_gpa_4",
        "final_gpa_4",
        "status",
    ]
    df_enrollment = df_enrollment[base_cols + comp_cols + end_cols]

    # 12. Xuất file CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"enrollment_{SEMESTER.lower()}.csv"
    df_enrollment.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số bản ghi đăng ký & điểm HK211 (Cả K20 và K21): {len(df_enrollment):,} dòng")

    print("\nThống kê theo trạng thái hoàn thành học phần:")
    print(df_enrollment["status"].value_counts())

    print("\nThống kê số lượng sinh viên K20 học vượt MT2013:")
    mt2013_enrs = df_enrollment[df_enrollment["course_id"] == "MT2013"]
    print(f"Tổng số sinh viên học vượt MT2013: {len(mt2013_enrs)}")

    return out_file


if __name__ == "__main__":
    generate_enrollment_hk211()

