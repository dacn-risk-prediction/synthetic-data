"""Academic Curriculum Analysis Helpers.

Provides tools and helper functions to look up training programs, courses,
and prerequisite requirements for specific cohorts and semesters based on the
official BKU Computer Science & Engineering (CSE) curriculum catalog (K20 - K26).
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Directories
ROOT_DIR = Path(__file__).resolve().parents[1]
ACADEMICS_DIR = ROOT_DIR / "generated" / "academics"
USERS_DIR = ROOT_DIR / "generated" / "users"
CLASSES_DIR = ROOT_DIR / "generated" / "classes"
ENROLLMENTS_DIR = ROOT_DIR / "generated" / "enrollments"

CURRICULUMS_FILE = ACADEMICS_DIR / "curriculums.csv"
KNOWLEDGE_BLOCKS_FILE = ACADEMICS_DIR / "knowledge_blocks.csv"
COURSES_FILE = ACADEMICS_DIR / "courses.csv"
PROGRAM_STRUCTURES_FILE = ACADEMICS_DIR / "program_structures.csv"
PREREQUISITES_FILE = ACADEMICS_DIR / "course_prerequisites.csv"
SEMESTER_FILE = ACADEMICS_DIR / "semester.csv"
STUDENTS_FILE = USERS_DIR / "student.csv"
STUDENT_PROFILES_FILE = USERS_DIR / "student_profiles.csv"
CONFIG_FILE = ROOT_DIR / "config" / "generator_config.json"

# Global cache for academic datasets
_CACHE: Dict[str, Any] = {}

# Specialization alias mapping
SPECIALIZATION_ALIASES = {
    "ai": "Trí tuệ nhân tạo",
    "ttnt": "Trí tuệ nhân tạo",
    "ai_app": "Trí tuệ nhân tạo ứng dụng",
    "data": "Công nghệ dữ liệu và dữ liệu lớn",
    "bigdata": "Công nghệ dữ liệu và dữ liệu lớn",
    "data_sec": "Công nghệ Dữ liệu Bảo mật và Trí tuệ Kinh doanh",
    "se": "Công nghệ Phần mềm",
    "cnpm": "Công nghệ Phần mềm",
    "sec": "An ninh hệ thống và mạng",
    "security": "An ninh hệ thống và mạng",
    "crypto": "Mật mã và An ninh mạng",
    "vision": "Xử lý ảnh và Thị giác máy tính",
    "cs": "Khoa học Máy tính",
    "khmt": "Khoa học Máy tính",
}

# Standard Elective Roadmap Rules for BKU CSE
ELECTIVE_ROADMAP_RULES = {
    1: {"credits": 0, "desc": "100% môn học bắt buộc nền tảng Toán & KHTN, Nhập môn Điện toán."},
    2: {"credits": 0, "desc": "100% môn học bắt buộc Toán, Kỹ thuật Lập trình, GDQP."},
    3: {"credits": 0, "desc": "100% môn học bắt buộc Cơ sở ngành (DSA, Kiến trúc máy tính)."},
    4: {
        "credits": 3,
        "group": "Group D",
        "block_id": "MANAGEMENT",
        "desc": "Bắt buộc chọn 01 môn Quản lý Kỹ thuật (3 tín chỉ) thuộc Khối B.2.3.",
    },
    5: {
        "credits": 3,
        "group": "Free",
        "desc": "Khuyến nghị đăng ký 01 môn Tự chọn tự do (3 tín chỉ).",
    },
    6: {
        "credits": 7,
        "group": "Group A & C",
        "desc": (
            "Khuyến nghị đăng ký 02 môn Tự chọn Định hướng chuyên ngành (Group C, 6 tín chỉ) "
            "và 01 Đề án liên môn/Tích hợp (Group A, 1 tín chỉ)."
        ),
    },
    7: {
        "credits": 13,
        "group": "Group B & C & Free",
        "desc": (
            "Khuyến nghị đăng ký 03 môn Tự chọn Định hướng chuyên ngành (Group C, 9 tín chỉ), "
            "01 Đề án đa ngành (Group B, 1 tín chỉ) và 01 môn Tự chọn tự do (3 tín chỉ)."
        ),
    },
    8: {
        "credits": 3,
        "group": "Free",
        "desc": "Khuyến nghị hoàn thành nốt 01 môn Tự chọn tự do (3 tín chỉ) và Đồ án Tốt nghiệp.",
    },
}

RELATION_NAME_MAP = {
    "TQ": "Tiên quyết (phải thi đậu trước)",
    "KN": "Học trước / Khởi nguyên (phải từng tích lũy/học trước)",
    "SH": "Song hành (học đồng thời hoặc đã học trước)",
}


def _read_csv_dict(file_path: Path) -> List[Dict[str, str]]:
    """Read a CSV file with utf-8-sig encoding and clean column keys/values."""
    if not file_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file danh mục học vụ: {file_path}")

    records = []
    with open(file_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned_row = {
                (k.strip() if k else ""): (v.strip() if v else "")
                for k, v in row.items()
            }
            records.append(cleaned_row)
    return records


def load_academic_tables(force_reload: bool = False) -> Dict[str, Any]:
    """Load and cache all academic tables."""
    global _CACHE
    if _CACHE and not force_reload:
        return _CACHE

    curriculums = _read_csv_dict(CURRICULUMS_FILE)
    knowledge_blocks = _read_csv_dict(KNOWLEDGE_BLOCKS_FILE)
    courses = _read_csv_dict(COURSES_FILE)
    program_structures = _read_csv_dict(PROGRAM_STRUCTURES_FILE)
    prerequisites = _read_csv_dict(PREREQUISITES_FILE)

    # Indexing for high-performance lookup
    curriculum_by_id = {row["curriculum_id"]: row for row in curriculums}
    curriculum_by_cohort = {row["cohort"].upper(): row for row in curriculums}

    blocks_by_id = {row["block_id"]: row for row in knowledge_blocks}
    courses_by_code = {row["course_code"]: row for row in courses}

    prereqs_by_curr_course: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for p in prerequisites:
        key = (p["curriculum_id"], p["course_code"])
        prereqs_by_curr_course.setdefault(key, []).append(p)

    _CACHE = {
        "curriculums": curriculums,
        "curriculum_by_id": curriculum_by_id,
        "curriculum_by_cohort": curriculum_by_cohort,
        "knowledge_blocks": knowledge_blocks,
        "blocks_by_id": blocks_by_id,
        "courses": courses,
        "courses_by_code": courses_by_code,
        "program_structures": program_structures,
        "prerequisites": prerequisites,
        "prereqs_by_curr_course": prereqs_by_curr_course,
    }
    return _CACHE


def normalize_cohort(cohort: Union[str, int]) -> Tuple[int, str, str]:
    """Normalize cohort representation.

    Args:
        cohort: Cohort specifier, e.g. "K24", 24, "2024", "KHMT_K24".

    Returns:
        Tuple of (cohort_num, cohort_str, curriculum_id), e.g. (24, "K24", "KHMT_K24").
    """
    cohort_str = str(cohort).strip().upper()

    # Extract 2-digit cohort number
    match = re.search(r"(\d{2,4})", cohort_str)
    if not match:
        raise ValueError(f"Khóa sinh viên không hợp lệ: '{cohort}'")

    num_val = int(match.group(1))
    if num_val >= 2000:
        cohort_num = num_val - 2000
    else:
        cohort_num = num_val

    norm_cohort_str = f"K{cohort_num}"
    curriculum_id = f"KHMT_K{cohort_num}"

    tables = load_academic_tables()
    if norm_cohort_str not in tables["curriculum_by_cohort"]:
        available = ", ".join(sorted(tables["curriculum_by_cohort"].keys()))
        raise ValueError(
            f"Khóa '{norm_cohort_str}' không có trong danh mục đào tạo (Hiện có: {available})"
        )

    return cohort_num, norm_cohort_str, curriculum_id


def resolve_semester(
    cohort_num: int, semester: Union[str, int] = 1
) -> Dict[str, Any]:
    """Resolve an input semester (term number 1..8 or semester code) for a specific cohort.

    Supports:
        - Term number: 1, 2, 3, 4, 5, 6, 7, 8 (hoặc 'HK1', 'HK2', ..., 'HK8')
        - Absolute semester code: 'HK241', 'HK242', '241', '242', '20241'

    Returns:
        Dict containing relative_term, recommended_semester, academic_semester,
        status ('NORMAL', 'NOT_ENROLLED', 'BEYOND_STANDARD_DURATION'), and message.
    """
    sem_str = str(semester).strip().upper()

    # Case 1: Direct term number 1..8 (or 'HK1'..'HK8')
    rel_match = re.fullmatch(r"(?:HK)?(\d+)", sem_str)
    if rel_match:
        val = int(rel_match.group(1))
        # Standard 8-semester curriculum
        if 1 <= val <= 8:
            term_offset = (val - 1) // 2
            term_idx = 1 if (val % 2 != 0) else 2
            acad_year = cohort_num + term_offset
            academic_semester = f"HK{acad_year}{term_idx}"
            return {
                "relative_term": val,
                "recommended_semester": f"HK{val}",
                "academic_semester": academic_semester,
                "status": "NORMAL",
                "message": f"Học kỳ {val} theo lộ trình chuẩn (Năm học {academic_semester})",
            }
        elif 8 < val <= 14:
            term_offset = (val - 1) // 2
            term_idx = 1 if (val % 2 != 0) else 2
            acad_year = cohort_num + term_offset
            academic_semester = f"HK{acad_year}{term_idx}"
            return {
                "relative_term": val,
                "recommended_semester": f"HK{val}",
                "academic_semester": academic_semester,
                "status": "BEYOND_STANDARD_DURATION",
                "message": (
                    f"Học kỳ thứ {val} ({academic_semester}) vượt quá thời gian đào tạo chuẩn 4 năm (8 học kỳ). "
                    f"Giai đoạn này sinh viên chỉ học trả nợ, học vượt hoặc gia hạn tốt nghiệp."
                ),
            }
        elif val == 0:
            return {
                "relative_term": 0,
                "recommended_semester": "HK0",
                "academic_semester": f"HK{cohort_num}0",
                "status": "NOT_ENROLLED",
                "message": "Số học kỳ phải từ 1 đến 8 (HK1 - HK8 theo lộ trình chuẩn).",
            }

    # Case 2: Absolute semester, e.g. 'HK241', 'HK242', '241', '20241'
    abs_match = re.search(r"(\d{2,4})([1-3])$", sem_str)
    if abs_match:
        year_val = int(abs_match.group(1))
        acad_year = year_val - 2000 if year_val >= 2000 else year_val
        term_idx = int(abs_match.group(2))

        # Semester 3 is summer term (học kỳ hè)
        if term_idx == 3:
            relative_term = (acad_year - cohort_num) * 2
            return {
                "relative_term": relative_term,
                "recommended_semester": f"HK{relative_term}_HE",
                "academic_semester": f"HK{acad_year}3",
                "status": "SUMMER_TERM",
                "message": f"Học kỳ hè năm học 20{acad_year} (không có chương trình bắt buộc chuẩn)",
            }

        relative_term = (acad_year - cohort_num) * 2 + term_idx
        academic_semester = f"HK{acad_year}{term_idx}"

        if relative_term < 1:
            return {
                "relative_term": relative_term,
                "recommended_semester": f"HK{relative_term}",
                "academic_semester": academic_semester,
                "status": "NOT_ENROLLED",
                "message": (
                    f"Khóa K{cohort_num} chưa nhập học vào học kỳ {academic_semester} "
                    f"(Sinh viên nhập học vào HK{cohort_num}1)."
                ),
            }
        elif relative_term > 8:
            return {
                "relative_term": relative_term,
                "recommended_semester": f"HK{relative_term}",
                "academic_semester": academic_semester,
                "status": "BEYOND_STANDARD_DURATION",
                "message": (
                    f"Học kỳ {academic_semester} tương ứng học kỳ thứ {relative_term}, "
                    f"vượt quá thời gian đào tạo chuẩn 4 năm (8 học kỳ). "
                    f"Giai đoạn này sinh viên chỉ học trả nợ, học vượt hoặc gia hạn tốt nghiệp."
                ),
            }
        else:
            return {
                "relative_term": relative_term,
                "recommended_semester": f"HK{relative_term}",
                "academic_semester": academic_semester,
                "status": "NORMAL",
                "message": f"Học kỳ {relative_term} theo lộ trình chuẩn ({academic_semester})",
            }

    raise ValueError(
        f"Không nhận diện được học kỳ: '{semester}'. "
        f"Vui lòng chỉ cần nhập số học kỳ từ 1 đến 8 (hoặc mã học kỳ như 'HK241')."
    )


def normalize_specialization(spec_str: Optional[str]) -> Optional[str]:
    """Normalize specialization name from code or alias."""
    if not spec_str:
        return None
    cleaned = spec_str.strip().lower()
    return SPECIALIZATION_ALIASES.get(cleaned, spec_str.strip())


def get_course_prerequisites(
    curriculum_id: str,
    course_code: str,
    base_curriculum_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve prerequisite course constraints for a course in a curriculum."""
    tables = load_academic_tables()
    prereqs_map = tables["prereqs_by_curr_course"]

    # Try target curriculum first, fallback to base_curriculum_id
    raw_list = prereqs_map.get((curriculum_id, course_code))
    if not raw_list and base_curriculum_id:
        raw_list = prereqs_map.get((base_curriculum_id, course_code))

    if not raw_list:
        return []

    result = []
    for item in raw_list:
        rel_type = item.get("relation_type", "KN")
        result.append({
            "prerequisite_course_code": item.get("prerequisite_course_code", ""),
            "prerequisite_course_name_vi": item.get("prerequisite_course_name_vi", ""),
            "relation_type": rel_type,
            "relation_name": RELATION_NAME_MAP.get(rel_type, rel_type),
            "min_grade": float(item.get("min_grade", 0.0) or 0.0),
            "description": item.get("description", ""),
        })
    return result


