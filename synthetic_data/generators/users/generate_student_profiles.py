"""Generate persistent student psychological profiles and academic baselines.

Generates latent traits (academic_level, math_level, english_level, discipline,
motivation, stress, base_score) and assigns realistic specializations (chuyên ngành)
for all students in synthetic_data/generated/users/student.csv.
Exports directly to: synthetic_data/generated/users/student_profiles.csv.

These persistent traits ensure academic performance follows realistic, consistent patterns
across all semesters (HK201 - HK262).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
USERS_DIR = ROOT_DIR / "generated" / "users"
RULES_DIR = ROOT_DIR / "rules"
CONFIG_FILE = ROOT_DIR / "config" / "generator_config.json"

if str(RULES_DIR) not in sys.path:
    sys.path.insert(0, str(RULES_DIR))

from academic_rules import (
    GENERATOR_CONFIG,
    generate_student_profile,
    select_early_graduation_candidates,
)

INPUT_STUDENT_FILE = USERS_DIR / "student.csv"
OUTPUT_PROFILE_FILE = USERS_DIR / "student_profiles.csv"


def assign_specialization(student_id: str, cohort: str, config: Dict[str, Any]) -> str:
    """Assign student specialization based on cohort distribution configured in generator_config.json."""
    spec_config = config.get("student_progress", {}).get("specializations", {})
    if not spec_config:
        spec_config = config.get("specializations", {})

    cohort_dist = spec_config.get("cohort_distribution", {}).get(
        cohort, spec_config.get("default_distribution", {})
    )
    if not cohort_dist:
        return "Khoa học Máy tính"

    specs = list(cohort_dist.keys())
    probs = np.array(list(cohort_dist.values()), dtype=float)
    probs = probs / probs.sum()

    # Deterministic assignment using sha256 to ensure reproducibility
    seed = config.get("seed", 20261006)
    val = f"{seed}:{student_id}:specialization".encode("utf-8")
    hash_val = int(hashlib.sha256(val).hexdigest()[:8], 16)
    rng = np.random.default_rng(hash_val)
    return str(rng.choice(specs, p=probs))


def generate_student_profiles() -> Path:
    """Generate persistent profiles for all system students."""
    print("=== KHỞI CHẠY SINH HỒ SƠ NĂNG LỰC SINH VIÊN (STUDENT PROFILES) ===")

    if not INPUT_STUDENT_FILE.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {INPUT_STUDENT_FILE}")

    df_students = pd.read_csv(INPUT_STUDENT_FILE, encoding="utf-8-sig", dtype=str)
    student_count = len(df_students)
    print(f"1. Tổng số sinh viên cần sinh hồ sơ: {student_count:,} sinh viên (Khóa K20 - K26).")

    # 1. Sinh latent profile và gán chuyên ngành cho từng sinh viên
    print("\n2. Đang tạo các chỉ số tâm lý, học lực ẩn và gán chuyên ngành theo khóa...")
    profiles: List[Dict[str, Any]] = []
    for _, row in df_students.iterrows():
        uid = str(row["user_id"])
        prog = row.get("program", "standard")
        cohort = "K" + uid[:2]

        p = generate_student_profile(uid, GENERATOR_CONFIG)

        # Gán chuyên ngành theo cấu hình generator_config.json
        p["specialization"] = assign_specialization(uid, cohort, GENERATOR_CONFIG)

        # Với hệ Chất lượng cao và Tiên tiến: Miễn tiếng Anh đầu vào
        if prog in ("high-quality", "advanced"):
            p["english_pass"] = True
            for item in p.get("english_eligibility_by_semester", []):
                item["eligible"] = True

        profiles.append(p)

    # 2. Xác định các ứng viên tốt nghiệp sớm (Early Graduation Candidates)
    print("\n3. Xác định ứng viên tốt nghiệp sớm và đẩy nhanh tiến độ CTXH...")
    profile_records_for_selection = [
        {"student_id": uid, **p}
        for uid, p in zip(df_students["user_id"], profiles)
    ]
    early_graduation_candidates = select_early_graduation_candidates(
        profile_records_for_selection, GENERATOR_CONFIG
    )
    print(f"   -> Số ứng viên tốt nghiệp sớm: {len(early_graduation_candidates):,} sinh viên.")

    # Cập nhật điều kiện cho ứng viên tốt nghiệp sớm
    ctxh_benchmarks = [3, 6, 8, 10, 12, 15, 17]
    for uid, profile in zip(df_students["user_id"], profiles):
        if uid in early_graduation_candidates:
            profile["english_pass"] = True
            for item in profile.get("english_eligibility_by_semester", []):
                item["eligible"] = True
            ctxh_raw = profile.get("ctxh_days_by_semester", [])
            ctxh_list = (
                json.loads(ctxh_raw)
                if isinstance(ctxh_raw, str)
                else [dict(x) for x in ctxh_raw]
            )
            for idx, item in enumerate(ctxh_list):
                if idx < len(ctxh_benchmarks):
                    item["cumulative_days"] = max(
                        item.get("cumulative_days", 0), ctxh_benchmarks[idx]
                    )
                else:
                    item["cumulative_days"] = max(
                        item.get("cumulative_days", 0), 18 + (idx - 6)
                    )
            profile["ctxh_days_by_semester"] = ctxh_list

    # 3. Tổng hợp thành DataFrame hoàn chỉnh
    print("\n4. Đang định dạng dữ liệu và tính toán base_score...")
    result = pd.DataFrame()
    result["student_id"] = df_students["user_id"]
    result["name"] = df_students["name"]
    result["program"] = df_students["program"]
    result["specialization"] = [p["specialization"] for p in profiles]

    profile_fields = [k for k in profiles[0].keys() if k != "specialization"]
    for field in profile_fields:
        values = [p[field] for p in profiles]
        if values and isinstance(values[0], (list, dict)):
            values = [json.dumps(val, separators=(",", ":")) for val in values]
        result[field] = values

    # Tính điểm nền tảng (base_score 3.0 - 9.5) từ academic_level
    result["base_score"] = [
        GENERATOR_CONFIG["academic"]["base_scores"][p["academic_level"] - 1]
        for p in profiles
    ]
    result["early_graduation_candidate"] = result["student_id"].isin(early_graduation_candidates)

    # 4. Xuất file CSV hồ sơ sinh viên
    OUTPUT_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PROFILE_FILE, index=False, encoding="utf-8-sig")

    # 5. Đồng bộ chuyên ngành vào student.csv và user.csv
    spec_map = dict(zip(result["student_id"], result["specialization"]))
    df_students["specialization"] = df_students["user_id"].map(spec_map)
    df_students.to_csv(INPUT_STUDENT_FILE, index=False, encoding="utf-8-sig")

    user_file = USERS_DIR / "user.csv"
    if user_file.exists():
        df_user = pd.read_csv(user_file, dtype=str)
        is_student = df_user["role"] == "student"
        df_user.loc[is_student, "specialization"] = (
            df_user.loc[is_student, "user_id"].map(spec_map).fillna(df_user.loc[is_student, "specialization"])
        )
        df_user.to_csv(user_file, index=False, encoding="utf-8-sig")

    print(f"\n=== ĐÃ TẠO THÀNH CÔNG: {OUTPUT_PROFILE_FILE} ===")
    print(f"Tổng số hồ sơ sinh viên: {len(result):,} dòng")

    result["cohort"] = "K" + result["student_id"].str[:2]
    print("\nThống kê chuyên ngành (specialization) theo từng khóa:")
    cross_tab = pd.crosstab(result["cohort"], result["specialization"], margins=True)
    print(cross_tab)

    print("\nTỷ lệ chuyên ngành theo từng khóa (%):")
    cross_tab_pct = pd.crosstab(result["cohort"], result["specialization"], normalize="index").round(3) * 100
    print(cross_tab_pct)

    return OUTPUT_PROFILE_FILE


if __name__ == "__main__":
    generate_student_profiles()
