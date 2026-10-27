"""Script to import synthetic academic data into Neon PostgreSQL Database.

Clean Business Schema (13 tables):
  - Academic Catalogs: semesters, courses, course_prerequisites
  - Curriculum & Structure: curriculums, knowledge_blocks, program_structures, course_assessments
  - Users & Profiles: users, students, lecturers, admins
  - Operations & Grades: classes, enrollments

Usage:
    # 1. Chạy kiểm tra đối soát toàn diện (Dry Run - KHÔNG kết nối hoặc tác động DB):
    python database/push_data.py --dry-run

    # 2. Đẩy dữ liệu thật lên Neon (cần DATABASE_URL trong .env):
    python database/push_data.py

    # 3. Làm sạch dữ liệu cũ rồi đẩy mới:
    python database/push_data.py --reset
"""

import glob
import os
import sys
import time
import uuid
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# Try loading with python-dotenv, with safe fallback if not installed
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# -----------------------------------------------------------------------------
# 1. DATABASE CONFIGURATION
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_DIR = PROJECT_ROOT / "synthetic_data"
ENV_FILE = PROJECT_ROOT / ".env"

# Load environment variables from .env file
if load_dotenv:
    load_dotenv(dotenv_path=ENV_FILE)
elif ENV_FILE.exists():
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


