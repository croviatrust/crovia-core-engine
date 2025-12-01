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

# events_to_royalty.py: convert simple usage events NDJSON into royalty_receipt.v1 NDJSON

import argparse, json, hashlib
from pathlib import Path

ROYALTY_SCHEMA = "royalty_receipt.v1"


def iter_ndjson(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                yield lineno, json.loads(s)
            except Exception as e:
                print(f"[WARN] line {lineno}: JSON parse error: {e}")
                continue


def make_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser(
        description="Convert simple usage events (timestamp, model_id, providers, score) "
                    "into royalty_receipt.v1 NDJSON for CROVIA."
    )
    ap.add_argument("--input", required=True, help="Input NDJSON events file")
    ap.add_argument("--out", required=True, help="Output NDJSON royalty_receipt.v1 file")
    ap.add_argument(
        "--attribution-scope",
        default="synthetic_demo",
        help="Value for attribution_scope field (default: synthetic_demo)",
    )
    ap.add_argument(
        "--default-model-id",
        default="demo-llm-2025",
        help="Fallback model_id if missing in events (default: demo-llm-2025)",
    )
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.out)

    if not in_path.exists():
        raise SystemExit(f"[ADAPTER] Input not found: {in_path}")

    model_hash_cache = {}
    data_index_hash = make_hash("synthetic_demo_index_v1")

    n_in = 0    # righe lette
    n_out = 0   # receipts scritte

    with out_path.open("w", encoding="utf-8") as out:
        for lineno, ev in iter_ndjson(in_path):
            n_in += 1

            ts = ev.get("timestamp")
            if not isinstance(ts, str):
                print(f"[WARN] line {lineno}: missing/invalid timestamp, skipping")
                continue

            model_id = ev.get("model_id") or args.default_model_id
            if not isinstance(model_id, str):
                model_id = str(model_id)

            segment = ev.get("segment") or "demo"
            providers = ev.get("providers")
            if not isinstance(providers, list) or not providers:
                print(f"[WARN] line {lineno}: no providers list, skipping")
                continue

            # preserva l'ordine ma toglie duplicati
            seen = set()
            clean_providers = []
            for p in providers:
                if not isinstance(p, str):
                    p = str(p)
                if not p:
                    continue
                if p in seen:
                    continue
                seen.add(p)
                clean_providers.append(p)

            if not clean_providers:
                print(f"[WARN] line {lineno}: providers list empty after cleanup, skipping")
                continue

            share = 1.0 / len(clean_providers)
            top_k = []
            for rank, pid in enumerate(clean_providers, 1):
                top_k.append(
                    {
                        "rank": rank,
                        "provider_id": pid,
                        "shard_id": f"synthetic:{pid}",
                        "share": share,
                    }
                )

            # hash modello (semplice, ma stabile)
            if model_id in model_hash_cache:
                hash_model = model_hash_cache[model_id]
            else:
                hash_model = make_hash(model_id)
                model_hash_cache[model_id] = hash_model

            # usage minimale: token a 0, tanto è demo
            usage = {
                "input_tokens": 0,
                "output_tokens": 0,
            }

            output_id = f"demo-{lineno:06d}"
            request_id = output_id

            rec = {
                "schema": ROYALTY_SCHEMA,
                "output_id": output_id,
                "request_id": request_id,
                "model_id": model_id,
                "timestamp": ts,
                "attribution_scope": f"{args.attribution_scope}/{segment}",
                "usage": usage,
                "top_k": top_k,
                "hash_model": hash_model,
                "hash_data_index": data_index_hash,
            }

            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_out += 1

    print(f"[ADAPTER] Read {n_in} events, wrote {n_out} royalty_receipt.v1 records to {out_path}")


if __name__ == "__main__":
    main()
