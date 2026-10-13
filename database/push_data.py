"""Script to import synthetic academic data into Neon PostgreSQL Database.

This script creates a normalized 8-table relational schema with UUID Primary Keys
for users and enrollments, and bulk inserts synthetic data generated for 14 cohorts
(K13-K26) across 27 semesters (HK131-HK261).

Usage:
    export DATABASE_URL="postgresql://user:password@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require"
    python database/push_data.py
"""

import glob
import os
import sys
import time
import uuid
from pathlib import Path
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
# 2. SCHEMA DEFINITION (DDL)
# -----------------------------------------------------------------------------
DDL_STATEMENTS = """
-- 1. Semesters (Danh mục học kỳ)
CREATE TABLE IF NOT EXISTS semesters (
    semester_code VARCHAR(20) PRIMARY KEY,
    academic_year VARCHAR(20) NOT NULL,
    term INT NOT NULL
);

-- 2. Courses (Danh mục môn học)
CREATE TABLE IF NOT EXISTS courses (
    course_code VARCHAR(20) PRIMARY KEY,
    course_name VARCHAR(255) NOT NULL,
    credits INT NOT NULL,
    difficulty FLOAT
);

-- 3. Course Prerequisites (Môn tiên quyết)
CREATE TABLE IF NOT EXISTS course_prerequisites (
    course_prerequisite_id INT PRIMARY KEY,
    course_code VARCHAR(20) REFERENCES courses(course_code) ON DELETE CASCADE,
    related_course_code VARCHAR(20) REFERENCES courses(course_code) ON DELETE CASCADE,
    relation_type VARCHAR(10) NOT NULL
);

-- 4. Users (Tài khoản người dùng: Admin, Giảng viên, Sinh viên) - UUID Primary Key
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    user_code VARCHAR(50) UNIQUE NOT NULL, -- MSSV / MSGV / Admin ID
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    title VARCHAR(100)
);

-- 5. Students (Hồ sơ học vụ & đặc trưng sinh viên)
CREATE TABLE IF NOT EXISTS students (
    student_id VARCHAR(50) PRIMARY KEY REFERENCES users(user_code) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    cohort VARCHAR(20) NOT NULL,
    major VARCHAR(100) NOT NULL,
    family_income VARCHAR(50),
    financial_pressure VARCHAR(50),
    living_condition VARCHAR(50),
    discipline INT,
    motivation INT,
    stress INT,
    social_activity INT,
    academic_level INT,
    math_level INT,
    english_level INT,
    english_pass BOOLEAN DEFAULT FALSE,
    english_eligibility_by_semester TEXT,
    ctxh_days_by_semester TEXT,
    voluntary_dropout_semester VARCHAR(20),
    voluntary_dropout_reason VARCHAR(255),
    base_score FLOAT,
    early_graduation_candidate BOOLEAN DEFAULT FALSE
);

-- 6. Lecturers (Hồ sơ giảng viên & bộ môn phụ trách)
CREATE TABLE IF NOT EXISTS lecturers (
    lecturer_id VARCHAR(50) PRIMARY KEY REFERENCES users(user_code) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    departments VARCHAR(100) NOT NULL
);

-- 7. Admins (Hồ sơ quản trị viên hệ thống)
CREATE TABLE IF NOT EXISTS admins (
    admin_id VARCHAR(50) PRIMARY KEY REFERENCES users(user_code) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    department VARCHAR(100) DEFAULT 'Phong Dao Tao'
);

-- 8. Classes (Danh sách lớp học phần mở theo kỳ)
CREATE TABLE IF NOT EXISTS classes (
    class_id VARCHAR(100) PRIMARY KEY,
    course_code VARCHAR(20) REFERENCES courses(course_code) ON DELETE RESTRICT,
    semester_code VARCHAR(20) REFERENCES semesters(semester_code) ON DELETE RESTRICT,
    class_group VARCHAR(20) NOT NULL,
    lecturer_id VARCHAR(50) REFERENCES lecturers(lecturer_id) ON DELETE SET NULL
);

-- 9. Enrollments (Lịch sử đăng ký & điểm chi tiết) - UUID Primary Key
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

-- Indexes for high-performance querying
CREATE INDEX IF NOT EXISTS idx_users_user_code ON users(user_code);
CREATE INDEX IF NOT EXISTS idx_classes_course ON classes(course_code);
CREATE INDEX IF NOT EXISTS idx_classes_semester ON classes(semester_code);
CREATE INDEX IF NOT EXISTS idx_classes_lecturer ON classes(lecturer_id);

CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_class ON enrollments(class_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments(course_code);
CREATE INDEX IF NOT EXISTS idx_enrollments_semester ON enrollments(semester_code);
"""


