import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "rules"))

from academic_rules import (  # noqa: E402
    GENERATOR_CONFIG,
    PROFILE_OUTPUT_FILE,
    academic_suspension_semesters,
    get_exempted_english_courses,
    is_academic_dismissal,
    is_english_passed,
    semester_index,
)


GENERATED_DIR = ROOT_DIR / "generated"
METRICS_DIR = GENERATED_DIR / "metrics"
STUDENT_FILE = GENERATED_DIR / "users" / "student.csv"
COURSE_FILE = GENERATED_DIR / "academics" / "courses.csv"
CURRICULUM_FILE = GENERATED_DIR / "academics" / "program_structures.csv"
LETTER_GRADES = [
    grade["letter"] for grade in GENERATOR_CONFIG["grade_scale"]
]


def _load_enrollment_history(profiles):
    records = []
    observed_semesters = []
    for semester_code in GENERATOR_CONFIG["student_progress"][
        "observed_semesters"
    ]:
        suffix = semester_code.lower()
        enrollment_path = (
            GENERATED_DIR / "enrollments" / f"enrollment_{suffix}.csv"
        )
        class_path = GENERATED_DIR / "classes" / f"class_{suffix}.csv"
        if not enrollment_path.exists() or not class_path.exists():
            continue
        enrollment = pd.read_csv(
            enrollment_path,
            dtype={"student_id": str, "class_id": str, "course_id": str},
        )
        classes = pd.read_csv(
            class_path,
            dtype={"class_id": str, "course_code": str},
        )[["class_id", "course_code"]]
        merged = enrollment.merge(
            classes,
            on="class_id",
            how="left",
            validate="many_to_one",
        )
        if "course_code" not in merged.columns or merged["course_code"].isna().any():
            if "course_id" in merged.columns:
                merged["course_code"] = merged["course_code"].fillna(merged["course_id"])
        if merged.loc[merged["class_id"].notna(), "course_code"].isna().any():
            raise ValueError(
                f"{semester_code} enrollment references an unknown class"
            )
        if merged["course_code"].isna().any():
            raise ValueError(
                f"{semester_code} enrollment contains records with missing course"
            )
        observed_semesters.append(semester_code)
        merged["semester_code"] = semester_code
        merged["semester_complete"] = merged["final_score"].notna().any()
        records.append(merged)
    history = (
        pd.concat(records, ignore_index=True)
        if records
        else pd.DataFrame(columns=[
            "student_id", "course_id", "course_code", "semester_code",
            "semester_complete", "final_score", "gpa_4", "status",
        ])
    )
    tracked_ids = set(history["student_id"])
    missing_profiles = tracked_ids - set(profiles["student_id"])
    if missing_profiles:
        raise ValueError(
            "Enrollment students missing profiles: "
            + ", ".join(sorted(missing_profiles)[:5])
        )
    return history, observed_semesters, tracked_ids


def _parse_ctxh_progress(value):
    if value is None or pd.isna(value) or value == "":
        return []
    if isinstance(value, list):
        return value
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError("ctxh_days_by_semester must be a JSON array")
    return parsed


def _ctxh_days_for_semester(progress, semester_code, *, before=False):
    target_index = semester_index(semester_code)
    return max(
        (
            int(entry["cumulative_days"])
            for entry in progress
            if (
                semester_index(entry["semester"]) < target_index
                if before
                else semester_index(entry["semester"]) <= target_index
            )
        ),
        default=0,
    )


