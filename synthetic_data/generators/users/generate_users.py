import csv
from contextlib import ExitStack
import re
import secrets
import string
import unicodedata
from pathlib import Path

from faker import Faker


INITIAL_STUDENT_COUNT = 1500
STUDENT_INCREMENT_MIN = 15
STUDENT_INCREMENT_MAX = 50
COHORTS = tuple(range(20, 27))

ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT_DIR / "generated" / "users"
OUTPUT_FILE = OUTPUT_DIR / "user.csv"
ROLE_OUTPUT_FILES = {
    "student": OUTPUT_DIR / "student.csv",
    "lecturer": OUTPUT_DIR / "lecturer.csv",
    "admin": OUTPUT_DIR / "admin.csv",
}
MSSV_STEP = 7919
MSSV_MODULUS = 100_000
ADMIN_COUNT = 10

# Phân bổ 100 giảng viên theo Khoa/Bộ môn và Chuyên môn để cân bằng tải số lớp
LECTURER_ALLOCATIONS = [
    # 1. Khoa KH&KT Máy tính (55 GV)
    {
        "department": "Khoa Khoa học và Kỹ thuật Máy tính",
        "specialization": "Trí tuệ nhân tạo",
        "count": 13,
    },
    {
        "department": "Khoa Khoa học và Kỹ thuật Máy tính",
        "specialization": "Công nghệ Phần mềm",
        "count": 13,
    },
    {
        "department": "Khoa Khoa học và Kỹ thuật Máy tính",
        "specialization": "An ninh hệ thống và mạng",
        "count": 11,
    },
    {
        "department": "Khoa Khoa học và Kỹ thuật Máy tính",
        "specialization": "Kỹ thuật Máy tính",
        "count": 10,
    },
    {
        "department": "Khoa Khoa học và Kỹ thuật Máy tính",
        "specialization": "Công nghệ dữ liệu và dữ liệu lớn",
        "count": 8,
    },
    # 2. Toán Ứng dụng (15 GV)
    {
        "department": "Khoa Khoa học Ứng dụng - Bộ môn Toán ứng dụng",
        "specialization": "Toán Ứng dụng & Thống kê",
        "count": 15,
    },
    # 3. Trung tâm Ngoại ngữ (14 GV)
    {
        "department": "Trung tâm Ngoại ngữ",
        "specialization": "Tiếng Anh học thuật",
        "count": 14,
    },
    # 4. Lý luận Chính trị (8 GV)
    {
        "department": "Khoa Khoa học Ứng dụng - Bộ môn Lý luận Chính trị",
        "specialization": "Lý luận Chính trị & Pháp luật",
        "count": 8,
    },
    # 5. Vật lý & KHTN (8 GV)
    {
        "department": "Khoa Khoa học Ứng dụng - Bộ môn Vật lý ứng dụng",
        "specialization": "Vật lý & Khoa học Tự nhiên",
        "count": 8,
    },
]

LECTURER_COUNT = sum(a["count"] for a in LECTURER_ALLOCATIONS)
LECTURER_TITLES = ("bachelor", "master", "doctor", "associate_professor", "professor")
PROGRAMS = ("standard", "advanced", "high-quality")
PROGRAM_WEIGHTS = (0.60, 0.10, 0.30)

USER_HEADER = [
    "user_id", "name", "email", "password", "password_hash", "role", "title", "program", "department", "specialization",
]
ROLE_HEADERS = {
    "student": [
        "user_id", "name", "email", "password", "password_hash", "role", "title", "program",
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


def normalize_name(name):
    name = name.replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFD", name)
    without_marks = "".join(
        character for character in normalized
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"[^a-z0-9]", "", without_marks.lower())


def generate_password():
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


def generate_vietnamese_name(fake):
    surname = fake.random_element(elements=SURNAMES)
    middle_name = fake.random_element(elements=MIDDLE_NAMES)
    given_name = fake.random_element(elements=GIVEN_NAMES)
    return f"{surname} {middle_name} {given_name}"


def generate_users():
    fake = Faker("vi_VN")
    Faker.seed(20260923)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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
        for seq in range(1, ADMIN_COUNT + 1):
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
        for alloc in LECTURER_ALLOCATIONS:
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
                title = fake.random_element(elements=LECTURER_TITLES)
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
        current_students_per_cohort = INITIAL_STUDENT_COUNT
        cohort_summary = []
        program_counts = {p: 0 for p in PROGRAMS}

        for i, cohort in enumerate(COHORTS):
            if i > 0:
                current_students_per_cohort += fake.random_int(
                    min=STUDENT_INCREMENT_MIN, max=STUDENT_INCREMENT_MAX
                )
            cohort_summary.append((f"K{cohort}", current_students_per_cohort))

            for sequence in range(1, current_students_per_cohort + 1):
                suffix = (sequence * MSSV_STEP + cohort * 1049) % MSSV_MODULUS
                user_id = f"{cohort}{suffix:05d}"
                name = generate_vietnamese_name(fake)
                email_name = normalize_name(name)
                email = f"{email_name}.{user_id}@hcmut.edu.vn"
                password = generate_password()
                role, title = "student", "undergraduate"
                program = fake.random.choices(PROGRAMS, weights=PROGRAM_WEIGHTS, k=1)[0]
                program_counts[program] += 1

                row = [user_id, name, email, password, password, role, title, program]
                role_writers["student"].writerow(row)
                writer.writerow([
                    user_id, name, email, password, password, role, title, program,
                    "Khoa Khoa học và Kỹ thuật Máy tính", "Khoa học Máy tính"
                ])
                total_students += 1

        total_users = total_admins + total_lecturers + total_students
        print("=== KẾT QUẢ SINH DỮ LIỆU ===")
        print(f"- Số Admin: {total_admins} -> {ROLE_OUTPUT_FILES['admin'].name}")
        print(f"- Số Giảng viên: {total_lecturers} -> {ROLE_OUTPUT_FILES['lecturer'].name}")
        print("  * Phân bổ Giảng viên theo Khoa & Chuyên môn:")
        for alloc in LECTURER_ALLOCATIONS:
            print(f"    + {alloc['count']:>2} GV | {alloc['department'][:35]:<35} | {alloc['specialization']}")
        print(f"- Số Sinh viên: {total_students} -> {ROLE_OUTPUT_FILES['student'].name}")
        for c_name, c_count in cohort_summary:
            print(f"    + Khóa {c_name}: {c_count} sinh viên")
        print("  * Phân bổ hệ đào tạo (Program distribution):")
        for p in PROGRAMS:
            pct = (program_counts[p] / total_students) * 100 if total_students else 0
            print(f"    + {p}: {program_counts[p]} ({pct:.1f}%)")
        print(f"- Tổng số User (Admin + Giảng viên + Sinh viên): {total_users} -> {OUTPUT_FILE.name}")


if __name__ == "__main__":
    generate_users()