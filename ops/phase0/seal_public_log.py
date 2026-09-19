#!/usr/bin/env python3
"""Publish the Seal service's log as the public transparency log (CANON.md §5).

    python3 seal_public_log.py \
        --wall http://127.0.0.1:8090/v1/wall?limit=500 \
        --stats http://127.0.0.1:8090/v1/stats \
        --out-dir /var/www/registry/data/seal

Writes `public_log.jsonl` (conformant crovia.seal.v1 objects, oldest first, one per
line; the 10 conformance-chain Seals that were there before are kept at the top so
existing verifier tutorials still work) and `transparency_log.json` (issuers, counts,
chain head). Every Seal is re-verified with the reference implementation before it
is published; anything that fails is reported and dropped.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from truth_lib import iso, now, write_json_atomic

try:
    from crovia_seal import verify_seal
    from crovia_seal.seal import compute_seal_hash
except ImportError:  # the phase0 cron runs with the seal-svc venv on PATH; be explicit if not
    sys.path.insert(0, "/opt/crovia/repos/crovia-seal/reference/python")
    from crovia_seal import verify_seal
    from crovia_seal.seal import compute_seal_hash


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wall", default="http://127.0.0.1:8090/v1/wall?limit=500")
    ap.add_argument("--stats", default="http://127.0.0.1:8090/v1/stats")
    ap.add_argument("--out-dir", type=Path, default=Path("/var/www/registry/data/seal"))
    a = ap.parse_args()

    log_path = a.out_dir / "public_log.jsonl"
    conformance = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                s = json.loads(line)
            except json.JSONDecodeError:
                continue
            if s.get("issuer", {}).get("id") == "urn:crovia:seal-issuer:conformance":
                conformance.append(s)

    wall = fetch_json(a.wall)
    stats = fetch_json(a.stats)
    production = sorted(wall.get("seals", []), key=lambda s: s["chain"]["sequence"])
    good, bad = [], []
    for s in production:
        r = verify_seal(s)
        (good if r.ok else bad).append(s if r.ok else (s.get("seal_id"), r.errors))

    tmp = log_path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for s in conformance + good:
            f.write(json.dumps(s, ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.chmod(0o644)
    tmp.replace(log_path)

    issuers = {}
    for s in conformance + good:
        iid = s["issuer"]["id"]
        e = issuers.setdefault(iid, {"id": iid, "pubkey_hex": s["issuer"]["pubkey"]["key_hex"], "seals": 0,
                                     "first_emitted_at": None, "last_emitted_at": None})
        e["seals"] += 1
        t = s["timestamp"]["emitted_at"]
        e["first_emitted_at"] = min(e["first_emitted_at"] or t, t)
        e["last_emitted_at"] = max(e["last_emitted_at"] or t, t)

    write_json_atomic(a.out_dir / "transparency_log.json", {
        "log_version": "crovia-seal-tlog-v1",
        "seal_version": "crovia.seal.v1",
        "updated_at": iso(now()),
        "description": "Public append-only log of Crovia Seals: the conformance chain followed by every Seal issued by "
                       "seal.croviatrust.com, each re-verified with the reference implementation before publication.",
        "log_url": "/registry/data/seal/public_log.jsonl",
        "verify_url": "/registry/seal/verify/",
        "issuer_service": {"sign": "https://seal.croviatrust.com/v1/sign", "wall": "https://seal.croviatrust.com/v1/wall",
                           "trust_root": stats.get("trust_root")},
        "issuers": sorted(issuers.values(), key=lambda e: e["id"]),
        "production": {"seals": len(good), "chain_head": stats.get("chain"), "rejected_on_publish": len(bad),
                       "legacy_pre_0_6_objects_not_published": stats.get("legacy_seals")},
        "head_hash": compute_seal_hash(good[-1]) if good else None,
    })
    print(f"[seal_public_log] conformance={len(conformance)} production={len(good)} rejected={len(bad)}"
          + (f" {bad[:3]}" if bad else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