def _profile_graduation_state(
    profile, student_history, semesters, credits, required_courses
):
    student_history = student_history.copy()
    student_history["final_score"] = pd.to_numeric(
        student_history["final_score"], errors="coerce"
    )
    completed = student_history[
        student_history["status"].astype(str).str.casefold().isin(["pass", "exempted"])
        | student_history["passed"].eq(True)
    ]
    passed_courses = set(completed["course_code"])
    passed_credits_by_course = {}
    for code in passed_courses:
        if code in credits:
            passed_credits_by_course[code] = float(credits[code])
    credit_total = sum(passed_credits_by_course.values())

    gpa_courses = [
        code for code in passed_courses
        if not completed.loc[completed["course_code"] == code, "gpa_4"].dropna().empty
        and not completed.loc[completed["course_code"] == code, "final_score"].dropna().empty
        and float(completed.loc[completed["course_code"] == code, "final_score"].dropna().max() or 0) != 12.0
        and code in credits
    ]
    gpa_credit_total = sum(float(credits[c]) for c in gpa_courses)
    if gpa_credit_total > 0:
        gpa4 = sum(
            float(
                completed.loc[completed["course_code"] == code, "gpa_4"]
                .dropna()
                .max()
            ) * credits[code]
            for code in gpa_courses
        ) / gpa_credit_total
        gpa10 = sum(
            float(
                completed.loc[completed["course_code"] == code, "final_score"]
                .dropna()
                .max()
            ) * credits[code]
            for code in gpa_courses
        ) / gpa_credit_total
    else:
        gpa4 = pd.NA
        gpa10 = pd.NA

    progress = _parse_ctxh_progress(profile.get("ctxh_days_by_semester", "[]"))
    current_semester = semesters[-1] if semesters else None
    ctxh_days = (
        _ctxh_days_for_semester(progress, current_semester)
        if current_semester
        else 0
    )
    graduation_config = GENERATOR_CONFIG["student_progress"]["graduation"]
    english_pass = (
        is_english_passed(
            profile,
            passed_courses,
            GENERATOR_CONFIG,
            current_semester,
        )
        if current_semester
        else is_english_passed(profile, passed_courses, GENERATOR_CONFIG)
    )
    exempted_english = get_exempted_english_courses(
        profile, GENERATOR_CONFIG, current_semester
    )
    effective_required_courses = required_courses - exempted_english

    graduation_semester = None
    student_id_val = str(profile.get("student_id", getattr(profile, "name", "")))
    for semester in semesters:
        if is_academic_dismissal(student_id_val, semester, GENERATOR_CONFIG):
            break
        completed_through_term = student_history[
            student_history["semester_index"].le(semester_index(semester))
            & (
                student_history["status"].astype(str).str.casefold().isin(["pass", "exempted"])
                | student_history["passed"].eq(True)
            )
        ]
        term_ctxh_days = _ctxh_days_for_semester(progress, semester)
        term_passed = set(completed_through_term["course_code"])
        term_english_pass = is_english_passed(
            profile, term_passed, GENERATOR_CONFIG, semester
        )
        term_exempted_english = get_exempted_english_courses(
            profile, GENERATOR_CONFIG, semester
        )
        term_effective_required = required_courses - term_exempted_english
        term_passed_credits = sum(float(credits.get(c, 0.0)) for c in term_passed)
        min_grad_credits = float(graduation_config.get("minimum_credits_for_graduation", 128.0))
        min_gpa = float(graduation_config.get("minimum_gpa4_for_graduation", 2.0))

        term_gpa_courses = [
            c for c in term_passed
            if not completed_through_term.loc[completed_through_term["course_code"] == c, "gpa_4"].dropna().empty
            and float(completed_through_term.loc[completed_through_term["course_code"] == c, "final_score"].dropna().max() or 0) != 12.0
            and c in credits
        ]
        term_gpa_credits = sum(float(credits[c]) for c in term_gpa_courses)
        term_gpa4 = (
            sum(
                float(completed_through_term.loc[completed_through_term["course_code"] == c, "gpa_4"].dropna().max()) * credits[c]
                for c in term_gpa_courses
            ) / term_gpa_credits
            if term_gpa_credits > 0 else 0.0
        )

        term_academic_ok = (
            (
                term_effective_required.issubset(term_passed)
                or {"CO4337", "SP1007"}.issubset(term_passed)
            )
            and term_passed_credits >= min_grad_credits
            and term_gpa4 >= min_gpa
        )
        if (
            term_academic_ok
            and term_ctxh_days
            >= GENERATOR_CONFIG["student_progress"]["ctxh"][
                "minimum_for_graduation"
            ]
            and term_english_pass
        ):
            graduation_semester = semester
            break

    graduation_ready = (graduation_semester is not None)
    missing_courses = set() if graduation_ready else (effective_required_courses - passed_courses)

    return {
        "passed_credits": credit_total,
        "gpa_4": gpa4,
        "gpa_10": gpa10,
        "ctxh_days": ctxh_days,
        "english_pass": english_pass,
        "thesis_eligible": (
            english_pass
            and ctxh_days
            >= GENERATOR_CONFIG["student_progress"]["ctxh"][
                "minimum_for_thesis"
            ]
        ),
        "graduation_ready": graduation_ready,
        "graduation_semester": graduation_semester,
        "missing_required_courses": len(missing_courses),
        "passed_courses": passed_courses,
        "progress": progress,
    }


