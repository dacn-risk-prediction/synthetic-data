import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RULES_DIR = Path(__file__).resolve().parents[1] / "rules"
sys.path.insert(0, str(RULES_DIR))

from academic_rules import (
    DISMISSAL_AFTER_SEMESTERS,
    FREE_CREDIT_LIMIT,
    GENERATOR_CONFIG,
    GROUP_C_CREDIT_LIMIT,
    MAX_LATE_SEMESTERS,
    STANDARD_SEMESTERS,
    academic_dismissal_semesters,
    academic_suspension_semesters,
    add_gpa_summaries,
    allocate_course_rosters,
    assign_balanced_lecturers,
    balanced_class_sizes,
    calculate_eligibility_for_schedule,
    calculate_prerequisite_adjustment,
    clear_student_past_grades,
    convert_score_to_grade,
    course_mean_score,
    extract_student_academic_standing,
    filter_students_from_2013,
    generate_observed_score,
    generate_student_profile,
    get_academic_dismissal_semester,
    get_exempted_english_courses,
    get_late_semesters_count,
    is_academic_dismissal,
    is_english_passed,
    is_late_semester,
    is_thesis_eligible,
    score_course_components,
    set_student_past_grades,
    sync_class_teamwork_btl,
    select_early_graduation_candidates,
    semester_from_index,
    semester_index,
    students_by_course_from_eligibility,
    validate_generator_config,
    wants_acceleration,
    additional_courses,
)


