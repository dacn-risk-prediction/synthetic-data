"""Course scoring models, random grading distributions, letter grades, and GPA calculations."""

from collections import defaultdict
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from .common import ROOT_DIR, _normalized_trait, _student_value
from .config import GENERATOR_CONFIG
from .profile_rules import _base_score_for_level, resolve_student_profile

_PREREQUISITE_MAP: Optional[Dict[str, List[str]]] = None
_STUDENT_PAST_GRADES: Dict[str, Dict[str, float]] = defaultdict(dict)


def get_course_prerequisites_map(prereq_file: Optional[Path] = None) -> Dict[str, List[str]]:
    """Retrieve mapping of course_code -> list of prerequisite course codes (TQ and KN)."""
    global _PREREQUISITE_MAP
    if _PREREQUISITE_MAP is None:
        _PREREQUISITE_MAP = defaultdict(list)
        target = prereq_file or (ROOT_DIR / "generated" / "academics" / "course_prerequisites.csv")
        if target.exists():
            try:
                df = pd.read_csv(target)
                valid = df[df["relation_type"].isin(["TQ", "KN"])]
                for _, row in valid.iterrows():
                    c = str(row["course_code"]).strip().upper()
                    p = str(row["prerequisite_course_code"]).strip().upper()
                    if p not in _PREREQUISITE_MAP[c]:
                        _PREREQUISITE_MAP[c].append(p)
            except Exception:
                pass
    return _PREREQUISITE_MAP


def clear_student_past_grades() -> None:
    """Clear in-memory cache of student past course grades."""
    global _STUDENT_PAST_GRADES
    _STUDENT_PAST_GRADES.clear()


def set_student_past_grades(grades: Dict[str, Dict[str, float]]) -> None:
    """Set or update in-memory cache of student past course grades."""
    global _STUDENT_PAST_GRADES
    for sid, courses in grades.items():
        _STUDENT_PAST_GRADES[str(sid).strip()].update({
            str(c).strip().upper(): float(v) for c, v in courses.items() if pd.notna(v)
        })


def update_student_past_grades_from_df(df: pd.DataFrame) -> None:
    """Extract and cache past final scores from an enrollment DataFrame."""
    global _STUDENT_PAST_GRADES
    c_col = "course_id" if "course_id" in df.columns else "course_code"
    if "student_id" not in df.columns or c_col not in df.columns or "final_score" not in df.columns:
        return
    for _, r in df.iterrows():
        sid = str(r["student_id"]).strip()
        cid = str(r[c_col]).strip().upper()
        score = r["final_score"]
        if pd.notna(score):
            try:
                val = float(score)
                if 0.0 <= val <= 10.0:
                    current_max = _STUDENT_PAST_GRADES[sid].get(cid, -1.0)
                    if val > current_max:
                        _STUDENT_PAST_GRADES[sid][cid] = val
            except (ValueError, TypeError):
                pass


def init_prerequisite_grades_for_semester(current_semester: str, enrollments_dir: Optional[Path] = None) -> None:
    """Initialize student past grades cache from enrollment files prior to current_semester."""
    global _STUDENT_PAST_GRADES
    semesters_order = (
        "HK201", "HK202", "HK211", "HK212",
        "HK221", "HK222", "HK231", "HK232",
        "HK241", "HK242", "HK251", "HK252",
        "HK261",
    )
    cur_upper = str(current_semester).strip().upper()
    if cur_upper not in semesters_order:
        return
    idx = semesters_order.index(cur_upper)
    prior_sems = semesters_order[:idx]

    clear_student_past_grades()
    enr_dir = enrollments_dir or (ROOT_DIR / "generated" / "enrollments")
    for sem in prior_sems:
        fpath = enr_dir / f"enrollment_{sem.lower()}.csv"
        if fpath.exists():
            try:
                df = pd.read_csv(
                    fpath,
                    usecols=["student_id", "course_id", "final_score"],
                    dtype={"student_id": str, "course_id": str},
                )
                update_student_past_grades_from_df(df)
            except Exception:
                pass


