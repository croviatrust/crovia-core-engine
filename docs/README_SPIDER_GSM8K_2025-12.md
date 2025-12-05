# CROVIA Spider – GSM8K evidence run (period 2025-12)

> This run documents how CROVIA Spider turns a **real training dataset**
> (HF mirror of OpenAI GSM8K) into `spider_receipt.v1` evidence logs.

---

## 1. Run summary

- **Dataset:** `oieieio/gsm8k` (HF dataset, Parquet shard)
- **License hint:** `mit` (dataset license, treated as a hint)
- **CROVIA schema:** `spider_receipt.v1`
- **Engine:** `crovia-spider` (local run)
- **Period:** `2025-12`
- **Receipts generated:** `7473`

### License hint distribution

- `mit`: `7473` (~100.0%)

### Question length statistics (characters)

- mean: `234.51`
- p50: `217`
- p90: `361`
- min: `42`
- max: `985`

---

## 2. How this evidence was generated

### 2.1. Download the Parquet shard

```bash
cd /opt/crovia
mkdir -p data/gsm8k_real && cd data/gsm8k_real
wget -O gsm8k_main_train.parquet \
  "https://huggingface.co/datasets/oieieio/gsm8k/resolve/main/main/train-00000-of-00001.parquet"
```

### 2.2. Generate `spider_receipt.v1` NDJSON

```bash
cd /opt/crovia
source .venv/bin/activate
PYTHONPATH=src python << 'EOF'
import pandas as pd, json, hashlib
from datetime import datetime, timezone
from pathlib import Path

parquet_path = Path("data/gsm8k_real/gsm8k_main_train.parquet")
out_path = Path("data/spider_gsm8k_main.ndjson")

period = "2025-12"
dataset_origin = "gsm8k-main"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def make_content_id(source_url: str) -> str:
    h = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
    return f"cid:url_sha256:{h}"

print(f"[*] Loading Parquet: {parquet_path}")
df = pd.read_parquet(parquet_path)
print(f"[*] Rows in gsm8k train shard: {len(df)}")

with out_path.open("w", encoding="utf-8") as f_out:
    for idx, row in df.iterrows():
        source_url = ("hf://oieieio/gsm8k/main/"
                       "train-00000-of-00001.parquet"
                       f"#row={idx}")

        receipt = {
            "schema": "spider_receipt.v1",
            "version": "1.0.0",
            "content_id": make_content_id(source_url),
            "source_url": source_url,
            "retrieved_at": now_iso(),
            "dataset_origin": dataset_origin,
            "period": period,
            "license_hint": "mit",
            "metadata": {
                "data_source_type": "training_text",
                "confidence": {
                    "license": "medium",
                    "url_status": "not_applicable",
                    "content_availability": "known"
                },
                "original_source": "huggingface:gsm8k",
                "original_fields": {
                    "question": row["question"],
                    "answer": row["answer"],
                },
            },
            "links": [],
        }

        normalized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        receipt["receipt_id"] = f"sr_sha256:{h}"

        f_out.write(json.dumps(receipt, ensure_ascii=False) + "\n")

print(f"[*] Wrote {len(df)} receipts to {out_path}")
EOF
```

### 2.3. Validate against `spider_receipt.v1`

```bash
cd /opt/crovia
crovia-spider validate \
  --input data/spider_gsm8k_main.ndjson
```

---

## 3. Sample receipts

Below are a few redacted examples of `spider_receipt.v1` entries derived from GSM8K:

```json
{
  "content_id": "cid:url_sha256:077ddcca2dcd1386beba35ab29d237b84dcc2188e7eb20d4c8ab6619e9e0e688",
  "source_url": "hf://oieieio/gsm8k/main/train-00000-of-00001.parquet#row=0",
  "metadata": {
    "original_fields": {
      "question": "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?",
      "answer": "Natalia sold 48/2 = <<48/2=24>>24 clips in May.\nNatalia sold 48+24 = <<48+24=72>>72 clips altogether in April and May.\n#### 72"
    }
  }
}
```

```json
{
  "content_id": "cid:url_sha256:0e7504ff2fe9b3369523aa8f7450a7ef3ffe1bafab5074ce2fc3ce25fbc34caa",
  "source_url": "hf://oieieio/gsm8k/main/train-00000-of-00001.parquet#row=1",
  "metadata": {
    "original_fields": {
      "question": "Weng earns $12 an hour for babysitting. Yesterday, she just did 50 minutes of babysitting. How much did she earn?",
      "answer": "Weng earns 12/60 = $<<12/60=0.2>>0.2 per minute.\nWorking 50 minutes, she earned 0.2 x 50 = $<<0.2*50=10>>10.\n#### 10"
    }
  }
}
```

```json
{
  "content_id": "cid:url_sha256:fbb27950b6b982e45ebab1940208d380b81f5ed8d91f04d003c6a468b5c151ed",
  "source_url": "hf://oieieio/gsm8k/main/train-00000-of-00001.parquet#row=2",
  "metadata": {
    "original_fields": {
      "question": "Betty is saving money for a new wallet which costs $100. Betty has only half of the money she needs. Her parents decided to give her $15 for that purpose, and her grandparents twice as much as her parents. How much more money does Betty need to buy the wallet?",
      "answer": "In the beginning, Betty has only 100 / 2 = $<<100/2=50>>50.\nBetty's grandparents gave her 15 * 2 = $<<15*2=30>>30.\nThis means, Betty needs 100 - 50 - 30 - 15 = $<<100-50-30-15=5>>5 more.\n#### 5"
    }
  }
}
```
