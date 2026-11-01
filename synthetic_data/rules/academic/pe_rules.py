"""Physical Education (GDTC) Academic Rules and Allocation Engine.

Encapsulates all domain rules for Physical Education courses (PE1009 - PE1063):
1. 12 Sport Pairs: Each HP1 sport (HK1) maps to an exact corresponding HP2 sport (HK2).
2. Continuity Rule: A student taking HP1 in sport X must take HP2 in that exact same sport X.
3. Assessment: 100% Final Exam score only (cuoi_ky = final_score, quiz = lab = btl = giua_ky = nan).
4. Section Sizing: Max capacity 40 per section, balanced section sizes without empty classes.
5. Lecturer Balancing: Rotates sections across Physical Education lecturers (GV00206 - GV00209).
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from .scoring_rules import score_course_components
from .allocation_rules import balanced_class_sizes


# 12 Standardized Physical Education Sport Pairs
SPORT_PAIRS: Dict[str, str] = {
    "PE1009": "PE1033",  # Bóng đá
    "PE1011": "PE1035",  # Bóng chuyền
    "PE1013": "PE1037",  # Bóng bàn
    "PE1015": "PE1039",  # Bóng rổ
    "PE1017": "PE1041",  # Cầu lông
    "PE1019": "PE1043",  # Bơi
    "PE1021": "PE1045",  # Aerobic
    "PE1025": "PE1049",  # Điền kinh
    "PE1027": "PE1051",  # Quần vợt
    "PE1053": "PE1055",  # Cờ vua
    "PE1057": "PE1059",  # Bowling
    "PE1061": "PE1063",  # Pickleball
}

REVERSE_SPORT_PAIRS: Dict[str, str] = {v: k for k, v in SPORT_PAIRS.items()}

HP1_SPORTS: List[str] = list(SPORT_PAIRS.keys())
HP2_SPORTS: List[str] = list(SPORT_PAIRS.values())
ALL_PE_SPORTS: List[str] = HP1_SPORTS + HP2_SPORTS

SPORT_NAMES: Dict[str, str] = {
    "PE1009": "Bóng đá (Học phần 1)",
    "PE1011": "Bóng chuyền (Học phần 1)",
    "PE1013": "Bóng bàn (Học phần 1)",
    "PE1015": "Bóng rổ (Học phần 1)",
    "PE1017": "Cầu lông (Học phần 1)",
    "PE1019": "Bơi (Học phần 1)",
    "PE1021": "Aerobic (Học phần 1)",
    "PE1025": "Điền kinh (Học phần 1)",
    "PE1027": "Quần vợt (Học phần 1)",
    "PE1053": "Cờ vua (Học phần 1)",
    "PE1057": "Bowling (Học phần 1)",
    "PE1061": "Pickleball (Học phần 1)",
    "PE1033": "Bóng đá (Học phần 2)",
    "PE1035": "Bóng chuyền (Học phần 2)",
    "PE1037": "Bóng bàn (Học phần 2)",
    "PE1039": "Bóng rổ (Học phần 2)",
    "PE1041": "Cầu lông (Học phần 2)",
    "PE1043": "Bơi (Học phần 2)",
    "PE1045": "Aerobic (Học phần 2)",
    "PE1049": "Điền kinh (Học phần 2)",
    "PE1051": "Quần vợt (Học phần 2)",
    "PE1055": "Cờ vua (Học phần 2)",
    "PE1059": "Bowling (Học phần 2)",
    "PE1063": "Pickleball (Học phần 2)",
}


def assign_student_hp1_sport(student_id: str) -> str:
    """Deterministically assign freshman to one of the 12 HP1 sports using student_id hash."""
    h = hashlib.sha256(f"{student_id}:pe_sport_selection".encode("utf-8")).hexdigest()
    idx = int(h[:8], 16) % len(HP1_SPORTS)
    return HP1_SPORTS[idx]


def get_student_hp2_sport(
    student_id: str,
    prev_enrollments: Optional[Union[pd.DataFrame, List[pd.DataFrame]]] = None,
) -> str:
    """Retrieve the exact paired HP2 sport corresponding to student's HP1 enrollment."""
    if prev_enrollments is not None:
        if isinstance(prev_enrollments, list):
            if len(prev_enrollments) > 0:
                prev_df = pd.concat(prev_enrollments, ignore_index=True)
            else:
                prev_df = pd.DataFrame()
        else:
            prev_df = prev_enrollments

        if not prev_df.empty:
            sid_str = str(student_id)
            pe_sub = prev_df[
                (prev_df["student_id"].astype(str) == sid_str)
                & (prev_df["course_id"].isin(HP1_SPORTS))
            ]
            if not pe_sub.empty:
                hp1_course = str(pe_sub.iloc[0]["course_id"])
                if hp1_course in SPORT_PAIRS:
                    return SPORT_PAIRS[hp1_course]

    # Deterministic fallback consistent with assign_student_hp1_sport
    hp1 = assign_student_hp1_sport(student_id)
    return SPORT_PAIRS[hp1]