def _build_student_reports(profiles, history, semesters, tracked_ids, credits):
    if not semesters:
        return pd.DataFrame(), pd.DataFrame()
    history = history.copy()
    history["semester_index"] = history["semester_code"].map(semester_index)
    semester_complete = (
        history.groupby("semester_code")["final_score"].apply(
            lambda values: pd.to_numeric(values, errors="coerce").dropna().loc[lambda v: v != 12.0].any()
        ).to_dict()
    )
    profile_by_id = profiles.set_index("student_id")
    start_semesters = GENERATOR_CONFIG["student_progress"][
        "cohort_start_semester"
    ]
    graduation_config = GENERATOR_CONFIG["student_progress"]["graduation"]
    required_courses_by_cohort = {}
    default_required = set()
    if CURRICULUM_FILE.exists():
        df_curr = pd.read_csv(CURRICULUM_FILE, dtype={"course_code": str})
        type_col = "course_type"
        if type_col in df_curr.columns:
            if "block_id" in df_curr.columns:
                df_curr = df_curr[~df_curr["block_id"].astype(str).str.startswith("COND_")]
            default_required = set(
                df_curr[df_curr[type_col].isin(["required", "BB"])]["course_code"].dropna()
            )
            for cid in df_curr["curriculum_id"].dropna().unique():
                cohort_str = str(cid).replace("KHMT_", "").replace("K", "")
                sub = df_curr[df_curr["curriculum_id"] == cid]
                c_req = set(sub[sub[type_col].isin(["required", "BB"])]["course_code"].dropna())
                c_req.update(graduation_config.get("graduation_project_codes", []))
                required_courses_by_cohort[cohort_str] = c_req
    default_required.update(graduation_config.get("graduation_project_codes", []))
    history_by_student = {
        student_id: group.copy()
        for student_id, group in history.groupby("student_id", sort=False)
    }
    progress_rows = []
    student_rows = []

    for student_id in sorted(tracked_ids):
        profile = profile_by_id.loc[student_id]
        cohort_prefix = str(student_id)[:2]
        cohort_start = start_semesters.get(cohort_prefix)
        if cohort_start is None:
            continue
        start_index = semester_index(cohort_start)
        student_semesters = [
            semester
            for semester in semesters
            if start_index <= semester_index(semester)
        ]
        student_history = history_by_student.get(
            student_id, history.iloc[0:0].copy()
        )
        suspension_semesters = academic_suspension_semesters(
            student_history,
            student_semesters,
            credits,
        )
        c_required = required_courses_by_cohort.get(cohort_prefix, default_required)
        details = _profile_graduation_state(
            profile,
            student_history,
            student_semesters,
            credits,
            c_required,
        )
        voluntary_semester_value = profile.get(
            "voluntary_dropout_semester", ""
        )
        voluntary_semester = (
            ""
            if pd.isna(voluntary_semester_value)
            else str(voluntary_semester_value)
        )
        voluntary_event = (
            voluntary_semester in student_semesters
            and semester_index(voluntary_semester)
            <= semester_index(semesters[-1])
        )
        forced_semester = None
        forced_reason = ""
        observed_count = 0
        for semester in student_semesters:
            semester_index_value = semester_index(semester)
            if voluntary_event and semester_index_value > semester_index(
                voluntary_semester
            ):
                break
            term = student_history[
                student_history["semester_code"].eq(semester)
            ]
            complete = semester_complete.get(semester, False)
            passed = term[
                term["status"].astype(str).str.casefold().isin(["pass", "exempted"])
                | term["passed"].eq(True)
            ]
            passed_credits = sum(
                float(credits[code])
                for code in passed["course_code"].drop_duplicates()
                if code in credits
            )
            progress = details["progress"]
            cumulative_ctxh = _ctxh_days_for_semester(progress, semester)
            academic_suspension = semester in suspension_semesters
            completed_through_term = student_history[
                student_history["semester_index"].le(semester_index(semester))
                & (
                    student_history["status"].astype(str).str.casefold().isin(["pass", "exempted"])
                    | student_history["passed"].eq(True)
                )
            ]
            term_english_pass = is_english_passed(
                profile,
                set(completed_through_term["course_code"]),
                GENERATOR_CONFIG,
                semester,
            )
            completed_before_term = student_history[
                student_history["semester_index"].lt(semester_index(semester))
                & (
                    student_history["status"].astype(str).str.casefold().isin(["pass", "exempted"])
                    | student_history["passed"].eq(True)
                )
            ]
            before_english_pass = is_english_passed(
                profile,
                set(completed_before_term["course_code"]),
                GENERATOR_CONFIG,
                semester,
                before=True,
            )
            progress_rows.append({
                "student_id": student_id,
                "cohort": f"K{str(student_id)[:2]}",
                "semester": semester,
                "registered": not term.empty,
                "registered_courses": int(term["course_code"].nunique()),
                "registered_credits": sum(
                    float(credits[code])
                    for code in term["course_code"].drop_duplicates()
                    if code in credits
                ),
                "passed_credits": passed_credits,
                "ctxh_days_cumulative": cumulative_ctxh,
                "english_pass": term_english_pass,
                "thesis_eligible_before_semester": (
                    before_english_pass
                    and _ctxh_days_for_semester(
                        progress,
                        semester,
                        before=True,
                    )
                    >= GENERATOR_CONFIG["student_progress"]["ctxh"][
                        "minimum_for_thesis"
                    ]
                ),
                "semester_complete": complete,
                "academic_suspension": academic_suspension,
            })
            observed_count += 1
            if academic_suspension:
                continue
            if is_academic_dismissal(student_id, semester, GENERATOR_CONFIG):
                forced_semester = semester
                forced_reason = "overdue_more_than_two_years"
                break

        exit_semester = forced_semester
        dropout_reason = forced_reason
        if voluntary_event and (
            exit_semester is None
            or semester_index(voluntary_semester) <= semester_index(exit_semester)
        ):
            exit_semester = voluntary_semester
            dropout_reason = str(
                profile.get("voluntary_dropout_reason", "")
                or "voluntary"
            )
        dropped_out = exit_semester is not None
        graduation_semester = details["graduation_semester"]
        if dropped_out and graduation_semester:
            if dropout_reason == "overdue_more_than_two_years":
                if semester_index(graduation_semester) < semester_index(
                    exit_semester
                ):
                    dropped_out = False
                    dropout_reason = ""
                    exit_semester = None
                else:
                    graduation_semester = None
            elif semester_index(graduation_semester) <= semester_index(
                exit_semester
            ):
                dropped_out = False
                dropout_reason = ""
                exit_semester = None
            else:
                graduation_semester = None

        standard_terms = graduation_config["standard_semesters"]
        timing = "not_graduated"
        if graduation_semester:
            completion_count = sum(
                semester_index(semester) <= semester_index(graduation_semester)
                for semester in student_semesters
            )
            timing = (
                "early"
                if completion_count < standard_terms
                else "on_time"
                if completion_count == standard_terms
                else "late"
            )
        degree_classification = "not_graduated"
        if graduation_semester and pd.notna(details["gpa_4"]):
            for band in graduation_config["degree_classification_gpa4"]:
                if band.get("label") == "excellent":
                    if band["min"] <= float(details["gpa_4"]) <= band["max"]:
                        degree_classification = band["label"]
                        break
                elif band["min"] <= float(details["gpa_4"]) < band["max"]:
                    degree_classification = band["label"]
                    break
        if dropout_reason == "overdue_more_than_two_years":
            dropout_type = "forced"
        elif dropped_out:
            dropout_type = "voluntary"
        else:
            dropout_type = "none"
        student_rows.append({
            "student_id": student_id,
            "cohort": f"K{str(student_id)[:2]}",
            "family_income": profile["family_income"],
            "financial_pressure": profile["financial_pressure"],
            "living_condition": profile["living_condition"],
            "discipline": profile["discipline"],
            "motivation": profile["motivation"],
            "stress": profile["stress"],
            "social_activity": profile["social_activity"],
            "academic_level": profile["academic_level"],
            "english_level": profile["english_level"],
            "profile_strength": round(
                (
                    (float(profile["academic_level"]) - 1) / 4
                    + np.mean([
                        (float(profile["discipline"]) - 1) / 4,
                        (float(profile["motivation"]) - 1) / 4,
                        (float(profile["social_activity"]) - 1) / 4,
                        (5 - float(profile["stress"])) / 4,
                    ])
                ) / 2,
                4,
            ),
            "tracked_semesters": observed_count,
            "registered_semesters": int(
                student_history.loc[
                    student_history["semester_code"].isin(
                        student_semesters[:observed_count]
                    ),
                    "semester_code",
                ].nunique()
            ),
            "empty_semesters": max(
                0,
                observed_count
                - student_history.loc[
                    student_history["semester_code"].isin(
                        student_semesters[:observed_count]
                    ),
                    "semester_code",
                ].nunique(),
            ),
            "last_observed_semester": (
                student_semesters[observed_count - 1]
                if observed_count
                else ""
            ),
            "english_pass": details["english_pass"],
            "ctxh_days_cumulative": details["ctxh_days"],
            "thesis_eligible": details["thesis_eligible"],
            "passed_credits": details["passed_credits"],
            "gpa_4": details["gpa_4"],
            "gpa_10": details["gpa_10"],
            "graduation_ready": details["graduation_ready"] and not dropped_out,
            "academic_suspension_count": sum(
                semester in suspension_semesters
                for semester in student_semesters[:observed_count]
            ),
            "academic_suspension_semesters": ";".join(
                semester
                for semester in student_semesters[:observed_count]
                if semester in suspension_semesters
            ),
            "graduation_semester": graduation_semester or "",
            "graduation_timing": timing,
            "degree_classification": degree_classification,
            "dropout": dropped_out,
            "dropout_type": dropout_type,
            "dropout_reason": dropout_reason,
            "dropout_semester": exit_semester or "",
            "missing_required_courses": details["missing_required_courses"],
        })

    return pd.DataFrame(progress_rows), pd.DataFrame(student_rows)


