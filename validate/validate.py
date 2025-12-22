# NOTE: This validator is part of Crovia Open Core.
# It validates structure and integrity, not attribution correctness.

#!/usr/bin/env python3
"""
crovia_validate.py

Streaming validator per NDJSON Crovia.

Supporta due schemi principali:

- royalty_receipt.v1  → attribution / payout (top_k, model_id, ecc.)
- data_receipt.v1     → dataset origin receipts (LAION, C4, ecc.)

Cosa fa:
- usa (se disponibile) schema.validate_record / schema.is_schema_compatible
- applica regole business per i royalty receipts (top_k, share, ecc.)
- per i data receipts applica controlli basilari (provider_id, content_id, timestamp)
- produce:
  - report Markdown con health score (A/B/C/D)
  - NDJSON con un campione di record problematici

Exit code:
  0 = OK (A/B)
  2 = parzialmente ok (C)
  3 = fail (D)
"""

import argparse
import json
import math
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


# ----------------------------- Schema registry (best-effort) -----------------------------

try:
    from schema import validate_record as _validate_record  # type: ignore
    from schema import is_schema_compatible as _is_schema_compatible_raw  # type: ignore
except Exception:
    _validate_record = None
    _is_schema_compatible_raw = None


def validate_record(rec: Dict[str, Any]) -> None:
    """
    Best-effort schema validation:
    - if schema.py exists and exposes validate_record, use it
    - otherwise, no-op
    """
    if _validate_record is None:
        return
    _validate_record(rec)


def is_schema_compatible(rec: Dict[str, Any], expected: Optional[str] = None) -> bool:
    """
    Adapter robusto:
    - se schema.is_schema_compatible(rec) esiste (1 arg), lo usiamo
    - se esiste una variante a 2 arg (rec, expected), la usiamo
    - expected, se dato, richiede match esatto sul campo "schema"
    """
    s = rec.get("schema")
    if not isinstance(s, str):
        return False

    if _is_schema_compatible_raw is None:
        return (expected is None) or (s == expected)

    # prova firma a 2 argomenti
    try:
        ok = bool(_is_schema_compatible_raw(rec, expected))  # type: ignore
        return ok
    except TypeError:
        # fallback firma a 1 argomento
        ok = bool(_is_schema_compatible_raw(rec))  # type: ignore
        if expected is None:
            return ok
        return ok and (s == expected)


# ----------------------------- Constants -----------------------------

ROYALTY_SCHEMA = "royalty_receipt.v1"
DATA_SCHEMA = "data_receipt.v1"

SHARE_SUM_TOL = 0.02
MAX_SAMPLE_DEFAULT = 200


# ----------------------------- Types -----------------------------

@dataclass
class LineIssue:
    line: int
    level: str   # "ERROR" / "WARN"
    code: str
    message: str
    provider_id: Optional[str] = None
    shard_id: Optional[str] = None

    def to_dict(self, rec: Any) -> Dict[str, Any]:
        d = {
            "_line": self.line,
            "_level": self.level,
            "_code": self.code,
            "_msg": self.message,
        }
        if self.provider_id is not None:
            d["_provider_id"] = self.provider_id
        if self.shard_id is not None:
            d["_shard_id"] = self.shard_id
        d["_rec"] = rec
        return d


def iter_ndjson(path: str) -> Iterable[tuple[int, Any]]:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception as e:
                yield lineno, {"_parse_error": str(e), "_raw": s}
                continue
            yield lineno, obj


# ----------------------------- Business rules -----------------------------

