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
    MAX_CREDITS,
    additional_courses,
    course_catalog,
    curriculum_courses,
    free_elective_courses,
    group_c_elective_courses,
    get_department,
)


SEMESTER = "HK161"
K13_COURSES = ["SP1037", "CO4029"]
K14_COURSES = curriculum_courses("HK5")
K15_COURSES = curriculum_courses("HK3")
K16_COURSES = curriculum_courses("HK1")
K14_EXTRA_COURSES = [
    code for code in additional_courses("HK5") if code not in K14_COURSES
]
K15_EXTRA_COURSES = [
    code for code in additional_courses("HK3") if code not in K15_COURSES
]
K16_EXTRA_COURSES = [
    code for code in additional_courses("HK1") if code not in K16_COURSES
]
FREE = free_elective_courses("HK7")
GROUP_C = group_c_elective_courses("HK7")
COURSE_ORDER = list(dict.fromkeys(
    K13_COURSES
    + K14_COURSES + K14_EXTRA_COURSES
    + K15_COURSES + K15_EXTRA_COURSES
    + K16_COURSES + K16_EXTRA_COURSES
    + FREE + GROUP_C
))

students = load_student_profiles()
lecturers = pd.read_csv(ROOT_DIR / "data" / "people" / "lecturer_for_class.csv")
history = load_history(("hk131", "hk132", "hk141", "hk142", "hk151", "hk152"))
prerequisites = pd.read_csv(ROOT_DIR / "data" / "catalog" / "course_prerequisite.csv")
course_names, course_credits, _ = course_catalog()

eligibility, _ = calculate_eligibility_for_schedule(
    students,
    history,
    course_credits,
    prerequisites,
    {"13": K13_COURSES, "14": K14_COURSES, "15": K15_COURSES, "16": K16_COURSES},
    {
        "14": K14_EXTRA_COURSES,
        "15": K15_EXTRA_COURSES,
        "16": K16_EXTRA_COURSES,
    },
    {
        "13": {"FREE": FREE, "GROUP_C": GROUP_C},
        "14": {"FREE": FREE, "GROUP_C": GROUP_C},
        "15": {"FREE": FREE, "GROUP_C": GROUP_C},
        "16": {"FREE": FREE, "GROUP_C": GROUP_C},
    },
    {
        "13": {"FREE": FREE, "GROUP_C": GROUP_C},
        "14": {"FREE": FREE, "GROUP_C": GROUP_C},
        "15": {"FREE": FREE, "GROUP_C": GROUP_C},
        "16": {"FREE": FREE, "GROUP_C": GROUP_C},
    },
    {
        "13": {"FREE": 3, "GROUP_C": 6},
    },
    semester_code=SEMESTER,
)

COURSE_ORDER = list(dict.fromkeys(
    COURSE_ORDER + [code for selected in eligibility.values() for code in selected]
))
class_data = assign_balanced_lecturers(
    course_order=COURSE_ORDER,
    eligibility=eligibility,
    lecturers=lecturers,
    course_names=course_names,
    semester=SEMESTER,
)

output = ROOT_DIR / "generated" / "classes" / "class_hk161.csv"
pd.DataFrame(class_data).to_csv(output, index=False, encoding="utf-8-sig")
print(f"Created {output.name}: {len(class_data)} classes")
print(f"Maximum credits per student: {MAX_CREDITS}")