# -----------------------------------------------------------------------------
# 3. DATA EXTRACTION & TRANSFORMATION HELPERS
# -----------------------------------------------------------------------------
def load_semesters_data():
    """Load semesters data."""
    csv_file = SYNTHETIC_DIR / "data" / "academic" / "semester.csv"
    df = pd.read_csv(csv_file)
    df = df[["semester_code", "academic_year", "term"]].drop_duplicates(subset=["semester_code"])
    return df


def load_courses_data():
    """Load courses catalog."""
    csv_file = SYNTHETIC_DIR / "data" / "catalog" / "course.csv"
    df = pd.read_csv(csv_file)
    df = df[["course_code", "course_name", "credits", "difficulty"]].drop_duplicates(subset=["course_code"])
    return df


def load_prerequisites_data():
    """Load course prerequisites."""
    csv_file = SYNTHETIC_DIR / "data" / "catalog" / "course_prerequisite.csv"
    df = pd.read_csv(csv_file)
    df = df[["course_prerequisite_id", "course_code", "related_course_code", "relation_type"]].drop_duplicates()
    return df


def load_users_data():
    """Consolidate all system users and generate UUID for each."""
    users_list = []

    # 1. Admins
    admin_file = SYNTHETIC_DIR / "admin.csv"
    if admin_file.exists():
        df_admin = pd.read_csv(admin_file, dtype=str)
        df_admin["user_code"] = df_admin["user_id"]
        users_list.append(df_admin[["user_code", "name", "email", "password_hash", "role", "title"]])

    # 2. Lecturers
    lec_file = SYNTHETIC_DIR / "data" / "people" / "lecture.csv"
    df_lec = pd.read_csv(lec_file, dtype=str)
    df_lec["user_code"] = df_lec["lecture_id"]
    df_lec["password_hash"] = "hashed_pass_lecturer_" + df_lec["user_code"]
    df_lec["role"] = "lecturer"
    users_list.append(df_lec[["user_code", "name", "email", "password_hash", "role", "title"]])

    # 3. Students
    stu_file = SYNTHETIC_DIR / "data" / "people" / "student.csv"
    df_stu = pd.read_csv(stu_file, dtype=str)
    df_stu["user_code"] = df_stu["student_id"]
    df_stu["password_hash"] = "hashed_pass_student_" + df_stu["user_code"]
    df_stu["role"] = "student"
    users_list.append(df_stu[["user_code", "name", "email", "password_hash", "role", "title"]])

    df_users = pd.concat(users_list, ignore_index=True)
    df_users.drop_duplicates(subset=["user_code"], inplace=True)
    # Generate UUID Primary Key
    df_users["id"] = [str(uuid.uuid4()) for _ in range(len(df_users))]

    cols = ["id", "user_code", "name", "email", "password_hash", "role", "title"]
    return df_users[cols]


def load_students_data(user_uuid_map):
    """Load detailed student profiles and map user_id UUID."""
    stu_file = SYNTHETIC_DIR / "data" / "people" / "student.csv"
    profile_file = SYNTHETIC_DIR / "generated" / "student_profile" / "student_profiles.csv"

    df_stu = pd.read_csv(stu_file, dtype=str)
    df_prof = pd.read_csv(profile_file, dtype={"student_id": str})

    df = pd.merge(
        df_stu[["student_id", "cohort", "major"]],
        df_prof,
        on="student_id",
        how="inner",
    )
    df.drop(columns=["name"], errors="ignore", inplace=True)
    df.drop_duplicates(subset=["student_id"], inplace=True)
    # Link UUID
    df["user_id"] = df["student_id"].map(user_uuid_map)
    return df


def load_lecturers_data(user_uuid_map):
    """Load lecturer departmental assignments and map user_id UUID."""
    lec_dep_file = SYNTHETIC_DIR / "data" / "people" / "lecturer_for_class.csv"
    df = pd.read_csv(lec_dep_file, dtype={"lecturer_id": str})
    df = df[["lecturer_id", "departments"]].drop_duplicates(subset=["lecturer_id"])
    # Link UUID
    df["user_id"] = df["lecturer_id"].map(user_uuid_map)
    return df


