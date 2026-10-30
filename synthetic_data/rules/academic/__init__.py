"""Academic Rules Package.

Decomposed into 6 distinct business domain modules + config + common utilities:
- config: Generator configuration schema validation and loader
- common: Stable seeds, student cohort filters, and file helpers
- profile_rules: Student profiles, personality traits, CTXH progress, English transition, and dropout models
- scoring_rules: Score expectations, noise injection, component grades, and GPA summaries
- standing_rules: Semester chronology, academic dismissal, and suspension tracking
- retake_rules: Failed course retake limits and GPA improvement policies
- eligibility_rules: Prerequisite fulfillment, English exemptions, and elective selections
- allocation_rules: Balanced section sizing, instructor assignment, and roster generation
"""

from .common import (
    COHORT_START_SEMESTER,
    ROOT_DIR,
    _normalized_trait,
    _stable_seed,
    _student_flag,
    _student_value,
    cohort_year,
    filter_students_from_2013,
    filter_students_from_2020,
    get_department,
    load_course_data,
    load_history,
)

from .config import (
    CONFIG_FILE,
    GENERATOR_CONFIG,
    load_generator_config,
    validate_generator_config,
)

from .standing_rules import (
    DISMISSAL_AFTER_SEMESTERS,
    MAX_LATE_SEMESTERS,
    STANDARD_SEMESTERS,
    _is_academic_suspension_semester,
    academic_dismissal_semesters,
    academic_suspension_semesters,
    filter_active_students_for_semester,
    get_academic_dismissal_semester,
    get_late_semesters_count,
    is_academic_dismissal,
    is_late_semester,
    is_student_active_for_semester,
    semester_from_index,
    semester_index,
)

from .profile_rules import (
    ACCELERATION_BASE_SCORE,
    ACCELERATION_PROBABILITY,
    PROFILE_FIELDS,
    PROFILE_OUTPUT_DIR,
    PROFILE_OUTPUT_FILE,
    _base_score_for_level,
    _generate_ctxh_progress,
    _generate_english_eligibility_progress,
    _generate_voluntary_dropout,
    _progress_personality_strength,
    ctxh_days_before_semester,
    generate_student_profile,
    load_student_profiles,
    resolve_student_profile,
    select_early_graduation_candidates,
    wants_acceleration,
)

from .scoring_rules import (
    add_gpa_summaries,
    convert_score_to_grade,
    course_mean_score,
    generate_observed_score,
    score_course_components,
)

from .retake_rules import (
    filter_retake_demand_by_credit_limit,
    generate_grade_improvement_retakes,
)

from .eligibility_rules import (
    COURSE_ORDER,
    ENGLISH_COURSE_CODES,
    FREE_CREDIT_LIMIT,
    GROUP_C_CREDIT_LIMIT,
    K13_COURSES,
    K13_EXTRA_COURSES,
    K14_COURSES,
    K23_COURSES,
    K23_EXTRA_COURSES,
    K24_COURSES,
    OPTIONAL_16_CREDIT_PROBABILITY,
    OPTIONAL_ENROLLMENT_THRESHOLD,
    SEMESTER,
    _FREE_COURSE_CODES,
    _GROUP_C_COURSE_CODES,
    allows_optional_course_at_16,
    calculate_eligibility,
    calculate_eligibility_for_schedule,
    can_skip_la1003,
    english_eligible_by_semester,
    get_exempted_english_courses,
    get_free_course_codes,
    get_group_c_course_codes,
    is_english_passed,
    is_thesis_eligible,
)

from .allocation_rules import (
    allocate_course_rosters,
    assign_balanced_lecturers,
    balanced_class_sizes,
    students_by_course_from_eligibility,
)