def get_curriculum_for_cohort_semester(
    cohort: Union[str, int],
    semester: Union[str, int] = 1,
    specialization: Optional[str] = None,
    *,
    term: Optional[Union[str, int]] = None,
) -> Dict[str, Any]:
    """Retrieve curriculum courses and requirements for a cohort in a given semester.

    This is the core academic engine function. Simply pass cohort ('K24') and
    term number (1, 2, ..., 8).

    Args:
        cohort: Cohort identifier (e.g. "K24", 24, "2024", "KHMT_K24").
        semester: Semester number (1..8) or semester code ('HK241'). Defaults to 1.
        specialization: Optional specialization to filter elective courses.
        term: Optional keyword alias for semester (term number 1..8).

    Returns:
        Dict with comprehensive curriculum breakdown:
            - cohort, curriculum_id, curriculum_name, major_name
            - semester resolution (relative_term, academic_semester, status)
            - compulsory_courses: list of compulsory courses (BB)
            - total_compulsory_credits
            - elective_guidance: description and credit requirements
            - available_electives: list of elective courses for this stage
            - total_recommended_credits: sum of compulsory and recommended electives
    """
    target_sem = term if term is not None else semester
    tables = load_academic_tables()
    cohort_num, cohort_str, curriculum_id = normalize_cohort(cohort)
    curr_info = tables["curriculum_by_id"][curriculum_id]
    base_curr_id = curr_info.get("base_curriculum_id") or None

    sem_info = resolve_semester(cohort_num, target_sem)
    relative_term = sem_info["relative_term"]
    rec_semester_code = sem_info["recommended_semester"]
    status = sem_info["status"]

    norm_spec = normalize_specialization(specialization)

    base_result: Dict[str, Any] = {
        "cohort": cohort_str,
        "cohort_num": cohort_num,
        "academic_year_start": int(curr_info["academic_year_start"]),
        "curriculum_id": curriculum_id,
        "curriculum_name": curr_info["curriculum_name"],
        "major_name": curr_info["major_name"],
        "base_curriculum_id": base_curr_id,
        "input_semester": str(semester),
        "relative_semester": relative_term,
        "recommended_semester": rec_semester_code,
        "academic_semester": sem_info["academic_semester"],
        "status": status,
        "status_message": sem_info["message"],
        "specialization_filter": norm_spec,
        "compulsory_courses": [],
        "total_compulsory_credits": 0.0,
        "elective_guidance": {},
        "available_electives": [],
        "total_recommended_credits": 0.0,
    }

    if status in ("NOT_ENROLLED", "BEYOND_STANDARD_DURATION", "SUMMER_TERM"):
        return base_result

    # 1. Fetch Compulsory Courses for recommended_semester
    structures = tables["program_structures"]
    courses_dict = tables["courses_by_code"]
    blocks_dict = tables["blocks_by_id"]

    compulsory_list: List[Dict[str, Any]] = []
    seen_courses = set()

    # Search in program structures (direct curriculum_id first, then base if empty)
    curr_structures = [
        s for s in structures if s["curriculum_id"] == curriculum_id
    ]
    if not curr_structures and base_curr_id:
        curr_structures = [
            s for s in structures if s["curriculum_id"] == base_curr_id
        ]

    for item in curr_structures:
        if (
            item["course_type"] == "BB"
            and item["recommended_semester"] == rec_semester_code
        ):
            code = item["course_code"]
            if code in seen_courses:
                continue
            seen_courses.add(code)

            c_info = courses_dict.get(code, {})
            b_info = blocks_dict.get(item["block_id"], {})
            prereqs = get_course_prerequisites(curriculum_id, code, base_curr_id)

            prereq_display = (
                ", ".join(
                    f"{p['prerequisite_course_code']} ({p['relation_type']})"
                    for p in prereqs
                )
                if prereqs
                else "Không có"
            )

            credits_val = float(item["credits"]) if item["credits"] else 0.0
            compulsory_list.append({
                "course_code": code,
                "course_name_vi": c_info.get("course_name_vi", code),
                "course_name_en": c_info.get("course_name_en", ""),
                "credits": credits_val,
                "block_id": item["block_id"],
                "block_code": b_info.get("block_code", ""),
                "block_name_vi": b_info.get("block_name_vi", ""),
                "department": c_info.get("department", ""),
                "course_type": "BB",
                "specialization": item.get("specialization", "Toàn ngành"),
                "prerequisites": prereqs,
                "prerequisites_display": prereq_display,
            })

    # Sort compulsory courses by block code, then course code
    compulsory_list.sort(key=lambda x: (x["block_code"], x["course_code"]))
    total_compulsory_credits = sum(c["credits"] for c in compulsory_list)

    # 2. Elective Guidance
    elective_rule = ELECTIVE_ROADMAP_RULES.get(
        relative_term, {"credits": 0, "desc": "Không có môn tự chọn."}
    )
    rec_elective_credits = elective_rule.get("credits", 0)

    # 3. Available Electives Pool (if semester includes electives)
    available_electives: List[Dict[str, Any]] = []
    if rec_elective_credits > 0:
        for item in curr_structures:
            if item["course_type"] != "TC":
                continue

            # Filtering based on semester stage:
            # HK4: Group D (Management)
            if relative_term == 4 and item.get("elective_group") != "Group D":
                continue
            # HK6: Group A & Group C
            elif relative_term == 6 and item.get("elective_group") not in (
                "Group A",
                "Group C",
            ):
                continue
            # HK7: Group B & Group C
            elif relative_term == 7 and item.get("elective_group") not in (
                "Group B",
                "Group C",
            ):
                continue

            # Filter specialization if specified
            item_spec = item.get("specialization", "")
            if (
                norm_spec
                and item.get("elective_group") == "Group C"
                and item_spec
                and item_spec != "Toàn ngành"
                and norm_spec.lower() not in item_spec.lower()
            ):
                continue

            code = item["course_code"]
            c_info = courses_dict.get(code, {})
            b_info = blocks_dict.get(item["block_id"], {})
            prereqs = get_course_prerequisites(curriculum_id, code, base_curr_id)

            prereq_display = (
                ", ".join(
                    f"{p['prerequisite_course_code']} ({p['relation_type']})"
                    for p in prereqs
                )
                if prereqs
                else "Không có"
            )

            available_electives.append({
                "course_code": code,
                "course_name_vi": c_info.get("course_name_vi", code),
                "credits": float(item["credits"]) if item["credits"] else 0.0,
                "elective_group": item.get("elective_group", ""),
                "specialization": item_spec,
                "block_name_vi": b_info.get("block_name_vi", ""),
                "prerequisites_display": prereq_display,
            })

    base_result["compulsory_courses"] = compulsory_list
    base_result["total_compulsory_credits"] = total_compulsory_credits
    base_result["elective_guidance"] = {
        "recommended_elective_credits": rec_elective_credits,
        "description": elective_rule["desc"],
        "target_group": elective_rule.get("group", "None"),
    }
    base_result["available_electives"] = available_electives
    base_result["total_recommended_credits"] = (
        total_compulsory_credits + rec_elective_credits
    )

    return base_result