def load_admins_data(user_uuid_map):
    """Load system administrators and map user_id UUID."""
    admin_file = SYNTHETIC_DIR / "admin.csv"
    if admin_file.exists():
        df_admin = pd.read_csv(admin_file, dtype=str)
        df_admin["admin_id"] = df_admin["user_id"]
        df_admin["user_id"] = df_admin["admin_id"].map(user_uuid_map)
        df_admin["department"] = "Phong Dao Tao"
        cols = ["admin_id", "user_id", "department"]
        return df_admin[cols].drop_duplicates(subset=["admin_id"])
    return pd.DataFrame(columns=["admin_id", "user_id", "department"])


def load_classes_data():
    """Concatenate all 27 semester class files into a single DataFrame."""
    pattern = str(SYNTHETIC_DIR / "generated" / "classes" / "class_hk*.csv")
    class_files = sorted(glob.glob(pattern))

    dfs = []
    for file_path in class_files:
        df_part = pd.read_csv(file_path, dtype={"lecturer_id": str})
        dfs.append(df_part)

    df_classes = pd.concat(dfs, ignore_index=True)
    df_classes.rename(columns={"semester": "semester_code"}, inplace=True)
    cols = ["class_id", "course_code", "semester_code", "class_group", "lecturer_id"]
    df_classes = df_classes[cols].drop_duplicates(subset=["class_id"])
    return df_classes


def load_enrollments_data():
    """Concatenate all 27 semester enrollment files into a single DataFrame with UUID keys."""
    pattern = str(SYNTHETIC_DIR / "generated" / "enrollments" / "enrollment_hk*.csv")
    enroll_files = sorted(glob.glob(pattern))

    dfs = []
    for file_path in enroll_files:
        df_part = pd.read_csv(file_path, dtype={"student_id": str})
        dfs.append(df_part)

    df_enroll = pd.concat(dfs, ignore_index=True)

    # Generate UUID Primary Key for each enrollment record
    df_enroll["id"] = [str(uuid.uuid4()) for _ in range(len(df_enroll))]
    df_enroll["semester_code"] = df_enroll["class_id"].str.split("_").str[0]
    df_enroll.rename(
        columns={
            "course_id": "course_code",
        },
        inplace=True,
    )

    columns_order = [
        "id", "student_id", "class_id", "course_code", "semester_code",
        "retaken", "quiz", "lab", "btl", "giua_ky", "cuoi_ky",
        "final_score", "letter_grade", "gpa_4", "passed", "semester_gpa_4",
        "final_gpa_4", "status",
    ]
    df_enroll = df_enroll[[c for c in columns_order if c in df_enroll.columns]]
    return df_enroll


