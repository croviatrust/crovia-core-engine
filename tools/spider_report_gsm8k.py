import json
import os
from pathlib import Path
from datetime import datetime, timezone
from statistics import mean

NDJSON_PATH = Path("data/spider_gsm8k_main.ndjson")
JSON_REPORT_PATH = Path("data/spider_gsm8k_main_report.json")
MD_REPORT_PATH = Path("docs/README_SPIDER_GSM8K_2025-12.md")


def load_and_analyze(path: Path, sample_size: int = 1000):
    total = 0
    license_counts = {}
    q_lengths = []
    examples = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            rec = json.loads(line)

            lic = rec.get("license_hint", "unknown")
            license_counts[lic] = license_counts.get(lic, 0) + 1

            meta = rec.get("metadata", {})
            orig = meta.get("original_fields", {})
            q = orig.get("question")
            if isinstance(q, str):
                q_lengths.append(len(q))

            if len(examples) < 3:
                examples.append(
                    {
                        "content_id": rec.get("content_id"),
                        "source_url": rec.get("source_url"),
                        "question": q,
                        "answer": orig.get("answer"),
                    }
                )

            if total >= sample_size and len(q_lengths) >= sample_size:
                # per ora, limitiamo la statistica a un sample
                pass

    stats = {}
    if q_lengths:
        q_lengths_sorted = sorted(q_lengths)
        stats["question_length_mean"] = round(mean(q_lengths), 2)
        stats["question_length_p50"] = q_lengths_sorted[len(q_lengths_sorted) // 2]
        stats["question_length_p90"] = q_lengths_sorted[int(0.9 * len(q_lengths_sorted))]
        stats["question_length_min"] = min(q_lengths_sorted)
        stats["question_length_max"] = max(q_lengths_sorted)
    else:
        stats["question_length_mean"] = None

    return {
        "total_receipts": total,
        "license_counts": license_counts,
        "question_stats": stats,
        "examples": examples,
    }


def write_json_report(analysis: dict, path: Path):
    report = {
        "dataset": "gsm8k (HF mirror: oieieio/gsm8k)",
        "period": "2025-12",
        "engine": "crovia-spider",
        "schema": "spider_receipt.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis": analysis,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def write_markdown_report(analysis: dict, path: Path):
    total = analysis["total_receipts"]
    license_counts = analysis["license_counts"]
    q_stats = analysis["question_stats"]
    examples = analysis["examples"]

    lines = []
    lines.append("# CROVIA Spider – GSM8K evidence run (period 2025-12)")
    lines.append("")
    lines.append("> This run documents how CROVIA Spider turns a **real training dataset**")
    lines.append("> (HF mirror of OpenAI GSM8K) into `spider_receipt.v1` evidence logs.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Run summary")
    lines.append("")
    lines.append(f"- **Dataset:** `oieieio/gsm8k` (HF dataset, Parquet shard)")
    lines.append("- **License hint:** `mit` (dataset license, treated as a hint)")
    lines.append("- **CROVIA schema:** `spider_receipt.v1`")
    lines.append("- **Engine:** `crovia-spider` (local run)")
    lines.append(f"- **Period:** `2025-12`")
    lines.append(f"- **Receipts generated:** `{total}`")
    lines.append("")

    lines.append("### License hint distribution")
    lines.append("")
    for lic, count in license_counts.items():
        pct = (count / total * 100) if total else 0.0
        lines.append(f"- `{lic}`: `{count}` (~{pct:.1f}%)")
    lines.append("")

    lines.append("### Question length statistics (characters)")
    lines.append("")
    lines.append(f"- mean: `{q_stats.get('question_length_mean')}`")
    lines.append(f"- p50: `{q_stats.get('question_length_p50')}`")
    lines.append(f"- p90: `{q_stats.get('question_length_p90')}`")
    lines.append(f"- min: `{q_stats.get('question_length_min')}`")
    lines.append(f"- max: `{q_stats.get('question_length_max')}`")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 2. How this evidence was generated")
    lines.append("")
    lines.append("### 2.1. Download the Parquet shard")
    lines.append("")
    lines.append("```bash")
    lines.append("cd /opt/crovia")
    lines.append("mkdir -p data/gsm8k_real && cd data/gsm8k_real")
    lines.append('wget -O gsm8k_main_train.parquet \\')
    lines.append('  "https://huggingface.co/datasets/oieieio/gsm8k/resolve/main/main/train-00000-of-00001.parquet"')
    lines.append("```")
    lines.append("")
    lines.append("### 2.2. Generate `spider_receipt.v1` NDJSON")
    lines.append("")
    lines.append("```bash")
    lines.append("cd /opt/crovia")
    lines.append("source .venv/bin/activate")
    lines.append("PYTHONPATH=src python << 'EOF'")
    lines.append("import pandas as pd, json, hashlib")
    lines.append("from datetime import datetime, timezone")
    lines.append("from pathlib import Path")
    lines.append("")
    lines.append('parquet_path = Path("data/gsm8k_real/gsm8k_main_train.parquet")')
    lines.append('out_path = Path("data/spider_gsm8k_main.ndjson")')
    lines.append('')
    lines.append('period = "2025-12"')
    lines.append('dataset_origin = "gsm8k-main"')
    lines.append("")
    lines.append("def now_iso():")
    lines.append("    return datetime.now(timezone.utc).isoformat()")
    lines.append("")
    lines.append("def make_content_id(source_url: str) -> str:")
    lines.append('    h = hashlib.sha256(source_url.encode("utf-8")).hexdigest()')
    lines.append('    return f"cid:url_sha256:{h}"')
    lines.append("")
    lines.append('print(f"[*] Loading Parquet: {parquet_path}")')
    lines.append("df = pd.read_parquet(parquet_path)")
    lines.append('print(f"[*] Rows in gsm8k train shard: {len(df)}")')
    lines.append("")
    lines.append('with out_path.open("w", encoding="utf-8") as f_out:')
    lines.append("    for idx, row in df.iterrows():")
    lines.append('        source_url = ("hf://oieieio/gsm8k/main/"')
    lines.append('                       "train-00000-of-00001.parquet"')
    lines.append('                       f"#row={idx}")')
    lines.append("")
    lines.append("        receipt = {")
    lines.append('            "schema": "spider_receipt.v1",')
    lines.append('            "version": "1.0.0",')
    lines.append('            "content_id": make_content_id(source_url),')
    lines.append('            "source_url": source_url,')
    lines.append('            "retrieved_at": now_iso(),')
    lines.append('            "dataset_origin": dataset_origin,')
    lines.append('            "period": period,')
    lines.append('            "license_hint": "mit",')
    lines.append('            "metadata": {')
    lines.append('                "data_source_type": "training_text",')
    lines.append('                "confidence": {')
    lines.append('                    "license": "medium",')
    lines.append('                    "url_status": "not_applicable",')
    lines.append('                    "content_availability": "known"')
    lines.append("                },")
    lines.append('                "original_source": "huggingface:gsm8k",')
    lines.append('                "original_fields": {')
    lines.append('                    "question": row["question"],')
    lines.append('                    "answer": row["answer"],')
    lines.append("                },")
    lines.append("            },")
    lines.append('            "links": [],')
    lines.append("        }")
    lines.append("")
    lines.append("        normalized = json.dumps(receipt, sort_keys=True, separators=(\",\", \":\"))")
    lines.append("        h = hashlib.sha256(normalized.encode(\"utf-8\")).hexdigest()")
    lines.append('        receipt["receipt_id"] = f"sr_sha256:{h}"')
    lines.append("")
    lines.append("        f_out.write(json.dumps(receipt, ensure_ascii=False) + \"\\n\")")
    lines.append("")
    lines.append('print(f"[*] Wrote {len(df)} receipts to {out_path}")')
    lines.append("EOF")
    lines.append("```")
    lines.append("")
    lines.append("### 2.3. Validate against `spider_receipt.v1`")
    lines.append("")
    lines.append("```bash")
    lines.append("cd /opt/crovia")
    lines.append("crovia-spider validate \\")
    lines.append("  --input data/spider_gsm8k_main.ndjson")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. Sample receipts")
    lines.append("")
    if examples:
        lines.append("Below are a few redacted examples of `spider_receipt.v1` entries derived from GSM8K:")
        lines.append("")
        for ex in examples:
            lines.append("```json")
            snippet = {
                "content_id": ex["content_id"],
                "source_url": ex["source_url"],
                "metadata": {
                    "original_fields": {
                        "question": ex["question"],
                        "answer": ex["answer"],
                    }
                },
            }
            lines.append(json.dumps(snippet, indent=2, ensure_ascii=False))
            lines.append("```")
            lines.append("")
    else:
        lines.append("_No examples captured in analysis._")
        lines.append("")

    content = "\n".join(lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(content)


def main():
    if not NDJSON_PATH.exists():
        raise SystemExit(f"NDJSON file not found: {NDJSON_PATH}")

    print(f"[*] Analyzing: {NDJSON_PATH}")
    analysis = load_and_analyze(NDJSON_PATH)

    print(f"[*] Total receipts: {analysis['total_receipts']}")
    print(f"[*] License counts: {analysis['license_counts']}")
    print(f"[*] Question stats: {analysis['question_stats']}")

    write_json_report(analysis, JSON_REPORT_PATH)
    write_markdown_report(analysis, MD_REPORT_PATH)

    print(f"[*] JSON report written to: {JSON_REPORT_PATH}")
    print(f"[*] Markdown report written to: {MD_REPORT_PATH}")


if __name__ == "__main__":
    main()
