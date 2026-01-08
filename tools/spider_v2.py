#!/usr/bin/env python3
"""
Crovia Spider v2 — Metadata-only Observation Engine
--------------------------------------------------

Purpose:
- Observe what AI training datasets DECLARE (metadata-only)
- Produce deterministic NDJSON receipts
- No URL fetch
- No inference
- No license validation
- Scales to very large Parquet files (pyarrow batches)

This is an OBSERVATION tool, not an audit tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Iterator, List, Optional

# Optional deps (preferred: pyarrow)
try:
    import pyarrow.parquet as pq
    import pyarrow as pa
except Exception:
    pq = None
    pa = None

try:
    import pandas as pd
except Exception:
    pd = None


SPIDER_SCHEMA = "spider_receipt.v2"
SPIDER_VERSION = "2.0.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    u = url.strip().split("#", 1)[0]
    return u[:-1] if u.endswith("/") else u


def content_id_from_url(url: str) -> str:
    if not url:
        return "cid:url_sha256:0"
    return f"cid:url_sha256:{sha256_hex(url.encode('utf-8'))}"


def json_fingerprint(obj: Dict[str, Any]) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_hex(raw.encode("utf-8"))


def detect_key(d: Dict[str, Any], candidates: List[str]) -> Optional[str]:
    lower = {k.lower(): k for k in d.keys()}
    for c in candidates:
        if c in d:
            return c
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def row_to_dict(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        return row
    if pd is not None and isinstance(row, getattr(pd, "Series", ())):
        return row.to_dict()
    try:
        return dict(row)
    except Exception:
        return {"_raw": str(row)}


def build_receipt(
    *,
    run_id: str,
    dataset_origin: str,
    period: str,
    row: Dict[str, Any],
    target_origin: str = "",
) -> Optional[Dict[str, Any]]:
    url_key = detect_key(row, ["url", "source_url", "URL"])
    if not url_key:
        return None

    url = canonicalize_url(str(row.get(url_key) or ""))
    if not url:
        return None

    lic_key = detect_key(row, ["license", "licence", "LICENSE", "LICENCE"])
    license_hint = str(row.get(lic_key, "unknown")).strip() if lic_key else "unknown"
    if not license_hint:
        license_hint = "unknown"

    receipt: Dict[str, Any] = {
        "schema": SPIDER_SCHEMA,
        "version": SPIDER_VERSION,
        "observed_at": utc_now(),
        "observer": {
            "engine": "crovia-spider",
            "engine_version": SPIDER_VERSION,
            "run_id": run_id,
        },
        "target": {
            "type": "dataset",
            "name": dataset_origin,
            "origin": target_origin,
        },
        "evidence": {
            "category": "training_data_declaration",
            "marker": "metadata_only",
            "expected": True,
        },
        "observation": {
            "status": "present",
            "confidence": "weak",
        },
        "content_id": content_id_from_url(url),
        "source_url": url,
        "license_hint": license_hint,
        "metadata": {
            "data_source_type": "metadata_only",
            "original_source": "dataset_metadata",
        },
        "period": period,
        "links": [],
    }

    receipt["receipt_id"] = f"sr_sha256:{json_fingerprint(receipt)}"
    return receipt


def iter_parquet_pyarrow(path: str, batch_size: int) -> Iterator[Dict[str, Any]]:
    if pq is None:
        raise RuntimeError("pyarrow not installed")
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=batch_size):
        table = pa.Table.from_batches([batch])
        for row in table.to_pylist():
            yield row


def iter_parquet_pandas(path: str) -> Iterator[Dict[str, Any]]:
    if pd is None:
        raise RuntimeError("pandas not installed")
    df = pd.read_parquet(path)
    for _, row in df.iterrows():
        yield row.to_dict()


def write_ndjson(path: str, items: Iterable[Dict[str, Any]]) -> int:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for obj in items:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            n += 1
    return n


def cmd_from_laion(args) -> int:
    meta = args.metadata_path
    out = args.out
    period = args.period
    dataset_origin = args.dataset_origin
    run_id = args.run_id or f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    if not os.path.exists(meta):
        print(f"[ERROR] file not found: {meta}", file=sys.stderr)
        return 2

    def gen():
        iterator = (
            iter_parquet_pandas(meta)
            if args.mode == "pandas"
            else iter_parquet_pyarrow(meta, args.batch_size)
        )

        scanned = 0
        written = 0
        for row in iterator:
            scanned += 1
            rec = build_receipt(
                run_id=run_id,
                dataset_origin=dataset_origin,
                period=period,
                row=row_to_dict(row),
                target_origin=args.target_origin,
            )
            if rec:
                written += 1
                yield rec
            if written and written % 50000 == 0:
                print(f"[SPIDERv2] wrote={written:,} scanned={scanned:,}")

        print(f"[SPIDERv2] DONE scanned={scanned:,} wrote={written:,}")

    n = write_ndjson(out, gen())
    print(f"[SPIDERv2] wrote {n} receipts -> {out}")
    return 0


def cmd_validate(args) -> int:
    ok = 0
    failed = 0
    with open(args.input, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                if obj.get("schema") != SPIDER_SCHEMA:
                    raise ValueError("schema mismatch")
                if not str(obj.get("receipt_id", "")).startswith("sr_sha256:"):
                    raise ValueError("bad receipt_id prefix")
                if not str(obj.get("content_id", "")).startswith("cid:url_sha256:"):
                    raise ValueError("bad content_id prefix")
                ok += 1
            except Exception:
                failed += 1
    print(f"[VALIDATE] ok={ok} failed={failed}")
    return 0 if failed == 0 else 1


def cmd_report(args) -> int:
    total = 0
    licenses: Dict[str, int] = {}

    with open(args.input, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            obj = json.loads(line)
            lic = (obj.get("license_hint") or "unknown").strip().lower()
            licenses[lic] = licenses.get(lic, 0) + 1

    print(f"[REPORT] total_receipts={total:,}")
    for k, v in sorted(licenses.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"  {k}: {v:,}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser("spider_v2", description="Crovia Spider v2 (metadata-only)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("from-laion", help="Generate spider_receipt.v2 NDJSON from LAION-style Parquet metadata")
    a.add_argument("--metadata-path", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--period", required=True)
    a.add_argument("--dataset-origin", required=True)
    a.add_argument("--target-origin", default="")
    a.add_argument("--run-id", default=None)
    a.add_argument("--batch-size", type=int, default=200000)
    a.add_argument("--mode", choices=["pyarrow", "pandas"], default="pyarrow")
    a.set_defaults(func=cmd_from_laion)

    v = sub.add_parser("validate", help="Validate spider_receipt.v2 NDJSON file")
    v.add_argument("--input", required=True)
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("report", help="Quick report (top license_hint)")
    r.add_argument("--input", required=True)
    r.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