class AcademicScoreRulesTests(unittest.TestCase):
    def test_cohort_filter_keeps_real_students_from_2013_onward(self):
        students = pd.DataFrame({
            "student_id": ["1210001", "1310001", "1610001", "2310001"],
            "name": ["old", "2013", "2016", "2023"],
        })

        result = filter_students_from_2013(students)

        self.assertEqual(
            result["student_id"].tolist(),
            ["1310001", "1610001", "2310001"],
        )

    def test_class_sections_are_balanced_and_respect_capacity(self):
        self.assertEqual(balanced_class_sizes(0), [])
        self.assertEqual(balanced_class_sizes(39), [39])
        self.assertEqual(balanced_class_sizes(120), [120])
        self.assertEqual(balanced_class_sizes(121), [61, 60])
        self.assertEqual(balanced_class_sizes(241), [81, 80, 80])

    def test_assign_balanced_lecturers_distributes_workload_evenly(self):
        lecturers = pd.DataFrame({
            "lecturer_id": ["GV01", "GV02", "GV03", "DC01", "DC02"],
            "lecturer_name": ["Prof 1", "Prof 2", "Prof 3", "Math 1", "Math 2"],
            "departments": ["ChuyenNganh", "ChuyenNganh", "ChuyenNganh", "DaiCuong", "DaiCuong"],
        })
        course_names = {
            "CO1001": "Prog 1",
            "CO1002": "Prog 2",
            "CO1003": "Prog 3",
            "CO1004": "Prog 4",
            "CO1005": "Prog 5",
            "CO1006": "Prog 6",
            "MT1001": "Calc 1",
            "MT1002": "Calc 2",
            "MT1003": "Calc 3",
            "MT1004": "Calc 4",
        }
        # 1 section per course (demand 50 <= 120)
        eligibility = {
            f"std_{i}": ["CO1001", "CO1002", "CO1003", "CO1004", "CO1005", "CO1006",
                         "MT1001", "MT1002", "MT1003", "MT1004"]
            for i in range(50)
        }
        course_order = list(course_names.keys())

        classes = assign_balanced_lecturers(
            course_order=course_order,
            eligibility=eligibility,
            lecturers=lecturers,
            course_names=course_names,
            semester="HK231",
        )

        self.assertEqual(len(classes), 10)
        # Check workload per lecturer
        assigned_lecturers = [c["lecturer_id"] for c in classes]
        # ChuyenNganh: 6 courses / 3 lecturers = 2 courses each
        self.assertEqual(assigned_lecturers.count("GV01"), 2)
        self.assertEqual(assigned_lecturers.count("GV02"), 2)
        self.assertEqual(assigned_lecturers.count("GV03"), 2)
        # DaiCuong: 4 courses / 2 lecturers = 2 courses each
        self.assertEqual(assigned_lecturers.count("DC01"), 2)
        self.assertEqual(assigned_lecturers.count("DC02"), 2)

    def test_assign_balanced_lecturers_supports_direct_demand_dict(self):
        lecturers = pd.DataFrame({
            "lecturer_id": ["DC01", "DC02"],
            "lecturer_name": ["Math 1", "Math 2"],
            "departments": ["DaiCuong", "DaiCuong"],
        })
        course_names = {"MT1001": "Calc 1", "MT1002": "Calc 2"}
        demands = {"MT1001": 240, "MT1002": 120}  # MT1001 has 2 sections, MT1002 has 1 section

        classes = assign_balanced_lecturers(
            course_order=["MT1001", "MT1002"],
            eligibility=demands,
            lecturers=lecturers,
            course_names=course_names,
            semester="HK131",
        )

        self.assertEqual(len(classes), 3)
        self.assertEqual(classes[0]["class_id"], "HK131_MT1001_L01")
        self.assertEqual(classes[1]["class_id"], "HK131_MT1001_L02")
        self.assertEqual(classes[2]["class_id"], "HK131_MT1002_L01")
        # DC01 gets section 1, DC02 gets section 2, then DC01 gets section 3
        assigned = [c["lecturer_id"] for c in classes]
        self.assertEqual(assigned, ["DC01", "DC02", "DC01"])

    def test_assign_balanced_lecturers_raises_on_missing_course(self):
        lecturers = pd.DataFrame({
            "lecturer_id": ["DC01"],
            "lecturer_name": ["Math 1"],
            "departments": ["DaiCuong"],
        })
        with self.assertRaises(ValueError) as ctx:
            assign_balanced_lecturers(
                course_order=["NONEXISTENT"],
                eligibility={"NONEXISTENT": 50},
                lecturers=lecturers,
                course_names={"MA1001": "Calc 1"},
                semester="HK131",
            )
        self.assertIn("Courses missing from course.csv: NONEXISTENT", str(ctx.exception))

    def test_course_rosters_assign_every_student_to_available_matching_classes(self):
        eligibility = {
            "2310001": ["CO1001", "CO1002"],
            "2310002": ["CO1001"],
            "2310003": ["CO1001"],
        }
        students_by_course = students_by_course_from_eligibility(eligibility)
        classes = pd.DataFrame({
            "class_id": ["CO1001-L01", "CO1002-L01"],
            "course_code": ["CO1001", "CO1002"],
        })

        rosters = allocate_course_rosters(students_by_course, classes)

        self.assertEqual(
            {
                course: [
                    student_id
                    for _, roster in assignments
                    for student_id in roster
                ]
                for course, assignments in rosters.items()
            },
            students_by_course,
        )
        self.assertTrue(all(
            len(roster) <= 120
            for assignments in rosters.values()
            for _, roster in assignments
        ))

    def test_course_roster_fails_when_available_classes_cannot_cover_demand(self):
        eligible = {"CO1001": [f"231{index:04d}" for index in range(121)]}
        classes = pd.DataFrame({
            "class_id": ["CO1001-L01"],
            "course_code": ["CO1001"],
        })

        with self.assertRaisesRegex(ValueError, "needs 2 classes"):
            allocate_course_rosters(eligible, classes)

    def test_course_roster_fails_when_an_eligible_course_has_no_class(self):
        with self.assertRaisesRegex(ValueError, "No existing class"):
            allocate_course_rosters(
                {"CO1001": ["2310001"]},
                pd.DataFrame(columns=["class_id", "course_code"]),
            )

    def test_profile_is_reproducible_and_within_configured_ranges(self):
        first = generate_student_profile("2310001")
        second = generate_student_profile("2310001")

        self.assertEqual(first, second)
        self.assertIsInstance(first["english_pass"], bool)
        self.assertEqual(
            first["english_eligibility_by_semester"],
            second["english_eligibility_by_semester"],
        )
        self.assertEqual(
            first["english_eligibility_by_semester"][0]["eligible"],
            first["english_pass"],
        )
        self.assertTrue(all(
            not earlier["eligible"] or later["eligible"]
            for earlier, later in zip(
                first["english_eligibility_by_semester"],
                first["english_eligibility_by_semester"][1:],
            )
        ))
        self.assertIsInstance(first["ctxh_days_by_semester"], list)
        self.assertTrue(all(
            earlier["cumulative_days"] <= later["cumulative_days"]
            for earlier, later in zip(
                first["ctxh_days_by_semester"],
                first["ctxh_days_by_semester"][1:],
            )
        ))
        for field in (
            "discipline",
            "motivation",
            "stress",
            "social_activity",
            "academic_level",
            "math_level",
            "english_level",
        ):
            self.assertIn(first[field], range(1, 6))

    def test_thesis_course_requires_english_and_prior_ctxh_days(self):
        history = pd.DataFrame(columns=[
            "student_id", "course_code", "semester", "status",
        ])
        prerequisites = pd.DataFrame(columns=[
            "course_code", "related_course_code", "relation_type",
        ])
        students = pd.DataFrame([
            {
                "student_id": "2310001",
                "base_score": 6.5,
                "english_pass": True,
                "ctxh_days_by_semester": [
                    {"semester": "HK231", "cumulative_days": 12},
                ],
            },
            {
                "student_id": "2310002",
                "base_score": 6.5,
                "english_pass": False,
                "ctxh_days_by_semester": [
                    {"semester": "HK231", "cumulative_days": 15},
                ],
            },
            {
                "student_id": "2310003",
                "base_score": 6.5,
                "english_pass": True,
                "ctxh_days_by_semester": [
                    {"semester": "HK231", "cumulative_days": 11},
                ],
            },
        ])
        thesis_pause_config = {
            **GENERATOR_CONFIG,
            "student_progress": {
                **GENERATOR_CONFIG["student_progress"],
                "graduation": {
                    **GENERATOR_CONFIG["student_progress"]["graduation"],
                    "ineligible_thesis_empty_semester_probability": 1.0,
                },
            },
        }

        eligible, _ = calculate_eligibility_for_schedule(
            students,
            history,
            {"CO4337": 4, "CO1001": 3},
            prerequisites,
            {"23": ["CO4337", "CO1001"]},
            {},
            semester_code="HK241",
            config=thesis_pause_config,
        )

        self.assertEqual(eligible, {
            "2310001": ["CO4337", "CO1001"],
            "2310002": [],
            "2310003": [],
        })

    def test_two_low_credit_terms_trigger_only_one_suspension_term(self):
        history = pd.DataFrame([
            {
                "student_id": "1310001",
                "course_code": "CO0001",
                "semester": semester_index("HK131"),
                "status": "Pass",
            },
            {
                "student_id": "1310001",
                "course_code": "CO0002",
                "semester": semester_index("HK132"),
                "status": "Pass",
            },
            {
                "student_id": "1310001",
                "course_code": "CO0003",
                "semester": semester_index("HK142"),
                "status": "Pass",
            },
        ])
        credits = {
            "CO0001": 5,
            "CO0002": 5,
            "CO0003": 5,
        }
        semesters = [
            "HK131", "HK132", "HK141", "HK142",
            "HK151", "HK152", "HK161",
        ]

        suspensions = academic_suspension_semesters(
            history, semesters, credits
        )

        self.assertEqual(suspensions, {"HK141", "HK152"})

    def test_suspended_student_cannot_enroll_then_can_resume_next_term(self):
        history = pd.DataFrame([
            {
                "student_id": "1310001",
                "course_code": "CO0001",
                "semester": semester_index("HK131"),
                "status": "Pass",
            },
            {
                "student_id": "1310001",
                "course_code": "CO0002",
                "semester": semester_index("HK132"),
                "status": "Pass",
            },
        ])
        students = pd.DataFrame([{
            "student_id": "1310001",
            "base_score": 6.5,
            "english_pass": True,
            "ctxh_days_by_semester": [],
        }])
        prerequisites = pd.DataFrame(columns=[
            "course_code", "related_course_code", "relation_type",
        ])
        credits = {
            "CO0001": 5,
            "CO0002": 5,
            "CO1001": 3,
        }
        scheduled = {"13": ["CO1001"]}

        paused, _ = calculate_eligibility_for_schedule(
            students,
            history,
            credits,
            prerequisites,
            scheduled,
            {},
            semester_code="HK141",
        )
        resumed, _ = calculate_eligibility_for_schedule(
            students,
            history,
            credits,
            prerequisites,
            scheduled,
            {},
            semester_code="HK142",
        )

        self.assertEqual(paused, {"1310001": []})
        self.assertEqual(resumed, {"1310001": ["CO1001"]})

    def test_stronger_profile_is_less_affected_by_course_difficulty(self):
        low_profile = {
            "student_id": "low",
            "academic_level": 1,
            "discipline": 1,
            "motivation": 1,
            "stress": 5,
        }
        high_profile = {
            "student_id": "high",
            "academic_level": 5,
            "discipline": 5,
            "motivation": 5,
            "stress": 1,
        }
        easy_config = {
            **GENERATOR_CONFIG,
            "difficulty": {
                **GENERATOR_CONFIG["difficulty"],
                "course_overrides": {"CO9999": 1.0},
            },
        }
        hard_config = {
            **GENERATOR_CONFIG,
            "difficulty": {
                **GENERATOR_CONFIG["difficulty"],
                "course_overrides": {"CO9999": -1.0},
            },
        }

        low_change = course_mean_score(
            low_profile, "CO9999", 0, hard_config
        ) - course_mean_score(low_profile, "CO9999", 0, easy_config)
        high_change = course_mean_score(
            high_profile, "CO9999", 0, hard_config
        ) - course_mean_score(high_profile, "CO9999", 0, easy_config)

        self.assertLess(abs(high_change), abs(low_change))

    def test_positive_difficulty_adds_points_and_negative_penalizes(self):
        profile = {
            "student_id": "test_student",
            "academic_level": 3,
            "discipline": 3,
            "motivation": 3,
            "stress": 3,
        }
        bonus_config = {
            **GENERATOR_CONFIG,
            "difficulty": {
                **GENERATOR_CONFIG["difficulty"],
                "course_overrides": {"CO_EASY": 0.5},
            },
        }
        penalty_config = {
            **GENERATOR_CONFIG,
            "difficulty": {
                **GENERATOR_CONFIG["difficulty"],
                "course_overrides": {"CO_HARD": -0.5},
            },
        }
        neutral_score = course_mean_score(profile, "CO_NORM", 0.0, GENERATOR_CONFIG)
        bonus_score = course_mean_score(profile, "CO_EASY", 0.0, bonus_config)
        penalty_score = course_mean_score(profile, "CO_HARD", 0.0, penalty_config)

        self.assertGreater(bonus_score, neutral_score, "Positive difficulty must add points")
        self.assertLess(penalty_score, neutral_score, "Negative difficulty must reduce points")

    def test_grade_boundaries_are_lower_inclusive(self):
        cases = {
            3.99: ("F", 0.0),
            4.0: ("D", 1.0),
            5.0: ("D+", 1.5),
            5.5: ("C", 2.0),
            6.4: ("C+", 2.5),
            7.0: ("B", 3.0),
            8.0: ("B+", 3.5),
            8.5: ("A", 4.0),
            9.5: ("A+", 4.0),
            10.0: ("A+", 4.0),
        }
        for score, expected in cases.items():
            with self.subTest(score=score):
                self.assertEqual(convert_score_to_grade(score), expected)

    def test_scores_are_clipped_and_gpa_summaries_are_credit_weighted(self):
        rng = np.random.default_rng(42)
        scores = [
            generate_observed_score(6.0, rng)
            for _ in range(1000)
        ]
        self.assertTrue(all(0 <= score <= 10 for score in scores))

        history = pd.DataFrame([{
            "student_id": "s1",
            "course_code": "CO1001",
            "final_score": 8.5,
        }])
        current = pd.DataFrame([
            {
                "student_id": "s1",
                "course_id": "CO1002",
                "final_score": 3.9,
                "gpa_4": 0.0,
            },
            {
                "student_id": "s1",
                "course_id": "CO1003",
                "final_score": 4.5,
                "gpa_4": 1.0,
            },
        ])

        result = add_gpa_summaries(
            current,
            history,
            {"CO1001": 3, "CO1002": 3, "CO1003": 3},
        )

        self.assertEqual(result["semester_gpa_4"].tolist(), [0.5, 0.5])
        self.assertEqual(result["final_gpa_4"].tolist(), [2.5, 2.5])

    def test_zero_credit_pass_does_not_divide_by_zero_in_cumulative_gpa(self):
        result = add_gpa_summaries(
            pd.DataFrame([{
                "student_id": "s1",
                "course_id": "CO0000",
                "final_score": 8.5,
                "gpa_4": 4.0,
            }]),
            pd.DataFrame(columns=["student_id", "course_code", "final_score"]),
            {"CO0000": 0},
        )

    def test_exempted_english_courses_exempts_all_when_english_pass_is_true(self):
        student = {"student_id": "1300001", "english_pass": True, "english_level": 2}
        exempted = get_exempted_english_courses(student)
        self.assertEqual(exempted, {"LA1003", "LA1005", "LA1007", "LA1009"})

    def test_exempted_english_courses_placement_when_english_pass_is_false(self):
        # Level 1 student never skips more than LA1003 and never skips LA1009
        student_l1 = {"student_id": "1300002", "english_pass": False, "english_level": 1}
        exempted_l1 = get_exempted_english_courses(student_l1)
        self.assertTrue(exempted_l1.issubset({"LA1003"}))
        self.assertNotIn("LA1009", exempted_l1)

        # Level 5 student skips early courses but still must learn LA1009
        student_l5 = {"student_id": "1300003", "english_pass": False, "english_level": 5}
        exempted_l5 = get_exempted_english_courses(student_l5)
        self.assertEqual(exempted_l5, {"LA1003", "LA1005", "LA1007"})
        self.assertNotIn("LA1009", exempted_l5)

    def test_calculate_eligibility_exempted_english_satisfies_prerequisites(self):
        # Student exempt from LA1003: LA1003 should not be scheduled, but LA1005 can be scheduled
        students = pd.DataFrame([{
            "student_id": "1300003",
            "base_score": 6.5,
            "english_pass": False,
            "english_level": 5,  # skips LA1003, LA1005, LA1007
        }])
        history = pd.DataFrame(columns=["student_id", "course_code", "status"])
        prerequisites = pd.DataFrame([
            {"course_code": "LA1005", "related_course_code": "LA1003", "relation_type": "TQ"},
            {"course_code": "LA1009", "related_course_code": "LA1007", "relation_type": "TQ"},
        ])
        credits = {"LA1003": 2, "LA1005": 2, "LA1009": 2}
        scheduled = {"13": ["LA1003", "LA1009"]}

        eligible, _ = calculate_eligibility_for_schedule(
            students,
            history,
            credits,
            prerequisites,
            scheduled,
            {},
            semester_code="HK142",
        )
        # LA1003 was exempted so not in eligible; LA1009 had prerequisite LA1007 which was exempted, so satisfied!
        self.assertNotIn("LA1003", eligible["1300003"])
        self.assertIn("LA1009", eligible["1300003"])

    def test_student_switches_course_type_when_elective_limit_reached(self):
        # Student 1310001 has passed 15 credits of GROUP_C courses
        # and needs to register courses for the semester
        students = pd.DataFrame([{
            "student_id": "1310001",
            "base_score": 7.0,
            "english_pass": True,
        }])
        # 5 courses * 3 credits = 15 credits from actual GROUP_C courses
        passed_group_c = ["CO3011", "CO3013", "CO3015", "CO3017", "CO3021"]
        history = pd.DataFrame([
            {"student_id": "1310001", "course_code": code, "status": "Pass"}
            for code in passed_group_c
        ])
        prerequisites = pd.DataFrame(columns=["course_code", "related_course_code", "relation_type"])
        credits = {code: 3 for code in passed_group_c}
        credits.update({"CO3023": 3, "CO3027": 3, "IM1011": 3, "IM1021": 3, "EXTRA01": 3})

        free_candidates = ["IM1011", "IM1021"]
        group_c_candidates = ["CO3023", "CO3027"]

        eligible, _ = calculate_eligibility_for_schedule(
            students,
            history,
            credits,
            prerequisites,
            {"13": []},
            {"13": ["EXTRA01"]},
            {"13": {"FREE": free_candidates, "GROUP_C": group_c_candidates}},
            {"13": {"FREE": free_candidates, "GROUP_C": group_c_candidates}},
            semester_code="HK161",
        )

        selected = eligible["1310001"]
        # Since student already passed 15 credits of GROUP_C, no more GROUP_C should be selected!
        for c in group_c_candidates:
            self.assertNotIn(c, selected)
        # FREE candidates should be selected instead
        self.assertTrue(any(c in selected for c in free_candidates))

        # Scenario 2: Student has passed BOTH 15 credits of GROUP_C AND 9 credits of FREE
        passed_both = passed_group_c + ["IM1011", "IM1021", "IM1019"]
        history_both = pd.DataFrame([
            {"student_id": "1310001", "course_code": code, "status": "Pass"}
            for code in passed_both
        ])
        credits.update({"IM1019": 3})
        eligible_both, _ = calculate_eligibility_for_schedule(
            students,
            history_both,
            credits,
            prerequisites,
            {"13": []},
            {"13": ["EXTRA01"]},
            {"13": {"FREE": free_candidates, "GROUP_C": group_c_candidates}},
            {"13": {"FREE": free_candidates, "GROUP_C": group_c_candidates}},
            semester_code="HK161",
        )
        selected_both = eligible_both["1310001"]
        # No FREE and no GROUP_C should be selected!
        for c in group_c_candidates + free_candidates:
            self.assertNotIn(c, selected_both)
        # Other course type (EXTRA01) should be selected instead!
        self.assertIn("EXTRA01", selected_both)

    def test_constants_and_semester_from_index(self):
        self.assertEqual(STANDARD_SEMESTERS, 8)
        self.assertEqual(MAX_LATE_SEMESTERS, 4)
        self.assertEqual(DISMISSAL_AFTER_SEMESTERS, 12)

        self.assertEqual(semester_from_index(1), "HK131")
        self.assertEqual(semester_from_index(8), "HK162")
        self.assertEqual(semester_from_index(13), "HK191")

        for year in range(13, 26):
            for term in (1, 2):
                code = f"HK{year}{term}"
                self.assertEqual(semester_from_index(semester_index(code)), code)

    def test_late_semesters_count(self):
        # Student K13 starts at HK131
        student_id = "1310001"
        # Semesters 1-8: standard duration, late count = 0
        self.assertEqual(get_late_semesters_count(student_id, "HK131"), 0)
        self.assertEqual(get_late_semesters_count(student_id, "HK162"), 0)

        # Semesters 9-12: allowed late semesters (1 to 4)
        self.assertEqual(get_late_semesters_count(student_id, "HK171"), 1)
        self.assertEqual(get_late_semesters_count(student_id, "HK172"), 2)
        self.assertEqual(get_late_semesters_count(student_id, "HK181"), 3)
        self.assertEqual(get_late_semesters_count(student_id, "HK182"), 4)

        # Semester 13: exceeding 12 semesters (late count = 5)
        self.assertEqual(get_late_semesters_count(student_id, "HK191"), 5)

        # Unknown cohort returns 0
        self.assertEqual(get_late_semesters_count("9910001", "HK191"), 0)

    def test_academic_dismissal_logic(self):
        student_id = "1310001"
        # Semesters 1-12: NOT dismissed
        for sem in ["HK131", "HK141", "HK151", "HK161", "HK162", "HK171", "HK172", "HK181", "HK182"]:
            self.assertFalse(
                is_academic_dismissal(student_id, sem),
                f"Student should not be dismissed at {sem}",
            )

        # Semester 13+ (HK191 onward): Dismissed
        self.assertTrue(is_academic_dismissal(student_id, "HK191"))
        self.assertTrue(is_academic_dismissal(student_id, "HK192"))

        # Dismissal trigger semester
        self.assertEqual(get_academic_dismissal_semester(student_id), "HK191")
        self.assertEqual(get_academic_dismissal_semester("1610001"), "HK221")
        self.assertIsNone(get_academic_dismissal_semester("9910001"))

        # academic_dismissal_semesters set filtering
        sems = ["HK162", "HK182", "HK191", "HK192"]
        self.assertEqual(
            academic_dismissal_semesters(student_id, sems),
            {"HK191", "HK192"},
        )

    def test_calculate_eligibility_blocks_dismissed_student(self):
        students = pd.DataFrame([{
            "student_id": "1310001",
            "base_score": 7.0,
            "voluntary_dropout_semester": "",
            "english_pass": True,
            "ctxh_days": 15,
        }])
        history = pd.DataFrame(columns=["student_id", "course_code", "status"])
        credits = {"CO1001": 3}
        prerequisites = pd.DataFrame(
            columns=["course_code", "related_course_code", "relation_type"]
        )
        scheduled = {"13": ["CO1001"]}

        # Semester 12 (HK182): Still eligible
        eligible_12, _ = calculate_eligibility_for_schedule(
            students,
            history,
            credits,
            prerequisites,
            {"13": []},
            scheduled,
            {"13": {}},
            {"13": {}},
            semester_code="HK182",
        )
        self.assertEqual(eligible_12["1310001"], ["CO1001"])

        # Semester 13 (HK191): Exceeds 12 semesters -> blocked / dismissed
        eligible_13, _ = calculate_eligibility_for_schedule(
            students,
            history,
            credits,
            prerequisites,
            {"13": []},
            scheduled,
            {"13": {}},
            {"13": {}},
            semester_code="HK191",
        )
        self.assertEqual(eligible_13["1310001"], [])

    def test_is_late_semester(self):
        student_id = "1310001"
        # Semesters 1-8: Not late (standard time)
        for sem in ["HK131", "HK141", "HK151", "HK161", "HK162"]:
            self.assertFalse(is_late_semester(student_id, sem))

        # Semesters 9-12: Late within allowed window (1 to 4 late semesters)
        for sem in ["HK171", "HK172", "HK181", "HK182"]:
            self.assertTrue(is_late_semester(student_id, sem))

        # Semester 13: Exceeds allowed window (>4 late semesters -> dismissed)
        self.assertFalse(is_late_semester(student_id, "HK191"))

    def test_config_contains_constants_and_validation(self):
        progress = GENERATOR_CONFIG["student_progress"]
        self.assertEqual(progress["graduation"]["max_late_semesters"], 4)
        self.assertEqual(progress["electives"]["free_credit_limit"], 9)
        self.assertEqual(progress["electives"]["group_c_credit_limit"], 15)
        self.assertEqual(progress["enrollment_policy"]["optional_threshold"], 15)
        self.assertEqual(progress["enrollment_policy"]["acceleration_base_score"], 8.0)

        # Fallbacks in code
        self.assertEqual(FREE_CREDIT_LIMIT, 9)
        self.assertEqual(GROUP_C_CREDIT_LIMIT, 15)

        # Validation checks
        import copy
        bad_config = copy.deepcopy(GENERATOR_CONFIG)
        bad_config["student_progress"]["electives"]["free_credit_limit"] = -1
        with self.assertRaisesRegex(ValueError, "Invalid electives configuration"):
            validate_generator_config(bad_config)

        bad_policy = copy.deepcopy(GENERATOR_CONFIG)
        bad_policy["student_progress"]["enrollment_policy"]["acceleration_probability"] = 1.5
        with self.assertRaisesRegex(ValueError, "Invalid enrollment policy configuration"):
            validate_generator_config(bad_policy)

    def test_early_graduation_selection_is_stable_and_limited_to_top_one_percent(self):
        profiles = [
            {
                "student_id": f"23{index:05d}",
                "academic_level": 5 if index < 100 else 1,
                "discipline": 5,
                "motivation": 5,
                "stress": 1,
                "social_activity": 5,
            }
            for index in range(10000)
        ]
        profiles.append({
            "student_id": "1210001",
            "academic_level": 5,
            "discipline": 5,
            "motivation": 5,
            "stress": 1,
            "social_activity": 5,
        })

        selected = select_early_graduation_candidates(profiles)

        self.assertEqual(len(selected), 5)
        self.assertTrue(all(
            student_id.startswith(tuple(str(c) for c in range(13, 27)))
            for student_id in selected
        ))
        self.assertEqual(selected, select_early_graduation_candidates(profiles))
        self.assertTrue(selected.issubset({
            profile["student_id"] for profile in profiles[:100]
        }))

    def test_early_courses_are_cohort_scoped_and_injected_only_for_candidates(self):
        self.assertEqual(
            additional_courses(
                "HK7",
                early_graduation=True,
                early_graduation_only=True,
                cohort="23",
            ),
            ["CO4337", "SP1007"],
        )
        self.assertEqual(
            additional_courses(
                "HK7",
                early_graduation=True,
                early_graduation_only=True,
                cohort="12",
            ),
            [],
        )

        students = pd.DataFrame([
            {
                "student_id": "2310001",
                "base_score": 9.0,
                "voluntary_dropout_semester": "",
                "english_pass": True,
                "ctxh_days_by_semester": (
                    '[{"semester":"HK252","cumulative_days":15}]'
                ),
                "early_graduation_candidate": True,
            },
            {
                "student_id": "2310002",
                "base_score": 9.0,
                "voluntary_dropout_semester": "",
                "english_pass": True,
                "ctxh_days_by_semester": (
                    '[{"semester":"HK252","cumulative_days":15}]'
                ),
                "early_graduation_candidate": False,
            },
        ])
        history = pd.DataFrame([
            {"student_id": student_id, "course_code": course_code, "status": "pass"}
            for student_id in students["student_id"]
            for course_code in ("CO3335", "CO4029")
        ])
        credits = {"SP1037": 2, "CO4029": 2, "CO4337": 4, "SP1007": 2}
        prerequisites = pd.DataFrame([
            {"course_code": "CO4337", "related_course_code": "CO3335", "relation_type": "TQ"},
            {"course_code": "CO4337", "related_course_code": "CO4029", "relation_type": "TQ"},
        ])
        config = GENERATOR_CONFIG.copy()
        config["student_progress"] = GENERATOR_CONFIG["student_progress"].copy()
        config["student_progress"]["graduation"] = (
            GENERATOR_CONFIG["student_progress"]["graduation"].copy()
        )
        config["student_progress"]["graduation"][
            "minimum_passed_credits_per_semester"
        ] = 0
        eligible, _ = calculate_eligibility_for_schedule(
            students,
            history,
            credits,
            prerequisites,
            {"23": ["SP1037", "CO4029"]},
            {"23": {}},
            semester_code="HK261",
            config=config,
        )

        self.assertIn("CO4337", eligible["2310001"])
        self.assertIn("SP1007", eligible["2310001"])
        self.assertNotIn("CO4337", eligible["2310002"])
        self.assertNotIn("SP1007", eligible["2310002"])

    def test_custom_config_overrides_electives_and_acceleration(self):
        import copy
        custom_config = copy.deepcopy(GENERATOR_CONFIG)
        # Raise acceleration score requirement to 9.5
        custom_config["student_progress"]["enrollment_policy"]["acceleration_base_score"] = 9.5
        # Student with score 8.5 does NOT get acceleration under this custom config
        self.assertFalse(wants_acceleration("1310001", 8.5, custom_config))

    def test_is_english_passed_satisfied_by_profile_or_curriculum(self):
        # 1. Profile english_pass True -> always True
        student_exempt = {"student_id": "1300001", "english_pass": True}
        self.assertTrue(is_english_passed(student_exempt))

        # 2. Level 5 skips 1003, 1005, 1007. Needs LA1009.
        student_l5 = {"student_id": "1300003", "english_pass": False, "english_level": 5}
        self.assertFalse(is_english_passed(student_l5, set()))
        self.assertFalse(is_english_passed(student_l5, {"LA1003"}))
        self.assertTrue(is_english_passed(student_l5, {"LA1009"}))

        # 3. Level 1 skips none. Needs all 4.
        student_l1 = {"student_id": "1300002", "english_pass": False, "english_level": 1}
        exempted_l1 = get_exempted_english_courses(student_l1)
        needed = {"LA1003", "LA1005", "LA1007", "LA1009"} - exempted_l1
        self.assertFalse(is_english_passed(student_l1, {"LA1003"}))
        self.assertTrue(is_english_passed(student_l1, needed))

    def test_english_eligibility_switches_on_and_is_used_per_semester(self):
        student = {
            "student_id": "1300001",
            "english_pass": False,
            "english_level": 1,
            "english_eligibility_by_semester": (
                '[{"semester":"HK131","eligible":false},'
                '{"semester":"HK132","eligible":true},'
                '{"semester":"HK141","eligible":true}]'
            ),
        }

        self.assertFalse(is_english_passed(student, set(), semester_code="HK131"))
        self.assertFalse(is_english_passed(student, set(), semester_code="HK132", before=True))
        self.assertTrue(is_english_passed(student, set(), semester_code="HK132"))
        self.assertTrue(is_english_passed(student, set(), semester_code="HK141"))
        initial_english_exemptions = get_exempted_english_courses({
            "student_id": "1300001",
            "english_pass": False,
            "english_level": 1,
        })
        self.assertEqual(
            get_exempted_english_courses(student, semester_code="HK131"),
            initial_english_exemptions,
        )
        self.assertEqual(
            get_exempted_english_courses(student, semester_code="HK132"),
            {"LA1003", "LA1005", "LA1007", "LA1009"},
        )
        self.assertEqual(
            get_exempted_english_courses(student),
            {"LA1003", "LA1005", "LA1007", "LA1009"},
        )

    def test_english_eligibility_progression_can_be_configured_to_switch(self):
        import copy

        config = copy.deepcopy(GENERATOR_CONFIG)
        english = config["student_progress"]["english"]
        for key in (
            "base_probability",
            "background_weight",
            "english_skill_weight",
            "academic_weight",
            "personality_weight",
        ):
            english[key] = 0
        english["transition"] = {
            "base_probability": 1,
            "background_weight": 0,
            "english_skill_weight": 0,
            "academic_weight": 0,
            "personality_weight": 0,
        }

        profile = generate_student_profile("1300001", config)

        self.assertFalse(profile["english_pass"])
        self.assertFalse(profile["english_eligibility_by_semester"][0]["eligible"])
        self.assertTrue(profile["english_eligibility_by_semester"][1]["eligible"])
        self.assertTrue(all(
            entry["eligible"]
            for entry in profile["english_eligibility_by_semester"][1:]
        ))

    def test_transitioned_english_eligibility_allows_thesis_next_semester(self):
        students = pd.DataFrame([{
            "student_id": "1397004",
            "base_score": 7.0,
            "english_pass": False,
            "english_level": 1,
            "english_eligibility_by_semester": [
                {"semester": "HK131", "eligible": False},
                {"semester": "HK132", "eligible": True},
            ],
            "ctxh_days_by_semester": [
                {"semester": "HK131", "cumulative_days": 15},
            ],
        }])
        history = pd.DataFrame(columns=[
            "student_id", "course_code", "semester", "status",
        ])
        prerequisites = pd.DataFrame(columns=[
            "course_code", "related_course_code", "relation_type",
        ])

        eligible, _ = calculate_eligibility_for_schedule(
            students,
            history,
            {"CO4029": 2},
            prerequisites,
            {"13": ["CO4029"]},
            {},
            semester_code="HK141",
        )

        self.assertEqual(eligible["1397004"], ["CO4029"])

    def test_thesis_eligible_when_student_passed_english_courses(self):
        students = pd.DataFrame([{
            "student_id": "1397003",
            "base_score": 7.0,
            "english_pass": False,
            "english_level": 5, # skips 1003, 1005, 1007
            "ctxh_days_by_semester": [
                {"semester": "HK161", "cumulative_days": 15},
            ],
        }])
        history = pd.DataFrame([{
            "student_id": "1397003",
            "course_code": "LA1009",
            "status": "Pass",
        }])
        credits = {"CO4029": 4, "LA1009": 2}
        prerequisites = pd.DataFrame(columns=["course_code", "related_course_code", "relation_type"])
        scheduled = {"13": ["CO4029"]}

        eligible, _ = calculate_eligibility_for_schedule(
            students,
            history,
            credits,
            prerequisites,
            scheduled,
            {},
            semester_code="HK162",
        )
        self.assertEqual(eligible["1397003"], ["CO4029"])

    def test_graduation_phase_semesters_exempt_from_low_credit_suspension(self):
        # K13 student has < 11 credits in HK161 (sem 7) and HK162 (sem 8)
        history = pd.DataFrame([
            {"student_id": "1310001", "course_code": "CO4029", "semester": semester_index("HK161"), "status": "Pass"},
            {"student_id": "1310001", "course_code": "CO4337", "semester": semester_index("HK162"), "status": "Pass"},
        ])
        credits = {"CO4029": 4, "CO4337": 4}
        semesters = [
            "HK131", "HK132", "HK141", "HK142",
            "HK151", "HK152", "HK161", "HK162", "HK171",
        ]
        suspensions = academic_suspension_semesters(history, semesters, credits)
        # Should NOT be suspended in HK171 because sem 7 & 8 are graduation phase
        self.assertNotIn("HK171", suspensions)

    def test_pe_sport_pairs_completeness(self):
        """Test physical education sport pairs, bijection, and naming."""
        from academic_rules import SPORT_PAIRS, REVERSE_SPORT_PAIRS, HP1_SPORTS, HP2_SPORTS, SPORT_NAMES
        self.assertEqual(len(SPORT_PAIRS), 12, "Must define exactly 12 sport pairs")
        self.assertEqual(len(REVERSE_SPORT_PAIRS), 12, "Reverse mapping must have 12 pairs")
        self.assertEqual(len(HP1_SPORTS), 12)
        self.assertEqual(len(HP2_SPORTS), 12)
        self.assertTrue(set(HP1_SPORTS).isdisjoint(set(HP2_SPORTS)), "HP1 and HP2 courses must be disjoint")
        for hp1, hp2 in SPORT_PAIRS.items():
            self.assertIn(hp1, SPORT_NAMES)
            self.assertIn(hp2, SPORT_NAMES)
            self.assertEqual(REVERSE_SPORT_PAIRS[hp2], hp1)

    def test_pe_student_continuity(self):
        """Test that HP2 sport strictly matches HP1 sport for each student."""
        from academic_rules import assign_student_hp1_sport, get_student_hp2_sport, SPORT_PAIRS
        # Synthetic freshmen student IDs
        test_ids = [f"231{i:04d}" for i in range(100)]
        for sid in test_ids:
            hp1 = assign_student_hp1_sport(sid)
            hp2 = get_student_hp2_sport(sid)
            self.assertEqual(SPORT_PAIRS[hp1], hp2, f"Student {sid} HP2 must match HP1 sport pair")

            # Also test when historical enrollment record is provided
            prev_df = pd.DataFrame([{"student_id": sid, "course_id": hp1}])
            hp2_from_history = get_student_hp2_sport(sid, prev_df)
            self.assertEqual(hp2_from_history, hp2)

    def test_pe_assessment_cuoi_ky_only(self):
        """Test that PE enrollment generates 100% cuoi_ky score with zero/nan other components."""
        from academic_rules import (
            build_pe_classes_for_semester,
            build_pe_enrollments_for_semester,
        )
        students = pd.DataFrame([
            {"user_id": f"231{i:04d}", "program": "standard"} for i in range(120)
        ])
        lecturers = [
            {"user_id": "GV00206", "name": "Vũ Khánh Minh", "department": "Bộ môn Giáo dục Thể chất"},
            {"user_id": "GV00207", "name": "Hồ Thị An", "department": "Bộ môn Giáo dục Thể chất"},
        ]
        assigned_count = {"GV00206": 0, "GV00207": 0}
        prog_cfg = {"standard": {"prefix": "L"}}
        classes, sport_map = build_pe_classes_for_semester(
            semester="HK231",
            term_type=1,
            freshmen_df=students,
            lecturers=lecturers,
            assigned_count=assigned_count,
            program_config=prog_cfg,
        )
        self.assertGreater(len(classes), 0)
        for cl in classes:
            self.assertLessEqual(cl["max_capacity"], 40)

        enrs = build_pe_enrollments_for_semester(
            semester="HK231",
            term_type=1,
            freshmen_df=students,
            pe_classes=classes,
            student_sport_map=sport_map,
            student_profiles={f"231{i:04d}": {} for i in range(120)},
            start_enrollment_id=1,
            config=GENERATOR_CONFIG,
        )
        self.assertEqual(len(enrs), 120, "All 120 students must be enrolled in PE")
        for rec in enrs:
            self.assertTrue(pd.isna(rec["quiz"]))
            self.assertTrue(pd.isna(rec["lab"]))
            self.assertTrue(pd.isna(rec["btl"]))
            self.assertTrue(pd.isna(rec["giua_ky"]))
            self.assertFalse(pd.isna(rec["cuoi_ky"]))
            self.assertEqual(rec["cuoi_ky"], rec["final_score"])

    def test_score_course_components_applies_component_shifts(self):
        # Student with fixed ability (academic_level 4, etc.)
        student = {
            "student_id": "2110001",
            "academic_level": 4,
            "discipline": 3,
            "motivation": 3,
            "stress": 3,
            "social_activity": 3,
        }
        components = [
            ("quiz", 0.1),
            ("lab", 0.2),
            ("btl", 0.2),
            ("giua_ky", 0.2),
            ("cuoi_ky", 0.3),
        ]
        # Simulate across 200 random seeds
        comp_totals = {c[0]: 0.0 for c in components}
        n = 200
        for i in range(n):
            rng = np.random.default_rng(i + 1000)
            scores, final_score, _, _ = score_course_components(
                student=student,
                course_code="CO2001",
                components=components,
                catalog_difficulty=0.0,
                rng=rng,
                config=GENERATOR_CONFIG,
            )
            for c, s in scores.items():
                comp_totals[c] += s
        means = {c: comp_totals[c] / n for c in comp_totals}
        # In generator_config: shifts are lab=+0.8, btl=+1.0, giua_ky=0.0, cuoi_ky=-0.6
        # Therefore mean(btl) > mean(giua_ky) > mean(cuoi_ky)
        self.assertGreater(means["btl"], means["giua_ky"])
        self.assertGreater(means["lab"], means["cuoi_ky"])
        self.assertGreater(means["giua_ky"], means["cuoi_ky"])

    def test_validate_generator_config_component_shifts(self):
        import copy
        bad_cfg = copy.deepcopy(GENERATOR_CONFIG)
        bad_cfg["component_shifts"] = "not_a_dict"
        with self.assertRaises(ValueError):
            validate_generator_config(bad_cfg)

        bad_cfg2 = copy.deepcopy(GENERATOR_CONFIG)
        bad_cfg2["component_shifts"] = {"btl": "invalid_number"}
        with self.assertRaises(ValueError):
            validate_generator_config(bad_cfg2)

    def test_sync_class_teamwork_btl_synchronizes_scores_within_team(self):
        # 4 students in the same class section with different initial BTL scores
        df = pd.DataFrame([
            {
                "enrollment_id": 1,
                "student_id": "2110001",
                "class_id": "HK211_CO1005_L01",
                "course_id": "CO1005",
                "btl": 9.0,  # Leader
                "final_score": 8.0,
                "letter_grade": "B+",
                "gpa_4": 3.5,
                "passed": True,
                "status": "Pass",
            },
            {
                "enrollment_id": 2,
                "student_id": "2110002",
                "class_id": "HK211_CO1005_L01",
                "course_id": "CO1005",
                "btl": 6.0,  # Weaker student
                "final_score": 6.0,
                "letter_grade": "C",
                "gpa_4": 2.0,
                "passed": True,
                "status": "Pass",
            },
            {
                "enrollment_id": 3,
                "student_id": "2110003",
                "class_id": "HK211_CO1005_L01",
                "course_id": "CO1005",
                "btl": 7.0,
                "final_score": 6.8,
                "letter_grade": "C+",
                "gpa_4": 2.5,
                "passed": True,
                "status": "Pass",
            },
            {
                "enrollment_id": 4,
                "student_id": "2110004",
                "class_id": "HK211_CO1005_L01",
                "course_id": "CO1005",
                "btl": 8.0,
                "final_score": 7.5,
                "letter_grade": "B",
                "gpa_4": 3.0,
                "passed": True,
                "status": "Pass",
            },
        ])
        
        weights = {"CO1005": 0.2}  # BTL has 20% weight
        synced = sync_class_teamwork_btl(df, assessment_weights=weights)

        # All students in the 4-person team must have BTL equal to the top performer (9.0)
        self.assertEqual(synced["btl"].tolist(), [9.0, 9.0, 9.0, 9.0])

        # Weaker student (initial BTL 6.0 -> 9.0, +3.0 * 0.2 = +0.6 final_score)
        # 6.0 + 0.6 = 6.6 -> Letter grade B (grade scale 6.5 <= score < 7.0 is B? Let's check grade_scale)
        self.assertEqual(synced.loc[1, "btl"], 9.0)
        self.assertEqual(synced.loc[1, "final_score"], 6.6)
        self.assertGreater(synced.loc[1, "final_score"], 6.0)

    def test_sync_class_teamwork_btl_recalculates_gpa(self):
        df = pd.DataFrame([
            {
                "enrollment_id": 1,
                "student_id": "2110001",
                "class_id": "HK211_CO1005_L01",
                "course_id": "CO1005",
                "btl": 9.0,
                "final_score": 8.0,
                "letter_grade": "B+",
                "gpa_4": 3.5,
                "passed": True,
                "status": "Pass",
                "semester_gpa_4": 3.5,
                "final_gpa_4": 3.5,
            },
            {
                "enrollment_id": 2,
                "student_id": "2110002",
                "class_id": "HK211_CO1005_L01",
                "course_id": "CO1005",
                "btl": 5.0,
                "final_score": 5.0,
                "letter_grade": "D",
                "gpa_4": 1.0,
                "passed": True,
                "status": "Pass",
                "semester_gpa_4": 1.0,
                "final_gpa_4": 1.0,
            },
        ])
        weights = {"CO1005": 0.2}
        credits_map = {"CO1005": 3.0}
        synced = sync_class_teamwork_btl(df, assessment_weights=weights, credits_map=credits_map)
        # Student 2 BTL increased from 5.0 to 9.0 -> final_score from 5.0 to 5.8 -> GPA 4.0 scale improves
        self.assertGreater(synced.loc[1, "semester_gpa_4"], 1.0)

    def test_thesis_eligibility_academic_standing_rules(self):
        # Student with >= 12 CTXH and English passed
        import json
        ctxh_progress = json.dumps([{"semester": "HK201", "cumulative_days": 15}])
        student = {
            "student_id": "2010001",
            "ctxh_days_by_semester": ctxh_progress,
            "english_pass": True,
            "english_eligibility_by_semester": json.dumps(["HK201"]),
        }
        passed_courses = {"CO1001", "CO4029"}

        # 1. Base eligibility (without standing args) should be True for backward compatibility
        self.assertTrue(is_thesis_eligible(student, "HK232", passed_courses))

        # 2. Credits < 105 -> Ineligible
        self.assertFalse(is_thesis_eligible(
            student, "HK232", passed_courses,
            passed_credits=104.0, co4029_score=6.0, cumulative_gpa=2.5
        ))

        # 3. CO4029 < 5.5 -> Ineligible
        self.assertFalse(is_thesis_eligible(
            student, "HK232", passed_courses,
            passed_credits=110.0, co4029_score=5.0, cumulative_gpa=2.5
        ))

        # 4. GPA < 2.0 -> Ineligible
        self.assertFalse(is_thesis_eligible(
            student, "HK232", passed_courses,
            passed_credits=110.0, co4029_score=6.0, cumulative_gpa=1.95
        ))

        # 5. All criteria met: credits >= 105, CO4029 >= 5.5, GPA >= 2.0, CTXH >= 12, English pass -> Eligible
        self.assertTrue(is_thesis_eligible(
            student, "HK232", passed_courses,
            passed_credits=105.0, co4029_score=5.5, cumulative_gpa=2.00
        ))

    def test_extract_student_academic_standing(self):
        prev_df = pd.DataFrame([
            {
                "student_id": "2010001",
                "course_id": "CO1005",
                "final_score": 8.0,
                "gpa_4": 3.5,
                "passed": True,
                "status": "Pass",
            },
            {
                "student_id": "2010001",
                "course_id": "CO4029",
                "final_score": 6.0,
                "gpa_4": 2.5,
                "passed": True,
                "status": "Pass",
            },
            {
                "student_id": "2010002",
                "course_id": "CO4029",
                "final_score": 5.0,
                "gpa_4": 1.0,
                "passed": True,
                "status": "Pass",
            },
        ])
        credits_map = {"CO1005": 4.0, "CO4029": 3.0}
        passed_creds, co4029_sc, cum_gpa = extract_student_academic_standing(prev_df, credits_map)

        self.assertEqual(passed_creds["2010001"], 7.0)
        self.assertEqual(co4029_sc["2010001"], 6.0)
        self.assertEqual(co4029_sc["2010002"], 5.0)
        # 2010001 GPA: (3.5*4 + 2.5*3) / 7 = 21.5 / 7 = 3.07
        self.assertAlmostEqual(cum_gpa["2010001"], 3.07, places=2)

    def test_calculate_prerequisite_adjustment_penalties_and_bonuses(self):
        # MT1005 requires MT1003
        # When MT1003 = 4.0: deficit = 6.0 - 4.0 = 2.0 -> penalty = 2.0 * 0.6 = 1.2 -> adj = -1.2
        adj_40 = calculate_prerequisite_adjustment(
            student_id="sv01",
            course_code="MT1005",
            past_grades={"MT1003": 4.0},
        )
        self.assertEqual(adj_40, -1.2)

        # When MT1003 = 5.0: deficit = 6.0 - 5.0 = 1.0 -> penalty = 1.0 * 0.6 = 0.6 -> adj = -0.6
        adj_50 = calculate_prerequisite_adjustment(
            student_id="sv01",
            course_code="MT1005",
            past_grades={"MT1003": 5.0},
        )
        self.assertEqual(adj_50, -0.6)

        # When MT1003 = 6.5: between safe (6.0) and bonus (7.5) -> adj = 0.0
        adj_65 = calculate_prerequisite_adjustment(
            student_id="sv01",
            course_code="MT1005",
            past_grades={"MT1003": 6.5},
        )
        self.assertEqual(adj_65, 0.0)

        # When MT1003 = 8.5: surplus = 8.5 - 7.5 = 1.0 -> bonus = 1.0 * 0.1 = 0.1 -> adj = +0.1
        adj_85 = calculate_prerequisite_adjustment(
            student_id="sv01",
            course_code="MT1005",
            past_grades={"MT1003": 8.5},
        )
        self.assertEqual(adj_85, 0.1)

    def test_calculate_prerequisite_adjustment_weakest_link(self):
        # MT2013 requires MT1003 and MT1007
        # Weakest link is MT1003 (4.0) even though MT1007 is 8.0
        adj_weak = calculate_prerequisite_adjustment(
            student_id="sv02",
            course_code="MT2013",
            past_grades={"MT1003": 4.0, "MT1007": 8.0},
        )
        self.assertEqual(adj_weak, -1.2)

    def test_course_mean_score_applies_prerequisite_adjustment(self):
        profile = {
            "student_id": "sv03",
            "academic_level": 3,
            "math_level": 3,
            "discipline": 3,
            "motivation": 3,
            "stress": 3,
        }
        score_no_prereq = course_mean_score(profile, "MT1005", 0.0, GENERATOR_CONFIG, student_id="sv03")
        score_weak_prereq = course_mean_score(
            profile, "MT1005", 0.0, GENERATOR_CONFIG,
            student_id="sv03",
            past_prereq_scores={"MT1003": 4.0},
        )
        self.assertAlmostEqual(score_no_prereq - score_weak_prereq, 1.2, places=2)

    def test_set_student_past_grades_cache_integration(self):
        clear_student_past_grades()
        set_student_past_grades({"sv04": {"MT1003": 4.5}})
        # Deficit = 6.0 - 4.5 = 1.5 -> penalty = 1.5 * 0.6 = 0.9 -> adj = -0.9
        adj = calculate_prerequisite_adjustment(student_id="sv04", course_code="MT1005")
        self.assertEqual(adj, -0.9)
        clear_student_past_grades()


if __name__ == "__main__":
    unittest.main()
