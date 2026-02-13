import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from typing import Dict, List, Optional, Tuple

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

REPORT_SKIP_FILES = {
    "missing_translation_report.csv",
    "m_newline_scan_report.csv",
}

TERM_PATTERNS = {
    "Brace": re.compile(r"\bbrace\b", re.IGNORECASE),
    "immobilize": re.compile(r"\bimmobilize(?:d|s|ing)?\b", re.IGNORECASE),
    "Bruise": re.compile(r"\bbruise\b", re.IGNORECASE),
    "Knockback": re.compile(r"\bknockback\b", re.IGNORECASE),
    "Poison": re.compile(r"\bpoison(?:ed|ing)?\b", re.IGNORECASE),
    "Thorns": re.compile(r"\bthorns\b", re.IGNORECASE),
}

TERM_TO_ZH = {
    "Brace": "护甲",
    "immobilize": "定身",
    "Bruise": "挫伤",
    "Knockback": "击退",
    "Poison": "中毒",
    "Thorns": "荆棘",
}


def normalize_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return value.strip()


def should_skip_row(row: Dict[str, str]) -> bool:
    key = normalize_text(row.get("KEY"))
    if key.startswith("//"):
        return True
    return all(normalize_text(v) == "" for v in row.values())


def required_zh_terms_from_en(en_text: str) -> List[str]:
    required = []
    for term, pattern in TERM_PATTERNS.items():
        if pattern.search(en_text):
            required.append(TERM_TO_ZH[term])
    # 保留顺序去重
    out: List[str] = []
    seen = set()
    for t in required:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out


def zh_missing_required_terms(zh_text: str, required_terms: List[str]) -> List[str]:
    missing = []
    for term in required_terms:
        if term not in zh_text:
            missing.append(term)
    return missing


def call_openai_chat(api_key: str, model: str, system_prompt: str, user_prompt: str, timeout_sec: int = 90) -> str:
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    req = urllib.request.Request(
        OPENAI_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    choices = data.get("choices") or []
    if not choices:
        return ""

    content = ((choices[0].get("message") or {}).get("content") or "").strip()
    return content


def sanitize_model_output(text: str) -> str:
    s = text.strip()
    s = re.sub(r"^```[a-zA-Z]*\n", "", s)
    s = re.sub(r"\n```$", "", s)
    return s.strip()


def ai_rewrite_zh_for_terms(
    api_key: str,
    model: str,
    key: str,
    en_text: str,
    zh_text: str,
    required_terms: List[str],
    retries: int,
    sleep_sec: float,
) -> str:
    system_prompt = (
        "你是游戏本地化校对助手。"
        "任务是最小修改现有中文翻译，使术语映射正确。"
        "必须保留占位符和标签，例如 {catname}、[img:spd]、[b]...[/b]、[s:.7]。"
        "不要改变数值、语气和换行结构，除非为修正术语必须微调。"
        "只输出修正后的 zh 文本本体，不要解释。"
    )

    mapping_lines = "\n".join(f"- {k} -> {v}" for k, v in TERM_TO_ZH.items())
    required_line = "、".join(required_terms)

    user_prompt = (
        "请修正以下一条本地化的 zh，使其术语与 en 对齐。\n"
        f"KEY: {key}\n"
        f"EN: {en_text}\n"
        f"当前 ZH: {zh_text}\n"
        f"必须包含的中文术语: {required_line}\n"
        "术语映射表：\n"
        f"{mapping_lines}\n"
        "要求：\n"
        "1) 优先保留原 zh 文本，只做必要术语替换。\n"
        "2) 不删除任何占位符、标签、换行。\n"
        "3) 不要新增说明文字。\n"
        "只返回修正后的 zh。"
    )

    last_error = None
    for attempt in range(retries + 1):
        try:
            out = sanitize_model_output(call_openai_chat(api_key, model, system_prompt, user_prompt))
            if out:
                return out
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}"
            try:
                body = e.read().decode("utf-8", errors="ignore")
                if body:
                    last_error = f"{last_error}: {body[:260]}"
            except Exception:
                pass
        except Exception as e:
            last_error = str(e)

        if attempt < retries:
            time.sleep(sleep_sec)

    raise RuntimeError(last_error or "unknown api error")


