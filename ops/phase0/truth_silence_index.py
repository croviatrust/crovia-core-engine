#!/usr/bin/env python3
"""Recompute silence_index.json from the ledger under the observation-bounded rule.

    python3 truth_silence_index.py \
        --ledger /opt/crovia/substrate/axiom_ledger.jsonl \
        --out /var/www/registry/data/silence_index.json

Rule (CANON.md §4, TACET SPEC §8.4 in its pre-TACET form): a target's silence
is the span between its first and its LAST negative observation (AX.ABS with
decision NEGATIVE, or observation_type absence). Nothing accrues after the last
observation. Targets that are not AI models are excluded. Every figure carries
the date of the last observation that supports it.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path
from typing import Dict, Optional

from truth_lib import (days_between, envelope_target, envelope_time, is_model_target, iso, iter_jsonl, now,
                       observation_status, write_json_atomic)


def is_negative(env: dict) -> bool:
    if env.get("axiom_type") == "AX.ABS":
        return True
    return str(env.get("decision", "")).upper() == "NEGATIVE" and env.get("axiom_type") in ("AX.OBS", "AX.NEC")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--min-observations", type=int, default=2)
    a = ap.parse_args()

    scanned = negatives = 0
    first: Dict[str, object] = {}
    last: Dict[str, object] = {}
    count: Dict[str, int] = {}
    last_any: Dict[str, object] = {}
    for env in iter_jsonl(a.ledger):
        scanned += 1
        tid = envelope_target(env)
        if not is_model_target(tid):
            continue
        t = envelope_time(env)
        if t is None:
            continue
        if tid not in last_any or t > last_any[tid]:
            last_any[tid] = t
        if not is_negative(env):
            continue
        negatives += 1
        count[tid] = count.get(tid, 0) + 1
        if tid not in first or t < first[tid]:
            first[tid] = t
        if tid not in last or t > last[tid]:
            last[tid] = t

    rows = []
    for tid in first:
        if count[tid] < a.min_observations:
            continue
        days = days_between(first[tid], last[tid])
        rows.append({"target_id": tid, "first_seen": iso(first[tid]), "last_seen": iso(last[tid]),
                     "observations": count[tid], "silence_days": days,
                     "observation_status": observation_status(last[tid])})
    rows.sort(key=lambda r: (-r["silence_days"], r["target_id"]))
    days_list = [r["silence_days"] for r in rows]
    active = [r for r in rows if r["observation_status"]["state"] == "active"]
    latest_obs: Optional[object] = max(last.values()) if last else None

    out = {
        "schema": "crovia.silence_index.v2",
        "generated_at": iso(now()),
        "rule": "silence = last negative observation - first negative observation; no accrual after observation stops",
        "ledger_lines_scanned": scanned,
        "negative_envelopes": negatives,
        "n_real_targets": len(rows),
        "n_targets_actively_observed": len(active),
        "total_silence_days": sum(days_list),
        "mean_silence_days": int(statistics.fmean(days_list)) if days_list else 0,
        "median_silence_days": int(statistics.median(days_list)) if days_list else 0,
        "last_negative_observation_at": iso(latest_obs) if latest_obs else None,
        "observation_status": observation_status(latest_obs),
        "top_silent": rows[0] if rows else None,
        "top_silent_active": active[0] if active else None,
        "targets": rows[:500],
        # v1 field names kept for the embed widget and the lacuna page
        "top_100": rows[:100],
        "total_silence_years": round(sum(days_list) / 365.25, 2),
        "ax_abs_lines": negatives,
    }
    write_json_atomic(a.out, out)
    print(f"[truth_silence_index] targets={len(rows)} active={len(active)} total_days={out['total_silence_days']} "
          f"top={out['top_silent']['target_id'] if rows else None} ({out['top_silent']['silence_days'] if rows else 0}d, "
          f"last {out['top_silent']['last_seen'] if rows else None})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