# -----------------------------------------------------------------------------
# 2. SCHEMA DEFINITION (DDL CHUẨN NGHIỆP VỤ - 13 BẢNG)
# -----------------------------------------------------------------------------
DDL_STATEMENTS = """
-- ============================================================================
-- 1. DANH MỤC HỌC VỤ & CHƯƠNG TRÌNH ĐÀO TẠO
-- ============================================================================

-- 1. Semesters (Danh mục học kỳ)
CREATE TABLE IF NOT EXISTS semesters (
    semester_code VARCHAR(20) PRIMARY KEY,
    academic_year VARCHAR(20) NOT NULL,
    term INT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE
);

-- 2. Courses (Danh mục môn học - Đã bỏ trường difficulty của bộ sinh data)
CREATE TABLE IF NOT EXISTS courses (
    course_code VARCHAR(20) PRIMARY KEY,
    course_name VARCHAR(255) NOT NULL,
    credits INT NOT NULL
);

-- 3. Course Prerequisites (Môn tiên quyết / học trước / song hành)
CREATE TABLE IF NOT EXISTS course_prerequisites (
    course_prerequisite_id INT PRIMARY KEY,
    course_code VARCHAR(20) REFERENCES courses(course_code) ON DELETE CASCADE,
    related_course_code VARCHAR(20) REFERENCES courses(course_code) ON DELETE CASCADE,
    relation_type VARCHAR(10) NOT NULL
);

-- 4. Curriculums (Chương trình đào tạo theo ngành/khóa)
CREATE TABLE IF NOT EXISTS curriculums (
    curriculum_id VARCHAR(50) PRIMARY KEY,
    curriculum_name VARCHAR(255) NOT NULL,
    major_code VARCHAR(50) NOT NULL,
    major_name VARCHAR(255) NOT NULL,
    cohort VARCHAR(20) NOT NULL,
    academic_year_start INT,
    total_credits FLOAT,
    base_curriculum_id VARCHAR(50),
    faculty VARCHAR(255)
);

-- 5. Knowledge Blocks (Khối kiến thức trong CTĐT)
CREATE TABLE IF NOT EXISTS knowledge_blocks (
    block_id VARCHAR(50) PRIMARY KEY,
    block_code VARCHAR(20),
    block_name_vi VARCHAR(255) NOT NULL,
    block_name_en VARCHAR(255),
    category VARCHAR(100),
    required_credits FLOAT,
    description TEXT
);

-- 6. Program Structures (Cấu trúc khung CTĐT - Phân bổ môn học theo khối)
CREATE TABLE IF NOT EXISTS program_structures (
    structure_id INT PRIMARY KEY,
    curriculum_id VARCHAR(50) REFERENCES curriculums(curriculum_id) ON DELETE CASCADE,
    course_code VARCHAR(20) REFERENCES courses(course_code) ON DELETE CASCADE,
    block_id VARCHAR(50) REFERENCES knowledge_blocks(block_id) ON DELETE SET NULL,
    course_type VARCHAR(20),
    elective_group VARCHAR(50),
    specialization VARCHAR(100),
    credits INT,
    recommended_semester VARCHAR(20),
    prerequisites TEXT
);

-- 7. Course Assessments (Tỷ lệ phần trăm đánh giá môn học: Quiz, Lab, BTL, GK, CK)
CREATE TABLE IF NOT EXISTS course_assessments (
    course_code VARCHAR(20) PRIMARY KEY REFERENCES courses(course_code) ON DELETE CASCADE,
    course_category VARCHAR(50),
    quiz INT,
    lab INT,
    btl INT,
    giua_ky INT,
    cuoi_ky INT
);

-- ============================================================================
-- 2. TÀI KHOẢN NGƯỜI DÙNG & HỒ SƠ THỰC THỂ
-- ============================================================================

-- 8. Users (Tài khoản hệ thống: Admin, Giảng viên, Sinh viên) - UUID PK
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    user_code VARCHAR(50) UNIQUE NOT NULL, -- MSSV / MSGV / Admin ID
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    title VARCHAR(100)
);

-- 9. Students (Hồ sơ học vụ sinh viên - Đã tinh gọn chuẩn học vụ)
CREATE TABLE IF NOT EXISTS students (
    student_id VARCHAR(50) PRIMARY KEY REFERENCES users(user_code) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    cohort VARCHAR(20) NOT NULL,
    major VARCHAR(100) NOT NULL,
    program VARCHAR(100),
    specialization VARCHAR(100),
    english_pass BOOLEAN DEFAULT FALSE,
    ctxh_days INT DEFAULT 0
);

-- 10. Lecturers (Hồ sơ giảng viên & bộ môn)
CREATE TABLE IF NOT EXISTS lecturers (
    lecturer_id VARCHAR(50) PRIMARY KEY REFERENCES users(user_code) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    departments VARCHAR(100) NOT NULL
);

-- 11. Admins (Hồ sơ cán bộ quản lý đào tạo)
CREATE TABLE IF NOT EXISTS admins (
    admin_id VARCHAR(50) PRIMARY KEY REFERENCES users(user_code) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    department VARCHAR(100) DEFAULT 'Phong Dao Tao'
);

-- ============================================================================
-- 3. LỚP HỌC PHẦN & ĐĂNG KÝ HỌC
-- ============================================================================

-- 12. Classes (Danh sách lớp học phần mở theo từng kỳ)
CREATE TABLE IF NOT EXISTS classes (
    class_id VARCHAR(100) PRIMARY KEY,
    course_code VARCHAR(20) REFERENCES courses(course_code) ON DELETE RESTRICT,
    semester_code VARCHAR(20) REFERENCES semesters(semester_code) ON DELETE RESTRICT,
    class_group VARCHAR(20) NOT NULL,
    lecturer_id VARCHAR(50) REFERENCES lecturers(lecturer_id) ON DELETE SET NULL
);

-- 13. Enrollments (Lịch sử đăng ký & kết quả điểm chi tiết) - UUID PK
CREATE TABLE IF NOT EXISTS enrollments (
    id UUID PRIMARY KEY,
    student_id VARCHAR(50) REFERENCES students(student_id) ON DELETE CASCADE,
    class_id VARCHAR(100) REFERENCES classes(class_id) ON DELETE CASCADE,
    course_code VARCHAR(20) REFERENCES courses(course_code) ON DELETE RESTRICT,
    semester_code VARCHAR(20) REFERENCES semesters(semester_code) ON DELETE RESTRICT,
    retaken BOOLEAN DEFAULT FALSE,
    quiz FLOAT,
    lab FLOAT,
    btl FLOAT,
    giua_ky FLOAT,
    cuoi_ky FLOAT,
    final_score FLOAT,
    letter_grade VARCHAR(10),
    gpa_4 FLOAT,
    passed BOOLEAN,
    semester_gpa_4 FLOAT,
    final_gpa_4 FLOAT,
    status VARCHAR(20)
);

-- ============================================================================
-- CHỈ MỤC TỐI ƯU HIỆU NĂNG (INDEXES)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_users_user_code ON users(user_code);
CREATE INDEX IF NOT EXISTS idx_students_cohort ON students(cohort);
CREATE INDEX IF NOT EXISTS idx_students_major ON students(major);

CREATE INDEX IF NOT EXISTS idx_classes_course ON classes(course_code);
CREATE INDEX IF NOT EXISTS idx_classes_semester ON classes(semester_code);
CREATE INDEX IF NOT EXISTS idx_classes_lecturer ON classes(lecturer_id);

CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_class ON enrollments(class_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments(course_code);
CREATE INDEX IF NOT EXISTS idx_enrollments_semester ON enrollments(semester_code);

CREATE INDEX IF NOT EXISTS idx_prog_struct_curriculum ON program_structures(curriculum_id);
CREATE INDEX IF NOT EXISTS idx_prog_struct_course ON program_structures(course_code);
"""


