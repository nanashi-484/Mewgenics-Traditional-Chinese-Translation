import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

SKIP_FILES = {
    "missing_translation_report.csv",
    "m_newline_scan_report.csv",
}


def normalize_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return value.strip()


def is_missing_translation(en_text: str, zh_text: str) -> bool:
    en_norm = normalize_text(en_text)
    zh_norm = normalize_text(zh_text)
    if en_norm == "":
        return False
    return zh_norm == "" or zh_norm == en_norm


def load_targets_from_report(report_path: str) -> Dict[str, set]:
    targets: Dict[str, set] = {}
    if not os.path.isfile(report_path):
        return targets

    with open(report_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            file_name = normalize_text(row.get("file"))
            key = normalize_text(row.get("key"))
            target_col = normalize_text(row.get("target_col"))
            if not file_name or not key:
                continue
            if target_col and target_col != "zh":
                continue

            if file_name not in targets:
                targets[file_name] = set()
            targets[file_name].add(key)

    return targets


def should_skip_row(row: Dict[str, str]) -> bool:
    key = normalize_text(row.get("KEY"))
    if key.startswith("//"):
        return True
    return all(normalize_text(v) == "" for v in row.values())


def build_key_index(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    index: Dict[str, Dict[str, str]] = {}
    for row in rows:
        key = normalize_text(row.get("KEY"))
        if key:
            index[key] = row
    return index


def get_desc_context(row_key: str, key_index: Dict[str, Dict[str, str]]) -> Tuple[str, str]:
    if not row_key.endswith("_NAME"):
        return "", ""

    base = row_key[: -len("_NAME")]
    desc_key = f"{base}_DESC"
    desc_row = key_index.get(desc_key)
    if not desc_row:
        return "", ""

    en_desc = desc_row.get("en") or ""
    zh_desc = desc_row.get("zh") or ""
    return en_desc, zh_desc


def call_openai_chat(api_key: str, model: str, system_prompt: str, user_prompt: str, timeout_sec: int = 90) -> str:
    payload = {
        "model": model,
        "temperature": 0.2,
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
        body = resp.read().decode("utf-8")
        data = json.loads(body)

    choices = data.get("choices") or []
    if not choices:
        return ""

    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    return content.strip()


def sanitize_model_output(text: str) -> str:
    s = text.strip()
    s = re.sub(r"^```[a-zA-Z]*\n", "", s)
    s = re.sub(r"\n```$", "", s)
    return s.strip()


def translate_zh_text(
    api_key: str,
    model: str,
    key: str,
    en_text: str,
    row_type: str,
    en_desc: str,
    zh_desc: str,
    retries: int,
    sleep_sec: float,
) -> str:
    system_prompt = (
        "你是游戏本地化翻译助手。"
        "目标语言是简体中文。"
        "你必须只输出翻译结果本体，不要输出解释、引号或多余内容。"
        "保留原文中的占位符和标签格式，例如 {var}、[img:...]、[b]...[/b]。"
        "保持换行结构与语义自然，避免机器直译。"
    )

    if row_type == "name":
        user_prompt = (
            "请翻译一个游戏名称字段。\n"
            "规则：\n"
            "1) 输出简体中文短名称。\n"
            "2) 若英文名称是非常规造词/词典里不常见词（例如 fartoom 这类），"
            "请结合描述语义重新命名，优先可读性与玩法含义。\n"
            "3) 不要保留英文原词作为中文结果（除非是必须保留的专有名词）。\n"
            f"KEY: {key}\n"
            f"EN_NAME: {en_text}\n"
            f"EN_DESC_CONTEXT: {en_desc}\n"
            f"ZH_DESC_CONTEXT: {zh_desc}\n"
            "只返回中文名称。"
        )
    else:
        user_prompt = (
            "请翻译一个游戏描述字段为简体中文。\n"
            "规则：\n"
            "1) 准确自然，符合游戏术语。\n"
            "2) 保留占位符和标签，不要删除或改写。\n"
            "3) 如原文有换行，可保留合理换行。\n"
            f"KEY: {key}\n"
            f"EN_DESC: {en_text}\n"
            "只返回中文描述。"
        )

    last_error = None
    for attempt in range(retries + 1):
        try:
            result = call_openai_chat(api_key, model, system_prompt, user_prompt)
            result = sanitize_model_output(result)
            if result:
                return result
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}"
            try:
                err_body = e.read().decode("utf-8", errors="ignore")
                if err_body:
                    last_error = f"{last_error}: {err_body[:300]}"
            except Exception:
                pass
        except Exception as e:
            last_error = str(e)

        if attempt < retries:
            time.sleep(sleep_sec)

    raise RuntimeError(last_error or "unknown api error")


def process_file(
    file_path: str,
    output_path: str,
    api_key: str,
    model: str,
    retries: int,
    sleep_sec: float,
    max_rows: int,
    report_targets: Optional[set],
) -> Tuple[int, int]:
    translated_rows = 0
    failed_rows = 0

    with open(file_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    if "en" not in fieldnames or "zh" not in fieldnames:
        with open(output_path, "w", encoding="utf-8", newline="") as out_f:
            writer = csv.DictWriter(out_f, fieldnames=fieldnames)
            if fieldnames:
                writer.writeheader()
            writer.writerows(rows)
        return 0, 0

    key_index = build_key_index(rows)

    with open(output_path, "w", encoding="utf-8", newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()

        for row in rows:
            if should_skip_row(row):
                writer.writerow(row)
                continue

            key = normalize_text(row.get("KEY"))
            en_text = row.get("en") or ""
            zh_text = row.get("zh") or ""

            if report_targets is not None and key not in report_targets:
                writer.writerow(row)
                continue

            need_translate = is_missing_translation(en_text, zh_text)
            if need_translate and (max_rows <= 0 or translated_rows < max_rows):
                row_type = "name" if key.endswith("_NAME") else "desc" if key.endswith("_DESC") else "generic"
                en_desc_ctx, zh_desc_ctx = get_desc_context(key, key_index)

                try:
                    translated = translate_zh_text(
                        api_key=api_key,
                        model=model,
                        key=key,
                        en_text=en_text,
                        row_type=row_type,
                        en_desc=en_desc_ctx,
                        zh_desc=zh_desc_ctx,
                        retries=retries,
                        sleep_sec=sleep_sec,
                    )
                    if translated:
                        row["zh"] = translated
                        translated_rows += 1
                except Exception:
                    failed_rows += 1

            writer.writerow(row)

    return translated_rows, failed_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="根据漏译报告使用 OpenAI 自动翻译 CSV 漏译项，并输出到新目录。"
    )
    parser.add_argument("input_dir", help="CSV 所在目录")
    parser.add_argument(
        "--output-dir",
        default="ai_translated_output",
        help="输出子目录（默认 ai_translated_output）",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI 模型名（默认 gpt-4o-mini）",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="OpenAI API Key（建议改用环境变量 OPENAI_API_KEY）",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="单条失败重试次数（默认 2）",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="每次请求间隔秒数（默认 0.2）",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=0,
        help="最多翻译多少行（0 表示不限制）",
    )
    parser.add_argument(
        "--report",
        default="missing_translation_report.csv",
        help="漏译报告路径（默认 input_dir/missing_translation_report.csv）",
    )
    args = parser.parse_args()

    api_key = (args.api_key or os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("缺少 API Key：请传 --api-key 或设置环境变量 OPENAI_API_KEY")

    input_dir = os.path.abspath(args.input_dir)
    if not os.path.isdir(input_dir):
        raise SystemExit(f"输入目录不存在: {input_dir}")

    output_dir = os.path.join(input_dir, args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    report_path = args.report
    if not os.path.isabs(report_path):
        report_path = os.path.join(input_dir, report_path)
    report_targets_by_file = load_targets_from_report(report_path)
    if not report_targets_by_file:
        raise SystemExit(f"漏译报告为空或不存在: {report_path}")

    csv_files = sorted(
        name
        for name in os.listdir(input_dir)
        if name.lower().endswith(".csv")
        and name not in SKIP_FILES
        and os.path.isfile(os.path.join(input_dir, name))
    )

    total_translated = 0
    total_failed = 0

    for name in csv_files:
        src = os.path.join(input_dir, name)
        dst = os.path.join(output_dir, name)
        report_targets = report_targets_by_file.get(name)

        translated, failed = process_file(
            file_path=src,
            output_path=dst,
            api_key=api_key,
            model=args.model,
            retries=max(0, args.retries),
            sleep_sec=max(0.0, args.sleep),
            max_rows=args.max_rows,
            report_targets=report_targets,
        )

        total_translated += translated
        total_failed += failed
        print(f"{name}: translated {translated}, failed {failed}")

    print("-" * 48)
    print(f"files processed: {len(csv_files)}")
    print(f"rows translated: {total_translated}")
    print(f"rows failed: {total_failed}")
    print(f"report used: {report_path}")
    print(f"output dir: {output_dir}")


if __name__ == "__main__":
    main()
