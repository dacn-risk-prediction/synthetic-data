import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "rules"))

from academic_rules import (
    MAX_CREDITS,
    add_gpa_summaries,
    allocate_course_rosters,
    assign_balanced_lecturers,
    balanced_class_sizes,
    calculate_eligibility_for_schedule,
    load_history,
    load_student_profiles,
    score_course_components,
    semester_index,
    students_by_course_from_eligibility,
)
from curriculum_rules import (
    additional_courses,
    course_catalog,
    curriculum_courses,
    free_elective_courses,
    group_c_elective_courses,
    management_elective_courses,
    get_department,
)


SEMESTERS = (
    "HK131", "HK132", "HK141", "HK142", "HK151", "HK152",
    "HK161", "HK162", "HK171", "HK172", "HK181", "HK182",
    "HK191", "HK192", "HK201", "HK202", "HK211", "HK212",
    "HK221", "HK222", "HK231", "HK232", "HK241", "HK242",
    "HK251", "HK252", "HK261", "HK262",
)
NEW_SEMESTERS = (
    "HK221", "HK222", "HK231", "HK232", "HK241", "HK242", "HK251", "HK252", "HK261"
)
ACTIVE_SEMESTER = "HK261"
PROJECT_OPTIONS = ["CO3107", "CO3109", "CO3111"]


def is_semester_active(semester: str) -> bool:
    """Kiểm tra học kỳ hiện tại có đang hoạt động hay không (chỉ HK261 là True)."""
    return str(semester).strip().upper() in ("HK261", "261")


def get_semesters_catalog() -> pd.DataFrame:
    """Trả về danh mục học kỳ với cột trạng thái is_active (True cho HK261, False cho các kỳ khác)."""
    csv_file = ROOT_DIR / "generated" / "academics" / "semester.csv"
    if csv_file.exists():
        return pd.read_csv(csv_file)
    from academics.generate_semester import generate_semesters
    return pd.DataFrame(generate_semesters())


def _cohort_term(cohort, semester):
    start = semester_index(f"HK{cohort}1")
    current = semester_index(semester)
    return current - start + 1


def _courses_for_term(term):
    if term in range(1, 6):
        return curriculum_courses(f"HK{term}")
    if term == 6:
        return ["SP1039", "CO2001", "CO3005", "CO3335"]
    if term == 7:
        return ["SP1037", "CO4029"]
    if term == 8:
        return ["SP1007", "CO4337"]
    return ["CO4029", "CO4337", "SP1037", "SP1007"]