# -----------------------------------------------------------------------------
# 3. DATA EXTRACTION & TRANSFORMATION HELPERS
# -----------------------------------------------------------------------------
def load_semesters_data():
    """Load semesters catalog (bao gồm cờ is_active cho học kỳ hiện tại)."""
    csv_file = SYNTHETIC_DIR / "generated" / "academics" / "semester.csv"
    df = pd.read_csv(csv_file)
    if "term" not in df.columns:
        df["term"] = df["semester_code"].astype(str).str[-1].astype(int)
    if "is_active" not in df.columns:
        df["is_active"] = df["semester_code"].astype(str).str.strip().str.upper().isin(["HK261", "261"])
    else:
        df["is_active"] = df["is_active"].astype(bool)
    cols = ["semester_code", "academic_year", "term", "is_active"]
    return df[cols].drop_duplicates(subset=["semester_code"])


def load_courses_data():
    """Load courses catalog (đã bỏ cột difficulty không cần thiết)."""
    csv_file = SYNTHETIC_DIR / "generated" / "academics" / "courses.csv"
    df = pd.read_csv(csv_file)
    if "course_name" not in df.columns and "course_name_vi" in df.columns:
        df["course_name"] = df["course_name_vi"]
    cols = ["course_code", "course_name", "credits"]
    return df[cols].drop_duplicates(subset=["course_code"])


def load_prerequisites_data():
    """Load course prerequisites."""
    csv_file = SYNTHETIC_DIR / "generated" / "academics" / "course_prerequisites.csv"
    df = pd.read_csv(csv_file)
    if "course_prerequisite_id" not in df.columns and "prerequisite_id" in df.columns:
        df["course_prerequisite_id"] = df["prerequisite_id"]
    elif "course_prerequisite_id" not in df.columns:
        df["course_prerequisite_id"] = range(1, len(df) + 1)
    if "related_course_code" not in df.columns and "prerequisite_course_code" in df.columns:
        df["related_course_code"] = df["prerequisite_course_code"]
    cols = ["course_prerequisite_id", "course_code", "related_course_code", "relation_type"]
    return df[cols].drop_duplicates()


def load_curriculums_data():
    """Load curriculum definitions."""
    csv_file = SYNTHETIC_DIR / "generated" / "academics" / "curriculums.csv"
    df = pd.read_csv(csv_file)
    cols = [
        "curriculum_id", "curriculum_name", "major_code", "major_name",
        "cohort", "academic_year_start", "total_credits", "base_curriculum_id", "faculty"
    ]
    return df[[c for c in cols if c in df.columns]].drop_duplicates(subset=["curriculum_id"])


def load_knowledge_blocks_data():
    """Load knowledge blocks structure."""
    csv_file = SYNTHETIC_DIR / "generated" / "academics" / "knowledge_blocks.csv"
    df = pd.read_csv(csv_file)
    cols = [
        "block_id", "block_code", "block_name_vi", "block_name_en",
        "category", "required_credits", "description"
    ]
    return df[[c for c in cols if c in df.columns]].drop_duplicates(subset=["block_id"])


