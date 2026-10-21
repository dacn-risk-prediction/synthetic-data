"""Generate enrollment records and course grades for semester HK241.

In this semester, five distinct cohorts attend classes simultaneously:
1. Cohort K24 in Term 1 (Freshmen - Tân sinh viên):
   - Compulsory courses: MT1003, PH1003, CO1005, CO1023, LA1003
   - CLC and Advanced: 100% exempted from English
   - Standard: Placement test exemption (~25%) or class enrollment
   - Retakers from older cohorts join regular classes

2. Cohort K23 in Term 3 (Sophomore - Năm 2):
   - Compulsory courses: CO2011, SP1031, CO2003, CO2007, LA1007
   - Accelerated: MT2013 (Xác suất & Thống kê) per ADD_MT2013_HK3

3. Cohort K22 in Term 5 (Junior - Năm 3):
   - Compulsory courses: SP1035, CO2001, CO3001, CO3005,
     CO2013 (bỏ qua nếu đã hoàn thành ở HK232)
   - Elective Group C: CO3011, CO3021, CO3029, CO3043, CO3045

4. Cohort K21 in Term 7 (Senior - Năm 4):
   - Compulsory courses: SP1039, CO3335,
     CO4029 (bỏ qua nếu đã hoàn thành ở HK232)
   - Lộ trình tốt nghiệp sớm 3.5 năm (18 SV K21): CO4337 (Đồ án tốt nghiệp) & SP1007

5. Cohort K20 in Term 9 (Năm 5 - Tốt nghiệp trễ hạn / Kéo dài đào tạo):
   - 714 SV K20 đã tốt nghiệp ở HK231/HK232 không tham gia.
   - 786 SV K20 chưa tốt nghiệp học trả nợ môn rớt (kể cả CO4337, SP1007) để xét tốt nghiệp đợt 4.5 năm.

6. Lớp học lại môn chẵn/HK2 (L_HL):
   - Gán sinh viên nợ các môn chẵn vào các lớp học lại L_HL
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

from academic_rules import (
    GENERATOR_CONFIG,
    balanced_class_sizes,
    score_course_components,
)

ANALYSIS_DIR = ROOT_DIR / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from analysis_helpers import get_curriculum_for_cohort_semester

SEMESTER = "HK241"
MAX_SEMESTER_CREDITS = 22.0
GROUP_C_COURSES = ["CO3011", "CO3021", "CO3029", "CO3043", "CO3045"]


def is_k24_standard_exempt_la1003(student_id: str) -> bool:
    """Determine whether a K24 Standard freshman qualifies for LA1003 exemption."""
    digest = hashlib.sha256(f"{student_id}:la1003_placement".encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    return (seed % 100) < 25


def get_k23_acceleration_students(k23_students: pd.DataFrame, df_prof: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K23 students accelerating MT2013 in HK3 per additional_course_rules.csv."""
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")
    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k23_students.iterrows():
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


def get_k22_group_c_distribution(k22_students: pd.DataFrame) -> Dict[Tuple[str, str], List[str]]:
    """Distribute K22 students among Group C elective courses."""
    choice_map: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, row in k22_students.iterrows():
        uid = str(row["user_id"])
        prog = row["program"]
        seed_val = int(hashlib.sha256(f"{uid}:group_c".encode()).hexdigest()[:8], 16)
        c_code = GROUP_C_COURSES[seed_val % len(GROUP_C_COURSES)]
        choice_map[(prog, c_code)].append(uid)
    return choice_map


