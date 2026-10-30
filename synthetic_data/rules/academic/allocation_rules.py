"""Course section capacity balancing, instructor workload assignment, and student roster allocation."""

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from curriculum_rules import get_department as catalog_department


def balanced_class_sizes(demand: int, max_size: int = 120) -> List[int]:
    """Use the fewest sections possible and balance them within the capacity limit."""
    demand = int(demand)
    max_size = int(max_size)
    if demand < 0:
        raise ValueError("Class demand cannot be negative")
    if max_size <= 0:
        raise ValueError("Class capacity must be positive")
    if demand == 0:
        return []
    class_count = math.ceil(demand / max_size)
    base_size, remainder = divmod(demand, class_count)
    return [
        base_size + (1 if index < remainder else 0)
        for index in range(class_count)
    ]


def assign_balanced_lecturers(
    course_order: List[str],
    eligibility: Union[Dict[str, List[str]], Dict[str, int]],
    lecturers: pd.DataFrame,
    course_names: Dict[str, str],
    semester: str,
    max_size: int = 120,
) -> List[Dict[str, Any]]:
    """Assign lecturers to classes across courses in a semester in a balanced round-robin manner per department.

    Parameters:
    - course_order: sequence of course codes to create classes for
    - eligibility: dict mapping student_id -> list/set of selected courses, or course_code -> int demand
    - lecturers: DataFrame containing 'lecturer_id', 'departments', 'lecturer_name'
    - course_names: dict mapping course_code -> course_name
    - semester: semester code (e.g. 'HK221')
    - max_size: maximum class capacity (default: 120)

    Returns:
    - list of dicts representing classes
    """
    if not eligibility:
        return []

    # Precompute demand per course
    first_val = next(iter(eligibility.values()))
    if isinstance(first_val, (int, np.integer, float)):
        demands = {code: int(demand) for code, demand in eligibility.items()}
    else:
        demands = {}
        for selected in eligibility.values():
            for code in selected:
                demands[code] = demands.get(code, 0) + 1

    lecturer_names = dict(zip(lecturers["lecturer_id"], lecturers["lecturer_name"]))
    dept_lecturers: Dict[str, List[str]] = {}
    for dept, group in lecturers.groupby("departments", sort=False):
        dept_lecturers[dept] = group["lecturer_id"].tolist()
    dept_pointers = {dept: 0 for dept in dept_lecturers}

    class_data: List[Dict[str, Any]] = []
    for course_code in course_order:
        demand = demands.get(course_code, 0)
        if not demand:
            continue
        if course_code not in course_names:
            raise ValueError(f"Courses missing from course.csv: {course_code}")

        dept = catalog_department(course_code)
        dept_ids = dept_lecturers.get(dept)
        if not dept_ids:
            dept_ids = lecturers.loc[
                lecturers["departments"] == dept,
                "lecturer_id",
            ].tolist() or ["UNKNOWN_ID"]
            dept_lecturers[dept] = dept_ids
            dept_pointers[dept] = 0

        for index, _ in enumerate(
            balanced_class_sizes(demand, max_size=max_size), start=1
        ):
            group = f"L{index:02d}"
            ptr = dept_pointers[dept]
            lecturer_id = dept_ids[ptr % len(dept_ids)]
            dept_pointers[dept] = ptr + 1
            class_data.append({
                "class_id": f"{semester}_{course_code}_{group}",
                "course_code": course_code,
                "course_name": course_names[course_code],
                "semester": semester,
                "class_group": group,
                "lecturer_id": lecturer_id,
                "lecturer_name": lecturer_names.get(lecturer_id, "Unknown Name"),
            })

    return class_data


def students_by_course_from_eligibility(eligibility: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Invert student->courses eligibility mapping into course->students mapping."""
    students_by_course: Dict[str, List[str]] = {}
    for student_id, courses in eligibility.items():
        for course_code in courses:
            students_by_course.setdefault(course_code, []).append(student_id)
    return students_by_course


def allocate_course_rosters(
    students_by_course: Dict[str, List[str]],
    classes: pd.DataFrame,
    max_size: int = 120,
) -> Dict[str, List[Tuple[str, List[str]]]]:
    """Assign every eligible student to an existing same-course class within capacity."""
    required_columns = {"class_id", "course_code"}
    if not required_columns.issubset(classes.columns):
        missing = sorted(required_columns - set(classes.columns))
        raise ValueError(f"Class data is missing columns: {', '.join(missing)}")
    if classes["class_id"].duplicated().any():
        duplicates = classes.loc[
            classes["class_id"].duplicated(), "class_id"
        ].head(5).tolist()
        raise ValueError(f"Duplicate class IDs: {duplicates}")

    classes_by_course = {
        course_code: group["class_id"].tolist()
        for course_code, group in classes.groupby("course_code", sort=False)
    }
    rosters: Dict[str, List[Tuple[str, List[str]]]] = {}
    for course_code, student_ids in students_by_course.items():
        student_ids = list(student_ids)
        if not student_ids:
            continue
        if len(student_ids) != len(set(student_ids)):
            raise ValueError(f"Duplicate eligible student for {course_code}")
        class_ids = classes_by_course.get(course_code, [])
        if not class_ids:
            raise ValueError(
                f"No existing class is available for {len(student_ids)} "
                f"eligible students in {course_code}"
            )
        sizes = balanced_class_sizes(len(student_ids), max_size)
        if len(class_ids) < len(sizes):
            raise ValueError(
                f"{course_code} needs {len(sizes)} classes for "
                f"{len(student_ids)} students, but only {len(class_ids)} exist"
            )
        assignments: List[Tuple[str, List[str]]] = []
        offset = 0
        for class_id, size in zip(class_ids, sizes):
            assignments.append((class_id, student_ids[offset:offset + size]))
            offset += size
        rosters[course_code] = assignments
    return rosters