def _schedule(semester):
    current_index = semester_index(semester)
    is_term_2 = str(semester).upper().endswith("2")
    cohorts = {}
    additional = {}
    required_groups = {}
    optional_groups = {}
    required_credits = {}
    choices = {}
    all_courses = []

    management = management_elective_courses("HK4" if is_term_2 else "HK6")
    free = free_elective_courses("HK8" if is_term_2 else "HK7")
    group_c = group_c_elective_courses("HK8" if is_term_2 else "HK7")

    for cohort in range(13, 27):
        start = semester_index(f"HK{cohort}1")
        if start > current_index:
            continue
        term = _cohort_term(cohort, semester)
        if term < 1 or term > 12:
            continue
        prefix = str(cohort)
        scheduled = _courses_for_term(term)
        cohorts[prefix] = scheduled
        all_courses.extend(scheduled)

        # Extras: only for regular advancing cohorts (terms 1-7 in term 1, terms 1-6 in term 2)
        if (not is_term_2 and term <= 7) or (is_term_2 and term <= 6):
            extras = [
                code for code in additional_courses(f"HK{term}")
                if code not in scheduled
            ]
            if extras:
                additional[prefix] = extras
                all_courses.extend(extras)

        optional_groups[prefix] = {"FREE": free, "GROUP_C": group_c}

        if is_term_2:
            # Spring semester (HKxx2)
            if term <= 6:
                required_groups[prefix] = {"MANAGEMENT": management}
            else:
                required_groups[prefix] = {
                    "GROUP_C": group_c,
                    "MANAGEMENT": management,
                    "FREE": free,
                }

            if term == 6:
                required_credits[prefix] = {"MANAGEMENT": 3}
                choices[prefix] = {"INTERDISCIPLINARY_PROJECT": PROJECT_OPTIONS}
                all_courses.extend(PROJECT_OPTIONS)
            elif term == 8:
                # Graduation semester
                required_credits[prefix] = {"GROUP_C": 9, "MANAGEMENT": 3}
            elif term >= 10:
                # Late semesters
                required_credits[prefix] = {
                    "FREE": 9,
                    "GROUP_C": 15,
                    "MANAGEMENT": 3,
                }
        else:
            # Fall semester (HKxx1)
            if term >= 9:
                required_groups[prefix] = {
                    "FREE": free,
                    "GROUP_C": group_c,
                    "MANAGEMENT": management,
                }
                required_credits[prefix] = {
                    "FREE": 9,
                    "GROUP_C": 15,
                    "MANAGEMENT": 3,
                }
            elif term == 7:
                required_groups[prefix] = {
                    "FREE": free,
                    "GROUP_C": group_c,
                }
                required_credits[prefix] = {"FREE": 3, "GROUP_C": 6}
            else:
                # terms 1, 3, 5
                required_groups[prefix] = {
                    "FREE": free,
                    "GROUP_C": group_c,
                }

    all_courses.extend(free + group_c + management)

    return (
        cohorts,
        additional,
        required_groups,
        optional_groups,
        required_credits,
        choices,
        list(dict.fromkeys(all_courses)),
    )


def _history_for(semester):
    current = semester_index(semester)
    return tuple(
        value.lower()
        for value in SEMESTERS
        if semester_index(value) < current
    )


def _eligibility(semester, students, history, credits, prerequisites):
    return calculate_eligibility_for_schedule(
        students,
        history,
        credits,
        prerequisites,
        *_schedule(semester)[:6],
        semester_code=semester,
    )


def generate_class(semester):
    students = load_student_profiles()
    lec_file = ROOT_DIR / "generated" / "users" / "lecturer.csv"
    lecturers = pd.read_csv(lec_file)
    if "user_id" in lecturers.columns and "lecturer_id" not in lecturers.columns:
        lecturers = lecturers.rename(columns={"user_id": "lecturer_id", "name": "lecturer_name", "department": "departments"})

    prereq_file = ROOT_DIR / "generated" / "academics" / "course_prerequisites.csv"
    prerequisites = pd.read_csv(prereq_file)

    course_names, course_credits, _ = course_catalog()
    history = load_history(_history_for(semester))
    schedule = _schedule(semester)
    eligibility, _ = _eligibility(
        semester, students, history, course_credits, prerequisites
    )

    course_order = list(dict.fromkeys(
        schedule[-1] + [
            code for selected in eligibility.values() for code in selected
        ]
    ))
    class_data = assign_balanced_lecturers(
        course_order=course_order,
        eligibility=eligibility,
        lecturers=lecturers,
        course_names=course_names,
        semester=semester,
    )

    output = ROOT_DIR / "generated" / "classes" / f"class_{semester.lower()}.csv"
    pd.DataFrame(class_data).to_csv(output, index=False, encoding="utf-8-sig")
    print(f"Created {output.name}: {len(class_data)} classes")
    print(f"Maximum credits per student: {MAX_CREDITS}")


