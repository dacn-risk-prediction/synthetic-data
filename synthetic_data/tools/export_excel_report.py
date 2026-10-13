"""Export academic validation report from generated synthetic data to an Excel (.xlsx) workbook.

This script aggregates university-wide and cohort-level synthetic metrics from
synthetic_data/generated/metrics/ and outputs a formatted multi-sheet Excel file.
"""

from pathlib import Path
import pandas as pd
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT_DIR = Path(__file__).resolve().parents[1]
METRICS_DIR = ROOT_DIR / "generated" / "metrics"
DEFAULT_OUTPUT_FILE = ROOT_DIR / "academic_validation_report.xlsx"


def load_metrics():
    """Load the required metrics CSV files."""
    univ_file = METRICS_DIR / "university_metrics.csv"
    student_file = METRICS_DIR / "student_metrics.csv"
    letter_file = METRICS_DIR / "letter_grade_distribution.csv"
    score_file = METRICS_DIR / "score_distribution.csv"

    if not univ_file.exists() or not student_file.exists():
        raise FileNotFoundError(
            f"Required metrics files not found in {METRICS_DIR}. "
            "Please run generate_academic_metrics.py first."
        )

    df_univ = pd.read_csv(univ_file)
    df_students = pd.read_csv(student_file, dtype={"student_id": str, "cohort": str})
    df_letters = pd.read_csv(letter_file) if letter_file.exists() else pd.DataFrame()
    df_scores = pd.read_csv(score_file) if score_file.exists() else pd.DataFrame()

    return df_univ, df_students, df_letters, df_scores