def generate_enrollment_hk241() -> Path:
    """Execute enrollment generation for semester HK241 and export to enrollment_hk241.csv."""
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

    # 2. Đọc danh sách lớp học phần HK241
    classes_file = CLASSES_DIR / "class_hk241.csv"
    if not classes_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file lớp: {classes_file}. Hãy chạy generate_class_hk241.py trước!")
    df_classes = pd.read_csv(classes_file, encoding="utf-8-sig")
    print(f"2. Tổng số lớp học phần đã mở cho HK241: {len(df_classes)} lớp.")

    # 3. Đọc lịch sử học tập các kỳ trước: HK201 -> HK232
    prior_sems = ["hk201", "hk202", "hk211", "hk212", "hk221", "hk222", "hk231", "hk232"]
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
            if pd.isna(score) or float(score) == 12.0 or pd.isna(gpa4):
                continue
            if r["passed"] == True:
                history_passed[sid][cid] = float(gpa4)

    # Đọc profiles
    profiles_file = USERS_DIR / "student_profiles.csv"
    df_profiles = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    student_profiles: Dict[str, Dict[str, Any]] = df_profiles.set_index("student_id").to_dict(orient="index")

    # K20: Loại trừ SV đã tốt nghiệp đủ điều kiện ở HK231/HK232
    k20_graduated_uids = set()
    for uid in k20_students["user_id"]:
        if "CO4337" in history_passed[uid] and "SP1007" in history_passed[uid]:
            p = student_profiles.get(uid, {})
            is_eng = str(p.get("english_pass", "")).lower() == "true"
            if not is_eng:
                try:
                    eng_l = json.loads(p.get("english_eligibility_by_semester", "[]"))
                    is_eng = any(x.get("eligible", False) for x in eng_l if x.get("semester") in ["HK231", "HK232"])
                except Exception:
                    pass
            ctxh_ok = False
            try:
                ctxh_l = json.loads(p.get("ctxh_days_by_semester", "[]"))
                ctxh_by_s = {x.get("semester"): x.get("cumulative_days", 0) for x in ctxh_l}
                ctxh_ok = ctxh_by_s.get("HK232", 0) >= 15
            except Exception:
                pass

            if is_eng and ctxh_ok:
                k20_graduated_uids.add(uid)

    k20_active_students = k20_students[~k20_students["user_id"].isin(k20_graduated_uids)].copy()
    print(f"3. K20 đã tốt nghiệp ở HK231/HK232: {len(k20_graduated_uids)} SV -> K20 còn lại học HK241: {len(k20_active_students)} SV.")

    # K21 đã hoàn thành CO4029 ở HK232 (nhóm sớm)
    k21_passed_co4029 = {uid for uid in k21_students["user_id"] if "CO4029" in history_passed[uid]}

    # K22 đã học vượt CO2013 ở HK232
    k22_passed_co2013 = {uid for uid in k22_students["user_id"] if "CO2013" in history_passed[uid]}

    # K23 Đại trà đạt LA1005 ở HK232 -> đủ điều kiện học LA1007
    k23_passed_la1005 = {uid for uid in k23_students["user_id"] if "LA1005" in history_passed[uid]}

    # Nhu cầu học lại từ các kỳ trước (chỉ tính SV chưa tốt nghiệp)
    all_prev_enrollments = pd.concat(prev_dfs)
    retake_demand: Dict[str, List[str]] = defaultdict(list)
    for _, r in all_prev_enrollments[all_prev_enrollments["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        if sid not in k20_graduated_uids and cid not in history_passed[sid] and sid not in retake_demand[cid]:
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

    # Theo dõi số tín chỉ đăng ký thực tế của từng sinh viên trong HK241 (tối đa 22 TC)
    student_credits: Dict[str, float] = defaultdict(float)

    def can_enroll(uid: str, course_code: str) -> bool:
        """Kiểm tra điều kiện đăng ký môn học: Tiên quyết (TQ) & Giới hạn tối đa 22 tín chỉ."""
        tc = credits_map.get(course_code, 0.0)
        if tc > 0 and (student_credits[uid] + tc > MAX_SEMESTER_CREDITS):
            return False

        # Đối với CO4337: Nhóm tốt nghiệp sớm K21 học KLTN ở HK7 song hành với Thực tập CO3335
        if course_code == "CO4337":
            p = student_profiles.get(uid, {})
            is_early = str(p.get("early_graduation_candidate", "")).lower() == "true"
            if is_early and uid in k21_passed_co4029:
                return True
            # Các SV khác (K20 trả nợ): bắt buộc phải hoàn thành các môn tiên quyết (CO3335, CO4029)
            for req in tq_map.get(course_code, set()):
                if req not in history_passed[uid]:
                    return False
            return True

        # Tất cả các môn học khác: bắt buộc đã đậu toàn bộ môn tiên quyết (TQ)
        for req in tq_map.get(course_code, set()):
            if req not in history_passed[uid]:
                return False
        return True

    k23_accel = get_k23_acceleration_students(k23_students, df_profiles)
    k22_group_c = get_k22_group_c_distribution(k22_students)

    k24_compulsory = get_curriculum_for_cohort_semester("K24", 1)["compulsory_courses"]
    k24_core_courses = [c["course_code"] for c in k24_compulsory if not c["course_code"].startswith("LA")]

    k23_compulsory = get_curriculum_for_cohort_semester("K23", 3)["compulsory_courses"]
    k23_core_courses = [c["course_code"] for c in k23_compulsory if not c["course_code"].startswith("LA")]

    k22_compulsory = get_curriculum_for_cohort_semester("K22", 5)["compulsory_courses"]
    k22_core_courses = [c["course_code"] for c in k22_compulsory if c["course_code"] != "CO2013"]

    k21_compulsory = get_curriculum_for_cohort_semester("K21", 7)["compulsory_courses"]
    k21_core_courses = [c["course_code"] for c in k21_compulsory if c["course_code"] != "CO4029"]

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
    # A. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K24 (HỌC KỲ 1)
    # -------------------------------------------------------------------------
    print("\n4. Đang xử lý đăng ký và điểm cho KHÓA K24 (Học kỳ 1)...")
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

        # Môn Ngoại ngữ LA1003 cho K24
        if prog in ("high-quality", "advanced"):
            for uid in student_ids:
                for c_eng in ["LA1003", "LA1005", "LA1007", "LA1009"]:
                    rec = {
                        "enrollment_id": enrollment_id,
                        "student_id": uid,
                        "class_id": np.nan,
                        "course_id": c_eng,
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
            exempt_uids = [uid for uid in student_ids if is_k24_standard_exempt_la1003(uid)]
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
            valid_la1003 = [uid for uid in all_la1003 if can_enroll(uid, course_code)]
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_la1003), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_la1003[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(retakers_la1003)))

            print(f"   -> Đã gán {len(valid_la1003)} SV vào môn LA1003 ({len(class_ids)} lớp, miễn {len(exempt_uids)} SV)")

    # -------------------------------------------------------------------------
    # B. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K23 (HỌC KỲ 3)
    # -------------------------------------------------------------------------
    print("\n5. Đang xử lý đăng ký và điểm cho KHÓA K23 (Học kỳ 3)...")
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

        # Môn Ngoại ngữ LA1007 cho K23 Đại trà
        if prog == "standard":
            course_code = "LA1007"
            eligible_uids = [uid for uid in student_ids if uid in k23_passed_la1005]
            retakers_la1007 = [
                uid for uid in retake_demand.get("LA1007", [])
                if uid in set(df_students[df_students["program"] == "standard"]["user_id"])
            ]
            all_la1007 = eligible_uids + retakers_la1007
            valid_la1007 = [uid for uid in all_la1007 if can_enroll(uid, course_code)]
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_la1007), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_la1007[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(retakers_la1007)))

            print(f"   -> Đã gán {len(valid_la1007)} SV vào môn LA1007 ({len(class_ids)} lớp)")

        # Môn học vượt K23: MT2013
        accel_uids = k23_accel.get(prog, [])
        valid_accel = [uid for uid in accel_uids if can_enroll(uid, "MT2013")]
        if valid_accel:
            course_code = "MT2013"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_accel), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_accel[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=False, seed_suffix="_accel")

            print(f"   -> [K23 Học vượt] {len(valid_accel)} SV học vượt MT2013 vào {len(class_ids)} lớp.")

    # -------------------------------------------------------------------------
    # C. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K22 (HỌC KỲ 5)
    # -------------------------------------------------------------------------
    print("\n6. Đang xử lý đăng ký và điểm cho KHÓA K22 (Học kỳ 5)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k22 = k22_students[k22_students["program"] == prog].copy()
        student_ids = p_k22["user_id"].tolist()
        print(f"\n* K22 hệ {prog} ({len(student_ids)} sinh viên)")

        for course_code in k22_core_courses:
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

        # CO2013 cho K22 (bỏ qua nếu đã học vượt ở HK232)
        k22_co2013_learners = [uid for uid in student_ids if uid not in k22_passed_co2013]
        retakers_co2013 = [
            uid for uid in retake_demand.get("CO2013", [])
            if uid in set(df_students[df_students["program"] == prog]["user_id"])
        ]
        all_co2013 = k22_co2013_learners + retakers_co2013
        valid_co2013 = [uid for uid in all_co2013 if can_enroll(uid, "CO2013")]
        if valid_co2013:
            course_code = "CO2013"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_co2013), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_co2013[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(retakers_co2013)))

            print(f"   -> Đã gán {len(valid_co2013)} SV vào môn CO2013 ({len(class_ids)} lớp)")

        # Tự chọn Group C cho K22
        for g_course in GROUP_C_COURSES:
            g_uids = k22_group_c.get((prog, g_course), [])
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

    # -------------------------------------------------------------------------
    # D. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO KHÓA K21 (HỌC KỲ 7) & K20 TRẢ NỢ
    # -------------------------------------------------------------------------
    print("\n7. Đang xử lý đăng ký và điểm cho KHÓA K21 (Học kỳ 7) & K20 TRẢ NỢ...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k21 = k21_students[k21_students["program"] == prog].copy()
        student_ids = p_k21["user_id"].tolist()
        print(f"\n* K21 hệ {prog} ({len(student_ids)} sinh viên)")

        for course_code in k21_core_courses:
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

        # CO4029 (Đồ án chuyên ngành): chỉ SV K21 chưa hoàn thành ở HK232
        k21_co4029_learners = [uid for uid in student_ids if uid not in k21_passed_co4029]
        retakers_co4029 = [
            uid for uid in retake_demand.get("CO4029", [])
            if uid in set(df_students[df_students["program"] == prog]["user_id"])
        ]
        all_co4029 = k21_co4029_learners + retakers_co4029
        valid_co4029 = [uid for uid in all_co4029 if can_enroll(uid, "CO4029")]
        if valid_co4029:
            course_code = "CO4029"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_co4029), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_co4029[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(retakers_co4029)))

            print(f"   -> Đã gán {len(valid_co4029)} SV vào môn CO4029 ({len(class_ids)} lớp)")

        # Lộ trình tốt nghiệp sớm 3.5 năm: K21 early candidates + K20 trả nợ CO4337 và SP1007
        early_candidates = [
            uid for uid in student_ids
            if str(student_profiles.get(uid, {}).get("early_graduation_candidate", "")).lower() == "true"
            and uid in k21_passed_co4029
        ]
        k20_prog_retakers_co4337 = [
            uid for uid in retake_demand.get("CO4337", [])
            if uid in set(k20_active_students[k20_active_students["program"] == prog]["user_id"])
        ]
        k20_prog_retakers_sp1007 = [
            uid for uid in retake_demand.get("SP1007", [])
            if uid in set(k20_active_students[k20_active_students["program"] == prog]["user_id"])
        ]

        # Xử lý CO4337 (Khóa luận tốt nghiệp)
        all_co4337 = early_candidates + k20_prog_retakers_co4337
        valid_co4337 = [uid for uid in all_co4337 if can_enroll(uid, "CO4337")]
        if valid_co4337:
            course_code = "CO4337"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_co4337), max_size=40)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_co4337[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(k20_prog_retakers_co4337)), seed_suffix="_grad")

            print(f"   -> [CO4337] {len(valid_co4337)} SV hoàn tất đăng ký ({len(class_ids)} lớp)")

        # Xử lý SP1007
        all_sp1007 = early_candidates + k20_prog_retakers_sp1007
        valid_sp1007 = [uid for uid in all_sp1007 if can_enroll(uid, "SP1007")]
        if valid_sp1007:
            course_code = "SP1007"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(valid_sp1007), max_size=120)
            offset = 0

            for class_id, size in zip(class_ids, sizes):
                assigned_chunk = valid_sp1007[offset : offset + size]
                offset += size

                for uid in assigned_chunk:
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(k20_prog_retakers_sp1007)), seed_suffix="_grad")

            print(f"   -> [SP1007] {len(valid_sp1007)} SV hoàn tất đăng ký ({len(class_ids)} lớp)")

    # -------------------------------------------------------------------------
    # E. MÔ PHỎNG ĐĂNG KÝ VÀ CHẤM ĐIỂM CHO LỚP HỌC LẠI MÔN CHẴN/HK2 (L_HL)
    # -------------------------------------------------------------------------
    print("\n8. Đang xử lý đăng ký cho các LỚP HỌC LẠI MÔN CHẴN/HK2 (L_HL)...")
    even_courses_retake = [
        "CO1027", "PH1007", "CO2017", "CO1007", "MT1007", "MT1005",
        "CO2039", "SP1033", "CO3093", "CH1003", "SP1037", "MI1003",
    ]
    for retake_code in even_courses_retake:
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
    generate_enrollment_hk241()