def validate_royalty_business_rules(obj: Dict[str, Any]) -> List[LineIssue]:
    issues: List[LineIssue] = []

    schema = obj.get("schema")
    if schema != ROYALTY_SCHEMA and not is_schema_compatible(obj, ROYALTY_SCHEMA):
        issues.append(LineIssue(
            line=-1, level="ERROR", code="BAD_SCHEMA",
            message=f"schema={schema!r}, expected {ROYALTY_SCHEMA!r}",
        ))
        return issues

    if not obj.get("output_id"):
        issues.append(LineIssue(
            line=-1, level="ERROR", code="MISSING_OUTPUT_ID",
            message="Missing or empty 'output_id'",
        ))

    top_k = obj.get("top_k")
    if not isinstance(top_k, list) or not top_k:
        issues.append(LineIssue(
            line=-1, level="ERROR", code="MISSING_TOPK",
            message="Missing or empty 'top_k'",
        ))
        return issues

    last_rank = None
    sum_share = 0.0
    shares: List[float] = []

    for a in top_k:
        if not isinstance(a, dict):
            issues.append(LineIssue(
                line=-1, level="ERROR", code="TOPK_NOT_OBJECT",
                message="top_k entry is not an object",
            ))
            continue

        pid = a.get("provider_id")
        sid = a.get("shard_id")

        sh = a.get("share")
        if not isinstance(sh, (int, float)):
            issues.append(LineIssue(
                line=-1, level="ERROR", code="MISSING_SHARE",
                message=f"Missing or non-numeric 'share' in top_k entry (provider_id={pid!r})",
                provider_id=str(pid) if pid is not None else None,
                shard_id=str(sid) if sid is not None else None,
            ))
            continue

        if sh < 0:
            issues.append(LineIssue(
                line=-1, level="ERROR", code="NEGATIVE_SHARE",
                message=f"Negative share={sh} in top_k entry (provider_id={pid!r})",
                provider_id=str(pid) if pid is not None else None,
                shard_id=str(sid) if sid is not None else None,
            ))

        sh_f = float(sh)
        shares.append(sh_f)
        sum_share += sh_f

        r = a.get("rank")
        if r is not None:
            try:
                r_int = int(r)
                if last_rank is not None and r_int < last_rank:
                    issues.append(LineIssue(
                        line=-1, level="ERROR", code="RANK_NOT_MONOTONE",
                        message=f"rank={r_int} < previous={last_rank}",
                        provider_id=str(pid) if pid is not None else None,
                        shard_id=str(sid) if sid is not None else None,
                    ))
                last_rank = r_int
            except Exception:
                issues.append(LineIssue(
                    line=-1, level="WARN", code="RANK_NOT_INT",
                    message=f"rank not int: {r!r}",
                    provider_id=str(pid) if pid is not None else None,
                    shard_id=str(sid) if sid is not None else None,
                ))

    if shares:
        if not math.isfinite(sum_share):
            issues.append(LineIssue(
                line=-1, level="ERROR", code="SHARE_NOT_FINITE",
                message="Sum of share is not finite",
            ))
        elif abs(sum_share - 1.0) > SHARE_SUM_TOL:
            issues.append(LineIssue(
                line=-1, level="WARN", code="SUM_SHARE_NOT_1",
                message=f"Sum of share={sum_share:.6f} differs from 1.0 by > {SHARE_SUM_TOL}",
            ))

    return issues


def validate_data_receipt_business_rules(obj: Dict[str, Any]) -> List[LineIssue]:
    issues: List[LineIssue] = []

    schema = obj.get("schema")
    if schema != DATA_SCHEMA and not is_schema_compatible(obj, DATA_SCHEMA):
        issues.append(LineIssue(
            line=-1, level="ERROR", code="BAD_SCHEMA_DATA",
            message=f"schema={schema!r}, expected {DATA_SCHEMA!r}",
        ))
        return issues

    provider_id = obj.get("provider_id")
    if not isinstance(provider_id, str) or not provider_id.strip():
        issues.append(LineIssue(
            line=-1, level="ERROR", code="MISSING_PROVIDER_ID",
            message="Missing or empty 'provider_id' in data_receipt.v1",
        ))

    content_id = obj.get("content_id")
    if not isinstance(content_id, str) or not content_id.strip():
        issues.append(LineIssue(
            line=-1, level="ERROR", code="MISSING_CONTENT_ID",
            message="Missing or empty 'content_id' in data_receipt.v1",
        ))

    timestamp = obj.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp.strip():
        issues.append(LineIssue(
            line=-1, level="ERROR", code="MISSING_TIMESTAMP",
            message="Missing or empty 'timestamp' in data_receipt.v1",
        ))

    return issues


# ----------------------------- Health & report -----------------------------

def classify_health(total: int, errors: int, warns: int) -> str:
    if total == 0:
        return "D"
    err_rate = errors / total
    if errors == 0 and warns == 0:
        return "A"
    if err_rate <= 0.01:
        return "B"
    if err_rate <= 0.05:
        return "C"
    return "D"


