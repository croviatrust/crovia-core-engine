#!/usr/bin/env python3
"""
Generate balanced targets file: 900 models + 300 datasets = 1200 total
"""

import json
import requests
from datetime import datetime, timezone

HF_API = "https://huggingface.co/api"

def fetch_top_models(limit: int = 900) -> list:
    """Fetch top models by downloads."""
    print(f"Fetching top {limit} models...")
    url = f"{HF_API}/models?sort=downloads&direction=-1&limit={limit}"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        print(f"Error fetching models: {resp.status_code}")
        return []
    
    models = resp.json()
    result = []
    for m in models:
        result.append({
            "target_id": m.get("id", ""),
            "tipo_target": "model",
            "downloads": m.get("downloads", 0),
            "likes": m.get("likes", 0),
            "gated": m.get("gated"),
            "private": m.get("private", False),
            "fetched_at": datetime.now(timezone.utc).isoformat()
        })
    
    print(f"  Fetched {len(result)} models")
    return result


def fetch_top_datasets(limit: int = 300) -> list:
    """Fetch top datasets by downloads."""
    print(f"Fetching top {limit} datasets...")
    url = f"{HF_API}/datasets?sort=downloads&direction=-1&limit={limit}"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        print(f"Error fetching datasets: {resp.status_code}")
        return []
    
    datasets = resp.json()
    result = []
    for d in datasets:
        result.append({
            "target_id": d.get("id", ""),
            "tipo_target": "dataset",
            "downloads": d.get("downloads", 0),
            "likes": d.get("likes", 0),
            "gated": d.get("gated"),
            "private": d.get("private", False),
            "fetched_at": datetime.now(timezone.utc).isoformat()
        })
    
    print(f"  Fetched {len(result)} datasets")
    return result


def main():
    print("=" * 50)
    print("Generating balanced targets file")
    print("=" * 50)
    
    models = fetch_top_models(900)
    datasets = fetch_top_datasets(300)
    
    all_targets = models + datasets
    
    output = {
        "schema": "crovia.targets.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "huggingface_api",
        "config": {
            "models_limit": 900,
            "datasets_limit": 300,
            "min_downloads": 0,
            "note": "Proportional to HF reality: ~75% models, ~25% datasets"
        },
        "stats": {
            "models_fetched": len(models),
            "datasets_fetched": len(datasets),
            "total_merged": len(all_targets)
        },
        "targets": all_targets
    }
    
    outfile = "crovia-automation/targets_balanced_1200.json"
    with open(outfile, "w") as f:
        json.dump(output, f, indent=2)
    
    print()
    print(f"Written to {outfile}")
    print(f"  Models: {len(models)}")
    print(f"  Datasets: {len(datasets)}")
    print(f"  Total: {len(all_targets)}")


if __name__ == "__main__":
    main()
