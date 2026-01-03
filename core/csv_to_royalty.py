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


import argparse, csv, json, hashlib

def build_topk(row, k):
    tk=[]
    for i in range(1, k+1):
        pid=row.get(f"provider_id{i}","").strip()
        sid=row.get(f"shard_id{i}","").strip()
        sh=row.get(f"share{i}","").strip()
        if not pid or not sid or not sh:
            continue
        try:
            sh=float(sh)
        except:
            continue
        tk.append({"rank": i, "provider_id": pid, "shard_id": sid, "share": sh})
    # ordina per share desc e riassegna rank
    tk=sorted(tk, key=lambda x: -x["share"])
    for r,it in enumerate(tk, start=1): it["rank"]=r
    return tk

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model-hash", default=None)
    ap.add_argument("--data-index-hash", default=None)
    args=ap.parse_args()

    with open(args.csv, newline="", encoding="utf-8-sig") as f, open(args.out, "w", encoding="utf-8") as out:
        rd=csv.DictReader(f)
        for row in rd:
            k=int(row.get("k","3") or 3)
            tk=build_topk(row, k)
            if not tk: 
                continue
            model_id=row.get("model_id","crovia-llm-v1")
            period = row.get("timestamp","")[:7] if row.get("timestamp") else "0000-00"
            mh = args.model_hash or hashlib.sha256(f"{model_id}|{period}".encode()).hexdigest()[:12]
            dh = args.data_index_hash or hashlib.sha256(f"csvseed|{period}".encode()).hexdigest()[:12]
            obj={
                "schema": "royalty_receipt.v1",
                "output_id": row.get("output_id"),
                "model_id": model_id,
                "timestamp": row.get("timestamp"),
                "attribution_scope": "completion",
                "usage": {
                    "input_tokens": int(row.get("input_tokens", "0") or 0),
                    "output_tokens": int(row.get("output_tokens", "0") or 0),
                },
                "top_k": tk,
                "hash_model": mh,
                "hash_data_index": dh
            }
            # license_refs opzionali
            lic=[]
            for i in range(1,10):
                lid=row.get(f"license_id{i}","").strip()
                if lid:
                    lic.append({"license_id": lid, "source": "csv"})
            if lic:
                # dedup
                dd={}
                for x in lic: dd[x["license_id"]]=x
                obj["license_refs"]=list(dd.values())

            out.write(json.dumps(obj, ensure_ascii=False)+"\n")
    print(f"[ADAPTER] NDJSON: {args.out}")

if __name__=="__main__":
    main()

