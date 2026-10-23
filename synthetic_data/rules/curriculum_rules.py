"""Academic Curriculum and Elective Rules.

Defines program structures, course catalogs, and elective course groupings
based directly on BKU ABET Computer Science & Engineering curriculum datasets
in generated/academics/ (program_structures.csv, courses.csv, curriculums.csv).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
ACADEMICS_DIR = ROOT_DIR / "generated" / "academics"
PROGRAM_STRUCTURES_FILE = ACADEMICS_DIR / "program_structures.csv"
COURSES_FILE = ACADEMICS_DIR / "courses.csv"
CURRICULUMS_FILE = ACADEMICS_DIR / "curriculums.csv"
RULE_FILE = ROOT_DIR / "rules" / "additional_course_rules.csv"

MAX_CREDITS = 22
TUITION_BASELINE_CREDITS = 18

MERGEABLE_PROGRAMS = ("high-quality", "advanced")


def can_share_class(prog1: str, prog2: str) -> bool:
    """Check if two programs can share the same class section.
    High-quality and Advanced programs can study together in the same class
    (both taught in English / Computer Science department).
    """
    if prog1 == prog2:
        return True
    return prog1 in MERGEABLE_PROGRAMS and prog2 in MERGEABLE_PROGRAMS


def get_shared_program_group(prog: str) -> str:
    """Return canonical program name for shared English classes."""
    if prog in MERGEABLE_PROGRAMS:
        return "high-quality"
    return prog


def load_curriculum(cohort: Optional[str] = "K20") -> pd.DataFrame:
    """Load curriculum structure for a cohort from program_structures.csv."""
    if not PROGRAM_STRUCTURES_FILE.exists():
        return pd.DataFrame(columns=["semester", "course_code", "course_order"])

    df = pd.read_csv(PROGRAM_STRUCTURES_FILE, dtype={"course_code": "string"})

    # Determine curriculum_id
    if cohort:
        c_str = str(cohort).strip().upper()
        curriculum_id = c_str if c_str.startswith("KHMT_") else f"KHMT_{c_str}"
        k_mask = df["curriculum_id"] == curriculum_id
        sub = df[k_mask].copy() if k_mask.any() else df[df["curriculum_id"] == "KHMT_K20"].copy()
    else:
        sub = df[df["curriculum_id"] == "KHMT_K20"].copy()

    if sub.empty:
        sub = df.copy()

    sub["semester"] = sub["recommended_semester"].fillna("")
    sub["course_order"] = sub["structure_id"]
    return sub[["semester", "course_code", "course_order"]].dropna(subset=["course_code"])


def load_rules() -> pd.DataFrame:
    """Load acceleration and additional course rules from additional_course_rules.csv."""
    if not RULE_FILE.exists():
        return pd.DataFrame(columns=["rule_id", "course_code", "available_from_semester", "priority"])
    return pd.read_csv(RULE_FILE, dtype={"course_code": "string"})


def load_electives(cohort: Optional[str] = "K20") -> pd.DataFrame:
    """Load Free Elective courses directly from program_structures.csv."""
    free_codes = ["IM1011", "IM1021", "IM1019", "IM3047", "ME4625", "CH4079", "E1013"]
    if PROGRAM_STRUCTURES_FILE.exists():
        df = pd.read_csv(PROGRAM_STRUCTURES_FILE, dtype={"course_code": "string"})
        mask = df["block_id"].fillna("").eq("FREE_ELECTIVE") | df["course_code"].isin(free_codes)
        sub = df[mask][["course_code"]].drop_duplicates().copy()
        if not sub.empty:
            sub["elective_group"] = "FREE"
            sub["available_from_semester"] = "HK5"
            sub["priority"] = 1
            return sub
    sub = pd.DataFrame({"course_code": free_codes})
    sub["elective_group"] = "FREE"
    sub["available_from_semester"] = "HK5"
    sub["priority"] = 1
    return sub


def load_management_electives(cohort: Optional[str] = "K20") -> pd.DataFrame:
    """Load Management Electives (Group D) directly from program_structures.csv."""
    if PROGRAM_STRUCTURES_FILE.exists():
        df = pd.read_csv(PROGRAM_STRUCTURES_FILE, dtype={"course_code": "string"})
        mask = (
            df["block_id"].fillna("").eq("MANAGEMENT")
            | df["elective_group"].fillna("").str.upper().isin(["GROUP D", "GROUP_D", "MANAGEMENT"])
        )
        sub = df[mask][["course_code"]].drop_duplicates().copy()
        if not sub.empty:
            sub["elective_group"] = "MANAGEMENT"
            sub["available_from_semester"] = "HK4"
            sub["priority"] = 1
            return sub
    fallback_codes = ["IM1013", "IM1023", "IM1025", "IM1027", "IM3001"]
    sub = pd.DataFrame({"course_code": fallback_codes})
    sub["elective_group"] = "MANAGEMENT"
    sub["available_from_semester"] = "HK4"
    sub["priority"] = 1
    return sub


_STUDENT_SPEC_MAP: Optional[Dict[str, str]] = None


def get_student_specialization_map() -> Dict[str, str]:
    """Retrieve mapping of student_id -> specialization from student_profiles.csv with caching."""
    global _STUDENT_SPEC_MAP
    if _STUDENT_SPEC_MAP is not None:
        return _STUDENT_SPEC_MAP
    profile_file = ROOT_DIR / "generated" / "users" / "student_profiles.csv"
    if profile_file.exists():
        df = pd.read_csv(profile_file, dtype=str)
        if "student_id" in df.columns and "specialization" in df.columns:
            _STUDENT_SPEC_MAP = dict(zip(df["student_id"], df["specialization"]))
            return _STUDENT_SPEC_MAP
    return {}


def get_specialization_group_c_courses(specialization: str, cohort: Optional[str] = None) -> List[str]:
    """Retrieve list of Group C course codes for a specific specialization and cohort."""
    if PROGRAM_STRUCTURES_FILE.exists():
        df = pd.read_csv(PROGRAM_STRUCTURES_FILE, dtype={"course_code": "string"})
        mask = (
            df["elective_group"].fillna("").str.upper().isin(["GROUP C", "GROUP_C"])
            | df["block_id"].fillna("").str.startswith("SPEC_")
        )
        if cohort:
            curr_id = f"KHMT_{cohort.upper()}"
            if curr_id in df["curriculum_id"].values:
                mask = mask & (df["curriculum_id"] == curr_id)
        if specialization:
            mask = mask & (df["specialization"] == specialization)

        courses = df[mask]["course_code"].dropna().unique().tolist()
        if courses:
            return courses

    fallback_map = {
        "Khoa học Máy tính": ["CO3011", "CO3021", "CO3029", "CO3043", "CO3045"],
        "Công nghệ Phần mềm": ["CO3011", "CO3013", "CO3015", "CO3017", "CO3065"],
        "Trí tuệ nhân tạo ứng dụng": ["CO3029", "CO3035", "CO3037", "CO3041", "CO3043", "CO3045"],
        "Trí tuệ nhân tạo": ["CO3061", "CO3029", "CO3045", "CO3057", "CO3085"],
        "Công nghệ Dữ liệu Bảo mật và Trí tuệ Kinh doanh": ["CO3021", "CO3023", "CO3027", "CO3029", "CO3033"],
        "Công nghệ dữ liệu và dữ liệu lớn": ["CO3021", "CO3027", "CO3029", "CO3033", "CO4031"],
        "Mật mã và An ninh mạng": ["CO3047", "CO3049", "CO3051", "CO3069", "CO3083"],
        "An ninh hệ thống và mạng": ["CO3049", "CO3051", "CO3069", "CO3033", "CO3151"],
        "Xử lý ảnh và Thị giác máy tính": ["CO3043", "CO3045", "CO3049", "CO3051", "CO3057"],
    }
    return fallback_map.get(specialization, ["CO3011", "CO3021", "CO3029", "CO3043", "CO3045"])


def select_student_group_c_course(
    student_id: str,
    cohort: str,
    specialization: Optional[str] = None,
    seed_salt: str = "group_c",
    exclude_courses: Optional[Set[str]] = None,
) -> str:
    """Select a Group C course deterministically matching the student's specialization."""
    if not specialization:
        spec_map = get_student_specialization_map()
        specialization = spec_map.get(str(student_id), "Khoa học Máy tính")

    spec_courses = get_specialization_group_c_courses(specialization, cohort)
    exclude = exclude_courses or set()
    available = [c for c in spec_courses if c not in exclude]

    if not available:
        all_group_c = load_group_c_electives(cohort=cohort)["course_code"].tolist()
        available = [c for c in all_group_c if c not in exclude]

    if not available:
        available = spec_courses if spec_courses else ["CO3011", "CO3021", "CO3029", "CO3043", "CO3045"]

    seed_val = int(hashlib.sha256(f"{student_id}:{seed_salt}".encode("utf-8")).hexdigest()[:8], 16)
    return available[seed_val % len(available)]