def calculate_prerequisite_adjustment(
    student_id: Optional[str],
    course_code: str,
    past_grades: Optional[Dict[str, float]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Calculate score penalty or bonus based on student performance in prerequisite courses."""
    cfg = config or GENERATOR_CONFIG
    rules = cfg.get("prerequisite_rules", {})
    if not rules.get("enabled", True):
        return 0.0

    c_code = str(course_code).strip().upper()
    prereq_map = get_course_prerequisites_map()
    prereqs = prereq_map.get(c_code, [])
    if not prereqs:
        return 0.0

    sid = str(student_id).strip() if student_id else ""
    if past_grades is not None:
        grades_lookup = {str(k).strip().upper(): float(v) for k, v in past_grades.items() if pd.notna(v)}
    elif sid and sid in _STUDENT_PAST_GRADES:
        grades_lookup = _STUDENT_PAST_GRADES[sid]
    else:
        return 0.0

    prereq_scores: List[float] = []
    for p in prereqs:
        if p in grades_lookup:
            val = grades_lookup[p]
            if 0.0 <= val <= 10.0:
                prereq_scores.append(val)

    if not prereq_scores:
        return 0.0

    # Weakest link principle (Nguyên tắc thùng gỗ): Môn tiên quyết điểm thấp nhất quyết định mức độ hổng kiến thức
    min_score = min(prereq_scores)

    safe_threshold = float(rules.get("safe_threshold", 6.0))
    penalty_rate = float(rules.get("penalty_rate", 0.6))
    max_penalty = float(rules.get("max_penalty", 1.5))
    bonus_threshold = float(rules.get("bonus_threshold", 7.5))
    bonus_rate = float(rules.get("bonus_rate", 0.1))
    max_bonus = float(rules.get("max_bonus", 0.3))

    if min_score < safe_threshold:
        deficit = safe_threshold - min_score
        penalty = min(deficit * penalty_rate, max_penalty)
        return -round(penalty, 3)
    elif min_score >= bonus_threshold:
        surplus = min_score - bonus_threshold
        bonus = min(surplus * bonus_rate, max_bonus)
        return round(bonus, 3)
    return 0.0


def course_mean_score(
    student: Any,
    course_code: str,
    catalog_difficulty: float,
    config: Optional[Dict[str, Any]] = None,
    *,
    student_id: Optional[str] = None,
    past_prereq_scores: Optional[Dict[str, float]] = None,
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
    overrides = difficulty_config.get("course_overrides", {})
    min_lvl = float(difficulty_config.get("min_level", -1.0))
    max_lvl = float(difficulty_config.get("max_level", 1.0))

    if course_code in overrides:
        diff_val = float(overrides[course_code])
    else:
        catalog_value = float(catalog_difficulty)
        if not math.isfinite(catalog_value):
            raise ValueError(f"Invalid catalog difficulty for course {course_code}")
        cat_min = float(difficulty_config.get("catalog_min", -1.0))
        cat_max = float(difficulty_config.get("catalog_max", 1.0))
        diff_val = float(np.clip(catalog_value, cat_min, cat_max))

    diff_val = float(np.clip(diff_val, min_lvl, max_lvl))

    academic_strength = (profile["academic_level"] - 1) / 4.0
    personality_strength = sum((
        (profile["discipline"] - 1) / 4.0,
        (profile["motivation"] - 1) / 4.0,
        (5 - profile["stress"]) / 4.0,
    )) / 3.0
    overall_strength = (academic_strength + personality_strength) / 2.0
    # Positive diff_val (> 0) adds points (easy course bonus);
    # Negative diff_val (< 0) subtracts points (hard course penalty).
    adjustment = (
        diff_val
        * difficulty_config["max_penalty"]
        * (1.0 - difficulty_config["resilience"] * overall_strength)
    )

    # Prerequisite chain adjustment
    prereq_adj = calculate_prerequisite_adjustment(
        student_id=student_id_val,
        course_code=course_code,
        past_grades=past_prereq_scores,
        config=config,
    )

    return mean_score + adjustment + prereq_adj


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
    catalog_difficulty: float = 0.0,
    rng: Optional[np.random.Generator] = None,
    config: Optional[Dict[str, Any]] = None,
    *,
    retaken: bool = False,
    student_id: Optional[str] = None,
    past_prereq_scores: Optional[Dict[str, float]] = None,
) -> Tuple[Dict[str, float], float, str, float]:
    """Score individual assessment components (assignments, midterm, final exam)."""
    config = config or GENERATOR_CONFIG
    mean_score = course_mean_score(
        student,
        course_code,
        catalog_difficulty,
        config,
        student_id=student_id,
        past_prereq_scores=past_prereq_scores,
    )
    shifts = config.get("component_shifts", {})

    scores: Dict[str, float] = {}
    final_score = 0.0
    for component, weight in components:
        comp_mean = mean_score + float(shifts.get(component, 0.0))
        score = round(generate_observed_score(
            comp_mean,
            rng if rng is not None else np.random.default_rng(),
            config,
            retaken=retaken,
        ), 1)
        scores[component] = score
        final_score += score * weight
    final_score = round(final_score, 1)
    final_score = float(np.clip(final_score, config["score"]["min"], config["score"]["max"]))
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


def sync_class_teamwork_btl(
    df_enrollment: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
    assessment_weights: Optional[Dict[str, float]] = None,
    credits_map: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """Group students in each class section for BTL assignments and synchronize their scores.

    Students in the same teamwork group receive equal BTL scores based on the top performer (leader) of the group.
    Final scores, letter grades, GPAs, and pass/fail statuses are recalculated accordingly.
    """
    if df_enrollment.empty or "btl" not in df_enrollment.columns or "class_id" not in df_enrollment.columns:
        return df_enrollment

    config = config or GENERATOR_CONFIG
    team_cfg = config.get("teamwork_btl", {})
    team_size = max(2, int(team_cfg.get("team_size", 4)))
    score_min = float(config.get("score", {}).get("min", 0.0))
    score_max = float(config.get("score", {}).get("max", 10.0))

    # Read assessment weights if not provided
    if assessment_weights is None:
        assessment_weights = {}
        assessment_file = ROOT_DIR / "generated" / "academics" / "assessment.csv"
        if assessment_file.exists():
            df_ass = pd.read_csv(assessment_file, encoding="utf-8-sig")
            for _, row in df_ass.iterrows():
                cid = str(row["course_id"])
                btl_val = row.get("btl", 0.0)
                if pd.notna(btl_val) and float(btl_val) > 0:
                    assessment_weights[cid] = float(btl_val) / 100.0

    # Read credits if not provided (needed if GPA columns exist)
    recalc_gpa = "semester_gpa_4" in df_enrollment.columns or "final_gpa_4" in df_enrollment.columns
    if recalc_gpa and credits_map is None:
        credits_map = {}
        courses_file = ROOT_DIR / "generated" / "academics" / "courses.csv"
        if courses_file.exists():
            df_crs = pd.read_csv(courses_file, encoding="utf-8-sig")
            for _, row in df_crs.iterrows():
                c_code = str(row["course_code"])
                credits_map[c_code] = float(row.get("credits", 0.0))

    df_enrollment = df_enrollment.copy()
    has_changes = False

    # Filter records that belong to a class section and have BTL
    valid_mask = df_enrollment["class_id"].notna() & df_enrollment["btl"].notna()
    if not valid_mask.any():
        return df_enrollment

    valid_indices = df_enrollment[valid_mask].index

    # Group by course_id and class_id
    grouped = df_enrollment.loc[valid_indices].groupby(["course_id", "class_id"])
    for (course_id, class_id), group in grouped:
        class_indices = group.index.tolist()
        if len(class_indices) <= 1:
            continue

        w_btl = float(assessment_weights.get(str(course_id), 0.2))
        if w_btl <= 0.0:
            continue

        # Partition class into teams of size team_size
        teams = [class_indices[i : i + team_size] for i in range(0, len(class_indices), team_size)]
        if len(teams) > 1 and len(teams[-1]) <= 1:
            teams[-2].extend(teams.pop())

        for team in teams:
            member_btls = [
                float(df_enrollment.at[idx, "btl"])
                for idx in team
                if pd.notna(df_enrollment.at[idx, "btl"])
            ]
            if not member_btls:
                continue

            team_btl = max(member_btls)

            for idx in team:
                old_btl = float(df_enrollment.at[idx, "btl"])
                if team_btl != old_btl:
                    has_changes = True
                    df_enrollment.at[idx, "btl"] = team_btl

                    old_final = df_enrollment.at[idx, "final_score"]
                    if pd.notna(old_final) and old_final != 12.0:
                        old_final = float(old_final)
                        delta = (team_btl - old_btl) * w_btl
                        new_final = round(old_final + delta, 1)
                        new_final = float(np.clip(new_final, score_min, score_max))
                        letter, gpa = convert_score_to_grade(new_final, config)

                        df_enrollment.at[idx, "final_score"] = new_final
                        df_enrollment.at[idx, "letter_grade"] = letter
                        df_enrollment.at[idx, "gpa_4"] = gpa
                        df_enrollment.at[idx, "passed"] = (letter != "F")
                        if "status" in df_enrollment.columns:
                            cur_status = str(df_enrollment.at[idx, "status"])
                            if cur_status in ["Pass", "Fail", ""]:
                                df_enrollment.at[idx, "status"] = "Pass" if letter != "F" else "Fail"

    # Recalculate GPA if GPA columns are present and changes occurred
    if has_changes and recalc_gpa and credits_map:
        semester_gpas: Dict[str, float] = {}
        final_gpas: Dict[str, float] = {}
        for uid, attempts in df_enrollment.groupby("student_id"):
            weighted_points = 0.0
            attempted_credits = 0.0
            passed_points = 0.0
            passed_credits = 0.0
            for _, att in attempts.iterrows():
                cid = str(att["course_id"])
                tc = float(credits_map.get(cid, 0.0))
                score = att["final_score"]
                gpa4 = att["gpa_4"]
                if pd.isna(score) or score == 12.0 or pd.isna(gpa4):
                    continue
                weighted_points += float(gpa4) * tc
                attempted_credits += tc
                if att["passed"]:
                    passed_points += float(gpa4) * tc
                    passed_credits += tc
            semester_gpas[uid] = round(weighted_points / attempted_credits, 2) if attempted_credits > 0 else np.nan
            final_gpas[uid] = round(passed_points / passed_credits, 2) if passed_credits > 0 else np.nan

        if "semester_gpa_4" in df_enrollment.columns:
            df_enrollment["semester_gpa_4"] = df_enrollment["student_id"].map(semester_gpas)
        if "final_gpa_4" in df_enrollment.columns:
            df_enrollment["final_gpa_4"] = df_enrollment["student_id"].map(final_gpas)

    return df_enrollment