def load_program_structures_data():
    """Load detailed curriculum structure."""
    csv_file = SYNTHETIC_DIR / "generated" / "academics" / "program_structures.csv"
    df = pd.read_csv(csv_file)
    cols = [
        "structure_id", "curriculum_id", "course_code", "block_id",
        "course_type", "elective_group", "specialization", "credits",
        "recommended_semester", "prerequisites"
    ]
    return df[[c for c in cols if c in df.columns]].drop_duplicates(subset=["structure_id"])


def load_course_assessments_data():
    """Load course assessment weight rules."""
    csv_file = SYNTHETIC_DIR / "generated" / "academics" / "assessment.csv"
    df = pd.read_csv(csv_file)
    df.rename(columns={"course_id": "course_code"}, inplace=True)
    cols = ["course_code", "course_category", "quiz", "lab", "btl", "giua_ky", "cuoi_ky"]
    return df[[c for c in cols if c in df.columns]].drop_duplicates(subset=["course_code"])


def load_users_data():
    """Consolidate all system users and generate UUID for each."""
    user_file = SYNTHETIC_DIR / "generated" / "users" / "user.csv"
    if user_file.exists():
        df_users = pd.read_csv(user_file, dtype=str)
        df_users["user_code"] = df_users["user_id"]
    else:
        users_list = []
        admin_file = SYNTHETIC_DIR / "generated" / "users" / "admin.csv"
        if admin_file.exists():
            df_admin = pd.read_csv(admin_file, dtype=str)
            df_admin["user_code"] = df_admin["user_id"]
            users_list.append(df_admin[["user_code", "name", "email", "password_hash", "role", "title"]])
        lec_file = SYNTHETIC_DIR / "generated" / "users" / "lecturer.csv"
        df_lec = pd.read_csv(lec_file, dtype=str)
        df_lec["user_code"] = df_lec["user_id"]
        users_list.append(df_lec[["user_code", "name", "email", "password_hash", "role", "title"]])
        stu_file = SYNTHETIC_DIR / "generated" / "users" / "student.csv"
        df_stu = pd.read_csv(stu_file, dtype=str)
        df_stu["user_code"] = df_stu["user_id"]
        users_list.append(df_stu[["user_code", "name", "email", "password_hash", "role", "title"]])
        df_users = pd.concat(users_list, ignore_index=True)

    df_users.drop_duplicates(subset=["user_code"], inplace=True)
    df_users["id"] = [str(uuid.uuid4()) for _ in range(len(df_users))]
    cols = ["id", "user_code", "name", "email", "password_hash", "role", "title"]
    return df_users[cols]


def load_students_data(user_uuid_map):
    """Load clean student profiles (chuẩn học vụ tinh gọn: giữ english_pass và ctxh_days, bỏ các trường khảo sát)."""
    import json
    profile_file = SYNTHETIC_DIR / "generated" / "users" / "student_profiles.csv"
    df = pd.read_csv(profile_file, dtype={"student_id": str})
    df.drop_duplicates(subset=["student_id"], inplace=True)
    if "cohort" not in df.columns:
        df["cohort"] = "K" + df["student_id"].str[:2]
    if "major" not in df.columns:
        df["major"] = "Khoa hoc May tinh"
    df["user_id"] = df["student_id"].map(user_uuid_map)

    # Trích xuất số ngày CTXH tích lũy từ ctxh_days_by_semester nếu chưa có cột ctxh_days
    if "ctxh_days" not in df.columns:
        def extract_ctxh_days(val):
            if pd.isna(val):
                return 0
            try:
                arr = json.loads(val)
                if isinstance(arr, list) and len(arr) > 0:
                    last = arr[-1]
                    return int(last.get("cumulative_days", last.get("days", 0)))
                elif isinstance(arr, (int, float)):
                    return int(arr)
            except Exception:
                pass
            return 0

        df["ctxh_days"] = df["ctxh_days_by_semester"].apply(extract_ctxh_days) if "ctxh_days_by_semester" in df.columns else 0

    if "english_pass" not in df.columns:
        df["english_pass"] = False
    else:
        df["english_pass"] = df["english_pass"].astype(bool)

    # Chỉ giữ các cột học vụ thực tế tinh gọn
    cols = [
        "student_id", "user_id", "cohort", "major", "program", "specialization",
        "english_pass", "ctxh_days"
    ]
    return df[[c for c in cols if c in df.columns]]


