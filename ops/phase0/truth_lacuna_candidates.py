#!/usr/bin/env python3
"""Qualify lacuna_candidates.json: drop internal targets, flag stale candidates, expose the pause.

    python3 truth_lacuna_candidates.py --path /var/www/registry/data/substrate/lacuna_candidates.json

Adds top-level `observation_status` (state active|paused, paused_since) and
`n_fresh`; adds `stale: true` to every candidate whose last_seen is older than
the pause threshold. The /registry/lacuna/ page can then show the banner from
lacuna_banner.js instead of a frozen table.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from truth_lib import PAUSE_THRESHOLD_DAYS, is_model_target, iso, now, observation_status, parse_ts, read_json, write_json_atomic


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, type=Path)
    a = ap.parse_args()

    d = read_json(a.path)
    cands = [c for c in d.get("candidates", []) if is_model_target(c.get("target_id"))]
    dropped = len(d.get("candidates", [])) - len(cands)
    ref = now()
    latest = None
    fresh = 0
    for c in cands:
        ls = parse_ts(c.get("last_seen"))
        stale = ls is None or (ref - ls).total_seconds() / 86400 > PAUSE_THRESHOLD_DAYS
        c["stale"] = stale
        fresh += not stale
        if ls and (latest is None or ls > latest):
            latest = ls
    d["candidates"] = cands
    d["n"] = len(cands)
    d["n_fresh"] = fresh
    d["n_dropped_internal"] = dropped
    d["observation_status"] = observation_status(latest, ref)
    d["sources"] = sorted({c.get("source_collector") for c in cands if c.get("source_collector")})
    d["post_processed_at"] = iso(ref)
    write_json_atomic(a.path, d)
    print(f"[truth_lacuna] candidates={len(cands)} fresh={fresh} dropped_internal={dropped} "
          f"status={d['observation_status']['state']} paused_since={d['observation_status']['paused_since']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
