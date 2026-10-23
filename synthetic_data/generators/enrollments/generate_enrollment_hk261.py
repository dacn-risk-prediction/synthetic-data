"""Generate enrollment records for semester HK261 (Current Semester - Học kỳ hiện tại).

In this semester, six cohorts attend classes:
1. Cohort K26 in Term 1 (Freshmen - Tân sinh viên):
   - Compulsory courses: MT1003, PH1003, CO1005, CO1023, LA1003
   - CLC and Advanced: 100% exempted from English
   - Standard: Placement test exemption (~25%) or regular class enrollment
   - Retakers from older cohorts join regular classes for HK1 courses

2. Cohort K25 in Term 3 (Sophomore - Năm 2):
   - Compulsory courses: CO2011, SP1031, CO2003, CO2007, LA1007
   - Accelerated: MT2013 (Xác suất & Thống kê) per ADD_MT2013_HK3

3. Cohort K24 in Term 5 (Junior - Năm 3):
   - Compulsory courses: SP1035, CO2001, CO3001, CO3005,
     CO2013 (bỏ qua nếu đã hoàn thành ở HK252)
   - Elective Group C: CO3011, CO3021, CO3029, CO3043, CO3045

4. Cohort K23 in Term 7 (Senior - Năm 4):
   - Compulsory courses: SP1039, CO3335,
     CO4029 (bỏ qua nếu đã hoàn thành ở HK252)
   - Lộ trình tốt nghiệp sớm 3.5 năm (19 SV K23): CO4337 (Đồ án tốt nghiệp) & SP1007

5. Cohort K22 in Term 9 (Năm 5 - Tốt nghiệp trễ hạn / Kéo dài đào tạo 4.5 năm):
   - 738 SV K22 đã tốt nghiệp ở HK251/HK252 không tham gia.
   - 821 SV K22 chưa tốt nghiệp học trả nợ môn rớt (kể cả CO4337, SP1007).

6. Cohort K21 in Term 11 (Năm 6 - Tốt nghiệp trễ hạn 5.5 năm):
   - 1,166 SV K21 đã tốt nghiệp tính đến HK252 không tham gia.
   - 354 SV K21 chưa tốt nghiệp học trả nợ môn rớt.

7. Khóa K20 đã hết hạn đào tạo tối đa (6.0 năm / 12 học kỳ chính) tại HK252, không tham gia HK261.

8. ĐẶC BIỆT: Đây là HỌC KỲ HIỆN TẠI (CURRENT ONGOING SEMESTER):
   - Sinh viên đã có các cột điểm quá trình: quiz, lab, btl, giua_ky (phục vụ mô hình AI dự đoán rủi ro rớt môn).
   - Chưa thi cuối kỳ: cuoi_ky, final_score, letter_grade, gpa_4, passed, status để trống (NaN).
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

from curriculum_rules import select_student_group_c_course, get_student_specialization_map

from academic_rules import (
    GENERATOR_CONFIG,
    balanced_class_sizes,
    score_course_components,
)

ANALYSIS_DIR = ROOT_DIR / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from analysis_helpers import get_curriculum_for_cohort_semester

SEMESTER = "HK261"
MAX_SEMESTER_CREDITS = 22.0
GROUP_C_COURSES = ["CO3011", "CO3021", "CO3029", "CO3043", "CO3045"]


def is_k26_standard_exempt_la1003(student_id: str) -> bool:
    """Determine whether a K26 Standard freshman qualifies for LA1003 exemption."""
    digest = hashlib.sha256(f"{student_id}:la1003_placement".encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    return (seed % 100) < 25


def get_k25_acceleration_students(k25_students: pd.DataFrame, df_prof: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify K25 students accelerating MT2013 in HK3 per additional_course_rules.csv."""
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")
    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k25_students.iterrows():
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


def get_k24_group_c_distribution(k24_students: pd.DataFrame) -> Dict[Tuple[str, str], List[str]]:
    """Distribute K24 students among Group C elective courses based on specialization."""
    spec_map = get_student_specialization_map()
    choice_map: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, row in k24_students.iterrows():
        uid = str(row["user_id"])
        prog = row["program"]
        spec = spec_map.get(uid, "Khoa học Máy tính")
        c_code = select_student_group_c_course(uid, "K24", spec, seed_salt="k24_group_c_hk261")
        choice_map[(prog, c_code)].append(uid)
    return choice_map


