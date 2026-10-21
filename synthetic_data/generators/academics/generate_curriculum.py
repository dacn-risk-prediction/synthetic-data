"""
Academic Curriculum Generator for Computer Science (KHMT)
Cohorts: K20, K21, K22, K23, K24, K25, K26 (K25 & K26 share K24 curriculum)

Generates 5 standardized academic catalog tables:
1. curriculums.csv - Program definitions per cohort
2. knowledge_blocks.csv - Standardized academic knowledge areas
3. courses.csv - Master course catalog with metadata
4. program_structures.csv - Detailed mapping of courses to curriculum blocks
5. course_prerequisites.csv - Comprehensive prerequisite relations (TQ, KN, SH)
"""

import csv
import re
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DOCUMENTS_GROUP_DIR = ROOT_DIR.parent / "documents" / "group"
OUTPUT_DIR = ROOT_DIR / "generated" / "academics"

# Department mapping by course prefix
DEPARTMENT_MAP = {
    "CO": "Khoa Khoa học và Kỹ thuật Máy tính",
    "MT": "Khoa Khoa học Ứng dụng - Bộ môn Toán ứng dụng",
    "PH": "Khoa Khoa học Ứng dụng - Bộ môn Vật lý ứng dụng",
    "CH": "Khoa Kỹ thuật Hóa học",
    "SP": "Khoa Khoa học Ứng dụng - Bộ môn Lý luận Chính trị",
    "LA": "Trung tâm Ngoại ngữ",
    "IM": "Khoa Quản lý Công nghiệp",
    "ME": "Khoa Kỹ thuật Cơ khí",
    "PE": "Bộ môn Giáo dục Thể chất",
    "MI": "Trung tâm GDQP và AN",
    "SA": "Phòng Công tác Sinh viên",
}

