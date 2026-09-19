#!/usr/bin/env python3
"""Qualify lacuna_candidates.json: drop internal targets, flag stale candidates, expose the pause,
and merge the live LACUNA candidates from the TACET log.

    python3 truth_lacuna_candidates.py --path /var/www/registry/data/substrate/lacuna_candidates.json \
        [--tacet /var/www/registry/data/tacet/targets.json]

Adds top-level `observation_status` (state active|paused, paused_since) and
`n_fresh`; adds `stale: true` to every candidate whose last_seen is older than
the pause threshold. Since 2026-09-19 the live candidates come from TACET
(CANON §TACET): every target whose last verdict is negative is listed with
`source_collector: "tacet"`, its anchored negative hours, and `stale: false`;
the archive rows (2026-01..06) stay, flagged stale. One target appears once:
the TACET row wins.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from truth_lib import PAUSE_THRESHOLD_DAYS, is_model_target, iso, now, observation_status, parse_ts, read_json, write_json_atomic


def tacet_candidates(path: Path) -> list:
    """Live candidates from TACET targets.json (negative last verdict). Silence = anchored negative hours / 24."""
    if not path.exists():
        return []
    try:
        t = read_json(path)
    except Exception:
        return []
    out = []
    for r in t.get("targets", []):
        if r.get("last_result") is not False or not r.get("negative") or not is_model_target(r.get("target_id")):
            continue
        anchored = int(r.get("negative_anchored_epochs") or 0)
        out.append({
            "target_id": r["target_id"],
            "source_collector": "tacet",
            "first_seen": r.get("first_seen"),
            "last_seen": r.get("last_seen"),
            "observation_count": int(r.get("observations") or 0),
            "negative_observations": int(r.get("negative") or 0),
            "negative_anchored_epochs": anchored,
            "absence_streak_days": round(anchored / 24.0, 2),
            "observed_to": r.get("last_seen"),
            "surface": r.get("last_surface"),
            "stale": False,
        })
    out.sort(key=lambda c: (-c["negative_anchored_epochs"], -c["negative_observations"], c["target_id"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, type=Path)
    ap.add_argument("--tacet", type=Path, default=Path("/var/www/registry/data/tacet/targets.json"))
    a = ap.parse_args()

    d = read_json(a.path)
    legacy = [c for c in d.get("candidates", []) if is_model_target(c.get("target_id")) and c.get("source_collector") != "tacet"]
    dropped = len(d.get("candidates", [])) - len(legacy)
    tacet_rows = tacet_candidates(a.tacet)
    tacet_ids = {c["target_id"] for c in tacet_rows}
    cands = tacet_rows + [c for c in legacy if c["target_id"] not in tacet_ids]
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
    d["n_tacet"] = len(tacet_rows)
    d["definition"] = ("A LACUNA candidate is a TACET target whose latest predicate result is negative; "
                       "absence_streak_days counts anchored negative epochs only (SPEC 8.4). Archive rows are stale.")
    d["post_processed_at"] = iso(ref)
    write_json_atomic(a.path, d)
    print(f"[truth_lacuna] candidates={len(cands)} fresh={fresh} dropped_internal={dropped} "
          f"status={d['observation_status']['state']} paused_since={d['observation_status']['paused_since']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
