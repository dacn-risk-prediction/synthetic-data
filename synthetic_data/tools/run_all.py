import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

# 1. Core academic and user generation scripts
core_scripts = [
    ROOT_DIR / "generators" / "academics" / "generate_semester.py",
    ROOT_DIR / "generators" / "academics" / "generate_curriculum.py",
    ROOT_DIR / "generators" / "academics" / "generate_assessment.py",
    ROOT_DIR / "generators" / "users" / "generate_users.py",
    ROOT_DIR / "generators" / "users" / "generate_student_profiles.py",
]

# 2. Discover available class and enrollment scripts dynamically
classes_dir = ROOT_DIR / "generators" / "classes"
enrollments_dir = ROOT_DIR / "generators" / "enrollments"

class_scripts = sorted(classes_dir.glob("generate_class_hk*.py"))
semester_pipeline = []
for cs in class_scripts:
    semester_code = cs.stem.replace("generate_class_", "")
    es = enrollments_dir / f"generate_enrollment_{semester_code}.py"
    semester_pipeline.append(cs)
    if es.exists():
        semester_pipeline.append(es)

# 3. Add class pruning and metrics calculation at the end of the pipeline
prune_script = ROOT_DIR / "tools" / "prune_empty_classes.py"
metrics_script = ROOT_DIR / "tools" / "generate_academic_metrics.py"
post_scripts = [p for p in [prune_script, metrics_script] if p.exists()]
all_scripts = core_scripts + semester_pipeline + post_scripts

for script_path in all_scripts:
    if not script_path.exists():
        continue
    rel_path = script_path.relative_to(ROOT_DIR)
    print(f"Running {rel_path}...")
    child_environment = os.environ.copy()
    child_environment["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(script_path)],
        check=False,
        env=child_environment,
    )
    if result.returncode != 0:
        print(f"Failed: {rel_path}. Stopping the pipeline.")
        raise SystemExit(result.returncode)

    print(f"Finished {rel_path}\n")

print("All active generators completed successfully.")