"""Academic standing, semester chronology, suspension, and academic dismissal regulations."""

from typing import Any, Dict, List, Optional, Set
import pandas as pd

from .common import ROOT_DIR
from .config import GENERATOR_CONFIG

STANDARD_SEMESTERS = 8
MAX_LATE_SEMESTERS = 4
DISMISSAL_AFTER_SEMESTERS = 12

_STANDING_PROFILES_CACHE = None


def _get_standing_profiles_cache() -> Dict[str, Dict[str, Any]]:
    global _STANDING_PROFILES_CACHE
    if _STANDING_PROFILES_CACHE is None:
        p_path = ROOT_DIR / "generated" / "users" / "student_profiles.csv"
        if p_path.exists():
            try:
                df = pd.read_csv(p_path, dtype={"student_id": str})
                _STANDING_PROFILES_CACHE = df.set_index("student_id").to_dict(orient="index")
            except Exception:
                _STANDING_PROFILES_CACHE = {}
        else:
            _STANDING_PROFILES_CACHE = {}
    return _STANDING_PROFILES_CACHE


def semester_index(semester_code: Any) -> int:
    """Calculate integer index for semester code (e.g. 'HK201' -> 15 under canonical semester chronology)."""
    code = str(semester_code).upper().strip()
    if len(code) != 5 or not code.startswith("HK") or not code[2:].isdigit():
        raise ValueError(f"Invalid semester code: {semester_code}")
    year = int(code[2:4])
    term = int(code[4])
    if term not in (1, 2):
        raise ValueError(f"Invalid semester term in {semester_code}")
    return (year - 13) * 2 + term


def semester_from_index(idx: int) -> str:
    """Convert integer semester index back to canonical semester code, e.g. 15 -> 'HK201'."""
    year = 13 + (idx - 1) // 2
    term = 1 if (idx % 2 != 0) else 2
    return f"HK{year}{term}"