def build_overview_sheet(df_univ, df_students):
    """Build high-level university benchmark metrics."""
    metrics_map = dict(zip(df_univ["metric"], df_univ["value"]))
    num_map = dict(zip(df_univ["metric"], df_univ["numerator"]))
    den_map = dict(zip(df_univ["metric"], df_univ["denominator"]))

    # Calculations from students
    completed_cohorts = ["K13", "K14", "K15", "K16", "K17", "K18", "K19", "K20"]
    c_students = df_students[df_students["cohort"].isin(completed_cohorts)]
    c_grads = c_students[c_students["graduation_ready"] == True]

    tracked_count = int(metrics_map.get("tracked_students", len(df_students)))
    grad_all_rate = float(metrics_map.get("graduation_ready_rate", 0.0))
    grad_comp_rate = len(c_grads) / len(c_students) if len(c_students) else 0.0
    early_rate = float(metrics_map.get("graduation_early_rate", 0.0))
    on_time_rate = float(metrics_map.get("graduation_on_time_rate", 0.0))
    late_rate = float(metrics_map.get("graduation_late_rate", 0.0))

    exc_rate = float(metrics_map.get("degree_excellent_rate", 0.0))
    good_rate = float(metrics_map.get("degree_good_rate", 0.0))
    fair_rate = float(c_grads["degree_classification"].eq("fair").sum() / len(c_grads)) if len(c_grads) else 0.0
    f_avg_rate = float(c_grads["degree_classification"].eq("fairly_average").sum() / len(c_grads)) if len(c_grads) else 0.0
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
        # Nhóm 1: Quy mô & Tiến độ tốt nghiệp
        {
            "Nhóm danh mục": "1. Quy mô & Tiến độ tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tổng sinh viên mô phỏng toàn hệ thống",
            "Giá trị mô phỏng (Synthetic)": f"{tracked_count:,} sinh viên",
            "Ghi chú": "14 khóa từ K13 đến K26 (HK131 - HK261)",
        },
        {
            "Nhóm danh mục": "1. Quy mô & Tiến độ tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tỷ lệ tốt nghiệp chung (Toàn hệ thống)",
            "Giá trị mô phỏng (Synthetic)": f"{grad_all_rate * 100:.1f}%",
            "Ghi chú": f"{int(num_map.get('graduation_ready_rate', 0)):,} / {int(den_map.get('graduation_ready_rate', 0)):,} SV (Bao gồm cả các khóa đang học)",
        },
        {
            "Nhóm danh mục": "1. Quy mô & Tiến độ tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tỷ lệ tốt nghiệp trung bình các khóa đã hoàn thành (K13-K20)",
            "Giá trị mô phỏng (Synthetic)": f"{grad_comp_rate * 100:.1f}%",
            "Ghi chú": f"{len(c_grads):,} / {len(c_students):,} SV hoàn tất lộ trình đào tạo chuẩn",
        },
        {
            "Nhóm danh mục": "1. Quy mô & Tiến độ tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp sớm hạn (Early / 3.5 năm - Học kỳ 7)",
            "Giá trị mô phỏng (Synthetic)": f"{early_rate * 100:.1f}%",
            "Ghi chú": f"{int(num_map.get('graduation_early_rate', 0)):,} SV đạt chuẩn học vượt toàn khóa",
        },
        {
            "Nhóm danh mục": "1. Quy mô & Tiến độ tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp đúng hạn (On time / 4.0 năm - Học kỳ 8)",
            "Giá trị mô phỏng (Synthetic)": f"{on_time_rate * 100:.1f}%",
            "Ghi chú": f"{int(num_map.get('graduation_on_time_rate', 0)):,} SV (Chiếm tỷ lệ đa số theo tiến độ chuẩn)",
        },
        {
            "Nhóm danh mục": "1. Quy mô & Tiến độ tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp trễ hạn (Late / 4.5 - 6.0 năm - Kỳ 9 đến 12)",
            "Giá trị mô phỏng (Synthetic)": f"{late_rate * 100:.1f}%",
            "Ghi chú": f"{int(num_map.get('graduation_late_rate', 0)):,} SV (Trả nợ môn, tích lũy thêm CTXH/tiếng Anh)",
        },

        # Nhóm 2: Xếp loại tốt nghiệp
        {
            "Nhóm danh mục": "2. Xếp loại tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp loại Xuất sắc (GPA 3.60 - 4.00)",
            "Giá trị mô phỏng (Synthetic)": f"{exc_rate * 100:.1f}%",
            "Ghi chú": f"{int(num_map.get('degree_excellent_rate', 0)):,} SV tốt nghiệp",
        },
        {
            "Nhóm danh mục": "2. Xếp loại tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp loại Giỏi (GPA 3.20 - 3.59)",
            "Giá trị mô phỏng (Synthetic)": f"{good_rate * 100:.1f}%",
            "Ghi chú": f"{int(num_map.get('degree_good_rate', 0)):,} SV tốt nghiệp",
        },
        {
            "Nhóm danh mục": "2. Xếp loại tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp loại Khá (GPA 2.80 - 3.19)",
            "Giá trị mô phỏng (Synthetic)": f"{fair_rate * 100:.1f}%",
            "Ghi chú": "Phân khúc năng lực khá",
        },
        {
            "Nhóm danh mục": "2. Xếp loại tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp loại Trung bình khá (GPA 2.40 - 2.79)",
            "Giá trị mô phỏng (Synthetic)": f"{f_avg_rate * 100:.1f}%",
            "Ghi chú": "Phân khúc phổ thông",
        },
        {
            "Nhóm danh mục": "2. Xếp loại tốt nghiệp",
            "Chỉ số học vụ (Metric)": "Tốt nghiệp loại Trung bình & Trung bình yếu (GPA < 2.40)",
            "Giá trị mô phỏng (Synthetic)": f"{avg_rate * 100:.1f}%",
            "Ghi chú": f"{int(num_map.get('degree_average_rate', 0)):,} SV tốt nghiệp",
        },

        # Nhóm 3: Học lực & Điểm tích lũy (GPA)
        {
            "Nhóm danh mục": "3. Học lực & Điểm tích lũy (GPA)",
            "Chỉ số học vụ (Metric)": "Điểm GPA trung bình tích lũy toàn hệ thống (Thang 4.0)",
            "Giá trị mô phỏng (Synthetic)": f"{gpa_4_mean:.2f} / 4.0",
            "Ghi chú": "Điểm trung bình của sinh viên có dữ liệu môn học",
        },
        {
            "Nhóm danh mục": "3. Học lực & Điểm tích lũy (GPA)",
            "Chỉ số học vụ (Metric)": "Điểm học phần trung bình toàn trường (Thang 10.0)",
            "Giá trị mô phỏng (Synthetic)": f"{score_10_mean:.2f} / 10.0",
            "Ghi chú": f"Tổng cộng {int(metrics_map.get('score_10_count', 0)):,} lượt điểm học phần",
        },
        {
            "Nhóm danh mục": "3. Học lực & Điểm tích lũy (GPA)",
            "Chỉ số học vụ (Metric)": "Độ lệch chuẩn điểm học phần (Std Thang 10)",
            "Giá trị mô phỏng (Synthetic)": f"{score_10_std:.2f} điểm",
            "Ghi chú": "Độ phân tán năng lực học tập",
        },
        {
            "Nhóm danh mục": "3. Học lực & Điểm tích lũy (GPA)",
            "Chỉ số học vụ (Metric)": "Tỷ lệ đạt chuẩn tiếng Anh tích lũy",
            "Giá trị mô phỏng (Synthetic)": f"{eng_rate * 100:.1f}%",
            "Ghi chú": f"{int(num_map.get('english_eligibility_rate', 0)):,} / {len(df_students):,} sinh viên",
        },
        {
            "Nhóm danh mục": "3. Học lực & Điểm tích lũy (GPA)",
            "Chỉ số học vụ (Metric)": "Số ngày Công tác Xã hội (CTXH) tích lũy trung bình",
            "Giá trị mô phỏng (Synthetic)": f"{ctxh_mean:.1f} ngày",
            "Ghi chú": "Chuẩn KLTN: >= 12 ngày, chuẩn tốt nghiệp: >= 15 ngày",
        },

        # Nhóm 4: Thôi học & Kỷ luật học vụ
        {
            "Nhóm danh mục": "4. Thôi học & Kỷ luật học vụ",
            "Chỉ số học vụ (Metric)": "Tổng tỷ lệ thôi học / bỏ học (Toàn trường)",
            "Giá trị mô phỏng (Synthetic)": f"{drop_rate * 100:.1f}%",
            "Ghi chú": f"{int(num_map.get('dropout_rate', 0)):,} / {len(df_students):,} sinh viên",
        },
        {
            "Nhóm danh mục": "4. Thôi học & Kỷ luật học vụ",
            "Chỉ số học vụ (Metric)": "- Tự nguyện thôi học (Hoàn cảnh gia đình, cá nhân)",
            "Giá trị mô phỏng (Synthetic)": f"{vol_drop_rate * 100:.1f}%",
            "Ghi chú": f"{int(num_map.get('voluntary_dropout_rate', 0)):,} sinh viên",
        },
        {
            "Nhóm danh mục": "4. Thôi học & Kỷ luật học vụ",
            "Chỉ số học vụ (Metric)": "- Buộc thôi học (Quá thời hạn đào tạo tối đa 12 kỳ)",
            "Giá trị mô phỏng (Synthetic)": f"{forced_drop_rate * 100:.1f}%",
            "Ghi chú": f"{int(num_map.get('forced_dropout_rate', 0)):,} sinh viên vi phạm khung thời gian",
        },
        {
            "Nhóm danh mục": "4. Thôi học & Kỷ luật học vụ",
            "Chỉ số học vụ (Metric)": "Tỷ lệ sinh viên từng bị cảnh cáo học vụ (Tạm dừng)",
            "Giá trị mô phỏng (Synthetic)": f"{susp_rate * 100:.1f}%",
            "Ghi chú": f"{int(num_map.get('academic_suspension_rate', 0)):,} sinh viên từng bị tạm dừng kỳ học",
        },
    ]

    return pd.DataFrame(overview_rows)


