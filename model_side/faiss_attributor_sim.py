# Copyright 2025  CroviaTrust Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# model_side/faiss_attributor_sim.py — FAISS → CIM-lite (+Shapley-2) → royalty_receipt.v1
import argparse, json, os, hashlib, sys
import numpy as np, faiss

from cim_estimator import cim_estimate

#!/usr/bin/env python3
# faiss_attributor_sim.py - FAISS - CIM-lite+Shapley2 - royalty_receipt.v1
import argparse, json, os, sys, hashlib
import numpy as np, faiss

# import robusto (modulo o script)
try:
    from model_side.cim_estimator import cim_estimate
except Exception:
    sys.path.append(os.path.dirname(__file__))
    from cim_estimator import cim_estimate

def sha12(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--out", default="data/royalty_from_faiss.ndjson")
    ap.add_argument("--period", default="2025-11")
    ap.add_argument("--model-id", default="crovia-llm-v1")
    ap.add_argument("--outputs", type=int, default=200)
    ap.add_argument("--M", type=int, default=32, help="candidati FAISS")
    ap.add_argument("--K", type=int, default=3, help="top-K nel log")
    ap.add_argument("--alpha", type=float, default=10.0, help="temperatura softmax")
    ap.add_argument("--syn", type=float, default=0.12, help="frazione sinergia Shapley-2")
    ap.add_argument("--epsilon", type=float, default=0.0, help="epsilon DP (0=off)")
    ap.add_argument("--seed", type=int, default=123, help="seed query (demo)")
    args = ap.parse_args()

    # carica indice e mapping
    index = faiss.read_index(args.index)
    mp = json.load(open(args.map, "r", encoding="utf-8"))
    dim = int(mp["dim"])
    hash_data_index = mp["hash_data_index"]
    shards = {int(e["i"]): e for e in mp["shards"]}

    # clamp sicuri per FAISS (evita indici -1)
    M = min(int(args.M), index.ntotal)
    K = min(int(args.K), M)

    rng = np.random.default_rng(args.seed)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    f = open(args.out, "w", encoding="utf-8")

    hash_model = sha12(args.model_id)

    for i in range(int(args.outputs)):
        # demo: query random normalizzata (in prod: embedding dell’output)
        q = rng.standard_normal(dim).astype("float32")
        q /= (np.linalg.norm(q) + 1e-9)

        D, I = index.search(q.reshape(1, -1), M)   # D: similarity, I: indici shard
        scores = D[0].astype("float32")

        # CIM-lite + Shapley-2 + DP (se epsilon > 0)
        shares, keep_idx = cim_estimate(
            scores=scores,
            alpha=args.alpha,
            top_k=K,
            synergy_frac=args.syn,
            epsilon_dp=(args.epsilon if args.epsilon > 0 else None),
            seed=int(args.seed) + i,
        )

        # costruisci top_k ordinato per share decrescente
        order = np.argsort(-shares)
        tk = []
        rank = 0
        for j in order:
            if shares[j] <= 0:
                continue
            idx_global = int(I[0][j])   # mappa posizione locale → id shard globale
            meta = shards[idx_global]
            rank += 1
            tk.append({
                "rank": rank,
                "provider_id": meta["provider_id"],
                "shard_id": meta["shard_id"],
                "share": float(round(float(shares[j]), 6))
            })

    rec = {
        "schema": "royalty_receipt.v1",
        "output_id": f"sim_{args.period}_{i:06d}",
        "model_id": args.model_id,
        "timestamp": "2025-11-12T00:00:00Z",
        "attribution_scope": "completion",
        "usage": {"input_tokens": int(rng.integers(40, 200)),
                  "output_tokens": int(rng.integers(60, 400))},
        "top_k": tk,
        "hash_model": hash_model,
        "hash_data_index": hash_data_index,
        "meta": {
            "cim_method_id": "CIM:FAISS-SHAP2-2025-11",
            "cim_k_candidates": args.M,
            "cim_k_top": args.K,
            "alpha": args.alpha,
            "synergy_frac": args.syn
        }
    }
    # scrivi epsilon_dp solo se > 0
    if args.epsilon > 0:
       rec["epsilon_dp"] = float(args.epsilon)

if __name__ == "__main__":
    main()


