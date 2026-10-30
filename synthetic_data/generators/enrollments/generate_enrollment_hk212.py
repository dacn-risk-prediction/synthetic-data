"""Generate enrollment records and course grades for semester HK212.

In this semester, two distinct cohorts attend classes simultaneously:
1. Cohort K20 in Term 4 (Sophomore - Học kỳ 4):
   - Compulsory courses:
     * SP1033: Kinh tế Chính trị Mác - Lênin (2 TC)
     * CO2039: Lập trình Nâng cao (3 TC)
     * CO2017: Hệ điều hành (3 TC)
     * MT2013: Xác suất và Thống kê (4 TC) - chỉ SV K20 chưa hoàn thành ở HK211
     * LA1009: Anh văn 4 (2 TC) - SV Đại trà đã đạt LA1007 ở HK211 (881 SV)
   - Tự chọn Khối Quản lý Kỹ thuật (Group D - 3 TC):
     * IM1013, IM1023, IM1025, IM1027, IM3001
   - Môn học vượt theo additional_course_rules.csv:
     * CO3093: Mạng máy tính (3 TC)
     * CO2013: Hệ cơ sở Dữ liệu (4 TC)
   - Ghép học lại các môn HK2 còn nợ (CO1007, MT1005, MT1007, PH1007, CO1027, LA1005).

2. Cohort K21 in Term 2 (Freshmen - Học kỳ 2):
   - Compulsory courses:
     * CO1007: Cấu trúc Rời rạc cho Khoa học Máy tính (4 TC)
     * MT1005: Giải tích 2 (4 TC)
     * MT1007: Đại số Tuyến tính (3 TC)
     * PH1007: Thí nghiệm Vật lý (1 TC)
     * CO1027: Kỹ thuật Lập trình (3 TC)
     * LA1005: Anh văn 2 (2 TC) - SV Đại trà đã đạt/miễn LA1003 ở HK211 (905 SV)
   - Môn học vượt theo additional_course_rules.csv:
     * CO2001: Kỹ năng Chuyên nghiệp cho Kỹ sư (3 TC) per ADD_CO2001_HK2 (~271 SV)

3. Lớp học lại cho các môn HK1 có số lượng rớt >= 20 sinh viên:
   - MT1003 (27 SV rớt) -> L_HL01
   - CO1005 (24 SV rớt) -> L_HL01
   - CO1023 (23 SV rớt) -> L_HL01
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
    filter_active_students_for_semester,
    is_student_active_for_semester,
    is_thesis_eligible,
    balanced_class_sizes,
    convert_score_to_grade,
    filter_retake_demand_by_credit_limit,
    score_course_components,
)

ANALYSIS_DIR = ROOT_DIR / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from analysis_helpers import get_curriculum_for_cohort_semester

SEMESTER = "HK212"
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


def get_k21_acceleration_students(k21_students: pd.DataFrame, df_prof: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K21 students eligible to accelerate course from additional_course_rules.csv (HK2)."""
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


def get_k20_acceleration_students(
    k20_students: pd.DataFrame, df_prof: pd.DataFrame, k20_passed_mt2013: Set[str]
) -> Dict[str, List[str]]:
    """Identify K20 students eligible to accelerate CO3093 and CO2013 in HK4."""
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")
    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k20_students.iterrows():
        uid = str(row["user_id"])
        prog = row["program"]
        p = prof_by_id.get(uid, {})
        is_early_candidate = str(p.get("early_graduation_candidate", "")).lower() == "true"

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


