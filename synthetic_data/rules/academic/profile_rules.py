"""Student profile generation, psychological traits, social activity (CTXH), English progress, and dropout models."""

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

from .common import (
    ROOT_DIR,
    _normalized_trait,
    _stable_seed,
    _student_flag,
    _student_value,
    filter_students_from_2020,
)
from .config import GENERATOR_CONFIG
from .standing_rules import (
    _get_cohort_start,
    is_academic_dismissal,
    semester_from_index,
    semester_index,
)

PROFILE_OUTPUT_DIR = ROOT_DIR / "generated" / "users"
PROFILE_OUTPUT_FILE = PROFILE_OUTPUT_DIR / "student_profiles.csv"

ACCELERATION_BASE_SCORE = 8.0
ACCELERATION_PROBABILITY = 0.35

PROFILE_FIELDS = (
    "high_school_type",
    "admission_block",
    "family_income",
    "study_habit",
    "discipline",
    "motivation",
    "stress",
    "social_activity",
    "academic_level",
    "math_level",
    "english_level",
)


def load_student_profiles(profile_file: Optional[Path] = None) -> pd.DataFrame:
    """Load generated profiles for cohort 2020 (K20) onward."""
    target_file = Path(profile_file) if profile_file else PROFILE_OUTPUT_FILE
    if not target_file.exists():
        raise FileNotFoundError(
            f"Student profiles are missing at {target_file}. Run generators/users/generate_student_profiles.py first."
        )
    students = pd.read_csv(target_file, dtype={"student_id": str})
    required_columns = {"student_id", "name", "base_score"}
    missing_columns = required_columns.difference(students.columns)
    if missing_columns:
        raise ValueError(
            "student_profiles.csv is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )
    students = filter_students_from_2020(students)
    cohort_filter = os.environ.get("SYNTHETIC_DATA_COHORT_FILTER", "").strip()
    if cohort_filter:
        if len(cohort_filter) != 2 or not cohort_filter.isdigit():
            raise ValueError(
                "SYNTHETIC_DATA_COHORT_FILTER must be a two-digit cohort year"
            )
        students = students[
            students["student_id"].str.startswith(cohort_filter)
        ].copy()
    return students


def _base_score_for_level(level: float, config: Optional[Dict[str, Any]] = None) -> float:
    """Interpolate continuous base score between academic levels."""
    config = config or GENERATOR_CONFIG
    base_scores = config["academic"]["base_scores"]
    lower = int(math.floor(level))
    upper = int(math.ceil(level))
    if lower == upper:
        return float(base_scores[lower - 1])
    fraction = level - lower
    return (
        float(base_scores[lower - 1]) * (1 - fraction)
        + float(base_scores[upper - 1]) * fraction
    )


def _progress_personality_strength(profile: Dict[str, Any], progress_config: Dict[str, Any]) -> float:
    """Calculate overall personality strength weighted for CTXH & extracurricular performance."""
    weights = progress_config["ctxh"]["personality_weights"]
    trait_strengths = {
        "discipline": (profile["discipline"] - 1) / 4,
        "motivation": (profile["motivation"] - 1) / 4,
        "social_activity": (profile["social_activity"] - 1) / 4,
        "stress": (5 - profile["stress"]) / 4,
    }
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("CTXH personality weights must sum to a positive value")
    return float(sum(
        weights[trait] * trait_strengths[trait]
        for trait in weights
    ) / total_weight)


def _generate_english_eligibility_progress(
    student_id: str,
    profile: Dict[str, Any],
    config: Dict[str, Any],
    *,
    initial_eligible: bool,
) -> List[Dict[str, Any]]:
    """Simulate semester-by-semester transition to English-qualified status."""
    progress_config = config["student_progress"]
    start_semester = _get_cohort_start(student_id, config)
    if start_semester is None:
        return []
    start_index = semester_index(start_semester)
    semesters = [
        semester
        for semester in progress_config["observed_semesters"]
        if semester_index(semester) >= start_index
    ]
    if not semesters or semester_index(semesters[0]) > start_index + 12:
        semesters = [
            semester_from_index(idx)
            for idx in range(start_index, start_index + 8)
        ]
    if not semesters:
        return []

    english_config = progress_config["english"]
    background_scores = english_config["background_scores"]
    background_strength = float(np.mean([
        background_scores[field][profile[field]]
        for field in background_scores
    ]))
    factors = {
        "background_weight": background_strength,
        "english_skill_weight": (profile["english_level"] - 1) / 4,
        "academic_weight": (profile["academic_level"] - 1) / 4,
        "personality_weight": _progress_personality_strength(
            profile, progress_config
        ),
    }
    transition_config = english_config["transition"]
    probability = transition_config["base_probability"] + sum(
        transition_config[name] * factors[name]
        for name in factors
    )
    eligible = bool(initial_eligible)
    progress = []
    for index, semester in enumerate(semesters):
        if is_academic_dismissal(student_id, semester, config):
            break
        if index and not eligible:
            rng = np.random.default_rng(
                _stable_seed(student_id, config, f"english_transition:{semester}")
            )
            eligible = bool(rng.random() < probability)
        progress.append({
            "semester": semester,
            "eligible": eligible,
            "transition_probability": float(probability),
        })
    return progress


def _generate_ctxh_progress(
    student_id: str,
    profile: Dict[str, Any],
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Simulate Poisson-distributed CTXH days accumulated each semester."""
    progress_config = config["student_progress"]
    start_semester = _get_cohort_start(student_id, config)
    if start_semester is None:
        return []
    start_index = semester_index(start_semester)
    semesters = [
        semester
        for semester in progress_config["observed_semesters"]
        if semester_index(semester) >= start_index
    ]
    ctxh_config = progress_config["ctxh"]
    prog = profile.get("program", "standard")
    prog_cfg = ctxh_config.get("program_expected_days_per_semester", {}).get(prog)
    if prog_cfg and isinstance(prog_cfg, dict):
        min_days = prog_cfg.get("min", ctxh_config["minimum_expected_days_per_semester"])
        max_days = prog_cfg.get("max", ctxh_config["maximum_expected_days_per_semester"])
    else:
        min_days = ctxh_config["minimum_expected_days_per_semester"]
        max_days = ctxh_config["maximum_expected_days_per_semester"]

    personality_strength = _progress_personality_strength(
        profile, progress_config
    )
    expected_days = (
        min_days
        + personality_strength
        * (max_days - min_days)
    )
    cumulative_days = 0
    progress = []
    for semester in semesters:
        if is_academic_dismissal(student_id, semester, config):
            break
        rng = np.random.default_rng(
            _stable_seed(student_id, config, f"ctxh:{semester}")
        )
        cumulative_days += int(rng.poisson(expected_days))
        progress.append({
            "semester": semester,
            "cumulative_days": cumulative_days,
        })
    return progress


def _generate_voluntary_dropout(
    student_id: str,
    profile: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[Optional[str], Optional[str]]:
    """Simulate voluntary dropout due to economic or personal reasons."""
    # Miễn trừ rủi ro bỏ học tự nguyện cho hệ Chất lượng cao và Tiên tiến
    if profile.get("program") in ("high-quality", "advanced"):
        return None, None

    progress_config = config["student_progress"]
    dropout_config = progress_config["dropout"]
    background_scores = progress_config["english"]["background_scores"]
    background_strength = float(np.mean([
        background_scores[field][profile[field]]
        for field in background_scores
    ]))
    at_risk = (
        background_strength <= dropout_config["low_background_score_max"]
        or profile["academic_level"]
        <= dropout_config["low_academic_level_max"]
    )
    if not at_risk:
        return None, None

    rng = np.random.default_rng(
        _stable_seed(student_id, config, "voluntary_dropout")
    )
    if rng.random() >= dropout_config["voluntary_probability"]:
        return None, None

    reason_weights = dropout_config["voluntary_reason_weights"]
    reasons = list(reason_weights)
    weights = np.array([reason_weights[reason] for reason in reasons], dtype=float)
    reason = str(rng.choice(reasons, p=weights))
    start_semester = _get_cohort_start(student_id, config)
    if start_semester is None:
        return None, None
    start_index = semester_index(start_semester)
    semesters = [
        semester
        for semester in progress_config["observed_semesters"]
        if semester_index(semester) >= start_index
    ]
    if not semesters:
        return None, None
    return str(rng.choice(semesters)), reason


def generate_student_profile(
    student_id: str,
    config: Optional[Dict[str, Any]] = None,
    program: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate complete student profile attributes, personality, and progress trackers."""
    config = config or GENERATOR_CONFIG
    profile: Dict[str, Any] = {}
    if program:
        profile["program"] = program
    for field, distribution in config["background"].items():
        rng = np.random.default_rng(_stable_seed(student_id, config, field))
        profile[field] = rng.choice(
            distribution["values"],
            p=distribution["probabilities"],
        )
    for field in ("discipline", "motivation", "stress", "social_activity"):
        rng = np.random.default_rng(_stable_seed(student_id, config, field))
        profile[field] = int(rng.choice(
            config["personality"]["scale"],
            p=config["personality"][field],
        ))

    acad_dist = config["academic"]["distribution"]
    if isinstance(acad_dist, dict):
        prog_key = program if (program and program in acad_dist) else "standard"
        p_dist = acad_dist.get(prog_key, acad_dist.get("standard"))
    else:
        p_dist = acad_dist

    rng = np.random.default_rng(_stable_seed(student_id, config, "academic_level"))
    academic_level = int(rng.choice(
        [1, 2, 3, 4, 5],
        p=p_dist,
    ))
    profile["academic_level"] = academic_level
    for field in ("math_level", "english_level"):
        subject_rng = np.random.default_rng(
            _stable_seed(student_id, config, field)
        )
        profile[field] = int(np.clip(
            round(subject_rng.normal(
                academic_level,
                config["academic"]["subject_sigma"],
            )),
            1,
            5,
        ))
    progress_config = config["student_progress"]
    background_scores = progress_config["english"]["background_scores"]
    background_strength = float(np.mean([
        background_scores[field][profile[field]]
        for field in background_scores
    ]))
    personality_strength = _progress_personality_strength(profile, progress_config)
    english_probability = (
        progress_config["english"]["base_probability"]
        + progress_config["english"]["background_weight"] * background_strength
        + progress_config["english"]["english_skill_weight"]
        * ((profile["english_level"] - 1) / 4)
        + progress_config["english"]["academic_weight"]
        * ((profile["academic_level"] - 1) / 4)
        + progress_config["english"]["personality_weight"]
        * personality_strength
    )
    english_rng = np.random.default_rng(
        _stable_seed(student_id, config, "english_eligibility")
    )
    profile["english_pass"] = bool(
        english_rng.random() < np.clip(english_probability, 0.0, 1.0)
    )
    profile["english_eligibility_by_semester"] = (
        _generate_english_eligibility_progress(
            student_id,
            profile,
            config,
            initial_eligible=profile["english_pass"],
        )
    )
    profile["ctxh_days_by_semester"] = _generate_ctxh_progress(
        student_id, profile, config
    )
    dropout_semester, dropout_reason = _generate_voluntary_dropout(
        student_id, profile, config
    )
    profile["voluntary_dropout_semester"] = dropout_semester or ""
    profile["voluntary_dropout_reason"] = dropout_reason or ""
    return profile


def ctxh_days_before_semester(
    student: Any,
    semester_code: str,
    config: Optional[Dict[str, Any]] = None,
) -> int:
    """Calculate cumulative CTXH days earned by a student prior to the given semester."""
    config = config or GENERATOR_CONFIG
    progress = _student_value(student, "ctxh_days_by_semester", [])
    if progress is None or (
        not isinstance(progress, (list, str)) and pd.isna(progress)
    ):
        progress = []
    if isinstance(progress, str):
        try:
            progress = json.loads(progress) if progress else []
        except json.JSONDecodeError as error:
            raise ValueError("ctxh_days_by_semester must contain a JSON array") from error
    if not isinstance(progress, list):
        raise ValueError("ctxh_days_by_semester must be an array")
    current_index = semester_index(semester_code)
    if not progress or max((semester_index(entry["semester"]) for entry in progress), default=-999) < current_index - 1:
        student_id = _student_value(student, "student_id", "")
        if student_id:
            profile = {
                field: _student_value(student, field)
                for field in PROFILE_FIELDS
            }
            if any(profile.get(k) is not None for k in ["discipline", "motivation"]):
                progress = _generate_ctxh_progress(student_id, profile, config)
    return max(
        (
            int(entry["cumulative_days"])
            for entry in progress
            if semester_index(entry["semester"]) < current_index
        ),
        default=0,
    )


def resolve_student_profile(
    student: Any,
    config: Optional[Dict[str, Any]] = None,
    *,
    student_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve full student profile dict from student row, filling in any missing fields."""
    config = config or GENERATOR_CONFIG
    student_id = student_id or _student_value(student, "student_id")
    if student_id is None or pd.isna(student_id):
        raise ValueError("student_id is required to resolve a student profile")
    student_id = str(student_id)
    program = _student_value(student, "program")
    profile = generate_student_profile(student_id, config, program=program)
    for field in PROFILE_FIELDS:
        value = _student_value(student, field)
        if pd.notna(value):
            profile[field] = value
    if pd.isna(_student_value(student, "academic_level")) and pd.notna(_student_value(student, "base_score")):
        base_scores = config["academic"]["base_scores"]
        profile["academic_level"] = min(
            range(1, 6),
            key=lambda level: abs(
                float(_student_value(student, "base_score")) - base_scores[level - 1]
            ),
        )
    for field in (
        "discipline",
        "motivation",
        "stress",
        "social_activity",
        "academic_level",
        "math_level",
        "english_level",
    ):
        value = int(profile[field])
        if value < 1 or value > 5:
            raise ValueError(f"{field} for student {student_id} must be between 1 and 5")
        profile[field] = value
    return profile


def select_early_graduation_candidates(
    profiles: Any,
    config: Optional[Dict[str, Any]] = None,
) -> Set[str]:
    """Select a deterministic share of the top-scoring eligible-cohort profiles per cohort."""
    config = config or GENERATOR_CONFIG
    settings = config["student_progress"]["graduation"]["early_graduation"]
    supported_cohorts = {
        str(value).upper().removeprefix("K")
        for value in settings["supported_cohorts"]
    }

    if isinstance(profiles, pd.DataFrame):
        profiles_list = profiles.to_dict("records")
    else:
        profiles_list = list(profiles)

    by_cohort: Dict[str, List[Dict[str, Any]]] = {}
    for profile in profiles_list:
        cohort = str(profile["student_id"])[:2]
        if cohort in supported_cohorts:
            by_cohort.setdefault(cohort, []).append(profile)

    if not by_cohort:
        return set()

    def score(profile: Dict[str, Any]) -> float:
        personality = np.mean([
            (float(profile["discipline"]) - 1) / 4,
            (float(profile["motivation"]) - 1) / 4,
            (5 - float(profile["stress"])) / 4,
            (float(profile["social_activity"]) - 1) / 4,
        ])
        academic = (float(profile["academic_level"]) - 1) / 4
        return float(academic + personality)

    selected: Set[str] = set()
    for cohort in sorted(by_cohort.keys()):
        cohort_profiles = by_cohort[cohort]
        high_performers = [
            p for p in cohort_profiles
            if float(p.get("base_score", 0.0) or 0.0) >= 8.5
            or int(p.get("academic_level", 0)) >= 5
        ]
        pool = high_performers if high_performers else cohort_profiles
        pool.sort(
            key=lambda profile: (
                -score(profile),
                str(profile["student_id"]),
            )
        )

        if 1000 <= len(cohort_profiles) <= 2500:
            target_count = max(15, min(20, round(len(cohort_profiles) * 0.012)))
            top_performers = pool[:target_count]
            selected_count = min(len(top_performers), target_count)
        else:
            top_count = max(
                1,
                math.ceil(len(cohort_profiles) * settings["top_performer_share"]),
            )
            top_performers = pool[:top_count]
            selected_count = max(
                1,
                min(
                    top_count,
                    int(math.floor(top_count * settings["selection_rate"] + 0.5)),
                ),
            )

        selected.update(
            str(profile["student_id"])
            for profile in sorted(
                top_performers,
                key=lambda item: (
                    _stable_seed(item["student_id"], config, "early_graduation"),
                    str(item["student_id"]),
                ),
            )[:selected_count]
        )
    return selected


def wants_acceleration(
    student_id: str,
    base_score: float,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """Determine whether an eligible high-performing student opts to accelerate their study load."""
    config = config or GENERATOR_CONFIG
    policy = config.get("student_progress", {}).get("enrollment_policy", {})
    min_base_score = policy.get("acceleration_base_score", ACCELERATION_BASE_SCORE)
    prob = policy.get("acceleration_probability", ACCELERATION_PROBABILITY)
    if float(base_score) < min_base_score:
        return False
    digest = hashlib.sha256(
        f"{student_id}:acceleration".encode("utf-8")
    ).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF < prob
