"""Unit tests for Student Academic History lookup and reporting."""

import sys
import unittest
from pathlib import Path

# Add analysis directory to path
ANALYSIS_DIR = Path(__file__).resolve().parents[1] / "analysis"
sys.path.insert(0, str(ANALYSIS_DIR))

from analysis_helpers import (
    format_student_history_report,
    get_student_academic_history,
)


class TestStudentAcademicHistory(unittest.TestCase):
    """Test student semester-by-semester history retrieval and reporting."""

    def test_lookup_by_mssv(self):
        res = get_student_academic_history("2028899")
        self.assertTrue(res["found"])
        self.assertEqual(res["student_id"], "2028899")
        self.assertEqual(res["cohort"], "K20")
        self.assertEqual(res["program"], "standard")
        self.assertIn("Nguyễn Quang Phúc", res["name"])
        self.assertGreaterEqual(res["summary"]["total_credits_enrolled"], 15)
        self.assertGreaterEqual(len(res["semesters"]), 1)

    def test_lookup_by_email(self):
        res = get_student_academic_history("nguyenquangphuc.2028899@hcmut.edu.vn")
        self.assertTrue(res["found"])
        self.assertEqual(res["student_id"], "2028899")

    def test_lookup_advanced_student_exemptions(self):
        res = get_student_academic_history("2031846")
        self.assertTrue(res["found"])
        self.assertEqual(res["program"], "advanced")
        self.assertEqual(res["summary"]["exempted_courses_count"], 4)
        # Check that exempted English courses are marked Exempted
        first_sem = res["semesters"][0]
        exempted_courses = [c for c in first_sem["courses"] if c["status"] == "Exempted"]
        self.assertEqual(len(exempted_courses), 4)
        for ec in exempted_courses:
            self.assertEqual(ec["final_score"], 12.0)
            self.assertIsNone(ec["gpa_4"])

    def test_lookup_not_found(self):
        res = get_student_academic_history("NONEXISTENT_9999999")
        self.assertFalse(res["found"])
        self.assertIn("Không tìm thấy", res["message"])
        report = format_student_history_report(res)
        self.assertIn("THÔNG BÁO", report)

    def test_report_formatting(self):
        res = get_student_academic_history("2028899")
        report = format_student_history_report(res)
        self.assertIn("HỒ SƠ & LỊCH SỬ HỌC TẬP TỪNG KỲ CỦA SINH VIÊN", report)
        self.assertIn("Nguyễn Quang Phúc", report)
        self.assertIn("2028899", report)
        self.assertIn("HK201", report)


if __name__ == "__main__":
    unittest.main()

