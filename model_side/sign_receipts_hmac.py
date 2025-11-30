#!/usr/bin/env python3
# sign_receipts_hmac.py - aggiunge "signature" HMAC-SHA256 al JSON per riga
import argparse, json, os, hmac, hashlib

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="NDJSON input")
    ap.add_argument("--out", dest="out", required=True, help="NDJSON output firmato")
    ap.add_argument("--env", dest="env", default="CROVIA_HMAC_KEY")
    args = ap.parse_args()

    key = os.environ.get(args.env, "")
    if not key:
        raise SystemExit(f"ERROR: set {args.env} in environment")

    with open(args.inp, "r", encoding="utf-8") as fi, open(args.out, "w", encoding="utf-8") as fo:
        for lineno, line in enumerate(fi, 1):
            s = line.strip()
            if not s: 
                continue
            try:
                obj = json.loads(s)
            except Exception:
                print(f"[WARN] skip invalid JSON at line {lineno}")
                continue
            payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            sig = hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
            obj["signature"] = sig
            fo.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"[HMAC] firmato → {args.out} (env={args.env})")

if __name__ == "__main__":
    main()
