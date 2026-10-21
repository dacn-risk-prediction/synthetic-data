"""Unit tests for the new Academic Curriculum lookup functions."""

import sys
import unittest
from pathlib import Path

# Add analysis directory to path
ANALYSIS_DIR = Path(__file__).resolve().parents[1] / "analysis"
sys.path.insert(0, str(ANALYSIS_DIR))

from analysis_helpers import (
    get_curriculum_for_cohort_semester,
    get_full_curriculum_roadmap,
    normalize_cohort,
    resolve_semester,
)


class TestCurriculumLookup(unittest.TestCase):
    """Test curriculum resolution across cohorts and semesters."""

    def test_normalize_cohort(self):
        # Various valid cohort inputs
        self.assertEqual(normalize_cohort("K24"), (24, "K24", "KHMT_K24"))
        self.assertEqual(normalize_cohort("k24"), (24, "K24", "KHMT_K24"))
        self.assertEqual(normalize_cohort(24), (24, "K24", "KHMT_K24"))
        self.assertEqual(normalize_cohort("2024"), (24, "K24", "KHMT_K24"))
        self.assertEqual(normalize_cohort("KHMT_K20"), (20, "K20", "KHMT_K20"))
        self.assertEqual(normalize_cohort("K26"), (26, "K26", "KHMT_K26"))

        # Invalid cohort
        with self.assertRaises(ValueError):
            normalize_cohort("ABC")
        with self.assertRaises(ValueError):
            normalize_cohort("K15")  # Not in catalog (K20 - K26)

    def test_resolve_semester_relative(self):
        # Relative semester for K24
        s1 = resolve_semester(24, "HK1")
        self.assertEqual(s1["relative_term"], 1)
        self.assertEqual(s1["academic_semester"], "HK241")
        self.assertEqual(s1["status"], "NORMAL")

        s2 = resolve_semester(24, 2)
        self.assertEqual(s2["relative_term"], 2)
        self.assertEqual(s2["academic_semester"], "HK242")
        self.assertEqual(s2["status"], "NORMAL")

        s8 = resolve_semester(24, "HK8")
        self.assertEqual(s8["relative_term"], 8)
        self.assertEqual(s8["academic_semester"], "HK272")
        self.assertEqual(s8["status"], "NORMAL")

    def test_resolve_semester_absolute(self):
        # Absolute semester for K24
        s_hk241 = resolve_semester(24, "HK241")
        self.assertEqual(s_hk241["relative_term"], 1)
        self.assertEqual(s_hk241["recommended_semester"], "HK1")
        self.assertEqual(s_hk241["status"], "NORMAL")

        s_hk242 = resolve_semester(24, "HK242")
        self.assertEqual(s_hk242["relative_term"], 2)
        self.assertEqual(s_hk242["recommended_semester"], "HK2")
        self.assertEqual(s_hk242["status"], "NORMAL")

        # Absolute semester for K23 at HK241 (Semester 3)
        s_k23_241 = resolve_semester(23, "HK241")
        self.assertEqual(s_k23_241["relative_term"], 3)
        self.assertEqual(s_k23_241["recommended_semester"], "HK3")
        self.assertEqual(s_k23_241["status"], "NORMAL")

        # Before enrollment
        s_early = resolve_semester(24, "HK232")
        self.assertEqual(s_early["status"], "NOT_ENROLLED")

        # Beyond standard duration
        s_late = resolve_semester(20, "HK242")
        self.assertEqual(s_late["status"], "BEYOND_STANDARD_DURATION")

    def test_get_curriculum_for_cohort_semester_k24(self):
        # K24 at HK1
        res_hk1 = get_curriculum_for_cohort_semester("K24", "HK241")
        self.assertEqual(res_hk1["cohort"], "K24")
        self.assertEqual(res_hk1["relative_semester"], 1)
        self.assertEqual(res_hk1["status"], "NORMAL")
        self.assertEqual(res_hk1["total_compulsory_credits"], 16.0)

        codes = [c["course_code"] for c in res_hk1["compulsory_courses"]]
        self.assertIn("MT1003", codes)
        self.assertIn("PH1003", codes)
        self.assertIn("CO1005", codes)
        self.assertIn("LA1003", codes)
        self.assertIn("CO1023", codes)

        # K24 at HK2 (Check prerequisites)
        res_hk2 = get_curriculum_for_cohort_semester("K24", "HK242")
        self.assertEqual(res_hk2["relative_semester"], 2)
        self.assertEqual(res_hk2["total_compulsory_credits"], 17.0)

        mt1005 = next(
            c for c in res_hk2["compulsory_courses"] if c["course_code"] == "MT1005"
        )
        self.assertTrue(any(p["prerequisite_course_code"] == "MT1003" for p in mt1005["prerequisites"]))

    def test_inherited_cohort_k25_k26(self):
        # K25 and K26 share K24 base curriculum
        res_k25 = get_curriculum_for_cohort_semester("K25", "HK251")
        self.assertEqual(res_k25["status"], "NORMAL")
        self.assertEqual(res_k25["relative_semester"], 1)
        self.assertEqual(res_k25["total_compulsory_credits"], 16.0)

        res_k26 = get_curriculum_for_cohort_semester("K26", "HK261")
        self.assertEqual(res_k26["status"], "NORMAL")
        self.assertEqual(res_k26["relative_semester"], 1)
        self.assertEqual(res_k26["total_compulsory_credits"], 16.0)

    def test_numeric_term_lookup(self):
        # Direct term number 1..8
        res1 = get_curriculum_for_cohort_semester("K24", 1)
        self.assertEqual(res1["relative_semester"], 1)
        self.assertEqual(res1["recommended_semester"], "HK1")
        self.assertEqual(res1["total_compulsory_credits"], 16.0)

        # Using term shorthand function
        from analysis_helpers import get_curriculum_for_cohort_term
        res2 = get_curriculum_for_cohort_term("K24", 2)
        self.assertEqual(res2["relative_semester"], 2)
        self.assertEqual(res2["recommended_semester"], "HK2")
        self.assertEqual(res2["total_compulsory_credits"], 17.0)

        # String digit '3'
        res3 = get_curriculum_for_cohort_term("K24", "3")
        self.assertEqual(res3["relative_semester"], 3)
        self.assertEqual(res3["recommended_semester"], "HK3")

    def test_lecturer_course_mapping(self):
        from analysis_helpers import get_courses_by_lecturer, get_lecturers_by_course

        # Test lookup courses for math lecturer (GV00056)
        res_gv = get_courses_by_lecturer("GV00056")
        self.assertEqual(res_gv["department"], "Khoa Khoa học Ứng dụng - Bộ môn Toán ứng dụng")
        self.assertEqual(res_gv["total_qualified_courses"], 4)
        c_codes = [c["course_code"] for c in res_gv["qualified_courses"]]
        self.assertIn("MT1003", c_codes)
        self.assertIn("MT2013", c_codes)

        # Test reverse lookup lecturers for course (SP1031)
        res_c = get_lecturers_by_course("SP1031")
        self.assertEqual(res_c["department"], "Khoa Khoa học Ứng dụng - Bộ môn Lý luận Chính trị")
        self.assertEqual(res_c["total_eligible_lecturers"], 8)


if __name__ == "__main__":
    unittest.main()

