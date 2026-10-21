"""Course Assessment Syllabus Generator.

Defines and generates the standardized course assessment scheme
(percentage weights for quiz, lab, btl, giua_ky, cuoi_ky)
for all active courses in the curriculum.

Output:
- synthetic_data/generated/academics/assessment.csv
"""

import csv
from pathlib import Path
from typing import Dict, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT_DIR / "generated" / "academics"
COURSES_FILE = OUTPUT_DIR / "courses.csv"
OUTPUT_FILE = OUTPUT_DIR / "assessment.csv"

# Mapping: course_code -> (category, quiz, lab, btl, giua_ky, cuoi_ky)
# Total percentage weights for each course must strictly sum up to 100.
COURSE_ASSESSMENT_SPECS: Dict[str, Tuple[str, int, int, int, int, int]] = {
    # Đại cương & Cơ bản (Toán, Lý, Hóa)
    "CH1003": ("toan_ly_hoa", 0, 20, 0, 30, 50),
    "MT1003": ("toan_ly_hoa", 0, 0, 20, 20, 60),
    "MT1005": ("toan_ly_hoa", 0, 0, 20, 20, 60),
    "MT1007": ("toan_ly_hoa", 0, 0, 20, 30, 50),
    "MT2013": ("toan_ly_hoa", 0, 0, 20, 20, 60),
    "PH1003": ("toan_ly_hoa", 0, 0, 20, 20, 60),
    "PH1007": ("toan_ly_hoa", 40, 0, 0, 0, 60),

    # Lý luận Chính trị & Pháp luật
    "SP1007": ("chinh_tri", 0, 0, 20, 30, 50),
    "SP1031": ("chinh_tri", 20, 0, 30, 0, 50),
    "SP1033": ("chinh_tri", 20, 0, 30, 0, 50),
    "SP1035": ("chinh_tri", 20, 0, 30, 0, 50),
    "SP1037": ("chinh_tri", 20, 0, 30, 0, 50),
    "SP1039": ("chinh_tri", 20, 0, 30, 0, 50),

    # Ngoại ngữ
    "LA1003": ("ngoai_ngu", 0, 0, 20, 30, 50),
    "LA1005": ("ngoai_ngu", 0, 0, 20, 30, 50),
    "LA1007": ("ngoai_ngu", 10, 0, 20, 20, 50),
    "LA1009": ("ngoai_ngu", 0, 0, 20, 30, 50),

    # Giáo dục thể chất & Giáo dục quốc phòng
    "MI1003": ("giao_duc", 0, 0, 20, 20, 60),
    "PE1003": ("giao_duc", 0, 0, 20, 20, 60),
    "PE1005": ("giao_duc", 0, 0, 20, 20, 60),

    # Kinh tế & Quản lý
    "IM1013": ("kinh_te", 0, 0, 20, 30, 50),
    "IM1023": ("kinh_te", 0, 20, 20, 0, 60),
    "IM1025": ("kinh_te", 0, 0, 20, 30, 50),
    "IM1027": ("kinh_te", 0, 0, 20, 30, 50),
    "IM3001": ("kinh_te", 10, 0, 20, 20, 50),

    # Chuyên ngành & Cơ sở ngành Khoa học Máy tính (CO)
    "CO1005": ("khac", 0, 30, 20, 0, 50),
    "CO1007": ("khac", 0, 0, 20, 20, 60),
    "CO1023": ("khac", 0, 20, 20, 0, 60),
    "CO1027": ("khac", 0, 10, 20, 20, 50),
    "CO2001": ("khac", 0, 0, 20, 30, 50),
    "CO2003": ("khac", 0, 20, 20, 0, 60),
    "CO2007": ("khac", 0, 0, 20, 20, 60),
    "CO2011": ("khac", 0, 0, 20, 30, 50),
    "CO2013": ("khac", 0, 0, 20, 20, 60),
    "CO2017": ("khac", 0, 0, 20, 30, 50),
    "CO2039": ("khac", 0, 20, 20, 0, 60),
    "CO3001": ("khac", 0, 0, 20, 30, 50),
    "CO3005": ("khac", 0, 0, 20, 20, 60),
    "CO3011": ("khac", 10, 0, 20, 20, 50),
    "CO3013": ("khac", 0, 20, 20, 0, 60),
    "CO3015": ("khac", 0, 0, 20, 30, 50),
    "CO3017": ("khac", 0, 0, 20, 30, 50),
    "CO3021": ("khac", 0, 0, 20, 30, 50),
    "CO3023": ("khac", 0, 20, 20, 0, 60),
    "CO3027": ("khac", 0, 0, 20, 30, 50),
    "CO3029": ("khac", 0, 0, 20, 30, 50),
    "CO3031": ("khac", 0, 0, 20, 30, 50),
    "CO3033": ("khac", 0, 20, 20, 0, 60),
    "CO3035": ("khac", 10, 0, 20, 20, 50),
    "CO3037": ("khac", 0, 0, 20, 30, 50),
    "CO3041": ("khac", 0, 0, 20, 30, 50),
    "CO3043": ("khac", 0, 20, 20, 0, 60),
    "CO3045": ("khac", 0, 0, 20, 30, 50),
    "CO3047": ("khac", 10, 0, 20, 20, 50),
    "CO3049": ("khac", 0, 0, 20, 30, 50),
    "CO3051": ("khac", 0, 20, 20, 0, 60),
    "CO3057": ("khac", 0, 0, 20, 30, 50),
    "CO3059": ("khac", 0, 0, 20, 30, 50),
    "CO3061": ("khac", 10, 0, 20, 20, 50),
    "CO3065": ("khac", 0, 20, 20, 0, 60),
    "CO3067": ("khac", 0, 0, 20, 30, 50),
    "CO3069": ("khac", 0, 0, 20, 30, 50),
    "CO3071": ("khac", 0, 0, 20, 30, 50),
    "CO3083": ("khac", 0, 20, 20, 0, 60),
    "CO3085": ("khac", 0, 0, 20, 30, 50),
    "CO3089": ("khac", 0, 0, 20, 30, 50),
    "CO3093": ("khac", 0, 0, 20, 30, 50),
    "CO3101": ("khac", 0, 0, 20, 20, 60),
    "CO3103": ("khac", 0, 0, 20, 20, 60),
    "CO3105": ("khac", 0, 0, 20, 20, 60),
    "CO3107": ("khac", 0, 0, 20, 20, 60),
    "CO3109": ("khac", 0, 0, 20, 20, 60),
    "CO3111": ("khac", 0, 0, 20, 20, 60),
    "CO3115": ("khac", 10, 0, 20, 20, 50),
    "CO3117": ("khac", 0, 0, 20, 30, 50),
    "CO3119": ("khac", 0, 0, 20, 20, 60),
    "CO3127": ("khac", 0, 0, 20, 20, 60),
    "CO3129": ("khac", 0, 0, 20, 30, 50),
    "CO3131": ("khac", 10, 0, 20, 20, 50),
    "CO3133": ("khac", 0, 20, 20, 0, 60),
    "CO3135": ("khac", 0, 0, 20, 30, 50),
    "CO3137": ("khac", 0, 0, 20, 30, 50),
    "CO3139": ("khac", 0, 0, 20, 30, 50),
    "CO3151": ("khac", 0, 20, 20, 0, 60),
    "CO3153": ("khac", 0, 0, 20, 30, 50),
    "CO3335": ("khac", 0, 0, 20, 30, 50),
    "CO4025": ("khac", 0, 0, 20, 30, 50),
    "CO4029": ("khac", 0, 0, 20, 30, 50),
    "CO4031": ("khac", 10, 0, 20, 20, 50),
    "CO4033": ("khac", 0, 0, 20, 30, 50),
    "CO4035": ("khac", 0, 0, 20, 30, 50),
    "CO4037": ("khac", 0, 20, 20, 0, 60),
    "CO4039": ("khac", 0, 0, 20, 30, 50),
    "CO4337": ("khac", 0, 0, 20, 20, 60),
}