def process_file(
    input_path: str,
    output_path: str,
    api_key: str,
    model: str,
    retries: int,
    sleep_sec: float,
    max_rows: int,
) -> Tuple[int, int, Counter]:
    rows_fixed = 0
    rows_failed = 0
    term_counter: Counter = Counter()

    with open(input_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()

        for row in rows:
            if should_skip_row(row):
                writer.writerow(row)
                continue

            if "en" not in row or "zh" not in row:
                writer.writerow(row)
                continue

            en_text = row.get("en") or ""
            zh_text = row.get("zh") or ""
            key = normalize_text(row.get("KEY"))

            required_terms = required_zh_terms_from_en(en_text)
            if not required_terms:
                writer.writerow(row)
                continue

            missing_terms = zh_missing_required_terms(zh_text, required_terms)
            if not missing_terms:
                writer.writerow(row)
                continue

            if max_rows > 0 and rows_fixed >= max_rows:
                writer.writerow(row)
                continue

            try:
                fixed_zh = ai_rewrite_zh_for_terms(
                    api_key=api_key,
                    model=model,
                    key=key,
                    en_text=en_text,
                    zh_text=zh_text,
                    required_terms=required_terms,
                    retries=retries,
                    sleep_sec=sleep_sec,
                )
                if fixed_zh and fixed_zh != zh_text:
                    row["zh"] = fixed_zh
                    rows_fixed += 1
                    for term in missing_terms:
                        if term in fixed_zh:
                            term_counter[term] += 1
            except Exception:
                rows_failed += 1

            writer.writerow(row)

    return rows_fixed, rows_failed, term_counter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="用 AI 对齐术语：当 en 含关键术语但 zh 未使用对应中文术语时，自动修正 zh。"
    )
    parser.add_argument("input_dir", help="CSV 所在目录（例如 data/text）")
    parser.add_argument("--output-dir", default="ai_term_aligned_output", help="输出子目录名")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI 模型名")
    parser.add_argument("--api-key", default="", help="OpenAI API Key（建议用 OPENAI_API_KEY 环境变量）")
    parser.add_argument("--retries", type=int, default=2, help="失败重试次数")
    parser.add_argument("--sleep", type=float, default=0.2, help="请求间隔秒数")
    parser.add_argument("--max-rows", type=int, default=0, help="最多修正行数（0 不限制）")
    args = parser.parse_args()

    api_key = normalize_text(args.api_key) or normalize_text(os.environ.get("OPENAI_API_KEY"))
    if not api_key:
        raise SystemExit("缺少 API Key：请传 --api-key 或设置 OPENAI_API_KEY")

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

    total_fixed = 0
    total_failed = 0
    global_counter: Counter = Counter()

    for name in csv_files:
        src = os.path.join(input_dir, name)
        dst = os.path.join(output_dir, name)

        fixed, failed, counter = process_file(
            input_path=src,
            output_path=dst,
            api_key=api_key,
            model=args.model,
            retries=max(0, args.retries),
            sleep_sec=max(0.0, args.sleep),
            max_rows=args.max_rows,
        )

        total_fixed += fixed
        total_failed += failed
        global_counter.update(counter)
        print(f"{name}: fixed {fixed}, failed {failed}")

    print("-" * 56)
    print(f"files processed: {len(csv_files)}")
    print(f"rows fixed: {total_fixed}")
    print(f"rows failed: {total_failed}")
    print("term coverage in fixed rows:")
    print(f"  护甲: {global_counter['护甲']}")
    print(f"  定身: {global_counter['定身']}")
    print(f"  挫伤: {global_counter['挫伤']}")
    print(f"  击退: {global_counter['击退']}")
    print(f"  中毒: {global_counter['中毒']}")
    print(f"  荆棘: {global_counter['荆棘']}")
    print(f"output dir: {output_dir}")


if __name__ == "__main__":
    main()
