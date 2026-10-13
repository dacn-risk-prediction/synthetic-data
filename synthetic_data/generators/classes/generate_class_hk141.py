import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "rules"))

from academic_rules import (
    assign_balanced_lecturers,
    balanced_class_sizes,
    get_department,
    load_history,
    calculate_eligibility_for_schedule,
    load_student_profiles,
)
from curriculum_rules import (
    additional_courses,
    course_catalog,
    curriculum_courses,
)


SEMESTER = "HK141"
K13_COURSES = curriculum_courses("HK3")
K13_EXTRA_COURSES = [
    code for code in additional_courses("HK3") if code not in K13_COURSES
]
K14_COURSES = curriculum_courses("HK1")
COURSE_ORDER = list(dict.fromkeys(
    K13_COURSES + K13_EXTRA_COURSES + K14_COURSES
))

students = load_student_profiles()
lecturers = pd.read_csv(
    ROOT_DIR / "data" / "people" / "lecturer_for_class.csv"
)
history = load_history(("hk131", "hk132"))
prerequisites = pd.read_csv(ROOT_DIR / "data" / "catalog" / "course_prerequisite.csv")
course_names, course_credits, _ = course_catalog()

eligibility, _ = calculate_eligibility_for_schedule(
    students,
    history,
    course_credits,
    prerequisites,
    {"13": K13_COURSES, "14": K14_COURSES},
    {"13": K13_EXTRA_COURSES},
    semester_code=SEMESTER,
)

course_codes = list(dict.fromkeys(
    COURSE_ORDER
    + [
        code
        for selected in eligibility.values()
        for code in selected
    ]
))
class_data = assign_balanced_lecturers(
    course_order=course_codes,
    eligibility=eligibility,
    lecturers=lecturers,
    course_names=course_names,
    semester=SEMESTER,
)

output = ROOT_DIR / "generated" / "classes" / "class_hk141.csv"
pd.DataFrame(class_data).to_csv(output, index=False, encoding="utf-8-sig")
print(f"Created {output.name}: {len(class_data)} classes")