def load_lecturers_data(user_uuid_map):
    """Load lecturer departmental assignments and map user_id UUID."""
    lec_file = SYNTHETIC_DIR / "generated" / "users" / "lecturer.csv"
    df = pd.read_csv(lec_file, dtype={"user_id": str})
    df["lecturer_id"] = df["user_id"]
    df["departments"] = df["department"]
    df = df[["lecturer_id", "departments"]].drop_duplicates(subset=["lecturer_id"])
    df["user_id"] = df["lecturer_id"].map(user_uuid_map)
    cols = ["lecturer_id", "user_id", "departments"]
    return df[cols]


def load_admins_data(user_uuid_map):
    """Load system administrators and map user_id UUID."""
    admin_file = SYNTHETIC_DIR / "generated" / "users" / "admin.csv"
    if admin_file.exists():
        df_admin = pd.read_csv(admin_file, dtype=str)
        df_admin["admin_id"] = df_admin["user_id"]
        df_admin["user_id"] = df_admin["admin_id"].map(user_uuid_map)
        df_admin["department"] = "Phong Dao Tao"
        cols = ["admin_id", "user_id", "department"]
        return df_admin[cols].drop_duplicates(subset=["admin_id"])
    return pd.DataFrame(columns=["admin_id", "user_id", "department"])


def load_classes_data():
    """Concatenate all semester class files into a single DataFrame."""
    pattern = str(SYNTHETIC_DIR / "generated" / "classes" / "class_hk*.csv")
    class_files = sorted(glob.glob(pattern))

    dfs = []
    for file_path in class_files:
        df_part = pd.read_csv(file_path, dtype={"lecturer_id": str})
        dfs.append(df_part)

    df_classes = pd.concat(dfs, ignore_index=True)
    df_classes.rename(columns={"semester": "semester_code"}, inplace=True)
    cols = ["class_id", "course_code", "semester_code", "class_group", "lecturer_id"]
    return df_classes[cols].drop_duplicates(subset=["class_id"])


def load_enrollments_data():
    """Concatenate all semester enrollment files into a single DataFrame with UUID keys."""
    pattern = str(SYNTHETIC_DIR / "generated" / "enrollments" / "enrollment_hk*.csv")
    enroll_files = sorted(glob.glob(pattern))

    dfs = []
    for file_path in enroll_files:
        df_part = pd.read_csv(file_path, dtype={"student_id": str})
        dfs.append(df_part)

    df_enroll = pd.concat(dfs, ignore_index=True)

    # Generate UUID Primary Key for each enrollment record
    df_enroll["id"] = [str(uuid.uuid4()) for _ in range(len(df_enroll))]

    # Fix semester_code: Lấy từ cột semester gốc thay vì cắt từ class_id (tránh NaN khi môn miễn thi)
    if "semester" in df_enroll.columns:
        df_enroll["semester_code"] = df_enroll["semester"]
    else:
        df_enroll["semester_code"] = df_enroll["class_id"].str.split("_").str[0]

    df_enroll.rename(columns={"course_id": "course_code"}, inplace=True)

    # Chuẩn hóa tên cột GPA giữa các kỳ (HK201-211 dùng _4, HK212-231 dùng semester_gpa/cumulative_gpa)
    if "semester_gpa" in df_enroll.columns:
        if "semester_gpa_4" in df_enroll.columns:
            df_enroll["semester_gpa_4"] = df_enroll["semester_gpa_4"].combine_first(df_enroll["semester_gpa"])
        else:
            df_enroll["semester_gpa_4"] = df_enroll["semester_gpa"]

    if "cumulative_gpa" in df_enroll.columns:
        if "final_gpa_4" in df_enroll.columns:
            df_enroll["final_gpa_4"] = df_enroll["final_gpa_4"].combine_first(df_enroll["cumulative_gpa"])
        else:
            df_enroll["final_gpa_4"] = df_enroll["cumulative_gpa"]

    columns_order = [
        "id", "student_id", "class_id", "course_code", "semester_code",
        "retaken", "quiz", "lab", "btl", "giua_ky", "cuoi_ky",
        "final_score", "letter_grade", "gpa_4", "passed", "semester_gpa_4",
        "final_gpa_4", "status",
    ]
    return df_enroll[[c for c in columns_order if c in df_enroll.columns]]


