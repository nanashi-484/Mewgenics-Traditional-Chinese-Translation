import argparse
import csv
import os
import re
from collections import Counter
from typing import Dict, Tuple

TERM_PATTERNS = {
    "Brace": re.compile(r"\bbrace\b", re.IGNORECASE),
    "immobilize": re.compile(r"\bimmobilize(?:d|s|ing)?\b", re.IGNORECASE),
    "Bruise": re.compile(r"\bbruise\b", re.IGNORECASE),
    "Knockback": re.compile(r"\bknockback\b", re.IGNORECASE),
    "Poison": re.compile(r"\bpoison\b", re.IGNORECASE),
    "Thorns": re.compile(r"\bthorns\b", re.IGNORECASE),
}

TERM_REPLACEMENTS = {
    "Brace": "护甲",
    "immobilize": "定身",
    "Bruise": "挫伤",
    "Knockback": "击退",
    "Poison": "中毒",
    "Thorns": "荆棘",
}

REPORT_SKIP_FILES = {
    "missing_translation_report.csv",
    "m_newline_scan_report.csv",
}

CJK_PATTERN = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")


def has_cjk(text: str) -> bool:
    return bool(CJK_PATTERN.search(text or ""))


def fix_zh_terms(text: str) -> Tuple[str, Counter]:
    fixed = text
    term_counter: Counter = Counter()

    for term, pattern in TERM_PATTERNS.items():
        replacement = TERM_REPLACEMENTS[term]

        def _repl(_: re.Match) -> str:
            term_counter[term] += 1
            return replacement

        fixed = pattern.sub(_repl, fixed)

    return fixed, term_counter


def process_file(input_path: str, output_path: str) -> Tuple[int, Counter]:
    rows_changed = 0
    file_counter: Counter = Counter()

    with open(input_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()

        for row in rows:
            key = (row.get("KEY") or "").strip()
            if key.startswith("//"):
                writer.writerow(row)
                continue

            if "zh" not in row or row["zh"] is None:
                writer.writerow(row)
                continue

            zh_text = row["zh"]
            if not zh_text or not has_cjk(zh_text):
                writer.writerow(row)
                continue

            fixed_text, term_hits = fix_zh_terms(zh_text)
            if fixed_text != zh_text:
                row["zh"] = fixed_text
                rows_changed += 1
                file_counter.update(term_hits)

            writer.writerow(row)

    return rows_changed, file_counter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="修复 zh 列中的中英混杂术语（Brace/immobilize/Bruise/Knockback/Poison/Thorns）。"
    )
    parser.add_argument("input_dir", help="CSV 所在目录（例如 data/text）")
    parser.add_argument(
        "--output-dir",
        default="fixed_terms_output",
        help="输出子目录名（默认 fixed_terms_output）",
    )
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    if not os.path.isdir(input_dir):
        raise SystemExit(f"输入目录不存在: {input_dir}")

    output_dir = os.path.join(input_dir, args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    csv_files = sorted(
        name
        for name in os.listdir(input_dir)
        if name.lower().endswith(".csv")
        and name not in REPORT_SKIP_FILES
        and os.path.isfile(os.path.join(input_dir, name))
    )

    total_rows_changed = 0
    total_counter: Counter = Counter()

    for name in csv_files:
        src = os.path.join(input_dir, name)
        dst = os.path.join(output_dir, name)

        rows_changed, file_counter = process_file(src, dst)
        total_rows_changed += rows_changed
        total_counter.update(file_counter)

        print(f"{name}: rows changed {rows_changed}")

    print("-" * 48)
    print(f"files processed: {len(csv_files)}")
    print(f"rows changed: {total_rows_changed}")
    print("term replacements:")
    print(f"  Brace -> 护甲: {total_counter['Brace']}")
    print(f"  immobilize -> 定身: {total_counter['immobilize']}")
    print(f"  Bruise -> 挫伤: {total_counter['Bruise']}")
    print(f"  Knockback -> 击退: {total_counter['Knockback']}")
    print(f"  Poison -> 中毒: {total_counter['Poison']}")
    print(f"  Thorns -> 荆棘: {total_counter['Thorns']}")
    print(f"output dir: {output_dir}")


if __name__ == "__main__":
    main()