def build_pe_classes_for_semester(
    semester: str,
    term_type: int,  # 1 for HP1 (odd semester), 2 for HP2 (even semester)
    freshmen_df: pd.DataFrame,
    lecturers: List[Dict[str, Any]],
    assigned_count: Dict[str, int],
    program_config: Dict[str, Any],
    prev_enrollments: Optional[pd.DataFrame] = None,
    max_capacity: int = 40,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Generate balanced class sections for all Physical Education sports in the semester.

    Returns:
        (pe_classes, student_sport_map)
    """
    classes: List[Dict[str, Any]] = []
    student_sport_map: Dict[str, str] = {}

    # 1. Determine each student's sport
    for _, row in freshmen_df.iterrows():
        sid = str(row["user_id"])
        if term_type == 1:
            sport = assign_student_hp1_sport(sid)
        else:
            sport = get_student_hp2_sport(sid, prev_enrollments)
        student_sport_map[sid] = sport

    # 2. Filter PE lecturers (Bộ môn Giáo dục Thể chất)
    pe_lecturers = [
        g for g in lecturers
        if "thể chất" in str(g.get("department", "")).lower() or "thể dục" in str(g.get("department", "")).lower()
    ]
    if not pe_lecturers:
        pe_lecturers = lecturers  # Fallback if unassigned

    # 3. For each program and each sport, allocate balanced classes
    for prog, cfg in program_config.items():
        prefix = cfg["prefix"]
        prog_students = freshmen_df[freshmen_df["program"] == prog]
        prog_uids = set(prog_students["user_id"].astype(str))

        sports_list = HP1_SPORTS if term_type == 1 else HP2_SPORTS
        for sport_code in sports_list:
            sport_students = [
                uid for uid in prog_uids if student_sport_map.get(uid) == sport_code
            ]
            demand = len(sport_students)
            if demand <= 0:
                continue

            sizes = balanced_class_sizes(demand, max_size=max_capacity)
            c_name = SPORT_NAMES.get(sport_code, sport_code)

            for idx, size in enumerate(sizes, start=1):
                group_code = f"{prefix}{idx:02d}"

                # Round-robin greedy load balancing across PE lecturers
                best_gv = min(
                    pe_lecturers,
                    key=lambda g: (assigned_count[g["user_id"]], g["user_id"]),
                )
                assigned_count[best_gv["user_id"]] += 1

                classes.append({
                    "class_id": f"{semester}_{sport_code}_{group_code}",
                    "course_code": sport_code,
                    "course_name": c_name,
                    "semester": semester,
                    "class_group": group_code,
                    "program": prog,
                    "max_capacity": max_capacity,
                    "lecturer_id": best_gv["user_id"],
                    "lecturer_name": best_gv["name"],
                    "department": "Bộ môn Giáo dục Thể chất",
                })

    return classes, student_sport_map


def build_pe_enrollments_for_semester(
    semester: str,
    term_type: int,
    freshmen_df: pd.DataFrame,
    pe_classes: List[Dict[str, Any]],
    student_sport_map: Dict[str, str],
    student_profiles: Dict[str, Any],
    start_enrollment_id: int,
    config: Dict[str, Any],
    is_ongoing: bool = False,
) -> List[Dict[str, Any]]:
    """Enroll freshmen into Physical Education classes with 100% cuoi_ky component scoring.

    Returns:
        List of enrollment record dicts.
    """
    enrollment_records: List[Dict[str, Any]] = []
    enrollment_id = start_enrollment_id

    # Group classes by (program, course_code)
    classes_by_prog_course: Dict[Tuple[str, str], List[str]] = {}
    for cl in pe_classes:
        key = (cl["program"], cl["course_code"])
        classes_by_prog_course.setdefault(key, []).append(cl["class_id"])

    # Process per program and sport
    programs = freshmen_df["program"].unique()
    sports_list = HP1_SPORTS if term_type == 1 else HP2_SPORTS

    for prog in programs:
        prog_students = freshmen_df[freshmen_df["program"] == prog]
        prog_uids = prog_students["user_id"].astype(str).tolist()

        for sport_code in sports_list:
            assigned_uids = [
                uid for uid in prog_uids if student_sport_map.get(uid) == sport_code
            ]
            if not assigned_uids:
                continue

            class_ids = classes_by_prog_course.get((prog, sport_code), [])
            if not class_ids:
                continue

            sizes = balanced_class_sizes(len(assigned_uids), max_size=40)
            offset = 0

            # 100% final exam only assessment
            comps = [("cuoi_ky", 1.0)]

            for class_id, size in zip(class_ids, sizes):
                chunk = assigned_uids[offset : offset + size]
                offset += size

                for uid in chunk:
                    if is_ongoing:
                        rec = {
                            "enrollment_id": enrollment_id,
                            "student_id": uid,
                            "class_id": class_id,
                            "course_id": sport_code,
                            "semester": semester,
                            "retaken": False,
                            "quiz": np.nan,
                            "lab": np.nan,
                            "btl": np.nan,
                            "giua_ky": np.nan,
                            "cuoi_ky": np.nan,
                            "final_score": np.nan,
                            "letter_grade": np.nan,
                            "gpa_4": np.nan,
                            "passed": np.nan,
                            "status": np.nan,
                        }
                    else:
                        profile = student_profiles.get(uid, {})
                        student_data = {"student_id": uid, **profile}

                        seed_str = f"{uid}:{sport_code}:{semester}"
                        rng = np.random.default_rng(
                            int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
                        )

                        component_scores, final_score, letter, gpa = score_course_components(
                            student=student_data,
                            course_code=sport_code,
                            components=comps,
                            catalog_difficulty=0.0,
                            rng=rng,
                            config=config,
                            retaken=False,
                            student_id=uid,
                        )

                        rec = {
                            "enrollment_id": enrollment_id,
                            "student_id": uid,
                            "class_id": class_id,
                            "course_id": sport_code,
                            "semester": semester,
                            "retaken": False,
                            "quiz": np.nan,
                            "lab": np.nan,
                            "btl": np.nan,
                            "giua_ky": np.nan,
                            "cuoi_ky": component_scores.get("cuoi_ky", final_score),
                            "final_score": final_score,
                            "letter_grade": letter,
                            "gpa_4": gpa,
                            "passed": letter != "F",
                            "status": "Pass" if letter != "F" else "Fail",
                        }
                    enrollment_records.append(rec)
                    enrollment_id += 1

    return enrollment_records
