#!/usr/bin/env python3
import argparse, json, os, hashlib
from datetime import datetime, timezone

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def load(path):
    with open(path) as f:
        return json.load(f)

def numeric_keys(d):
    return {k: v for k, v in d.items() if isinstance(v, (int, float))}

def drift_metrics(a, b):
    IGNORE = {"records_seen"}
    drift = {}
    for k in a:
        if k in b and k not in IGNORE:
            drift[k] = round(b[k] - a[k], 6)
    return drift

def trust_from_snapshot(snap):
    """
    Trust spiegabile (0..1) basato su snapshot governance.
    """
    score = 0.0

    if "receipts_fraction" in snap:
        score += snap["receipts_fraction"] * 0.5
    if "missing_fields_fraction" in snap:
        score += (1 - snap["missing_fields_fraction"]) * 0.3
    if "legal_ambiguity_level" in snap:
        score += (1 - snap["legal_ambiguity_level"]) * 0.2

    return round(min(1.0, max(0.0, score)), 6)

def main():
    ap = argparse.ArgumentParser(description="CROVIA snapshot → trust_drift.v1")
    ap.add_argument("--a", required=True, help="snapshot A")
    ap.add_argument("--b", required=True, help="snapshot B")
    ap.add_argument("--from-period", required=True)
    ap.add_argument("--to-period", required=True)
    ap.add_argument("--dataset-id", required=True)
    ap.add_argument("--model-id", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sign", action="store_true")
    args = ap.parse_args()

    A = numeric_keys(load(args.a))
    B = numeric_keys(load(args.b))

    drift = drift_metrics(A, B)
    trust_before = trust_from_snapshot(A)
    trust_after  = trust_from_snapshot(B)
    delta = round(trust_after - trust_before, 6)

    rec = {
        "schema": "trust_drift.v1",
        "dataset_id": args.dataset_id,
        "model_id": args.model_id,
        "from": args.from_period,
        "to": args.to_period,
        "trust_before": trust_before,
        "trust_after": trust_after,
        "delta": delta,
        "signals": drift,
        "inputs": [
            f"{os.path.basename(args.a)}:{sha256_file(args.a)}",
            f"{os.path.basename(args.b)}:{sha256_file(args.b)}",
        ],
        "engine": {
            "method": "snapshot_metrics_v1",
            "dsse": "future (semantic compression)",
        },
        "meta": {
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
    }

    if args.sign:
        key = os.environ.get("CROVIA_HMAC_KEY")
        if not key:
            raise SystemExit("CROVIA_HMAC_KEY not set")
        payload = json.dumps(rec, separators=(",", ":"), sort_keys=True).encode()
        import hmac
        rec["signature"] = hmac.new(key.encode(), payload, hashlib.sha256).hexdigest()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "a") as f:
        f.write(json.dumps(rec) + "\n")

    print(f"[SNAP-DRIFT] {args.dataset_id} {args.from_period}->{args.to_period} Δ={delta:+.6f}")

if __name__ == "__main__":
    main()