def generate_enrollment_hk261() -> Path:
    """Execute enrollment generation for semester HK261 and export to enrollment_hk261.csv."""
    print(f"=== KHỞI CHẠY SINH DỮ LIỆU ĐĂNG KÝ HỌC PHẦN CHO {SEMESTER} (KỲ HIỆN TẠI - ĐA KHÓA: K21 -> K26) ===")

    # 1. Đọc sinh viên các khóa
    students_file = USERS_DIR / "student.csv"
    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k21_students = df_students[df_students["user_id"].str.startswith("21")].copy()
    k22_students = df_students[df_students["user_id"].str.startswith("22")].copy()
    k23_students = df_students[df_students["user_id"].str.startswith("23")].copy()
    k24_students = df_students[df_students["user_id"].str.startswith("24")].copy()
    k25_students = df_students[df_students["user_id"].str.startswith("25")].copy()
    k26_students = df_students[df_students["user_id"].str.startswith("26")].copy()
    k20_all_uids = set(df_students[df_students["user_id"].str.startswith("20")]["user_id"])

    print(f"1. Tổng SV: K21: {len(k21_students)} | K22: {len(k22_students)} | K23: {len(k23_students)} | K24: {len(k24_students)} | K25: {len(k25_students)} | K26: {len(k26_students)}")

    # 2. Đọc danh sách lớp học phần HK261
    classes_file = CLASSES_DIR / f"class_{SEMESTER.lower()}.csv"
    if not classes_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file lớp: {classes_file}. Hãy chạy generate_class_{SEMESTER.lower()}.py trước!")
    df_classes = pd.read_csv(classes_file, encoding="utf-8-sig")
    print(f"2. Tổng số lớp học phần đã mở cho {SEMESTER}: {len(df_classes)} lớp.")

    # 3. Đọc lịch sử học tập các kỳ trước: HK201 -> HK252
    prior_sems = [
        "hk201", "hk202", "hk211", "hk212", "hk221", "hk222",
        "hk231", "hk232", "hk241", "hk242", "hk251", "hk252",
    ]
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
                if r.get("status") == "Exempted" or r["passed"] == True:
                    history_passed[sid][cid] = 4.0
                continue
            if r["passed"] == True:
                history_passed[sid][cid] = float(gpa4)

    # Đọc profiles
    profiles_file = USERS_DIR / "student_profiles.csv"
    df_profiles = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    student_profiles: Dict[str, Dict[str, Any]] = df_profiles.set_index("student_id").to_dict(orient="index")

    # K22: Loại trừ SV đã tốt nghiệp đủ điều kiện tính đến HK252 (738 SV)
    k22_graduated_uids = set()
    for uid in k22_students["user_id"]:
        if "CO4337" in history_passed[uid] and "SP1007" in history_passed[uid]:
            p = student_profiles.get(uid, {})
            is_eng = str(p.get("english_pass", "")).lower() == "true"
            if not is_eng:
                try:
                    eng_l = json.loads(p.get("english_eligibility_by_semester", "[]"))
                    is_eng = any(x.get("eligible", False) for x in eng_l if x.get("semester") in ["HK251", "HK252"])
                except Exception:
                    pass
            ctxh_ok = False
            try:
                ctxh_l = json.loads(p.get("ctxh_days_by_semester", "[]"))
                ctxh_by_s = {x.get("semester"): x.get("cumulative_days", 0) for x in ctxh_l}
                ctxh_ok = ctxh_by_s.get("HK252", 0) >= 15
            except Exception:
                pass
            if is_eng and ctxh_ok:
                k22_graduated_uids.add(uid)

    k22_active_students = k22_students[~k22_students["user_id"].isin(k22_graduated_uids)].copy()
    print(f"3. K22 đã tốt nghiệp tính đến HK252: {len(k22_graduated_uids)} SV -> K22 còn lại học HK261 (Kỳ 9 - 4.5 năm): {len(k22_active_students)} SV.")

    # K21: Loại trừ SV đã tốt nghiệp đủ điều kiện tính đến HK252 (1,166 SV)
    k21_graduated_uids = set()
    for uid in k21_students["user_id"]:
        if "CO4337" in history_passed[uid] and "SP1007" in history_passed[uid]:
            p = student_profiles.get(uid, {})
            is_eng = str(p.get("english_pass", "")).lower() == "true"
            if not is_eng:
                try:
                    eng_l = json.loads(p.get("english_eligibility_by_semester", "[]"))
                    is_eng = any(x.get("eligible", False) for x in eng_l if x.get("semester") in ["HK241", "HK242", "HK251", "HK252"])
                except Exception:
                    pass
            ctxh_ok = False
            try:
                ctxh_l = json.loads(p.get("ctxh_days_by_semester", "[]"))
                ctxh_by_s = {x.get("semester"): x.get("cumulative_days", 0) for x in ctxh_l}
                ctxh_ok = ctxh_by_s.get("HK252", 0) >= 15
            except Exception:
                pass
            if is_eng and ctxh_ok:
                k21_graduated_uids.add(uid)

    k21_active_students = k21_students[~k21_students["user_id"].isin(k21_graduated_uids)].copy()
    print(f"   K21 đã tốt nghiệp tính đến HK252: {len(k21_graduated_uids)} SV -> K21 còn lại học HK261 (Kỳ 11 - 5.5 năm): {len(k21_active_students)} SV.")

    # K23 đã hoàn thành CO4029 ở HK252 (nhóm tốt nghiệp sớm)
    k23_passed_co4029 = {uid for uid in k23_students["user_id"] if "CO4029" in history_passed[uid]}

    # K24 đã học vượt CO2013 ở HK252
    k24_passed_co2013 = {uid for uid in k24_students["user_id"] if "CO2013" in history_passed[uid]}

    # K25 Đại trà đạt LA1005 ở HK252 -> đủ điều kiện học LA1007
    k25_passed_la1005 = {uid for uid in k25_students["user_id"] if "LA1005" in history_passed[uid]}

    # Nhu cầu học lại từ các kỳ trước (chỉ tính SV chưa tốt nghiệp)
    graduated_all = k22_graduated_uids.union(k21_graduated_uids).union(k20_all_uids)
    all_prev_enrollments = pd.concat(prev_dfs)
    retake_demand: Dict[str, List[str]] = defaultdict(list)
    for _, r in all_prev_enrollments[all_prev_enrollments["passed"] == False].iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        if sid not in graduated_all and cid not in history_passed[sid] and sid not in retake_demand[cid]:
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

    # Theo dõi số tín chỉ đăng ký thực tế của từng sinh viên trong HK261 (tối đa 22 TC)
    student_credits: Dict[str, float] = defaultdict(float)

    def can_enroll(uid: str, course_code: str) -> bool:
        """Kiểm tra điều kiện đăng ký môn học: Tiên quyết (TQ) & Giới hạn tối đa 22 tín chỉ."""
        tc = credits_map.get(course_code, 0.0)
        if tc > 0 and (student_credits[uid] + tc > MAX_SEMESTER_CREDITS):
            return False

        # Đối với CO4337: Nhóm tốt nghiệp sớm K23 học KLTN ở HK7 song hành với Thực tập CO3335
        if course_code == "CO4337":
            p = student_profiles.get(uid, {})
            is_early = str(p.get("early_graduation_candidate", "")).lower() == "true"
            if is_early and uid in k23_passed_co4029:
                return True
            # Các SV khác (K22/K21 trả nợ): bắt buộc phải hoàn thành các môn tiên quyết (CO3335, CO4029)
            for req in tq_map.get(course_code, set()):
                if req not in history_passed[uid]:
                    return False
            return True

        # Tất cả các môn học khác: bắt buộc đã đậu toàn bộ môn tiên quyết (TQ)
        for req in tq_map.get(course_code, set()):
            if req not in history_passed[uid]:
                return False
        return True

    k25_accel = get_k25_acceleration_students(k25_students, df_profiles)
    k24_group_c = get_k24_group_c_distribution(k24_students)

    k26_compulsory = get_curriculum_for_cohort_semester("K26", 1)["compulsory_courses"]
    k26_core_courses = [c["course_code"] for c in k26_compulsory if not c["course_code"].startswith("LA")]

    k25_compulsory = get_curriculum_for_cohort_semester("K25", 3)["compulsory_courses"]
    k25_core_courses = [c["course_code"] for c in k25_compulsory if not c["course_code"].startswith("LA")]

    k24_compulsory = get_curriculum_for_cohort_semester("K24", 5)["compulsory_courses"]
    k24_core_courses = [c["course_code"] for c in k24_compulsory if c["course_code"] != "CO2013"]

    k23_compulsory = get_curriculum_for_cohort_semester("K23", 7)["compulsory_courses"]
    k23_core_courses = [c["course_code"] for c in k23_compulsory if c["course_code"] != "CO4029"]

    enrollment_records: List[Dict[str, Any]] = []
    enrollment_id = total_past_enrollments + 1

    classes_by_prog_course: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, r in df_classes.iterrows():
        classes_by_prog_course[(r["program"], r["course_code"])].append(r["class_id"])

    def record_grade(uid: str, course_code: str, class_id: Any, is_retake: bool, seed_suffix: str = ""):
        """
        Record enrollment for current ongoing semester HK261:
        - In-term components (quiz, lab, btl, giua_ky) are scored for dropout risk prediction.
        - cuoi_ky, final_score, letter_grade, gpa_4, passed, status are NaN (as final exams haven't happened).
        """
        nonlocal enrollment_id
        profile = student_profiles[uid]
        student_data = {"student_id": uid, **profile}

        seed_str = f"{uid}:{course_code}:{SEMESTER}{seed_suffix}"
        rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16))

        comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])
        component_scores, _, _, _ = score_course_components(
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
            "cuoi_ky": np.nan,
            "final_score": np.nan,
            "letter_grade": np.nan,
            "gpa_4": np.nan,
            "passed": np.nan,
            "status": np.nan,
        }
        enrollment_records.append(rec)
        enrollment_id += 1

    # -------------------------------------------------------------------------
    # A. MÔ PHỎNG ĐĂNG KÝ CHO KHÓA K26 (HỌC KỲ 1)
    # -------------------------------------------------------------------------
    print("\n4. Đang xử lý đăng ký và điểm quá trình cho KHÓA K26 (Học kỳ 1)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k26 = k26_students[k26_students["program"] == prog].copy()
        student_ids = p_k26["user_id"].tolist()
        print(f"\n* K26 hệ {prog} ({len(student_ids)} sinh viên)")

        for course_code in k26_core_courses:
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

        # Môn Ngoại ngữ LA1003 cho K26
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
            exempt_uids = [uid for uid in student_ids if is_k26_standard_exempt_la1003(uid)]
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
    # B. MÔ PHỎNG ĐĂNG KÝ CHO KHÓA K25 (HỌC KỲ 3)
    # -------------------------------------------------------------------------
    print("\n5. Đang xử lý đăng ký và điểm quá trình cho KHÓA K25 (Học kỳ 3)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k25 = k25_students[k25_students["program"] == prog].copy()
        student_ids = p_k25["user_id"].tolist()
        print(f"\n* K25 hệ {prog} ({len(student_ids)} sinh viên)")

        for course_code in k25_core_courses:
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

        # Môn Ngoại ngữ LA1007 cho K25 Đại trà
        if prog == "standard":
            course_code = "LA1007"
            eligible_uids = [uid for uid in student_ids if uid in k25_passed_la1005]
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

        # Môn học vượt K25: MT2013
        accel_uids = k25_accel.get(prog, [])
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

            print(f"   -> [K25 Học vượt] {len(valid_accel)} SV học vượt MT2013 vào {len(class_ids)} lớp.")

    # -------------------------------------------------------------------------
    # C. MÔ PHỎNG ĐĂNG KÝ CHO KHÓA K24 (HỌC KỲ 5)
    # -------------------------------------------------------------------------
    print("\n6. Đang xử lý đăng ký và điểm quá trình cho KHÓA K24 (Học kỳ 5)...")
    for prog in ["standard", "high-quality", "advanced"]:
        p_k24 = k24_students[k24_students["program"] == prog].copy()
        student_ids = p_k24["user_id"].tolist()
        print(f"\n* K24 hệ {prog} ({len(student_ids)} sinh viên)")

        for course_code in k24_core_courses:
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

        # CO2013 cho K24 (bỏ qua nếu đã học vượt ở HK252)
        k24_co2013_learners = [uid for uid in student_ids if uid not in k24_passed_co2013]
        retakers_co2013 = [
            uid for uid in retake_demand.get("CO2013", [])
            if uid in set(df_students[df_students["program"] == prog]["user_id"])
        ]
        all_co2013 = k24_co2013_learners + retakers_co2013
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

        # Tự chọn Group C cho K24 theo chuyên ngành
        # Quy tắc: Hệ Tiên tiến (advanced) ghép học chung lớp với Chất lượng cao (high-quality)
        if prog == "advanced":
            print(f"   -> [K24 Tự chọn ngành - Group C]: Đã ghép học chung lớp với hệ Chất lượng cao (CC)")
        elif prog == "high-quality":
            all_group_c = sorted(list({c for (p, c) in k24_group_c.keys() if p in ("high-quality", "advanced")}))
            for g_course in all_group_c:
                g_uids = k24_group_c.get(("high-quality", g_course), []) + k24_group_c.get(("advanced", g_course), [])
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
        else:
            all_group_c = sorted(list({c for (p, c) in k24_group_c.keys() if p == prog}))
            for g_course in all_group_c:
                g_uids = k24_group_c.get((prog, g_course), [])
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
    # D. MÔ PHỎNG ĐĂNG KÝ CHO KHÓA K23 (HỌC KỲ 7) & K22/K21 TRẢ NỢ
    # -------------------------------------------------------------------------
    print("\n7. Đang xử lý đăng ký và điểm quá trình cho KHÓA K23 (Học kỳ 7) & K22/K21 TRẢ NỢ...")
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

        # CO4029 (Đồ án chuyên ngành): chỉ SV K23 chưa hoàn thành ở HK252
        k23_co4029_learners = [uid for uid in student_ids if uid not in k23_passed_co4029]
        retakers_co4029 = [
            uid for uid in retake_demand.get("CO4029", [])
            if uid in set(df_students[df_students["program"] == prog]["user_id"])
        ]
        all_co4029 = k23_co4029_learners + retakers_co4029
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

        # Lộ trình tốt nghiệp sớm 3.5 năm: K23 early candidates + K22/K21 trả nợ CO4337 và SP1007
        early_candidates = [
            uid for uid in student_ids
            if str(student_profiles.get(uid, {}).get("early_graduation_candidate", "")).lower() == "true"
            and uid in k23_passed_co4029
        ]
        active_prog_older_uids = set(
            df_students[
                (df_students["program"] == prog)
                & (df_students["user_id"].isin(k21_active_students["user_id"].tolist() + k22_active_students["user_id"].tolist()))
            ]["user_id"]
        )
        older_prog_retakers_co4337 = [
            uid for uid in retake_demand.get("CO4337", [])
            if uid in active_prog_older_uids
        ]
        older_prog_retakers_sp1007 = [
            uid for uid in retake_demand.get("SP1007", [])
            if uid in active_prog_older_uids
        ]

        # Xử lý CO4337 (Khóa luận tốt nghiệp)
        all_co4337 = early_candidates + older_prog_retakers_co4337
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
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(older_prog_retakers_co4337)), seed_suffix="_grad")

            print(f"   -> [CO4337] {len(valid_co4337)} SV hoàn tất đăng ký ({len(class_ids)} lớp)")

        # Xử lý SP1007
        all_sp1007 = early_candidates + older_prog_retakers_sp1007
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
                    record_grade(uid, course_code, class_id, is_retake=(uid in set(older_prog_retakers_sp1007)), seed_suffix="_grad")

            print(f"   -> [SP1007] {len(valid_sp1007)} SV hoàn tất đăng ký ({len(class_ids)} lớp)")

    # -------------------------------------------------------------------------
    # E. MÔ PHỎNG ĐĂNG KÝ CHO LỚP HỌC LẠI MÔN CHẴN/HK2 (L_HL)
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
    # F. XUẤT FILE KẾT QUẢ CHO HỌC KỲ HIỆN TẠI
    # -------------------------------------------------------------------------
    print(f"\n9. Đang lưu bảng điểm đăng ký học phần cho học kỳ hiện tại {SEMESTER}...")
    df_enrollment = pd.DataFrame(enrollment_records)

    # Xuất file kết quả
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"enrollment_{SEMESTER.lower()}.csv"
    df_enrollment.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số bản ghi đăng ký trong {SEMESTER}: {len(df_enrollment):,} dòng.")

    # Thống kê chi tiết
    for ch in ["21", "22", "23", "24", "25", "26"]:
        cnt = len(df_enrollment[df_enrollment["student_id"].str.startswith(ch)])
        print(f"- Bản ghi K{ch}: {cnt:,} lượt học.")

    # Kiểm tra cột điểm quá trình so với cột điểm cuối kỳ
    in_term_count = df_enrollment["giua_ky"].notna().sum()
    final_exam_count = df_enrollment["cuoi_ky"].notna().sum()
    final_score_count = df_enrollment["final_score"].dropna().loc[lambda x: x != 12.0].count()
    print(f"- Số bản ghi có điểm quá trình (giữa kỳ/quiz/lab/btl): {in_term_count:,} lượt (phục vụ mô hình AI dự đoán rủi ro).")
    print(f"- Số bản ghi có điểm cuối kỳ (cuoi_ky): {final_exam_count} (Chưa thi).")
    print(f"- Số bản ghi có điểm tổng kết (final_score môn học bình thường): {final_score_count} (Chưa tổng kết).")

    return out_file


if __name__ == "__main__":
    generate_enrollment_hk261()

