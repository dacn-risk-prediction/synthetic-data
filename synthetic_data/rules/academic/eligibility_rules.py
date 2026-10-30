"""Course eligibility evaluation, prerequisite checks, English exemptions, and elective selections."""

import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

from curriculum_rules import (
    MAX_CREDITS,
    TUITION_BASELINE_CREDITS,
    additional_courses,
    curriculum_courses,
    get_specialization_group_c_courses,
    get_student_specialization_map,
    load_electives,
    load_group_c_electives,
)
from .common import (
    _stable_seed,
    _student_flag,
    _student_value,
    load_history,
)
from .config import GENERATOR_CONFIG
from .standing_rules import (
    _get_cohort_start,
    _is_academic_suspension_semester,
    is_academic_dismissal,
    semester_index,
)
from .profile_rules import (
    ACCELERATION_BASE_SCORE,
    ACCELERATION_PROBABILITY,
    ctxh_days_before_semester,
    wants_acceleration,
)

OPTIONAL_ENROLLMENT_THRESHOLD = 15
OPTIONAL_16_CREDIT_PROBABILITY = 0.35
FREE_CREDIT_LIMIT = 9
GROUP_C_CREDIT_LIMIT = 15

_FREE_COURSE_CODES = None
_GROUP_C_COURSE_CODES = None


def get_free_course_codes() -> Set[str]:
    """Retrieve set of available free elective course codes."""
    global _FREE_COURSE_CODES
    if _FREE_COURSE_CODES is None:
        try:
            df = load_electives()
            _FREE_COURSE_CODES = set(
                df[df["elective_group"] == "FREE"]["course_code"].dropna()
            )
        except Exception:
            _FREE_COURSE_CODES = set()
    return _FREE_COURSE_CODES


def get_group_c_course_codes() -> Set[str]:
    """Retrieve set of available Group C elective course codes."""
    global _GROUP_C_COURSE_CODES
    if _GROUP_C_COURSE_CODES is None:
        try:
            df = load_group_c_electives()
            _GROUP_C_COURSE_CODES = set(
                df[df["elective_group"] == "GROUP_C"]["course_code"].dropna()
            )
        except Exception:
            _GROUP_C_COURSE_CODES = set()
    return _GROUP_C_COURSE_CODES


SEMESTER = "HK261"
try:
    K20_COURSES = curriculum_courses("HK1")
    K20_EXTRA_COURSES = [
        code for code in additional_courses("HK1") if code not in K20_COURSES
    ]
    COURSE_ORDER = list(dict.fromkeys(K20_COURSES + K20_EXTRA_COURSES))
except Exception:
    K20_COURSES = []
    K20_EXTRA_COURSES = []
    COURSE_ORDER = []

# Backward-compatible aliases for legacy imports
K13_COURSES = K20_COURSES
K13_EXTRA_COURSES = K20_EXTRA_COURSES
K14_COURSES = K20_COURSES
K23_COURSES = K20_COURSES
K23_EXTRA_COURSES = K20_EXTRA_COURSES
K24_COURSES = K20_COURSES

ENGLISH_COURSE_CODES = ("LA1003", "LA1005", "LA1007", "LA1009")


def get_exempted_english_courses(
    student: Any,
    config: Optional[Dict[str, Any]] = None,
    semester_code: Optional[str] = None,
    *,
    before: bool = False,
) -> Set[str]:
    """Return the set of English courses exempted for the student."""
    config = config or GENERATOR_CONFIG
    english_pass = (
        english_eligible_by_semester(
            student, semester_code, before=before
        )
        if semester_code is not None
        else english_eligible_by_semester(student)
    )
    if english_pass:
        return set(ENGLISH_COURSE_CODES)

    student_id = str(_student_value(student, "student_id", ""))
    english_level = int(_student_value(student, "english_level", 3))

    seed = _stable_seed(student_id, config, "english_placement_test")
    rng = np.random.default_rng(seed)
    val = rng.random()

    if english_level <= 1:
        skip_count = 1 if val < 0.20 else 0
    elif english_level == 2:
        skip_count = 0 if val < 0.20 else (2 if val > 0.80 else 1)
    elif english_level == 3:
        skip_count = 1 if val < 0.10 else (3 if val > 0.80 else 2)
    elif english_level == 4:
        skip_count = 2 if val < 0.10 else 3
    else:
        skip_count = 3

    mapping = {
        0: set(),
        1: {"LA1003"},
        2: {"LA1003", "LA1005"},
        3: {"LA1003", "LA1005", "LA1007"},
    }
    return mapping[skip_count]


