"""Unit tests for HK231 and HK232 class and enrollment data."""

from pathlib import Path
import unittest
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
CLASSES_DIR = ROOT_DIR / "generated" / "classes"
ENROLLMENTS_DIR = ROOT_DIR / "generated" / "enrollments"


class TestHK231HK232Generators(unittest.TestCase):
    """Validate class and enrollment data generated for semesters HK231 and HK232 (K20, K21, K22, K23)."""

    def test_hk231_data_integrity(self):
        """Validate class and enrollment outputs for semester HK231."""
        class_file = CLASSES_DIR / "class_hk231.csv"
        enr_file = ENROLLMENTS_DIR / "enrollment_hk231.csv"
        self.assertTrue(class_file.exists(), "class_hk231.csv must exist")
        self.assertTrue(enr_file.exists(), "enrollment_hk231.csv must exist")

        df_classes = pd.read_csv(class_file, encoding="utf-8-sig")
        df_enr = pd.read_csv(enr_file, encoding="utf-8-sig", dtype={"student_id": str})

        # All 4 cohorts must be present
        k20 = df_enr[df_enr["student_id"].str.startswith("20")]
        k21 = df_enr[df_enr["student_id"].str.startswith("21")]
        k22 = df_enr[df_enr["student_id"].str.startswith("22")]
        k23 = df_enr[df_enr["student_id"].str.startswith("23")]

        self.assertEqual(len(k20["student_id"].unique()), 1500)
        self.assertEqual(len(k21["student_id"].unique()), 1520)
        self.assertEqual(len(k22["student_id"].unique()), 1559)
        self.assertEqual(len(k23["student_id"].unique()), 1577)

        # Check early graduation for K20 in HK231 (Term 7)
        k20_co4337 = df_enr[(df_enr["course_id"] == "CO4337") & (df_enr["student_id"].str.startswith("20"))]
        k20_sp1007 = df_enr[(df_enr["course_id"] == "SP1007") & (df_enr["student_id"].str.startswith("20"))]
        self.assertEqual(len(k20_co4337), 18, "18 fast-track K20 students should enroll in CO4337 in HK231")
        self.assertEqual(len(k20_sp1007), 18, "18 fast-track K20 students should enroll in SP1007 in HK231")

        # Check 0-credit PE1003 course for K23
        k23_pe1003 = df_enr[(df_enr["course_id"] == "PE1003") & (df_enr["student_id"].str.startswith("23"))]
        self.assertEqual(len(k23_pe1003), 1577, "All 1,577 K23 freshmen must enroll in PE1003")

        # Check SP lecture hall max capacity
        sp_classes = df_classes[df_classes["course_code"].isin(["SP1031", "SP1035", "SP1039", "SP1007"])]
        self.assertTrue(all(sp_classes["max_capacity"] == 120))

    def test_hk232_data_integrity(self):
        """Validate class and enrollment outputs for semester HK232."""
        class_file = CLASSES_DIR / "class_hk232.csv"
        enr_file = ENROLLMENTS_DIR / "enrollment_hk232.csv"
        self.assertTrue(class_file.exists(), "class_hk232.csv must exist")
        self.assertTrue(enr_file.exists(), "enrollment_hk232.csv must exist")

        df_classes = pd.read_csv(class_file, encoding="utf-8-sig")
        df_enr = pd.read_csv(enr_file, encoding="utf-8-sig", dtype={"student_id": str})

        # Cohort participation in HK232:
        # K20: 1,482 active students (18 already graduated in HK231!)
        k20 = df_enr[df_enr["student_id"].str.startswith("20")]
        k21 = df_enr[df_enr["student_id"].str.startswith("21")]
        k22 = df_enr[df_enr["student_id"].str.startswith("22")]
        k23 = df_enr[df_enr["student_id"].str.startswith("23")]

        self.assertEqual(len(k20["student_id"].unique()), 1482, "Only remaining 1,482 K20 students should enroll in HK232")
        self.assertEqual(len(k21["student_id"].unique()), 1520)
        self.assertEqual(len(k22["student_id"].unique()), 1559)
        self.assertEqual(len(k23["student_id"].unique()), 1577)

        # Check standard 4-year graduation for remaining K20
        k20_co4337 = df_enr[(df_enr["course_id"] == "CO4337") & (df_enr["student_id"].str.startswith("20"))]
        k20_sp1007 = df_enr[(df_enr["course_id"] == "SP1007") & (df_enr["student_id"].str.startswith("20"))]
        self.assertEqual(len(k20_co4337), 1482, "All 1,482 regular K20 students should complete CO4337 in HK232")
        self.assertEqual(len(k20_sp1007), 1482, "All 1,482 regular K20 students should complete SP1007 in HK232")

        # Check K23 acceleration course CH1003 per priority 15
        k23_ch1003 = df_enr[(df_enr["course_id"] == "CH1003") & (df_enr["student_id"].str.startswith("23"))]
        self.assertGreater(len(k23_ch1003), 200, "K23 should accelerate CH1003 per priority 15")

        # Check 0-credit courses for K23: MI1003 and PE1005
        k23_mi1003 = df_enr[(df_enr["course_id"] == "MI1003") & (df_enr["student_id"].str.startswith("23"))]
        k23_pe1005 = df_enr[(df_enr["course_id"] == "PE1005") & (df_enr["student_id"].str.startswith("23"))]
        self.assertEqual(len(k23_mi1003), 1577, "All 1,577 K23 freshmen must enroll in MI1003")
        self.assertEqual(len(k23_pe1005), 1577, "All 1,577 K23 freshmen must enroll in PE1005")

        # Check early graduation candidates for K21 in HK6 (CO3061 and CO4029)
        k21_early_ai = df_enr[(df_enr["course_id"] == "CO3061") & (df_enr["student_id"].str.startswith("21"))]
        k21_early_proj = df_enr[(df_enr["course_id"] == "CO4029") & (df_enr["student_id"].str.startswith("21"))]
        self.assertGreaterEqual(len(k21_early_ai), 18, "K21 fast-track students should enroll in CO3061")
        self.assertEqual(len(k21_early_proj), 18, "18 K21 fast-track students (1.2%) should enroll in CO4029")

        # Check retake classes opened for HK1/odd courses with >= 20 students
        for rc in ["MT1003", "PH1003", "CO1005", "CO1023", "CO2011", "CO2003", "CO2007", "SP1031"]:
            hl = df_classes[(df_classes["course_code"] == rc) & (df_classes["class_group"] == "L_HL01")]
            self.assertEqual(len(hl), 1, f"Should open 1 retake class for {rc}")


if __name__ == "__main__":
    unittest.main()

