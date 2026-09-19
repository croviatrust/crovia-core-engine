#!/usr/bin/env python3
"""Rewrite _home_pulse.json so that every headline number follows the canon.

Runs AFTER the existing pulse generator, on the published file:

    python3 truth_pulse.py \
        --pulse /var/www/registry/data/_home_pulse.json \
        --ledger /opt/crovia/substrate/axiom_ledger.jsonl \
        --ots /var/www/registry/data/substrate/ots_anchors.json

Changes (CANON.md §4):
  * ledger.by_axiom_type["AX.LAC"] becomes the count of AX.LAC envelopes whose
    target is an AI model; the raw count (collector heartbeats included) is
    preserved as ledger.by_axiom_type_raw. The home page reads AX.LAC, so it
    starts showing the honest figure without an HTML change.
  * silence.top_silent.absence_streak_days becomes last_seen - first_seen
    (observation-bounded), and gains observed_to + observation_status.
  * anchors: adds distinct_roots and stalled/repeated flags so the page's
    "Bitcoin-confirmed anchors" can be qualified.
  * adds a top-level "canon" block naming the definition of each figure.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from truth_lib import (days_between, envelope_target, envelope_time, is_model_target, iso, iter_jsonl, now,
                       observation_status, parse_ts, read_json, write_json_atomic)


def count_lacuna_models(ledger: Path) -> dict:
    total = models = 0
    last_model_lac = None
    per_target: Counter = Counter()
    for env in iter_jsonl(ledger, must_contain='"AX.LAC"'):
        if env.get("axiom_type") != "AX.LAC":
            continue
        total += 1
        tid = envelope_target(env)
        if is_model_target(tid):
            models += 1
            per_target[tid] += 1
            t = envelope_time(env)
            if t and (last_model_lac is None or t > last_model_lac):
                last_model_lac = t
    return {"raw": total, "models": models, "distinct_model_targets": len(per_target),
            "last_model_lacuna_at": iso(last_model_lac) if last_model_lac else None}


def anchor_health(ots_path: Path | None) -> dict:
    if not ots_path or not ots_path.exists():
        return {}
    d = read_json(ots_path)

    def when(a: dict) -> str:  # hex-root anchors carry no anchor_date, only stamped_at
        return (a.get("anchor_date") or a.get("stamped_at") or "")[:10]

    anchors = sorted(d.get("anchors", []), key=when)
    confirmed = [a for a in anchors if a.get("status") == "bitcoin"]
    dated = [a for a in confirmed if when(a)]
    roots = [a.get("merkle_root") for a in confirmed]
    longest = run = 0
    for i, r in enumerate(roots):
        run = run + 1 if i and r == roots[i - 1] else 1
        longest = max(longest, run)
    newest = parse_ts(when(dated[-1])) if dated else None
    return {
        "confirmed_total": len(confirmed),
        "distinct_roots": len(set(roots)),
        "longest_repeated_root_run": longest,
        "newest_anchor_date": when(dated[-1]) if dated else None,
        "undated_confirmed": len(confirmed) - len(dated),
        "pending": sum(1 for a in anchors if a.get("status") == "pending"),
        "stalled_days": days_between(newest, now()) if newest else None,
        "valid": bool(confirmed) and longest < 3 and days_between(newest, now()) <= 3,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pulse", required=True, type=Path)
    ap.add_argument("--ledger", type=Path)
    ap.add_argument("--ots", type=Path)
    ap.add_argument("--cache", type=Path,
                    help="cache file for the ledger scan; reused while younger than --cache-max-age seconds")
    ap.add_argument("--cache-max-age", type=int, default=3600)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    pulse = read_json(a.pulse)
    ledger = pulse.setdefault("ledger", {})
    by_type = dict(ledger.get("by_axiom_type", {}))
    ledger.setdefault("by_axiom_type_raw", by_type)

    lac = None
    if a.ledger and a.ledger.exists():
        cached = None
        if a.cache and a.cache.exists() and (now().timestamp() - a.cache.stat().st_mtime) < a.cache_max_age:
            cached = read_json(a.cache)
        if cached is not None:
            lac = cached
        else:
            lac = count_lacuna_models(a.ledger)
            if a.cache and not a.dry_run:
                write_json_atomic(a.cache, lac)
    if lac is not None:
        ledger["by_axiom_type"] = {**by_type, "AX.LAC": lac["models"]}
        ledger["lacuna_records"] = lac
    else:
        ledger["by_axiom_type"] = {**by_type, "AX.LAC": 0}
        ledger["lacuna_records"] = {"raw": by_type.get("AX.LAC"), "models": None,
                                    "note": "ledger not available to this post-processor; raw count hidden"}

    sil = pulse.setdefault("silence", {})
    top = sil.get("top_silent") or {}
    if top:
        first, last = parse_ts(top.get("first_seen")), parse_ts(top.get("last_seen"))
        top["absence_streak_days_raw"] = top.get("absence_streak_days")
        top["absence_streak_days"] = days_between(first, last)
        top["observed_to"] = top.get("last_seen")
        top["observation_status"] = observation_status(last)
        sil["top_silent"] = top

    pulse["anchors"] = anchor_health(a.ots)
    pulse["canon"] = {
        "revision": "2026-09-19",
        "definitions": {
            "signed_observations": "envelopes in the AXIOM ledger",
            "lacuna_records": "AX.LAC envelopes whose target is an AI model (org/model); collector heartbeats excluded",
            "silence_days": "days between first and last negative observation; does not accrue after observation stops",
            "bitcoin_anchors": "OTS anchors confirmed in Bitcoin; repeated anchoring of an unchanged root is flagged",
        },
        "post_processed_at": iso(now()),
    }

    if a.dry_run:
        import json
        print(json.dumps({"ledger": ledger.get("by_axiom_type"), "lacuna_records": ledger.get("lacuna_records"),
                          "top_silent": sil.get("top_silent"), "anchors": pulse["anchors"]}, indent=1))
        return 0
    write_json_atomic(a.pulse, pulse)
    print(f"[truth_pulse] AX.LAC {by_type.get('AX.LAC')} -> {ledger['by_axiom_type']['AX.LAC']}; "
          f"top_silent {top.get('absence_streak_days_raw')} -> {top.get('absence_streak_days')} days; "
          f"anchors valid={pulse['anchors'].get('valid')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
