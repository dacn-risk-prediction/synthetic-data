"""Generate enrollment records and course grades for semester HK232.

In this semester, four distinct cohorts attend classes simultaneously:
1. Cohort K23 in Term 2 (Freshmen - Học kỳ 2):
   - Compulsory courses: CO1007, MT1005, MT1007, PH1007, CO1027, LA1005, PE1005 (0 TC), MI1003 (0 TC)
   - Accelerated: CH1003 (Hóa đại cương per additional_course_rules.csv priority 15)
   - K22, K21, K20 retakers join regular classes for HK2 courses

2. Cohort K22 in Term 4 (Sophomore - Năm 2):
   - Compulsory courses: SP1033, CO2039, CO2017, LA1009,
     MT2013 (bỏ qua nếu đã hoàn thành ở HK231)
   - Tự chọn Khối Quản lý Kỹ thuật (Group D): IM1013, IM1023, IM1025, IM1027, IM3001
   - Accelerated: CO3093 (Mạng máy tính) & CO2013 (Hệ cơ sở Dữ liệu)
   - K21, K20 retakers join regular classes for HK4 courses

3. Cohort K21 in Term 6 (Junior - Năm 3):
   - Compulsory courses: CH1003, SP1037, CO3093 (bỏ qua nếu đã hoàn thành ở các kỳ trước)
   - Lộ trình tốt nghiệp sớm 3.5 năm: CO3061 (Nhập môn AI) & CO4029 (Đồ án Chuyên ngành)
   - Tự chọn ngành Group C cho sinh viên còn lại: chọn 2 môn

4. Cohort K20 in Term 8 (Senior - Năm 4 - Tốt nghiệp chuẩn 4 năm):
   - 242 sinh viên tốt nghiệp sớm 3.5 năm đã hoàn tất CO4337 và SP1007 ở HK231 và ĐÃ TỐT NGHIỆP (không học HK232).
   - 1,258 sinh viên K20 còn lại hoàn tất tốt nghiệp chuẩn 4 năm:
     * CO4337: Đồ án Tốt nghiệp (4 TC)
     * SP1007: Pháp luật Việt Nam Đại cương (2 TC)

5. Lớp học lại cho các môn HK1/lẻ có số lượng rớt >= 20 sinh viên:
   - MT1003, PH1003, CO1005, CO1023, CO2011, CO2003, CO2007, SP1031 -> Lớp L_HL
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

from curriculum_rules import select_student_group_c_course, get_student_specialization_map

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

SEMESTER = "HK232"
GROUP_D_COURSES = ["IM1013", "IM1023", "IM1025", "IM1027", "IM3001"]
GROUP_C_COURSES = ["CO3061", "CO3029", "CO3043", "CO3045", "CO3021", "CO3011"]


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


def get_k23_acceleration_students(k23_students: pd.DataFrame, df_prof: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K23 students eligible to accelerate CH1003 (HK2)."""
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


def get_k22_acceleration_students(
    k22_students: pd.DataFrame, df_prof: pd.DataFrame, k22_passed_mt2013: Set[str]
) -> Dict[str, List[str]]:
    """Identify K22 students eligible to accelerate CO3093 and CO2013 in HK4."""
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


