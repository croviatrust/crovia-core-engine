#!/usr/bin/env python3
# Costruisce indice FAISS e mapping con hash_data_index
import argparse, json, os, hashlib
import numpy as np
import faiss

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="NPZ con vettori shard")
    ap.add_argument("--out", dest="out", default="data/shard_index.faiss")
    ap.add_argument("--map", dest="map", default="data/shard_index_map.json")
    args = ap.parse_args()

    with open(args.inp, "rb") as f: npz_bytes = f.read()
    dset = np.load(args.inp)
    xb = dset["vectors"]
    dim = int(dset["dim"][0]) if "dim" in dset else xb.shape[1]
    shard_ids = dset["shard_ids"].tolist()
    providers = dset["providers"].tolist()

    faiss.normalize_L2(xb)
    index = faiss.IndexFlatIP(dim)
    index.add(xb)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    faiss.write_index(index, args.out)

    hash_data_index = sha256_hex(npz_bytes)
    mapping = {
        "index_path": args.out,
        "hash_data_index": hash_data_index,
        "dim": dim,
        "shards": [
            {"i": int(i), "shard_id": s, "provider_id": p}
            for i, (s, p) in enumerate(zip(shard_ids, providers))
        ]
    }
    with open(args.map, "w", encoding="utf-8") as m:
        json.dump(mapping, m, indent=2)

    print(f"[FAISS] Index: {args.out}  |  dim={dim}  |  n={len(shard_ids)}")
    print(f"[FAISS] Map:   {args.map}")
    print(f"[FAISS] hash_data_index={hash_data_index}")

if __name__ == "__main__":
    main()