# Standardized Knowledge Blocks definitions
KNOWLEDGE_BLOCKS_DATA = [
    {
        "block_id": "MATH_SCI",
        "block_code": "A",
        "block_name_vi": "Toán và Khoa học Tự nhiên",
        "block_name_en": "Mathematics and Basic Sciences",
        "category": "Toán & KHTN",
        "required_credits": 30.0,
        "description": "Các môn toán nền tảng, vật lý, hóa học, cấu trúc rời rạc và mô hình hóa toán học.",
    },
    {
        "block_id": "POLITICS_LAW",
        "block_code": "B.1",
        "block_name_vi": "Kinh tế, Chính trị, Xã hội, Pháp luật",
        "block_name_en": "Socials, Politics, Economics and Law",
        "category": "Giáo dục chung",
        "required_credits": 13.0,
        "description": "Lý luận chính trị Mác - Lênin, Tư tưởng Hồ Chí Minh, Lịch sử Đảng và Pháp luật đại cương.",
    },
    {
        "block_id": "GEN_SKILLS",
        "block_code": "B.2.1-2",
        "block_name_vi": "Nhập môn & Kỹ năng Nghề nghiệp",
        "block_name_en": "Introduction and Professional Skills",
        "category": "Giáo dục chung",
        "required_credits": 6.0,
        "description": "Nhập môn điện toán và Kỹ năng chuyên nghiệp cho kỹ sư.",
    },
    {
        "block_id": "MANAGEMENT",
        "block_code": "B.2.3",
        "block_name_vi": "Quản lý cho Kỹ sư",
        "block_name_en": "Management for Engineers",
        "category": "Giáo dục chung",
        "required_credits": 3.0,
        "description": "Các môn quản lý dự án, kinh tế kỹ thuật, khởi nghiệp, năng suất chất lượng.",
    },
    {
        "block_id": "FOREIGN_LANG",
        "block_code": "B.3",
        "block_name_vi": "Ngoại ngữ (Tiếng Anh)",
        "block_name_en": "Foreign Languages",
        "category": "Giáo dục chung",
        "required_credits": 8.0,
        "description": "Chuỗi học phần Anh văn 1, 2, 3, 4.",
    },
    {
        "block_id": "CORE",
        "block_code": "C",
        "block_name_vi": "Cơ sở ngành",
        "block_name_en": "Core Courses",
        "category": "Cơ sở ngành",
        "required_credits": 21.0,
        "description": "Hệ thống số, Kỹ thuật lập trình, Cấu trúc dữ liệu & giải thuật, Kiến trúc máy tính, Hệ CSDL, Lập trình nâng cao.",
    },
    {
        "block_id": "MAJOR",
        "block_code": "D",
        "block_name_vi": "Bắt buộc ngành",
        "block_name_en": "Compulsory Major Subjects",
        "category": "Ngành",
        "required_credits": 13.0,
        "description": "Hệ điều hành, Công nghệ phần mềm, Nguyên lý ngôn ngữ lập trình, Mạng máy tính.",
    },
    {
        "block_id": "ELECTIVE_MAJOR_A",
        "block_code": "E.1",
        "block_name_vi": "Tự chọn ngành - Nhóm A (Đồ án tổng hợp)",
        "block_name_en": "Elective Major - Group A (Integration Project)",
        "category": "Tự chọn ngành",
        "required_credits": 1.0,
        "description": "Đồ án tổng hợp thực hành lập trình theo hướng chuyên sâu.",
    },
    {
        "block_id": "ELECTIVE_MAJOR_B",
        "block_code": "E.2",
        "block_name_vi": "Tự chọn ngành - Nhóm B (Đồ án đa ngành)",
        "block_name_en": "Elective Major - Group B (Multidisciplinary Project)",
        "category": "Tự chọn ngành",
        "required_credits": 1.0,
        "description": "Thực tập đồ án môn học đa ngành kết hợp thực chiến.",
    },
    {
        "block_id": "SPEC_DATA",
        "block_code": "F.1",
        "block_name_vi": "Chuyên ngành Công nghệ Dữ liệu & Dữ liệu lớn",
        "block_name_en": "Specialty: Data Engineering and Big Data",
        "category": "Chuyên ngành",
        "required_credits": 15.0,
        "description": "Hệ quản trị CSDL, Khai phá dữ liệu, Dữ liệu lớn, Kho dữ liệu & BI.",
    },
    {
        "block_id": "SPEC_SE",
        "block_code": "F.2",
        "block_name_vi": "Chuyên ngành Công nghệ Phần mềm",
        "block_name_en": "Specialty: Software Engineering",
        "category": "Chuyên ngành",
        "required_credits": 15.0,
        "description": "Kiến trúc phần mềm, Kiểm thử phần mềm, Quản lý dự án PM, Bảo mật phần mềm.",
    },
    {
        "block_id": "SPEC_CS",
        "block_code": "F.3",
        "block_name_vi": "Chuyên ngành Khoa học Máy tính",
        "block_name_en": "Specialty: Computer Science",
        "category": "Chuyên ngành",
        "required_credits": 15.0,
        "description": "Chuyên ngành rộng bao quát toàn diện các lĩnh vực KHMT.",
    },
    {
        "block_id": "SPEC_SEC",
        "block_code": "F.4",
        "block_name_vi": "Chuyên ngành An ninh Hệ thống và Mạng",
        "block_name_en": "Specialty: System and Network Security",
        "category": "Chuyên ngành",
        "required_credits": 15.0,
        "description": "Mật mã & an ninh mạng, Quản trị mạng, Đánh giá an toàn thông tin, Hệ phân bố.",
    },
    {
        "block_id": "SPEC_AI",
        "block_code": "F.5",
        "block_name_vi": "Chuyên ngành Trí tuệ Nhân tạo",
        "block_name_en": "Specialty: Artificial Intelligence",
        "category": "Chuyên ngành",
        "required_credits": 15.0,
        "description": "Nhập môn AI, Học máy, Học sâu, Xử lý ngôn ngữ tự nhiên, Thị giác máy tính.",
    },
    {
        "block_id": "SPEC_CV",
        "block_code": "F.6",
        "block_name_vi": "Chuyên ngành Xử lý ảnh và Thị giác máy tính",
        "block_name_en": "Specialty: Image Processing and Computer Vision",
        "category": "Chuyên ngành",
        "required_credits": 15.0,
        "description": "Xử lý ảnh số, Đồ họa máy tính, Game programming (K20-K23, sáp nhập vào AI từ K24).",
    },
    {
        "block_id": "FREE_ELECTIVE",
        "block_code": "G",
        "block_name_vi": "Tự chọn tự do",
        "block_name_en": "Free Electives",
        "category": "Tự do",
        "required_credits": 9.0,
        "description": "Sinh viên tự do tích lũy các học phần trong hoặc ngoài Khoa.",
    },
    {
        "block_id": "GRADUATION",
        "block_code": "H",
        "block_name_vi": "Học phần Tốt nghiệp",
        "block_name_en": "Graduation Modules",
        "category": "Tốt nghiệp",
        "required_credits": 8.0,
        "description": "Thực tập ngoài trường (2 TC), Đồ án chuyên ngành (2 TC), Đồ án tốt nghiệp (4 TC).",
    },
    {
        "block_id": "COND_DEFENSE",
        "block_code": "I",
        "block_name_vi": "Giáo dục Quốc phòng",
        "block_name_en": "National Defense Education",
        "category": "Điều kiện tốt nghiệp",
        "required_credits": 0.0,
        "description": "Chứng chỉ Giáo dục Quốc phòng và An ninh (MI1003).",
    },
    {
        "block_id": "COND_PHYSICAL",
        "block_code": "J",
        "block_name_vi": "Giáo dục Thể chất",
        "block_name_en": "Physical Education",
        "category": "Điều kiện tốt nghiệp",
        "required_credits": 0.0,
        "description": "Học phần Giáo dục thể chất 1 & 2 (PE1003/PE1005 hoặc thể thao tự chọn).",
    },
    {
        "block_id": "COND_OTHERS",
        "block_code": "K",
        "block_name_vi": "Điều kiện Tốt nghiệp Khác",
        "block_name_en": "Other Graduation Requirements",
        "category": "Điều kiện tốt nghiệp",
        "required_credits": 0.0,
        "description": "Hoạt động sinh viên (SA4001), Chuẩn tiếng Anh tốt nghiệp.",
    },
]