def _get_cohort_start(student_id: Any, config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Retrieve cohort start semester code, with automatic fallback for valid cohorts (e.g. '20' -> 'HK201', '13' -> 'HK131')."""
    config = config or GENERATOR_CONFIG
    progress_config = config.get("student_progress", {})
    prefix = str(student_id)[:2]
    start = progress_config.get("cohort_start_semester", {}).get(prefix)
    if start is None and len(prefix) == 2 and prefix.isdigit():
        val = int(prefix)
        if 13 <= val <= 26:
            start = f"HK{prefix}1"
    return start


def get_late_semesters_count(student_id: str, semester_code: str, config: Optional[Dict[str, Any]] = None) -> int:
    """Calculate the number of late semesters for a student at a given semester.

    Returns:
        int: Number of late semesters (0 if on-time or early, 1-4 if within late allowance, >4 if overdue).
    """
    config = config or GENERATOR_CONFIG
    progress_config = config["student_progress"]
    cohort_start = _get_cohort_start(student_id, config)
    if cohort_start is None:
        return 0
    elapsed = semester_index(semester_code) - semester_index(cohort_start)
    standard_terms = progress_config["graduation"].get(
        "standard_semesters", STANDARD_SEMESTERS
    )
    return max(0, elapsed - standard_terms + 1)


def is_late_semester(student_id: str, semester_code: str, config: Optional[Dict[str, Any]] = None) -> bool:
    """Check if student is in an allowed late semester (1 to max_late_semesters late)."""
    late_count = get_late_semesters_count(student_id, semester_code, config)
    config = config or GENERATOR_CONFIG
    max_late = config.get("student_progress", {}).get("graduation", {}).get(
        "max_late_semesters", MAX_LATE_SEMESTERS
    )
    return 1 <= late_count <= max_late


def is_academic_dismissal(student_id: str, semester_code: str, config: Optional[Dict[str, Any]] = None) -> bool:
    """Check if student is dismissed for exceeding maximum allowed study duration.

    Under HCMUT academic regulations:
    - Standard curriculum duration: 8 semesters (4 years).
    - Maximum extension allowed: 4 late semesters (2 years).
    - Total maximum study duration: 12 semesters.
    After 12 semesters (i.e. at or after the 13th semester from cohort start),
    students who have not graduated are subjected to academic dismissal (buộc thôi học).
    """
    config = config or GENERATOR_CONFIG
    progress_config = config["student_progress"]
    cohort_start = _get_cohort_start(student_id, config)
    if cohort_start is None:
        return False
    elapsed = semester_index(semester_code) - semester_index(cohort_start)
    grad_config = progress_config.get("graduation", {})
    dismissal_threshold = grad_config.get(
        "dismissal_after_semesters",
        grad_config.get("standard_semesters", STANDARD_SEMESTERS)
        + grad_config.get("max_late_semesters", MAX_LATE_SEMESTERS),
    )
    return elapsed >= dismissal_threshold


def get_academic_dismissal_semester(student_id: str, config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Return the semester code where dismissal triggers (the 13th semester, exceeding 12 semesters)."""
    config = config or GENERATOR_CONFIG
    progress_config = config["student_progress"]
    cohort_start = _get_cohort_start(student_id, config)
    if cohort_start is None:
        return None
    start_idx = semester_index(cohort_start)
    grad_config = progress_config.get("graduation", {})
    dismissal_threshold = grad_config.get(
        "dismissal_after_semesters",
        grad_config.get("standard_semesters", STANDARD_SEMESTERS)
        + grad_config.get("max_late_semesters", MAX_LATE_SEMESTERS),
    )
    return semester_from_index(start_idx + dismissal_threshold)


def academic_dismissal_semesters(student_id: str, semesters: List[str], config: Optional[Dict[str, Any]] = None) -> Set[str]:
    """Return the set of semesters from the list that fall under academic dismissal for the student."""
    return {
        semester
        for semester in semesters
        if is_academic_dismissal(student_id, semester, config)
    }


def is_student_active_for_semester(
    student_id: str,
    semester_code: str,
    profiles: Optional[Any] = None,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """Check if a student is active for enrollment in semester_code.
    Returns False if student has voluntarily dropped out in a prior semester or is academically dismissed.
    """
    config = config or GENERATOR_CONFIG
    sid = str(student_id)
    # 1. Academic dismissal check
    if is_academic_dismissal(sid, semester_code, config):
        return False
    # 2. Voluntary dropout check
    if profiles is None:
        profiles = _get_standing_profiles_cache()

    prof_dict = None
    if isinstance(profiles, pd.DataFrame):
        if "dict_cache" not in profiles.attrs:
            pid_col = "student_id" if "student_id" in profiles.columns else "user_id"
            profiles.attrs["dict_cache"] = profiles.set_index(pid_col).to_dict(orient="index")
        prof_dict = profiles.attrs["dict_cache"]
    elif isinstance(profiles, dict):
        prof_dict = profiles

    if prof_dict is not None:
        p = prof_dict.get(sid, {})
        v_drop = p.get("voluntary_dropout_semester")
        if v_drop and pd.notna(v_drop) and str(v_drop).strip() != "":
            if semester_index(semester_code) > semester_index(str(v_drop)):
                return False
    return True


def filter_active_students_for_semester(
    students: pd.DataFrame,
    semester_code: str,
    profiles: Optional[Any] = None,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Filter students DataFrame to only include active students for semester_code."""
    if students.empty:
        return students
    config = config or GENERATOR_CONFIG
    id_col = "user_id" if "user_id" in students.columns else "student_id"
    prof_dict = None
    if isinstance(profiles, pd.DataFrame):
        pid_col = "student_id" if "student_id" in profiles.columns else "user_id"
        prof_dict = profiles.set_index(pid_col).to_dict(orient="index")
    elif isinstance(profiles, dict):
        prof_dict = profiles

    active_mask = [
        is_student_active_for_semester(str(getattr(r, id_col)), semester_code, prof_dict, config)
        for r in students.itertuples(index=False)
    ]
    return students[active_mask].copy()


def academic_suspension_semesters(
    student_history: pd.DataFrame,
    semesters: List[str],
    credits: Dict[str, float],
    config: Optional[Dict[str, Any]] = None,
) -> Set[str]:
    """Return the one-semester pauses triggered by consecutive low-credit terms."""
    config = config or GENERATOR_CONFIG
    if "status" not in student_history or "course_code" not in student_history:
        return set()

    semester_column = (
        "semester_code"
        if "semester_code" in student_history
        else "semester"
        if "semester" in student_history
        else None
    )
    if semester_column is None:
        return set()

    low_credit_threshold = config["student_progress"]["graduation"][
        "minimum_passed_credits_per_semester"
    ]
    standard_semesters = config.get("student_progress", {}).get(
        "graduation", {}
    ).get("standard_semesters", 8)
    low_credit_streak = 0
    suspensions = set()

    for idx, semester in enumerate(semesters):
        sem_num = idx + 1
        current_index = semester_index(semester)
        if low_credit_streak >= 2:
            suspensions.add(semester)
            low_credit_streak = 0
            continue

        if sem_num >= standard_semesters - 1:
            continue

        if semester_column == "semester_code":
            term_history = student_history[
                student_history[semester_column].astype(str).str.upper()
                == semester.upper()
            ]
        else:
            term_history = student_history[
                pd.to_numeric(
                    student_history[semester_column], errors="coerce"
                )
                == current_index
            ]
        passed = term_history[
            term_history["status"].astype(str).str.casefold() == "pass"
        ]
        passed_credits = sum(
            float(credits[course_code])
            for course_code in passed["course_code"].drop_duplicates()
            if course_code in credits
        )
        if passed_credits < low_credit_threshold:
            low_credit_streak += 1
        else:
            low_credit_streak = 0

    return suspensions


def _is_academic_suspension_semester(
    student_id: str,
    history: pd.DataFrame,
    credits: Dict[str, float],
    semester_code: str,
    config: Dict[str, Any],
) -> bool:
    """Internal helper to check if a specific semester is suspended for a student."""
    if history.empty:
        return False
    progress_config = config["student_progress"]
    start_semester = _get_cohort_start(student_id, config)
    if start_semester is None:
        return False
    current_index = semester_index(semester_code)
    start_index = semester_index(start_semester)
    semesters = [
        semester
        for semester in progress_config["observed_semesters"]
        if start_index <= semester_index(semester) <= current_index
    ]
    if not semesters and start_index <= current_index:
        semesters = [
            semester_from_index(idx)
            for idx in range(start_index, current_index + 1)
        ]
    student_history = (
        history[history["student_id"] == student_id]
        if "student_id" in history
        else history
    )
    return semester_code in academic_suspension_semesters(
        student_history, semesters, credits, config
    )