def get_full_curriculum_roadmap(
    cohort: Union[str, int], specialization: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieve the full 8-semester standard roadmap for a given cohort."""
    cohort_num, cohort_str, curriculum_id = normalize_cohort(cohort)
    tables = load_academic_tables()
    curr_info = tables["curriculum_by_id"][curriculum_id]

    semesters_data = []
    total_program_compulsory = 0.0
    total_program_elective = 0.0

    for sem_num in range(1, 9):
        sem_data = get_curriculum_for_cohort_semester(
            cohort=cohort_str,
            semester=f"HK{sem_num}",
            specialization=specialization,
        )
        total_program_compulsory += sem_data["total_compulsory_credits"]
        total_program_elective += sem_data["elective_guidance"][
            "recommended_elective_credits"
        ]
        semesters_data.append(sem_data)

    return {
        "cohort": cohort_str,
        "curriculum_id": curriculum_id,
        "curriculum_name": curr_info["curriculum_name"],
        "academic_year_start": int(curr_info["academic_year_start"]),
        "total_compulsory_credits": total_program_compulsory,
        "total_recommended_elective_credits": total_program_elective,
        "total_roadmap_credits": total_program_compulsory + total_program_elective,
        "semesters": semesters_data,
    }


def get_curriculum_for_cohort_term(
    cohort: Union[str, int],
    term: Union[str, int] = 1,
    specialization: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve curriculum courses for a cohort in a given term number (1, 2, ..., 8).

    Simple shorthand: get_curriculum_for_cohort_term('K24', 1).
    """
    return get_curriculum_for_cohort_semester(
        cohort=cohort, semester=term, specialization=specialization
    )


def format_curriculum_report(
    data: Dict[str, Any], show_electives_pool: bool = False
) -> str:
    """Format curriculum analysis results into a clean terminal report."""
    lines: List[str] = []
    separator = "=" * 88

    lines.append(separator)
    lines.append(
        f" CHƯƠNG TRÌNH ĐÀO TẠO {data['curriculum_id']} - {data['curriculum_name']} ".center(
            88, "="
        )
    )
    lines.append(separator)
    lines.append(
        f" Khóa tuyển sinh: {data['cohort']} (Bắt đầu: {data['academic_year_start']}) "
        f"| Học kỳ khảo sát: Học kỳ {data['relative_semester']} ({data['recommended_semester']} - Năm học: {data['academic_semester']})"
    )
    lines.append(f" Tình trạng học vụ: {data['status_message']}")

    if data["status"] in ("NOT_ENROLLED", "BEYOND_STANDARD_DURATION", "SUMMER_TERM"):
        lines.append(separator)
        return "\n".join(lines)

    lines.append("-" * 88)
    lines.append(
        f" I. DANH SÁCH MÔN HỌC BẮT BUỘC THEO LỘ TRÌNH (HỌC KỲ {data['relative_semester']} - BB):"
    )
    lines.append("-" * 88)

    courses = data["compulsory_courses"]
    if not courses:
        lines.append("  (Không có môn bắt buộc nào được xếp vào học kỳ này)")
    else:
        # Table Header
        header = f"  {'STT':<4} {'Mã môn':<8} {'Tên môn học':<32} {'TC':<4} {'Khối kiến thức':<20} {'Tiên quyết'}"
        lines.append(header)
        lines.append("  " + "-" * 84)

        for idx, c in enumerate(courses, 1):
            name = c["course_name_vi"]
            if len(name) > 30:
                name = name[:29] + "…"
            block = c["block_name_vi"]
            if len(block) > 18:
                block = block[:17] + "…"
            prereq = c["prerequisites_display"]
            row_str = f"  {idx:<4} {c['course_code']:<8} {name:<32} {int(c['credits']):<4} {block:<20} {prereq}"
            lines.append(row_str)

        lines.append("  " + "-" * 84)
        lines.append(
            f"  Tổng số môn bắt buộc: {len(courses)} môn | Tổng tín chỉ bắt buộc: {int(data['total_compulsory_credits'])} TC"
        )

    # Elective guidance
    eg = data["elective_guidance"]
    lines.append("-" * 88)
    lines.append(
        f" II. ĐỊNH HƯỚNG TỰ CHỌN (ELECTIVES) - YÊU CẦU: {eg['recommended_elective_credits']} TC:"
    )
    lines.append(f"  * {eg['description']}")

    # Available electives pool (if applicable)
    pool = data["available_electives"]
    if show_electives_pool and pool:
        lines.append(
            f"\n  DANH SÁCH CÁC HỌC PHẦN TỰ CHỌN CÓ THỂ ĐĂNG KÝ ({len(pool)} môn):"
        )
        spec_text = (
            f" (Lọc theo hướng: {data['specialization_filter']})"
            if data["specialization_filter"]
            else ""
        )
        if spec_text:
            lines.append(f"  {spec_text}")
        lines.append(
            f"  {'Mã môn':<8} {'Tên môn học':<32} {'TC':<4} {'Nhóm':<10} {'Chuyên ngành / Khối':<26}"
        )
        lines.append("  " + "-" * 84)
        for ec in pool[:15]:  # limit to top 15 for concise display
            name = ec["course_name_vi"]
            if len(name) > 30:
                name = name[:29] + "…"
            spec = ec["specialization"] or ec["block_name_vi"]
            if len(spec) > 24:
                spec = spec[:23] + "…"
            lines.append(
                f"  {ec['course_code']:<8} {name:<32} {int(ec['credits']):<4} {ec['elective_group']:<10} {spec:<26}"
            )
        if len(pool) > 15:
            lines.append(f"  ... và còn {len(pool) - 15} môn tự chọn khác.")

    lines.append("-" * 88)
    lines.append(
        f" TỔNG CỘNG TÍN CHỈ KHUYẾN NGHỊ HỌC KỲ NÀY: {int(data['total_recommended_credits'])} TÍN CHỈ"
    )
    lines.append(separator)

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# LECTURER <-> COURSE DYNAMIC MAPPING HELPERS
# -----------------------------------------------------------------------------
LECTURERS_FILE = ROOT_DIR / "generated" / "users" / "lecturer.csv"


def load_lecturers_table() -> List[Dict[str, str]]:
    """Load lecturer catalog from lecturer.csv."""
    return _read_csv_dict(LECTURERS_FILE)


def get_courses_by_lecturer(lecturer_id: str) -> Dict[str, Any]:
    """Retrieve all courses that a lecturer is qualified to teach based on department and specialization.

    Mapping Rules:
      - Lecturer's department matches course department.
      - For CSE courses:
        * General / Foundation courses ('Toàn ngành') can be taught by all CSE lecturers.
        * Specialized elective courses (Group C) match the lecturer's specialization.
      - For external departments (Math, Physics, Politics, English):
        * Lecturer can teach all courses belonging to that department.
    """
    lecturers = load_lecturers_table()
    gv = next((l for l in lecturers if l["user_id"].upper() == str(lecturer_id).strip().upper()), None)
    if not gv:
        raise ValueError(f"Không tìm thấy giảng viên với mã: '{lecturer_id}'")

    tables = load_academic_tables()
    courses = tables["courses"]
    structures = tables["program_structures"]

    # Collect all specializations associated with each course
    course_specs: Dict[str, set] = {}
    for item in structures:
        c = item["course_code"]
        s = item.get("specialization", "")
        if c not in course_specs:
            course_specs[c] = set()
        if s:
            course_specs[c].add(s)

    dept = gv["department"]
    spec = gv["specialization"]
    qualified_courses = []

    for c in courses:
        code = c["course_code"]
        c_dept = c["department"]

        # Department must match
        if c_dept != dept:
            continue

        c_spec_set = course_specs.get(code, set())

        # If not CSE, can teach all courses in that department
        if "Khoa học và Kỹ thuật Máy tính" not in dept:
            qualified_courses.append({
                "course_code": code,
                "course_name_vi": c["course_name_vi"],
                "course_name_en": c.get("course_name_en", ""),
                "credits": float(c["credits"]) if c.get("credits") else 0.0,
                "department": c_dept,
                "scope": "Toàn khoa",
            })
        else:
            # CSE logic: Foundation/Common vs Specialized
            is_common = not c_spec_set or "Toàn ngành" in c_spec_set
            is_spec_match = spec in c_spec_set or any(spec.lower() in s.lower() for s in c_spec_set)

            if is_common or is_spec_match:
                scope = "Chuyên ngành" if is_spec_match and not is_common else "Cơ sở chung"
                qualified_courses.append({
                    "course_code": code,
                    "course_name_vi": c["course_name_vi"],
                    "course_name_en": c.get("course_name_en", ""),
                    "credits": float(c["credits"]) if c.get("credits") else 0.0,
                    "department": c_dept,
                    "scope": scope,
                })

    qualified_courses.sort(key=lambda x: (x["scope"], x["course_code"]))

    return {
        "lecturer_id": gv["user_id"],
        "name": gv["name"],
        "email": gv["email"],
        "title": gv.get("title", ""),
        "department": dept,
        "specialization": spec,
        "qualified_courses": qualified_courses,
        "total_qualified_courses": len(qualified_courses),
    }


def get_lecturers_by_course(course_code: str) -> Dict[str, Any]:
    """Retrieve all lecturers qualified to teach a specific course."""
    tables = load_academic_tables()
    c_code = str(course_code).strip().upper()
    c_info = tables["courses_by_code"].get(c_code)
    if not c_info:
        raise ValueError(f"Không tìm thấy môn học với mã: '{course_code}'")

    lecturers = load_lecturers_table()
    structures = tables["program_structures"]

    # Specializations of this course
    c_specs = {
        item.get("specialization", "")
        for item in structures
        if item["course_code"] == c_code and item.get("specialization")
    }

    dept = c_info["department"]
    eligible_lecturers = []

    for gv in lecturers:
        gv_dept = gv["department"]
        gv_spec = gv["specialization"]

        if gv_dept != dept:
            continue

        if "Khoa học và Kỹ thuật Máy tính" not in dept:
            eligible_lecturers.append(gv)
        else:
            is_common = not c_specs or "Toàn ngành" in c_specs
            is_spec_match = gv_spec in c_specs or any(gv_spec.lower() in s.lower() for s in c_specs)
            if is_common or is_spec_match:
                eligible_lecturers.append(gv)

    return {
        "course_code": c_code,
        "course_name_vi": c_info["course_name_vi"],
        "course_name_en": c_info.get("course_name_en", ""),
        "credits": float(c_info["credits"]) if c_info.get("credits") else 0.0,
        "department": dept,
        "specializations": list(c_specs),
        "eligible_lecturers": eligible_lecturers,
        "total_eligible_lecturers": len(eligible_lecturers),
    }


def format_lecturer_courses_report(data: Dict[str, Any]) -> str:
    """Format lecturer qualified courses report into a clean table."""
    lines: List[str] = []
    sep = "=" * 88
    lines.append(sep)
    lines.append(f" DANH SÁCH MÔN HỌC GIẢNG VIÊN CÓ THỂ ĐẢM NHẬN ".center(88, "="))
    lines.append(sep)
    lines.append(
        f" Giảng viên: {data['name']} ({data['lecturer_id']}) | Học vị: {data['title']} | Email: {data['email']}"
    )
    lines.append(f" Khoa/Bộ môn: {data['department']}")
    lines.append(f" Hướng chuyên môn: {data['specialization']}")
    lines.append("-" * 88)

    courses = data["qualified_courses"]
    if not courses:
        lines.append("  (Chưa có môn học nào được phân công)")
    else:
        lines.append(f"  {'STT':<4} {'Mã môn':<8} {'Tên môn học':<38} {'TC':<4} {'Phân loại'}")
        lines.append("  " + "-" * 84)
        for idx, c in enumerate(courses, 1):
            name = c["course_name_vi"]
            if len(name) > 36:
                name = name[:35] + "…"
            lines.append(f"  {idx:<4} {c['course_code']:<8} {name:<38} {int(c['credits']):<4} {c['scope']}")
        lines.append("  " + "-" * 84)
        lines.append(f"  TỔNG CỘNG: {data['total_qualified_courses']} môn học có thể giảng dạy")
    lines.append(sep)
    return "\n".join(lines)


def format_course_lecturers_report(data: Dict[str, Any]) -> str:
    """Format course eligible lecturers report into a clean table."""
    lines: List[str] = []
    sep = "=" * 88
    lines.append(sep)
    lines.append(f" DANH SÁCH GIẢNG VIÊN ĐỦ ĐIỀU KIỆN GIẢNG DẠY MÔN HỌC ".center(88, "="))
    lines.append(sep)
    lines.append(
        f" Môn học: {data['course_code']} - {data['course_name_vi']} ({int(data['credits'])} TC)"
    )
    lines.append(f" Khoa / Bộ môn phụ trách: {data['department']}")
    if data["specializations"]:
        lines.append(f" Định hướng chuyên ngành: {', '.join(data['specializations'])}")
    lines.append("-" * 88)

    gvs = data["eligible_lecturers"]
    if not gvs:
        lines.append("  (Chưa tìm thấy giảng viên đủ điều kiện)")
    else:
        lines.append(f"  {'STT':<4} {'Mã GV':<9} {'Họ và tên':<26} {'Học vị':<14} {'Chuyên môn'}")
        lines.append("  " + "-" * 84)
        for idx, g in enumerate(gvs, 1):
            lines.append(
                f"  {idx:<4} {g['user_id']:<9} {g['name']:<26} {g.get('title',''):<14} {g.get('specialization','')}"
            )
        lines.append("  " + "-" * 84)
        lines.append(f"  TỔNG CỘNG: {data['total_eligible_lecturers']} giảng viên đủ điều kiện giảng dạy môn này")
    lines.append(sep)
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# STUDENT ACADEMIC HISTORY LOOKUP HELPERS
# -----------------------------------------------------------------------------
def _semester_sort_key(sem_code: str) -> int:
    """Sort key for semesters (e.g. HK201 -> 201, HK202 -> 202)."""
    match = re.match(r"HK(\d{2})([123])", sem_code.upper())
    if match:
        return int(match.group(1)) * 10 + int(match.group(2))
    return 0


def get_student_academic_history(query: str) -> Dict[str, Any]:
    """Retrieve full semester-by-semester academic history for a given student ID, email, or name.

    Returns a structured dictionary with student metadata, profile attributes,
    detailed semester-by-semester course records, grades, and cumulative GPA/credits.
    """
    query_str = str(query).strip()
    if not query_str:
        return {"found": False, "message": "Vui lòng cung cấp MSSV, Email hoặc Họ tên sinh viên."}

    if not STUDENTS_FILE.exists():
        return {"found": False, "message": f"Không tìm thấy file sinh viên: {STUDENTS_FILE}"}

    students = _read_csv_dict(STUDENTS_FILE)
    matched_student = None

    # Exact match on user_id (MSSV) or email
    for st in students:
        uid = st.get("user_id", "").strip()
        email = st.get("email", "").strip()
        if query_str.lower() in [uid.lower(), email.lower()]:
            matched_student = st
            break

    # Exact match on full name
    if not matched_student:
        for st in students:
            if query_str.lower() == st.get("name", "").strip().lower():
                matched_student = st
                break

    # Substring match on name
    if not matched_student:
        for st in students:
            if query_str.lower() in st.get("name", "").strip().lower():
                matched_student = st
                break

    if not matched_student:
        return {
            "found": False,
            "message": f"Không tìm thấy sinh viên nào khớp với từ khóa '{query_str}'. Vui lòng kiểm tra lại MSSV.",
        }

    student_id = matched_student["user_id"]
    student_name = matched_student["name"]
    student_email = matched_student["email"]
    program = matched_student.get("program", "standard")
    cohort_code = f"K{student_id[:2]}" if len(student_id) >= 2 else "K??"

    # Load student profile if exists
    profile_data: Dict[str, Any] = {}
    if STUDENT_PROFILES_FILE.exists():
        for p in _read_csv_dict(STUDENT_PROFILES_FILE):
            if p.get("student_id") == student_id:
                profile_data = p
                break

    # Load master tables
    academic_tables = load_academic_tables()
    courses_by_code = academic_tables["courses_by_code"]

    semesters_by_code: Dict[str, Dict[str, str]] = {}
    if SEMESTER_FILE.exists():
        for s in _read_csv_dict(SEMESTER_FILE):
            semesters_by_code[s["semester_code"]] = s

    # Parse CTXH days by semester
    ctxh_list = []
    if profile_data.get("ctxh_days_by_semester"):
        try:
            raw_ctxh = profile_data["ctxh_days_by_semester"]
            ctxh_list = json.loads(raw_ctxh) if isinstance(raw_ctxh, str) else raw_ctxh
        except Exception:
            ctxh_list = []
    ctxh_by_sem = {
        item.get("semester"): item.get("cumulative_days")
        for item in ctxh_list
        if isinstance(item, dict) and "semester" in item
    }

    # Discover and sort all enrollment files
    enrollment_files = (
        sorted(
            ENROLLMENTS_DIR.glob("enrollment_hk*.csv"),
            key=lambda p: _semester_sort_key(p.stem.replace("enrollment_", "")),
        )
        if ENROLLMENTS_DIR.exists()
        else []
    )

    semester_records = []
    total_credits_enrolled = 0
    total_credits_passed = 0
    passed_count = 0
    failed_count = 0
    exempted_count = 0
    latest_final_gpa_4 = None
    weighted_score_10_sum = 0.0
    weighted_score_10_credits = 0

    for enr_file in enrollment_files:
        sem_code = enr_file.stem.replace("enrollment_", "").upper()
        enr_rows = _read_csv_dict(enr_file)
        matching_enrs = [r for r in enr_rows if r.get("student_id") == student_id]
        if not matching_enrs:
            continue

        # Load corresponding class catalog
        class_file = CLASSES_DIR / f"class_{sem_code.lower()}.csv"
        classes_by_id: Dict[str, Dict[str, str]] = {}
        if class_file.exists():
            for c in _read_csv_dict(class_file):
                classes_by_id[c["class_id"]] = c

        courses_detail = []
        sem_credits_enrolled = 0
        sem_credits_passed = 0
        sem_gpa_4 = None
        sem_final_gpa_4 = None

        for enr in matching_enrs:
            cid = enr.get("class_id", "")
            course_code = enr.get("course_id", "")
            cls_info = classes_by_id.get(cid, {})

            course_info = courses_by_code.get(course_code, {})
            course_name = (
                course_info.get("course_name_vi")
                or cls_info.get("course_name")
                or course_code
            )
            try:
                credits_val = int(float(course_info.get("credits", 0) or 0))
            except Exception:
                credits_val = 0

            status = enr.get("status", "Pass")
            passed_bool = str(enr.get("passed", "True")).strip().lower() == "true"

            final_score_str = enr.get("final_score", "")
            try:
                final_score_val = float(final_score_str) if final_score_str else None
            except Exception:
                final_score_val = None

            gpa_4_str = enr.get("gpa_4", "")
            try:
                gpa_4_val = float(gpa_4_str) if gpa_4_str else None
            except Exception:
                gpa_4_val = None

            letter_grade = enr.get("letter_grade", "")
            if status == "Exempted" and not letter_grade:
                letter_grade = "Miễn"

            def _parse_float(v: str) -> Optional[float]:
                try:
                    return float(v) if v != "" else None
                except Exception:
                    return None

            quiz_val = _parse_float(enr.get("quiz", ""))
            lab_val = _parse_float(enr.get("lab", ""))
            btl_val = _parse_float(enr.get("btl", ""))
            gk_val = _parse_float(enr.get("giua_ky", ""))
            ck_val = _parse_float(enr.get("cuoi_ky", ""))

            # Semester GPAs
            if enr.get("semester_gpa_4"):
                try:
                    sem_gpa_4 = float(enr["semester_gpa_4"])
                except Exception:
                    pass
            if enr.get("final_gpa_4"):
                try:
                    sem_final_gpa_4 = float(enr["final_gpa_4"])
                except Exception:
                    pass

            # Credits tracking
            sem_credits_enrolled += credits_val
            if passed_bool:
                sem_credits_passed += credits_val

            if status == "Exempted":
                exempted_count += 1
            elif passed_bool:
                passed_count += 1
            else:
                failed_count += 1

            if (
                final_score_val is not None
                and final_score_val <= 10.0
                and credits_val > 0
            ):
                weighted_score_10_sum += final_score_val * credits_val
                weighted_score_10_credits += credits_val

            courses_detail.append({
                "course_code": course_code,
                "course_name": course_name,
                "credits": credits_val,
                "class_id": cid or None,
                "class_group": cls_info.get("class_group") or ("Miễn" if status == "Exempted" else "-"),
                "lecturer_name": cls_info.get("lecturer_name") or ("-" if status == "Exempted" else "Chưa phân công"),
                "quiz": quiz_val,
                "lab": lab_val,
                "btl": btl_val,
                "giua_ky": gk_val,
                "cuoi_ky": ck_val,
                "final_score": final_score_val,
                "gpa_4": gpa_4_val,
                "letter_grade": letter_grade,
                "passed": passed_bool,
                "status": status,
            })

        total_credits_enrolled += sem_credits_enrolled
        total_credits_passed += sem_credits_passed
        if sem_final_gpa_4 is not None:
            latest_final_gpa_4 = sem_final_gpa_4

        sem_meta = semesters_by_code.get(sem_code, {})
        semester_records.append({
            "semester_code": sem_code,
            "academic_year": sem_meta.get("academic_year", "-"),
            "semester_gpa_4": sem_gpa_4,
            "cumulative_gpa_4": sem_final_gpa_4,
            "credits_enrolled": sem_credits_enrolled,
            "credits_passed": sem_credits_passed,
            "ctxh_cumulative_days": ctxh_by_sem.get(sem_code),
            "courses": courses_detail,
        })

    cumulative_gpa_10 = (
        round(weighted_score_10_sum / weighted_score_10_credits, 2)
        if weighted_score_10_credits > 0
        else None
    )

    # Academic standing classification
    if latest_final_gpa_4 is not None:
        if latest_final_gpa_4 >= 3.6:
            classification = "Xuất sắc"
        elif latest_final_gpa_4 >= 3.2:
            classification = "Giỏi"
        elif latest_final_gpa_4 >= 2.5:
            classification = "Khá"
        elif latest_final_gpa_4 >= 2.0:
            classification = "Trung bình"
        else:
            classification = "Yếu / Cảnh báo học vụ"
    else:
        classification = "Chưa xếp loại"

    program_names = {
        "standard": "Đại trà (Tiêu chuẩn)",
        "high-quality": "Chất lượng cao (CLC)",
        "advanced": "Chương trình Tiên tiến",
    }

    english_status_desc = (
        "Đạt / Miễn 4 học phần"
        if (
            profile_data.get("english_pass") == "True"
            or program in ["high-quality", "advanced"]
        )
        else "Chưa đạt chuẩn đầu vào"
    )

    return {
        "found": True,
        "student_id": student_id,
        "name": student_name,
        "email": student_email,
        "cohort": cohort_code,
        "program": program,
        "program_display": program_names.get(program, program),
        "profile": {
            "academic_level": profile_data.get("academic_level"),
            "base_score": profile_data.get("base_score"),
            "discipline": profile_data.get("discipline"),
            "motivation": profile_data.get("motivation"),
            "stress": profile_data.get("stress"),
            "english_pass": profile_data.get("english_pass") == "True" or program in ["high-quality", "advanced"],
            "english_status": english_status_desc,
            "early_graduation_candidate": profile_data.get("early_graduation_candidate") == "True",
        },
        "summary": {
            "total_semesters_studied": len(semester_records),
            "total_credits_enrolled": total_credits_enrolled,
            "total_credits_passed": total_credits_passed,
            "cumulative_gpa_4": latest_final_gpa_4,
            "cumulative_gpa_10": cumulative_gpa_10,
            "passed_courses_count": passed_count,
            "failed_courses_count": failed_count,
            "exempted_courses_count": exempted_count,
            "academic_classification": classification,
            "latest_ctxh_days": ctxh_list[-1]["cumulative_days"] if ctxh_list else None,
        },
        "semesters": semester_records,
    }


def format_student_history_report(data: Dict[str, Any]) -> str:
    """Format full student academic history report into a clean, human-readable view."""
    if not data.get("found"):
        return f"\n[!] THÔNG BÁO: {data.get('message', 'Không tìm thấy dữ liệu sinh viên.')}\n"

    lines: List[str] = []
    sep = "=" * 115
    lines.append("\n" + sep)
    lines.append(f" HỒ SƠ & LỊCH SỬ HỌC TẬP TỪNG KỲ CỦA SINH VIÊN ".center(115, "="))
    lines.append(sep)

    # 1. Student Metadata & Psychological Profile
    prof = data["profile"]
    summ = data["summary"]
    lines.append(f"  Họ và tên: {data['name']:<28} MSSV: {data['student_id']:<14} Khóa: {data['cohort']}")
    lines.append(f"  Email: {data['email']:<32} Hệ đào tạo: {data['program_display']}")

    prof_details = []
    if prof.get("base_score"):
        prof_details.append(f"Điểm nền (Base score): {prof['base_score']}/10")
    if prof.get("academic_level"):
        prof_details.append(f"Học lực ẩn: Mức {prof['academic_level']}/5")
    if prof.get("english_status"):
        prof_details.append(f"Tiếng Anh: {prof['english_status']}")
    if summ.get("latest_ctxh_days") is not None:
        prof_details.append(f"CTXH tích lũy: {summ['latest_ctxh_days']} ngày")

    if prof_details:
        lines.append(f"  Năng lực & Điều kiện: {' | '.join(prof_details)}")

    gpa_4_display = f"{summ['cumulative_gpa_4']:.2f}/4.0" if summ['cumulative_gpa_4'] is not None else "N/A"
    gpa_10_display = f"{summ['cumulative_gpa_10']:.2f}/10" if summ['cumulative_gpa_10'] is not None else "N/A"

    lines.append(
        f"  Tổng kết toàn khóa: Đã học {summ['total_semesters_studied']} kỳ | "
        f"Tích lũy: {summ['total_credits_passed']}/{summ['total_credits_enrolled']} TC | "
        f"GPA tích lũy: {gpa_4_display} ({gpa_10_display}) | "
        f"Xếp loại: {summ['academic_classification']}"
    )
    lines.append(sep)

    # 2. Semester-by-Semester breakdown
    semesters = data["semesters"]
    if not semesters:
        lines.append("\n  (Sinh viên chưa có lịch sử đăng ký học phần trong các học kỳ đã mô phỏng)\n")
        lines.append(sep)
        return "\n".join(lines)

    for sem in semesters:
        sem_gpa = f"{sem['semester_gpa_4']:.2f}" if sem['semester_gpa_4'] is not None else "N/A"
        cpa = f"{sem['cumulative_gpa_4']:.2f}" if sem['cumulative_gpa_4'] is not None else "N/A"
        ctxh = f" | CTXH tích lũy: {sem['ctxh_cumulative_days']} ngày" if sem['ctxh_cumulative_days'] is not None else ""

        lines.append(f"\n▶ HỌC KỲ: {sem['semester_code']} (Năm học {sem['academic_year']})")
        lines.append(
            f"  GPA học kỳ: {sem_gpa}/4.0 | GPA tích lũy: {cpa}/4.0 | "
            f"Tín chỉ: Đăng ký {sem['credits_enrolled']} TC / Tích lũy {sem['credits_passed']} TC{ctxh}"
        )
        lines.append("-" * 115)
        lines.append(
            f"  {'STT':<4} {'Mã môn':<8} {'Tên môn học':<26} {'TC':<3} {'Lớp':<7} "
            f"{'Giảng viên':<20} {'Điểm TP':<22} {'TK(10)':<7} {'Hệ 4':<5} {'Chữ':<5} {'Trạng thái'}"
        )
        lines.append("  " + "-" * 111)

        for c_idx, c in enumerate(sem["courses"], 1):
            name = c["course_name"]
            if len(name) > 25:
                name = name[:24] + "…"

            gv = c["lecturer_name"]
            if len(gv) > 19:
                gv = gv[:18] + "…"

            # Build component scores string
            if c["status"] == "Exempted":
                tp_str = "[Miễn chuẩn AV]"
                tk_str = "12.0"
                h4_str = "-"
                ch_str = "Miễn"
                st_str = "Exempted"
            else:
                parts = []
                if c["quiz"] is not None: parts.append(f"Qz:{c['quiz']:.1f}")
                if c["lab"] is not None: parts.append(f"Lab:{c['lab']:.1f}")
                if c["btl"] is not None: parts.append(f"BTL:{c['btl']:.1f}")
                if c["giua_ky"] is not None: parts.append(f"GK:{c['giua_ky']:.1f}")
                if c["cuoi_ky"] is not None: parts.append(f"CK:{c['cuoi_ky']:.1f}")
                tp_str = " ".join(parts) if parts else "-"
                tk_str = f"{c['final_score']:.1f}" if c['final_score'] is not None else "-"
                h4_str = f"{c['gpa_4']:.1f}" if c['gpa_4'] is not None else "-"
                ch_str = c["letter_grade"] or "-"
                st_str = c["status"]

            lines.append(
                f"  {c_idx:<4} {c['course_code']:<8} {name:<26} {c['credits']:<3} {c['class_group']:<7} "
                f"{gv:<20} {tp_str:<22} {tk_str:<7} {h4_str:<5} {ch_str:<5} {st_str}"
            )
        lines.append("  " + "-" * 111)

    lines.append(sep)
    lines.append(" [*] Ghi chú: Điểm 12.0 là điểm quy ước dành cho các học phần Miễn Anh văn (không tính vào GPA học kỳ & tích lũy).")
    lines.append(sep + "\n")
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# COHORT GRADUATION ANALYSIS HELPERS (EARLY 3.5Y, ON-TIME 4.0Y, LATE 9-12 TERMS)
# -----------------------------------------------------------------------------

def get_cohort_graduation_analysis(cohort: Union[str, int]) -> Dict[str, Any]:
    """Phân tích thống kê chi tiết tỷ lệ tốt nghiệp sớm, đúng hạn và trễ hạn theo từng kỳ (kỳ 9 - 12) của một khóa.

    Theo quy chế đào tạo BKU CSE:
      - Tốt nghiệp sớm: Kỳ 7 (3.5 năm) - hoàn thành KLTN (CO4337) và môn kết thúc SP1007 ở HK7.
      - Tốt nghiệp đúng hạn: Kỳ 8 (4.0 năm) - hoàn thành chương trình ở HK8.
      - Tốt nghiệp trễ hạn: Kỳ 9 (4.5 năm), Kỳ 10 (5.0 năm), Kỳ 11 (5.5 năm), Kỳ 12 (6.0 năm - tối đa).
      - Quá hạn: Sau kỳ 12 (> 6.0 năm).
      - Chưa tốt nghiệp / Nợ môn: Chưa hoàn thành đủ điều kiện tốt nghiệp tính đến học kỳ mô phỏng gần nhất.
    """
    cohort_num, cohort_str, curriculum_id = normalize_cohort(cohort)
    tables = load_academic_tables()
    curr_info = tables["curriculum_by_id"][curriculum_id]

    # 1. Load students of this cohort
    all_students = _read_csv_dict(STUDENTS_FILE) if STUDENTS_FILE.exists() else []
    cohort_students = [
        s for s in all_students
        if s.get("user_id", "").startswith(f"{cohort_num:02d}")
        or s.get("cohort", "").upper() == cohort_str
    ]
    if not cohort_students:
        raise ValueError(f"Không tìm thấy sinh viên nào thuộc khóa {cohort_str}")

    total_cohort_students = len(cohort_students)
    student_dict = {s["user_id"]: s for s in cohort_students}

    # Load student profiles for early_graduation_candidate and base_score
    profiles_dict = {}
    if STUDENT_PROFILES_FILE.exists():
        for p in _read_csv_dict(STUDENT_PROFILES_FILE):
            if p.get("student_id") in student_dict:
                profiles_dict[p["student_id"]] = p

    # 2. Terms mapping (1 to 14)
    # Term 1: HK{YY}1, Term 2: HK{YY}2, Term 3: HK{YY+1}1, ...
    term_semester_map: Dict[int, str] = {}
    semester_term_map: Dict[str, int] = {}
    for t in range(1, 15):
        offset = (t - 1) // 2
        term_idx = 1 if (t % 2 != 0) else 2
        sem_code = f"HK{cohort_num + offset}{term_idx}"
        term_semester_map[t] = sem_code
        semester_term_map[sem_code] = t

    # 3. Detect simulated semesters and load enrollments
    available_semesters: Dict[str, Path] = {}
    for sem_code in term_semester_map.values():
        enr_path = ENROLLMENTS_DIR / f"enrollment_{sem_code.lower()}.csv"
        if enr_path.exists():
            available_semesters[sem_code] = enr_path

    simulated_terms = [
        t for t, sem_code in term_semester_map.items()
        if sem_code in available_semesters
    ]
    latest_simulated_term = max(simulated_terms) if simulated_terms else 0
    latest_simulated_semester = (
        term_semester_map.get(latest_simulated_term) if latest_simulated_term > 0 else "Chưa có"
    )

    # Track earliest passing term for CO4337 and SP1007
    co_pass_term: Dict[str, int] = {}
    sp_pass_term: Dict[str, int] = {}
    co_pass_detail: Dict[str, Dict[str, Any]] = {}

    for t in sorted(simulated_terms):
        sem_code = term_semester_map[t]
        enr_file = available_semesters[sem_code]
        rows = _read_csv_dict(enr_file)
        for r in rows:
            sid = r.get("student_id")
            if sid not in student_dict:
                continue
            is_passed = str(r.get("passed", "True")).strip().lower() == "true"
            if not is_passed:
                continue

            cid = r.get("course_id", "")
            if cid == "CO4337" and sid not in co_pass_term:
                co_pass_term[sid] = t
                co_pass_detail[sid] = {
                    "final_score": float(r.get("final_score", 0.0) or 0.0),
                    "gpa_4": float(r.get("gpa_4", 0.0) or 0.0),
                    "letter_grade": r.get("letter_grade", ""),
                    "term": t,
                    "semester_code": sem_code,
                }
            elif cid == "SP1007" and sid not in sp_pass_term:
                sp_pass_term[sid] = t

    # English proficiency and CTXH days progression map (from student_profiles.csv)
    eng_prog_map: Dict[str, Dict[str, Any]] = {}
    ctxh_days_map: Dict[str, Dict[str, int]] = {}
    for sid, p in profiles_dict.items():
        is_exempt = str(p.get("english_pass", "")).strip().lower() == "true"
        eng_raw = p.get("english_eligibility_by_semester", "[]")
        try:
            eng_list = json.loads(eng_raw) if isinstance(eng_raw, str) else eng_raw
        except Exception:
            eng_list = []
        eng_by_sem = {
            item["semester"]: bool(item.get("eligible", False))
            for item in eng_list
            if isinstance(item, dict) and "semester" in item
        }

        ctxh_raw = p.get("ctxh_days_by_semester", "[]")
        try:
            ctxh_list = json.loads(ctxh_raw) if isinstance(ctxh_raw, str) else ctxh_raw
        except Exception:
            ctxh_list = []
        ctxh_by_sem = {
            item["semester"]: int(item.get("cumulative_days", 0))
            for item in ctxh_list
            if isinstance(item, dict) and "semester" in item
        }

        eng_prog_map[sid] = {"is_exempt": is_exempt, "by_sem": eng_by_sem}
        ctxh_days_map[sid] = ctxh_by_sem

    # Read graduation configuration thresholds
    min_ctxh_grad = 15
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, mode="r", encoding="utf-8") as f:
                cfg_json = json.load(f)
                min_ctxh_grad = int(
                    cfg_json.get("student_progress", {})
                    .get("ctxh", {})
                    .get("minimum_for_graduation", 15)
                )
        except Exception:
            min_ctxh_grad = 15

    # 4. Student Graduation Term (Phương án 1: Kích hoạt chuẩn Tiếng Anh & CTXH từ config)
    # Student graduates at the earliest term T where:
    #   a) Both CO4337 and SP1007 are passed by term T
    #   b) English requirement is satisfied at semester T (english_pass or english_eligibility_by_semester)
    #   c) CTXH requirement is satisfied at semester T (cumulative_days >= min_ctxh_grad per BKU regulation)
    grad_terms: Dict[str, int] = {}
    for sid in student_dict:
        for t in sorted(simulated_terms):
            sem = term_semester_map[t]
            academic_ok = (
                sid in co_pass_term
                and sid in sp_pass_term
                and max(co_pass_term[sid], sp_pass_term[sid]) <= t
            )
            if not academic_ok:
                continue

            em = eng_prog_map.get(sid, {})
            eng_ok = em.get("is_exempt", False) or em.get("by_sem", {}).get(sem, False)
            if not eng_ok:
                continue

            ctxh_ok = ctxh_days_map.get(sid, {}).get(sem, 0) >= min_ctxh_grad
            if not ctxh_ok:
                continue

            grad_terms[sid] = t
            break

    # 5. Categorize by Term
    # Early: term <= 7
    # On-time: term == 8
    # Late: term 9, 10, 11, 12
    # Beyond: term > 12
    early_students = [sid for sid, t in grad_terms.items() if t <= 7]
    ontime_students = [sid for sid, t in grad_terms.items() if t == 8]
    late_9_students = [sid for sid, t in grad_terms.items() if t == 9]
    late_10_students = [sid for sid, t in grad_terms.items() if t == 10]
    late_11_students = [sid for sid, t in grad_terms.items() if t == 11]
    late_12_students = [sid for sid, t in grad_terms.items() if t == 12]
    beyond_students = [sid for sid, t in grad_terms.items() if t > 12]
    pending_students = [sid for sid in student_dict if sid not in grad_terms]

    # Program breakdown
    program_labels = {
        "standard": "Đại trà (Tiêu chuẩn)",
        "high-quality": "Chất lượng cao (CLC)",
        "advanced": "Chương trình Tiên tiến",
    }
    by_program: Dict[str, Dict[str, Any]] = {}
    for prog_key, prog_name in program_labels.items():
        prog_sids = [sid for sid, s in student_dict.items() if s.get("program") == prog_key]
        n_prog = len(prog_sids)
        if n_prog == 0:
            continue

        p_early = [s for s in prog_sids if s in early_students]
        p_ontime = [s for s in prog_sids if s in ontime_students]
        p_late_9 = [s for s in prog_sids if s in late_9_students]
        p_late_10 = [s for s in prog_sids if s in late_10_students]
        p_late_11 = [s for s in prog_sids if s in late_11_students]
        p_late_12 = [s for s in prog_sids if s in late_12_students]
        p_beyond = [s for s in prog_sids if s in beyond_students]
        p_pending = [s for s in prog_sids if s in pending_students]
        p_total_grad = len(p_early) + len(p_ontime) + len(p_late_9) + len(p_late_10) + len(p_late_11) + len(p_late_12) + len(p_beyond)

        by_program[prog_key] = {
            "program_key": prog_key,
            "program_name": prog_name,
            "total_students": n_prog,
            "graduated_count": p_total_grad,
            "graduated_rate": round(p_total_grad / n_prog * 100, 2),
            "early_count": len(p_early),
            "early_percentage": round(len(p_early) / n_prog * 100, 2),
            "ontime_count": len(p_ontime),
            "ontime_percentage": round(len(p_ontime) / n_prog * 100, 2),
            "late_9_count": len(p_late_9),
            "late_9_percentage": round(len(p_late_9) / n_prog * 100, 2),
            "late_10_count": len(p_late_10),
            "late_10_percentage": round(len(p_late_10) / n_prog * 100, 2),
            "late_11_count": len(p_late_11),
            "late_11_percentage": round(len(p_late_11) / n_prog * 100, 2),
            "late_12_count": len(p_late_12),
            "late_12_percentage": round(len(p_late_12) / n_prog * 100, 2),
            "total_late_count": len(p_late_9) + len(p_late_10) + len(p_late_11) + len(p_late_12),
            "total_late_percentage": round((len(p_late_9) + len(p_late_10) + len(p_late_11) + len(p_late_12)) / n_prog * 100, 2),
            "beyond_count": len(p_beyond),
            "beyond_percentage": round(len(p_beyond) / n_prog * 100, 2),
            "pending_count": len(p_pending),
            "pending_percentage": round(len(p_pending) / n_prog * 100, 2),
        }

    # Build early graduates detailed roster
    early_roster = []
    for sid in sorted(early_students):
        s_info = student_dict[sid]
        p_info = profiles_dict.get(sid, {})
        co_det = co_pass_detail.get(sid, {})
        early_roster.append({
            "student_id": sid,
            "name": s_info["name"],
            "program": s_info.get("program", "standard"),
            "program_name": program_labels.get(s_info.get("program", "standard"), s_info.get("program", "")),
            "base_score": float(p_info.get("base_score", 0.0) or 0.0),
            "kltn_score": co_det.get("final_score"),
            "kltn_grade": co_det.get("letter_grade"),
            "kltn_term": co_det.get("term"),
            "kltn_semester": co_det.get("semester_code"),
        })

    def _term_meta(t: int, name: str, sids: List[str]) -> Dict[str, Any]:
        sem = term_semester_map.get(t, "HK??")
        is_sim = t in simulated_terms
        cnt = len(sids)
        pct = round(cnt / total_cohort_students * 100, 2) if total_cohort_students > 0 else 0.0
        return {
            "term": t,
            "years": round(t * 0.5, 1),
            "semester_code": sem,
            "name": name,
            "count": cnt,
            "percentage": pct,
            "status": "SIMULATED" if is_sim else "NOT_SIMULATED",
            "status_label": "Đã mô phỏng" if is_sim else "Chưa mô phỏng",
            "student_ids": sids,
        }

    total_graduated = len(grad_terms)
    total_grad_rate = round(total_graduated / total_cohort_students * 100, 2)

    categories = {
        "early": _term_meta(7, "Tốt nghiệp sớm (Kỳ 7 - 3.5 năm)", early_students),
        "on_time": _term_meta(8, "Tốt nghiệp đúng hạn (Kỳ 8 - 4.0 năm)", ontime_students),
        "late_terms": {
            9: _term_meta(9, "Tốt nghiệp trễ hạn Kỳ 9 (4.5 năm)", late_9_students),
            10: _term_meta(10, "Tốt nghiệp trễ hạn Kỳ 10 (5.0 năm)", late_10_students),
            11: _term_meta(11, "Tốt nghiệp trễ hạn Kỳ 11 (5.5 năm)", late_11_students),
            12: _term_meta(12, "Tốt nghiệp trễ hạn Kỳ 12 (6.0 năm - Tối đa)", late_12_students),
        },
        "beyond_max": {
            "name": "Quá hạn đào tạo tối đa (> 6.0 năm / > 12 học kỳ)",
            "years": "> 6.0",
            "count": len(beyond_students),
            "percentage": round(len(beyond_students) / total_cohort_students * 100, 2),
            "status": "SIMULATED" if any(t > 12 for t in simulated_terms) else "NOT_SIMULATED",
            "status_label": "Đã mô phỏng" if any(t > 12 for t in simulated_terms) else "Chưa mô phỏng",
            "student_ids": beyond_students,
        },
        "pending": {
            "name": "Chưa tốt nghiệp / Đang nợ chuẩn đầu ra",
            "count": len(pending_students),
            "percentage": round(len(pending_students) / total_cohort_students * 100, 2),
            "description": f"Chưa hoàn thành KLTN/môn bắt buộc hoặc chưa đạt chuẩn Tiếng Anh / 15 ngày CTXH tính đến {latest_simulated_semester}",
            "student_ids": pending_students,
        },
    }

    return {
        "cohort": cohort_str,
        "cohort_num": cohort_num,
        "curriculum_id": curriculum_id,
        "curriculum_name": curr_info.get("curriculum_name", "Khoa học Máy tính"),
        "total_students": total_cohort_students,
        "total_graduated": total_graduated,
        "graduation_rate": total_grad_rate,
        "total_pending": len(pending_students),
        "pending_rate": round(len(pending_students) / total_cohort_students * 100, 2),
        "latest_simulated_term": latest_simulated_term,
        "latest_simulated_semester": latest_simulated_semester,
        "categories": categories,
        "by_program": by_program,
        "early_graduates_roster": early_roster,
    }