def load_group_c_electives(cohort: Optional[str] = "K20", specialization: Optional[str] = None) -> pd.DataFrame:
    """Load Specialized Electives (Group C) directly from program_structures.csv."""
    if PROGRAM_STRUCTURES_FILE.exists():
        df = pd.read_csv(PROGRAM_STRUCTURES_FILE, dtype={"course_code": "string"})
        mask = (
            df["elective_group"].fillna("").str.upper().isin(["GROUP C", "GROUP_C"])
            | df["block_id"].fillna("").str.startswith("SPEC_")
        )
        if cohort:
            curr_id = f"KHMT_{cohort.upper()}"
            if curr_id in df["curriculum_id"].values:
                mask = mask & (df["curriculum_id"] == curr_id)
        if specialization:
            mask = mask & (df["specialization"] == specialization)

        sub = df[mask][["course_code"]].drop_duplicates().copy()
        if not sub.empty:
            sub["elective_group"] = "GROUP_C"
            sub["available_from_semester"] = "HK6"
            sub["priority"] = 1
            return sub
    fallback_codes = ["CO3061", "CO3029", "CO3043", "CO3045", "CO3021", "CO3011"]
    sub = pd.DataFrame({"course_code": fallback_codes})
    sub["elective_group"] = "GROUP_C"
    sub["available_from_semester"] = "HK6"
    sub["priority"] = 1
    return sub


