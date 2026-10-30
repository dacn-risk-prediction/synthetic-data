"""Common shared utilities, path definitions, and helper functions for academic rules."""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from curriculum_rules import get_department as catalog_department

# Root directory pointing to synthetic_data/
ROOT_DIR = Path(__file__).resolve().parents[2]


def _stable_seed(student_id_or_val: Any, config: Optional[Dict[str, Any]] = None, salt: Optional[str] = None) -> int:
    """Deterministic hash seed. Supports either (val) or (student_id, config, salt)."""
    if config is not None and salt is not None:
        value = f"{config['seed']}:{student_id_or_val}:{salt}".encode("utf-8")
        return int(hashlib.sha256(value).hexdigest()[:8], 16)
    return int(hashlib.md5(str(student_id_or_val).encode("utf-8")).hexdigest(), 16) % (2**32)


def filter_students_from_2020(students: pd.DataFrame, min_cohort: int = 20) -> pd.DataFrame:
    """Filter students DataFrame to only include real students from 2020 (K20) onwards."""
    if students is None or students.empty:
        return students

    def is_valid_student(student_id: Any) -> bool:
        if not isinstance(student_id, str):
            student_id = str(student_id)
        if len(student_id) >= 2 and student_id[:2].isdigit():
            cohort = int(student_id[:2])
            return cohort >= min_cohort
        return False

    mask = students["student_id"].apply(is_valid_student)
    return students[mask].copy()


def filter_students_from_2013(students: pd.DataFrame) -> pd.DataFrame:
    """Legacy filter for students from 2013 onward."""
    return filter_students_from_2020(students, min_cohort=13)


def cohort_year(student_id: Any) -> int:
    """Extract cohort year from student ID (e.g. '2010001' -> 20)."""
    student_id = str(student_id).strip()
    prefix = student_id[:2]
    if not prefix.isdigit() or len(prefix) != 2:
        raise ValueError(
            f"Student ID must start with a two-digit cohort year: {student_id}"
        )
    return int(prefix)


def _student_value(student: Any, field: str, default: Any = None) -> Any:
    """Safely extract field from dict, namedtuple, Series or object."""
    if hasattr(student, "get"):
        return student.get(field, default)
    return getattr(student, field, default)


def _student_flag(student: Any, field: str, default: bool = False) -> bool:
    """Extract boolean flag safely from student object."""
    value = _student_value(student, field, default)
    if pd.isna(value):
        return default
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "1", "yes"}
    return bool(value)


def _normalized_trait(value: Any, default: float = 0.5) -> float:
    """Normalize personality trait to [-1.0, 1.0]."""
    return (float(value) - 3.0) / 2.0 if value is not None and not pd.isna(value) else default


def load_course_data() -> Tuple[Dict[str, str], Dict[str, float], Dict[str, float]]:
    """Load course catalog information."""
    from curriculum_rules import course_catalog
    names, credits, difficulties = course_catalog()
    return names, credits, difficulties


def load_history(semesters: Tuple[str, ...] = ("hk231", "hk232")) -> pd.DataFrame:
    """Load historical enrollment and class records for specified semesters."""
    history = []
    for semester in semesters:
        enrollment_file = ROOT_DIR / "generated" / "enrollments" / f"enrollment_{semester}.csv"
        class_file = ROOT_DIR / "generated" / "classes" / f"class_{semester}.csv"
        if enrollment_file.exists() and class_file.exists():
            enrollment = pd.read_csv(enrollment_file, dtype={"student_id": str})
            classes = pd.read_csv(class_file)[["class_id", "course_code"]]
            history.append(pd.merge(enrollment, classes, on="class_id"))
    if not history:
        return pd.DataFrame(columns=["student_id", "course_code", "status"])
    return pd.concat(history, ignore_index=True)


def get_department(course_code: str) -> str:
    """Get department responsible for teaching a course."""
    return catalog_department(course_code)


COHORT_START_SEMESTER: Dict[str, str] = {
    "20": "HK201",
    "21": "HK211",
    "22": "HK221",
    "23": "HK231",
    "24": "HK241",
    "25": "HK251",
    "26": "HK261",
    "K20": "HK201",
    "K21": "HK211",
    "K22": "HK221",
    "K23": "HK231",
    "K24": "HK241",
    "K25": "HK251",
    "K26": "HK261",
}