def write_markdown_report(
    path: str,
    *,
    input_path: str,
    total: int,
    valid: int,
    errors: int,
    warns: int,
    health: str,
    codes: Counter,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Crovia NDJSON validation report\n\n")
        f.write(f"- Generated: **{now} UTC**\n")
        f.write(f"- Input file: `{os.path.basename(input_path)}`\n")
        f.write(f"- Total lines parsed: **{total}**\n")
        f.write(f"- Valid records: **{valid}**\n")
        f.write(f"- Lines with errors: **{errors}**\n")
        f.write(f"- Lines with warnings only: **{warns}**\n\n")
        f.write(f"**Health score:** `{health}`\n\n")

        if codes:
            f.write("## Issue codes summary\n\n")
            f.write("| Code | Count |\n|------|-------|\n")
            for code, cnt in sorted(codes.items(), key=lambda x: (-x[1], x[0])):
                f.write(f"| `{code}` | {cnt} |\n")
            f.write("\n")


# ----------------------------- Main -----------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Validate Crovia NDJSON and emit a Markdown report")
    ap.add_argument("input", help="Input NDJSON file")
    ap.add_argument("--out-md", default="validate_report.md", help="Output Markdown report path")
    ap.add_argument("--out-bad", default="validate_bad_sample.ndjson", help="Output NDJSON sample of problematic records")
    ap.add_argument("--max-bad", type=int, default=MAX_SAMPLE_DEFAULT, help="Max bad/warn records to sample")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"[FATAL] Input file not found: {args.input}", file=sys.stderr)
        sys.exit(3)

    total = valid = 0
    error_lines = warn_lines = 0
    issue_codes: Counter = Counter()
    sample_bad: List[Dict[str, Any]] = []

    for lineno, rec in iter_ndjson(args.input):
        total += 1

        if isinstance(rec, dict) and "_parse_error" in rec:
            error_lines += 1
            issue_codes["JSON_DECODE_ERROR"] += 1
            if len(sample_bad) < args.max_bad:
                sample_bad.append({
                    "_line": lineno, "_level": "ERROR", "_code": "JSON_DECODE_ERROR",
                    "_msg": rec.get("_parse_error"), "_raw": rec.get("_raw"),
                })
            continue

        if not isinstance(rec, dict):
            error_lines += 1
            issue_codes["RECORD_NOT_OBJECT"] += 1
            if len(sample_bad) < args.max_bad:
                sample_bad.append({
                    "_line": lineno, "_level": "ERROR", "_code": "RECORD_NOT_OBJECT",
                    "_msg": f"Record is not a JSON object: {type(rec)}",
                    "_rec": rec,
                })
            continue

        schema_name = rec.get("schema")

        # schema-level validation (best-effort)
        try:
            validate_record(rec)
        except Exception as e:
            # per data_receipt, in open-core possiamo tollerare come WARN
            if schema_name == DATA_SCHEMA:
                warn_lines += 1
                issue_codes["SCHEMA_VALIDATE_DATA_WARN"] += 1
                if len(sample_bad) < args.max_bad:
                    sample_bad.append({
                        "_line": lineno, "_level": "WARN", "_code": "SCHEMA_VALIDATE_DATA_WARN",
                        "_msg": str(e), "_rec": rec,
                    })
            else:
                error_lines += 1
                issue_codes["SCHEMA_VALIDATE_ERROR"] += 1
                if len(sample_bad) < args.max_bad:
                    sample_bad.append({
                        "_line": lineno, "_level": "ERROR", "_code": "SCHEMA_VALIDATE_ERROR",
                        "_msg": str(e), "_rec": rec,
                    })
                continue

        # branch schema
        if schema_name == DATA_SCHEMA:
            issues = validate_data_receipt_business_rules(rec)
        elif schema_name == ROYALTY_SCHEMA or is_schema_compatible(rec, ROYALTY_SCHEMA):
            issues = validate_royalty_business_rules(rec)
        else:
            error_lines += 1
            issue_codes["UNKNOWN_SCHEMA"] += 1
            if len(sample_bad) < args.max_bad:
                sample_bad.append({
                    "_line": lineno, "_level": "ERROR", "_code": "UNKNOWN_SCHEMA",
                    "_msg": f"Unknown or missing schema: {schema_name!r}",
                    "_rec": rec,
                })
            continue

        has_error = False
        has_warn = False
        for it in issues:
            if it.level == "ERROR":
                has_error = True
            elif it.level == "WARN":
                has_warn = True
            issue_codes[it.code] += 1
            if len(sample_bad) < args.max_bad:
                sample_bad.append(it.to_dict(rec))

        if has_error:
            error_lines += 1
        elif has_warn:
            warn_lines += 1
        else:
            valid += 1

    health = classify_health(total, error_lines, warn_lines)

    write_markdown_report(
        args.out_md,
        input_path=args.input,
        total=total,
        valid=valid,
        errors=error_lines,
        warns=warn_lines,
        health=health,
        codes=issue_codes,
    )

    if sample_bad:
        with open(args.out_bad, "w", encoding="utf-8") as f:
            for r in sample_bad:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[VALIDATE] Health={health} | total={total} valid={valid} errors={error_lines} warns={warn_lines}")
    sys.exit(0 if health in ("A", "B") else (2 if health == "C" else 3))


if __name__ == "__main__":
    main()
