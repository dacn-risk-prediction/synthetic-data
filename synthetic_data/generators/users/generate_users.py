import csv
from contextlib import ExitStack
import json
import re
import secrets
import string
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple

from faker import Faker


# -------------------------------------------------------------------------
# DIRECTORY CONFIGURATION
# -------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT_DIR / "config" / "generator_config.json"
OUTPUT_DIR = ROOT_DIR / "generated" / "users"
OUTPUT_FILE = OUTPUT_DIR / "user.csv"
ROLE_OUTPUT_FILES = {
    "student": OUTPUT_DIR / "student.csv",
    "lecturer": OUTPUT_DIR / "lecturer.csv",
    "admin": OUTPUT_DIR / "admin.csv",
}

# -------------------------------------------------------------------------
# DEFAULT FALLBACKS (Nghiệp vụ - sẽ được ưu tiên đọc từ generator_config.json)
# -------------------------------------------------------------------------
DEFAULT_SEED = 20260923
INITIAL_STUDENT_COUNT_DEFAULT = 1500
STUDENT_INCREMENT_MIN_DEFAULT = 15
STUDENT_INCREMENT_MAX_DEFAULT = 50
COHORTS_DEFAULT = tuple(range(20, 27))

ADMIN_COUNT_DEFAULT = 10
LECTURER_TITLES_DEFAULT = ("bachelor", "master", "doctor", "associate_professor", "professor")
PROGRAMS_DEFAULT = ("standard", "advanced", "high-quality")
PROGRAM_WEIGHTS_DEFAULT = (0.60, 0.10, 0.30)

LECTURER_ALLOCATIONS_DEFAULT = [
    # 1. Khoa KH&KT Máy tính (55 GV)
    {"department": "Khoa Khoa học và Kỹ thuật Máy tính", "specialization": "Trí tuệ nhân tạo", "count": 13},
    {"department": "Khoa Khoa học và Kỹ thuật Máy tính", "specialization": "Công nghệ Phần mềm", "count": 13},
    {"department": "Khoa Khoa học và Kỹ thuật Máy tính", "specialization": "An ninh hệ thống và mạng", "count": 11},
    {"department": "Khoa Khoa học và Kỹ thuật Máy tính", "specialization": "Kỹ thuật Máy tính", "count": 10},
    {"department": "Khoa Khoa học và Kỹ thuật Máy tính", "specialization": "Công nghệ dữ liệu và dữ liệu lớn", "count": 8},
    # 2. Toán Ứng dụng (15 GV)
    {"department": "Khoa Khoa học Ứng dụng - Bộ môn Toán ứng dụng", "specialization": "Toán Ứng dụng & Thống kê", "count": 15},
    # 3. Trung tâm Ngoại ngữ (14 GV)
    {"department": "Trung tâm Ngoại ngữ", "specialization": "Tiếng Anh học thuật", "count": 14},
    # 4. Lý luận Chính trị (8 GV)
    {"department": "Khoa Khoa học Ứng dụng - Bộ môn Lý luận Chính trị", "specialization": "Lý luận Chính trị & Pháp luật", "count": 8},
    # 5. Vật lý & KHTN (8 GV)
    {"department": "Khoa Khoa học Ứng dụng - Bộ môn Vật lý ứng dụng", "specialization": "Vật lý & Khoa học Tự nhiên", "count": 8},
]

# -------------------------------------------------------------------------
# TECHNICAL CONSTANTS (Chi tiết giải thuật & Schema file - giữ lại trong code)
# -------------------------------------------------------------------------
MSSV_STEP = 7919
MSSV_MODULUS = 100_000

USER_HEADER = [
    "user_id", "name", "email", "password", "password_hash", "role", "title", "program", "department", "specialization",
]
ROLE_HEADERS = {
    "student": [
        "user_id", "name", "email", "password", "password_hash", "role", "title", "program", "specialization",
    ],
    "lecturer": [
        "user_id", "name", "email", "password", "password_hash", "role", "title", "department", "specialization",
    ],
    "admin": [
        "user_id", "name", "email", "password", "password_hash", "role", "title",
    ],
}