def english_eligible_by_semester(
    student: Any,
    semester_code: Optional[str] = None,
    *,
    before: bool = False,
) -> bool:
    """Return the monotonic English eligibility state for a semester."""
    initial_eligible = (
        str(_student_value(student, "english_pass", False)).casefold()
        == "true"
    )
    progress = _student_value(student, "english_eligibility_by_semester", [])
    if progress is None or (
        not isinstance(progress, (list, str)) and pd.isna(progress)
    ):
        progress = []
    if isinstance(progress, str):
        try:
            progress = json.loads(progress) if progress else []
        except json.JSONDecodeError as error:
            raise ValueError(
                "english_eligibility_by_semester must contain a JSON array"
            ) from error
    if not isinstance(progress, list):
        raise ValueError("english_eligibility_by_semester must be an array")
    if not progress:
        return initial_eligible
    if initial_eligible:
        return True

    target_index = (
        semester_index(semester_code)
        if semester_code is not None
        else float("inf")
    )
    return any(
        bool(entry["eligible"])
        and (
            semester_index(entry["semester"]) < target_index
            if before
            else semester_index(entry["semester"]) <= target_index
        )
        for entry in progress
    )


def is_english_passed(
    student: Any,
    passed_courses: Optional[Set[str]] = None,
    config: Optional[Dict[str, Any]] = None,
    semester_code: Optional[str] = None,
    *,
    before: bool = False,
) -> bool:
    """Return True if the student has satisfied English graduation requirements."""
    if english_eligible_by_semester(
        student, semester_code, before=before
    ):
        return True
    if passed_courses is None:
        return False
    exempted = get_exempted_english_courses(
        student,
        config,
        semester_code,
        before=before,
    )
    return set(ENGLISH_COURSE_CODES).issubset(set(passed_courses) | exempted)


