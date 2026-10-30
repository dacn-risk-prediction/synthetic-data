"""Course scoring models, random grading distributions, letter grades, and GPA calculations."""

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from .common import _normalized_trait, _student_value
from .config import GENERATOR_CONFIG
from .profile_rules import _base_score_for_level, resolve_student_profile


def course_mean_score(
    student: Any,
    course_code: str,
    catalog_difficulty: float,
    config: Optional[Dict[str, Any]] = None,
    *,
    student_id: Optional[str] = None,
) -> float:
    """Calculate expected mean score for a student in a specific course."""
    config = config or GENERATOR_CONFIG
    profile = resolve_student_profile(
        student,
        config,
        student_id=student_id,
    )
    prefix = str(course_code)[:2].upper()
    subject = (
        "english_level"
        if prefix == "LA"
        else "math_level"
        if prefix in {"MT", "MA", "PH", "CH"}
        else None
    )
    ability_level = float(profile["academic_level"])
    if subject:
        ability_level += config["academic"]["subject_effect"] * (
            profile[subject] - profile["academic_level"]
        )
    mean_score = _base_score_for_level(ability_level, config)
    mean_score += sum(
        weight * _normalized_trait(profile[trait])
        for trait, weight in config["personality_weights"].items()
    )
    student_id_val = str(student_id or _student_value(student, "student_id") or profile.get("student_id") or "")
    cohort_key = "K" + student_id_val[:2] if len(student_id_val) >= 2 else ""
    shift = config.get("academic", {}).get("cohort_shift", {}).get(cohort_key, 0.0)
    mean_score += shift

    difficulty_config = config["difficulty"]
    overrides = difficulty_config["course_overrides"]
    if course_code in overrides:
        difficulty_fraction = (
            overrides[course_code] - difficulty_config["min_level"]
        ) / (difficulty_config["max_level"] - difficulty_config["min_level"])
    else:
        catalog_value = float(catalog_difficulty)
        if not math.isfinite(catalog_value):
            raise ValueError(f"Invalid catalog difficulty for course {course_code}")
        difficulty_fraction = (
            catalog_value - difficulty_config["catalog_min"]
        ) / (difficulty_config["catalog_max"] - difficulty_config["catalog_min"])
    difficulty_fraction = float(np.clip(difficulty_fraction, 0.0, 1.0))

    academic_strength = (profile["academic_level"] - 1) / 4.0
    personality_strength = sum((
        (profile["discipline"] - 1) / 4.0,
        (profile["motivation"] - 1) / 4.0,
        (5 - profile["stress"]) / 4.0,
    )) / 3.0
    overall_strength = (academic_strength + personality_strength) / 2.0
    difficulty_effect = (
        difficulty_fraction
        * difficulty_config["max_penalty"]
        * (1.0 - difficulty_config["resilience"] * overall_strength)
    )
    return mean_score - difficulty_effect


def generate_observed_score(
    mean_score: float,
    rng: np.random.Generator,
    config: Optional[Dict[str, Any]] = None,
    *,
    retaken: bool = False,
) -> float:
    """Generate actual observed score adding controlled noise and optional retake bonus."""
    config = config or GENERATOR_CONFIG
    noise = config["noise"]
    if rng.random() < noise["high_deviation_ratio"]:
        deviation = abs(rng.normal(0, noise["high_sigma"]))
        if rng.random() < noise["low_direction_ratio"]:
            score = mean_score - deviation
        else:
            score = mean_score + deviation
    else:
        score = rng.normal(mean_score, noise["normal_sigma"])
    if retaken:
        score += config["score"]["retake_bonus"]
    return float(np.clip(score, config["score"]["min"], config["score"]["max"]))


def convert_score_to_grade(
    score: float,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[str, float]:
    """Map 10-point scale score to letter grade (A+, A, B+, B, C, D, F) and 4.0 GPA scale."""
    config = config or GENERATOR_CONFIG
    grade_scale = config["grade_scale"]
    for index, grade in enumerate(grade_scale):
        if grade["min"] <= score < grade["max"]:
            return grade["letter"], float(grade["gpa4"])
        if index == len(grade_scale) - 1 and score == grade["max"]:
            return grade["letter"], float(grade["gpa4"])
    raise ValueError(f"Score {score} is outside the configured grade scale")


def score_course_components(
    student: Any,
    course_code: str,
    components: List[Tuple[str, float]],
    catalog_difficulty: float,
    rng: np.random.Generator,
    config: Optional[Dict[str, Any]] = None,
    *,
    retaken: bool = False,
    student_id: Optional[str] = None,
) -> Tuple[Dict[str, float], float, str, float]:
    """Score individual assessment components (assignments, midterm, final exam)."""
    config = config or GENERATOR_CONFIG
    mean_score = course_mean_score(
        student,
        course_code,
        catalog_difficulty,
        config,
        student_id=student_id,
    )
    scores: Dict[str, float] = {}
    final_score = 0.0
    for component, weight in components:
        score = round(generate_observed_score(
            mean_score,
            rng,
            config,
            retaken=retaken,
        ), 1)
        scores[component] = score
        final_score += score * weight
    final_score = round(final_score, 1)
    letter, gpa = convert_score_to_grade(final_score, config)
    return scores, final_score, letter, gpa


def add_gpa_summaries(
    result: pd.DataFrame,
    history: pd.DataFrame,
    credits: Dict[str, float],
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Calculate and append semester GPA and cumulative GPA (CPA) to enrollment results."""
    config = config or GENERATOR_CONFIG
    semester_gpas: Dict[str, Any] = {}
    for student_id, attempts in result.groupby("student_id"):
        weighted_points = 0.0
        attempted_credits = 0.0
        for attempt in attempts.to_dict("records"):
            score = attempt.get("final_score")
            if pd.isna(score):
                continue
            course_code = attempt["course_id"]
            if course_code not in credits:
                raise ValueError(f"Credits missing for course {course_code}")
            course_credits = float(credits[course_code])
            weighted_points += float(attempt["gpa_4"]) * course_credits
            attempted_credits += course_credits
        semester_gpas[student_id] = (
            round(weighted_points / attempted_credits, 2)
            if attempted_credits
            else pd.NA
        )

    completed_courses: Dict[str, Dict[str, Tuple[float, float]]] = {}
    history_rows = history.to_dict("records")
    current_rows = result.to_dict("records")
    for attempt in history_rows + current_rows:
        score = attempt.get("final_score")
        if pd.isna(score):
            continue
        course_code = attempt.get("course_code", attempt.get("course_id"))
        student_id = attempt.get("student_id")
        if course_code not in credits:
            raise ValueError(f"Credits missing for course {course_code}")
        letter, gpa = convert_score_to_grade(float(score), config)
        if letter == "F":
            continue
        student_courses = completed_courses.setdefault(student_id, {})
        student_courses[course_code] = (
            gpa,
            float(credits[course_code]),
        )

    final_gpas: Dict[str, Any] = {}
    for student_id, student_courses in completed_courses.items():
        total_credits = sum(credit for _, credit in student_courses.values())
        final_gpas[student_id] = (
            round(
                sum(gpa * credit for gpa, credit in student_courses.values())
                / total_credits,
                2,
            )
            if total_credits > 0
            else pd.NA
        )

    result["semester_gpa_4"] = result["student_id"].map(semester_gpas)
    result["final_gpa_4"] = result["student_id"].map(final_gpas)
    return result

