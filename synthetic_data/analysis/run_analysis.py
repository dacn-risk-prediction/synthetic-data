"""Academic Curriculum Analysis CLI and Demonstration Tool.

Executes analysis and lookup of training program roadmaps, required courses,
and prerequisite requirements for student cohorts across academic terms 1 to 8 (K20 - K26).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add current directory to sys.path to enable imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysis_helpers import (
    format_cohort_graduation_report,
    format_course_lecturers_report,
    format_curriculum_report,
    format_lecturer_courses_report,
    format_student_history_report,
    get_cohort_graduation_analysis,
    get_courses_by_lecturer,
    get_curriculum_for_cohort_semester,
    get_curriculum_for_cohort_term,
    get_full_curriculum_roadmap,
    get_lecturers_by_course,
    get_student_academic_history,
    normalize_cohort,
    resolve_semester,
)


def run_demo():
    """Run an illustrative demonstration of curriculum retrieval across cohorts and terms."""
    print("\n" + "=" * 90)
    print(" HỆ THỐNG TRA CỨU CHƯƠNG TRÌNH ĐÀO TẠO & LỘ TRÌNH MÔN HỌC (DEMO ANALYSIS) ".center(90, "="))
    print("=" * 90)
    print("Khảo sát dữ liệu đào tạo ABET Khoa Khoa học & Kỹ thuật Máy tính - ĐHBK ĐHQG-HCM (K20 - K26)")

    # 1. K24 tại Học kỳ 1 (chỉ cần nhập số 1)
    print("\n[DEMO 1] Khóa K24 - Học kỳ 1 (chỉ cần nhập số 1):")
    res_k24_hk1 = get_curriculum_for_cohort_semester("K24", 1)
    print(format_curriculum_report(res_k24_hk1))

    # 2. K24 tại Học kỳ 2 (chỉ cần nhập số 2) - có môn tiên quyết (TQ/KN)
    print("\n[DEMO 2] Khóa K24 - Học kỳ 2 (chỉ cần nhập số 2) kèm ràng buộc tiên quyết:")
    res_k24_hk2 = get_curriculum_for_cohort_semester("K24", 2)
    print(format_curriculum_report(res_k24_hk2))

    # 3. K24 tại Học kỳ 6 (nhập số 6) - Bắt buộc + Tự chọn chuyên ngành AI
    print("\n[DEMO 3] Khóa K24 - Học kỳ 6 (nhập số 6) theo định hướng Trí tuệ Nhân tạo (AI):")
    res_k24_hk6 = get_curriculum_for_cohort_semester("K24", 6, specialization="AI")
    print(format_curriculum_report(res_k24_hk6, show_electives_pool=True))

    # 4. So sánh cùng một thời điểm: Các khóa đang học ở kỳ thứ mấy?
    print("\n" + "=" * 90)
    print(" [DEMO 4] BẢNG SO SÁNH LỘ TRÌNH CÁC KHÓA ĐANG CÙNG HỌC TẠI HỌC KỲ HK241 ".center(90, "="))
    print("=" * 90)
    print(f"{'Khóa':<8} {'CTĐT áp dụng':<14} {'Học kỳ theo lộ trình':<24} {'Số môn BB':<12} {'Số TC BB':<12} {'TC Tự chọn':<12}")
    print("-" * 90)

    for ch in ["K24", "K23", "K22", "K21"]:
        c_res = get_curriculum_for_cohort_semester(ch, "HK241")
        if c_res["status"] == "NORMAL":
            sem_name = f"Học kỳ {c_res['relative_semester']} ({c_res['recommended_semester']})"
            bb_count = len(c_res["compulsory_courses"])
            bb_credits = int(c_res["total_compulsory_credits"])
            tc_credits = c_res["elective_guidance"]["recommended_elective_credits"]
            print(
                f"{c_res['cohort']:<8} {c_res['curriculum_id']:<14} {sem_name:<24} "
                f"{bb_count:<12} {bb_credits:<12} {tc_credits:<12}"
            )
        else:
            print(f"{ch:<8} - {c_res['status_message']}")
    print("=" * 90)

    # 5. Tra cứu lịch sử học tập từng kỳ của sinh viên (MSSV: 2028899)
    print("\n" + "=" * 90)
    print(" [DEMO 5] TRA CỨU LỊCH SỬ HỌC TẬP TỪNG KỲ CỦA SINH VIÊN (MSSV: 2028899) ".center(90, "="))
    print("=" * 90)
    st_res = get_student_academic_history("2028899")
    print(format_student_history_report(st_res))

    # 6. Thống kê tỷ lệ tốt nghiệp sớm, đúng hạn & trễ hạn của khóa K20
    print("\n" + "=" * 90)
    print(" [DEMO 6] THỐNG KÊ TỶ LỆ TỐT NGHIỆP SỚM, ĐÚNG HẠN & TRỄ HẠN - KHÓA K20 ".center(90, "="))
    print("=" * 90)
    grad_res = get_cohort_graduation_analysis("K20")
    print(format_cohort_graduation_report(grad_res))


def main():
    parser = argparse.ArgumentParser(
        description="Công cụ tra cứu môn học theo Khóa, Học kỳ, Lịch sử sinh viên & Thống kê tốt nghiệp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng cực kỳ đơn giản:
  python run_analysis.py -c K20 --grad       # Thống kê tỷ lệ tốt nghiệp sớm, đúng hạn, trễ hạn K20
  python run_analysis.py K20 --grad          # Tra cứu nhanh tỷ lệ tốt nghiệp khóa K20
  python run_analysis.py K20 --grad --json   # Xuất thống kê tỷ lệ tốt nghiệp dạng JSON
  python run_analysis.py 2028899             # Tra cứu lịch sử học tập của SV theo MSSV
  python run_analysis.py -st 2031846         # Tra cứu sinh viên theo MSSV, Email hoặc Tên
  python run_analysis.py -st 2028899 --json  # Xuất lịch sử học tập dạng JSON
  python run_analysis.py K24 1               # Tra cứu học kỳ 1 của khóa K24
  python run_analysis.py K24 2               # Tra cứu học kỳ 2 của khóa K24
  python run_analysis.py 3                   # Tra cứu học kỳ 3 (mặc định khóa K24)
  python run_analysis.py -c K24 -s 1         # Dùng cờ -c và -s
  python run_analysis.py -c K24 -t 2         # Dùng cờ -t (term: 1..8)
  python run_analysis.py -c K24 -t 6 -spec AI -e  # Kỳ 6 chuyên ngành AI kèm môn tự chọn
  python run_analysis.py -c K24 --all        # Xem trọn bộ lộ trình 8 học kỳ chuẩn
  python run_analysis.py --lecturer GV00001  # Tra cứu danh sách môn giảng viên GV00001 có thể dạy
  python run_analysis.py --course MT1003     # Tra cứu danh sách giảng viên đủ điều kiện dạy MT1003
  python run_analysis.py                     # Chạy demo so sánh minh họa
        """,
    )

    parser.add_argument(
        "positional_args",
        nargs="*",
        help="Nhập nhanh [MSSV] hoặc [KHÓA] [HỌC KỲ (1..8)], ví dụ: '2028899', 'K24 1' hoặc chỉ số kỳ '2'",
    )
    parser.add_argument(
        "-st",
        "--student",
        "--mssv",
        dest="student",
        metavar="STUDENT_QUERY",
        help="Tra cứu hồ sơ & lịch sử học tập từng kỳ của sinh viên (nhập MSSV, Email hoặc Họ tên)",
    )
    parser.add_argument(
        "-c",
        "--cohort",
        metavar="COHORT",
        help="Khóa tuyển sinh (VD: K24, 24, K20..K26). Mặc định: K24",
    )
    parser.add_argument(
        "-s",
        "-t",
        "--semester",
        "--term",
        dest="semester",
        metavar="TERM",
        help="Học kỳ theo lộ trình: chỉ cần nhập số 1, 2, 3, ..., 8 (hoặc mã học kỳ HK241)",
    )
    parser.add_argument(
        "-spec",
        "--specialization",
        metavar="SPEC",
        help="Chuyên ngành định hướng lọc môn tự chọn (VD: AI, SE, DATA, SEC, CS)",
    )
    parser.add_argument(
        "-e",
        "--electives",
        action="store_true",
        help="Hiển thị danh sách chi tiết các môn tự chọn khả dụng cho học kỳ này",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Hiển thị toàn bộ lộ trình 8 học kỳ chuẩn của khóa sinh viên",
    )
    parser.add_argument(
        "-grad",
        "--grad",
        "--graduation",
        action="store_true",
        dest="graduation",
        help="Thống kê tỷ lệ tốt nghiệp sớm (Kỳ 7 - 3.5 năm), đúng hạn (Kỳ 8 - 4.0 năm) và trễ hạn (kỳ 9..12) của một khóa",
    )
    parser.add_argument(
        "-l",
        "--lecturer",
        metavar="LECTURER_ID",
        help="Tra cứu danh sách các môn giảng viên có thể dạy (VD: GV00001, GV00056...)",
    )
    parser.add_argument(
        "--course",
        metavar="COURSE_CODE",
        help="Tra cứu danh sách giảng viên đủ điều kiện dạy môn học (VD: CO1005, MT1003, CO3117...)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất kết quả dưới định dạng JSON",
    )

    args = parser.parse_args()

    # Tra cứu lịch sử học tập theo từng kỳ của sinh viên
    if args.student:
        info = get_student_academic_history(args.student)
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(format_student_history_report(info))
        return

    # Tra cứu môn học theo giảng viên
    if args.lecturer:
        info = get_courses_by_lecturer(args.lecturer)
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(format_lecturer_courses_report(info))
        return

    # Tra cứu giảng viên theo môn học
    if args.course:
        info = get_lecturers_by_course(args.course)
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(format_course_lecturers_report(info))
        return

    # Check graduation query from flags or positional tokens
    is_graduation_query = bool(args.graduation)
    grad_keywords = {"grad", "-grad", "--grad", "graduation", "--graduation", "totnghiep", "tot-nghiep"}
    filtered_pos = []
    for arg in args.positional_args:
        if arg.lower() in grad_keywords:
            is_graduation_query = True
        else:
            filtered_pos.append(arg)

    if is_graduation_query:
        target_cohort = args.cohort
        if not target_cohort and filtered_pos:
            target_cohort = filtered_pos[0].strip()
        target_cohort = target_cohort or "K20"

        grad_info = get_cohort_graduation_analysis(target_cohort)
        if args.json:
            print(json.dumps(grad_info, ensure_ascii=False, indent=2))
        else:
            print(format_cohort_graduation_report(grad_info))
        return

    # Determine cohort and semester from positional args or flags
    target_cohort = args.cohort
    target_semester = args.semester

    if filtered_pos:
        pos = filtered_pos
        if len(pos) == 1:
            val = pos[0].strip()
            # If student query: starts with SV, contains @, or is 7-digit MSSV
            if "@" in val or val.upper().startswith("SV") or (val.isdigit() and len(val) >= 7):
                info = get_student_academic_history(val)
                if args.json:
                    print(json.dumps(info, ensure_ascii=False, indent=2))
                else:
                    print(format_student_history_report(info))
                return

            # If single argument is a number (e.g. '1'..'8'), treat as semester
            if (val.isdigit() and len(val) <= 2) or (val.upper().startswith("HK") and len(val) <= 3):
                target_semester = val
                if not target_cohort:
                    target_cohort = "K24"
            else:
                target_cohort = val
                if not target_semester:
                    target_semester = 1
        elif len(pos) >= 2:
            # Check if first or second is number
            if pos[0].strip().isdigit():
                target_semester = pos[0].strip()
                target_cohort = pos[1].strip()
            else:
                target_cohort = pos[0].strip()
                target_semester = pos[1].strip()

    # If no arguments provided at all, execute demo
    if not target_cohort and not target_semester and not args.all:
        run_demo()
        return

    target_cohort = target_cohort or "K24"

    # Display entire 8-semester roadmap
    if args.all:
        roadmap = get_full_curriculum_roadmap(
            cohort=target_cohort, specialization=args.specialization
        )
        if args.json:
            print(json.dumps(roadmap, ensure_ascii=False, indent=2))
        else:
            print("\n" + "=" * 88)
            print(
                f" TOÀN BỘ LỘ TRÌNH ĐÀO TẠO 8 HỌC KỲ - KHÓA {roadmap['cohort']} ({roadmap['curriculum_id']}) ".center(
                    88, "="
                )
            )
            print("=" * 88)
            print(
                f"Tổng tín chỉ bắt buộc: {int(roadmap['total_compulsory_credits'])} TC | "
                f"Tổng tín chỉ tự chọn: {int(roadmap['total_recommended_elective_credits'])} TC | "
                f"Tổng chương trình: {int(roadmap['total_roadmap_credits'])} TC\n"
            )
            for sem in roadmap["semesters"]:
                print(format_curriculum_report(sem, show_electives_pool=args.electives))
                print()
        return

    # Single semester/term lookup (default: term 1)
    target_semester = target_semester or 1
    res = get_curriculum_for_cohort_semester(
        cohort=target_cohort,
        semester=target_semester,
        specialization=args.specialization,
    )

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(format_curriculum_report(res, show_electives_pool=args.electives))


if __name__ == "__main__":
    main()