SURNAMES = (
    "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Võ", "Đặng",
    "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý", "Huỳnh", "Phan",
)
MIDDLE_NAMES = (
    "Văn", "Thị", "Hữu", "Minh", "Ngọc", "Quốc", "Thanh", "Gia",
    "Đức", "Hoàng", "Anh", "Phương", "Khánh", "Tuấn", "Quang",
)
GIVEN_NAMES = (
    "An", "Anh", "Bảo", "Châu", "Duy", "Hà", "Hải", "Hiếu", "Hùng",
    "Khang", "Khôi", "Lam", "Linh", "Long", "Mai", "Minh", "Nam",
    "Nhi", "Phát", "Phúc", "Quân", "Quang", "Thảo", "Trang", "Trinh",
    "Tú", "Tuấn", "Uyên", "Việt", "Yến",
)


def load_user_generation_config() -> Dict[str, Any]:
    """Load user generation configurations from generator_config.json with safe fallbacks."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("user_generation", {})
    except Exception as exc:
        print(f"Cảnh báo: Không thể nạp file cấu hình {CONFIG_FILE} ({exc}). Sử dụng cấu hình mặc định.")
        return {}


def normalize_name(name: str) -> str:
    """Normalize Vietnamese name to lowercase ASCII alphanumeric string for email creation."""
    name = name.replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFD", name)
    without_marks = "".join(
        character for character in normalized
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"[^a-z0-9]", "", without_marks.lower())


def generate_password() -> str:
    """Generate a random 12-character alphanumeric password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


def generate_vietnamese_name(fake: Faker) -> str:
    """Generate a natural full Vietnamese name from surname, middle name, and given name."""
    surname = fake.random_element(elements=SURNAMES)
    middle_name = fake.random_element(elements=MIDDLE_NAMES)
    given_name = fake.random_element(elements=GIVEN_NAMES)
    return f"{surname} {middle_name} {given_name}"


