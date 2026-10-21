import csv
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]

# Target output files:
# 1. generated/academics/semester.csv (Standard generator output directory)
OUTPUT_FILES = [
    ROOT_DIR / "generated" / "academics" / "semester.csv",
]

START_COHORT_YEAR = 20
END_COHORT_YEAR = 26
LAST_YEAR_MAX_TERM = 1


def generate_semesters(start_year=START_COHORT_YEAR, end_year=END_COHORT_YEAR, last_term_final_year=LAST_YEAR_MAX_TERM):
    """
    Generate semesters sequence from HK201 to HK261.
    Each academic year from 2020 to 2025 has 2 main terms (1 and 2).
    The final year 2026 stops at term 1 (HK261).
    """
    semesters = []
    semester_id = 1

    for year in range(start_year, end_year + 1):
        acad_start = 2000 + year
        acad_end = acad_start + 1
        academic_year = f"{acad_start}-{acad_end}"

        max_term = last_term_final_year if year == end_year else 2
        for term in range(1, max_term + 1):
            semester_code = f"HK{year}{term}"
            semesters.append({
                "semester_id": semester_id,
                "semester_code": semester_code,
                "academic_year": academic_year,
            })
            semester_id += 1

    return semesters


def save_semesters():
    semesters = generate_semesters()
    header = ["semester_id", "semester_code", "academic_year"]

    for output_file in OUTPUT_FILES:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(semesters)
        print(f"Created {output_file} with {len(semesters)} semesters.")


if __name__ == "__main__":
    save_semesters()

