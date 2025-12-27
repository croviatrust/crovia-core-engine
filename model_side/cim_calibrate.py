# Copyright 2025  Tarik En Nakhai
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