def generate_enrollment_hk212() -> Path:
    """Execute enrollment generation for semester HK212 and export to enrollment_hk212.csv."""
    print(f"=== KHỞI CHẠY SINH DỮ LIỆU ĐĂNG KÝ HỌC PHẦN (ENROLLMENT) CHO {SEMESTER} (ĐA KHÓA: K20 & K21) ===")

    # 1. Đọc sinh viên K20 và K21
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    k21_students = df_students[df_students["user_id"].str.startswith("21")].copy()
    print(f"1. Tổng số sinh viên K20: {len(k20_students)} SV | K21: {len(k21_students)} SV.")

    # 2. Đọc danh sách lớp học phần HK212
    classes_file = CLASSES_DIR / "class_hk212.csv"
    if not classes_file.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file lớp: {classes_file}. Hãy chạy generate_class_hk212.py trước!"
        )
    df_classes = pd.read_csv(classes_file, encoding="utf-8-sig")
    print(f"2. Tổng số lớp học phần đã mở cho HK212: {len(df_classes)} lớp.")

    # 3. Đọc lịch sử học tập các kỳ trước: HK201, HK202, HK211
    enr_files = [
        OUTPUT_DIR / "enrollment_hk201.csv",
        OUTPUT_DIR / "enrollment_hk202.csv",
        OUTPUT_DIR / "enrollment_hk211.csv",
    ]
    for ef in enr_files:
        if not ef.exists():
            raise FileNotFoundError(f"Thiếu file kết quả học kỳ trước: {ef}. Hãy kiểm tra lại!")

    df_hk201 = pd.read_csv(enr_files[0], encoding="utf-8-sig", dtype={"student_id": str})
    df_hk202 = pd.read_csv(enr_files[1], encoding="utf-8-sig", dtype={"student_id": str})
    df_hk211 = pd.read_csv(enr_files[2], encoding="utf-8-sig", dtype={"student_id": str})

    total_past_enrollments = len(df_hk201) + len(df_hk202) + len(df_hk211)

    # Lịch sử môn đạt của từng sinh viên (để tính GPA tích lũy và kiểm tra điều kiện)
    history_passed: Dict[str, Dict[str, float]] = defaultdict(dict)
    history_enrolled: Dict[str, Set[str]] = defaultdict(set)
    for df_prev in [df_hk201, df_hk202, df_hk211]:
        for _, r in df_prev.iterrows():
            sid = str(r["student_id"])
            cid = str(r["course_id"])
            score = r["final_score"]
            gpa4 = r["gpa_4"]
            history_enrolled[sid].add(cid)
            if r["passed"] == True or str(r.get("status", "")).lower() in ["pass", "exempted"]:
                history_passed[sid][cid] = float(gpa4) if (pd.notna(gpa4) and not (pd.notna(score) and float(score) == 12.0)) else 0.0

    # K20 đã học và đạt MT2013 ở HK211
    k20_passed_mt2013 = set(
        df_hk211[(df_hk211["course_id"] == "MT2013") & (df_hk211["passed"] == True)]["student_id"].tolist()
    )

    # K20 Đại trà đạt LA1007 ở HK211 -> đủ điều kiện học LA1009
    k20_passed_la1007 = set(
        df_hk211[(df_hk211["course_id"] == "LA1007") & (df_hk211["passed"] == True)]["student_id"].tolist()
    )

    # K21 Đại trà đạt/miễn LA1003 ở HK211 -> đủ điều kiện học LA1005
    k21_passed_la1003 = set(
        df_hk211[(df_hk211["course_id"] == "LA1003") & (df_hk211["passed"] == True)]["student_id"].tolist()
    )

    # K20 còn nợ môn HK2 cần học lại
    k20_failed_hk2: Dict[str, List[str]] = defaultdict(list)
    for _, r in df_hk202[df_hk202["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        if cid not in history_passed[sid]:
            k20_failed_hk2[cid].append(sid)

    # Môn HK1 rớt cần học lại (ngưỡng >= 20)
    hk1_candidates = ["MT1003", "CO1005", "CO1023"]
    hk1_retake_students: Dict[str, List[str]] = {}
    for c in hk1_candidates:
        failed_records = pd.concat([
            df_hk211[(df_hk211["course_id"] == c) & (df_hk211["passed"] == False)],
            df_hk202[(df_hk202["course_id"] == c) & (df_hk202["passed"] == False)] if "course_id" in df_hk202 else pd.DataFrame(),
        ])
        unresolved = [
            sid for sid in failed_records["student_id"].unique()
            if c not in history_passed[sid]
        ]
        if len(unresolved) >= 20:
            hk1_retake_students[c] = unresolved

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

    # Ràng buộc trần tín chỉ: Lọc môn học lại để không vượt quá trần tín chỉ học kỳ
    creds_tracker: Dict[str, float] = defaultdict(float)
    count_tracker: Dict[str, int] = defaultdict(int)
    k20_failed_hk2 = filter_retake_demand_by_credit_limit(
        k20_failed_hk2, credits_map, SEMESTER,
        student_assigned_creds=creds_tracker, student_assigned_count=count_tracker
    )
    hk1_retake_students = filter_retake_demand_by_credit_limit(
        hk1_retake_students, credits_map, SEMESTER,
        student_assigned_creds=creds_tracker, student_assigned_count=count_tracker
    )

    # 6. Đọc hồ sơ năng lực học tập cố định (student_profiles.csv)
    profiles_file = USERS_DIR / "student_profiles.csv"
    df_profiles = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    student_profiles: Dict[str, Dict[str, Any]] = df_profiles.set_index("student_id").to_dict(
        orient="index"
    )

    # Lọc sinh viên còn hoạt động (loại bỏ voluntary_dropout và academic_dismissal)
    k20_students = filter_active_students_for_semester(k20_students, SEMESTER, df_profiles)
    k21_students = filter_active_students_for_semester(k21_students, SEMESTER, df_profiles)

    # 7. Danh sách học vượt và tự chọn
    k21_accel = get_k21_acceleration_students(k21_students, df_profiles)
    k20_accel = get_k20_acceleration_students(k20_students, df_profiles, k20_passed_mt2013)
    k20_group_d = get_k20_group_d_distribution(k20_students)

    # Đọc danh mục môn học trực tiếp từ CTĐT của K21 (HK2) và K20 (HK4)
    k21_compulsory = get_curriculum_for_cohort_semester("K21", 2)["compulsory_courses"]
    k21_core_courses = [c["course_code"] for c in k21_compulsory if not c["course_code"].startswith("LA")]

    k20_compulsory = get_curriculum_for_cohort_semester("K20", 4)["compulsory_courses"]
    k20_core_courses = [c["course_code"] for c in k20_compulsory if not c["course_code"].startswith("LA") and c["course_code"] != "MT2013"]

    enrollment_records: List[Dict[str, Any]] = []
    enrollment_id = total_past_enrollments + 1

    # Map classes by (program, course_code)
    classes_by_prog_course: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, r in df_classes.iterrows():
        classes_by_prog_course[(r["program"], r["course_code"])].append(r["class_id"])

    # -------------------------------------------------------------------------
    # 8. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K21 (HỌC KỲ 2)
    # -------------------------------------------------------------------------
    print("\n4. Đang xử lý đăng ký và điểm cho KHÓA K21 (Học kỳ 2)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k21 = k21_students[k21_students["program"] == prog].copy()
        student_ids = p_k21["user_id"].tolist()
        print(f"\n* K21 hệ {prog} ({len(student_ids)} sinh viên)")

        # Các môn bắt buộc chung HK2 theo CTĐT K21
        for course_code in k21_core_courses:
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            # Gom cả sinh viên K20 học lại môn này (nếu có)
            k20_retake_uids = [
                uid for uid in k20_failed_hk2.get(course_code, [])
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

            retake_info = f" (+{len(k20_retake_uids)} K20 học ghép)" if k20_retake_uids else ""
            print(f"   -> Đã gán {len(all_assigned_uids)} SV{retake_info} vào môn {course_code} ({len(class_ids)} lớp)")

        # Môn Tiếng Anh 2 (LA1005):
        # Hệ CLC và Tiên tiến đã được miễn toàn bộ từ HK1 (HK211)
        # Hệ Đại trà: những SV đã đạt/miễn LA1003 ở HK211 + K20 học lại LA1005
        if prog == "standard":
            course_code = "LA1005"
            k21_take_la1005 = [uid for uid in student_ids if uid in k21_passed_la1003]
            k20_retake_la1005 = [
                uid for uid in k20_failed_hk2.get("LA1005", [])
                if uid in set(k20_students[k20_students["program"] == "standard"]["user_id"])
            ]
            all_la1005_learners = k21_take_la1005 + k20_retake_la1005

            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(all_la1005_learners), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = all_la1005_learners[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    is_retake = uid in set(k20_retake_la1005)
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

            retake_la_str = f" (+{len(k20_retake_la1005)} K20 học ghép)" if k20_retake_la1005 else ""
            print(f"   -> Đã gán {len(all_la1005_learners)} SV{retake_la_str} vào môn LA1005 ({len(class_ids)} lớp)")

        # Môn học vượt K21 theo additional_course_rules.csv (ví dụ CH1003 hoặc CO2001 theo priority)
        accel_uids = k21_accel.get(prog, [])
        if accel_uids:
            course_code, _ = get_top_acceleration_course_for_term("HK2")
            # Lớp học vượt của hệ này
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

            print(f"   -> [K21 Học vượt] {len(accel_uids)} SV học vượt {course_code} vào {len(class_ids)} lớp.")

    # -------------------------------------------------------------------------
    # 9. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K20 (HỌC KỲ 4)
    # -------------------------------------------------------------------------
    print("\n5. Đang xử lý đăng ký và điểm cho KHÓA K20 (Học kỳ 4)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k20 = k20_students[k20_students["program"] == prog].copy()
        student_ids = p_k20["user_id"].tolist()
        print(f"\n* K20 hệ {prog} ({len(student_ids)} sinh viên)")

        # A. Các môn bắt buộc chung HK4: SP1033, CO2039, CO2017
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

            print(f"   -> Đã gán {len(student_ids)} SV vào môn {course_code} ({len(class_ids)} lớp)")

        # B. Môn MT2013 (Xác suất & Thống kê): chỉ dành cho SV CHƯA hoàn thành ở HK211
        k20_mt2013_learners = [uid for uid in student_ids if uid not in k20_passed_mt2013]
        if k20_mt2013_learners:
            course_code = "MT2013"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(k20_mt2013_learners), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = k20_mt2013_learners[offset : offset + size]
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

            print(f"   -> Đã gán {len(k20_mt2013_learners)} SV vào môn MT2013 ({len(class_ids)} lớp, miễn {len(student_ids) - len(k20_mt2013_learners)} SV đã học sớm)")

        # C. Môn Tiếng Anh 4 (LA1009): chỉ dành cho SV Đại trà đã đạt LA1007
        if prog == "standard":
            course_code = "LA1009"
            k20_take_la1009 = [uid for uid in student_ids if uid in k20_passed_la1007]
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(k20_take_la1009), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = k20_take_la1009[offset : offset + size]
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

            print(f"   -> Đã gán {len(k20_take_la1009)} SV vào môn LA1009 ({len(class_ids)} lớp)")

        # D. Tự chọn Quản lý Kỹ thuật (Group D): mỗi SV chọn 1 trong 5 môn
        print(f"   -> Phân bổ SV vào Tự chọn Quản lý Kỹ thuật (Group D):")
        for g_course in GROUP_D_COURSES:
            g_uids = k20_group_d.get((prog, g_course), [])
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
                    rng = np.random.default_rng(
                        int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
                    )

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

        # E. Môn học vượt K20: CO3093 (Mạng máy tính) và CO2013 (Hệ cơ sở Dữ liệu)
        accel_k20_prog = k20_accel.get(prog, [])
        if accel_k20_prog:
            for accel_code in ["CO3093", "CO2013"]:
                class_ids = classes_by_prog_course.get((prog, accel_code), [])
                sizes = balanced_class_sizes(len(accel_k20_prog), max_size=40)
                offset = 0
                comps = course_assessments.get(accel_code, [("cuoi_ky", 1.0)])

                for class_id, size in zip(class_ids, sizes):
                    assigned_chunk = accel_k20_prog[offset : offset + size]
                    offset += size

                    for uid in assigned_chunk:
                        profile = student_profiles[uid]
                        student_data = {"student_id": uid, **profile}

                        seed_str = f"{uid}:{accel_code}:{SEMESTER}_accel"
                        rng = np.random.default_rng(
                            int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
                        )

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

                print(f"   -> [K20 Học vượt] {len(accel_k20_prog)} SV học vượt {accel_code} vào {len(class_ids)} lớp.")

    # -------------------------------------------------------------------------
    # 10. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO LỚP HỌC LẠI CÁC MÔN HK1
    # -------------------------------------------------------------------------
    print("\n6. Đang xử lý đăng ký cho các LỚP HỌC LẠI MÔN HK1 (Nhu cầu >= 20 SV)...")
    for retake_code, uids in hk1_retake_students.items():
        class_ids = classes_by_prog_course.get(("standard", retake_code), [])
        # Lọc ra lớp có mã L_HL
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
                rng = np.random.default_rng(
                    int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
                )

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
    # 11. TÍNH GPA HỌC KỲ VÀ TÍCH LŨY (PHÂN TÁCH K21 VÀ K20)
    # -------------------------------------------------------------------------
    print("\n7. Đang tính điểm trung bình học kỳ và GPA tích lũy cho cả K20 và K21...")
    # Chuẩn hóa cờ retaken dựa trên lịch sử
    for r in enrollment_records:
        if r.get("status") != "Exempted" and str(r.get("course_id")) in history_enrolled.get(str(r.get("student_id")), set()):
            r["retaken"] = True

    df_enrollment = pd.DataFrame(enrollment_records)

    semester_gpas: Dict[str, float] = {}
    final_gpas: Dict[str, float] = {}

    for uid, attempts in df_enrollment.groupby("student_id"):
        # GPA của học kỳ HK212
        hk4_points = 0.0
        hk4_credits = 0.0
        for _, att in attempts.iterrows():
            score = att["final_score"]
            gpa4 = att["gpa_4"]
            if pd.isna(score) or float(score) == 12.0 or pd.isna(gpa4):
                continue
            tc = credits_map.get(att["course_id"], 0.0)
            hk4_points += float(gpa4) * tc
            hk4_credits += tc

        semester_gpas[uid] = (
            round(hk4_points / hk4_credits, 2) if hk4_credits > 0 else np.nan
        )

        # GPA tích lũy: lấy tất cả các môn đã đạt từ các kỳ trước + kỳ hiện tại
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

    # 12. Xuất file CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"enrollment_{SEMESTER.lower()}.csv"
    df_enrollment.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số bản ghi đăng ký trong {SEMESTER}: {len(df_enrollment):,} dòng.")

    k20_count = len(df_enrollment[df_enrollment["student_id"].str.startswith("20")])
    k21_count = len(df_enrollment[df_enrollment["student_id"].str.startswith("21")])
    print(f"- Bản ghi K20 (Học kỳ 4): {k20_count:,} lượt học.")
    print(f"- Bản ghi K21 (Học kỳ 2): {k21_count:,} lượt học.")

    pass_count = len(df_enrollment[df_enrollment["passed"] == True])
    fail_count = len(df_enrollment[df_enrollment["passed"] == False])
    print(f"- Tỷ lệ đạt: {pass_count:,} ({pass_count/len(df_enrollment):.1%}) | Rớt: {fail_count:,} ({fail_count/len(df_enrollment):.1%})")

    avg_sem_gpa = df_enrollment.drop_duplicates(subset=["student_id"])["semester_gpa"].mean()
    avg_cum_gpa = df_enrollment.drop_duplicates(subset=["student_id"])["cumulative_gpa"].mean()
    print(f"- GPA trung bình học kỳ {SEMESTER}: {avg_sem_gpa:.2f}/4.0")
    print(f"- GPA tích lũy trung bình toàn trường: {avg_cum_gpa:.2f}/4.0")

    return out_file


if __name__ == "__main__":
    generate_enrollment_hk212()