def build_cohort_sheet(df_students):
    """Build detailed per-cohort metrics."""
    records = []
    cohort_list = sorted(df_students["cohort"].dropna().unique().tolist())

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

        avg_gpa = float(sub["gpa_4"].dropna().mean()) if not sub["gpa_4"].dropna().empty else 0.0
        avg_credits = float(sub["passed_credits"].mean()) if n else 0.0

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
            "Tỷ lệ tốt nghiệp (%)": grad_rate,
            "Sớm hạn - 3.5 năm (SV)": early_count,
            "Đúng hạn - 4.0 năm (SV)": on_time_count,
            "Trễ hạn - 4.5-6.0 năm (SV)": late_count,
            "Đang học (SV)": cont_count,
            "Tỷ lệ đang học (%)": cont_rate,
            "Thôi học (SV)": dropout_count,
            "Tỷ lệ thôi học (%)": dropout_rate,
            "GPA TB khóa (Thang 4)": avg_gpa,
            "Tín chỉ tích lũy TB": avg_credits,
            "Xếp loại Xuất sắc (SV)": exc_count,
            "Xếp loại Giỏi (SV)": good_count,
            "Xếp loại Khá (SV)": fair_count,
            "Xếp loại TB Khá (SV)": f_avg_count,
            "Xếp loại TB & Yếu (SV)": avg_cls_count,
        })

    return pd.DataFrame(records)


