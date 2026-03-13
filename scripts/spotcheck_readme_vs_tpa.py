import json
import urllib.request
from pathlib import Path

MODELS = [
    "google-bert/bert-base-cased",
    "BAAI/bge-m3",
    "google-t5/t5-base",
    "colbert-ir/colbertv2.0",
    "openai/clip-vit-large-patch14",
    "Qwen/Qwen2-VL-7B-Instruct",
]

TRAIN_KEYS = [
    "training data",
    "trained on",
    "dataset",
    "corpus",
    "data sources",
    "training procedure",
    "training details",
]
EVAL_KEYS = [
    "evaluation",
    "benchmark",
    "results",
    "performance",
    "accuracy",
    "f1",
    "bleu",
    "rouge",
]
LIMIT_KEYS = [
    "limitations",
    "risk",
    "warning",
    "caveat",
    "out of scope",
    "should not be used",
]


def fetch_readme(repo_id: str) -> str:
    url = f"https://huggingface.co/{repo_id}/raw/main/README.md"
    req = urllib.request.Request(url, headers={"User-Agent": "CroviaTrust/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def contains_any(content: str, keys) -> bool:
    if not content:
        return False
    lower = content.lower()
    return any(k in lower for k in keys)


def load_tpa_nec_flags(model_id: str):
    data = json.loads(Path("/var/www/registry/data/tpa_latest.json").read_text())
    entry = next((t for t in data.get("tpas", []) if t.get("model_id") == model_id), None)
    if not entry:
        return None
    obs = entry.get("observations") or []
    nec = {}
    for o in obs:
        nid = o.get("necessity_id")
        if nid:
            nec[nid] = o.get("is_present")
    return nec


def main() -> None:
    print("MODEL|training_or_dataset|evaluation|limitations|NEC#1_present|NEC#10_present")
    for mid in MODELS:
        try:
            readme = fetch_readme(mid)
        except Exception:
            readme = ""

        train_or_data = contains_any(readme, TRAIN_KEYS)
        eval_present = contains_any(readme, EVAL_KEYS)
        limits_present = contains_any(readme, LIMIT_KEYS)
        nec = load_tpa_nec_flags(mid) or {}

        print(
            "|".join(
                [
                    mid,
                    "1" if train_or_data else "0",
                    "1" if eval_present else "0",
                    "1" if limits_present else "0",
                    str(nec.get("NEC#1")),
                    str(nec.get("NEC#10")),
                ]
            )
        )


if __name__ == "__main__":
    main()
