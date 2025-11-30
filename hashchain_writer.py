#!/usr/bin/env python3
# proofs/hashchain_writer.py
# Calcola una rolling hash-chain sui blocchi di un NDJSON (per giorno o per intero file)

import argparse, json, os, sys, hashlib
from typing import Iterable

def iter_lines(path: str):
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            s = line.rstrip("\n")
            if s:
                yield s

def main():
    ap = argparse.ArgumentParser(description="CROVIA Hash-Chain Writer")
    ap.add_argument("--source", required=True, help="File NDJSON sorgente")
    ap.add_argument("--out", required=False, help="Output proofs/hashchain_<basename>.txt")
    ap.add_argument("--chunk", type=int, default=10000, help="Righe per blocco (default 10000)")
    args = ap.parse_args()

    if not os.path.exists(args.source):
        print(f"[FATAL] Sorgente non trovato: {args.source}", file=sys.stderr); sys.exit(2)

    base = os.path.basename(args.source)
    out_path = args.out or os.path.join("proofs", f"hashchain_{base}.txt")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    prev = b"\x00" * 32  # anchor iniziale
    block_idx = 0
    count = 0
    h = hashlib.sha256()

    with open(out_path, "w", encoding="utf-8") as out:
        for s in iter_lines(args.source):
            h.update(prev)
            h.update(s.encode("utf-8"))
            count += 1
            if (count % args.chunk) == 0:
                digest = h.hexdigest()
                out.write(f"{block_idx}\t{count}\t{digest}\n")
                prev = bytes.fromhex(digest)
                h = hashlib.sha256()
                block_idx += 1

        # flush finale (blocchi parziali)
        if count % args.chunk != 0:
            digest = h.hexdigest()
            out.write(f"{block_idx}\t{count}\t{digest}\n")

    print(f"[HASHCHAIN] Scritto: {out_path}")

if __name__ == "__main__":
    main()
