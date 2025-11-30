#!/usr/bin/env python3
# proofs/verify_hashchain.py
# Verifica una hash-chain generata da hashchain_writer.py per un dato file NDJSON

import argparse, os, sys, hashlib

def main():
    ap = argparse.ArgumentParser(description="CROVIA Hash-Chain Verifier")
    ap.add_argument("--source", required=True, help="File NDJSON originale")
    ap.add_argument("--chain", required=True, help="File hashchain_*.txt corrispondente")
    ap.add_argument("--chunk", type=int, default=10000, help="Righe per blocco (default 10000)")
    args = ap.parse_args()

    if not os.path.exists(args.source) or not os.path.exists(args.chain):
        print("[FATAL] Sorgente o chain non trovati.", file=sys.stderr); sys.exit(2)

    # Ricostruisci i digest riga per riga e confrontali con il file di chain
    with open(args.chain, "r", encoding="utf-8") as fc:
        chain_entries = [line.strip().split("\t") for line in fc if line.strip()]

    prev = b"\x00" * 32
    h = hashlib.sha256()
    count = 0
    ok = True
    entry_idx = 0

    with open(args.source, "r", encoding="utf-8-sig") as fs:
        for raw in fs:
            s = raw.rstrip("\n")
            if not s:
                continue
            h.update(prev)
            h.update(s.encode("utf-8"))
            count += 1
            if (count % args.chunk) == 0:
                digest = h.hexdigest()
                if entry_idx >= len(chain_entries):
                    print("[VERIFY] Catena più corta del necessario.", file=sys.stderr); ok = False; break
                blk, upto, dg = chain_entries[entry_idx]
                if dg != digest:
                    print(f"[VERIFY] Mismatch a block={blk} upto={upto}: atteso {dg}, calcolato {digest}", file=sys.stderr)
                    ok = False
                prev = bytes.fromhex(digest)
                h = hashlib.sha256()
                entry_idx += 1

    # Verifica blocco finale (parziale)
    if ok and (count % args.chunk) != 0:
        digest = h.hexdigest()
        if entry_idx >= len(chain_entries):
            print("[VERIFY] Catena più corta del necessario (blocco finale).", file=sys.stderr); ok = False
        else:
            blk, upto, dg = chain_entries[entry_idx]
            if dg != digest:
                print(f"[VERIFY] Mismatch blocco finale: atteso {dg}, calcolato {digest}", file=sys.stderr); ok = False

    if ok:
        print("[VERIFY] OK — catena coerente.")
        sys.exit(0)
    else:
        print("[VERIFY] FAIL — catena non coerente.")
        sys.exit(3)

if __name__ == "__main__":
    main()
