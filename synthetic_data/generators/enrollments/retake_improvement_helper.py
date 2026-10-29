"""Helper module for generating grade improvement retakes for students in late semesters (Term 7+).

Under HCMUT / BKU academic regulations:
- In late semesters (Terms 7, 8 and extension Terms 9-12), students with cumulative GPA 4 < 2.0
  are eligible to retake 1-2 previously passed courses with low grades (D = 1.0, D+ = 1.5).
- The improved grade replaces the previous lower grade in GPA calculation, pulling their
  cumulative GPA above 2.0 so they can graduate validly.
"""

import hashlib
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

# Path configuration
ROOT_DIR = Path(__file__).resolve().parents[2]
RULES_DIR = ROOT_DIR / "rules"
if str(RULES_DIR) not in sys.path:
    sys.path.insert(0, str(RULES_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from rules.academic_rules import (
        GENERATOR_CONFIG,
        convert_score_to_grade,
        score_course_components,
        semester_index,
    )
except ImportError:
    from academic_rules import (
        GENERATOR_CONFIG,
        convert_score_to_grade,
        score_course_components,
        semester_index,
    )

COHORT_START = {
    "20": "HK201",
    "21": "HK211",
    "22": "HK221",
    "23": "HK231",
    "24": "HK241",
    "25": "HK251",
    "26": "HK261",
}


def generate_grade_improvement_retakes(
    semester: str,
    prev_enrollments: Optional[pd.DataFrame],
    df_classes: pd.DataFrame,
    course_assessments: Dict[str, List[Tuple[str, float]]],
    credits_map: Dict[str, float],
    student_profiles: Dict[str, Dict[str, Any]],
    df_students: pd.DataFrame,
    current_records: List[Dict[str, Any]],
    start_enrollment_id: int,
    max_courses_per_student: int = 2,
    enrollments_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Identify students with cumulative GPA 4 < 2.0 in late semesters and register them

    for 1-2 improvement retakes.
    """
    curr_idx = semester_index(semester)

    # 1. Identify which cohorts are in Term 7 or later during this semester
    target_cohorts = [
        coh for coh, start in COHORT_START.items()
        if curr_idx - semester_index(start) + 1 >= 7
    ]
    if not target_cohorts:
        return []

    # 2. Ensure we have all past enrollments
    if prev_enrollments is None or prev_enrollments.empty:
        if enrollments_dir is None:
            enrollments_dir = Path(__file__).resolve().parent.parent.parent / "generated" / "enrollments"
        enr_files = sorted(enrollments_dir.glob("enrollment_hk*.csv"))
        past_dfs = []
        for f in enr_files:
            s_code = f.stem.replace("enrollment_", "").upper()
            if semester_index(s_code) < curr_idx:
                past_dfs.append(pd.read_csv(f, dtype=str))
        if not past_dfs:
            return []
        prev_enrollments = pd.concat(past_dfs, ignore_index=True)

    # Filter past enrollments to target cohorts
    df_target_students = df_students[
        df_students["user_id"].astype(str).str[:2].isin(target_cohorts)
    ].copy()
    valid_uids = set(df_target_students["user_id"].astype(str))

    # Pre-filter previous enrollments for these students
    df_past = prev_enrollments[prev_enrollments["student_id"].astype(str).isin(valid_uids)].copy()
    if df_past.empty:
        return []

    df_past["gpa_4"] = pd.to_numeric(df_past["gpa_4"], errors="coerce")
    df_past["final_score"] = pd.to_numeric(df_past["final_score"], errors="coerce")
    df_past["passed_bool"] = df_past["passed"].astype(str).str.lower().isin(["true", "pass", "exempted"])

    # Courses already taken in the current semester to avoid duplicate enrollment
    current_taken: Dict[str, Set[str]] = {}
    for r in current_records:
        sid = str(r["student_id"])
        if sid not in current_taken:
            current_taken[sid] = set()
        current_taken[sid].add(str(r["course_id"]))

    improvement_records: List[Dict[str, Any]] = []
    enrollment_id = start_enrollment_id

    # Group past enrollments by student
    grouped = df_past.groupby("student_id")

    for uid, u_rows in grouped:
        uid = str(uid)
        coh = uid[:2]
        start_sem = COHORT_START.get(coh)
        if not start_sem:
            continue
        term_num = curr_idx - semester_index(start_sem) + 1
        if term_num < 7 or term_num > 12:
            # Only Term 7 to Term 12 are active study/extension terms
            continue

        # Check voluntary dropout
        prof = student_profiles.get(uid, {})
        v_drop = prof.get("voluntary_dropout_semester")
        if v_drop and pd.notna(v_drop) and str(v_drop).strip():
            if semester_index(str(v_drop)) < curr_idx:
                continue

        # Look at passed courses
        u_passed = u_rows[u_rows["passed_bool"]].copy()
        if u_passed.empty:
            continue

        # Find best GPA 4 and final score per course
        best_scores: Dict[str, Dict[str, float]] = {}
        for cid, grp in u_passed.groupby("course_id"):
            cid = str(cid)
            g4_max = grp["gpa_4"].dropna().max()
            fs_max = grp["final_score"].dropna().max()
            tc = float(credits_map.get(cid, 0.0))
            if pd.notna(g4_max) and pd.notna(fs_max):
                best_scores[cid] = {
                    "gpa_4": float(g4_max),
                    "final_score": float(fs_max),
                    "credits": tc,
                }

        passed_cids = set(best_scores.keys())
        tot_passed_creds = sum(best_scores[c]["credits"] for c in passed_cids)
        gpa_courses = [
            c for c in passed_cids
            if best_scores[c]["final_score"] != 12.0 and best_scores[c]["credits"] > 0
        ]
        tot_gpa_creds = sum(best_scores[c]["credits"] for c in gpa_courses)
        current_gpa4 = (
            sum(best_scores[c]["gpa_4"] * best_scores[c]["credits"] for c in gpa_courses) / tot_gpa_creds
            if tot_gpa_creds > 0 else 0.0
        )

        # Check if student ALREADY graduated in an earlier semester
        # (met thesis, SP1007, 128 credits, and GPA4 >= 2.0)
        if {"CO4337", "SP1007"}.issubset(passed_cids) and tot_passed_creds >= 128.0 and current_gpa4 >= 2.0:
            continue

        # Check if student needs improvement
        if current_gpa4 >= 2.0:
            continue

        # Find candidate courses to improve (previously passed with gpa_4 <= 1.5, i.e. D or D+)
        u_current_taken = current_taken.get(uid, set())
        candidates = []
        for c in gpa_courses:
            if best_scores[c]["gpa_4"] <= 1.5:
                if c not in u_current_taken and c not in {"CO4337", "PE1003", "MI1003"}:
                    if best_scores[c]["credits"] > 0:
                        # Must have active classes in this semester
                        if not df_classes[df_classes["course_code"] == c].empty:
                            candidates.append(c)

        if not candidates:
            continue

        # Sort candidates:
        # 1. Lowest gpa_4 first (1.0 before 1.5)
        # 2. Highest credits first (4 TC before 3 TC before 2 TC)
        # 3. Lowest final_score first
        candidates.sort(key=lambda c: (
            best_scores[c]["gpa_4"],
            -best_scores[c]["credits"],
            best_scores[c]["final_score"],
        ))

        # Select up to max_courses_per_student
        chosen_courses = candidates[:max_courses_per_student]

        # Get student program
        u_prog_series = df_students.loc[df_students["user_id"].astype(str) == uid, "program"]
        prog = str(u_prog_series.values[0]) if not u_prog_series.empty else "standard"

        for cid in chosen_courses:
            # Find class in df_classes
            matching = df_classes[(df_classes["course_code"] == cid) & (df_classes["program"] == prog)]
            if matching.empty:
                matching = df_classes[df_classes["course_code"] == cid]
            if matching.empty:
                continue

            seed_hash = int(hashlib.sha256(f"{uid}:{cid}:{semester}".encode()).hexdigest()[:8], 16)
            class_id = matching.iloc[seed_hash % len(matching)]["class_id"]

            comps = course_assessments.get(cid, [("cuoi_ky", 1.0)])
            student_data = {"student_id": uid, **prof}
            seed_str = f"{uid}:{cid}:{semester}_improve_v2"
            rng = np.random.default_rng(int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16))

            comp_scores, final_score, letter, gpa = score_course_components(
                student=student_data,
                course_code=cid,
                components=comps,
                catalog_difficulty=0.5,
                rng=rng,
                config=GENERATOR_CONFIG,
                retaken=True,
                student_id=uid,
            )

            # Ensure the improved score is at least C+ / B (gpa >= 2.5, score >= 6.8):
            if final_score < 6.8:
                final_score = round(float(np.clip(final_score + 2.0, 6.8, 8.4)), 1)
                letter, gpa = convert_score_to_grade(final_score, GENERATOR_CONFIG)

            rec = {
                "enrollment_id": enrollment_id,
                "student_id": uid,
                "class_id": class_id,
                "course_id": cid,
                "semester": semester,
                "retaken": True,
                "quiz": comp_scores.get("quiz", np.nan),
                "lab": comp_scores.get("lab", np.nan),
                "btl": comp_scores.get("btl", np.nan),
                "giua_ky": comp_scores.get("giua_ky", np.nan),
                "cuoi_ky": comp_scores.get("cuoi_ky", np.nan),
                "final_score": final_score,
                "letter_grade": letter,
                "gpa_4": gpa,
                "passed": True,
                "status": "Pass",
            }
            if semester == "HK231":
                rec["semester_gpa"] = gpa
                rec["cumulative_gpa"] = gpa

            improvement_records.append(rec)
            enrollment_id += 1

    return improvement_records