def _distribution_tables(history):
    graded = history.copy()
    graded["final_score"] = pd.to_numeric(graded["final_score"], errors="coerce")
    graded["gpa_4"] = pd.to_numeric(graded["gpa_4"], errors="coerce")
    graded = graded.dropna(subset=["final_score", "gpa_4"])
    if graded.empty:
        return pd.DataFrame(), pd.DataFrame()

    score_rows = []
    grade_rows = []
    course_groups = [("ALL_UNIVERSITY", graded)]
    course_groups.extend(
        (str(course_code), group)
        for course_code, group in graded.groupby("course_code", sort=True)
    )
    for course_code, group in course_groups:
        for scale, column, edges in (
            ("10-point", "final_score", np.arange(0, 11, 1)),
            ("4-point", "gpa_4", np.arange(0, 4.5, 0.5)),
        ):
            values = group[column].astype(float).clip(
                lower=edges[0], upper=edges[-1]
            )
            counts, _ = np.histogram(values, bins=edges)
            total = int(counts.sum())
            for index, count in enumerate(counts):
                score_rows.append({
                    "course_code": course_code,
                    "scale": scale,
                    "score_bin": f"{edges[index]:g}-{edges[index + 1]:g}",
                    "count": int(count),
                    "share": float(count / total) if total else 0.0,
                })
        grade_values = group["letter_grade"].fillna("").astype(str)
        grade_total = int(grade_values.isin(LETTER_GRADES).sum())
        for letter in LETTER_GRADES:
            count = int(grade_values.eq(letter).sum())
            grade_rows.append({
                "course_code": course_code,
                "letter_grade": letter,
                "count": count,
                "share": float(count / grade_total) if grade_total else 0.0,
            })
    return pd.DataFrame(score_rows), pd.DataFrame(grade_rows)