def curriculum_courses(semester: str, cohort: Optional[str] = "K20") -> List[str]:
    """Retrieve compulsory course codes for a given semester (e.g. 'HK1', 'HK2')."""
    curriculum = load_curriculum(cohort=cohort)
    rows = curriculum[
        (curriculum["semester"] == semester)
        & curriculum["course_code"].notna()
        & (curriculum["course_code"] != "")
    ].sort_values("course_order")
    return rows["course_code"].tolist()


def additional_courses(
    semester: str,
    *,
    early_graduation: bool = False,
    early_graduation_only: bool = False,
    cohort: Optional[str] = None,
) -> List[str]:
    """Retrieve acceleration courses available for a semester."""
    rules = load_rules()
    rows = rules[
        (rules["available_from_semester"] <= semester)
        & rules["course_code"].notna()
        & ~rules["course_code"].isin(["GROUP_C"])
    ].sort_values(["priority", "rule_id"])

    if not early_graduation:
        rows = rows[rows["activation_condition"] != "early_graduation_3_5_years"]
    elif early_graduation_only:
        rows = rows[
            rows["activation_condition"].eq("early_graduation_3_5_years")
            & rows["early_graduation_semester"].eq(semester)
        ]

    if cohort is not None and "applies_to_cohorts" in rows:
        cohort_code = str(cohort).upper()
        if not cohort_code.startswith("K"):
            cohort_code = f"K{cohort_code}"
        rows = rows[
            rows["applies_to_cohorts"].fillna("").apply(
                lambda value: cohort_code in str(value).split("|")
            )
        ]
    return rows["course_code"].tolist()


def free_elective_courses(semester: str) -> List[str]:
    """Retrieve free elective courses available for a semester."""
    electives = load_electives()
    rows = electives[
        (electives["elective_group"] == "FREE")
        & (electives["available_from_semester"] <= semester)
    ].sort_values(["priority", "course_code"])
    return rows["course_code"].tolist()


def management_elective_courses(semester: str) -> List[str]:
    """Retrieve management elective courses (Group D) available for a semester."""
    electives = load_management_electives()
    rows = electives[
        (electives["elective_group"] == "MANAGEMENT")
        & (electives["available_from_semester"] <= semester)
    ].sort_values(["priority", "course_code"])
    return rows["course_code"].tolist()


def group_c_elective_courses(semester: str) -> List[str]:
    """Retrieve specialized elective courses (Group C) available for a semester."""
    electives = load_group_c_electives()
    rows = electives[
        electives["elective_group"].eq("GROUP_C")
        & (electives["available_from_semester"] <= semester)
    ].sort_values(["priority", "course_code"])
    return rows["course_code"].tolist()


def ordered_courses(semester: str, *, early_graduation: bool = False, cohort: Optional[str] = "K20") -> List[str]:
    """Get unique combined list of compulsory and acceleration courses for a semester."""
    return list(dict.fromkeys(
        curriculum_courses(semester, cohort=cohort)
        + additional_courses(semester, early_graduation=early_graduation, cohort=cohort)
    ))


def course_catalog() -> Tuple[Dict[str, str], Dict[str, float], Dict[str, float]]:
    """Load master course catalog metadata directly from generated/academics/courses.csv."""
    if COURSES_FILE.exists():
        courses = pd.read_csv(COURSES_FILE)
        name_col = "course_name_vi" if "course_name_vi" in courses.columns else "course_name"
        names = dict(zip(courses["course_code"], courses[name_col]))
        credits = dict(zip(courses["course_code"], courses["credits"].astype(float)))
        difficulties = dict(zip(courses["course_code"], [0.5] * len(courses)))
        return names, credits, difficulties
    return {}, {}, {}


def validate_courses(course_codes: List[str], names: Dict[str, str]) -> None:
    """Validate that all courses in the curriculum exist in the catalog."""
    missing = [code for code in course_codes if code not in names]
    if missing:
        raise ValueError(
            "Courses in curriculum/rules missing from courses.csv: "
            + ", ".join(missing)
        )


def get_department(course_code: str) -> str:
    """Map course code to department identifier for lecturer assignment."""
    code = str(course_code).strip().upper()
    if code.startswith(("MI", "SP")):
        return "Triet"
    if code.startswith(("MT", "PH", "LA", "CH")):
        return "DaiCuong"
    return "ChuyenNganh"
