

import pandas as pd

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "rules"))
from academic_rules import (
    assign_balanced_lecturers,
    balanced_class_sizes,
    get_exempted_english_courses,
    load_student_profiles,
)
from curriculum_rules import course_catalog, curriculum_courses, get_department


SEMESTER = "HK131"
CURRICULUM_SEMESTER = "HK1"
students = load_student_profiles()
lecturers = pd.read_csv(ROOT_DIR / "data" / "people" / "lecturer_for_class.csv")
student_ids = students.loc[
    students["student_id"].str.startswith("13"), "student_id"
].tolist()
course_names, _, _ = course_catalog()
course_codes = curriculum_courses(CURRICULUM_SEMESTER)

missing = [code for code in course_codes if code not in course_names]
if missing:
    raise ValueError("Courses missing from course.csv: " + ", ".join(missing))

course_demands = {
    code: (
        sum(
            "LA1003" not in get_exempted_english_courses(student)
            for student in students.loc[
                students["student_id"].str.startswith("13")
            ].itertuples(index=False)
        )
        if code == "LA1003"
        else len(student_ids)
    )
    for code in course_codes
}
class_data = assign_balanced_lecturers(
    course_order=course_codes,
    eligibility=course_demands,
    lecturers=lecturers,
    course_names=course_names,
    semester=SEMESTER,
)

output = ROOT_DIR / "generated" / "classes" / "class_hk131.csv"
pd.DataFrame(class_data).to_csv(output, index=False, encoding="utf-8-sig")
print(f"Created {output.name}: {len(class_data)} classes")