def format_cohort_graduation_report(data: Dict[str, Any]) -> str:
    """Format cohort graduation rate analysis into a clean, comprehensive terminal report."""
    lines: List[str] = []
    sep = "=" * 96

    lines.append(sep)
    lines.append(
        f" BÁO CÁO THỐNG KÊ TIẾN ĐỘ & TỶ LỆ TỐT NGHIỆP - KHÓA {data['cohort']} ({data['curriculum_id']}) ".center(
            96, "="
        )
    )
    lines.append(sep)
    lines.append(
        f" Khóa tuyển sinh: {data['cohort']} | Ngành: {data['curriculum_name']} | Tổng số sinh viên: {data['total_students']:,} SV"
    )
    lines.append(
        f" Dữ liệu mô phỏng hiện tại: Đến Học kỳ {data['latest_simulated_term']} ({data['latest_simulated_semester']})"
    )
    lines.append(
        f" Đã tốt nghiệp: {data['total_graduated']:,} SV ({data['graduation_rate']:.2f}%) | "
        f"Chưa tốt nghiệp / Đang nợ chuẩn đầu ra: {data['total_pending']:,} SV ({data['pending_rate']:.2f}%)"
    )

    cats = data["categories"]
    early = cats["early"]
    ontime = cats["on_time"]
    lates = cats["late_terms"]
    beyond = cats["beyond_max"]
    pending = cats["pending"]

    lines.append("-" * 96)
    lines.append(" I. BẢNG PHÂN BỐ TỶ LỆ TỐT NGHIỆP THEO TIẾN ĐỘ HỌC VỤ:")
    lines.append("-" * 96)
    header = f"  {'Mốc đào tạo / Tiến độ tốt nghiệp':<38} {'Học kỳ':<8} {'Thời gian':<11} {'Số lượng':<10} {'Tỷ lệ':<9} {'Tình trạng dữ liệu'}"
    lines.append(header)
    lines.append("  " + "-" * 92)

    # Early
    early_yr = f"{early['years']} năm"
    early_cnt = f"{early['count']} SV"
    early_pct = f"{early['percentage']:.2f}%"
    lines.append(
        f"  ★ {early['name']:<36} {early['semester_code']:<8} {early_yr:<11} "
        f"{early_cnt:<10} {early_pct:<9} {early['status_label']}"
    )

    # On-time
    ontime_yr = f"{ontime['years']} năm"
    ontime_cnt = f"{ontime['count']} SV"
    ontime_pct = f"{ontime['percentage']:.2f}%"
    lines.append(
        f"  ● {ontime['name']:<36} {ontime['semester_code']:<8} {ontime_yr:<11} "
        f"{ontime_cnt:<10} {ontime_pct:<9} {ontime['status_label']}"
    )

    # Late terms (9, 10, 11, 12)
    for t in [9, 10, 11, 12]:
        lt = lates[t]
        lt_yr = f"{lt['years']} năm"
        lt_cnt = f"{lt['count']} SV"
        lt_pct = f"{lt['percentage']:.2f}%"
        lines.append(
            f"  ▲ {lt['name']:<36} {lt['semester_code']:<8} {lt_yr:<11} "
            f"{lt_cnt:<10} {lt_pct:<9} {lt['status_label']}"
        )

    # Beyond
    beyond_cnt = f"{beyond['count']} SV"
    beyond_pct = f"{beyond['percentage']:.2f}%"
    lines.append(
        f"  ✕ {beyond['name']:<36} {'-':<8} {'> 6.0 năm':<11} "
        f"{beyond_cnt:<10} {beyond_pct:<9} {beyond['status_label']}"
    )

    lines.append("  " + "-" * 92)
    pend_cnt = f"{pending['count']} SV"
    pend_pct = f"{pending['percentage']:.2f}%"
    lines.append(
        f"  ⚠ {pending['name']} (tính đến {data['latest_simulated_semester']}): {'':<14} "
        f"{pend_cnt:<10} {pend_pct:<9} {pending['description']}"
    )

    # Program breakdown
    lines.append("-" * 96)
    lines.append(" II. THỐNG KÊ CHI TIẾT THEO HỆ ĐÀO TẠO:")
    lines.append("-" * 96)
    prog_header = f"  {'Hệ đào tạo':<24} {'Tổng SV':<9} {'Tốt nghiệp sớm':<17} {'Đúng hạn (K8)':<17} {'Trễ hạn (K9-12)':<17} {'Nợ chuẩn / Chưa TN'}"
    lines.append(prog_header)
    lines.append("  " + "-" * 92)

    for p_key, p in data["by_program"].items():
        p_tot_str = f"{p['total_students']} SV"
        early_str = f"{p['early_count']} SV ({p['early_percentage']:.2f}%)"
        ontime_str = f"{p['ontime_count']} SV ({p['ontime_percentage']:.2f}%)"
        late_str = f"{p['total_late_count']} SV ({p['total_late_percentage']:.2f}%)"
        pending_str = f"{p['pending_count']} SV ({p['pending_percentage']:.2f}%)"

        lines.append(
            f"  {p['program_name']:<24} {p_tot_str:<9} {early_str:<17} "
            f"{ontime_str:<17} {late_str:<17} {pending_str}"
        )

    # Early graduates roster (if any)
    roster = data.get("early_graduates_roster", [])
    if roster:
        lines.append("-" * 96)
        lines.append(f" III. DANH SÁCH SINH VIÊN TỐT NGHIỆP SỚM (KỲ 7 / 3.5 NĂM - TỔNG CỘNG {len(roster)} SV):")
        lines.append("-" * 96)
        r_header = f"  {'STT':<4} {'MSSV':<9} {'Họ và tên':<24} {'Hệ đào tạo':<22} {'Base GPA':<10} {'Điểm KLTN':<11} {'Học kỳ TN'}"
        lines.append(r_header)
        lines.append("  " + "-" * 92)

        for idx, st in enumerate(roster, 1):
            name = st["name"]
            if len(name) > 23:
                name = name[:22] + "…"
            prog_name = st["program_name"]
            if len(prog_name) > 20:
                prog_name = prog_name[:19] + "…"
            kltn_str = f"{st['kltn_score']:.1f} ({st['kltn_grade']})" if st['kltn_score'] is not None else "-"
            lines.append(
                f"  {idx:<4} {st['student_id']:<9} {name:<24} {prog_name:<22} "
                f"{st['base_score']:<10.1f} {kltn_str:<11} {st['kltn_semester']}"
            )

    lines.append("-" * 96)
    lines.append(" [*] Quy định đào tạo & Chuẩn tốt nghiệp Trường ĐHBK - ĐHQG-HCM:")
    lines.append("     - Tốt nghiệp sớm: Kỳ 7 (3.5 năm) chỉ áp dụng cho nhóm sinh viên xuất sắc học vượt KLTN (CO4337) và đủ chuẩn.")
    lines.append("     - Tốt nghiệp đúng hạn: Kỳ 8 (4.0 năm) hoàn thành CTĐT + Chuẩn Tiếng Anh + Tối thiểu 15 ngày CTXH.")
    lines.append("     - Tốt nghiệp trễ hạn: Kỳ 9 (4.5 năm), Kỳ 10 (5.0 năm), Kỳ 11 (5.5 năm), Kỳ 12 (6.0 năm).")
    lines.append("     - Thời gian đào tạo tối đa: 6.0 năm (12 học kỳ chính). Quá thời hạn này sẽ bị xử lý buộc thôi học.")
    lines.append(sep + "\n")

    return "\n".join(lines)



