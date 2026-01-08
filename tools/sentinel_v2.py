#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple


SENTINEL_SCHEMA = "sentinel_snapshot.v2"
SENTINEL_VERSION = "2.0.0"


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_ndjson(path: str) -> List[Dict[str, Any]]:
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def entropy(counts: Dict[str, int]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    e = 0.0
    for v in counts.values():
        p = v / total
        if p > 0:
            e -= p * math.log(p, 2)
    return e


def analyze_receipts(receipts: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(receipts)
    licenses = defaultdict(int)
    confidence = defaultdict(int)

    for r in receipts:
        lic = (r.get("license_hint") or "unknown").lower()
        licenses[lic] += 1
        conf = ((r.get("metadata") or {}).get("confidence") or {}).get("license", "unknown")
        confidence[conf] += 1

    return {
        "total_receipts": total,
        "license_distribution": dict(licenses),
        "license_entropy": round(entropy(licenses), 4),
        "confidence_distribution": dict(confidence),
        "unknown_license_ratio": round(licenses.get("unknown", 0) / total, 4) if total else 0.0,
    }


def drift_score(prev: Dict[str, Any], curr: Dict[str, Any]) -> float:
    """
    Drift score semplice ma potente:
    - variazione entropia licenze
    - variazione percentuale 'unknown'
    """
    de = abs(curr["license_entropy"] - prev["license_entropy"])
    du = abs(curr["unknown_license_ratio"] - prev["unknown_license_ratio"])
    return round(de * 0.6 + du * 0.4, 4)


def cmd_snapshot(args):
    receipts = load_ndjson(args.input)
    stats = analyze_receipts(receipts)

    snapshot = {
        "schema": SENTINEL_SCHEMA,
        "version": SENTINEL_VERSION,
        "generated_at": utc_now(),
        "dataset": args.dataset,
        "period": args.period,
        "stats": stats,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    print(f"[SENTINEL] Snapshot written → {args.out}")
    return 0


def cmd_compare(args):
    with open(args.prev, "r", encoding="utf-8") as f:
        prev = json.load(f)
    with open(args.curr, "r", encoding="utf-8") as f:
        curr = json.load(f)

    score = drift_score(prev["stats"], curr["stats"])

    alert = {
        "schema": "sentinel_alert.v2",
        "generated_at": utc_now(),
        "dataset": curr["dataset"],
        "from_period": prev["period"],
        "to_period": curr["period"],
        "drift_score": score,
        "severity": (
            "low" if score < 0.05 else
            "medium" if score < 0.15 else
            "high"
        ),
        "details": {
            "prev": prev["stats"],
            "curr": curr["stats"],
        }
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(alert, f, indent=2)

    print(f"[SENTINEL] Drift alert written → {args.out}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Crovia Sentinel v2 — Transparency Drift Watcher")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot", help="Create sentinel snapshot from spider receipts")
    s.add_argument("--input", required=True)
    s.add_argument("--dataset", required=True)
    s.add_argument("--period", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_snapshot)

    c = sub.add_parser("compare", help="Compare two snapshots and emit drift alert")
    c.add_argument("--prev", required=True)
    c.add_argument("--curr", required=True)
    c.add_argument("--out", required=True)
    c.set_defaults(func=cmd_compare)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
