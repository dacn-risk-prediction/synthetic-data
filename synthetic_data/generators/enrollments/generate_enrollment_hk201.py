"""Generate student course enrollments and academic grades for semester HK201 (Cohort K20 - Term 1).

Complies with HCMUT academic credit regulations:
- High-quality (CLC) and Advanced (Tiên tiến) students are 100% exempt from all 4 English courses
  (LA1003, LA1005, LA1007, LA1009), each receiving final_score = 12.0, class_id = NULL, letter_grade = NULL,
  gpa_4 = NULL, passed = True, status = 'Exempted'.
- Standard (Đại trà) students:
  * ~25% exempt from LA1003 (score 12.0, class_id = NULL, status = 'Exempted')
  * Remaining ~75% enroll in class sections HK201_LA1003_L01..L17 and are graded normally.
- All students take 4 compulsory courses (MT1003, PH1003, CO1005, CO1023) partitioned strictly by program
  (standard -> L, high-quality -> CC, advanced -> TT).
- Course component grades (quiz, lab, btl, giua_ky, cuoi_ky) simulated from student latent profiles
  (academic_level, math_level, discipline, motivation, stress) + course difficulty.
- Grade 12.0 is strictly excluded from GPA calculations (semester_gpa_4 and final_gpa_4), but counts
  towards accumulated credits for graduation.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

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
    course_mean_score,
    generate_student_profile,
    score_course_components,
)

SEMESTER = "HK201"
COHORT = "K20"
ENGLISH_COURSES = ["LA1003", "LA1005", "LA1007", "LA1009"]
COMPULSORY_REGULAR_COURSES = ["MT1003", "PH1003", "CO1005", "CO1023"]


def is_standard_exempt_la1003(student_id: str) -> bool:
    """Determine whether a Standard program student qualifies for English 1 (LA1003) exemption."""
    digest = hashlib.sha256(f"{student_id}:la1003_placement".encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    return (seed % 100) < 25


def generate_enrollment_hk201() -> Path:
    """Execute enrollment generation for semester HK201 and export to enrollment_hk201.csv."""
    print(f"=== KHỞI CHẠY SINH DỮ LIỆU ĐĂNG KÝ HỌC PHẦN (ENROLLMENT) CHO {SEMESTER} ===")

    # 1. Đọc dữ liệu sinh viên K20
    students_file = USERS_DIR / "student.csv"
    if not students_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {students_file}")

    df_students = pd.read_csv(students_file, encoding="utf-8-sig", dtype={"user_id": str})
    k20_students = df_students[df_students["user_id"].str.startswith("20")].copy()
    print(f"1. Tổng số sinh viên K20: {len(k20_students)}")

    # 2. Đọc danh sách lớp học phần HK201
    classes_file = CLASSES_DIR / "class_hk201.csv"
    if not classes_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file lớp: {classes_file}. Hãy chạy generate_class_hk201.py trước!")

    df_classes = pd.read_csv(classes_file, encoding="utf-8-sig")
    print(f"2. Tổng số lớp học phần đã mở: {len(df_classes)}")

    # 3. Đọc cấu trúc đánh giá môn học (assessment.csv)
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

    # 4. Đọc số tín chỉ môn học (courses.csv)
    courses_file = ACADEMICS_DIR / "courses.csv"
    df_courses = pd.read_csv(courses_file, encoding="utf-8-sig")
    credits_map: Dict[str, float] = dict(zip(df_courses["course_code"], df_courses["credits"].astype(float)))

    # 5. Đọc hồ sơ năng lực học tập cố định (student_profiles.csv)
    profiles_file = USERS_DIR / "student_profiles.csv"
    if not profiles_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {profiles_file}. Hãy chạy generate_student_profiles.py trước!")
    print(f"\n3. Đang đọc hồ sơ năng lực (student_profiles.csv) từ: {profiles_file}...")
    df_profiles = pd.read_csv(profiles_file, encoding="utf-8-sig", dtype={"student_id": str})
    student_profiles: Dict[str, Dict[str, Any]] = df_profiles.set_index("student_id").to_dict(orient="index")

    enrollment_records: List[Dict[str, Any]] = []
    enrollment_id = 1

    # 6. Phân bổ sinh viên vào lớp và tính điểm theo từng hệ đào tạo
    print("\n4. Phân bổ sinh viên vào lớp học phần và mô phỏng điểm số...")

    # Group classes by (program, course_code)
    classes_by_prog_course: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for _, r in df_classes.iterrows():
        classes_by_prog_course[(r["program"], r["course_code"])].append(r["class_id"])

    # Xử lý theo từng hệ đào tạo
    for prog in ["standard", "high-quality", "advanced"]:
        prog_students = k20_students[k20_students["program"] == prog].copy()
        student_ids = prog_students["user_id"].tolist()
        print(f"\n* Đang xử lý hệ: {prog} ({len(student_ids)} sinh viên)")

        # A. Xử lý 4 môn học bắt buộc thông thường (MT1003, PH1003, CO1005, CO1023)
        for course_code in COMPULSORY_REGULAR_COURSES:
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            if not class_ids:
                raise ValueError(f"Không tìm thấy lớp học phần nào cho môn {course_code} - hệ {prog}")

            # Chia đều danh sách sinh viên vào các lớp của hệ đó
            sizes = balanced_class_sizes(len(student_ids), max_size=40)
            offset = 0

            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_students = student_ids[offset : offset + size]
                offset += size

                for uid in assigned_students:
                    profile = student_profiles[uid]
                    student_data = {"student_id": uid, **profile}

                    # Seed ngẫu nhiên tất định cho lượt học
                    seed_str = f"{uid}:{course_code}:{SEMESTER}"
                    rng = np.random.default_rng(
                        int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
                    )

                    # Chấm điểm thành phần
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

        # B. Xử lý các môn Anh văn
        if prog in ("high-quality", "advanced"):
            # CLC và Tiên tiến: Miễn luôn cả 4 học phần tiếng Anh ngay từ HK201 (score 12)
            for eng_course in ENGLISH_COURSES:
                for uid in student_ids:
                    rec = {
                        "enrollment_id": enrollment_id,
                        "student_id": uid,
                        "class_id": np.nan,  # Không có lớp
                        "course_id": eng_course,
                        "semester": SEMESTER,
                        "retaken": False,
                        "quiz": np.nan,
                        "lab": np.nan,
                        "btl": np.nan,
                        "giua_ky": np.nan,
                        "cuoi_ky": np.nan,
                        "final_score": 12.0,  # Điểm 12 quy ước miễn
                        "letter_grade": np.nan,
                        "gpa_4": np.nan,
                        "passed": True,
                        "status": "Exempted",
                    }
                    enrollment_records.append(rec)
                    enrollment_id += 1
            print(f"   -> Đã tạo bản ghi miễn (điểm 12) trọn gói 4 môn Anh văn ({', '.join(ENGLISH_COURSES)}) cho {len(student_ids)} SV.")

        else:
            # Hệ Đại trà (standard): Chỉ học/miễn môn LA1003 trong HK1
            course_code = "LA1003"
            exempt_uids = [uid for uid in student_ids if is_standard_exempt_la1003(uid)]
            take_uids = [uid for uid in student_ids if uid not in set(exempt_uids)]

            # 1. Sinh viên được miễn LA1003 (điểm 12)
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

            # 2. Sinh viên học LA1003 bình thường
            class_ids = classes_by_prog_course.get((prog, course_code), [])
            sizes = balanced_class_sizes(len(take_uids), max_size=40)
            offset = 0
            comps = course_assessments.get(course_code, [("cuoi_ky", 1.0)])

            for class_id, size in zip(class_ids, sizes):
                assigned_students = take_uids[offset : offset + size]
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

            print(f"   -> Hệ Đại trà: {len(exempt_uids)} SV miễn AV1 (điểm 12), {len(take_uids)} SV vào {len(class_ids)} lớp học thường.")

    # 7. Tính toán GPA học kỳ & tích lũy (loại trừ điểm 12)
    print("\n5. Đang tính điểm trung bình học kỳ (semester_gpa_4) và tích lũy (final_gpa_4)...")
    df_enrollment = pd.DataFrame(enrollment_records)

    semester_gpas: Dict[str, float] = {}
    final_gpas: Dict[str, float] = {}

    for uid, attempts in df_enrollment.groupby("student_id"):
        weighted_points = 0.0
        attempted_credits = 0.0

        passed_points = 0.0
        passed_credits = 0.0

        for _, att in attempts.iterrows():
            score = att["final_score"]
            gpa4 = att["gpa_4"]

            # Bỏ qua điểm 12 khi tính GPA
            if pd.isna(score) or float(score) == 12.0 or pd.isna(gpa4):
                continue

            cid = att["course_id"]
            tc = credits_map.get(cid, 0.0)

            weighted_points += float(gpa4) * tc
            attempted_credits += tc

            if att["passed"]:
                passed_points += float(gpa4) * tc
                passed_credits += tc

        # Điểm trung bình học kỳ (gồm cả điểm F)
        semester_gpas[uid] = round(weighted_points / attempted_credits, 2) if attempted_credits > 0 else np.nan

        # Điểm trung bình tích lũy HK1 (chỉ tính các môn đạt)
        final_gpas[uid] = round(passed_points / passed_credits, 2) if passed_credits > 0 else np.nan

    df_enrollment["semester_gpa_4"] = df_enrollment["student_id"].map(semester_gpas)
    df_enrollment["final_gpa_4"] = df_enrollment["student_id"].map(final_gpas)

    # 8. Sắp xếp thứ tự cột chuẩn hóa
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

    # 9. Xuất file CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"enrollment_{SEMESTER.lower()}.csv"
    df_enrollment.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {out_file} ===")
    print(f"Tổng số bản ghi đăng ký & điểm: {len(df_enrollment):,} dòng")

    print("\nThống kê theo trạng thái hoàn thành học phần:")
    print(df_enrollment["status"].value_counts())

    print("\nThống kê phân bổ điểm chữ:")
    print(df_enrollment["letter_grade"].value_counts(dropna=False))

    print("\nThống kê GPA trung bình theo hệ đào tạo:")
    merged_sv = df_enrollment.drop_duplicates(subset=["student_id"]).merge(
        k20_students[["user_id", "program"]], left_on="student_id", right_on="user_id"
    )
    print(merged_sv.groupby("program")[["semester_gpa_4", "final_gpa_4"]].mean().round(2))

    return out_file


if __name__ == "__main__":
    generate_enrollment_hk201()

