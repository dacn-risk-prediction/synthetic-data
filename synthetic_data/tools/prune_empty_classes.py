"""Script to prune unused / empty classes (classes with 0 enrollments)
from synthetic_data/generated/classes/class_hk*.csv.

Ensures that only classes that actually have registered students are kept
in the generated catalog and database.
"""

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLASSES_DIR = PROJECT_ROOT / "generated" / "classes"
ENROLLMENTS_DIR = PROJECT_ROOT / "generated" / "enrollments"


def prune_empty_classes() -> int:
    """Scan all semester class files and remove classes with 0 enrollments."""
    print("=== TỰ ĐỘNG LỌC BỎ CÁC LỚP RỖNG (0 SINH VIÊN) TRONG GENERATED ===")
    total_removed = 0
    total_kept = 0

    class_files = sorted(CLASSES_DIR.glob("class_hk*.csv"))
    if not class_files:
        print("[!] Không tìm thấy file lớp học phần nào.")
        return 0

    for cfile in class_files:
        sem = cfile.stem.replace("class_", "")
        efile = ENROLLMENTS_DIR / f"enrollment_{sem}.csv"
        if not efile.exists():
            continue

        df_class = pd.read_csv(cfile)
        df_enr = pd.read_csv(efile, usecols=["class_id"], low_memory=False)

        enrolled_cids = set(df_enr["class_id"].dropna().unique())
        before_cnt = len(df_class)

        # Keep only classes that have at least one enrolled student
        df_clean = df_class[df_class["class_id"].isin(enrolled_cids)].copy()
        after_cnt = len(df_clean)
        removed_cnt = before_cnt - after_cnt

        total_removed += removed_cnt
        total_kept += after_cnt

        if removed_cnt > 0:
            df_clean.to_csv(cfile, index=False, encoding="utf-8")
            print(f"   -> [{sem.upper()}] Đã loại bỏ {removed_cnt:>2} lớp rỗng. Còn lại {after_cnt:>3} lớp hoạt động.")

    print(f"\n[✓] Tổng cộng: Đã xóa hoàn toàn {total_removed} lớp rỗng không có sinh viên.")
    print(f"    Số lớp học phần thực tế được lưu giữ: {total_kept:,} lớp.\n")
    return total_removed


if __name__ == "__main__":
    prune_empty_classes()

