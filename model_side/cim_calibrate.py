#!/usr/bin/env python3
# cim_calibrate.py - trova alpha per target avg top1 share (su FAISS scores)
import argparse, json, numpy as np, faiss
from cim_estimator import softmax_temp

def avg_top1_for_alpha(index, dim, M, samples, alpha, seed=123):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(samples):
        q = rng.standard_normal(dim).astype("float32")
        q /= (np.linalg.norm(q)+1e-9)
        D,I = index.search(q.reshape(1,-1), M)
        shares = softmax_temp(D[0], alpha=alpha)
        vals.append(float(shares.max()))
    return float(np.mean(vals))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--dim", type=int, required=True)
    ap.add_argument("--M", type=int, default=32)
    ap.add_argument("--samples", type=int, default=200)
    ap.add_argument("--target", type=float, default=0.55, help="target avg top1 share")
    ap.add_argument("--out", default="data/cim_calibrator.json")
    args = ap.parse_args()

    index = faiss.read_index(args.index)
    lo, hi = 1.0, 50.0
    for _ in range(20):
        mid = 0.5*(lo+hi)
        avg = avg_top1_for_alpha(index, args.dim, args.M, args.samples, mid)
        if avg < args.target:
            lo = mid
        else:
            hi = mid
    alpha = 0.5*(lo+hi)

    json.dump({"alpha": alpha, "target": args.target, "M": args.M, "samples": args.samples},
              open(args.out, "w"), indent=2)
    print(f"[CAL] alpha≈{alpha:.3f} per top1≈{args.target} → {args.out}")

if __name__ == "__main__":
    main()
