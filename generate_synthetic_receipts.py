import json
import random
from datetime import datetime, timedelta
from pathlib import Path

OUTPUT_PATH = Path("data/royalty_synthetic.ndjson")

PROVIDERS = [
    {"id": "news_corp", "topk": 92},
    {"id": "research_lab", "topk": 65},
    {"id": "community_forum", "topk": 25},
    {"id": "open_web", "topk": 5},
]

NUM_RECEIPTS = 3000
START_TIME = datetime(2025, 11, 1)

def generate_receipt(i: int) -> dict:
    timestamp = START_TIME + timedelta(seconds=i * 30)
    model_id = "crovia-2025-llm"
    segment = random.choice(["train", "eval", "inference"])

    # Probabilistically assign providers based on topk
    provider_pool = []
    for p in PROVIDERS:
        weight = p["topk"]
        provider_pool += [p["id"]] * weight

    chosen_providers = list(set(random.choices(provider_pool, k=random.randint(1, 3))))
    score = round(random.uniform(0.1, 1.0), 3)

    return {
        "timestamp": timestamp.isoformat(),
        "model_id": model_id,
        "segment": segment,
        "providers": chosen_providers,
        "score": score,
    }

def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for i in range(NUM_RECEIPTS):
            receipt = generate_receipt(i)
            f.write(json.dumps(receipt) + "\n")

    print(f"[OK] Synthetic receipts written to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