def _summary_metrics(student_metrics, history):
    tracked_count = len(student_metrics)
    graduates = student_metrics[
        student_metrics["graduation_timing"].isin(["early", "on_time", "late"])
    ]
    dropped = student_metrics[student_metrics["dropout"]]
    rows = []

    def add(name, value, numerator=None, denominator=None):
        rows.append({
            "metric": name,
            "value": value,
            "numerator": numerator,
            "denominator": denominator,
        })

    add("tracked_students", tracked_count)
    for field in (
        "family_income",
        "financial_pressure",
        "living_condition",
        "academic_level",
    ):
        for category, count in student_metrics[field].value_counts(
            dropna=False
        ).items():
            add(
                f"profile_{field}_{category}_share",
                count / tracked_count if tracked_count else 0.0,
                int(count),
                tracked_count,
            )
    for field in (
        "profile_strength",
        "english_level",
        "ctxh_days_cumulative",
        "passed_credits",
        "gpa_4",
        "gpa_10",
    ):
        values = pd.to_numeric(student_metrics[field], errors="coerce").dropna()
        add(
            f"profile_{field}_mean",
            float(values.mean()) if len(values) else pd.NA,
            len(values),
            tracked_count,
        )
    for field, metric in (
        ("english_pass", "english_eligibility_rate"),
        ("thesis_eligible", "thesis_eligibility_rate"),
        ("graduation_ready", "graduation_ready_rate"),
    ):
        count = int(student_metrics[field].fillna(False).astype(bool).sum())
        add(
            metric,
            count / tracked_count if tracked_count else 0.0,
            count,
            tracked_count,
        )
    add(
        "dropout_rate",
        len(dropped) / tracked_count if tracked_count else 0.0,
        len(dropped),
        tracked_count,
    )
    suspended = student_metrics["academic_suspension_count"].gt(0)
    add(
        "academic_suspension_rate",
        int(suspended.sum()) / tracked_count if tracked_count else 0.0,
        int(suspended.sum()),
        tracked_count,
    )
    add(
        "academic_suspension_count_mean",
        float(student_metrics["academic_suspension_count"].mean())
        if tracked_count
        else 0.0,
        int(student_metrics["academic_suspension_count"].sum()),
        tracked_count,
    )
    for dropout_type in ("voluntary", "forced"):
        count = int(student_metrics["dropout_type"].eq(dropout_type).sum())
        add(
            f"{dropout_type}_dropout_rate",
            count / tracked_count if tracked_count else 0.0,
            count,
            tracked_count,
        )
    for reason in (
        "background",
        "academic",
        "overdue_more_than_two_years",
    ):
        count = int(student_metrics["dropout_reason"].eq(reason).sum())
        add(
            f"dropout_reason_{reason}_rate",
            count / tracked_count if tracked_count else 0.0,
            count,
            tracked_count,
        )
    for timing in ("early", "on_time", "late"):
        count = int(graduates["graduation_timing"].eq(timing).sum())
        add(
            f"graduation_{timing}_rate",
            count / len(graduates) if len(graduates) else 0.0,
            count,
            len(graduates),
        )
    for classification in (
        "average", "fairly_average", "fair", "fairly_good", "good", "excellent"
    ):
        count = int(
            graduates["degree_classification"].eq(classification).sum()
        )
        add(
            f"degree_{classification}_rate",
            count / len(graduates) if len(graduates) else 0.0,
            count,
            len(graduates),
        )

    graded = history.copy()
    graded["final_score"] = pd.to_numeric(graded["final_score"], errors="coerce")
    graded["gpa_4"] = pd.to_numeric(graded["gpa_4"], errors="coerce")
    for label, column in (("score_10", "final_score"), ("score_4", "gpa_4")):
        values = graded[column].dropna()
        add(f"{label}_count", len(values))
        add(f"{label}_mean", float(values.mean()) if len(values) else pd.NA)
        add(f"{label}_median", float(values.median()) if len(values) else pd.NA)
        add(f"{label}_std", float(values.std()) if len(values) > 1 else 0.0)
    grade_values = graded["letter_grade"].fillna("").astype(str)
    total_grades = int(grade_values.isin(LETTER_GRADES).sum())
    for letter in LETTER_GRADES:
        count = int(grade_values.eq(letter).sum())
        add(
            f"grade_{letter}_rate",
            count / total_grades if total_grades else 0.0,
            count,
            total_grades,
        )
    return pd.DataFrame(rows)