# Supplementary course details for new courses or PE courses
SUPPLEMENTARY_COURSES = {
    "IM1031": ("Khởi nghiệp và đổi mới sáng tạo", "Entrepreneurship and Innovation", 3),
    "ME1019": ("Quản lý năng suất và chất lượng", "Quality and Productivity Management", 3),
    "SA4001": ("Hoạt động sinh viên", "Student Activities", 0),
    "MI1003": ("Giáo dục Quốc phòng", "National Defense Education", 0),
    "PE1003": ("Giáo dục thể chất 1", "Physical Education 1", 0),
    "PE1005": ("Giáo dục thể chất 2", "Physical Education 2", 0),
    "PE1009": ("Bóng đá (Học phần 1)", "Football 1", 0),
    "PE1011": ("Bóng chuyền (Học phần 1)", "Volleyball 1", 0),
    "PE1013": ("Bóng bàn (Học phần 1)", "Table Tennis 1", 0),
    "PE1015": ("Bóng rổ (Học phần 1)", "Basketball 1", 0),
    "PE1017": ("Cầu lông (Học phần 1)", "Badminton 1", 0),
    "PE1019": ("Bơi (Học phần 1)", "Swimming 1", 0),
    "PE1021": ("Aerobic (Học phần 1)", "Aerobic 1", 0),
    "PE1025": ("Điền kinh (Học phần 1)", "Athletics 1", 0),
    "PE1027": ("Quần vợt (Học phần 1)", "Tennis 1", 0),
    "PE1053": ("Cờ vua (Học phần 1)", "Chess 1", 0),
    "PE1057": ("Bowling (Học phần 1)", "Bowling 1", 0),
    "PE1061": ("Pickleball (Học phần 1)", "Pickleball 1", 0),
    "PE1033": ("Bóng đá (Học phần 2)", "Football 2", 0),
    "PE1035": ("Bóng chuyền (Học phần 2)", "Volleyball 2", 0),
    "PE1037": ("Bóng bàn (Học phần 2)", "Table Tennis 2", 0),
    "PE1039": ("Bóng rổ (Học phần 2)", "Basketball 2", 0),
    "PE1041": ("Cầu lông (Học phần 2)", "Badminton 2", 0),
    "PE1043": ("Bơi (Học phần 2)", "Swimming 2", 0),
    "PE1045": ("Aerobic (Học phần 2)", "Aerobic 2", 0),
    "PE1049": ("Điền kinh (Học phần 2)", "Athletics 2", 0),
    "PE1051": ("Quần vợt (Học phần 2)", "Tennis 2", 0),
    "PE1055": ("Cờ vua (Học phần 2)", "Chess 2", 0),
    "PE1059": ("Bowling (Học phần 2)", "Bowling 2", 0),
    "PE1063": ("Pickleball (Học phần 2)", "Pickleball 2", 0),
}

