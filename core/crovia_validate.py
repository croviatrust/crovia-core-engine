from datetime import datetime, timezone
#!/usr/bin/env python3
"""
crovia_validate.py

Streaming validator per `royalty_receipt.v1` (NDJSON).

- Usa (se disponibile) schema.validate_record / is_schema_compatible
- Applica regole business semplici (top_k, somme share, ecc.)
- Produce:
  - un report Markdown con health score (A/B/C/D)
  - un NDJSON con un campione di record problematici

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
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


# Proviamo a importare il registry degli schemi se esiste
try:
    from schema import validate_record, is_schema_compatible  # type: ignore
except Exception:
    def validate_record(obj: Dict[str, Any]) -> None:
        """Fallback no-op se schema.py non è disponibile."""
        return None

    def is_schema_compatible(obj: Dict[str, Any], expected: str) -> bool:
        return obj.get("schema") == expected


ROYALTY_SCHEMA = "royalty_receipt.v1"
SHARE_SUM_TOL = 0.02  # tolleranza su sum(share) rispetto a 1.0
MAX_SAMPLE_DEFAULT = 200


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


def validate_business_rules(obj: Dict[str, Any]) -> List[LineIssue]:
    issues: List[LineIssue] = []

    schema = obj.get("schema")
    if schema != ROYALTY_SCHEMA and not is_schema_compatible(obj, ROYALTY_SCHEMA):
        issues.append(LineIssue(
            line=-1,
            level="ERROR",
            code="BAD_SCHEMA",
            message=f"schema={schema!r}, expected {ROYALTY_SCHEMA!r}",
        ))
        return issues

    output_id = obj.get("output_id")
    if not output_id:
        issues.append(LineIssue(
            line=-1,
            level="ERROR",
            code="MISSING_OUTPUT_ID",
            message="Missing or empty 'output_id'",
        ))

    top_k = obj.get("top_k")
    if not isinstance(top_k, list) or not top_k:
        issues.append(LineIssue(
            line=-1,
            level="ERROR",
            code="MISSING_TOPK",
            message="Missing or empty 'top_k'",
        ))
        return issues

    shares: List[float] = []
    last_rank = None
    sum_share = 0.0
    for a in top_k:
        if not isinstance(a, dict):
            issues.append(LineIssue(
                line=-1,
                level="ERROR",
                code="TOPK_NOT_OBJECT",
                message="top_k entry is not an object",
            ))
            continue
        pid = a.get("provider_id")
        sid = a.get("shard_id")

        sh = a.get("share")
        if not isinstance(sh, (int, float)):
            issues.append(LineIssue(
                line=-1,
                level="ERROR",
                code="MISSING_SHARE",
                message=f"Missing or non-numeric 'share' in top_k entry (provider_id={pid!r})",
                provider_id=str(pid) if pid is not None else None,
                shard_id=str(sid) if sid is not None else None,
            ))
            continue
        if sh < 0:
            issues.append(LineIssue(
                line=-1,
                level="ERROR",
                code="NEGATIVE_SHARE",
                message=f"Negative share={sh} in top_k entry (provider_id={pid!r})",
                provider_id=str(pid) if pid is not None else None,
                shard_id=str(sid) if sid is not None else None,
            ))
        shares.append(float(sh))
        sum_share += float(sh)

        # rank monotono crescente (se presente)
        r = a.get("rank")
        if r is not None:
            try:
                r_int = int(r)
                if last_rank is not None and r_int < last_rank:
                    issues.append(LineIssue(
                        line=-1,
                        level="ERROR",
                        code="RANK_NOT_MONOTONE",
                        message=f"rank={r_int} < previous={last_rank}",
                        provider_id=str(pid) if pid is not None else None,
                        shard_id=str(sid) if sid is not None else None,
                    ))
                last_rank = r_int
            except Exception:
                issues.append(LineIssue(
                    line=-1,
                    level="WARN",
                    code="RANK_NOT_INT",
                    message=f"rank non intero: {r!r}",
                    provider_id=str(pid) if pid is not None else None,
                    shard_id=str(sid) if sid is not None else None,
                ))

    if shares:
        if not math.isfinite(sum_share):
            issues.append(LineIssue(
                line=-1,
                level="ERROR",
                code="SHARE_NOT_FINITE",
                message="Sum of share is not finite",
            ))
        else:
            if abs(sum_share - 1.0) > SHARE_SUM_TOL:
                issues.append(LineIssue(
                    line=-1,
                    level="WARN",
                    code="SUM_SHARE_NOT_1",
                    message=f"Sum of share={sum_share:.6f} differs from 1.0 by > {SHARE_SUM_TOL}",
                ))

    return issues


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
        f.write(f"# Crovia NDJSON validation report\n\n")
        f.write(f"- Generated: **{now} UTC**\n")
        f.write(f"- Input file: `{os.path.basename(input_path)}`\n")
        f.write(f"- Total lines parsed: **{total}**\n")
        f.write(f"- Valid records: **{valid}**\n")
        f.write(f"- Lines with errors: **{errors}**\n")
        f.write(f"- Lines with warnings only: **{warns}**\n\n")

        f.write(f"**Health score:** `{health}`  \n")
        if health == "A":
            f.write("All records valid. 👍\n\n")
        elif health == "B":
            f.write("Minor issues detected, but overall strong quality. ✅\n\n")
        elif health == "C":
            f.write("Some issues detected; review recommended. ⚠️\n\n")
        else:
            f.write("Significant issues detected; data not suitable without fixes. ❌\n\n")

        if codes:
            f.write("## Issue codes summary\n\n")
            f.write("| Code | Count |\n")
            f.write("|------|-------|\n")
            for code, cnt in sorted(codes.items(), key=lambda x: (-x[1], x[0])):
                f.write(f"| `{code}` | {cnt} |\n")
            f.write("\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Validate royalty_receipt.v1 NDJSON and emit a Markdown report"
    )
    ap.add_argument(
        "input",
        help="Input NDJSON file (royalty_receipt.v1)",
    )
    ap.add_argument(
        "--out-md",
        default="validate_report.md",
        help="Output Markdown report path (default: validate_report.md)",
    )
    ap.add_argument(
        "--out-bad",
        default="validate_bad_sample.ndjson",
        help="Output NDJSON sample of problematic records",
    )
    ap.add_argument(
        "--max-bad",
        type=int,
        default=MAX_SAMPLE_DEFAULT,
        help=f"Max bad/warn records to sample into out-bad (default: {MAX_SAMPLE_DEFAULT})",
    )
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"[FATAL] Input file not found: {args.input}", file=sys.stderr)
        sys.exit(3)

    total = 0
    valid = 0
    error_lines = 0
    warn_lines = 0

    issue_codes = Counter()
    sample_bad: List[Dict[str, Any]] = []

    for lineno, rec in iter_ndjson(args.input):
        total += 1

        # parse error?
        if isinstance(rec, dict) and "_parse_error" in rec:
            error_lines += 1
            issue_codes["JSON_DECODE_ERROR"] += 1
            if len(sample_bad) < args.max_bad:
                sample_bad.append({
                    "_line": lineno,
                    "_level": "ERROR",
                    "_code": "JSON_DECODE_ERROR",
                    "_msg": rec.get("_parse_error"),
                    "_raw": rec.get("_raw"),
                })
            continue

        # schema-level validation (best-effort)
        try:
            validate_record(rec)
        except Exception as e:
            error_lines += 1
            issue_codes["SCHEMA_VALIDATE_ERROR"] += 1
            if len(sample_bad) < args.max_bad:
                sample_bad.append({
                    "_line": lineno,
                    "_level": "ERROR",
                    "_code": "SCHEMA_VALIDATE_ERROR",
                    "_msg": str(e),
                    "_rec": rec,
                })
            continue

        # business rules
        issues = validate_business_rules(rec)

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

    # scrivi report markdown
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

    # scrivi sample bad
    if sample_bad:
        with open(args.out_bad, "w", encoding="utf-8") as f:
            for rec in sample_bad:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"[VALIDATE] Health={health} | total={total} valid={valid} errors={error_lines} warns={warn_lines}")
    if health in ("A", "B"):
        sys.exit(0)
    elif health == "C":
        sys.exit(2)
    else:
        sys.exit(3)


if __name__ == "__main__":
    main()
