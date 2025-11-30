#!/usr/bin/env python3
# generate_receipts.py
# Crea royalty_receipts.ndjson realistici da un seed YAML (provider/shard/pesi + licenze)
# Requisiti: pyyaml

import argparse, json, os, random, hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
try:
    import yaml
except ImportError:
    raise SystemExit("[FATAL] manca PyYAML: pip install pyyaml")

SCHEMA = "royalty_receipt.v1"

def load_seed(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def timestamp_in_period(period: str, i: int) -> str:
    year, month = map(int, period.split("-"))
    day = 1 + (i % 28)
    base = datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc)
    t = base + timedelta(seconds=random.randint(0, 43200))
    return t.isoformat().replace("+00:00", "Z")

def rnd_ci(center: float, width: float = 0.05):
    lo = max(0.0, center - random.random()*width)
    hi = min(1.0, center + random.random()*width)
    if lo > hi: lo, hi = hi, lo
    return lo, hi

def main():
    ap = argparse.ArgumentParser(description="CROVIA synthetic royalty_receipts generator")
    ap.add_argument("--seed", required=True, help="YAML con providers/shards/pesi")
    ap.add_argument("--outputs", type=int, required=True, help="Numero di ricevute da generare")
    ap.add_argument("--model-id", default="crovia-llm-v1", help="model_id")
    ap.add_argument("--out", default="data/royalty_receipts.ndjson", help="NDJSON di output")
    ap.add_argument("--sum_noise", type=float, default=0.01, help="rumore (0–0.05) per anomalie somma share")
    args = ap.parse_args()

    S = load_seed(args.seed)
    period = S.get("period")
    provs = S.get("providers", [])
    defaults = S.get("defaults", {})
    k_top = int(defaults.get("k_top", 3))
    dp_epsilon = defaults.get("dp_epsilon", None)
    add_ci = bool(defaults.get("add_ci", True))
    license_inclusion_rate = float(defaults.get("license_inclusion_rate", 0.5))
    anomaly_rate = float(defaults.get("anomaly_rate", 0.0))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    # normalizza pesi per scelte deterministiche
    random.seed(42)

    # Precalcolo pesi normalizzati
    tot_p = sum(max(0.0, p.get("weight", 0.0)) for p in provs) or 1.0
    for p in provs:
        p["_w"] = max(0.0, p.get("weight", 0.0)) / tot_p
        sh = p.get("shards", [])
        tot_s = sum(max(0.0, s.get("weight", 0.0)) for s in sh) or 1.0
        for s in sh:
            s["_w"] = max(0.0, s.get("weight", 0.0)) / tot_s

    def pick_weighted(items, key):
        r = random.random()
        acc = 0.0
        for it in items:
            acc += it[key]
            if r <= acc:
                return it
        return items[-1]

    with open(args.out, "w", encoding="utf-8") as fo:
        for i in range(args.outputs):
            chosen = []
            used = set()
            while len(chosen) < k_top and len(used) < len(provs):
                p = pick_weighted(provs, "_w")
                if p["id"] in used:
                    continue
                used.add(p["id"])
                shards = p.get("shards", [])
                if not shards:
                    continue
                s = pick_weighted(shards, "_w")
                chosen.append((p, s))

            # quote random che sommano ~1 (con possibili anomalie)
            alphas = [random.uniform(0.1, 1.0) for _ in chosen]
            tot = sum(alphas) or 1.0
            shares = [a / tot for a in alphas]
            if random.random() < anomaly_rate:
                bump = random.uniform(args.sum_noise, args.sum_noise*2)
                shares = [min(1.0, s + bump/len(shares)) for s in shares]

            tk = []
            for rank, (pair, sh) in enumerate(sorted(zip(chosen, shares), key=lambda x: -x[1]), start=1):
                prov, sha = pair
                item = {
                    "rank": rank,
                    "provider_id": prov["id"],
                    "shard_id": sha["id"],
                    "share": round(sh, 6),
                }
                if add_ci:
                    lo, hi = rnd_ci(item["share"])
                    item["share_ci95_low"] = round(lo, 6)
                    item["share_ci95_high"] = round(hi, 6)
                tk.append(item)

            ts = timestamp_in_period(period, i)
            out = {
                "schema": SCHEMA,
                "output_id": f"out_{period}_{i:06d}",
                "model_id": args.model_id,
                "timestamp": ts,
                "attribution_scope": "completion",
                "usage": {"input_tokens": random.randint(40, 300), "output_tokens": random.randint(60, 400)},
                "top_k": tk,
                "hash_model": hashlib.sha256(f"{args.model_id}|{period}".encode()).hexdigest()[:12],
                "hash_data_index": hashlib.sha256(f"seed|{period}".encode()).hexdigest()[:12],
            }
            if dp_epsilon is not None:
                out["epsilon_dp"] = float(dp_epsilon)

            if random.random() < license_inclusion_rate:
                lic_refs = []
                for _, shard in chosen:
                    lid = shard.get("license_id")
                    if lid:
                        lic_refs.append({"license_id": lid, "source": "seed"})
                # dedup
                uniq = {x["license_id"]: x for x in lic_refs}
                out["license_refs"] = list(uniq.values())

            fo.write(json.dumps(out, ensure_ascii=False) + "\n")

    print(f"[GEN] Scritto: {os.path.abspath(args.out)}")

if __name__ == "__main__":
    main()