def load_course_metadata() -> Dict[str, Tuple[str, int]]:
    """Load course names and credits from courses.csv if available."""
    metadata = {}
    if COURSES_FILE.exists():
        with COURSES_FILE.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row["course_code"].strip()
                name = row["course_name_vi"].strip()
                credits = int(float(row["credits"]))
                metadata[code] = (name, credits)
    return metadata


def generate_assessments():
    """Generate and validate assessment syllabus table."""
    course_meta = load_course_metadata()
    records = []

    for course_id, (category, quiz, lab, btl, giua_ky, cuoi_ky) in sorted(COURSE_ASSESSMENT_SPECS.items()):
        total = quiz + lab + btl + giua_ky + cuoi_ky
        if total != 100:
            raise ValueError(f"Course {course_id} assessment components sum to {total}%, expected 100%.")

        name, credits = course_meta.get(course_id, (f"Môn {course_id}", 3))
        records.append({
            "course_id": course_id,
            "course_name": name,
            "credits": credits,
            "course_category": category,
            "quiz": quiz,
            "lab": lab,
            "btl": btl,
            "giua_ky": giua_ky,
            "cuoi_ky": cuoi_ky,
        })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    fields = ["course_id", "course_name", "credits", "course_category", "quiz", "lab", "btl", "giua_ky", "cuoi_ky"]
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

    print(f"Generated {OUTPUT_FILE} with {len(records)} course assessment schemes.")


if __name__ == "__main__":
    generate_assessments()

