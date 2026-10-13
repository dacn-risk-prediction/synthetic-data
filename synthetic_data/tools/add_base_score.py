from pathlib import Path
import json
import sys

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "rules"))

from academic_rules import (
    GENERATOR_CONFIG,
    PROFILE_OUTPUT_DIR,
    PROFILE_OUTPUT_FILE,
    filter_students_from_2013,
    generate_student_profile,
    select_early_graduation_candidates,
)


students = pd.read_csv(
    ROOT_DIR / "data" / "people" / "student.csv",
    dtype={"student_id": str},
)
students = filter_students_from_2013(students)
profiles = [
    generate_student_profile(student_id, GENERATOR_CONFIG)
    for student_id in students["student_id"]
]
early_graduation_candidates = select_early_graduation_candidates(
    [
        {"student_id": student_id, **profile}
        for student_id, profile in zip(students["student_id"], profiles)
    ],
    GENERATOR_CONFIG,
)

# Accelerate CTXH and ensure english_pass for early graduation candidates
ctxh_benchmarks = [3, 6, 8, 10, 12, 15, 17]
for student_id, profile in zip(students["student_id"], profiles):
    if student_id in early_graduation_candidates:
        profile["english_pass"] = True
        ctxh_raw = profile.get("ctxh_days_by_semester", [])
        ctxh_list = json.loads(ctxh_raw) if isinstance(ctxh_raw, str) else [dict(x) for x in ctxh_raw]
        for idx, item in enumerate(ctxh_list):
            if idx < len(ctxh_benchmarks):
                item["cumulative_days"] = max(item.get("cumulative_days", 0), ctxh_benchmarks[idx])
            else:
                item["cumulative_days"] = max(item.get("cumulative_days", 0), 18 + (idx - 6))
        profile["ctxh_days_by_semester"] = ctxh_list

result = students[["student_id", "name"]].copy()
profile_fields = profiles[0].keys() if profiles else ()
for field in profile_fields:
    values = [profile[field] for profile in profiles]
    if values and isinstance(values[0], (list, dict)):
        values = [json.dumps(value, separators=(",", ":")) for value in values]
    result[field] = values
result["base_score"] = [
    GENERATOR_CONFIG["academic"]["base_scores"][profile["academic_level"] - 1]
    for profile in profiles
]
result["early_graduation_candidate"] = result["student_id"].isin(
    early_graduation_candidates
)

PROFILE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
result.to_csv(PROFILE_OUTPUT_FILE, index=False, encoding="utf-8-sig")

print(f"Generated student profiles: {PROFILE_OUTPUT_FILE}")
print(f"Eligible real students: {len(result)} (cohort prefix >= 13)")
print("academic_level distribution:")
if "academic_level" in result:
    print(result["academic_level"].value_counts(normalize=True).sort_index().round(3))
else:
    print("No eligible students in the source data.")
