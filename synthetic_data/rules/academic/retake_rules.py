"""Course retake policies, failed course recovery, and grade improvement rules under credit caps."""

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

from .common import COHORT_START_SEMESTER, ROOT_DIR
from .config import GENERATOR_CONFIG
from .standing_rules import is_student_active_for_semester, semester_index
from .scoring_rules import convert_score_to_grade, score_course_components
from curriculum_rules import can_share_class, get_tq_prerequisite_map

_PROFILES_CACHE = None


def _get_profiles_cache() -> Dict[str, Dict[str, Any]]:
    global _PROFILES_CACHE
    if _PROFILES_CACHE is None:
        p_path = ROOT_DIR / "generated" / "users" / "student_profiles.csv"
        if p_path.exists():
            try:
                df = pd.read_csv(p_path, dtype={"student_id": str})
                _PROFILES_CACHE = df.set_index("student_id").to_dict(orient="index")
            except Exception:
                _PROFILES_CACHE = {}
        else:
            _PROFILES_CACHE = {}
    return _PROFILES_CACHE


def filter_retake_demand_by_credit_limit(
    retake_demand: Dict[str, List[str]],
    credits_map: Dict[str, float],
    current_semester: str,
    max_regular_term_retake_credits: float = 4.0,
    max_regular_term_retake_courses: int = 1,
    max_extension_term_retake_credits: float = 22.0,
    max_extension_term_retake_courses: int = 6,
    student_assigned_creds: Optional[Dict[str, float]] = None,
    student_assigned_count: Optional[Dict[str, int]] = None,
    profiles: Optional[Any] = None,
) -> Dict[str, List[str]]:
    """Filter retake_demand dictionary to prevent student credit overloading
    and exclude students who have dropped out or been dismissed.
    """
    curr_idx = semester_index(current_semester)
    filtered: Dict[str, List[str]] = defaultdict(list)
    if student_assigned_creds is None:
        student_assigned_creds = defaultdict(float)
    if student_assigned_count is None:
        student_assigned_count = defaultdict(int)

    active_profiles = profiles if profiles is not None else _get_profiles_cache()

    for cid, sids in retake_demand.items():
        tc = float(credits_map.get(cid, 3.0))
        for sid in sids:
            sid = str(sid)
            # Filter out inactive students (voluntary dropout or dismissal)
            if not is_student_active_for_semester(sid, current_semester, profiles=active_profiles):
                continue

            coh = sid[:2]
            start_sem = COHORT_START_SEMESTER.get(coh)
            term_num = (curr_idx - semester_index(start_sem) + 1) if start_sem else 1

            if term_num <= 8:
                max_creds = 3.0 if term_num == 5 else max_regular_term_retake_credits
                max_courses = max_regular_term_retake_courses
            else:
                max_creds = max_extension_term_retake_credits
                max_courses = max_extension_term_retake_courses

            if (student_assigned_count[sid] < max_courses and 
                (student_assigned_creds[sid] + tc) <= max_creds):
                filtered[cid].append(sid)
                student_assigned_creds[sid] += tc
                student_assigned_count[sid] += 1

    return filtered


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
    max_credits_per_semester: float = 22.0,
) -> List[Dict[str, Any]]:
    """Identify students with cumulative GPA 4 < 2.0 in late semesters (Term 7+) and register them
    for 1-2 improvement retakes respecting max_credits_per_semester (22.0).
    """
    curr_idx = semester_index(semester)

    # 1. Identify which cohorts are in Term 7 or later during this semester
    target_cohorts = [
        coh for coh, start in COHORT_START_SEMESTER.items()
        if curr_idx - semester_index(start) + 1 >= 7
    ]
    if not target_cohorts:
        return []

    # Map student to program
    student_program_map: Dict[str, str] = {}
    if not df_students.empty and "student_id" in df_students.columns and "program" in df_students.columns:
        for _, row in df_students.iterrows():
            student_program_map[str(row["student_id"])] = str(row["program"])

    # Map course_id to open class_id list by program
    open_classes_by_course_prog: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    if not df_classes.empty:
        for _, c_row in df_classes.iterrows():
            cid = str(c_row["course_code"])
            cls_id = str(c_row["class_id"])
            c_grp = str(c_row["class_group"])
            if c_grp.startswith("TT"):
                prog = "advanced"
            elif c_grp.startswith("CC"):
                prog = "high-quality"
            else:
                prog = "standard"
            open_classes_by_course_prog[(cid, prog)].append(cls_id)

    # 2. Gather full historical grades
    all_prev_records: List[Dict[str, Any]] = []
    if prev_enrollments is not None and not prev_enrollments.empty:
        all_prev_records.extend(prev_enrollments.to_dict("records"))
    elif enrollments_dir is not None:
        pass

    if not all_prev_records:
        return []

    df_hist = pd.DataFrame(all_prev_records)
    if "student_id" not in df_hist.columns or "gpa_4" not in df_hist.columns:
        return []

    # Calculate current credits already taken in this semester
    current_credits_by_student: Dict[str, float] = defaultdict(float)
    already_enrolled_courses: Dict[str, Set[str]] = defaultdict(set)
    for rec in current_records:
        sid = str(rec["student_id"])
        cid = str(rec.get("course_id", ""))
        already_enrolled_courses[sid].add(cid)
        tc = float(credits_map.get(cid, 3.0))
        current_credits_by_student[sid] += tc

    # 3. Compute best grade and cumulative GPA 4 for each student
    hist_by_student: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for _, row in df_hist.iterrows():
        hist_by_student[str(row["student_id"])].append(row.to_dict())

    improvement_records: List[Dict[str, Any]] = []
    enrollment_id = start_enrollment_id
    is_active_sem = (str(semester).upper() == "HK261")
    active_profiles = student_profiles if student_profiles is not None else _get_profiles_cache()
    tq_map = get_tq_prerequisite_map()

    for sid, records in hist_by_student.items():
        coh = sid[:2]
        if coh not in target_cohorts:
            continue
        if not is_student_active_for_semester(sid, semester, profiles=active_profiles):
            continue

        best_by_course: Dict[str, Dict[str, Any]] = {}
        for r in records:
            cid = str(r["course_id"])
            g = float(r.get("gpa_4", 0.0))
            if cid not in best_by_course or g > float(best_by_course[cid].get("gpa_4", 0.0)):
                best_by_course[cid] = r

        total_creds = 0.0
        weighted_points = 0.0
        for cid, r in best_by_course.items():
            if str(r.get("passed", "True")).lower() in ("true", "1") or float(r.get("final_score", 0.0)) >= 5.0:
                tc = float(credits_map.get(cid, 3.0))
                total_creds += tc
                weighted_points += float(r.get("gpa_4", 0.0)) * tc

        if total_creds <= 0:
            continue
        cpa = weighted_points / total_creds

        # If student's GPA 4 is < 2.0 (threat of not graduating):
        if cpa < 2.0:
            passed_courses_set = {
                c for c, cr in best_by_course.items()
                if str(cr.get("passed", "True")).lower() in ("true", "1") or float(cr.get("final_score", 0.0)) >= 5.0
            }
            candidates: List[Tuple[float, float, str, Dict[str, Any]]] = []
            for cid, r in best_by_course.items():
                g = float(r.get("gpa_4", 0.0))
                passed = str(r.get("passed", "True")).lower() in ("true", "1") or float(r.get("final_score", 0.0)) >= 5.0
                tq_reqs = tq_map.get(cid, set())
                if (
                    passed
                    and g in (1.0, 1.5)
                    and cid not in already_enrolled_courses[sid]
                    and cid not in ("CO4337", "CO4029")
                    and tq_reqs.issubset(passed_courses_set)
                ):
                    tc = float(credits_map.get(cid, 3.0))
                    candidates.append((g, tc, cid, r))

            if not candidates:
                continue

            candidates.sort(key=lambda x: (x[0], -x[1]))

            prog = student_program_map.get(sid, "standard")
            selected_courses = candidates[:max_courses_per_student]

            for _, tc, cid, _ in selected_courses:
                if current_credits_by_student[sid] + tc > max_credits_per_semester:
                    continue

                open_classes = open_classes_by_course_prog.get((cid, prog), [])
                if not open_classes:
                    for (c, p), clist in open_classes_by_course_prog.items():
                        if c == cid and can_share_class(prog, p):
                            open_classes = clist
                            break

                if not open_classes:
                    continue

                idx = int(hash(f"{sid}:{cid}:{semester}")) % len(open_classes)
                chosen_class_id = open_classes[idx]

                comps = course_assessments.get(cid, [("exam", 1.0)])
                std_prof = student_profiles.get(sid, {})
                rng = np.random.default_rng(abs(hash(f"{sid}:{chosen_class_id}:retake")) % (2**32))

                scores, final_score, letter, gpa = score_course_components(
                    std_prof,
                    cid,
                    comps,
                    3.0,
                    rng,
                    retaken=True,
                    student_id=sid,
                )

                already_enrolled_courses[sid].add(cid)
                current_credits_by_student[sid] += tc

                if is_active_sem:
                    rec = {
                        "enrollment_id": enrollment_id,
                        "student_id": sid,
                        "class_id": chosen_class_id,
                        "course_id": cid,
                        "semester": semester,
                        "retaken": True,
                        "quiz": scores.get("quiz", np.nan),
                        "lab": scores.get("lab", np.nan),
                        "btl": scores.get("btl", np.nan),
                        "giua_ky": scores.get("giua_ky", np.nan),
                        "cuoi_ky": np.nan,
                        "final_score": np.nan,
                        "letter_grade": np.nan,
                        "gpa_4": np.nan,
                        "passed": np.nan,
                        "status": np.nan,
                        "assignment_score": np.nan,
                        "quiz_score": scores.get("quiz", np.nan),
                        "lab_score": scores.get("lab", np.nan),
                        "midterm_score": scores.get("giua_ky", np.nan),
                        "semester_gpa": np.nan,
                        "cumulative_gpa": np.nan,
                    }
                else:
                    passed_val = (letter != "F")
                    rec = {
                        "enrollment_id": enrollment_id,
                        "student_id": sid,
                        "class_id": chosen_class_id,
                        "course_id": cid,
                        "semester": semester,
                        "retaken": True,
                        "quiz": scores.get("quiz", np.nan),
                        "lab": scores.get("lab", np.nan),
                        "btl": scores.get("btl", np.nan),
                        "giua_ky": scores.get("giua_ky", np.nan),
                        "cuoi_ky": scores.get("cuoi_ky", np.nan),
                        "final_score": final_score,
                        "letter_grade": letter,
                        "gpa_4": gpa,
                        "passed": passed_val,
                        "status": "Pass" if passed_val else "Fail",
                        "assignment_score": np.nan,
                        "quiz_score": scores.get("quiz", np.nan),
                        "lab_score": scores.get("lab", np.nan),
                        "midterm_score": scores.get("giua_ky", np.nan),
                        "semester_gpa": np.nan,
                        "cumulative_gpa": np.nan,
                    }
                improvement_records.append(rec)
                enrollment_id += 1

    return improvement_records