# Fixed knowledge block sets
MATH_SCI_COURSES = {"MT1003", "MT1005", "MT1007", "MT2013", "CH1003", "PH1003", "PH1007", "CO1007", "CO2011"}
POLITICS_LAW_COURSES = {"SP1007", "SP1031", "SP1033", "SP1035", "SP1037", "SP1039"}
GEN_SKILLS_COURSES = {"CO1005", "CO2001"}
MANAGEMENT_COURSES = {"IM1013", "IM1023", "IM1025", "IM1027", "IM3001", "IM1031", "ME1019"}
FOREIGN_LANG_COURSES = {"LA1003", "LA1005", "LA1007", "LA1009"}
CORE_COURSES = {"CO1023", "CO1027", "CO2003", "CO2007", "CO2013", "CO2039"}
MAJOR_COURSES = {"CO2017", "CO3001", "CO3005", "CO3093"}
ELECTIVE_MAJOR_A_COURSES = {"CO3101", "CO3103", "CO3105", "CO3119", "CO3127"}
ELECTIVE_MAJOR_B_COURSES = {"CO3107", "CO3109", "CO3111"}
GRADUATION_COURSES = {"CO3335", "CO4029", "CO4337"}
DEFENSE_COURSES = {"MI1003"}
OTHERS_COURSES = {"SA4001"}

# Recommended semesters mapping
RECOMMENDED_SEMESTERS = {
    "LA1003": "HK1", "PE1003": "HK1", "MT1003": "HK1", "PH1003": "HK1", "CO1005": "HK1", "CO1023": "HK1",
    "LA1005": "HK2", "PE1005": "HK2", "MT1005": "HK2", "MT1007": "HK2", "CO1007": "HK2", "CO1027": "HK2", "PH1007": "HK2", "MI1003": "HK2",
    "LA1007": "HK3", "SP1031": "HK3", "CO2007": "HK3", "CO2011": "HK3", "CO2003": "HK3",
    "LA1009": "HK4", "SP1033": "HK4", "CO2017": "HK4", "CO2039": "HK4", "MT2013": "HK4",
    "SP1035": "HK5", "CO3005": "HK5", "CO3001": "HK5", "CO2013": "HK5", "CO2001": "HK5",
    "SP1037": "HK6", "CO3093": "HK6", "CH1003": "HK6",
    "SP1039": "HK7", "CO3335": "HK7", "CO4029": "HK7",
    "SP1007": "HK8", "CO4337": "HK8", "SA4001": "HK8"
}


def resolve_course_block(code, curr_spec):
    """
    Deterministically maps a course code and its active context to its block, type, and elective group.
    """
    if code in MATH_SCI_COURSES:
        return "MATH_SCI", "BB", "", "Toàn ngành"
    if code in POLITICS_LAW_COURSES:
        return "POLITICS_LAW", "BB", "", "Toàn ngành"
    if code in GEN_SKILLS_COURSES:
        return "GEN_SKILLS", "BB", "", "Toàn ngành"
    if code in MANAGEMENT_COURSES:
        return "MANAGEMENT", "TC", "Group D", "Toàn ngành"
    if code in FOREIGN_LANG_COURSES:
        return "FOREIGN_LANG", "BB", "", "Toàn ngành"
    if code in CORE_COURSES:
        return "CORE", "BB", "", "Toàn ngành"
    if code in MAJOR_COURSES:
        return "MAJOR", "BB", "", "Toàn ngành"
    if code in ELECTIVE_MAJOR_A_COURSES:
        return "ELECTIVE_MAJOR_A", "TC", "Group A", "Toàn ngành"
    if code in ELECTIVE_MAJOR_B_COURSES:
        return "ELECTIVE_MAJOR_B", "TC", "Group B", "Toàn ngành"
    if code in GRADUATION_COURSES:
        return "GRADUATION", "BB", "", "Toàn ngành"
    if code in DEFENSE_COURSES:
        return "COND_DEFENSE", "BB", "", "Toàn ngành"
    if code.startswith("PE"):
        return "COND_PHYSICAL", "BB", "", "Toàn ngành"
    if code in OTHERS_COURSES:
        return "COND_OTHERS", "BB", "", "Toàn ngành"

    # Specialization electives (Group C) - case-insensitive check
    s = curr_spec.lower()
    if "dữ liệu" in s:
        return "SPEC_DATA", "TC", "Group C", curr_spec
    if "phần mềm" in s:
        return "SPEC_SE", "TC", "Group C", curr_spec
    if "mật mã" in s or "an ninh" in s:
        return "SPEC_SEC", "TC", "Group C", curr_spec
    if "trí tuệ" in s:
        return "SPEC_AI", "TC", "Group C", curr_spec
    if "xử lý ảnh" in s:
        return "SPEC_CV", "TC", "Group C", curr_spec
    return "SPEC_CS", "TC", "Group C", curr_spec


