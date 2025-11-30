#!/usr/bin/env python3
import argparse, json, os, hashlib
import numpy as np

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def vec_from_hash(text: str, dim: int) -> np.ndarray:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    need = dim * 4
    buf = (h * ((need // len(h)) + 1))[:need]
    v = np.frombuffer(buf, dtype=np.uint32).astype("float32")[:dim]
    n = np.linalg.norm(v) + 1e-9
    return (v / n).astype("float32")

def main():
    ap = argparse.ArgumentParser(description="CROVIA shard sketch generator")
    ap.add_argument("--meta", required=True)
    ap.add_argument("--out", default="data/shard_vectors.npz")
    args = ap.parse_args()

    meta = json.load(open(args.meta, "r", encoding="utf-8"))
    dim = int(meta.get("dim", 384))
    shards = meta["shards"]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    vectors, shard_ids, providers = [], [], []
    for e in shards:
        pid, sid = e["provider_id"], e["shard_id"]
        vectors.append(vec_from_hash(f"{pid}::{sid}", dim))
        shard_ids.append(sid); providers.append(pid)

    X = np.vstack(vectors).astype("float32")
    np.savez_compressed(args.out,
        vectors=X,
        shard_ids=np.array(shard_ids),
        providers=np.array(providers),
        dim=np.array([dim], dtype=np.int32)
    )
    with open(args.out, "rb") as f: h = sha256_hex(f.read())
    open(os.path.splitext(args.out)[0] + "_sha256.txt","w",encoding="utf-8").write(f"DATA_INDEX_SHA256={h}\n")
    print(f"[SKETCH] {len(shard_ids)} shard, dim={dim} → {args.out}")
    print(f"[SKETCH] hash_data_index={h}")

if __name__ == "__main__":
    main()