# -----------------------------------------------------------------------------
# 4. MAIN INGESTION PIPELINE
# -----------------------------------------------------------------------------
def run_push_to_neon():
    """Execute the schema creation and data insertion into Neon PostgreSQL."""
    if not DATABASE_URL or "user:password" in DATABASE_URL:
        print("[!] ERROR: Chưa cấu hình DATABASE_URL hợp lệ.")
        print(f"    Vui lòng mở file '{ENV_FILE.name}' và điền chuỗi kết nối Neon:")
        print('    DATABASE_URL=postgresql://user:password@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require')
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
        # Check if classes or enrollments table contains old columns (course_name / lecturer_name / semester_index)
        classes_cols = [
            row[0]
            for row in conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'classes'")
            ).fetchall()
        ]
        enrollments_cols = [
            row[0]
            for row in conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'enrollments'")
            ).fetchall()
        ]
        if "course_name" in classes_cols or "lecturer_name" in classes_cols or "semester_index" in enrollments_cols:
            print("[*] Phát hiện schema cũ (course_name, lecturer_name hoặc semester_index). Đang cập nhật lại schema chuẩn...")
            conn.execute(text("DROP TABLE IF EXISTS enrollments CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS classes CASCADE;"))
            conn.commit()

        print("[*] Đang khởi tạo bảng và chỉ mục (DDL Statements)...")
        conn.execute(text(DDL_STATEMENTS))
        conn.commit()
    print("[✓] Khởi tạo cấu trúc bảng hoàn tất.\n")

    # Check if --reset flag is provided
    if "--reset" in sys.argv:
        print("[*] Phát hiện cờ --reset: Đang xóa sạch dữ liệu cũ trong các bảng (TRUNCATE)...")
        with engine.connect() as conn:
            conn.execute(text("""
                TRUNCATE TABLE enrollments, classes, lecturers, students, admins, users,
                               course_prerequisites, courses, semesters CASCADE;
            """))
            conn.commit()
        print("[✓] Đã làm trống toàn bộ bảng thành công.\n")

    # Step A: Load Reference Data
    ref_tables = [
        ("semesters", load_semesters_data, 1000),
        ("courses", load_courses_data, 1000),
        ("course_prerequisites", load_prerequisites_data, 1000),
    ]
    for table_name, loader_func, chunksize in ref_tables:
        with engine.connect() as conn:
            existing_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        if existing_count > 0:
            print(f"[i] Bảng '{table_name}' đã có sẵn {existing_count:,} bản ghi. Bỏ qua.")
            continue

        start_time = time.time()
        print(f"[*] Đang chuẩn bị dữ liệu cho bảng '{table_name}'...")
        df = loader_func()
        total_rows = len(df)
        print(f"    -> Đang đẩy {total_rows:,} bản ghi vào '{table_name}'...")
        df.to_sql(name=table_name, con=engine, if_exists="append", index=False, chunksize=chunksize, method="multi")
        print(f"[✓] Đã lưu {total_rows:,} dòng vào '{table_name}' ({time.time() - start_time:.2f}s)\n")

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
        print(f"    -> Đang đẩy {len(df_users):,} bản ghi vào 'users'...")
        df_users.to_sql(
            name="users",
            con=engine,
            if_exists="append",
            index=False,
            chunksize=2000,
            method="multi",
            dtype={"id": PG_UUID(as_uuid=True)},
        )
        print(f"[✓] Đã lưu {len(df_users):,} người dùng vào 'users' ({time.time() - start_time:.2f}s)\n")

    # Step C: Load Admins, Students, Lecturers, Classes, Enrollments
    # Use chunksize=2000 for enrollments (19 columns * 2000 = 38,000 params, safely under Postgres 65,535 limit)
    entity_tables = [
        ("admins", lambda: load_admins_data(user_uuid_map), 1000, {"user_id": PG_UUID(as_uuid=True)}),
        ("students", lambda: load_students_data(user_uuid_map), 2000, {"user_id": PG_UUID(as_uuid=True)}),
        ("lecturers", lambda: load_lecturers_data(user_uuid_map), 1000, {"user_id": PG_UUID(as_uuid=True)}),
        ("classes", load_classes_data, 2000, None),
        ("enrollments", load_enrollments_data, 2000, {"id": PG_UUID(as_uuid=True)}),
    ]
    for table_name, loader_func, chunksize, dtypes in entity_tables:
        with engine.connect() as conn:
            existing_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        if existing_count > 0:
            print(f"[i] Bảng '{table_name}' đã có sẵn {existing_count:,} bản ghi. Bỏ qua.")
            continue

        start_time = time.time()
        print(f"[*] Đang chuẩn bị dữ liệu cho bảng '{table_name}'...")
        df = loader_func()
        total_rows = len(df)
        print(f"    -> Đang đẩy {total_rows:,} bản ghi vào '{table_name}' (chunksize={chunksize})...")
        df.to_sql(
            name=table_name,
            con=engine,
            if_exists="append",
            index=False,
            chunksize=chunksize,
            method="multi",
            dtype=dtypes,
        )
        print(f"[✓] Đã lưu {total_rows:,} dòng vào '{table_name}' ({time.time() - start_time:.2f}s)\n")

    # Step D: Verification Query
    all_table_names = [
        "semesters", "courses", "course_prerequisites", "users",
        "admins", "students", "lecturers", "classes", "enrollments",
    ]
    print("==================================================================")
    print("                  KIỂM TRA DỮ LIỆU SAU KHI ĐẨY                    ")
    print("==================================================================")
    with engine.connect() as conn:
        for t_name in all_table_names:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {t_name}")).scalar()
            print(f"  - Bảng {t_name:<22}: {count:>8,} bản ghi")

    print("\n[✓] TOÀN BỘ DỮ LIỆU ĐÃ ĐƯỢC ĐẨY LÊN NEON DATABASE THÀNH CÔNG!")


if __name__ == "__main__":
    run_push_to_neon()