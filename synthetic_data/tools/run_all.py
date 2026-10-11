import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

# Danh sách các file cần chạy theo đúng thứ tự
scripts = [
    "../tools/add_base_score.py",
    "classes/generate_class_hk131.py",
    "enrollments/generate_enrollment_hk131.py",
    "classes/generate_class_hk132.py",
    "enrollments/generate_enrollment_hk132.py",
    "classes/generate_class_hk141.py",
    "enrollments/generate_enrollment_hk141.py",
    "classes/generate_class_hk142.py",
    "enrollments/generate_enrollment_hk142.py",
    "classes/generate_class_hk151.py",
    "enrollments/generate_enrollment_hk151.py",
    "classes/generate_class_hk152.py",
    "enrollments/generate_enrollment_hk152.py",
    "classes/generate_class_hk161.py",
    "enrollments/generate_enrollment_hk161.py",
    "classes/generate_class_hk162.py",
    "enrollments/generate_enrollment_hk162.py",
    "classes/generate_class_hk171.py",
    "enrollments/generate_enrollment_hk171.py",
    "classes/generate_class_hk172.py",
    "enrollments/generate_enrollment_hk172.py",
    "classes/generate_class_hk181.py",
    "enrollments/generate_enrollment_hk181.py",
    "classes/generate_class_hk182.py",
    "enrollments/generate_enrollment_hk182.py",
    "classes/generate_class_hk191.py",
    "enrollments/generate_enrollment_hk191.py",
    "classes/generate_class_hk192.py",
    "enrollments/generate_enrollment_hk192.py",
    "classes/generate_class_hk201.py",
    "enrollments/generate_enrollment_hk201.py",
    "classes/generate_class_hk202.py",
    "enrollments/generate_enrollment_hk202.py",
    "classes/generate_class_hk211.py",
    "enrollments/generate_enrollment_hk211.py",
    "classes/generate_class_hk212.py",
    "enrollments/generate_enrollment_hk212.py",
    "classes/generate_class_hk221.py",
    "enrollments/generate_enrollment_hk221.py",
    "classes/generate_class_hk222.py",
    "enrollments/generate_enrollment_hk222.py",
    "classes/generate_class_hk231.py",
    "enrollments/generate_enrollment_hk231.py",
    "classes/generate_class_hk232.py",
    "enrollments/generate_enrollment_hk232.py",
    "classes/generate_class_hk241.py",
    "enrollments/generate_enrollment_hk241.py",
    "classes/generate_class_hk242.py",
    "enrollments/generate_enrollment_hk242.py",
    "classes/generate_class_hk251.py",
    "enrollments/generate_enrollment_hk251.py",
    "classes/generate_class_hk252.py",
    "enrollments/generate_enrollment_hk252.py",
    "classes/generate_class_hk261.py",
    "enrollments/generate_enrollment_hk261.py",
    "../tools/generate_academic_metrics.py",
]

for script in scripts:
    print(f"Running {script}...")
    script_path = (ROOT_DIR / "generators" / script).resolve()
    child_environment = os.environ.copy()
    child_environment["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(script_path)],
        check=False,
        env=child_environment,
    )
    if result.returncode != 0:
        print(f"Failed: {script}. Stopping the pipeline.")
        raise SystemExit(result.returncode)

    print(f"Finished {script}\n")

print("All generators completed.")