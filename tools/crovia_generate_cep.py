#!/usr/bin/env python3
"""
crovia_generate_cep.py - Generate a CEP.v1 (Crovia Evidence Protocol) block
from existing Crovia artifacts.

Inputs:
  - trust bundle JSON
  - royalty receipts NDJSON (royalty_receipt.v1)
  - payouts file (NDJSON or CSV)
  - hashchain proof file

Output:
  - CEP.v1 YAML block on stdout (for model cards, reports, etc.)
"""

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional, Tuple

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # fallback: we can emit JSON if needed


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_ndjson(path: str):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                yield json.loads(s)
            except Exception:
                continue


def detect_payout_period_and_schema(path: str) -> Tuple[str, str]:
    """
    Try to detect the period (YYYY-MM) and schema (payouts.v1 or other) from
    a payouts file that may be NDJSON or CSV.
    """
    # NDJSON first (single JSON object per line)
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        first_line = f.readline()
        if not first_line:
            return "", ""
        s = first_line.strip()
        try:
            obj = json.loads(s)
            schema = obj.get("schema", "")
            period = obj.get("period", "")
            return str(period), str(schema)
        except Exception:
            pass

    # Fallback: CSV (expects 'period' column if present)
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        try:
            row = next(reader)
        except StopIteration:
            return "", ""
        period = row.get("period", "")
        schema = "payouts.v1" if period else ""
        return str(period), schema


def analyze_receipts(path: str):
    """
    Analyze royalty_receipt.v1 NDJSON:
      - count records
      - compute avg top1 share
      - min/max epsilon_dp
      - CI presence
    """
    total = 0
    sum_top1 = 0.0
    eps_min: Optional[float] = None
    eps_max: Optional[float] = None
    ci_present = False

    for rec in iter_ndjson(path):
        if rec.get("schema") != "royalty_receipt.v1":
            continue
        total += 1
        top_k = rec.get("top_k") or []

        # top1 share
        best = None
        for a in top_k:
            share = a.get("share")
            if isinstance(share, (int, float)):
                best = share if best is None else max(best, share)

            # CI presence
            if ("share_ci95_low" in a) or ("share_ci95_high" in a):
                ci_present = True

        if best is not None:
            sum_top1 += float(best)

        # epsilon_dp range
        eps = rec.get("epsilon_dp")
        if isinstance(eps, (int, float)):
            v = float(eps)
            eps_min = v if eps_min is None else min(eps_min, v)
            eps_max = v if eps_max is None else max(eps_max, v)

    avg_top1 = (sum_top1 / total) if total > 0 else 0.0
    return {
        "count": total,
        "avg_top1_share": avg_top1,
        "epsilon_min": eps_min,
        "epsilon_max": eps_max,
        "ci_present": ci_present,
    }


def extract_hashchain_root(path: str) -> Tuple[str, bool]:
    """
    Given a hashchain file (output of hashchain_writer.py), take the last
    non-empty line and use the last column as the root digest.

    We don't verify here; verification should be done separately with
    verify_hashchain.py (exit code == 0).
    """
    last = None
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            s = line.strip()
            if s:
                last = s
    if not last:
        return "", False
    parts = last.split("\t")
    digest = parts[-1] if parts else ""
    ok = bool(digest and len(digest) >= 32)
    return digest, ok


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate a CEP.v1 block from Crovia artifacts"
    )
    ap.add_argument(
        "--trust-bundle",
        required=True,
        help="Trust bundle JSON (trust_bundle.v1)",
    )
    ap.add_argument(
        "--period",
        required=True,
        help="Accounting period YYYY-MM",
    )
    ap.add_argument(
        "--receipts",
        required=True,
        help="Royalty receipts NDJSON (royalty_receipt.v1)",
    )
    ap.add_argument(
        "--payouts",
        required=True,
        help="Payouts file (NDJSON or CSV)",
    )
    ap.add_argument(
        "--hashchain",
        required=True,
        help="Hashchain proof file",
    )
    ap.add_argument(
        "--engine-version",
        default="",
        help="Engine version or git short SHA",
    )
    ap.add_argument(
        "--output-format",
        choices=["yaml", "json"],
        default="yaml",
    )
    args = ap.parse_args()

    # Basic checks
    for p in [args.trust_bundle, args.receipts, args.payouts, args.hashchain]:
        if not os.path.exists(p):
            print(f"[FATAL] File not found: {p}", file=sys.stderr)
            sys.exit(2)

    # Hashes
    trust_sha = sha256_file(args.trust_bundle)
    rec_sha = sha256_file(args.receipts)
    pay_sha = sha256_file(args.payouts)

    # Receipts analysis
    rec_info = analyze_receipts(args.receipts)

    # Payout period/schema (best effort)
    pay_period, pay_schema = detect_payout_period_and_schema(args.payouts)
    if not pay_period:
        pay_period = args.period
    if not pay_schema:
        pay_schema = "payouts.v1"

    # Hashchain root (just extract, no verification here)
    root, ok_root = extract_hashchain_root(args.hashchain)

    # Timestamp UTC
    ts = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    cep = {
        "crovia_evidence": {
            "protocol": "CEP.v1",
            "trust_bundle": {
                "schema": "trust_bundle.v1",
                "sha256": trust_sha,
                "period": args.period,
            },
            "receipts": {
                "count": rec_info["count"],
                "sha256": rec_sha,
                "schema": "royalty_receipt.v1",
            },
            "payouts": {
                "sha256": pay_sha,
                "schema": pay_schema,
                "period": pay_period,
            },
            "hash_chain": {
                "root": root,
                "verified": ok_root,
                "source": os.path.basename(args.hashchain),
            },
            "trust_metrics": {
                "avg_top1_share": round(float(rec_info["avg_top1_share"]), 6),
                "dp_epsilon": {
                    "min": rec_info["epsilon_min"],
                    "max": rec_info["epsilon_max"],
                },
                "ci_present": bool(rec_info["ci_present"]),
            },
            "generated_by": {
                "engine": "Crovia Core Engine",
                "version": args.engine_version or "unknown",
                "timestamp": ts,
            },
        }
    }

    if args.output_format == "json" or yaml is None:
        print(json.dumps(cep, ensure_ascii=False, indent=2))
    else:
        # emit just the inner block as YAML for direct paste
        out_obj = cep["crovia_evidence"]
        print("crovia_evidence:")
        print(
            yaml.safe_dump(
                out_obj,
                sort_keys=False,
                default_flow_style=False,
            )
        )


if __name__ == "__main__":
    main()