def generate_enrollment_hk232() -> Path:
    """Execute enrollment generation for semester HK232 and export to enrollment_hk232.csv."""
    print(f"=== KHỞI CHẠY SINH DỮ LIỆU ĐĂNG KÝ HỌC PHẦN CHO {SEMESTER} (ĐA KHÓA: K20, K21, K22, K23) ===")

    # 1. Đọc sinh viên K20, K21, K22, K23
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    k21_students = df_students[df_students["user_id"].str.startswith("21")].copy()
    k22_students = df_students[df_students["user_id"].str.startswith("22")].copy()
    k23_students = df_students[df_students["user_id"].str.startswith("23")].copy()
    print(f"1. Tổng SV: K20: {len(k20_students)} | K21: {len(k21_students)} | K22: {len(k22_students)} | K23: {len(k23_students)}")

    # 2. Đọc bảng lớp học HK232
    classes_file = CLASSES_DIR / f"class_{SEMESTER.lower()}.csv"
    if not classes_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file lớp học: {classes_file}")
    df_classes = pd.read_csv(classes_file, encoding="utf-8-sig")
    print(f"2. Tổng số lớp học phần đã mở cho {SEMESTER}: {len(df_classes)} lớp.")

    classes_by_prog_course: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, row in df_classes.iterrows():
        classes_by_prog_course[(str(row["program"]), str(row["course_code"]))].append(str(row["class_id"]))

    # 3. Đọc thông tin cấu trúc điểm và hồ sơ sinh viên
    assessment_file = ACADEMICS_DIR / "assessment.csv"
    df_assess = pd.read_csv(assessment_file, encoding="utf-8-sig")
    component_columns = ["quiz", "lab", "btl", "giua_ky", "cuoi_ky"]
    course_assessments: Dict[str, List[Tuple[str, float]]] = {}
    for _, row in df_assess.iterrows():
        c_code = str(row["course_id"])
        comps = []
        for col in component_columns:
            if col in df_assess.columns:
                val = row[col]
                if pd.notna(val) and float(val) > 0:
                    comps.append((col, float(val) / 100.0))
        course_assessments[c_code] = comps

    courses_file = ACADEMICS_DIR / "courses.csv"
    df_courses = pd.read_csv(courses_file, encoding="utf-8-sig")
    credits_map: Dict[str, float] = dict(zip(df_courses["course_code"], df_courses["credits"].astype(float)))

    profiles_file = USERS_DIR / "student_profiles.csv"
    df_prof = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    student_profiles = df_prof.set_index("student_id").to_dict(orient="index")

    # Đọc lịch sử đã học
    passed_map: Dict[str, Set[str]] = defaultdict(set)
    all_prev_enrollments: List[pd.DataFrame] = []
    for sem in ["hk201", "hk202", "hk211", "hk212", "hk221", "hk222", "hk231"]:
        enr_file = OUTPUT_DIR / f"enrollment_{sem}.csv"
        if enr_file.exists():
            df_enr = pd.read_csv(enr_file, encoding="utf-8-sig", dtype={"student_id": str})
            all_prev_enrollments.append(df_enr)
            for _, r in df_enr[df_enr["passed"] == True].iterrows():
                passed_map[str(r["student_id"])].add(str(r["course_id"]))

    # Xác định K20 đã tốt nghiệp sớm ở HK231
    k20_graduated_uids = {uid for uid in k20_students["user_id"] if "CO4337" in passed_map[uid] and "SP1007" in passed_map[uid]}
    k20_active_students = k20_students[~k20_students["user_id"].isin(k20_graduated_uids)].copy()
    print(f"   K20 tốt nghiệp sớm sau HK231: {len(k20_graduated_uids)} SV -> K20 còn lại học HK232 (Học kỳ 8): {len(k20_active_students)} SV.")

    # Xác định môn đã hoàn thành sớm
    k21_passed_ch1003 = {uid for uid in k21_students["user_id"] if "CH1003" in passed_map[uid]}
    k21_passed_co3093 = {uid for uid in k21_students["user_id"] if "CO3093" in passed_map[uid]}
    k22_passed_mt2013 = {uid for uid in k22_students["user_id"] if "MT2013" in passed_map[uid]}
    k22_passed_la1007 = {uid for uid in k22_students["user_id"] if "LA1007" in passed_map[uid]}
    k23_passed_la1003 = {uid for uid in k23_students["user_id"] if "LA1003" in passed_map[uid]}

    # Sinh viên nợ môn
    df_all_prev = pd.concat(all_prev_enrollments)
    retake_demand: Dict[str, List[str]] = defaultdict(list)
    for _, r in df_all_prev[df_all_prev["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        if cid not in passed_map[sid] and sid not in retake_demand[cid]:
            retake_demand[cid].append(sid)

    # Lớp học lại môn HK1/lẻ
    hk1_candidates = ["MT1003", "PH1003", "CO1005", "CO1023", "CO2011", "CO2003", "CO2007", "SP1031"]
    hk1_retake_students: Dict[str, List[str]] = {
        c: retake_demand[c] for c in hk1_candidates if len(retake_demand[c]) >= 20
    }

    enrollment_records: List[Dict[str, Any]] = []
    enrollment_id = 1

    # -------------------------------------------------------------------------
    # A. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K23 (HỌC KỲ 2)
    # -------------------------------------------------------------------------
    print("\n4. Đang xử lý đăng ký và điểm cho KHÓA K23 (Học kỳ 2)...")
    k23_curriculum = get_curriculum_for_cohort_semester("K23", 2)["compulsory_courses"]
    k23_accel = get_k23_acceleration_students(k23_students, df_prof)

    for prog in ["standard", "high-quality", "advanced"]:
        p_k23 = k23_students[k23_students["program"] == prog]
        student_ids = p_k23["user_id"].tolist()
        print(f"\n* K23 hệ {prog} ({len(student_ids)} sinh viên)")

        for c in k23_curriculum:
            course_code = c["course_code"]
            retakers = [
                uid for uid in retake_demand.get(course_code, [])
                if uid in set(df_students[df_students["program"] == prog]["user_id"])
            ]
            class_ids = [cid for cid in classes_by_prog_course.get((prog, course_code), []) if "L_HL" not in cid]

            if course_code == "LA1005":
                if prog in ("high-quality", "advanced"):
                    continue
                eligible_students = [uid for uid in student_ids if uid in k23_passed_la1003]
                all_learners = eligible_students + retakers
            else:
                all_learners = student_ids + retakers

            if not all_learners or not class_ids:
                continue

            sizes = balanced_class_sizes(len(all_learners), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = all_learners[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    is_retake = uid in retakers
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
            print(f"   -> Đã gán {len(all_learners)} SV{retake_str} vào môn {course_code} ({len(class_ids)} lớp)")

        # K23 Học vượt CH1003 per ADD_CH1003_HK2
        accel_uids = k23_accel.get(prog, [])
        if accel_uids:
            top_code, _ = get_top_acceleration_course_for_term("HK2")
            class_ids = [cid for cid in classes_by_prog_course.get((prog, top_code), []) if "L_HL" not in cid]
            # Loại các lớp K21 (nếu có chung tên) bằng cách chọn các lớp có nhóm học phù hợp
            sizes = balanced_class_sizes(len(accel_uids), max_size=40)
            offset = 0
            comps = course_assessments.get(top_code, [("cuoi_ky", 1.0)])

            # Chọn đúng số lượng lớp học vượt tương ứng
            accel_classes = class_ids[:len(sizes)]
            for class_id, size in zip(accel_classes, sizes):
                assigned_chunk = accel_uids[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{top_code}:{SEMESTER}_accel"
                    rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

                    component_scores, final_score, letter, gpa = score_course_components(
                        student=student_data,
                        course_code=top_code,
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
                        "course_id": top_code,
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

            print(f"   -> [K23 Học vượt] {len(accel_uids)} SV học vượt {top_code} vào {len(accel_classes)} lớp.")

    # -------------------------------------------------------------------------
    # B. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K22 (HỌC KỲ 4)
    # -------------------------------------------------------------------------
    print("\n5. Đang xử lý đăng ký và điểm cho KHÓA K22 (Học kỳ 4)...")
    k22_curriculum = get_curriculum_for_cohort_semester("K22", 4)["compulsory_courses"]
    k22_accel = get_k22_acceleration_students(k22_students, df_prof, k22_passed_mt2013)
    k22_group_d = get_k22_group_d_distribution(k22_students)

    for prog in ["standard", "high-quality", "advanced"]:
        p_k22 = k22_students[k22_students["program"] == prog]
        student_ids = p_k22["user_id"].tolist()
        print(f"\n* K22 hệ {prog} ({len(student_ids)} sinh viên)")

        for c in k22_curriculum:
            course_code = c["course_code"]
            retakers = [
                uid for uid in retake_demand.get(course_code, [])
                if uid in set(k21_students[k21_students["program"] == prog]["user_id"])
            ]
            class_ids = [cid for cid in classes_by_prog_course.get((prog, course_code), []) if "L_HL" not in cid]

            if course_code == "LA1009":
                if prog in ("high-quality", "advanced"):
                    continue
                eligible_students = [uid for uid in student_ids if uid in k22_passed_la1007]
                all_learners = eligible_students + retakers
            elif course_code == "MT2013":
                eligible_students = [uid for uid in student_ids if uid not in k22_passed_mt2013]
                all_learners = eligible_students + retakers
            else:
                all_learners = student_ids + retakers

            if not all_learners or not class_ids:
                continue

            is_politics = course_code.startswith("SP")
            max_cap = 120 if is_politics else 40
            sizes = balanced_class_sizes(len(all_learners), max_size=max_cap)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = all_learners[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    is_retake = uid in retakers
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

            retake_str = f" (+{len(retakers)} K21 học ghép)" if retakers else ""
            print(f"   -> Đã gán {len(all_learners)} SV{retake_str} vào môn {course_code} ({len(class_ids)} lớp)")

        # Group D Electives cho K22
        for g_course in GROUP_D_COURSES:
            g_uids = k22_group_d.get((prog, g_course), [])
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

        # Môn học vượt K22: CO3093 và CO2013
        accel_uids = k22_accel.get(prog, [])
        if accel_uids:
            for accel_code in ["CO3093", "CO2013"]:
                all_accel_classes = classes_by_prog_course.get((prog, accel_code), [])
                sizes = balanced_class_sizes(len(accel_uids), max_size=40)
                offset = 0
                comps = course_assessments.get(accel_code, [("cuoi_ky", 1.0)])

                # Lấy số lượng lớp tương ứng cho K22 học vượt
                accel_classes = all_accel_classes[:len(sizes)]
                for class_id, size in zip(accel_classes, sizes):
                    assigned_chunk = accel_uids[offset : offset + size]
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

                print(f"   -> [K22 Học vượt] {len(accel_uids)} SV học vượt {accel_code} vào {len(accel_classes)} lớp.")

    # -------------------------------------------------------------------------
    # C. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K21 (HỌC KỲ 6)
    # -------------------------------------------------------------------------
    print("\n6. Đang xử lý đăng ký và điểm cho KHÓA K21 (Học kỳ 6)...")
    k21_curriculum = get_curriculum_for_cohort_semester("K21", 6)["compulsory_courses"]

    for prog in ["standard", "high-quality", "advanced"]:
        p_k21 = k21_students[k21_students["program"] == prog]
        student_ids = p_k21["user_id"].tolist()
        print(f"\n* K21 hệ {prog} ({len(student_ids)} sinh viên)")

        # Môn bắt buộc HK6
        for c in k21_curriculum:
            course_code = c["course_code"]
            all_classes = [cid for cid in classes_by_prog_course.get((prog, course_code), []) if "L_HL" not in cid]

            if course_code == "CH1003":
                eligible_learners = [uid for uid in student_ids if uid not in k21_passed_ch1003]
            elif course_code == "CO3093":
                eligible_learners = [uid for uid in student_ids if uid not in k21_passed_co3093]
            else:
                eligible_learners = student_ids

            if not eligible_learners or not all_classes:
                continue

            is_politics = course_code.startswith("SP")
            max_cap = 120 if is_politics else 40
            sizes = balanced_class_sizes(len(eligible_learners), max_size=max_cap)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            # Dành các lớp phía sau cho K21 nếu môn đó đã có lớp học vượt ở trên
            k21_classes = all_classes[-len(sizes):]
            for class_id, size in zip(k21_classes, sizes):
                assigned_chunk = eligible_learners[offset : offset + size]
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

            exempt_cnt = len(student_ids) - len(eligible_learners)
            exempt_str = f", miễn {exempt_cnt} SV" if exempt_cnt > 0 else ""
            print(f"   -> Đã gán {len(eligible_learners)} SV vào môn {course_code} ({len(k21_classes)} lớp{exempt_str})")

        # Lộ trình tốt nghiệp sớm 3.5 năm & Tự chọn Group C (Hệ Tiên tiến học chung với CLC)
        if prog == "advanced":
            print(f"   -> [K21 Tốt nghiệp sớm]: Đã ghép học chung lớp với hệ Chất lượng cao (CC)")
            print(f"   -> [K21 Tự chọn ngành - Group C]: Đã ghép học chung lớp với hệ Chất lượng cao (CC)")
        else:
            if prog == "high-quality":
                k21_adv_uids = k21_students[k21_students["program"] == "advanced"]["user_id"].tolist()
                combined_student_ids = student_ids + k21_adv_uids
            else:
                combined_student_ids = student_ids

            early_candidates = [
                uid for uid in combined_student_ids
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

                    suffix_note = " (CLC+TT)" if prog == "high-quality" else ""
                    print(f"   -> [K21 Tốt nghiệp sớm] {len(early_candidates)} SV hoàn tất môn {early_code}{suffix_note} ({len(sizes)} lớp).")

            # Tự chọn Group C cho sinh viên K21 thông thường
            regular_k21_uids = [uid for uid in combined_student_ids if uid not in set(early_candidates)]
            if regular_k21_uids:
                spec_map = get_student_specialization_map()
                student_c_choices: Dict[str, List[str]] = defaultdict(list)
                for uid in regular_k21_uids:
                    spec = spec_map.get(uid, "Khoa học Máy tính")
                    prev_passed = passed_map.get(uid, set())
                    c1 = select_student_group_c_course(uid, "K21", spec, seed_salt="k21_group_c_1_hk232", exclude_courses=prev_passed)
                    c2 = select_student_group_c_course(uid, "K21", spec, seed_salt="k21_group_c_2_hk232", exclude_courses=prev_passed | {c1})
                    student_c_choices[c1].append(uid)
                    student_c_choices[c2].append(uid)

                for c_code, uids in student_c_choices.items():
                    if not uids:
                        continue
                    all_c_classes = classes_by_prog_course.get((prog, c_code), [])
                    sizes = balanced_class_sizes(len(uids), max_size=40)
                    offset = 0
                    comps = course_assessments.get(c_code, [("cuoi_ky", 1.0)])

                    c_classes = all_c_classes[-len(sizes):]
                    for class_id, size in zip(c_classes, sizes):
                        assigned_chunk = uids[offset : offset + size]
                        offset += size

                        for uid in assigned_chunk:
                            profile = student_profiles[uid]
                            student_data = {"student_id": uid, **profile}

                            seed_str = f"{uid}:{c_code}:{SEMESTER}_c"
                            rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

                            component_scores, final_score, letter, gpa = score_course_components(
                                student=student_data,
                                course_code=c_code,
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
                                "course_id": c_code,
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

    # -------------------------------------------------------------------------
    # D. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K20 (HỌC KỲ 8 - CHUẨN 4 NĂM)
    # -------------------------------------------------------------------------
    print("\n7. Đang xử lý đăng ký và điểm cho KHÓA K20 (Học kỳ 8 - Chuẩn 4 năm)...")
    k20_curriculum = get_curriculum_for_cohort_semester("K20", 8)["compulsory_courses"]

    for prog in ["standard", "high-quality", "advanced"]:
        p_k20 = k20_active_students[k20_active_students["program"] == prog]
        student_ids = p_k20["user_id"].tolist()
        print(f"\n* K20 hệ {prog} ({len(student_ids)} sinh viên)")

        for c in k20_curriculum:
            course_code = c["course_code"]
            class_ids = classes_by_prog_course.get((prog, course_code), [])

            if not student_ids or not class_ids:
                continue

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

                    seed_str = f"{uid}:{course_code}:{SEMESTER}_k20_grad"
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

            print(f"   -> [K20 Chuẩn 4 năm] {len(student_ids)} SV hoàn tất môn {course_code} ({len(class_ids)} lớp)")

    # -------------------------------------------------------------------------
    # E. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO LỚP HỌC LẠI MÔN LẺ/HK1
    # -------------------------------------------------------------------------
    print("\n8. Đang xử lý đăng ký cho các LỚP HỌC LẠI MÔN LẺ/HK1 (Nhu cầu >= 20 SV)...")
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
    # F. TÍNH GPA HỌC KỲ VÀ TÍCH LŨY
    # -------------------------------------------------------------------------
    print("\n9. Đang tính điểm trung bình học kỳ và GPA tích lũy cho cả 4 khóa (K20, K21, K22, K23)...")
    df_enrollment = pd.DataFrame(enrollment_records)

    semester_gpas: Dict[str, float] = {}
    final_gpas: Dict[str, float] = {}

    for uid, attempts in df_enrollment.groupby("student_id"):
        hk_points = 0.0
        hk_credits = 0.0
        for _, att in attempts.iterrows():
            gpa4 = att["gpa_4"]
            ccode = att["course_id"]
            creds = credits_map.get(ccode, 3.0)

            if creds > 0:
                hk_points += gpa4 * creds
                hk_credits += creds

        semester_gpas[str(uid)] = round(hk_points / hk_credits, 2) if hk_credits > 0 else 0.0

    # Xuất file kết quả
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"enrollment_{SEMESTER.lower()}.csv"
    df_enrollment.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số bản ghi đăng ký trong {SEMESTER}: {len(df_enrollment):,} dòng.")

    # Thống kê chi tiết
    df_enr_k20 = df_enrollment[df_enrollment["student_id"].str.startswith("20")]
    df_enr_k21 = df_enrollment[df_enrollment["student_id"].str.startswith("21")]
    df_enr_k22 = df_enrollment[df_enrollment["student_id"].str.startswith("22")]
    df_enr_k23 = df_enrollment[df_enrollment["student_id"].str.startswith("23")]

    print(f"- Bản ghi K20 (Học kỳ 8 - Tốt nghiệp chuẩn): {len(df_enr_k20):,} lượt học.")
    print(f"- Bản ghi K21 (Học kỳ 6): {len(df_enr_k21):,} lượt học.")
    print(f"- Bản ghi K22 (Học kỳ 4): {len(df_enr_k22):,} lượt học.")
    print(f"- Bản ghi K23 (Học kỳ 2): {len(df_enr_k23):,} lượt học.")

    passed_cnt = len(df_enrollment[df_enrollment["passed"] == True])
    failed_cnt = len(df_enrollment[df_enrollment["passed"] == False])
    print(f"- Tỷ lệ đạt: {passed_cnt:,} ({passed_cnt/len(df_enrollment)*100:.1f}%) | Rớt: {failed_cnt:,} ({failed_cnt/len(df_enrollment)*100:.1f}%)")

    mean_hk_gpa = np.mean(list(semester_gpas.values()))
    print(f"- GPA trung bình học kỳ {SEMESTER}: {mean_hk_gpa:.2f}/4.0")

    return out_file


if __name__ == "__main__":
    generate_enrollment_hk232()
