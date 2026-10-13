import sys
import unittest
from pathlib import Path

import pandas as pd


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from generate_academic_metrics import (
    _distribution_tables,
    _english_eligibility_metrics,
)


class AcademicMetricsTests(unittest.TestCase):
    def test_english_eligibility_metrics_show_rate_by_semester(self):
        progress = pd.DataFrame([
            {"semester": "HK131", "english_pass": False},
            {"semester": "HK131", "english_pass": True},
            {"semester": "HK132", "english_pass": True},
            {"semester": "HK132", "english_pass": True},
            {"semester": "HK132", "english_pass": False},
        ])

        result = _english_eligibility_metrics(progress).set_index("semester")

        self.assertEqual(result.loc["HK131", "eligible_students"], 1)
        self.assertEqual(result.loc["HK131", "tracked_students"], 2)
        self.assertEqual(result.loc["HK132", "eligible_students"], 2)
        self.assertEqual(result.loc["HK132", "tracked_students"], 3)
        self.assertAlmostEqual(result.loc["HK132", "rate"], 2 / 3)

    def test_score_and_letter_distributions_include_course_and_university(self):
        history = pd.DataFrame([
            {
                "course_code": "CO1001",
                "final_score": 9.7,
                "gpa_4": 4.0,
                "letter_grade": "A+",
            },
            {
                "course_code": "CO1001",
                "final_score": 6.5,
                "gpa_4": 2.5,
                "letter_grade": "C+",
            },
            {
                "course_code": "CO1002",
                "final_score": pd.NA,
                "gpa_4": pd.NA,
                "letter_grade": pd.NA,
            },
        ])

        scores, grades = _distribution_tables(history)

        self.assertEqual(set(scores["course_code"]), {"CO1001", "ALL_UNIVERSITY"})
        self.assertEqual(set(scores["scale"]), {"10-point", "4-point"})
        university_grades = grades[grades["course_code"] == "ALL_UNIVERSITY"]
        self.assertEqual(int(university_grades["count"].sum()), 2)
        self.assertAlmostEqual(float(university_grades["share"].sum()), 1.0)
        course_grades = grades[grades["course_code"] == "CO1001"]
        self.assertEqual(
            course_grades.set_index("letter_grade").loc["A+", "count"], 1
        )
        self.assertEqual(
            course_grades.set_index("letter_grade").loc["C+", "count"], 1
        )

    def test_cohort_summary_and_late_graduation_breakdown(self):
        analysis_dir = Path(__file__).resolve().parents[1] / "analysis"
        sys.path.insert(0, str(analysis_dir))
        from analysis_helpers import (
            summarize_cohort_results,
            view_early_graduation_distribution,
            view_late_graduation_distribution,
        )

        # Test K13 cohort
        res_k13 = summarize_cohort_results("K13", print_report=False)
        self.assertIsNotNone(res_k13)
        self.assertTrue(res_k13["has_metrics"])
        self.assertIn("early_info", res_k13)
        self.assertEqual(res_k13["early_info"]["semester_code"], "HK161")
        self.assertTrue(res_k13["early_info"]["has_occurred"])
        self.assertIn("late_by_semester", res_k13["graduated"])
        late_k13 = res_k13["graduated"]["late_by_semester"]
        self.assertEqual(list(late_k13.keys()), [9, 10, 11, 12])
        self.assertEqual(late_k13[9]["count"], 18)
        self.assertEqual(late_k13[10]["count"], 160)
        self.assertEqual(late_k13[11]["count"], 48)
        self.assertEqual(late_k13[12]["count"], 33)
        total_late = sum(late_k13[k]["count"] for k in [9, 10, 11, 12])
        self.assertEqual(total_late, res_k13["graduated"]["late_count"])
        self.assertEqual(total_late, 259)

        # Test dedicated late report function
        late_res = view_late_graduation_distribution("K13", print_report=False)
        self.assertIsNotNone(late_res)
        self.assertEqual(late_res["late_count"], 259)
        self.assertEqual(late_res["late_by_semester"][9]["semester_code"], "HK171")
        self.assertEqual(late_res["late_by_semester"][10]["semester_code"], "HK172")
        self.assertEqual(late_res["late_by_semester"][11]["semester_code"], "HK181")
        self.assertEqual(late_res["late_by_semester"][12]["semester_code"], "HK182")

        # Test dedicated early report function
        early_res = view_early_graduation_distribution("K13", print_report=False)
        self.assertIsNotNone(early_res)
        self.assertEqual(early_res["early_info"]["semester_code"], "HK161")
        self.assertTrue(early_res["early_info"]["has_occurred"])


if __name__ == "__main__":
    unittest.main()