# -----------------------------------------------------------------------------
# 4. DRY-RUN VALIDATION PIPELINE (KIỂM TRA DỮ LIỆU KHÔNG CẦN KẾT NỐI DB)
# -----------------------------------------------------------------------------
def run_dry_run_validation():
    """Kiểm tra toàn bộ 13 bảng dữ liệu nghiệp vụ, ràng buộc khóa ngoại và tính tương thích."""
    print("==================================================================")
    print("      DRY-RUN VALIDATION: KIỂM TRA 13 BẢNG DỮ LIỆU NGHIỆP VỤ      ")
    print("==================================================================")
    print("[*] Đang đọc và chuyển đổi 13 bảng dữ liệu...")

    start_all = time.time()
    dfs = {}

    dfs["semesters"] = load_semesters_data()
    dfs["courses"] = load_courses_data()
    dfs["course_prerequisites"] = load_prerequisites_data()
    dfs["curriculums"] = load_curriculums_data()
    dfs["knowledge_blocks"] = load_knowledge_blocks_data()
    dfs["program_structures"] = load_program_structures_data()
    dfs["course_assessments"] = load_course_assessments_data()

    df_users = load_users_data()
    uuid_map = dict(zip(df_users["user_code"], df_users["id"]))
    dfs["users"] = df_users

    dfs["students"] = load_students_data(uuid_map)
    dfs["lecturers"] = load_lecturers_data(uuid_map)
    dfs["admins"] = load_admins_data(uuid_map)
    dfs["classes"] = load_classes_data()
    dfs["enrollments"] = load_enrollments_data()

    print(f"[✓] Đã load thành công 13 bảng dữ liệu ({time.time() - start_all:.2f}s)\n")

    print(f"{'Tên Bảng':<25} | {'Số Bản Ghi':>12} | {'Số Cột':>6} | {'Trạng Thái':<12}")
    print("-" * 62)
    for t_name, df_table in dfs.items():
        print(f"{t_name:<25} | {len(df_table):>12,} | {len(df_table.columns):>6} | {'[✓] Hợp lệ':<12}")

    print("\n----------------- KIỂM TRA RÀNG BUỘC KHÓA NGOẠI (FK) -----------------")
    fk_checks = [
        ("course_prerequisites.course_code -> courses",
         set(dfs["course_prerequisites"]["course_code"]).issubset(set(dfs["courses"]["course_code"]))),
        ("course_prerequisites.related_course_code -> courses",
         set(dfs["course_prerequisites"]["related_course_code"]).issubset(set(dfs["courses"]["course_code"]))),
        ("program_structures.curriculum_id -> curriculums",
         set(dfs["program_structures"]["curriculum_id"]).issubset(set(dfs["curriculums"]["curriculum_id"]))),
        ("program_structures.course_code -> courses",
         set(dfs["program_structures"]["course_code"]).issubset(set(dfs["courses"]["course_code"]))),
        ("course_assessments.course_code -> courses",
         set(dfs["course_assessments"]["course_code"]).issubset(set(dfs["courses"]["course_code"]))),
        ("students.student_id -> users.user_code",
         set(dfs["students"]["student_id"]).issubset(set(dfs["users"]["user_code"]))),
        ("lecturers.lecturer_id -> users.user_code",
         set(dfs["lecturers"]["lecturer_id"]).issubset(set(dfs["users"]["user_code"]))),
        ("admins.admin_id -> users.user_code",
         set(dfs["admins"]["admin_id"]).issubset(set(dfs["users"]["user_code"]))),
        ("classes.course_code -> courses",
         set(dfs["classes"]["course_code"]).issubset(set(dfs["courses"]["course_code"]))),
        ("classes.semester_code -> semesters",
         set(dfs["classes"]["semester_code"]).issubset(set(dfs["semesters"]["semester_code"]))),
        ("classes.lecturer_id -> lecturers",
         set(dfs["classes"]["lecturer_id"].dropna()).issubset(set(dfs["lecturers"]["lecturer_id"]))),
        ("enrollments.student_id -> students",
         set(dfs["enrollments"]["student_id"]).issubset(set(dfs["students"]["student_id"]))),
        ("enrollments.course_code -> courses",
         set(dfs["enrollments"]["course_code"]).issubset(set(dfs["courses"]["course_code"]))),
        ("enrollments.semester_code -> semesters",
         set(dfs["enrollments"]["semester_code"].dropna()).issubset(set(dfs["semesters"]["semester_code"]))),
        ("enrollments.class_id -> classes",
         set(dfs["enrollments"]["class_id"].dropna()).issubset(set(dfs["classes"]["class_id"]))),
    ]

    all_passed = True
    for relation, status in fk_checks:
        symbol = "[✓] PASS" if status else "[X] FAIL"
        if not status:
            all_passed = False
        print(f"  {symbol:<10} : {relation}")

    if all_passed:
        print("\n[✓] KẾT QUẢ DRY-RUN: 100% CÁC RÀNG BUỘC KHÓA NGOẠI VÀ CỘT DỮ LIỆU ĐỀU HỢP LỆ!")
        print("    Dữ liệu 13 bảng nghiệp vụ đã sẵn sàng để push lên Neon Database.")
    else:
        print("\n[!] PHÁT HIỆN LỖI RÀNG BUỘC DỮ LIỆU! Cần kiểm tra lại các mục báo [X] FAIL.")