def generate_enrollment(semester, is_current=None):
    if is_current is None:
        is_current = is_semester_active(semester)

    students = load_student_profiles()
    classes = pd.read_csv(
        ROOT_DIR / "generated" / "classes" / f"class_{semester.lower()}.csv"
    )
    assess_file = ROOT_DIR / "generated" / "academics" / "assessment.csv"
    assessment = pd.read_csv(assess_file)

    prereq_file = ROOT_DIR / "generated" / "academics" / "course_prerequisites.csv"
    prerequisites = pd.read_csv(prereq_file)

    history = load_history(_history_for(semester))
    _, course_credits, difficulties = course_catalog()
    eligibility, failed = _eligibility(
        semester, students, history, course_credits, prerequisites
    )

    components = {}
    for item in assessment.itertuples(index=False):
        weights = [
            (name, float(getattr(item, name)) / 100)
            for name in ("quiz", "lab", "btl", "giua_ky", "cuoi_ky")
            if pd.notna(getattr(item, name)) and float(getattr(item, name)) > 0
        ]
        components[item.course_id] = weights or [("cuoi_ky", 1.0)]

    students_by_id = students.set_index("student_id")
    students_by_course = students_by_course_from_eligibility(eligibility)
    for course_code, student_ids in students_by_course.items():
        seed = int(hashlib.sha256(
            f"{semester}:{course_code}:roster".encode()
        ).hexdigest()[:8], 16)
        students_by_course[course_code] = np.random.default_rng(seed).permutation(
            student_ids
        ).tolist()
    course_rosters = allocate_course_rosters(students_by_course, classes)

    records = []
    enrollment_id = 1
    for course_code in classes["course_code"].drop_duplicates():
        for class_id, chunk in course_rosters.get(course_code, []):
            for student_id in chunk:
                student = students_by_id.loc[student_id]
                retake = course_code in failed.get(student_id, set())
                rng = np.random.default_rng(int(hashlib.sha256(
                    f"{semester}:{student_id}:{course_code}:score".encode()
                ).hexdigest()[:8], 16))
                record = {
                    "enrollment_id": enrollment_id,
                    "student_id": student_id,
                    "class_id": class_id,
                    "course_id": course_code,
                    "semester": semester_index(semester),
                    "retaken": retake,
                }
                if is_current:
                    scores, _, _, _ = score_course_components(
                        student,
                        course_code,
                        components.get(course_code, [("cuoi_ky", 1.0)]),
                        difficulties.get(course_code, 0.0),
                        rng,
                        retaken=retake,
                        student_id=student_id,
                    )
                    # For current ongoing semester, final exam has not occurred yet
                    scores["cuoi_ky"] = np.nan
                    record.update(scores)
                    record.update({
                        "final_score": np.nan,
                        "letter_grade": np.nan,
                        "gpa_4": np.nan,
                        "passed": np.nan,
                        "status": np.nan,
                    })
                else:
                    scores, final_score, letter, gpa = score_course_components(
                        student,
                        course_code,
                        components.get(course_code, [("cuoi_ky", 1.0)]),
                        difficulties.get(course_code, 0.0),
                        rng,
                        retaken=retake,
                        student_id=student_id,
                    )
                    record.update(scores)
                    record.update({
                        "final_score": final_score,
                        "letter_grade": letter,
                        "gpa_4": gpa,
                        "passed": letter != "F",
                        "status": "Pass" if letter != "F" else "Fail",
                    })
                records.append(record)
                enrollment_id += 1

    if is_current:
        result = pd.DataFrame(records)
        result["semester_gpa_4"] = np.nan
        result["final_gpa_4"] = np.nan
    else:
        result = add_gpa_summaries(pd.DataFrame(records), history, course_credits)

    base = ["enrollment_id", "student_id", "class_id", "course_id", "semester", "retaken"]
    end = [
        "final_score", "letter_grade", "gpa_4", "passed",
        "semester_gpa_4", "final_gpa_4", "status",
    ]
    components_in_result = [c for c in result.columns if c not in base + end]
    for comp in ["quiz", "lab", "btl", "giua_ky", "cuoi_ky"]:
        if comp not in components_in_result:
            result[comp] = np.nan
            components_in_result.append(comp)
    result = result[base + components_in_result + end]
    output = ROOT_DIR / "generated" / "enrollments" / f"enrollment_{semester.lower()}.csv"
    result.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"Created {output.name}: {len(result)} enrollment records")
    print(f"Maximum credits per student: {MAX_CREDITS}")
