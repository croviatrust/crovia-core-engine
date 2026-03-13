#!/usr/bin/env python3
"""
Canonical parity diff for public registry artifacts.

Compares legacy output dir vs shadow output dir using canonical JSON hashing,
with per-file volatile fields ignored.

Usage:
  python canonical_diff_public.py --left-dir /var/www/registry/data --right-dir /var/www/registry/data_next
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


FILES = [
    "tpa_latest.json",
    "global_ranking.json",
    "lineage_graph.json",
    "forensic_report.json",
    "gdna_results.json",
]

IGNORE_TOP_LEVEL: Dict[str, List[str]] = {
    "tpa_latest.json": ["generated_at", "sentinel"],
    "global_ranking.json": ["generated_at", "sentinel"],
    "lineage_graph.json": ["generated_at", "sentinel"],
    "forensic_report.json": ["generated_at", "sentinel"],
    "gdna_results.json": ["last_updated"],
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_hash(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _drop_volatile(data: Any, filename: str) -> Any:
    if not isinstance(data, dict):
        return data
    ignore = set(IGNORE_TOP_LEVEL.get(filename, []))
    return {k: v for k, v in data.items() if k not in ignore}


def _metrics(data: Any) -> Dict[str, Any]:
    m: Dict[str, Any] = {}
    if isinstance(data, dict):
        for k in ("total_tpas", "chain_height", "total_models", "total_orgs"):
            if k in data:
                m[k] = data[k]
        for k in ("tpas", "model_ranking", "org_ranking", "nodes", "edges", "runs"):
            if isinstance(data.get(k), list):
                m[f"{k}_len"] = len(data[k])
    return m


def _compare_file(left_path: Path, right_path: Path, filename: str) -> Dict[str, Any]:
    if not left_path.exists() or not right_path.exists():
        return {
            "ok": False,
            "error": "file_missing",
            "left_exists": left_path.exists(),
            "right_exists": right_path.exists(),
        }

    try:
        left_raw = _load_json(left_path)
        right_raw = _load_json(right_path)
    except Exception as e:
        return {"ok": False, "error": f"json_parse_error: {e}"}

    left = _drop_volatile(left_raw, filename)
    right = _drop_volatile(right_raw, filename)

    left_hash = _canonical_hash(left)
    right_hash = _canonical_hash(right)

    left_metrics = _metrics(left_raw)
    right_metrics = _metrics(right_raw)

    metric_diffs = {
        k: {"left": left_metrics.get(k), "right": right_metrics.get(k)}
        for k in sorted(set(left_metrics.keys()) | set(right_metrics.keys()))
        if left_metrics.get(k) != right_metrics.get(k)
    }

    return {
        "ok": left_hash == right_hash and not metric_diffs,
        "hash_equal": left_hash == right_hash,
        "left_hash": left_hash,
        "right_hash": right_hash,
        "metric_diffs": metric_diffs,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Canonical parity diff for public JSON artifacts")
    ap.add_argument("--left-dir", required=True)
    ap.add_argument("--right-dir", required=True)
    ap.add_argument("--report-out")
    args = ap.parse_args()

    left_dir = Path(args.left_dir)
    right_dir = Path(args.right_dir)

    report: Dict[str, Any] = {
        "ok": True,
        "left_dir": str(left_dir),
        "right_dir": str(right_dir),
        "artifacts": {},
    }

    for fn in FILES:
        result = _compare_file(left_dir / fn, right_dir / fn, fn)
        report["artifacts"][fn] = result
        if not result.get("ok", False):
            report["ok"] = False

    output = json.dumps(report, indent=2, ensure_ascii=False)
    print(output)

    if args.report_out:
        Path(args.report_out).write_text(output, encoding="utf-8")

    return 0 if report["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
