import argparse
import csv
import os
import re
from collections import defaultdict
from typing import Dict, List


TAG_OR_VAR_PATTERN = re.compile(r"\[img:[^\]]+\]|\[[^\]]+\]|\{[^{}]*\}|&nbsp;", re.IGNORECASE)
ALNUM_PATTERN = re.compile(r"[A-Za-z0-9\u00C0-\u024F\u4E00-\u9FFF]")


def normalize_text(value: str) -> str:
    if value is None:
        return ""
    return value.strip()


def should_skip_row(row: Dict[str, str]) -> bool:
    key = (row.get("KEY") or "").strip()
    if key.startswith("//"):
        return True

    # 如果整行全空，也跳过
    return all((v is None or str(v).strip() == "") for v in row.values())


def is_symbolic_or_tag_only_source(text: str) -> bool:
    normalized = normalize_text(text)
    if normalized == "":
        return False

    stripped = TAG_OR_VAR_PATTERN.sub("", normalized)
    stripped = stripped.replace("\\n", "").replace("\n", "").strip()

    # 去掉标签后不含字母数字（仅符号/标点）则视为无需翻译
    return ALNUM_PATTERN.search(stripped) is None


def scan_file(file_path: str, source_col: str, target_cols: List[str]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []

    with open(file_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        if source_col not in fieldnames:
            return issues

        valid_targets = [col for col in target_cols if col in fieldnames]
        if not valid_targets:
            return issues

        for row_number, row in enumerate(reader, start=2):
            if should_skip_row(row):
                continue

            source_text = row.get(source_col)
            source_norm = normalize_text(source_text)
            if source_norm == "":
                continue
            if is_symbolic_or_tag_only_source(source_norm):
                continue

            key = row.get("KEY", "")

            for target_col in valid_targets:
                target_text = row.get(target_col)
                target_norm = normalize_text(target_text)
                if target_norm != "" and target_norm == source_norm:
                    issues.append(
                        {
                            "file": os.path.basename(file_path),
                            "row": str(row_number),
                            "key": key,
                            "source_col": source_col,
                            "target_col": target_col,
                            "source_preview": (source_text or "").replace("\n", "\\n")[:120],
                        }
                    )

    return issues


def write_report(report_path: str, issues: List[Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(report_path), exist_ok=True) if os.path.dirname(report_path) else None

    with open(report_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["file", "row", "key", "source_col", "target_col", "source_preview"],
        )
        writer.writeheader()
        writer.writerows(issues)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="检查目录中所有 CSV 的翻译遗漏情况（默认 en -> zh 相同视为漏译）。"
    )
    parser.add_argument("input_dir", help="CSV 所在目录")
    parser.add_argument(
        "--source-col",
        default="en",
        help="源语言列名（默认 en）",
    )
    parser.add_argument(
        "--target-cols",
        nargs="+",
        default=["zh"],
        help="目标语言列名（默认 zh，可传多个）",
    )
    parser.add_argument(
        "--report",
        default="missing_translation_report.csv",
        help="报告文件名或路径（默认 missing_translation_report.csv）",
    )
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    if not os.path.isdir(input_dir):
        raise SystemExit(f"输入目录不存在: {input_dir}")

    csv_files = sorted(
        name for name in os.listdir(input_dir)
        if name.lower().endswith(".csv") and os.path.isfile(os.path.join(input_dir, name))
    )

    if not csv_files:
        raise SystemExit("未找到任何 CSV 文件")

    all_issues: List[Dict[str, str]] = []
    file_counts: Dict[str, int] = {}
    col_counts: Dict[str, int] = defaultdict(int)

    for file_name in csv_files:
        file_path = os.path.join(input_dir, file_name)
        issues = scan_file(file_path, args.source_col, args.target_cols)
        all_issues.extend(issues)
        file_counts[file_name] = len(issues)
        for issue in issues:
            col_counts[issue["target_col"]] += 1

    # 输出汇总
    for file_name in csv_files:
        print(f"{file_name}: missing {file_counts[file_name]}")

    print("-" * 48)
    print(f"files scanned: {len(csv_files)}")
    print(f"total missing: {len(all_issues)}")
    if col_counts:
        print("by target column:")
        for col, count in sorted(col_counts.items()):
            print(f"  {col}: {count}")

    report_path = args.report
    if not os.path.isabs(report_path):
        report_path = os.path.join(input_dir, report_path)

    write_report(report_path, all_issues)
    print(f"report written: {report_path}")


if __name__ == "__main__":
    main()
