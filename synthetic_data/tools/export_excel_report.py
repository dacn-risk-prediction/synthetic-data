"""Export comprehensive academic validation report from generated synthetic data to an Excel (.xlsx) workbook.

This script aggregates university-wide and cohort-level synthetic metrics from
synthetic_data/generated/ and outputs a beautifully formatted multi-sheet Excel file
with native interactive Excel charts (PieCharts, BarCharts) for maximum visual clarity.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
import openpyxl
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import SeriesLabel
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
METRICS_DIR = ROOT_DIR / "generated" / "metrics"
USERS_DIR = ROOT_DIR / "generated" / "users"
CLASSES_DIR = ROOT_DIR / "generated" / "classes"
DEFAULT_OUTPUT_FILE = ROOT_DIR / "academic_validation_report.xlsx"


def load_all_datasets():
    """Load all required datasets for report generation."""
    univ_file = METRICS_DIR / "university_metrics.csv"
    student_file = METRICS_DIR / "student_metrics.csv"
    letter_file = METRICS_DIR / "letter_grade_distribution.csv"
    score_file = METRICS_DIR / "score_distribution.csv"
    progress_file = METRICS_DIR / "student_progress.csv"
    user_student_file = USERS_DIR / "student.csv"
    profiles_file = USERS_DIR / "student_profiles.csv"
    lecturer_file = USERS_DIR / "lecturer.csv"

    if not univ_file.exists() or not student_file.exists():
        raise FileNotFoundError(
            f"Required metrics files not found in {METRICS_DIR}. "
            "Please run generate_academic_metrics.py first."
        )

    df_univ = pd.read_csv(univ_file)
    df_students = pd.read_csv(student_file, dtype={"student_id": str, "cohort": str})
    df_letters = pd.read_csv(letter_file) if letter_file.exists() else pd.DataFrame()
    df_scores = pd.read_csv(score_file) if score_file.exists() else pd.DataFrame()
    df_progress = pd.read_csv(progress_file, dtype={"student_id": str, "cohort": str}) if progress_file.exists() else pd.DataFrame()

    df_user_st = pd.read_csv(user_student_file, dtype={"user_id": str}) if user_student_file.exists() else pd.DataFrame()
    df_profiles = pd.read_csv(profiles_file, dtype={"student_id": str}) if profiles_file.exists() else pd.DataFrame()
    df_lecturers = pd.read_csv(lecturer_file, dtype={"user_id": str}) if lecturer_file.exists() else pd.DataFrame()

    # Merge program into students
    if not df_user_st.empty and "program" in df_user_st.columns:
        df_students = df_students.merge(df_user_st[["user_id", "program"]], left_on="student_id", right_on="user_id", how="left")

    return df_univ, df_students, df_letters, df_scores, df_progress, df_profiles, df_lecturers


def build_overview_sheet(df_univ: pd.DataFrame, df_students: pd.DataFrame) -> pd.DataFrame:
    """Build high-level university benchmark metrics for the entire university (K20 - K26)."""
    metrics_map = dict(zip(df_univ["metric"], df_univ["value"]))
    num_map = dict(zip(df_univ["metric"], df_univ["numerator"]))
    den_map = dict(zip(df_univ["metric"], df_univ["denominator"]))

    # Khóa đã hoàn tất chu kỳ đào tạo (K20)
    k20_students = df_students[df_students["cohort"] == "K20"]
    k20_grads = k20_students[k20_students["graduation_ready"] == True]

    tracked_count = int(metrics_map.get("tracked_students", len(df_students)))
    grad_all_rate = float(metrics_map.get("graduation_ready_rate", 0.0))
    grad_k20_rate = len(k20_grads) / len(k20_students) if len(k20_students) else 0.0
    early_rate = float(metrics_map.get("graduation_early_rate", 0.0))
    on_time_rate = float(metrics_map.get("graduation_on_time_rate", 0.0))
    late_rate = float(metrics_map.get("graduation_late_rate", 0.0))

    exc_rate = float(metrics_map.get("degree_excellent_rate", 0.0))
    good_rate = float(metrics_map.get("degree_good_rate", 0.0))
    fair_rate = float(k20_grads["degree_classification"].eq("fair").sum() / len(k20_grads)) if len(k20_grads) else 0.0
    f_avg_rate = float(k20_grads["degree_classification"].eq("fairly_average").sum() / len(k20_grads)) if len(k20_grads) else 0.0
    avg_rate = float(metrics_map.get("degree_average_rate", 0.0))

    gpa_4_mean = float(metrics_map.get("profile_gpa_4_mean", 0.0))
    score_10_mean = float(metrics_map.get("score_10_mean", 0.0))
    score_10_std = float(metrics_map.get("score_10_std", 0.0))
    eng_rate = float(metrics_map.get("english_eligibility_rate", 0.0))
    ctxh_mean = float(metrics_map.get("profile_ctxh_days_cumulative_mean", 0.0))

    drop_rate = float(metrics_map.get("dropout_rate", 0.0))
    vol_drop_rate = float(metrics_map.get("voluntary_dropout_rate", 0.0))
    forced_drop_rate = float(metrics_map.get("forced_dropout_rate", 0.0))
    susp_rate = float(metrics_map.get("academic_suspension_rate", 0.0))

    overview_rows = [
        # Nhóm 1: Quy mô & Tuyển sinh
        {
            "Nhóm danh mục": "1. Quy mô & Tuyển sinh",
            "Chỉ số học vụ (Metric)": "Tổng sinh viên mô phỏng toàn hệ thống",
            "Giá trị Synthetic Data": f"{tracked_count:,} sinh viên",
            "Ghi chú & Phạm vi": "7 khóa từ K20 đến K26 (HK201 - HK261)",
        },
        {
            "Nhóm danh mục": "1. Quy mô & Tuyển sinh",
            "Chỉ số học vụ (Metric)": "Tỷ lệ hệ Đại trà (Standard)",
            "Giá trị Synthetic Data": f"{(df_students['program'] == 'standard').mean() * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{(df_students['program'] == 'standard').sum():,} SV (Mục tiêu ~60%)",
        },
        {
            "Nhóm danh mục": "1. Quy mô & Tuyển sinh",
            "Chỉ số học vụ (Metric)": "Tỷ lệ hệ Chất lượng cao (High-quality)",
            "Giá trị Synthetic Data": f"{(df_students['program'] == 'high-quality').mean() * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{(df_students['program'] == 'high-quality').sum():,} SV (Mục tiêu ~30%)",
        },
        {
            "Nhóm danh mục": "1. Quy mô & Tuyển sinh",
            "Chỉ số học vụ (Metric)": "Tỷ lệ hệ Tiên tiến (Advanced)",
            "Giá trị Synthetic Data": f"{(df_students['program'] == 'advanced').mean() * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{(df_students['program'] == 'advanced').sum():,} SV (Mục tiêu ~10%)",
        },

        # Nhóm 2: Tiến độ & Tốt nghiệp
        {
            "Nhóm danh mục": "2. Tiến độ & Tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tỷ lệ tốt nghiệp Khóa K20 (Hoàn thành chu kỳ)",
            "Giá trị Synthetic Data": f"{grad_k20_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{len(k20_grads):,} / {len(k20_students):,} SV K20 hoàn tất lộ trình",
        },
        {
            "Nhóm danh mục": "2. Tiến độ & Tốt nghiệp",
            "Chỉ số học vụ (Metric)": "- Tốt nghiệp sớm hạn (3.5 năm - Học kỳ 7)",
            "Giá trị Synthetic Data": f"{early_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{int(num_map.get('graduation_early_rate', 0)):,} SV đạt chuẩn học vượt toàn khóa",
        },
        {
            "Nhóm danh mục": "2. Tiến độ & Tốt nghiệp",
            "Chỉ số học vụ (Metric)": "- Tốt nghiệp đúng hạn (4.0 năm - Học kỳ 8)",
            "Giá trị Synthetic Data": f"{on_time_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{int(num_map.get('graduation_on_time_rate', 0)):,} SV (Tiến độ chuẩn đào tạo)",
        },
        {
            "Nhóm danh mục": "2. Tiến độ & Tốt nghiệp",
            "Chỉ số học vụ (Metric)": "- Tốt nghiệp trễ hạn (4.5 - 6.0 năm - Kỳ 9 đến 12)",
            "Giá trị Synthetic Data": f"{late_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{int(num_map.get('graduation_late_rate', 0)):,} SV (Trả nợ môn, tích lũy thêm CTXH)",
        },

        # Nhóm 3: Xếp loại tốt nghiệp
        {
            "Nhóm danh mục": "3. Xếp loại tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp loại Xuất sắc (GPA 3.60 - 4.00)",
            "Giá trị Synthetic Data": f"{exc_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{int(num_map.get('degree_excellent_rate', 0)):,} SV tốt nghiệp",
        },
        {
            "Nhóm danh mục": "3. Xếp loại tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp loại Giỏi (GPA 3.20 - 3.59)",
            "Giá trị Synthetic Data": f"{good_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{int(num_map.get('degree_good_rate', 0)):,} SV tốt nghiệp",
        },
        {
            "Nhóm danh mục": "3. Xếp loại tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp loại Khá (GPA 2.80 - 3.19)",
            "Giá trị Synthetic Data": f"{fair_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": "Phân khúc năng lực khá",
        },
        {
            "Nhóm danh mục": "3. Xếp loại tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp loại Trung bình khá (GPA 2.40 - 2.79)",
            "Giá trị Synthetic Data": f"{f_avg_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": "Phân khúc phổ thông",
        },
        {
            "Nhóm danh mục": "3. Xếp loại tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp loại Trung bình & Yếu (GPA < 2.40)",
            "Giá trị Synthetic Data": f"{avg_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{int(num_map.get('degree_average_rate', 0)):,} SV tốt nghiệp",
        },

        # Nhóm 4: Học lực & Điểm tích lũy (GPA)
        {
            "Nhóm danh mục": "4. Học lực & Điểm tích lũy (GPA)",
            "Chỉ số học vụ (Metric)": "Điểm GPA trung bình tích lũy toàn hệ thống (Thang 4.0)",
            "Giá trị Synthetic Data": f"{gpa_4_mean:.2f} / 4.0",
            "Ghi chú & Phạm vi": "Điểm tích lũy trung bình toàn trường",
        },
        {
            "Nhóm danh mục": "4. Học lực & Điểm tích lũy (GPA)",
            "Chỉ số học vụ (Metric)": "Điểm học phần trung bình toàn trường (Thang 10.0)",
            "Giá trị Synthetic Data": f"{score_10_mean:.2f} / 10.0",
            "Ghi chú & Phạm vi": f"Tổng cộng {int(metrics_map.get('score_10_count', 0)):,} lượt điểm học phần",
        },
        {
            "Nhóm danh mục": "4. Học lực & Điểm tích lũy (GPA)",
            "Chỉ số học vụ (Metric)": "Độ lệch chuẩn điểm học phần (Std Thang 10)",
            "Giá trị Synthetic Data": f"{score_10_std:.2f} điểm",
            "Ghi chú & Phạm vi": "Độ phân tán năng lực học tập",
        },
        {
            "Nhóm danh mục": "4. Học lực & Điểm tích lũy (GPA)",
            "Chỉ số học vụ (Metric)": "Tỷ lệ đạt chuẩn tiếng Anh tích lũy",
            "Giá trị Synthetic Data": f"{eng_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{int(num_map.get('english_eligibility_rate', 0)):,} / {len(df_students):,} sinh viên",
        },
        {
            "Nhóm danh mục": "4. Học lực & Điểm tích lũy (GPA)",
            "Chỉ số học vụ (Metric)": "Số ngày Công tác Xã hội (CTXH) tích lũy trung bình",
            "Giá trị Synthetic Data": f"{ctxh_mean:.1f} ngày",
            "Ghi chú & Phạm vi": "Chuẩn tốt nghiệp BKU: >= 15 ngày CTXH",
        },

        # Nhóm 5: Thôi học & Kỷ luật học vụ
        {
            "Nhóm danh mục": "5. Thôi học & Kỷ luật học vụ",
            "Chỉ số học vụ (Metric)": "Tổng tỷ lệ thôi học / bỏ học (Toàn trường)",
            "Giá trị Synthetic Data": f"{drop_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{int(num_map.get('dropout_rate', 0)):,} / {len(df_students):,} sinh viên",
        },
        {
            "Nhóm danh mục": "5. Thôi học & Kỷ luật học vụ",
            "Chỉ số học vụ (Metric)": "- Tự nguyện thôi học (Hoàn cảnh gia đình, cá nhân)",
            "Giá trị Synthetic Data": f"{vol_drop_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{int(num_map.get('voluntary_dropout_rate', 0)):,} sinh viên",
        },
        {
            "Nhóm danh mục": "5. Thôi học & Kỷ luật học vụ",
            "Chỉ số học vụ (Metric)": "- Buộc thôi học (Quá thời hạn đào tạo tối đa 12 kỳ)",
            "Giá trị Synthetic Data": f"{forced_drop_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{int(num_map.get('forced_dropout_rate', 0)):,} sinh viên vi phạm khung thời gian",
        },
        {
            "Nhóm danh mục": "5. Thôi học & Kỷ luật học vụ",
            "Chỉ số học vụ (Metric)": "Tỷ lệ sinh viên từng bị cảnh cáo học vụ (Tạm dừng)",
            "Giá trị Synthetic Data": f"{susp_rate * 100:.1f}%",
            "Ghi chú & Phạm vi": f"{int(num_map.get('academic_suspension_rate', 0)):,} sinh viên từng bị tạm dừng kỳ học",
        },
    ]

    return pd.DataFrame(overview_rows)


def build_cohort_comparison_sheet(df_students: pd.DataFrame) -> pd.DataFrame:
    """Build detailed comparison table across all cohorts K20 to K26."""
    records = []
    cohort_list = sorted([c for c in df_students["cohort"].dropna().unique().tolist() if c.startswith("K")])

    for cohort in cohort_list:
        sub = df_students[df_students["cohort"] == cohort]
        n = len(sub)
        grad = sub[sub["graduation_ready"] == True]
        grad_count = len(grad)
        grad_rate = grad_count / n if n else 0.0

        early_count = int((grad["graduation_timing"] == "early").sum())
        on_time_count = int((grad["graduation_timing"] == "on_time").sum())
        late_count = int((grad["graduation_timing"] == "late").sum())

        dropout_count = int((sub["dropout"] == True).sum())
        dropout_rate = dropout_count / n if n else 0.0

        cont_count = int(((sub["graduation_ready"] == False) & (sub["dropout"] == False)).sum())
        cont_rate = cont_count / n if n else 0.0

        # GPA stats
        gpa_series = sub["gpa_4"].dropna()
        has_gpa = not gpa_series.empty
        avg_gpa = float(gpa_series.mean()) if has_gpa else None
        std_gpa = float(gpa_series.std()) if has_gpa else None
        med_gpa = float(gpa_series.median()) if has_gpa else None
        q1_gpa = float(gpa_series.quantile(0.25)) if has_gpa else None
        q3_gpa = float(gpa_series.quantile(0.75)) if has_gpa else None

        avg_credits = float(sub["passed_credits"].mean()) if n else 0.0
        eng_rate = float(sub["english_pass"].mean()) if n else 0.0
        avg_ctxh = float(sub["ctxh_days_cumulative"].mean()) if n else 0.0

        # Degree classifications
        exc_count = int(grad["degree_classification"].eq("excellent").sum())
        good_count = int(grad["degree_classification"].eq("good").sum())
        fair_count = int(grad["degree_classification"].eq("fair").sum())
        f_avg_count = int(grad["degree_classification"].eq("fairly_average").sum())
        avg_cls_count = int(grad["degree_classification"].isin(["average", "below_average"]).sum())

        records.append({
            "Khóa (Cohort)": cohort,
            "Sĩ số (Tổng SV)": n,
            "Đã tốt nghiệp (SV)": grad_count,
            "Tỷ lệ tốt nghiệp (%)": f"{grad_rate * 100:.1f}%" if grad_count > 0 else ("Chưa đến kỳ xét TN" if cohort in ["K23", "K24", "K25", "K26"] else "0.0%"),
            "Sớm hạn 3.5 năm (SV)": early_count,
            "Đúng hạn 4.0 năm (SV)": on_time_count,
            "Trễ hạn 4.5-6.0 năm (SV)": late_count,
            "Đang theo học (SV)": cont_count,
            "Tỷ lệ đang học (%)": f"{cont_rate * 100:.1f}%",
            "Thôi học (SV)": dropout_count,
            "Tỷ lệ thôi học (%)": f"{dropout_rate * 100:.1f}%",
            "GPA Trung bình": f"{avg_gpa:.2f}" if avg_gpa is not None else "Đang học HK1",
            "GPA Độ lệch chuẩn": f"{std_gpa:.2f}" if std_gpa is not None else "-",
            "GPA Trung vị": f"{med_gpa:.2f}" if med_gpa is not None else "-",
            "GPA Q1 (25%)": f"{q1_gpa:.2f}" if q1_gpa is not None else "-",
            "GPA Q3 (75%)": f"{q3_gpa:.2f}" if q3_gpa is not None else "-",
            "Tín chỉ tích lũy TB": f"{avg_credits:.1f}",
            "Tỷ lệ chuẩn Anh văn (%)": f"{eng_rate * 100:.1f}%",
            "CTXH TB tích lũy (Ngày)": f"{avg_ctxh:.1f}",
            "Tốt nghiệp Xuất sắc (SV)": exc_count if grad_count > 0 else "-",
            "Tốt nghiệp Giỏi (SV)": good_count if grad_count > 0 else "-",
            "Tốt nghiệp Khá (SV)": fair_count if grad_count > 0 else "-",
            "Tốt nghiệp TB Khá (SV)": f_avg_count if grad_count > 0 else "-",
            "Tốt nghiệp TB & Yếu (SV)": avg_cls_count if grad_count > 0 else "-",
        })

    return pd.DataFrame(records)


def build_single_cohort_sheet(cohort: str, df_students: pd.DataFrame) -> pd.DataFrame:
    """Build clean and accurate synthetic metrics table for a specific cohort (without real data placeholder columns)."""
    sub = df_students[df_students["cohort"] == cohort]
    n = len(sub)
    grad = sub[sub["graduation_ready"] == True]
    grad_count = len(grad)

    gpa_series = sub["gpa_4"].dropna()
    has_gpa = not gpa_series.empty
    avg_gpa = float(gpa_series.mean()) if has_gpa else None
    std_gpa = float(gpa_series.std()) if has_gpa else None
    med_gpa = float(gpa_series.median()) if has_gpa else None
    q1_gpa = float(gpa_series.quantile(0.25)) if has_gpa else None
    q3_gpa = float(gpa_series.quantile(0.75)) if has_gpa else None
    min_gpa = float(gpa_series.min()) if has_gpa else None
    max_gpa = float(gpa_series.max()) if has_gpa else None

    avg_credits = float(sub["passed_credits"].mean()) if n else 0.0
    eng_rate = float(sub["english_pass"].mean()) if n else 0.0
    avg_ctxh = float(sub["ctxh_days_cumulative"].mean()) if n else 0.0
    ctxh_qualified_rate = float((sub["ctxh_days_cumulative"] >= 15).mean()) if n else 0.0

    early_count = int((grad["graduation_timing"] == "early").sum())
    on_time_count = int((grad["graduation_timing"] == "on_time").sum())
    late_count = int((grad["graduation_timing"] == "late").sum())
    dropout_count = int((sub["dropout"] == True).sum())
    susp_count = int((sub["academic_suspension_count"] > 0).sum())

    is_grad_cohort = grad_count > 0

    metrics_rows = [
        {"STT": 1, "Nhóm chỉ số": "Quy mô", "Tên chỉ số học vụ": f"Sĩ số sinh viên khóa {cohort}", "Giá trị Synthetic Data": f"{n:,} SV", "Ghi chú & Đơn vị": "Tổng sinh viên tuyển sinh"},
        {"STT": 2, "Nhóm chỉ số": "Cơ cấu hệ", "Tên chỉ số học vụ": "Tỷ lệ hệ Đại trà (Standard)", "Giá trị Synthetic Data": f"{(sub['program'] == 'standard').mean() * 100:.1f}%", "Ghi chú & Đơn vị": f"{(sub['program'] == 'standard').sum():,} SV"},
        {"STT": 3, "Nhóm chỉ số": "Cơ cấu hệ", "Tên chỉ số học vụ": "Tỷ lệ hệ Chất lượng cao (High-quality)", "Giá trị Synthetic Data": f"{(sub['program'] == 'high-quality').mean() * 100:.1f}%", "Ghi chú & Đơn vị": f"{(sub['program'] == 'high-quality').sum():,} SV"},
        {"STT": 4, "Nhóm chỉ số": "Cơ cấu hệ", "Tên chỉ số học vụ": "Tỷ lệ hệ Tiên tiến (Advanced)", "Giá trị Synthetic Data": f"{(sub['program'] == 'advanced').mean() * 100:.1f}%", "Ghi chú & Đơn vị": f"{(sub['program'] == 'advanced').sum():,} SV"},
        
        {"STT": 5, "Nhóm chỉ số": "Học lực (GPA)", "Tên chỉ số học vụ": "GPA Trung bình (Thang 4.0)", "Giá trị Synthetic Data": f"{avg_gpa:.2f}" if avg_gpa is not None else "Đang học HK1", "Ghi chú & Đơn vị": "Điểm TB tích lũy"},
        {"STT": 6, "Nhóm chỉ số": "Học lực (GPA)", "Tên chỉ số học vụ": "GPA Độ lệch chuẩn (Std)", "Giá trị Synthetic Data": f"{std_gpa:.2f}" if std_gpa is not None else "-", "Ghi chú & Đơn vị": "Độ phân tán năng lực"},
        {"STT": 7, "Nhóm chỉ số": "Học lực (GPA)", "Tên chỉ số học vụ": "GPA Trung vị (Median)", "Giá trị Synthetic Data": f"{med_gpa:.2f}" if med_gpa is not None else "-", "Ghi chú & Đơn vị": "Mức điểm phân đôi 50% SV"},
        {"STT": 8, "Nhóm chỉ số": "Học lực (GPA)", "Tên chỉ số học vụ": "GPA Tứ phân vị 25% (Q1)", "Giá trị Synthetic Data": f"{q1_gpa:.2f}" if q1_gpa is not None else "-", "Ghi chú & Đơn vị": "Phân khúc 25% dưới"},
        {"STT": 9, "Nhóm chỉ số": "Học lực (GPA)", "Tên chỉ số học vụ": "GPA Tứ phân vị 75% (Q3)", "Giá trị Synthetic Data": f"{q3_gpa:.2f}" if q3_gpa is not None else "-", "Ghi chú & Đơn vị": "Phân khúc 25% trên"},
        {"STT": 10, "Nhóm chỉ số": "Học lực (GPA)", "Tên chỉ số học vụ": "Biên độ GPA (Min - Max)", "Giá trị Synthetic Data": f"{min_gpa:.2f} - {max_gpa:.2f}" if min_gpa is not None else "-", "Ghi chú & Đơn vị": "Khoảng điểm nhỏ nhất - lớn nhất"},
        
        {"STT": 11, "Nhóm chỉ số": "Tín chỉ", "Tên chỉ số học vụ": "Tín chỉ tích lũy trung bình", "Giá trị Synthetic Data": f"{avg_credits:.1f} tín chỉ", "Ghi chú & Đơn vị": "Tổng tín chỉ đạt (Passed Credits)"},
        {"STT": 12, "Nhóm chỉ số": "Ngoại kiểm", "Tên chỉ số học vụ": "Tỷ lệ đạt chuẩn Tiếng Anh", "Giá trị Synthetic Data": f"{eng_rate * 100:.1f}%", "Ghi chú & Đơn vị": f"{int((sub['english_pass'] == True).sum()):,} / {n:,} SV"},
        {"STT": 13, "Nhóm chỉ số": "Ngoại kiểm", "Tên chỉ số học vụ": "Ngày CTXH tích lũy trung bình", "Giá trị Synthetic Data": f"{avg_ctxh:.1f} ngày", "Ghi chú & Đơn vị": "Ngày công tác xã hội"},
        {"STT": 14, "Nhóm chỉ số": "Ngoại kiểm", "Tên chỉ số học vụ": "Tỷ lệ đạt chuẩn CTXH (>= 15 ngày)", "Giá trị Synthetic Data": f"{ctxh_qualified_rate * 100:.1f}%", "Ghi chú & Đơn vị": f"{int((sub['ctxh_days_cumulative'] >= 15).sum()):,} / {n:,} SV"},
        
        {"STT": 15, "Nhóm chỉ số": "Tiến độ", "Tên chỉ số học vụ": "Tỷ lệ tốt nghiệp chung", "Giá trị Synthetic Data": f"{grad_count / n * 100:.1f}% ({grad_count:,} SV)" if is_grad_cohort else "Chưa đến kỳ xét tốt nghiệp", "Ghi chú & Đơn vị": "Đạt chuẩn tốt nghiệp"},
        {"STT": 16, "Nhóm chỉ số": "Tiến độ", "Tên chỉ số học vụ": "- Tốt nghiệp sớm 3.5 năm", "Giá trị Synthetic Data": f"{early_count / n * 100:.1f}% ({early_count:,} SV)" if is_grad_cohort else "-", "Ghi chú & Đơn vị": "Tốt nghiệp ở Học kỳ 7"},
        {"STT": 17, "Nhóm chỉ số": "Tiến độ", "Tên chỉ số học vụ": "- Tốt nghiệp đúng hạn 4.0 năm", "Giá trị Synthetic Data": f"{on_time_count / n * 100:.1f}% ({on_time_count:,} SV)" if is_grad_cohort else "-", "Ghi chú & Đơn vị": "Tốt nghiệp ở Học kỳ 8"},
        {"STT": 18, "Nhóm chỉ số": "Tiến độ", "Tên chỉ số học vụ": "- Tốt nghiệp trễ hạn 4.5-6.0 năm", "Giá trị Synthetic Data": f"{late_count / n * 100:.1f}% ({late_count:,} SV)" if is_grad_cohort else "-", "Ghi chú & Đơn vị": "Tốt nghiệp ở Kỳ 9 đến 12"},
        
        {"STT": 19, "Nhóm chỉ số": "Rủi ro học vụ", "Tên chỉ số học vụ": "Tỷ lệ thôi học (Dropout)", "Giá trị Synthetic Data": f"{dropout_count / n * 100:.1f}% ({dropout_count:,} SV)", "Ghi chú & Đơn vị": "Tự nguyện hoặc Quá hạn 6 năm"},
        {"STT": 20, "Nhóm chỉ số": "Rủi ro học vụ", "Tên chỉ số học vụ": "Tỷ lệ từng bị cảnh cáo học vụ", "Giá trị Synthetic Data": f"{susp_count / n * 100:.1f}% ({susp_count:,} SV)", "Ghi chú & Đơn vị": "Tạm dừng kỳ học"},
        
        {"STT": 21, "Nhóm chỉ số": "Xếp loại TN", "Tên chỉ số học vụ": "Tỷ lệ Bằng Xuất sắc", "Giá trị Synthetic Data": f"{int(grad['degree_classification'].eq('excellent').sum()) / grad_count * 100:.1f}% ({int(grad['degree_classification'].eq('excellent').sum()):,} SV)" if is_grad_cohort else "-", "Ghi chú & Đơn vị": "GPA 3.60 - 4.00"},
        {"STT": 22, "Nhóm chỉ số": "Xếp loại TN", "Tên chỉ số học vụ": "Tỷ lệ Bằng Giỏi", "Giá trị Synthetic Data": f"{int(grad['degree_classification'].eq('good').sum()) / grad_count * 100:.1f}% ({int(grad['degree_classification'].eq('good').sum()):,} SV)" if is_grad_cohort else "-", "Ghi chú & Đơn vị": "GPA 3.20 - 3.59"},
        {"STT": 23, "Nhóm chỉ số": "Xếp loại TN", "Tên chỉ số học vụ": "Tỷ lệ Bằng Khá", "Giá trị Synthetic Data": f"{int(grad['degree_classification'].eq('fair').sum()) / grad_count * 100:.1f}% ({int(grad['degree_classification'].eq('fair').sum()):,} SV)" if is_grad_cohort else "-", "Ghi chú & Đơn vị": "GPA 2.80 - 3.19"},
        {"STT": 24, "Nhóm chỉ số": "Xếp loại TN", "Tên chỉ số học vụ": "Tỷ lệ Bằng Trung bình khá", "Giá trị Synthetic Data": f"{int(grad['degree_classification'].eq('fairly_average').sum()) / grad_count * 100:.1f}% ({int(grad['degree_classification'].eq('fairly_average').sum()):,} SV)" if is_grad_cohort else "-", "Ghi chú & Đơn vị": "GPA 2.40 - 2.79"},
        {"STT": 25, "Nhóm chỉ số": "Xếp loại TN", "Tên chỉ số học vụ": "Tỷ lệ Bằng Trung bình & Yếu", "Giá trị Synthetic Data": f"{int(grad['degree_classification'].isin(['average', 'below_average']).sum()) / grad_count * 100:.1f}% ({int(grad['degree_classification'].isin(['average', 'below_average']).sum()):,} SV)" if is_grad_cohort else "-", "Ghi chú & Đơn vị": "GPA < 2.40"},
    ]

    return pd.DataFrame(metrics_rows)


def build_grade_sheet(df_letters: pd.DataFrame, df_scores: pd.DataFrame) -> pd.DataFrame:
    """Build letter and score distributions."""
    records = []

    # Letter grades
    if not df_letters.empty:
        univ_letters = df_letters[df_letters["course_code"] == "ALL_UNIVERSITY"]
        for _, r in univ_letters.iterrows():
            records.append({
                "Phân loại đánh giá": "Điểm chữ (Letter Grade)",
                "Thang đo / Mức điểm": str(r["letter_grade"]),
                "Số lượng bản ghi": int(r["count"]),
                "Tỷ lệ phân bổ (%)": float(r["share"]),
                "Ghi chú học vụ": "Tỷ lệ trên tổng số lần đăng ký môn học",
            })

    # Score bins 10-point
    if not df_scores.empty:
        univ_10 = df_scores[(df_scores["course_code"] == "ALL_UNIVERSITY") & (df_scores["scale"] == "10-point")]
        for _, r in univ_10.iterrows():
            records.append({
                "Phân loại đánh giá": "Thang điểm 10 (Score Distribution)",
                "Thang đo / Mức điểm": f"Khoảng {r['score_bin']}",
                "Số lượng bản ghi": int(r["count"]),
                "Tỷ lệ phân bổ (%)": float(r["share"]),
                "Ghi chú học vụ": "Điểm tổng kết môn học (Final Score)",
            })

    return pd.DataFrame(records)


def build_faculty_load_sheet(df_lecturers: pd.DataFrame) -> pd.DataFrame:
    """Build faculty teaching load analysis by department."""
    semesters = [f"HK{y}{s}" for y in range(23, 27) for s in (1, 2) if not (y == 26 and s == 2)]
    all_classes = []
    for sem in semesters:
        c_file = CLASSES_DIR / f"class_{sem.lower()}.csv"
        if c_file.exists():
            df_c = pd.read_csv(c_file)
            all_classes.append(df_c)

    if not all_classes or df_lecturers.empty:
        return pd.DataFrame()

    df_all_c = pd.concat(all_classes, ignore_index=True)

    records = []
    for dept, grp in df_lecturers.groupby("department"):
        uids = set(grp["user_id"])
        sub_c = df_all_c[df_all_c["lecturer_id"].isin(uids)]

        # Class counts per lecturer per semester
        sem_counts = []
        for sem in semesters:
            sem_c = sub_c[sub_c["semester"] == sem]
            vc = sem_c["lecturer_id"].value_counts()
            for uid in uids:
                sem_counts.append(vc.get(uid, 0))

        records.append({
            "Khoa / Bộ môn phụ trách": dept,
            "Số lượng GV": len(uids),
            "Tổng lớp phụ trách (7 kỳ gần nhất)": len(sub_c),
            "Số lớp TB / GV / Kỳ": float(np.mean(sem_counts)) if sem_counts else 0.0,
            "Lớp ít nhất (Min)": int(np.min(sem_counts)) if sem_counts else 0,
            "Lớp nhiều nhất (Max)": int(np.max(sem_counts)) if sem_counts else 0,
            "Độ lệch chuẩn (Std)": float(np.std(sem_counts)) if sem_counts else 0.0,
        })

    return pd.DataFrame(records).sort_values(by="Khoa / Bộ môn phụ trách")


def add_charts_to_cohort_sheet(ws: openpyxl.worksheet.worksheet.Worksheet, cohort: str, df_students: pd.DataFrame, df_profiles: pd.DataFrame) -> None:
    """Add small supporting data tables and interactive charts (PieChart & BarChart) to cohort sheet."""
    sub = df_students[df_students["cohort"] == cohort]
    n = len(sub)
    if n == 0:
        return

    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    data_font = Font(name="Arial", size=9)

    # -------------------------------------------------------------
    # 1. BẢNG PHỤ 1 & BIỂU ĐỒ TRÒN: CƠ CẤU HỆ ĐÀO TẠO (Cột G, H, I)
    # -------------------------------------------------------------
    std_cnt = int((sub["program"] == "standard").sum())
    hq_cnt = int((sub["program"] == "high-quality").sum())
    adv_cnt = int((sub["program"] == "advanced").sum())

    ws.cell(row=1, column=7, value="Hệ đào tạo").font = header_font
    ws.cell(row=1, column=7).fill = header_fill
    ws.cell(row=1, column=8, value="Số lượng (SV)").font = header_font
    ws.cell(row=1, column=8).fill = header_fill
    ws.cell(row=1, column=9, value="Tỷ lệ (%)").font = header_font
    ws.cell(row=1, column=9).fill = header_fill

    prog_data = [
        ("Đại trà", std_cnt, std_cnt / n if n else 0.0),
        ("Chất lượng cao", hq_cnt, hq_cnt / n if n else 0.0),
        ("Tiên tiến", adv_cnt, adv_cnt / n if n else 0.0),
    ]
    for r_idx, (p_name, p_cnt, p_pct) in enumerate(prog_data, start=2):
        ws.cell(row=r_idx, column=7, value=p_name).font = data_font
        ws.cell(row=r_idx, column=7).border = thin_border
        ws.cell(row=r_idx, column=8, value=p_cnt).font = data_font
        ws.cell(row=r_idx, column=8).border = thin_border
        ws.cell(row=r_idx, column=8).number_format = "#,##0"
        ws.cell(row=r_idx, column=9, value=p_pct).font = data_font
        ws.cell(row=r_idx, column=9).border = thin_border
        ws.cell(row=r_idx, column=9).number_format = "0.0%"

    pie = PieChart()
    pie.title = f"Cơ cấu Hệ đào tạo ({cohort})"
    pie.width = 13.5
    pie.height = 7.5
    labels = Reference(ws, min_col=7, min_row=2, max_row=4)
    data = Reference(ws, min_col=8, min_row=1, max_row=4)
    pie.add_data(data, titles_from_data=True)
    pie.set_categories(labels)

    # Hiển thị % trực tiếp trên từng lát cắt của PieChart (chỉ hiện % duy nhất)
    pie.dataLabels = DataLabelList()
    pie.dataLabels.showPercent = True
    pie.dataLabels.showVal = False
    pie.dataLabels.showCatName = False
    pie.dataLabels.showSerName = False
    pie.dataLabels.showLegendKey = False
    ws.add_chart(pie, "G6")

    # -------------------------------------------------------------
    # 2. BẢNG PHỤ 2 & BIỂU ĐỒ CỘT: XẾP LOẠI TN HOẶC CHUYÊN NGÀNH (Cột K & L)
    # -------------------------------------------------------------
    grad = sub[sub["graduation_ready"] == True]
    is_grad_cohort = len(grad) > 0

    if is_grad_cohort:
        # Khóa đã có tốt nghiệp (K20, K21, K22): Biểu đồ Xếp loại tốt nghiệp
        ws.cell(row=1, column=11, value="Xếp loại tốt nghiệp").font = header_font
        ws.cell(row=1, column=11).fill = header_fill
        ws.cell(row=1, column=12, value="Số lượng (SV)").font = header_font
        ws.cell(row=1, column=12).fill = header_fill

        cls_data = [
            ("Xuất sắc", int(grad["degree_classification"].eq("excellent").sum())),
            ("Giỏi", int(grad["degree_classification"].eq("good").sum())),
            ("Khá", int(grad["degree_classification"].eq("fair").sum())),
            ("TB Khá", int(grad["degree_classification"].eq("fairly_average").sum())),
            ("TB & Yếu", int(grad["degree_classification"].isin(["average", "below_average"]).sum())),
        ]
        for r_idx, (c_name, c_cnt) in enumerate(cls_data, start=2):
            ws.cell(row=r_idx, column=11, value=c_name).font = data_font
            ws.cell(row=r_idx, column=11).border = thin_border
            ws.cell(row=r_idx, column=12, value=c_cnt).font = data_font
            ws.cell(row=r_idx, column=12).border = thin_border
            ws.cell(row=r_idx, column=12).number_format = "#,##0"

        bar = BarChart()
        bar.type = "col"
        bar.style = 10
        bar.title = f"Phân loại Bằng Tốt nghiệp ({cohort})"
        bar.y_axis.title = "Số lượng sinh viên"
        bar.x_axis.title = "Xếp loại bằng"
        bar.width = 14.5
        bar.height = 7.5
        b_labels = Reference(ws, min_col=11, min_row=2, max_row=6)
        b_data = Reference(ws, min_col=12, min_row=1, max_row=6)
        bar.add_data(b_data, titles_from_data=True)
        bar.set_categories(b_labels)
        bar.legend = None

        # Hiển thị số lượng cụ thể trên đỉnh mỗi cột (chỉ hiện con số)
        bar.dataLabels = DataLabelList()
        bar.dataLabels.showVal = True
        bar.dataLabels.showPercent = False
        bar.dataLabels.showCatName = False
        bar.dataLabels.showSerName = False
        bar.dataLabels.showLegendKey = False
        ws.add_chart(bar, "G19")

    else:
        # Khóa đang học (K23 - K26): Biểu đồ Phân bố Chuyên ngành đào tạo
        ws.cell(row=1, column=11, value="Chuyên ngành đào tạo").font = header_font
        ws.cell(row=1, column=11).fill = header_fill
        ws.cell(row=1, column=12, value="Số lượng (SV)").font = header_font
        ws.cell(row=1, column=12).fill = header_fill

        # Lấy phân bố chuyên ngành từ df_profiles
        c_num = cohort.replace("K", "")
        p_sub = df_profiles[df_profiles["student_id"].str.startswith(c_num)]
        if not p_sub.empty and "specialization" in p_sub.columns:
            spec_counts = p_sub["specialization"].value_counts().items()
        else:
            spec_counts = [("Khoa học Máy tính", n)]

        r_end = 1
        for r_idx, (s_name, s_cnt) in enumerate(spec_counts, start=2):
            ws.cell(row=r_idx, column=11, value=s_name).font = data_font
            ws.cell(row=r_idx, column=11).border = thin_border
            ws.cell(row=r_idx, column=12, value=int(s_cnt)).font = data_font
            ws.cell(row=r_idx, column=12).border = thin_border
            ws.cell(row=r_idx, column=12).number_format = "#,##0"
            r_end = r_idx

        bar = BarChart()
        bar.type = "col"
        bar.style = 11
        bar.title = f"Phân bố Chuyên ngành Đào tạo ({cohort})"
        bar.y_axis.title = "Số lượng sinh viên"
        bar.x_axis.title = "Chuyên ngành"
        bar.width = 15.5
        bar.height = 7.5
        b_labels = Reference(ws, min_col=11, min_row=2, max_row=r_end)
        b_data = Reference(ws, min_col=12, min_row=1, max_row=r_end)
        bar.add_data(b_data, titles_from_data=True)
        bar.set_categories(b_labels)
        bar.legend = None

        # Hiển thị số lượng cụ thể trên đỉnh mỗi cột (chỉ hiện con số)
        bar.dataLabels = DataLabelList()
        bar.dataLabels.showVal = True
        bar.dataLabels.showPercent = False
        bar.dataLabels.showCatName = False
        bar.dataLabels.showSerName = False
        bar.dataLabels.showLegendKey = False
        ws.add_chart(bar, "G19")


def add_charts_to_comparison_sheet(ws: openpyxl.worksheet.worksheet.Worksheet) -> None:
    """Add cross-cohort comparison charts (GPA & Graduation rates)."""
    pass


def add_charts_to_grade_sheet(ws: openpyxl.worksheet.worksheet.Worksheet) -> None:
    """Add letter grade distribution chart to Grade_Distribution sheet."""
    bar = BarChart()
    bar.type = "col"
    bar.style = 13
    bar.title = "Phân phối Điểm chữ Toàn trường (Letter Grade Distribution)"
    bar.y_axis.title = "Số lượt đăng ký môn học"
    bar.x_axis.title = "Mức điểm chữ"
    bar.width = 14
    bar.height = 7.5
    labels = Reference(ws, min_col=2, min_row=2, max_row=10)
    data = Reference(ws, min_col=3, min_row=1, max_row=10)
    bar.add_data(data, titles_from_data=True)
    bar.set_categories(labels)
    bar.legend = None

    # Hiển thị số lượng cụ thể trên đỉnh mỗi cột điểm chữ (chỉ hiện con số)
    bar.dataLabels = DataLabelList()
    bar.dataLabels.showVal = True
    bar.dataLabels.showPercent = False
    bar.dataLabels.showCatName = False
    bar.dataLabels.showSerName = False
    bar.dataLabels.showLegendKey = False
    ws.add_chart(bar, "G2")


def add_charts_to_faculty_sheet(ws: openpyxl.worksheet.worksheet.Worksheet) -> None:
    """Add faculty load comparison chart to Faculty_Teaching_Load sheet."""
    bar = BarChart()
    bar.type = "bar"  # Horizontal bar chart
    bar.style = 14
    bar.title = "Số lớp giảng dạy TB / GV / Kỳ theo từng Đơn vị phụ trách"
    bar.x_axis.title = "Số lớp TB / Kỳ"
    bar.y_axis.title = "Khoa / Bộ môn"
    bar.width = 15
    bar.height = 8.5
    labels = Reference(ws, min_col=1, min_row=2, max_row=ws.max_row)
    data = Reference(ws, min_col=4, min_row=1, max_row=ws.max_row)
    bar.add_data(data, titles_from_data=True)
    bar.set_categories(labels)
    bar.legend = None

    # Hiển thị số lớp TB trên mỗi thanh (chỉ hiện con số)
    bar.dataLabels = DataLabelList()
    bar.dataLabels.showVal = True
    bar.dataLabels.showPercent = False
    bar.dataLabels.showCatName = False
    bar.dataLabels.showSerName = False
    bar.dataLabels.showLegendKey = False
    ws.add_chart(bar, "A11")


def style_worksheet(ws: openpyxl.worksheet.worksheet.Worksheet, sheet_name: str) -> None:
    """Apply professional typography, borders, and number formats to an openpyxl worksheet."""
    ws.views.sheetView[0].showGridLines = True

    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")  # Navy Blue

    data_font = Font(name="Arial", size=9)
    bold_data_font = Font(name="Arial", size=9, bold=True)

    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    header_border = Border(
        left=Side(style="thin", color="1B365D"),
        right=Side(style="thin", color="1B365D"),
        top=Side(style="medium", color="1B365D"),
        bottom=Side(style="medium", color="1B365D"),
    )
    zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

    # Format header row (cho các cột bảng chính)
    max_c = min(ws.max_column, 6 if sheet_name.startswith("Cohort_K") else ws.max_column)
    for col_idx in range(1, max_c + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = header_border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.row_dimensions[1].height = 26

    # Format data rows
    for row_idx in range(2, ws.max_row + 1):
        ws.row_dimensions[row_idx].height = 20
        is_even = (row_idx % 2 == 0)

        for col_idx in range(1, max_c + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border
            if is_even:
                cell.fill = zebra_fill

            col_header = str(ws.cell(row=1, column=col_idx).value or "")
            val = cell.value

            # Numeric alignments
            if isinstance(val, (int, float)):
                if "%" in col_header or "Tỷ lệ" in col_header:
                    cell.number_format = "0.0%"
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                elif "GPA" in col_header or "Điểm" in col_header or "TB" in col_header or "Std" in col_header or "Ngày" in col_header:
                    cell.number_format = "#,##0.00"
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    cell.number_format = "#,##0"
                    cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                if col_idx == 1 and sheet_name == "Overview_Benchmark":
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                    cell.font = bold_data_font
                elif "STT" in col_header or "Khóa" in col_header or col_header in ["Học kỳ", "Hệ"]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif any(kw in col_header for kw in ["Giá trị", "Synthetic", "Số lượng", "Tỷ lệ", "GPA"]):
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

    # Auto-fit column widths with padding
    for col_idx in range(1, max_c + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for row_idx in range(1, ws.max_row + 1):
            cell_val = str(ws.cell(row=row_idx, column=col_idx).value or "")
            max_len = max(max_len, len(cell_val))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 11)


def export_validation_report(output_path: str = None) -> Path:
    """Main function to generate the comprehensive academic validation Excel workbook."""
    output_file = Path(output_path) if output_path else DEFAULT_OUTPUT_FILE

    print(f"[*] Đang tải dữ liệu mô phỏng từ {METRICS_DIR}...")
    df_univ, df_students, df_letters, df_scores, df_progress, df_profiles, df_lecturers = load_all_datasets()

    print("[*] Đang tổng hợp các bảng chỉ số học vụ...")
    df_overview = build_overview_sheet(df_univ, df_students)
    df_cohort_comp = build_cohort_comparison_sheet(df_students)
    df_grade = build_grade_sheet(df_letters, df_scores)
    df_faculty = build_faculty_load_sheet(df_lecturers)

    # Generate individual sheets for each cohort
    cohort_list = sorted([c for c in df_students["cohort"].dropna().unique().tolist() if c.startswith("K")])
    cohort_sheets_data = {}
    for c in cohort_list:
        df_cohort_single = build_single_cohort_sheet(c, df_students)
        cohort_sheets_data[f"Cohort_{c}"] = df_cohort_single

    print(f"[*] Đang ghi dữ liệu vào file Excel: {output_file.name}...")
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df_overview.to_excel(writer, sheet_name="Overview_Benchmark", index=False)
        df_cohort_comp.to_excel(writer, sheet_name="Cohort_Comparison", index=False)

        # Write each cohort sheet
        for sheet_name, df_data in cohort_sheets_data.items():
            df_data.to_excel(writer, sheet_name=sheet_name, index=False)

        if not df_grade.empty:
            df_grade.to_excel(writer, sheet_name="Grade_Distribution", index=False)

        if not df_faculty.empty:
            df_faculty.to_excel(writer, sheet_name="Faculty_Teaching_Load", index=False)

    print("[*] Đang áp dụng định dạng và vẽ các biểu đồ trực quan (Charts)...")
    wb = openpyxl.load_workbook(output_file)

    # 1. Styling cơ bản
    for sheet_name in wb.sheetnames:
        style_worksheet(wb[sheet_name], sheet_name)

    # 2. Vẽ biểu đồ cho từng Sheet Cohort (K20 -> K26)
    for c in cohort_list:
        ws_cohort = wb[f"Cohort_{c}"]
        add_cohort_charts_to_sheet = add_charts_to_cohort_sheet(ws_cohort, c, df_students, df_profiles)

    # 3. Vẽ biểu đồ cho Grade_Distribution và Faculty_Teaching_Load
    if "Grade_Distribution" in wb.sheetnames:
        add_charts_to_grade_sheet(wb["Grade_Distribution"])

    if "Faculty_Teaching_Load" in wb.sheetnames:
        add_charts_to_faculty_sheet(wb["Faculty_Teaching_Load"])

    wb.save(output_file)
    print(f"[✓] Đã xuất thành công báo cáo học vụ hoàn chỉnh kèm biểu đồ: {output_file.resolve()}\n")
    return output_file


if __name__ == "__main__":
    export_validation_report()