def build_grade_sheet(df_letters, df_scores):
    """Build letter and score distributions."""
    records = []

    # Letter grades
    if not df_letters.empty:
        univ_letters = df_letters[df_letters["course_code"] == "ALL_UNIVERSITY"]
        total_letters = univ_letters["count"].sum()
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


def style_worksheet(ws, sheet_name):
    """Apply professional typography and colors to an openpyxl worksheet."""
    ws.views.sheetView[0].showGridLines = True

    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")  # Navy Blue
    data_font = Font(name="Arial", size=10)
    bold_data_font = Font(name="Arial", size=10, bold=True)

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

    # Format header row
    for col_idx in range(1, ws.max_column + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = header_border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.row_dimensions[1].height = 28

    # Format data rows
    for row_idx in range(2, ws.max_row + 1):
        ws.row_dimensions[row_idx].height = 20
        is_even = (row_idx % 2 == 0)

        for col_idx in range(1, ws.max_column + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border
            if is_even:
                cell.fill = zebra_fill

            col_header = str(ws.cell(row=1, column=col_idx).value or "")

            # Alignments & Number formats
            val = cell.value
            if isinstance(val, (int, float)):
                if "%" in col_header or "Tỷ lệ" in col_header or "rate" in col_header.lower() or "share" in col_header.lower():
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
                elif "Khoa" in col_header or "Khóa" in col_header or "Đơn vị" in col_header or "Thang đo" in col_header:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif "Synthetic" in col_header or "Giá trị" in col_header:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

    # Auto-fit column widths with padding
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if cell.number_format and "0.0%" in cell.number_format:
                val_str += "%"
            max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)


def export_validation_report(output_path=None):
    """Main function to generate the academic validation Excel workbook."""
    output_file = Path(output_path) if output_path else DEFAULT_OUTPUT_FILE

    print(f"[*] Đang tải dữ liệu mô phỏng từ {METRICS_DIR}...")
    df_univ, df_students, df_letters, df_scores = load_metrics()

    print("[*] Đang tổng hợp các bảng chỉ số học vụ...")
    df_overview = build_overview_sheet(df_univ, df_students)
    df_cohort = build_cohort_sheet(df_students)
    df_grade = build_grade_sheet(df_letters, df_scores)

    print(f"[*] Đang ghi dữ liệu vào file Excel: {output_file.name}...")
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df_overview.to_excel(writer, sheet_name="Overview_Benchmark", index=False)
        df_cohort.to_excel(writer, sheet_name="Cohort_Breakdown", index=False)
        df_grade.to_excel(writer, sheet_name="Grade_Distribution", index=False)

    print("[*] Đang áp dụng định dạng (styling, gridlines, column widths)...")
    wb = openpyxl.load_workbook(output_file)
    for sheet_name in wb.sheetnames:
        style_worksheet(wb[sheet_name], sheet_name)

    wb.save(output_file)
    print(f"[✓] Đã xuất thành công báo cáo học vụ hoàn chỉnh: {output_file.resolve()}\n")
    return output_file


if __name__ == "__main__":
    export_validation_report()