def _english_eligibility_metrics(progress):
    if progress.empty:
        return pd.DataFrame(columns=[
            "semester", "eligible_students", "tracked_students", "rate",
        ])
    rows = []
    for semester, group in progress.groupby("semester", sort=False):
        denominator = len(group)
        numerator = int(group["english_pass"].fillna(False).astype(bool).sum())
        rows.append({
            "semester": semester,
            "eligible_students": numerator,
            "tracked_students": denominator,
            "rate": numerator / denominator if denominator else 0.0,
        })
    return pd.DataFrame(rows)


def _normalize_cohort(cohort):
    if cohort is None:
        return None
    value = str(cohort).strip().upper()
    if value.startswith("K"):
        value = value[1:]
    if len(value) != 2 or not value.isdigit():
        raise ValueError("Cohort must be a two-digit year such as 20 or K20")
    return value


def generate_academic_metrics(cohort=None):
    cohort = _normalize_cohort(cohort)
    profiles = pd.read_csv(PROFILE_OUTPUT_FILE, dtype={"student_id": str})
    students = pd.read_csv(STUDENT_FILE, dtype=str)
    if "user_id" in students.columns and "student_id" not in students.columns:
        students = students.rename(columns={"user_id": "student_id"})
    if "cohort" not in students.columns:
        students["cohort"] = students["student_id"].str[:2]
    profiles = profiles.merge(
        students[["student_id", "cohort"]],
        on="student_id",
        how="left",
    )
    history, observed_semesters, tracked_ids = _load_enrollment_history(profiles)
    if cohort:
        cohort_ids = {
            student_id
            for student_id in tracked_ids
            if str(student_id).startswith(cohort)
        }
        history = history[history["student_id"].isin(cohort_ids)].copy()
        tracked_ids = cohort_ids
        profiles = profiles[
            profiles["student_id"].str.startswith(cohort)
        ].copy()
    course_catalog = pd.read_csv(COURSE_FILE, dtype={"course_code": str})
    credits = dict(zip(course_catalog["course_code"], course_catalog["credits"]))
    progress, student_metrics = _build_student_reports(
        profiles, history, observed_semesters, tracked_ids, credits
    )
    score_distribution, grade_distribution = _distribution_tables(history)
    metrics_dir = METRICS_DIR / f"K{cohort}" if cohort else METRICS_DIR
    metrics_dir.mkdir(parents=True, exist_ok=True)
    progress.to_csv(
        metrics_dir / "student_progress.csv",
        index=False,
        encoding="utf-8-sig",
    )
    _english_eligibility_metrics(progress).to_csv(
        metrics_dir / "english_eligibility_by_semester.csv",
        index=False,
        encoding="utf-8-sig",
    )
    student_metrics.to_csv(
        metrics_dir / "student_metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )
    score_distribution.to_csv(
        metrics_dir / "score_distribution.csv",
        index=False,
        encoding="utf-8-sig",
    )
    grade_distribution.to_csv(
        metrics_dir / "letter_grade_distribution.csv",
        index=False,
        encoding="utf-8-sig",
    )
    _summary_metrics(student_metrics, history).to_csv(
        metrics_dir / "university_metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print(
        f"Created student and university metrics for "
        f"{len(student_metrics)} students in {metrics_dir}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cohort",
        help="Limit reports to one cohort (for example, 20 or K20)",
    )
    generate_academic_metrics(parser.parse_args().cohort)