def generate_users() -> None:
    """Generate system users (Admins, Lecturers, Students) using configuration from generator_config.json."""
    user_cfg = load_user_generation_config()
    students_cfg = user_cfg.get("students", {})
    staff_cfg = user_cfg.get("staff", {})

    # 1. Khởi tạo Seed
    seed_value = user_cfg.get("seed", DEFAULT_SEED)
    fake = Faker("vi_VN")
    Faker.seed(seed_value)

    # 2. Cấu hình nhân sự (Staff)
    admin_count = staff_cfg.get("admin_count", ADMIN_COUNT_DEFAULT)
    lecturer_titles = tuple(staff_cfg.get("lecturer_titles", LECTURER_TITLES_DEFAULT))
    lecturer_allocations = staff_cfg.get("lecturer_allocations", LECTURER_ALLOCATIONS_DEFAULT)

    # 3. Cấu hình sinh viên (Students)
    cohorts = tuple(students_cfg.get("cohorts", COHORTS_DEFAULT))
    initial_student_count = students_cfg.get("initial_student_count", INITIAL_STUDENT_COUNT_DEFAULT)
    increment_min = students_cfg.get("increment_min", STUDENT_INCREMENT_MIN_DEFAULT)
    increment_max = students_cfg.get("increment_max", STUDENT_INCREMENT_MAX_DEFAULT)

    prog_weights_cfg = students_cfg.get("program_weights", {})
    if prog_weights_cfg:
        programs = tuple(prog_weights_cfg.keys())
        program_weights = tuple(prog_weights_cfg.values())
    else:
        programs = PROGRAMS_DEFAULT
        program_weights = PROGRAM_WEIGHTS_DEFAULT

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing_students = []
    if ROLE_OUTPUT_FILES["student"].exists():
        with ROLE_OUTPUT_FILES["student"].open("r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for r in reader:
                if r:
                    existing_students.append(r)

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as output, ExitStack() as role_outputs:
        writer = csv.writer(output)
        role_writers = {}
        for role, role_output_file in ROLE_OUTPUT_FILES.items():
            role_output = role_outputs.enter_context(
                role_output_file.open("w", newline="", encoding="utf-8-sig")
            )
            role_writer = csv.writer(role_output)
            role_writer.writerow(ROLE_HEADERS[role])
            role_writers[role] = role_writer
        writer.writerow(USER_HEADER)

        # 1. Sinh danh sách Quản trị viên (Admins)
        total_admins = 0
        for seq in range(1, admin_count + 1):
            user_id = f"AD{seq:05d}"
            name = generate_vietnamese_name(fake)
            email_name = normalize_name(name)
            email = f"{email_name}.{user_id.lower()}@hcmut.edu.vn"
            password = generate_password()
            role, title = "admin", "none"
            role_writers["admin"].writerow([user_id, name, email, password, password, role, title])
            writer.writerow([user_id, name, email, password, password, role, title, "none", "Phòng Đào tạo", "Quản trị hệ thống"])
            total_admins += 1

        # 2. Sinh danh sách Giảng viên (Lecturers) kèm Department & Specialization
        total_lecturers = 0
        seq = 1
        for alloc in lecturer_allocations:
            dept = alloc["department"]
            spec = alloc["specialization"]
            count = alloc["count"]
            for _ in range(count):
                user_id = f"GV{seq:05d}"
                name = generate_vietnamese_name(fake)
                email_name = normalize_name(name)
                email = f"{email_name}.{user_id.lower()}@hcmut.edu.vn"
                password = generate_password()
                role = "lecturer"
                title = fake.random_element(elements=lecturer_titles)
                role_writers["lecturer"].writerow([
                    user_id, name, email, password, password, role, title, dept, spec
                ])
                writer.writerow([
                    user_id, name, email, password, password, role, title, "none", dept, spec
                ])
                total_lecturers += 1
                seq += 1

        # 3. Sinh danh sách Sinh viên (Students) theo từng khóa (Cohort)
        total_students = 0
        current_students_per_cohort = initial_student_count
        cohort_summary = []
        program_counts = {p: 0 for p in programs}

        if existing_students:
            for row in existing_students:
                role_writers["student"].writerow(row)
                prog = row[7] if len(row) > 7 else "standard"
                spec = row[8] if len(row) > 8 else "Khoa học Máy tính"
                writer.writerow([
                    row[0], row[1], row[2], row[3], row[4], row[5], row[6], prog,
                    "Khoa Khoa học và Kỹ thuật Máy tính", spec
                ])
                total_students += 1
                program_counts[prog] = program_counts.get(prog, 0) + 1
        else:
            for i, cohort in enumerate(cohorts):
                if i > 0:
                    current_students_per_cohort += fake.random_int(min=increment_min, max=increment_max)
                cohort_summary.append((f"K{cohort}", current_students_per_cohort))

                for sequence in range(1, current_students_per_cohort + 1):
                    suffix = (sequence * MSSV_STEP + int(cohort) * 1049) % MSSV_MODULUS
                    user_id = f"{cohort}{suffix:05d}"
                    name = generate_vietnamese_name(fake)
                    email_name = normalize_name(name)
                    email = f"{email_name}.{user_id}@hcmut.edu.vn"
                    password = generate_password()
                    role, title = "student", "undergraduate"
                    program = fake.random.choices(programs, weights=program_weights, k=1)[0]
                    program_counts[program] += 1

                    row = [user_id, name, email, password, password, role, title, program]
                    role_writers["student"].writerow(row)
                    writer.writerow([
                        user_id, name, email, password, password, role, title, program,
                        "Khoa Khoa học và Kỹ thuật Máy tính", "Khoa học Máy tính"
                    ])
                    total_students += 1

        total_users = total_admins + total_lecturers + total_students
        print("=== KẾT QUẢ SINH DỮ LIỆU USER (TỪ CẤU HÌNH GENERATOR_CONFIG.JSON) ===")
        print(f"- Số Admin: {total_admins} -> {ROLE_OUTPUT_FILES['admin'].name}")
        print(f"- Số Giảng viên: {total_lecturers} -> {ROLE_OUTPUT_FILES['lecturer'].name}")
        print("  * Phân bổ Giảng viên theo Khoa & Chuyên môn:")
        for alloc in lecturer_allocations:
            print(f"    + {alloc['count']:>2} GV | {alloc['department'][:35]:<35} | {alloc['specialization']}")
        print(f"- Số Sinh viên: {total_students} -> {ROLE_OUTPUT_FILES['student'].name}")
        for c_name, c_count in cohort_summary:
            print(f"    + Khóa {c_name}: {c_count} sinh viên")
        print("  * Phân bổ hệ đào tạo (Program distribution):")
        for p in programs:
            pct = (program_counts[p] / total_students) * 100 if total_students else 0
            print(f"    + {p}: {program_counts[p]} ({pct:.1f}%)")
        print(f"- Tổng số User (Admin + Giảng viên + Sinh viên): {total_users} -> {OUTPUT_FILE.name}")


if __name__ == "__main__":
    generate_users()

    generate_users()