#!/usr/bin/env python3
import argparse, json, os, hashlib
from datetime import datetime, timezone

# -------------------------
# Utils
# -------------------------
def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# -------------------------
# Trust logic (spiegabile)
# -------------------------
def completeness_score(bundle: dict) -> float:
    """
    Trust spiegabile (0..1) basato su presenza artefatti.
    Non usa DSSE: audit-friendly.
    """
    arts = bundle.get("artifacts") or []
    types = {a.get("type") for a in arts if isinstance(a, dict)}

    meta = bundle.get("meta") or {}
    has_sig = bool(bundle.get("signature") or meta.get("signature"))
    has_hashchain = bool(meta.get("hashchain_bound")) or ("hashchain" in types)

    weights = {
        "receipts": 0.30,
        "payouts": 0.25,
        "compliance": 0.20,
        "hashchain": 0.15,
        "signature": 0.10,
    }

    score = 0.0
    if "receipts" in types or "royalty_receipts" in types:
        score += weights["receipts"]
    if "payouts" in types:
        score += weights["payouts"]
    if "compliance" in types or "ai_act_pack" in types:
        score += weights["compliance"]
    if has_hashchain:
        score += weights["hashchain"]
    if has_sig:
        score += weights["signature"]

    return round(min(1.0, max(0.0, score)), 6)

def extract_ids(bundle: dict):
    meta = bundle.get("meta") or {}
    dataset_id = meta.get("dataset_id") or meta.get("dataset") or "unknown_dataset"
    model_id = meta.get("model_id") or meta.get("model")
    return str(dataset_id), (str(model_id) if model_id else None)

# -------------------------
# Main
# -------------------------
def main():
    ap = argparse.ArgumentParser(description="CROVIA trust_drift.v1 generator")
    ap.add_argument("--a", required=True, help="Trust bundle A (JSON)")
    ap.add_argument("--b", required=True, help="Trust bundle B (JSON)")
    ap.add_argument("--from-period", required=True, help="YYYY-MM")
    ap.add_argument("--to-period", required=True, help="YYYY-MM")
    ap.add_argument("--dataset-id", default=None)
    ap.add_argument("--model-id", default=None)
    ap.add_argument("--out", required=True, help="Output NDJSON")
    ap.add_argument("--sign", action="store_true", help="Sign with CROVIA_HMAC_KEY")
    args = ap.parse_args()

    A = load_json(args.a)
    B = load_json(args.b)

    dsA, mA = extract_ids(A)
    dsB, mB = extract_ids(B)

    dataset_id = args.dataset_id or (dsB if dsB != "unknown_dataset" else dsA)
    model_id = args.model_id or (mB or mA)

    trust_before = completeness_score(A)
    trust_after  = completeness_score(B)
    delta = round(trust_after - trust_before, 6)

    rec = {
        "schema": "trust_drift.v1",
        "dataset_id": dataset_id,
        "model_id": model_id,
        "from": args.from_period,
        "to": args.to_period,
        "trust_before": trust_before,
        "trust_after": trust_after,
        "delta": delta,
        "signals": {
            "bundle_completeness_delta": delta,
            "hashchain_before": bool((A.get("meta") or {}).get("hashchain_bound")),
            "hashchain_after":  bool((B.get("meta") or {}).get("hashchain_bound")),
            "signature_before": bool(A.get("signature")),
            "signature_after":  bool(B.get("signature")),
        },
        "inputs": [
            f"{os.path.basename(args.a)}:{sha256_file(args.a)}",
            f"{os.path.basename(args.b)}:{sha256_file(args.b)}",
        ],
        "engine": {
            "method": "bundle_completeness_v1",
            "dsse": "not required (internal)",
        },
        "meta": {
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    }

    if args.sign:
        key = os.environ.get("CROVIA_HMAC_KEY")
        if not key:
            raise SystemExit("ERROR: set CROVIA_HMAC_KEY")
        payload = json.dumps(rec, separators=(",", ":"), sort_keys=True).encode("utf-8")
        import hmac
        rec["signature"] = hmac.new(key.encode(), payload, hashlib.sha256).hexdigest()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"[DRIFT] OK -> {args.out}")
    print(f"[DRIFT] {dataset_id} {model_id or '-'} {args.from_period}->{args.to_period} Δ={delta:+.6f}")

if __name__ == "__main__":
    main()