def load_baseline_courses():
    baseline = {}
    courses_path = ROOT_DIR / "generated" / "academics" / "courses.csv"
    if courses_path.exists():
        with courses_path.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                baseline[row["course_code"]] = {
                    "name_vi": row.get("course_name_vi", ""),
                    "name_en": row.get("course_name_en", ""),
                    "credits": int(float(row.get("credits", 0))),
                }
    return baseline


def extract_text_from_pdf(pdf_path):
    txt_path = pdf_path.with_suffix(".txt")
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8", errors="ignore")
    
    # Try pdftotext
    try:
        res = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True, check=True)
        return res.stdout
    except Exception:
        # Fallback to scratch path if present
        scratch_txt = Path(f"/home/nhan/.gemini/antigravity/brain/4bad32cb-b566-4133-b853-3975bd6863b9/scratch/group/{pdf_path.stem}.txt")
        if scratch_txt.exists():
            return scratch_txt.read_text(encoding="utf-8", errors="ignore")
        return ""


def build_curriculums():
    curriculums = []
    cohorts = [
        (20, 2020, None),
        (21, 2021, None),
        (22, 2022, None),
        (23, 2023, None),
        (24, 2024, None),
        (25, 2025, "KHMT_K24"),
        (26, 2026, "KHMT_K24"),
    ]
    for c_num, acad_year, base_id in cohorts:
        cid = f"KHMT_K{c_num}"
        cname = f"Chương trình Đào tạo Cử nhân Khoa học Máy tính Khóa 20{c_num}"
        curriculums.append({
            "curriculum_id": cid,
            "curriculum_name": cname,
            "major_code": "KHMT",
            "major_name": "Khoa học Máy tính",
            "cohort": f"K{c_num}",
            "academic_year_start": acad_year,
            "total_credits": 128.0,
            "base_curriculum_id": base_id if base_id else "",
            "faculty": "Khoa Khoa học và Kỹ thuật Máy tính",
        })
    return curriculums


def parse_program_structures_from_pdf(year, text, master_courses):
    lines = text.split("\n")
    structures = []
    seen = set()

    in_body = False
    curr_spec = "Toàn ngành"

    for idx, line in enumerate(lines):
        l = line.strip()

        # Mark entrance into body
        if any(h in l for h in ["I. Cấu trúc CTĐT", "1. Kiến thức giáo dục", "I. Các môn bắt buộc", "A. Các môn bắt buộc", "A. Toán"]):
            in_body = True
            curr_spec = "Toàn ngành"
        if not in_body:
            continue

        # Check course line first
        m = re.match(r"^\s*(\d+(\.\d+)?)\s+([A-Z]{2}\d{4})\b\s*(.*)", line)
        if m:
            code = m.group(3)
            if code == "CO1033":
                continue  # Skip prerequisite typo

            block_id, course_type, elective_group, spec = resolve_course_block(code, curr_spec)

            # Avoid duplicating common courses within same curriculum
            unique_key = (code, block_id, spec)
            if unique_key in seen:
                continue
            seen.add(unique_key)

            # Prerequisite regex
            prereq = ""
            prereq_match = re.search(r"([A-Z]{2}\d{4}\([A-Z]+\)(?:,\s*[A-Z]{2}\d{4}\([A-Z]+\))*)", line)
            if prereq_match:
                prereq = prereq_match.group(1)

            course_meta = master_courses.get(code, {})
            credits_val = course_meta.get("credits", 0)

            structures.append({
                "curriculum_id": f"KHMT_K{year[2:]}",
                "course_code": code,
                "block_id": block_id,
                "course_type": course_type,
                "elective_group": elective_group,
                "specialization": spec,
                "credits": credits_val,
                "recommended_semester": RECOMMENDED_SEMESTERS.get(code, ""),
                "prerequisites": prereq,
            })
            continue

        # ONLY update section context if NOT a course line
        if "dữ liệu" in l.lower() and any(w in l.lower() for w in ["chuyên ngành", "special", "f.1", "b1.", "ii.1"]):
            curr_spec = "Công nghệ dữ liệu và dữ liệu lớn" if year == "2024" else "Công nghệ Dữ liệu Bảo mật và Trí tuệ Kinh doanh"
        elif "phần mềm" in l.lower() and any(w in l.lower() for w in ["chuyên ngành", "special", "f.2", "b2.", "ii.2"]):
            curr_spec = "Công nghệ Phần mềm"
        elif "khoa học máy tính" in l.lower() and any(w in l.lower() for w in ["chuyên ngành", "special", "f.3", "b3.", "ii.3"]):
            curr_spec = "Khoa học Máy tính"
        elif ("mật mã" in l.lower() or "an ninh" in l.lower()) and any(w in l.lower() for w in ["chuyên ngành", "special", "f.4", "b4.", "ii.4"]):
            curr_spec = "An ninh hệ thống và mạng" if year == "2024" else "Mật mã và An ninh mạng"
        elif "trí tuệ" in l.lower() and any(w in l.lower() for w in ["chuyên ngành", "special", "f.5", "b5.", "ii.5"]):
            curr_spec = "Trí tuệ nhân tạo" if year == "2024" else "Trí tuệ nhân tạo ứng dụng"
        elif "xử lý ảnh" in l.lower() and any(w in l.lower() for w in ["chuyên ngành", "special", "b6.", "ii.6"]):
            curr_spec = "Xử lý ảnh và Thị giác máy tính"
        elif "nhóm tự chọn c" in l.lower() and curr_spec == "Toàn ngành":
            curr_spec = "Khoa học Máy tính"

    return structures


