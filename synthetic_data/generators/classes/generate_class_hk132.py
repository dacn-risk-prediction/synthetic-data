import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "rules"))
from academic_rules import (
    assign_balanced_lecturers,
    balanced_class_sizes,
    calculate_eligibility_for_schedule,
    load_history,
    load_student_profiles,
)
from curriculum_rules import (
    additional_courses,
    course_catalog,
    curriculum_courses,
    get_department,
)


SEMESTER = "HK132"
CURRICULUM_SEMESTER = "HK2"
students = load_student_profiles()
lecturers = pd.read_csv(ROOT_DIR / "data" / "people" / "lecturer_for_class.csv")
student_ids = students.loc[
    students["student_id"].str.startswith("13"), "student_id"
].tolist()
course_names, course_credits, _ = course_catalog()
standard_courses = curriculum_courses(CURRICULUM_SEMESTER)
extra_courses = [
    code for code in additional_courses(CURRICULUM_SEMESTER)
    if code not in standard_courses
]
history = load_history(("hk131",))
prerequisites = pd.read_csv(ROOT_DIR / "data" / "catalog" / "course_prerequisite.csv")
eligibility, _ = calculate_eligibility_for_schedule(
    students,
    history,
    course_credits,
    prerequisites,
    {"13": standard_courses},
    {"13": extra_courses},
    semester_code=SEMESTER,
)

course_codes = list(dict.fromkeys(
    standard_courses
    + extra_courses
    + [code for selected in eligibility.values() for code in selected]
))
class_data = assign_balanced_lecturers(
    course_order=course_codes,
    eligibility=eligibility,
    lecturers=lecturers,
    course_names=course_names,
    semester=SEMESTER,
)

output = ROOT_DIR / "generated" / "classes" / "class_hk132.csv"
pd.DataFrame(class_data).to_csv(output, index=False, encoding="utf-8-sig")
print(f"Created {output.name}: {len(class_data)} classes")
