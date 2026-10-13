import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "rules"))

from curriculum_rules import (
    MAX_CREDITS,
    additional_courses,
    course_catalog,
    curriculum_courses,
    management_elective_courses,
    free_elective_courses,
    get_department,
)
from academic_rules import (
    assign_balanced_lecturers,
    balanced_class_sizes,
    calculate_eligibility_for_schedule,
    load_history,
    load_student_profiles,
)


SEMESTER = "HK142"
K13_COURSES = list(dict.fromkeys(
    curriculum_courses("HK4")
))
K13_EXTRA_COURSES = [
    code for code in additional_courses("HK4") if code not in K13_COURSES
]
K14_COURSES = list(dict.fromkeys(
    curriculum_courses("HK2")
))
K14_EXTRA_COURSES = [
    code for code in additional_courses("HK2") if code not in K14_COURSES
]
COURSE_ORDER = list(dict.fromkeys(
    K13_COURSES
    + K13_EXTRA_COURSES
    + management_elective_courses("HK4")
    + free_elective_courses("HK4")
    + K14_COURSES
    + K14_EXTRA_COURSES
))
students = load_student_profiles()
lecturers = pd.read_csv(ROOT_DIR / "data" / "people" / "lecturer_for_class.csv")
history = load_history(("hk131", "hk132", "hk141"))
course_names, course_credits, _ = course_catalog()
missing = [code for code in COURSE_ORDER if code not in course_names]
if missing:
    raise ValueError("Courses missing from course.csv: " + ", ".join(missing))

prerequisites = pd.read_csv(ROOT_DIR / "data" / "catalog" / "course_prerequisite.csv")
eligibility, _ = calculate_eligibility_for_schedule(
    students,
    history,
    course_credits,
    prerequisites,
    {"13": K13_COURSES, "14": K14_COURSES},
    {"13": K13_EXTRA_COURSES, "14": K14_EXTRA_COURSES},
    {"13": {"MANAGEMENT": management_elective_courses("HK4")}},
    {"13": {"FREE": free_elective_courses("HK4")}},
    semester_code=SEMESTER,
)
COURSE_ORDER = list(dict.fromkeys(
    COURSE_ORDER
    + [code for selected in eligibility.values() for code in selected]
))

class_data = assign_balanced_lecturers(
    course_order=COURSE_ORDER,
    eligibility=eligibility,
    lecturers=lecturers,
    course_names=course_names,
    semester=SEMESTER,
)

output = ROOT_DIR / "generated" / "classes" / "class_hk142.csv"
pd.DataFrame(class_data).to_csv(output, index=False, encoding="utf-8-sig")
print(f"Created {output.name}: {len(class_data)} classes")
print(f"K13 students: {sum(s.startswith('13') for s in eligibility)}")
print(f"K14 students: {sum(s.startswith('14') for s in eligibility)}")
print(f"Credit limit per student: {MAX_CREDITS}")