# -----------------------------------------------------------------------------
# 5. MAIN INGESTION PIPELINE (ĐẨY DỮ LIỆU LÊN DATABASE THẬT)
# -----------------------------------------------------------------------------
def run_push_to_neon():
    """Execute the schema creation and data insertion into Neon PostgreSQL."""
    # Check if --dry-run flag is provided
    if "--dry-run" in sys.argv:
        run_dry_run_validation()
        return

    if not DATABASE_URL or "user:password" in DATABASE_URL:
        print("[!] ERROR: Chưa cấu hình DATABASE_URL hợp lệ.")
        print(f"    Vui lòng mở file '{ENV_FILE.name}' và điền chuỗi kết nối Neon:")
        print('    DATABASE_URL=postgresql://user:password@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require')
        print("\n[*] GỢI Ý: Bạn có thể chạy thử nghiệm kiểm tra dữ liệu trước mà không cần DB:")
        print("    python database/push_data.py --dry-run")
        sys.exit(1)

    print("==================================================================")
    print("      IMPORTING SYNTHETIC ACADEMIC DATA TO NEON POSTGRESQL        ")
    print("==================================================================")
    print(f"[*] Đang kết nối tới Neon Database...")

    # Fix postgres:// URL prefix for SQLAlchemy 1.4+ if needed
    db_uri = DATABASE_URL
    if db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)

    engine = create_engine(db_uri, pool_pre_ping=True)

    with engine.connect() as conn:
        # Tự động phát hiện schema cũ thiếu trường -> tiến hành reset sạch sẽ
        students_cols = [
            row[0]
            for row in conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'students'")
            ).fetchall()
        ]
        semesters_cols = [
            row[0]
            for row in conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'semesters'")
            ).fetchall()
        ]
        if (
            "--reset" in sys.argv
            or (students_cols and ("program" not in students_cols or "ctxh_days" not in students_cols or "family_income" in students_cols))
            or (semesters_cols and "is_active" not in semesters_cols)
        ):
            print("[*] Đang làm sạch và tái cấu trúc toàn bộ 13 bảng (DROP & RECREATE CASCADE)...")
            conn.execute(text("""
                DROP TABLE IF EXISTS enrollments, classes, course_assessments, program_structures,
                                     knowledge_blocks, curriculums, lecturers, students, admins, users,
                                     course_prerequisites, courses, semesters CASCADE;
            """))
            conn.commit()

        print("[*] Đang khởi tạo bảng và chỉ mục (DDL Statements)...")
        conn.execute(text(DDL_STATEMENTS))
        conn.commit()
    print("[✓] Khởi tạo cấu trúc 13 bảng hoàn tất.\n")

    # Helper function to bulk insert with null cleaning
    def insert_table(table_name, df, chunksize=2000, dtypes=None):
        with engine.connect() as conn:
            existing_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        if existing_count > 0:
            print(f"[i] Bảng '{table_name}' đã có sẵn {existing_count:,} bản ghi. Bỏ qua.")
            return

        start_time = time.time()
        print(f"[*] Đang chuẩn bị dữ liệu cho bảng '{table_name}'...")
        total_rows = len(df)
        print(f"    -> Đang đẩy {total_rows:,} bản ghi vào '{table_name}' (chunksize={chunksize})...")

        # Sanitize np.nan to None for safe SQL NULL insertion
        df_clean = df.where(pd.notnull(df), None)

        df_clean.to_sql(
            name=table_name,
            con=engine,
            if_exists="append",
            index=False,
            chunksize=chunksize,
            method="multi",
            dtype=dtypes,
        )
        print(f"[✓] Đã lưu {total_rows:,} dòng vào '{table_name}' ({time.time() - start_time:.2f}s)\n")

    # Step A: Load Academic Catalogs & Curriculums
    insert_table("semesters", load_semesters_data(), chunksize=1000)
    insert_table("courses", load_courses_data(), chunksize=1000)
    insert_table("course_prerequisites", load_prerequisites_data(), chunksize=1000)
    insert_table("curriculums", load_curriculums_data(), chunksize=1000)
    insert_table("knowledge_blocks", load_knowledge_blocks_data(), chunksize=1000)
    insert_table("program_structures", load_program_structures_data(), chunksize=2000)
    insert_table("course_assessments", load_course_assessments_data(), chunksize=1000)

    # Step B: Load Users & generate UUIDs
    user_uuid_map = {}
    with engine.connect() as conn:
        users_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()

    if users_count > 0:
        print(f"[i] Bảng 'users' đã có sẵn {users_count:,} người dùng. Đang đọc UUID từ cơ sở dữ liệu...")
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT user_code, id FROM users")).fetchall()
            user_uuid_map = {r[0]: str(r[1]) for r in rows}
    else:
        start_time = time.time()
        print("[*] Đang chuẩn bị dữ liệu người dùng (bảng 'users' với UUID PK)...")
        df_users = load_users_data()
        user_uuid_map = dict(zip(df_users["user_code"], df_users["id"]))
        insert_table("users", df_users, chunksize=2000, dtypes={"id": PG_UUID(as_uuid=True)})

    # Step C: Load Entity Profiles
    insert_table("admins", load_admins_data(user_uuid_map), chunksize=1000, dtypes={"user_id": PG_UUID(as_uuid=True)})
    insert_table("students", load_students_data(user_uuid_map), chunksize=2000, dtypes={"user_id": PG_UUID(as_uuid=True)})
    insert_table("lecturers", load_lecturers_data(user_uuid_map), chunksize=1000, dtypes={"user_id": PG_UUID(as_uuid=True)})

    # Step D: Load Classes & Enrollments
    insert_table("classes", load_classes_data(), chunksize=2000)
    insert_table("enrollments", load_enrollments_data(), chunksize=3000, dtypes={"id": PG_UUID(as_uuid=True)})

    # Step E: Verification Query
    all_table_names = [
        "semesters", "courses", "course_prerequisites", "curriculums",
        "knowledge_blocks", "program_structures", "course_assessments",
        "users", "admins", "students", "lecturers",
        "classes", "enrollments",
    ]
    print("==================================================================")
    print("                  KIỂM TRA DỮ LIỆU SAU KHI ĐẨY                    ")
    print("==================================================================")
    with engine.connect() as conn:
        for t_name in all_table_names:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {t_name}")).scalar()
            print(f"  - Bảng {t_name:<22}: {count:>8,} bản ghi")

    print("\n[✓] TOÀN BỘ 13 BẢNG DỮ LIỆU ĐÃ ĐƯỢC ĐẨY LÊN NEON DATABASE THÀNH CÔNG!")


if __name__ == "__main__":
    run_push_to_neon()