import sys
import unittest
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parents[1] / "analysis"
sys.path.insert(0, str(ANALYSIS_DIR))

from analysis_helpers import (
    format_cohort_graduation_report,
    get_cohort_graduation_analysis,
)


class CohortGraduationAnalysisTests(unittest.TestCase):
    def test_k20_graduation_analysis(self):
        res = get_cohort_graduation_analysis("K20")
        self.assertIsNotNone(res)
        self.assertEqual(res["cohort"], "K20")
        self.assertEqual(res["cohort_num"], 20)
        self.assertEqual(res["curriculum_id"], "KHMT_K20")
        self.assertEqual(res["total_students"], 1500)

        # Early graduation (Kỳ 7 - 3.5 năm)
        early = res["categories"]["early"]
        self.assertEqual(early["term"], 7)
        self.assertEqual(early["semester_code"], "HK231")
        self.assertEqual(early["count"], 18)
        self.assertAlmostEqual(early["percentage"], 1.20, places=2)
        self.assertEqual(early["status"], "SIMULATED")

        # On-time graduation (Kỳ 8 - 4.0 năm)
        ontime = res["categories"]["on_time"]
        self.assertEqual(ontime["term"], 8)
        self.assertEqual(ontime["semester_code"], "HK232")
        self.assertEqual(ontime["count"], 696)
        self.assertAlmostEqual(ontime["percentage"], 46.40, places=2)
        self.assertEqual(ontime["status"], "SIMULATED")

        # Late terms (9, 10, 11, 12)
        late_terms = res["categories"]["late_terms"]
        self.assertIn(9, late_terms)
        lt9 = late_terms[9]
        self.assertEqual(lt9["count"], 226)
        self.assertAlmostEqual(lt9["percentage"], 15.07, places=2)
        self.assertEqual(lt9["status"], "SIMULATED")

        self.assertIn(10, late_terms)
        lt10 = late_terms[10]
        self.assertEqual(lt10["count"], 184)
        self.assertAlmostEqual(lt10["percentage"], 12.27, places=2)
        self.assertEqual(lt10["status"], "SIMULATED")

        self.assertIn(11, late_terms)
        lt11 = late_terms[11]
        self.assertEqual(lt11["count"], 127)
        self.assertAlmostEqual(lt11["percentage"], 8.47, places=2)
        self.assertEqual(lt11["status"], "SIMULATED")

        self.assertIn(12, late_terms)
        lt12 = late_terms[12]
        self.assertEqual(lt12["count"], 76)
        self.assertAlmostEqual(lt12["percentage"], 5.07, places=2)
        self.assertEqual(lt12["status"], "SIMULATED")

        # Pending debt / unfulfilled English or CTXH
        pending = res["categories"]["pending"]
        self.assertEqual(pending["count"], 173)
        self.assertAlmostEqual(pending["percentage"], 11.53, places=2)

        # Total reconciliation
        total_grad = res["total_graduated"]
        self.assertEqual(total_grad, 1327)
        self.assertEqual(total_grad + pending["count"], res["total_students"])

        # Program breakdown
        by_prog = res["by_program"]
        self.assertIn("standard", by_prog)
        self.assertIn("high-quality", by_prog)
        self.assertIn("advanced", by_prog)

        std = by_prog["standard"]
        hq = by_prog["high-quality"]
        adv = by_prog["advanced"]

        self.assertEqual(std["total_students"], 895)
        self.assertEqual(std["early_count"], 9)
        self.assertEqual(std["ontime_count"], 373)
        self.assertEqual(std["late_9_count"], 130)
        self.assertEqual(std["pending_count"], 141)

        self.assertEqual(hq["total_students"], 443)
        self.assertEqual(hq["early_count"], 6)
        self.assertEqual(hq["ontime_count"], 243)
        self.assertEqual(hq["late_9_count"], 67)
        self.assertEqual(hq["pending_count"], 24)

        self.assertEqual(adv["total_students"], 162)
        self.assertEqual(adv["early_count"], 3)
        self.assertEqual(adv["ontime_count"], 80)
        self.assertEqual(adv["late_9_count"], 29)
        self.assertEqual(adv["pending_count"], 8)

        # Early graduates roster
        roster = res["early_graduates_roster"]
        self.assertEqual(len(roster), 18)
        for st in roster:
            self.assertTrue(st["student_id"].startswith("20"))
            self.assertGreaterEqual(st["base_score"], 8.5)
            self.assertIsNotNone(st["kltn_score"])
            self.assertEqual(st["kltn_semester"], "HK231")

    def test_k21_future_cohort_simulation_status(self):
        res = get_cohort_graduation_analysis("K21")
        self.assertIsNotNone(res)
        self.assertEqual(res["cohort"], "K21")
        self.assertEqual(res["latest_simulated_term"], 11)
        self.assertEqual(res["latest_simulated_semester"], "HK261")
        self.assertEqual(res["total_graduated"], 1282)
        self.assertEqual(res["categories"]["early"]["count"], 18)
        self.assertEqual(res["categories"]["early"]["status"], "SIMULATED")
        self.assertEqual(res["categories"]["on_time"]["count"], 708)
        self.assertEqual(res["categories"]["on_time"]["status"], "SIMULATED")
        self.assertEqual(res["categories"]["late_terms"][9]["count"], 242)
        self.assertEqual(res["categories"]["late_terms"][9]["status"], "SIMULATED")
        self.assertEqual(res["categories"]["late_terms"][10]["count"], 198)
        self.assertEqual(res["categories"]["late_terms"][10]["status"], "SIMULATED")
        self.assertEqual(res["categories"]["late_terms"][11]["count"], 116)
        self.assertEqual(res["categories"]["late_terms"][11]["status"], "SIMULATED")

    def test_k22_graduation_analysis(self):
        res = get_cohort_graduation_analysis("K22")
        self.assertIsNotNone(res)
        self.assertEqual(res["cohort"], "K22")
        self.assertEqual(res["latest_simulated_term"], 9)
        self.assertEqual(res["latest_simulated_semester"], "HK261")
        self.assertEqual(res["total_graduated"], 962)
        self.assertEqual(res["categories"]["early"]["count"], 19)
        self.assertEqual(res["categories"]["early"]["status"], "SIMULATED")
        self.assertEqual(res["categories"]["on_time"]["count"], 719)
        self.assertEqual(res["categories"]["on_time"]["status"], "SIMULATED")
        self.assertEqual(res["categories"]["late_terms"][9]["count"], 224)
        self.assertEqual(res["categories"]["late_terms"][9]["status"], "SIMULATED")
        self.assertEqual(res["categories"]["pending"]["count"], 597)

    def test_format_cohort_graduation_report(self):
        res = get_cohort_graduation_analysis("K20")
        report = format_cohort_graduation_report(res)
        self.assertIsInstance(report, str)
        self.assertIn("BÁO CÁO THỐNG KÊ TIẾN ĐỘ & TỶ LỆ TỐT NGHIỆP - KHÓA K20", report)
        self.assertIn("Tốt nghiệp sớm (Kỳ 7 - 3.5 năm)", report)
        self.assertIn("Tốt nghiệp đúng hạn (Kỳ 8 - 4.0 năm)", report)
        self.assertIn("Tốt nghiệp trễ hạn Kỳ 9", report)
        self.assertIn("Tốt nghiệp trễ hạn Kỳ 10", report)
        self.assertIn("Tốt nghiệp trễ hạn Kỳ 11", report)
        self.assertIn("Tốt nghiệp trễ hạn Kỳ 12", report)
        self.assertIn("DANH SÁCH SINH VIÊN TỐT NGHIỆP SỚM", report)


if __name__ == "__main__":
    unittest.main()