def parse_prerequisites_from_pdf(text, year):
    """
    Extracts all prerequisite relations (TQ, KN, SH) from the PDF text.
    Captures course code and prerequisite relations within the course item 3-line block.
    """
    lines = text.split("\n")
    results = []
    seen = set()

    for k, line in enumerate(lines):
        m = re.match(r"^\s*(\d+(\.\d+)?)\s+([A-Z]{2}\d{4})\b", line)
        if m:
            code = m.group(3)
            # Item window: line k-1 (VI title), line k (code line), line k+1 (EN title)
            item_lines = [line]
            if k > 0 and not re.match(r"^\s*(\d+(\.\d+)?)\s+([A-Z]{2}\d{4})\b", lines[k-1]):
                item_lines.append(lines[k-1])
            if k + 1 < len(lines) and not re.match(r"^\s*(\d+(\.\d+)?)\s+([A-Z]{2}\d{4})\b", lines[k+1]):
                item_lines.append(lines[k+1])

            chunk = " ".join(item_lines)
            matches = re.findall(r"([A-Z]{2}\d{4})\s*\(([A-Z]+)\)", chunk)
            for p_code, p_type in matches:
                if p_code == "CO1033":
                    p_code = "CO1023"  # Fix typo in PDF
                if p_code != code:
                    key = (code, p_code, p_type)
                    if key not in seen:
                        seen.add(key)
                        norm_type = "KN" if p_type in ["KN", "HT"] else ("SH" if p_type in ["SH", "SHT"] else "TQ")
                        results.append({
                            "curriculum_id": f"KHMT_K{year[2:]}",
                            "course_code": code,
                            "prerequisite_course_code": p_code,
                            "relation_type": norm_type,
                            "relation_type_raw": p_type,
                            "min_grade": 5.0 if norm_type == "TQ" else 0.0,
                        })
    return results