def is_thesis_eligible(
    student: Any,
    semester_code: str,
    passed_courses: Optional[Set[str]] = None,
    profiles: Optional[Any] = None,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """Check if student meets conditions to enroll in thesis/project (CO4029, CO4337):
    - Accumulated CTXH days before semester >= 12
    - Passed English requirement (all required English courses passed or exempt)
    """
    # Accommodate callers that might pass (student, semester_code, passed_courses, config, profiles)
    if isinstance(profiles, dict) and ("student_progress" in profiles or "curriculum" in profiles):
        config, profiles = profiles, config

    if config is None:
        config = GENERATOR_CONFIG

    student_obj = student
    if isinstance(student, (str, int)):
        sid = str(student)
        prof_dict = {}
        if isinstance(profiles, pd.DataFrame):
            if "dict_cache" not in profiles.attrs:
                pid_col = "student_id" if "student_id" in profiles.columns else "user_id"
                profiles.attrs["dict_cache"] = profiles.set_index(pid_col).to_dict(orient="index")
            prof_dict = profiles.attrs["dict_cache"]
        elif isinstance(profiles, dict):
            prof_dict = profiles
        prof = prof_dict.get(sid, {})
        student_obj = {"student_id": sid, **prof}

    # 1. CTXH check: >= 12 days before semester
    min_ctxh = config.get("student_progress", {}).get("ctxh", {}).get("minimum_for_thesis", 12)
    ctxh_days = ctxh_days_before_semester(student_obj, semester_code, config)
    if ctxh_days < min_ctxh:
        return False

    # 2. English check
    if not is_english_passed(student_obj, passed_courses, config, semester_code, before=True):
        return False

    return True


def can_skip_la1003(
    student_id: Any,
    base_score: Optional[float] = None,
    *,
    student: Any = None,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """Check if student is exempted from taking LA1003."""
    target = student if student is not None else student_id
    if hasattr(target, "get") or hasattr(target, "student_id") or isinstance(target, dict):
        return "LA1003" in get_exempted_english_courses(target, config)
    digest = hashlib.sha256(str(student_id).encode("utf-8")).hexdigest()
    random_value = int(digest[:8], 16) / 0xFFFFFFFF
    if base_score is not None:
        if base_score >= 8.0:
            return True
        if base_score >= 7.0:
            return random_value < 0.70
        if base_score >= 5.0:
            return random_value < 0.15
    return False


def allows_optional_course_at_16(student_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
    """Determine whether student is permitted to take an optional course at 16 credits."""
    config = config or GENERATOR_CONFIG
    policy = config.get("student_progress", {}).get("enrollment_policy", {})
    prob = policy.get("optional_16_credit_probability", OPTIONAL_16_CREDIT_PROBABILITY)
    digest = hashlib.sha256(
        f"{student_id}:optional-at-16".encode("utf-8")
    ).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF < prob


def calculate_eligibility(
    students: pd.DataFrame,
    history: pd.DataFrame,
    credits: Dict[str, float],
    prerequisites: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, List[str]], Dict[str, Set[str]]]:
    """Calculate course eligibility for basic cohorts."""
    config = config or GENERATOR_CONFIG
    policy = config.get("student_progress", {}).get("enrollment_policy", {})
    optional_threshold = policy.get("optional_threshold", OPTIONAL_ENROLLMENT_THRESHOLD)
    passed = (
        history[history["status"].astype(str).str.casefold() == "pass"]
        .groupby("student_id")["course_code"].apply(set).to_dict()
    )
    failed = (
        history[history["status"].astype(str).str.casefold() == "fail"]
        .groupby("student_id")["course_code"].apply(set).to_dict()
    )
    tq_rules = (
        prerequisites[prerequisites["relation_type"] == "TQ"]
        .groupby("course_code")["related_course_code"].apply(list).to_dict()
    )
    eligibility = {student_id: [] for student_id in students["student_id"]}
    registered_credits = {student_id: 0 for student_id in eligibility}

    k23 = students[students["student_id"].str.startswith("23")]
    for student in k23.itertuples(index=False):
        student_id = student.student_id
        passed_courses = passed.get(student_id, set())
        failed_courses = failed.get(student_id, set())
        ordered_courses = [
            code for code in sorted(failed_courses)
            if code in credits and code not in passed_courses
        ] + [
            code for code in K23_COURSES if code not in failed_courses
        ]
        for code in ordered_courses:
            if code in passed_courses:
                continue
            if code not in failed_courses and not all(
                prerequisite in passed_courses
                for prerequisite in tq_rules.get(code, [])
            ):
                continue
            if registered_credits[student_id] + credits[code] > MAX_CREDITS:
                continue
            eligibility[student_id].append(code)
            registered_credits[student_id] += credits[code]
        acceleration = wants_acceleration(
            student.student_id,
            student.base_score,
            config,
        )
        can_fill_gap = (
            registered_credits[student_id] < TUITION_BASELINE_CREDITS
            and (
                registered_credits[student_id] <= optional_threshold
                or acceleration
            )
        )
        if can_fill_gap:
            for code in K23_EXTRA_COURSES:
                if registered_credits[student_id] >= TUITION_BASELINE_CREDITS:
                    break
                if code in passed_courses or code in eligibility[student_id]:
                    continue
                if not all(
                    prerequisite in passed_courses
                    for prerequisite in tq_rules.get(code, [])
                ):
                    continue
                if registered_credits[student_id] + credits[code] > MAX_CREDITS:
                    continue
                eligibility[student_id].append(code)
                registered_credits[student_id] += credits[code]

    k24 = students[students["student_id"].str.startswith("24")]
    for student in k24.itertuples(index=False):
        failed_courses = failed.get(student.student_id, set())
        ordered_courses = [
            code for code in sorted(failed_courses)
            if code in credits and code not in passed.get(student.student_id, set())
        ] + [
            code for code in K24_COURSES if code not in failed_courses
        ]
        for code in ordered_courses:
            if code == "LA1003" and code not in failed_courses and can_skip_la1003(
                student.student_id, student.base_score
            ):
                continue
            if registered_credits[student.student_id] + credits[code] > MAX_CREDITS:
                continue
            eligibility[student.student_id].append(code)
            registered_credits[student.student_id] += credits[code]

    return eligibility, failed


def calculate_eligibility_for_schedule(
    students,
    history,
    credits,
    prerequisites,
    scheduled_courses,
    additional_course_groups,
    required_elective_groups=None,
    optional_elective_groups=None,
    required_elective_credits=None,
    required_choice_groups=None,
    *,
    semester_code=None,
    config=None,
):
    """Build one eligibility map for a semester's class and enrollment generators."""
    config = config or GENERATOR_CONFIG
    if semester_code is None:
        raise ValueError("semester_code is required to evaluate student eligibility")
    progress_config = config.get("student_progress", {})
    electives_config = progress_config.get("electives", {})
    free_credit_limit = electives_config.get("free_credit_limit", FREE_CREDIT_LIMIT)
    group_c_credit_limit = electives_config.get("group_c_credit_limit", GROUP_C_CREDIT_LIMIT)
    policy_config = progress_config.get("enrollment_policy", {})
    optional_threshold = policy_config.get("optional_threshold", OPTIONAL_ENROLLMENT_THRESHOLD)
    scheduled_courses = {
        str(cohort)[:2]: courses for cohort, courses in scheduled_courses.items()
    }
    additional_course_groups = {
        str(cohort)[:2]: groups
        for cohort, groups in additional_course_groups.items()
    }
    required_elective_groups = {
        str(cohort)[:2]: groups
        for cohort, groups in (required_elective_groups or {}).items()
    }
    optional_elective_groups = {
        str(cohort)[:2]: groups
        for cohort, groups in (optional_elective_groups or {}).items()
    }
    required_elective_credits = {
        str(cohort)[:2]: groups
        for cohort, groups in (required_elective_credits or {}).items()
    }
    required_choice_groups = {
        str(cohort)[:2]: groups
        for cohort, groups in (required_choice_groups or {}).items()
    }
    passed = (
        history[history["status"].astype(str).str.casefold() == "pass"]
        .groupby("student_id")["course_code"].apply(set).to_dict()
    )
    failed = (
        history[history["status"].astype(str).str.casefold() == "fail"]
        .groupby("student_id")["course_code"].apply(set).to_dict()
    )
    tq_rules = (
        prerequisites[prerequisites["relation_type"] == "TQ"]
        .groupby("course_code")["related_course_code"].apply(list).to_dict()
    )
    eligibility = {}
    for student in students.itertuples(index=False):
        student_id = student.student_id
        dropout_semester_value = getattr(
            student, "voluntary_dropout_semester", ""
        )
        dropout_semester = (
            ""
            if pd.isna(dropout_semester_value)
            else str(dropout_semester_value)
        )
        if dropout_semester and semester_index(semester_code) > semester_index(
            dropout_semester
        ):
            continue
        if is_academic_dismissal(student_id, semester_code, config):
            eligibility[student_id] = []
            continue
        if _is_academic_suspension_semester(
            student_id, history, credits, semester_code, config
        ):
            eligibility[student_id] = []
            continue

        prefix = str(student.student_id)[:2]
        scheduled = scheduled_courses.get(prefix)
        if scheduled is None:
            continue
        scheduled = list(scheduled)
        start_semester = _get_cohort_start(prefix, config)
        if start_semester and _student_flag(student, "early_graduation_candidate"):
            term = (
                semester_index(semester_code)
                - semester_index(start_semester)
                + 1
            )
            if term in (6, 7):
                scheduled.extend(
                    additional_courses(
                        f"HK{term}",
                        early_graduation=True,
                        early_graduation_only=True,
                        cohort=prefix,
                    )
                )
                scheduled = list(dict.fromkeys(scheduled))
        passed_courses = passed.get(student.student_id, set())
        failed_courses = failed.get(student.student_id, set())

        thesis_courses = set(
            config["student_progress"]["graduation"]["thesis_course_codes"]
        )
        thesis_eligible = (
            is_english_passed(
                student,
                passed_courses,
                config,
                semester_code,
                before=True,
            )
            and ctxh_days_before_semester(student, semester_code)
            >= config["student_progress"]["ctxh"]["minimum_for_thesis"]
        )
        exempted_english = get_exempted_english_courses(
            student, config, semester_code, before=True
        )

        def course_is_available(course_code):
            if course_code in exempted_english:
                return False
            return course_code not in thesis_courses or thesis_eligible

        thesis_pending = any(
            code in thesis_courses and code not in passed_courses
            for code in scheduled
        )
        if thesis_pending and not thesis_eligible:
            empty_semester_probability = config["student_progress"][
                "graduation"
            ]["ineligible_thesis_empty_semester_probability"]
            pause_rng = np.random.default_rng(
                _stable_seed(
                    student_id,
                    config,
                    f"empty-thesis-semester:{semester_code}",
                )
            )
            if pause_rng.random() < empty_semester_probability:
                eligibility[student.student_id] = []
                continue
        scheduled = [code for code in scheduled if course_is_available(code)]
        extras = additional_course_groups.get(prefix, [])
        extras = [code for code in extras if course_is_available(code)]
        elective_groups = required_elective_groups.get(prefix, {})
        elective_groups = {
            name: [code for code in courses if course_is_available(code)]
            for name, courses in elective_groups.items()
        }
        optional_groups = optional_elective_groups.get(prefix, {})
        optional_groups = {
            name: [code for code in courses if course_is_available(code)]
            for name, courses in optional_groups.items()
        }
        credit_targets = required_elective_credits.get(prefix, {})
        choice_groups = required_choice_groups.get(prefix, {})
        choice_groups = {
            name: [code for code in courses if course_is_available(code)]
            for name, courses in choice_groups.items()
        }
        selected = []
        registered_credits = 0
        chosen_courses = set()
        for group_name, candidates in choice_groups.items():
            available = [
                code for code in candidates
                if code in credits
                and code not in passed_courses
                and all(
                    prerequisite in passed_courses or prerequisite in exempted_english
                    for prerequisite in tq_rules.get(code, [])
                )
            ]
            if available:
                digest = hashlib.sha256(
                    f"{student.student_id}:{group_name}".encode("utf-8")
                ).hexdigest()
                chosen_courses.add(
                    available[int(digest[:8], 16) % len(available)]
                )
        failed_to_retake = [
            code for code in sorted(failed_courses)
            if code in credits and code not in passed_courses
            and course_is_available(code)
        ]
        choice_codes = list(chosen_courses)
        ordered = list(dict.fromkeys(
            failed_to_retake
            + choice_codes
            + [
                code for code in scheduled
                if code not in failed_courses
                and code not in choice_codes
            ]
        ))
        for code in ordered:
            if code in passed_courses or registered_credits + credits[code] > MAX_CREDITS:
                continue
            if code not in failed_courses and not all(
                prerequisite in passed_courses or prerequisite in exempted_english
                for prerequisite in tq_rules.get(code, [])
            ):
                continue
            selected.append(code)
            registered_credits += credits[code]
        free_codes = (
            get_free_course_codes()
            | set(elective_groups.get("FREE", []))
            | set(optional_groups.get("FREE", []))
        )
        group_c_codes = (
            get_group_c_course_codes()
            | set(elective_groups.get("GROUP_C", []))
            | set(optional_groups.get("GROUP_C", []))
        )
        for group_name, target in credit_targets.items():
            candidates = elective_groups.get(group_name, [])
            if group_name == "GROUP_C":
                spec_map = get_student_specialization_map()
                spec = getattr(student, "specialization", None) or spec_map.get(str(student.student_id))
                if spec:
                    spec_courses = set(get_specialization_group_c_courses(spec, f"K{prefix}"))
                    candidates = [c for c in candidates if c in spec_courses] + [c for c in candidates if c not in spec_courses]
            current_all = passed_courses | set(selected)
            if group_name == "FREE" and sum(credits.get(code, 0) for code in current_all if code in free_codes) >= free_credit_limit:
                continue
            if group_name == "GROUP_C" and sum(credits.get(code, 0) for code in current_all if code in group_c_codes) >= group_c_credit_limit:
                continue
            completed = sum(
                credits[code]
                for code in passed_courses | set(selected)
                if code in candidates
            )
            for code in candidates:
                if completed >= target:
                    break
                if code in passed_courses or code in selected:
                    continue
                if group_name == "FREE" and sum(credits.get(c, 0) for c in (passed_courses | set(selected)) if c in get_free_course_codes()) >= free_credit_limit:
                    break
                if group_name == "GROUP_C" and sum(credits.get(c, 0) for c in (passed_courses | set(selected)) if c in get_group_c_course_codes()) >= group_c_credit_limit:
                    break
                if not all(
                    prerequisite in passed_courses or prerequisite in exempted_english
                    for prerequisite in tq_rules.get(code, [])
                ):
                    continue
                if registered_credits + credits[code] > MAX_CREDITS:
                    continue
                selected.append(code)
                registered_credits += credits[code]
                completed += credits[code]
        acceleration = wants_acceleration(
            student.student_id,
            student.base_score,
            config,
        )
        optional_at_16 = (
            registered_credits == 16
            and allows_optional_course_at_16(student.student_id, config)
        )
        can_fill_gap = (
            registered_credits < TUITION_BASELINE_CREDITS
            and (
                registered_credits <= optional_threshold
                or optional_at_16
                or acceleration
            )
        )
        if can_fill_gap:
            elective_stages = []
            management_candidates = elective_groups.get("MANAGEMENT", [])
            management_completed = (
                passed_courses | set(selected)
            ).intersection(management_candidates)
            if management_candidates and not management_completed:
                elective_stages.append(
                    ("MANAGEMENT", management_candidates)
                )
            peer_candidates = [
                (group_name, candidates)
                for group_name, candidates in [
                    *elective_groups.items(),
                    *optional_groups.items(),
                ]
                if group_name != "MANAGEMENT"
                and group_name in {"FREE", "GROUP_C"}
            ]
            if peer_candidates:
                peer_candidates.sort(key=lambda item: item[0])
                elective_stages.append(
                    (
                        "FREE_OR_GROUP_C",
                        [
                            (group_name, code)
                            for group_name, candidates in peer_candidates
                            for code in candidates
                        ],
                    )
                )
            management_stage = [
                stage for stage in elective_stages
                if stage[0] == "MANAGEMENT"
            ]
            for group_name, candidates in management_stage:
                if registered_credits >= TUITION_BASELINE_CREDITS:
                    break
                available = [
                    (group_name, code)
                    for code in candidates
                    if code not in passed_courses
                    and code not in selected
                    and all(
                        prerequisite in passed_courses or prerequisite in exempted_english
                        for prerequisite in tq_rules.get(code, [])
                    )
                    and registered_credits + credits[code] <= MAX_CREDITS
                ]
                if available:
                    digest = hashlib.sha256(
                        f"{student.student_id}:{group_name}".encode("utf-8")
                    ).hexdigest()
                    _, choice = available[
                        int(digest[:8], 16) % len(available)
                    ]
                    selected.append(choice)
                    registered_credits += credits[choice]

            peer_stage = next(
                (
                    candidates
                    for group_name, candidates in elective_stages
                    if group_name == "FREE_OR_GROUP_C"
                ),
                [],
            )
            peer_round = 0
            max_peer_courses = (
                None
                if acceleration or registered_credits <= optional_threshold
                else 1
            )
            optional_credit_limit = (
                MAX_CREDITS
                if acceleration
                else TUITION_BASELINE_CREDITS + 1
            )
            while (
                registered_credits < TUITION_BASELINE_CREDITS
                and peer_stage
                and (
                    max_peer_courses is None
                    or peer_round < max_peer_courses
                )
            ):
                current_all = passed_courses | set(selected)
                completed_free = sum(
                    credits.get(c, 0) for c in current_all if c in free_codes
                )
                completed_group_c = sum(
                    credits.get(c, 0) for c in current_all if c in group_c_codes
                )
                available = [
                    (source_group, code)
                    for source_group, code in peer_stage
                    if code not in passed_courses
                    and code not in selected
                    and not (source_group == "FREE" and completed_free >= free_credit_limit)
                    and not (source_group == "GROUP_C" and completed_group_c >= group_c_credit_limit)
                    and all(
                        prerequisite in passed_courses or prerequisite in exempted_english
                        for prerequisite in tq_rules.get(code, [])
                    )
                    and registered_credits + credits[code] <= optional_credit_limit
                ]
                if not available:
                    break
                spec_map = get_student_specialization_map()
                spec = getattr(student, "specialization", None) or spec_map.get(str(student.student_id))
                if spec:
                    spec_courses = set(get_specialization_group_c_courses(spec, f"K{prefix}"))
                    spec_available = [
                        (src, code) for (src, code) in available
                        if src != "GROUP_C" or (code in spec_courses)
                    ]
                    if spec_available:
                        available = spec_available
                digest = hashlib.sha256(
                    f"{student.student_id}:FREE_OR_GROUP_C:{peer_round}"
                    .encode("utf-8")
                ).hexdigest()
                _, choice = available[
                    int(digest[:8], 16) % len(available)
                ]
                selected.append(choice)
                registered_credits += credits[choice]
                peer_round += 1
        if (
            can_fill_gap
            and registered_credits < TUITION_BASELINE_CREDITS
        ):
            for code in extras:
                if registered_credits >= TUITION_BASELINE_CREDITS:
                    break
                if code in passed_courses or code in selected:
                    continue
                if not all(
                    prerequisite in passed_courses or prerequisite in exempted_english
                    for prerequisite in tq_rules.get(code, [])
                ):
                    continue
                if registered_credits + credits[code] > MAX_CREDITS:
                    continue
                selected.append(code)
                registered_credits += credits[code]
        eligibility[student.student_id] = selected
    return eligibility, failed
