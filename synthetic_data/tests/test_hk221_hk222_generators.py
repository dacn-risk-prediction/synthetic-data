"""Unit tests for HK221 and HK222 class and enrollment data."""

from pathlib import Path
import unittest
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
CLASSES_DIR = ROOT_DIR / "generated" / "classes"
ENROLLMENTS_DIR = ROOT_DIR / "generated" / "enrollments"


class TestHK221HK222Generators(unittest.TestCase):
    """Validate class and enrollment data generated for semesters HK221 and HK222 (K20, K21, K22)."""

    def test_hk221_data_integrity(self):
        """Validate class and enrollment outputs for semester HK221."""
        class_file = CLASSES_DIR / "class_hk221.csv"
        enr_file = ENROLLMENTS_DIR / "enrollment_hk221.csv"
        self.assertTrue(class_file.exists(), "class_hk221.csv must exist")
        self.assertTrue(enr_file.exists(), "enrollment_hk221.csv must exist")

        df_classes = pd.read_csv(class_file, encoding="utf-8-sig")
        df_enr = pd.read_csv(enr_file, encoding="utf-8-sig", dtype={"student_id": str})

        # All 3 cohorts must be present
        k20 = df_enr[df_enr["student_id"].str.startswith("20")]
        k21 = df_enr[df_enr["student_id"].str.startswith("21")]
        k22 = df_enr[df_enr["student_id"].str.startswith("22")]
        self.assertEqual(len(k20["student_id"].unique()), 1500)
        self.assertEqual(len(k21["student_id"].unique()), 1520)
        self.assertEqual(len(k22["student_id"].unique()), 1559)

        # Check GPA bounds
        self.assertTrue(all((0.0 <= g <= 4.0) for g in df_enr["semester_gpa"].dropna()))
        self.assertTrue(all((0.0 <= g <= 4.0) for g in df_enr["cumulative_gpa"].dropna()))

        # Check SP lecture hall max capacity
        sp_classes = df_classes[df_classes["course_code"].isin(["SP1031", "SP1035"])]
        self.assertTrue(all(sp_classes["max_capacity"] == 120))

    def test_hk222_data_integrity(self):
        """Validate class and enrollment outputs for semester HK222."""
        class_file = CLASSES_DIR / "class_hk222.csv"
        enr_file = ENROLLMENTS_DIR / "enrollment_hk222.csv"
        self.assertTrue(class_file.exists(), "class_hk222.csv must exist")
        self.assertTrue(enr_file.exists(), "enrollment_hk222.csv must exist")

        df_classes = pd.read_csv(class_file, encoding="utf-8-sig")
        df_enr = pd.read_csv(enr_file, encoding="utf-8-sig", dtype={"student_id": str})

        # All 3 cohorts must be present
        k20 = df_enr[df_enr["student_id"].str.startswith("20")]
        k21 = df_enr[df_enr["student_id"].str.startswith("21")]
        k22 = df_enr[df_enr["student_id"].str.startswith("22")]
        self.assertEqual(len(k20["student_id"].unique()), 1500)
        self.assertEqual(len(k21["student_id"].unique()), 1520)
        self.assertEqual(len(k22["student_id"].unique()), 1559)

        # Check K22 acceleration course CH1003
        k22_ch1003 = df_enr[(df_enr["course_id"] == "CH1003") & (df_enr["student_id"].str.startswith("22"))]
        self.assertGreater(len(k22_ch1003), 200, "K22 should accelerate CH1003 per priority 15")

        # Check early graduation candidates for K20 in HK6 (CO3061 and CO4029)
        k20_early_ai = df_enr[(df_enr["course_id"] == "CO3061") & (df_enr["student_id"].str.startswith("20"))]
        k20_early_thesis = df_enr[(df_enr["course_id"] == "CO4029") & (df_enr["student_id"].str.startswith("20"))]
        self.assertEqual(len(k20_early_ai), 18, "18 K20 fast-track students (1.2%) should enroll in CO3061")
        self.assertEqual(len(k20_early_thesis), 18, "18 K20 fast-track students (1.2%) should enroll in CO4029")

        # Check retake classes opened for HK1 courses with >= 20 students
        for rc in ["MT1003", "PH1003", "CO1005", "CO1023"]:
            hl = df_classes[(df_classes["course_code"] == rc) & (df_classes["class_group"] == "L_HL01")]
            self.assertEqual(len(hl), 1, f"Should open 1 retake class for {rc}")


if __name__ == "__main__":
    unittest.main()

