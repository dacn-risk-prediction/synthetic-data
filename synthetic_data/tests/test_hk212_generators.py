"""Unit tests for HK212 class and enrollment generation."""

from pathlib import Path
import unittest
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
CLASSES_FILE = ROOT_DIR / "generated" / "classes" / "class_hk212.csv"
ENROLLMENTS_FILE = ROOT_DIR / "generated" / "enrollments" / "enrollment_hk212.csv"
ENROLLMENTS_HK211 = ROOT_DIR / "generated" / "enrollments" / "enrollment_hk211.csv"


class TestHK212Generators(unittest.TestCase):
    """Validate class and enrollment data generated for semester HK212."""

    def test_class_hk212_structure_and_counts(self):
        """Check class_hk212.csv format, columns, and section counts."""
        self.assertTrue(CLASSES_FILE.exists(), "class_hk212.csv must exist")
        df_classes = pd.read_csv(CLASSES_FILE, encoding="utf-8-sig")

        expected_cols = {
            "class_id", "course_code", "course_name", "semester",
            "class_group", "program", "max_capacity", "lecturer_id",
            "lecturer_name", "department"
        }
        self.assertTrue(expected_cols.issubset(set(df_classes.columns)))
        self.assertGreater(len(df_classes), 400, "Should have over 400 classes for 2 cohorts")

        # Verify politics lecture hall capacity
        sp_classes = df_classes[df_classes["course_code"] == "SP1033"]
        self.assertTrue(all(sp_classes["max_capacity"] == 120), "SP1033 must have max capacity 120")

        # Verify retake classes for HK1 courses
        retake_courses = {"MT1003", "CO1005", "CO1023"}
        for rc in retake_courses:
            hl = df_classes[(df_classes["course_code"] == rc) & (df_classes["class_group"] == "L_HL01")]
            self.assertEqual(len(hl), 1, f"Should have 1 retake class for {rc}")

    def test_enrollment_hk212_coverage_and_academics(self):
        """Check enrollment_hk212.csv student coverage, GPAs, and acceleration."""
        self.assertTrue(ENROLLMENTS_FILE.exists(), "enrollment_hk212.csv must exist")
        df_enr = pd.read_csv(ENROLLMENTS_FILE, encoding="utf-8-sig", dtype={"student_id": str})

        # Check cohort distribution
        k20_ids = set(df_enr[df_enr["student_id"].str.startswith("20")]["student_id"])
        k21_ids = set(df_enr[df_enr["student_id"].str.startswith("21")]["student_id"])
        self.assertEqual(len(k20_ids), 1500, "All 1500 K20 students must have enrollments")
        self.assertEqual(len(k21_ids), 1520, "All 1520 K21 students must have enrollments")

        # Check GPA bounds
        valid_sem_gpa = df_enr["semester_gpa"].dropna()
        self.assertTrue(all((0.0 <= g <= 4.0) for g in valid_sem_gpa))
        valid_cum_gpa = df_enr["cumulative_gpa"].dropna()
        self.assertTrue(all((0.0 <= g <= 4.0) for g in valid_cum_gpa))

        # Check K20 MT2013 early completion bypass
        df_hk211 = pd.read_csv(ENROLLMENTS_HK211, encoding="utf-8-sig", dtype={"student_id": str})
        passed_mt2013_hk211 = set(
            df_hk211[(df_hk211["course_id"] == "MT2013") & (df_hk211["passed"] == True)]["student_id"]
        )
        mt2013_enr_hk212 = set(
            df_enr[df_enr["course_id"] == "MT2013"]["student_id"]
        )
        # Intersection must be empty: no student who already passed MT2013 should enroll in MT2013 again
        self.assertEqual(
            len(passed_mt2013_hk211.intersection(mt2013_enr_hk212)),
            0,
            "Students who passed MT2013 in HK211 must not re-enroll in MT2013 in HK212"
        )

        # Check K20 acceleration in CO3093 and CO2013
        k20_co3093 = df_enr[(df_enr["course_id"] == "CO3093") & (df_enr["student_id"].str.startswith("20"))]
        k20_co2013 = df_enr[(df_enr["course_id"] == "CO2013") & (df_enr["student_id"].str.startswith("20"))]
        self.assertIn(len(k20_co3093), (242, 254), "Fast-track K20 students should accelerate CO3093")
        self.assertIn(len(k20_co2013), (242, 254), "Fast-track K20 students should accelerate CO2013")

        # Check K21 acceleration in CH1003 (per updated priority in additional_course_rules.csv)
        k21_ch1003 = df_enr[(df_enr["course_id"] == "CH1003") & (df_enr["student_id"].str.startswith("21"))]
        self.assertGreater(len(k21_ch1003), 200, "K21 accelerating students should be enrolled in CH1003")


if __name__ == "__main__":
    unittest.main()

