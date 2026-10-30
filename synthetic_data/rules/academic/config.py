"""Configuration loading and validation for synthetic data generation."""

import json
import math
from pathlib import Path
from typing import Any, Dict, Optional

from .common import ROOT_DIR

CONFIG_FILE = ROOT_DIR / "config" / "generator_config.json"


def validate_generator_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate completeness and statistical invariants of generator_config.json."""
    def validate_distribution(name: str, values: Any) -> None:
        if (
            not values
            or any(not isinstance(value, (int, float)) or value < 0 for value in values)
            or not math.isclose(sum(values), 1.0, abs_tol=1e-9)
        ):
            raise ValueError(f"{name} probabilities must be non-negative and sum to 1")

    personality = config["personality"]
    scale = personality["scale"]
    for trait in ("discipline", "motivation", "stress", "social_activity"):
        if len(personality[trait]) != len(scale):
            raise ValueError(f"personality.{trait} must match personality.scale")
        validate_distribution(f"personality.{trait}", personality[trait])

    academic = config["academic"]
    acad_dist = academic["distribution"]
    if isinstance(acad_dist, dict):
        for prog_key, dist_vals in acad_dist.items():
            if len(dist_vals) != 5:
                raise ValueError(f"academic.distribution.{prog_key} must have five values")
            validate_distribution(f"academic.distribution.{prog_key}", dist_vals)
    else:
        if len(acad_dist) != 5:
            raise ValueError("academic distribution must have five values")
        validate_distribution("academic.distribution", acad_dist)

    if len(academic["base_scores"]) != 5:
        raise ValueError("academic base_scores must have five values")
    if "cohort_shift" in academic and not isinstance(academic["cohort_shift"], dict):
        raise ValueError("academic.cohort_shift must be a dictionary")
    if (
        academic["subject_sigma"] < 0
        or academic["base_scores"] != sorted(academic["base_scores"])
    ):
        raise ValueError("academic subject_sigma must be non-negative and base_scores ordered")

    for name, distribution in config["background"].items():
        if len(distribution["values"]) != len(distribution["probabilities"]):
            raise ValueError(f"background.{name} values and probabilities must match")
        validate_distribution(
            f"background.{name}",
            distribution["probabilities"],
        )

    noise = config["noise"]
    validate_distribution(
        "noise population",
        [noise["normal_ratio"], noise["high_deviation_ratio"]],
    )
    validate_distribution(
        "noise direction",
        [noise["low_direction_ratio"], noise["high_direction_ratio"]],
    )
    difficulty = config["difficulty"]
    if not 0 <= difficulty["resilience"] <= 1:
        raise ValueError("difficulty.resilience must be between 0 and 1")
    if (
        difficulty["catalog_min"] >= difficulty["catalog_max"]
        or difficulty["min_level"] >= difficulty["max_level"]
        or difficulty["max_penalty"] < 0
    ):
        raise ValueError("difficulty ranges must be increasing and penalty non-negative")
    if any(
        not difficulty["min_level"] <= float(level) <= difficulty["max_level"]
        for level in difficulty["course_overrides"].values()
    ):
        raise ValueError("course difficulty overrides must be within the configured levels")
    if noise["normal_sigma"] < 0 or noise["high_sigma"] < 0:
        raise ValueError("noise sigma values must be non-negative")
    if config["score"]["min"] >= config["score"]["max"]:
        raise ValueError("score.min must be less than score.max")

    progress = config["student_progress"]
    semesters = progress["observed_semesters"]
    if (
        not semesters
        or len(semesters) != len(set(semesters))
        or semesters != sorted(semesters, key=lambda value: int(value[2:]))
    ):
        raise ValueError(
            "student_progress.observed_semesters must be unique and ordered"
        )
    if any(
        start not in semesters
        for start in progress["cohort_start_semester"].values()
    ):
        raise ValueError(
            "cohort start semesters must be present in observed_semesters"
        )
    ctxh = progress["ctxh"]
    if (
        ctxh["minimum_for_thesis"] < 0
        or ctxh["minimum_for_graduation"] < ctxh["minimum_for_thesis"]
        or ctxh["minimum_expected_days_per_semester"] < 0
        or ctxh["maximum_expected_days_per_semester"]
        < ctxh["minimum_expected_days_per_semester"]
        or any(weight < 0 for weight in ctxh["personality_weights"].values())
        or not math.isclose(
            sum(ctxh["personality_weights"].values()), 1.0, abs_tol=1e-9
        )
    ):
        raise ValueError("Invalid CTXH progress configuration")
    if not 0 <= progress["dropout"]["voluntary_probability"] <= 1:
        raise ValueError("voluntary_dropout_probability must be between 0 and 1")
    if not math.isclose(
        sum(progress["dropout"]["voluntary_reason_weights"].values()),
        1.0,
        abs_tol=1e-9,
    ):
        raise ValueError("voluntary dropout reason weights must sum to 1")
    english = progress["english"]
    if (
        any(
            english[name] < 0
            for name in (
                "base_probability",
                "background_weight",
                "english_skill_weight",
                "academic_weight",
                "personality_weight",
            )
        )
        or english["base_probability"] > 1
    ):
        raise ValueError("Invalid English eligibility probability configuration")
    transition = english["transition"]
    transition_weights = (
        "background_weight",
        "english_skill_weight",
        "academic_weight",
        "personality_weight",
    )
    if (
        not 0 <= transition["base_probability"] <= 1
        or any(transition[name] < 0 for name in transition_weights)
        or transition["base_probability"]
        + sum(transition[name] for name in transition_weights)
        > 1
    ):
        raise ValueError("Invalid English transition probability configuration")
    graduation = progress["graduation"]
    early_graduation = graduation.get("early_graduation", {})
    if (
        graduation["standard_semesters"] <= 0
        or graduation.get("max_late_semesters", 1) <= 0
        or graduation["dismissal_after_semesters"]
        < graduation["standard_semesters"]
        or graduation["minimum_passed_credits_per_semester"] < 0
        or not 0 <= graduation[
            "ineligible_thesis_empty_semester_probability"
        ] <= 1
        or not graduation["thesis_course_codes"]
        or not graduation["graduation_project_codes"]
        or not 0 < early_graduation.get("top_performer_share", 0) <= 1
        or not 0 <= early_graduation.get("selection_rate", -1) <= 1
        or not early_graduation.get("supported_cohorts")
    ):
        raise ValueError("Invalid graduation progress configuration")
    if "electives" in progress:
        electives = progress["electives"]
        if (
            electives.get("free_credit_limit", 0) < 0
            or electives.get("group_c_credit_limit", 0) < 0
        ):
            raise ValueError("Invalid electives configuration")
    if "enrollment_policy" in progress:
        policy = progress["enrollment_policy"]
        if (
            policy.get("optional_threshold", 0) < 0
            or not 0 <= policy.get("optional_16_credit_probability", 0) <= 1
            or policy.get("acceleration_base_score", 0) < 0
            or not 0 <= policy.get("acceleration_probability", 0) <= 1
        ):
            raise ValueError("Invalid enrollment policy configuration")

    grade_scale = config["grade_scale"]
    if (
        not grade_scale
        or grade_scale[0]["min"] != config["score"]["min"]
        or grade_scale[-1]["max"] != config["score"]["max"]
        or any(
            lower["max"] != upper["min"]
            for lower, upper in zip(grade_scale, grade_scale[1:])
        )
    ):
        raise ValueError("grade_scale must continuously cover the configured score range")
    return config


def load_generator_config(config_file: Optional[Path] = None) -> Dict[str, Any]:
    """Load and validate generator configuration from JSON."""
    target = Path(config_file) if config_file else CONFIG_FILE
    with target.open(encoding="utf-8") as file_obj:
        config = json.load(file_obj)
    return validate_generator_config(config)


GENERATOR_CONFIG: Dict[str, Any] = load_generator_config()