def generate_all_academics():
    print("=== Generating Academic Catalog for K20 - K26 ===")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load baseline and extract text from all 5 PDFs
    baseline = load_baseline_courses()
    master_courses = {}

    # Initialize with baseline and supplementary
    for code, info in baseline.items():
        prefix = code[:2]
        master_courses[code] = {
            "course_code": code,
            "course_name_vi": info["name_vi"],
            "course_name_en": "",
            "credits": info["credits"],
            "department": DEPARTMENT_MAP.get(prefix, "Trường Đại học Bách Khoa"),
        }

    for code, (vi, en, cr) in SUPPLEMENTARY_COURSES.items():
        prefix = code[:2]
        if code not in master_courses:
            master_courses[code] = {
                "course_code": code,
                "course_name_vi": vi,
                "course_name_en": en,
                "credits": cr,
                "department": DEPARTMENT_MAP.get(prefix, "Trường Đại học Bách Khoa"),
            }
        else:
            if not master_courses[code]["course_name_en"]:
                master_courses[code]["course_name_en"] = en

    pdf_texts = {}
    years = ["2020", "2021", "2022", "2023", "2024"]
    for y in years:
        pdf_path = DOCUMENTS_GROUP_DIR / f"{y}_MT_KHMT.pdf"
        txt = extract_text_from_pdf(pdf_path)
        pdf_texts[y] = txt

        # Parse any additional English/Vietnamese names from lines
        lines = txt.split("\n")
        for idx, line in enumerate(lines):
            m = re.match(r"^\s*(\d+(\.\d+)?)\s+([A-Z]{2}\d{4})\b", line)
            if m:
                code = m.group(3)
                if code == "CO1033":
                    continue
                if code not in master_courses:
                    vi_name = lines[idx-1].strip() if idx > 0 else ""
                    en_name = lines[idx+1].strip() if idx + 1 < len(lines) else ""
                    prefix = code[:2]
                    master_courses[code] = {
                        "course_code": code,
                        "course_name_vi": vi_name,
                        "course_name_en": en_name,
                        "credits": 3,
                        "department": DEPARTMENT_MAP.get(prefix, "Trường Đại học Bách Khoa"),
                    }
                elif not master_courses[code]["course_name_en"] and idx + 1 < len(lines):
                    en_cand = lines[idx+1].strip()
                    if en_cand and not re.match(r"^[A-Z]{2}\d{4}", en_cand) and not en_cand.startswith("Trang"):
                        clean_en = re.sub(r"\s{2,}.*", "", en_cand)
                        master_courses[code]["course_name_en"] = clean_en

    # Fill English names for core courses if empty
    core_en_defaults = {
        "CO1005": "Introduction to Computing",
        "CO1007": "Discrete Structures for Computing",
        "CO1023": "Digital Systems",
        "CO1027": "Programming Fundamentals",
        "CO2001": "Professional Skills for Engineers",
        "CO2003": "Data Structures and Algorithms",
        "CO2007": "Computer Architecture",
        "CO2011": "Mathematical Modeling",
        "CO2013": "Database Systems",
        "CO2017": "Operating Systems",
        "CO2039": "Advanced Programming",
        "CO3001": "Software Engineering",
        "CO3005": "Principles of Programming Languages",
        "CO3093": "Computer Networks",
        "CO3335": "Internship",
        "CO4029": "Specialized Project",
        "CO4337": "Capstone Project",
        "MT1003": "Calculus 1",
        "MT1005": "Calculus 2",
        "MT1007": "Linear Algebra",
        "MT2013": "Probability and Statistics",
        "CH1003": "General Chemistry",
        "PH1003": "General Physics 1",
        "PH1007": "General Physics Lab",
        "LA1003": "English 1",
        "LA1005": "English 2",
        "LA1007": "English 3",
        "LA1009": "English 4",
        "SP1007": "Introduction to Vietnamese Law",
        "SP1031": "Marxist-Leninist Philosophy",
        "SP1033": "Marxist-Leninist Political Economy",
        "SP1035": "Scientific Socialism",
        "SP1037": "Ho Chi Minh Ideology",
        "SP1039": "History of Vietnamese Communist Party",
    }
    for c, en in core_en_defaults.items():
        if c in master_courses and not master_courses[c]["course_name_en"]:
            master_courses[c]["course_name_en"] = en

    # Assign course_id integer (1..N) sorted by course_code
    courses_list = []
    for c_id, code in enumerate(sorted(master_courses.keys()), start=1):
        info = master_courses[code]
        courses_list.append({
            "course_id": c_id,
            "course_code": code,
            "course_name_vi": info["course_name_vi"],
            "course_name_en": info["course_name_en"],
            "credits": info["credits"],
            "department": info["department"],
        })

    # Save courses.csv
    courses_file = OUTPUT_DIR / "courses.csv"
    with courses_file.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["course_id", "course_code", "course_name_vi", "course_name_en", "credits", "department"])
        writer.writeheader()
        writer.writerows(courses_list)
    print(f"-> Generated {courses_file} ({len(courses_list)} courses)")

    # 2. Save curriculums.csv
    curriculums = build_curriculums()
    curriculums_file = OUTPUT_DIR / "curriculums.csv"
    with curriculums_file.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "curriculum_id", "curriculum_name", "major_code", "major_name", "cohort",
            "academic_year_start", "total_credits", "base_curriculum_id", "faculty"
        ])
        writer.writeheader()
        writer.writerows(curriculums)
    print(f"-> Generated {curriculums_file} ({len(curriculums)} curriculums: K20 - K26)")

    # 3. Save knowledge_blocks.csv
    blocks_file = OUTPUT_DIR / "knowledge_blocks.csv"
    with blocks_file.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "block_id", "block_code", "block_name_vi", "block_name_en", "category", "required_credits", "description"
        ])
        writer.writeheader()
        writer.writerows(KNOWLEDGE_BLOCKS_DATA)
    print(f"-> Generated {blocks_file} ({len(KNOWLEDGE_BLOCKS_DATA)} knowledge blocks)")

    # 4. Save program_structures.csv
    program_structures = []
    structure_id = 1

    # Generate structures for K20..K24 from PDF text
    k24_structures = []
    for y in years:
        txt = pdf_texts[y]
        entries = parse_program_structures_from_pdf(y, txt, master_courses)
        for e in entries:
            e_copy = dict(e)
            e_copy["structure_id"] = structure_id
            structure_id += 1
            program_structures.append(e_copy)
            if y == "2024":
                k24_structures.append(e)

    # For K25 and K26: duplicate K24 program structures
    for next_cohort in ["K25", "K26"]:
        for e in k24_structures:
            e_clone = dict(e)
            e_clone["structure_id"] = structure_id
            e_clone["curriculum_id"] = f"KHMT_{next_cohort}"
            structure_id += 1
            program_structures.append(e_clone)

    prog_struct_file = OUTPUT_DIR / "program_structures.csv"
    with prog_struct_file.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "structure_id", "curriculum_id", "course_code", "block_id", "course_type",
            "elective_group", "specialization", "credits", "recommended_semester", "prerequisites"
        ])
        writer.writeheader()
        writer.writerows(program_structures)
    print(f"-> Generated {prog_struct_file} ({len(program_structures)} mapping entries across K20 - K26)")

    # 5. Save course_prerequisites.csv
    prereq_records = []
    prereq_id = 1

    # Parse prerequisites from 2021..2024
    parsed_prereqs_by_year = {}
    for y in ["2021", "2022", "2023", "2024"]:
        parsed_prereqs_by_year[y] = parse_prerequisites_from_pdf(pdf_texts[y], y)

    # 2020 inherits 2021 prerequisites
    k20_inherited = []
    for item in parsed_prereqs_by_year["2021"]:
        c_item = dict(item)
        c_item["curriculum_id"] = "KHMT_K20"
        k20_inherited.append(c_item)
    parsed_prereqs_by_year["2020"] = k20_inherited

    # Add K20..K24
    for y in ["2020", "2021", "2022", "2023", "2024"]:
        for item in parsed_prereqs_by_year[y]:
            c_code = item["course_code"]
            p_code = item["prerequisite_course_code"]
            rel_type = item["relation_type"]
            
            c_name = master_courses.get(c_code, {}).get("course_name_vi", c_code)
            p_name = master_courses.get(p_code, {}).get("course_name_vi", p_code)

            desc = ""
            if rel_type == "TQ":
                desc = f"Bắt buộc phải học và thi đậu môn {p_code} ({p_name}) với điểm >= 5.0"
            elif rel_type == "KN":
                desc = f"Học trước / khởi nguyên: Phải từng học / tích lũy môn {p_code} ({p_name})"
            elif rel_type == "SH":
                desc = f"Song hành: Được phép học cùng học kỳ hoặc trước môn {p_code} ({p_name})"

            prereq_records.append({
                "prerequisite_id": prereq_id,
                "curriculum_id": item["curriculum_id"],
                "course_code": c_code,
                "course_name_vi": c_name,
                "prerequisite_course_code": p_code,
                "prerequisite_course_name_vi": p_name,
                "relation_type": rel_type,
                "relation_type_raw": item["relation_type_raw"],
                "min_grade": item["min_grade"],
                "description": desc,
            })
            prereq_id += 1

    # K25 and K26 duplicate K24 prerequisites
    k24_prereqs = [p for p in prereq_records if p["curriculum_id"] == "KHMT_K24"]
    for next_cohort in ["K25", "K26"]:
        for item in k24_prereqs:
            c_clone = dict(item)
            c_clone["prerequisite_id"] = prereq_id
            c_clone["curriculum_id"] = f"KHMT_{next_cohort}"
            prereq_records.append(c_clone)
            prereq_id += 1

    prereq_file = OUTPUT_DIR / "course_prerequisites.csv"
    with prereq_file.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "prerequisite_id", "curriculum_id", "course_code", "course_name_vi",
            "prerequisite_course_code", "prerequisite_course_name_vi", "relation_type",
            "relation_type_raw", "min_grade", "description"
        ])
        writer.writeheader()
        writer.writerows(prereq_records)
    print(f"-> Generated {prereq_file} ({len(prereq_records)} prerequisite relations across K20 - K26)")


if __name__ == "__main__":
    generate_all_academics()
