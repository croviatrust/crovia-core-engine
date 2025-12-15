#!/usr/bin/env python3
import argparse, json, math
from collections import Counter
from pathlib import Path

# -------------------------
# DSSE-lite snapshot builder
# -------------------------
# Nota: DSSE completo potrà sostituire questi contatori
# Qui facciamo: streaming, compressione, segnali auditabili

def iter_records(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def main():
    ap = argparse.ArgumentParser(description="DSSE snapshot builder (governance metrics)")
    ap.add_argument("--in", dest="inp", required=True, help="Input NDJSON / JSONL")
    ap.add_argument("--out", required=True, help="Output snapshot JSON")
    ap.add_argument("--max", type=int, default=0, help="Max records (0 = all)")
    args = ap.parse_args()

    total = 0
    missing_fields = 0
    has_receipt = 0
    legal_ambiguous = 0
    card_lengths = []

    for rec in iter_records(args.inp):
        total += 1
        if args.max and total > args.max:
            break

        # 1) missing fields (governance)
        if not rec or not isinstance(rec, dict):
            missing_fields += 1
        else:
            # esempio: campi minimi attesi
            required = ["schema"]
            if any(k not in rec or rec.get(k) in (None, "") for k in required):
                missing_fields += 1

        # 2) receipts present?
        if rec.get("schema") == "royalty_receipt.v1":
            has_receipt += 1

        # 3) legal ambiguity (licenza mancante / non chiara)
        lic = rec.get("license") or rec.get("license_id")
        if not lic or lic in ("unknown", "unverified"):
            legal_ambiguous += 1

        # 4) card length proxy (dimensione informativa)
        card_lengths.append(len(json.dumps(rec, ensure_ascii=False)))

    if total == 0:
        raise SystemExit("No records processed")

    snapshot = {
        "card_length": int(sum(card_lengths) / max(1, len(card_lengths))),
        "missing_fields_fraction": round(missing_fields / total, 6),
        "legal_ambiguity_level": round(legal_ambiguous / total, 6),
        "receipts_fraction": round(has_receipt / total, 6),
        "records_seen": total,
        "dsse_engine": "dsse-lite.v1"
    }

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(snapshot, indent=2))
    print(f"[DSSE-SNAPSHOT] wrote {args.out}")
    print(json.dumps(snapshot, indent=2))

if __name__ == "__main__":
    main()
