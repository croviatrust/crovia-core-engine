import json, sys
from pathlib import Path

def iter_ndjson(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln: 
                continue
            try:
                yield json.loads(ln)
            except Exception:
                continue

def main():
    if len(sys.argv) < 4:
        print("USO: python tools/trust_from_receipts.py <receipts.jsonl> <identity_map.json> <period YYYY-MM> > payouts.ndjson", file=sys.stderr)
        sys.exit(1)

    receipts_path = Path(sys.argv[1])
    idmap_path    = Path(sys.argv[2])
    period        = sys.argv[3]

    idmap = json.loads(idmap_path.read_text(encoding="utf-8"))

    for rec in iter_ndjson(receipts_path):
        # supporta sia 'receipt' (wrapper) sia flat
        topk = rec.get("top_k")
        if topk is None and isinstance(rec.get("receipt"), dict):
            topk = rec["receipt"].get("top_k")
        if not topk:
            continue

        # trust/risk di default per il campione (puoi farli calcolare dal tuo trust engine)
        trust = float(rec.get("trust", 0.7))
        risk  = float(rec.get("risk", 0.1))

        # ripartisci quota sui top-k con 'share' se presente, altrimenti parti da score_mean normalizzato
        shares = []
        ssum = 0.0
        for k in topk:
            lab = k.get("label") or f"shard_{k.get('index')}"
            s  = float(k.get("share", 0.0) or k.get("score_mean", 0.0))
            shares.append((lab, s))
            ssum += s
        if ssum <= 0:
            continue
        shares = [(lab, s/ssum) for (lab, s) in shares]

        # emetti payouts.v1 per provider, accorpando shard -> provider
        per_provider = {}
        for lab, frac in shares:
            prov = (idmap.get(lab) or {}).get("provider_id")
            if not prov:
                # shard non mappato -> salta o manda a "unknown"
                prov = "unknown"
            per_provider[prov] = per_provider.get(prov, 0.0) + frac

        # amount base = 1.0 per receipt (unitario); puoi moltiplicare per revenue_unit se vuoi
        for prov, frac in per_provider.items():
            out = {
                "schema": "payouts.v1",
                "provider_id": prov,
                "period": period,
                "amount": round(frac, 6),   # share frazionaria dell'unitÃ 
                "trust": trust,
                "risk": risk
            }
            print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))

if __name__ == "__main__":
    main()
