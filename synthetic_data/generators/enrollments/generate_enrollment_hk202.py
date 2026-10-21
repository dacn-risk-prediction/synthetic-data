"""Generate student course enrollments and academic grades for semester HK202 (Cohort K20 - Term 2).

Complies with HCMUT academic credit regulations:
1. Standard compulsory courses: CO1007, MT1005, MT1007, PH1007, CO1027.
2. English 2 (LA1005): Standard program students who passed/exempted English 1 (LA1003) enroll in LA1005.
   High-quality and Advanced students were already exempted from LA1003..LA1009 in HK201.
3. English 1 (LA1003) retake: If retake section opened in class_hk202.csv (demand >= 20),
   failed students re-enroll with retaken=True.
4. Course acceleration (Học vượt) per rules/additional_course_rules.csv:
   Students with under 18 credits (e.g. English-exempt) and strong academic baseline
   can accelerate CO2001 (Kỹ năng Chuyên nghiệp cho Kỹ sư, 3 credits) starting from HK2.
5. Cumulative GPA (final_gpa_4) aggregates passed courses across both HK201 and HK202.
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

SEMESTER = "HK202"
COHORT = "K20"
CORE_COURSES = ["CO1007", "MT1005", "MT1007", "PH1007", "CO1027"]


def get_acceleration_students(k20_students: pd.DataFrame, df_prof: pd.DataFrame) -> Dict[str, List[str]]:
    """Identify students taking accelerated course CO2001 (from additional_course_rules.csv)."""
    prof_by_id = df_prof.set_index("student_id").to_dict(orient="index")
    accelerating_by_prog: Dict[str, List[str]] = defaultdict(list)
    for _, row in k20_students.iterrows():
        uid = str(row["user_id"])
        prog = row["program"]
        p = prof_by_id.get(uid, {})
        base_score = float(p.get("base_score", 0.0) or 0.0)
        is_early_candidate = str(p.get("early_graduation_candidate", "")).lower() == "true"

        seed_val = int(hashlib.sha256(f"{uid}:co2001_accel".encode()).hexdigest()[:8], 16)
        prob = seed_val % 100

        if is_early_candidate or (base_score >= 7.8 and prob < 35):
            accelerating_by_prog[prog].append(uid)

    return accelerating_by_prog


def generate_enrollment_hk202() -> Path:
    """Execute enrollment generation for semester HK202 and export to enrollment_hk202.csv."""
    print(f"=== KHỞI CHẠY SINH DỮ LIỆU ĐĂNG KÝ HỌC PHẦN (ENROLLMENT) CHO {SEMESTER} ===")

    # 1. Đọc dữ liệu sinh viên K20
    students_file = USERS_DIR / "student.csv"
    if not students_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {students_file}")

    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    print(f"1. Tổng số sinh viên K20: {len(k20_students)}")

    # 2. Đọc danh sách lớp học phần HK202
    classes_file = CLASSES_DIR / "class_hk202.csv"
    if not classes_file.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file lớp: {classes_file}. Hãy chạy generate_class_hk202.py trước!"
        )
    df_classes = pd.read_csv(classes_file, encoding="utf-8-sig")
    print(f"2. Tổng số lớp học phần đã mở cho HK202: {len(df_classes)}")

    # 3. Đọc kết quả học tập HK201
    enr_hk201_file = OUTPUT_DIR / "enrollment_hk201.csv"
    if not enr_hk201_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file kết quả HK201: {enr_hk201_file}")
    df_hk201 = pd.read_csv(enr_hk201_file, encoding="utf-8-sig", dtype={"student_id": str})

    la1003_passed_students = set(
        df_hk201[
            (df_hk201["course_id"] == "LA1003")
            & ((df_hk201["passed"] == True) | (df_hk201["status"] == "Exempted"))
        ]["student_id"].tolist()
    )
    la1003_failed_students = set(
        df_hk201[
            (df_hk201["course_id"] == "LA1003") & (df_hk201["passed"] == False)
        ]["student_id"].tolist()
    )

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
    if not profiles_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {profiles_file}")
    df_profiles = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    student_profiles: Dict[str, Dict[str, Any]] = df_profiles.set_index("student_id").to_dict(
        orient="index"
    )

    # 7. Nhận diện sinh viên học vượt (additional_course_rules.csv)
    accel_students = get_acceleration_students(k20_students, df_profiles)
    total_accel = sum(len(uids) for uids in accel_students.values())
    print(f"3. Sinh viên đăng ký học vượt CO2001: {total_accel} SV.")

    # Kiểm tra có mở lớp học lại LA1003 không
    retake_classes_la1003 = df_classes[
        (df_classes["course_code"] == "LA1003") & (df_classes["class_group"].str.contains("HL"))
    ]

    enrollment_records: List[Dict[str, Any]] = []
    enrollment_id = len(df_hk201) + 1

    # 8. Phân bổ sinh viên vào lớp và tính điểm
    print("\n4. Phân bổ sinh viên vào lớp học phần và mô phỏng điểm số HK202...")
    classes_by_prog_course: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, r in df_classes.iterrows():
        classes_by_prog_course[(r["program"], r["course_code"])].append(r["class_id"])

    for prog in ["standard", "high-quality", "advanced"]:
        prog_students = k20_students[k20_students["program"] == prog].copy()
        student_ids = prog_students["user_id"].tolist()
        print(f"\n* Đang xử lý hệ: {prog} ({len(student_ids)} sinh viên)")

        # A. 5 môn học bắt buộc cốt lõi (CO1007, MT1005, MT1007, PH1007, CO1027)
        for course_code in CORE_COURSES:
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            if not class_ids:
                raise ValueError(f"Không tìm thấy lớp học phần cho môn {course_code} - hệ {prog}")

            sizes = balanced_class_sizes(len(student_ids), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_students = student_ids[offset : offset + size]
                offset += size

                for uid in assigned_students:
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

                    rec: Dict[str, Any] = {
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

        # B. Anh văn 2 (LA1005) - Chỉ áp dụng cho hệ Đại trà đủ điều kiện
        if prog == "standard":
            course_code = "LA1005"
            eligible_uids = [uid for uid in student_ids if uid in la1003_passed_students]
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(eligible_uids), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_students = eligible_uids[offset : offset + size]
                offset += size

                for uid in assigned_students:
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

            print(f"   -> Hệ Đại trà: {len(eligible_uids)} SV học LA1005 vào {len(class_ids)} lớp.")

        # C. Môn học vượt CO2001 (Kỹ năng Chuyên nghiệp cho Kỹ sư)
        accel_uids = accel_students.get(prog, [])
        if accel_uids:
            course_code = "CO2001"
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(accel_uids), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_students = accel_uids[offset : offset + size]
                offset += size

                for uid in assigned_students:
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

            print(f"   -> [Học vượt] {len(accel_uids)} SV học vượt CO2001 vào {len(class_ids)} lớp.")

        # D. Môn học lại LA1003 (nếu có mở lớp)
        if not retake_classes_la1003.empty and prog == "standard":
            course_code = "LA1003"
            class_ids = retake_classes_la1003["class_id"].tolist()
            retake_uids = list(la1003_failed_students)
            sizes = balanced_class_sizes(len(retake_uids), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_students = retake_uids[offset : offset + size]
                offset += size

                for uid in assigned_students:
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    seed_str = f"{uid}:{course_code}:{SEMESTER}_retake"
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
                        retaken=True,
                        student_id=uid,
                    )

                    rec = {
                        "enrollment_id": enrollment_id,
                        "student_id": uid,
                        "class_id": class_id,
                        "course_id": course_code,
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

            print(f"   -> [Học lại] {len(retake_uids)} SV học lại LA1003.")

    # 9. Tính toán GPA học kỳ HK202 và GPA tích lũy toàn khóa (HK201 + HK202)
    print("\n5. Đang tính điểm trung bình học kỳ (semester_gpa_4) và GPA tích lũy (final_gpa_4)...")
    df_enrollment = pd.DataFrame(enrollment_records)

    hk201_passed_courses: Dict[str, Dict[str, float]] = defaultdict(dict)
    for _, r in df_hk201.iterrows():
        sid = str(r["student_id"])
        cid = str(r["course_id"])
        score = r["final_score"]
        gpa4 = r["gpa_4"]
        if pd.isna(score) or float(score) == 12.0 or pd.isna(gpa4):
            continue
        if r["passed"] == True:
            hk201_passed_courses[sid][cid] = float(gpa4)

    semester_gpas: Dict[str, float] = {}
    final_gpas: Dict[str, float] = {}

    for uid, attempts in df_enrollment.groupby("student_id"):
        hk2_points = 0.0
        hk2_credits = 0.0

        for _, att in attempts.iterrows():
            score = att["final_score"]
            gpa4 = att["gpa_4"]
            if pd.isna(score) or float(score) == 12.0 or pd.isna(gpa4):
                continue
            tc = credits_map.get(att["course_id"], 0.0)
            hk2_points += float(gpa4) * tc
            hk2_credits += tc

        semester_gpas[uid] = (
            round(hk2_points / hk2_credits, 2) if hk2_credits > 0 else np.nan
        )

        total_passed_points = 0.0
        total_passed_credits = 0.0

        # Lấy các môn đạt ở HK201
        current_passed = dict(hk201_passed_courses[uid])

        # Cập nhật các môn đạt ở HK202 (bao gồm cả môn học lại hoặc học vượt)
        for _, att in attempts.iterrows():
            if att["passed"] and pd.notna(att["gpa_4"]):
                cid = att["course_id"]
                current_passed[cid] = float(att["gpa_4"])

        for cid, g4 in current_passed.items():
            tc = credits_map.get(cid, 0.0)
            total_passed_points += g4 * tc
            total_passed_credits += tc

        final_gpas[uid] = (
            round(total_passed_points / total_passed_credits, 2)
            if total_passed_credits > 0
            else np.nan
        )

    df_enrollment["semester_gpa_4"] = df_enrollment["student_id"].map(semester_gpas)
    df_enrollment["final_gpa_4"] = df_enrollment["student_id"].map(final_gpas)

    # 10. Sắp xếp thứ tự cột chuẩn hóa
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

    # 11. Xuất file CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"enrollment_{SEMESTER.lower()}.csv"
    df_enrollment.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số bản ghi đăng ký & điểm HK202: {len(df_enrollment):,} dòng")

    print("\nThống kê theo trạng thái hoàn thành học phần:")
    print(df_enrollment["status"].value_counts())

    print("\nThống kê số lượng sinh viên học vượt CO2001:")
    co2001_enrs = df_enrollment[df_enrollment["course_id"] == "CO2001"]
    print(f"Tổng số sinh viên học vượt CO2001: {len(co2001_enrs)}")

    return out_file


if __name__ == "__main__":
    generate_enrollment_hk202()
