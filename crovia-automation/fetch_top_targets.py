#!/usr/bin/env python3
"""
CROVIA Top Targets Fetcher
==========================

Fetches top models and datasets from HuggingFace API sorted by downloads.
Generates a merged target list for DDF monitoring.

Author: Crovia Engineering
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests


HF_API_BASE = "https://huggingface.co/api"
TPR_REGISTRY_URL = "https://registry.croviatrust.com/api/targets/summary"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_top_models(limit: int = 500, min_downloads: int = 1000) -> List[Dict[str, Any]]:
    """Fetch top models from HuggingFace API sorted by downloads."""
    print(f"[CROVIA] Fetching top {limit} models...")
    
    models: List[Dict[str, Any]] = []
    seen_ids: set = set()
    offset = 0
    batch_size = 100  # HF API max per request
    
    prev_count = 0
    no_progress_count = 0
    
    while len(models) < limit:
        url = f"{HF_API_BASE}/models?sort=downloads&direction=-1&limit={batch_size}&skip={offset}"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                print(f"[WARN] Models API returned {r.status_code} at offset {offset}")
                break
            
            batch = r.json()
            if not batch:
                break
            
            for m in batch:
                downloads = m.get("downloads", 0) or 0
                if downloads < min_downloads:
                    continue
                
                model_id = m.get("id") or m.get("modelId")
                if not model_id or model_id in seen_ids:
                    continue
                
                seen_ids.add(model_id)
                models.append({
                    "target_id": model_id,
                    "tipo_target": "model",
                    "downloads": downloads,
                    "likes": m.get("likes", 0),
                    "gated": m.get("gated"),
                    "private": m.get("private"),
                    "fetched_at": _now_iso(),
                })
            
            offset += batch_size
            print(f"[CROVIA] Models: {len(models)} unique (offset={offset})")
            
            # Exit if no progress for 3 consecutive batches
            if len(models) == prev_count:
                no_progress_count += 1
                if no_progress_count >= 3:
                    print(f"[CROVIA] No more models with >={min_downloads} downloads. Stopping.")
                    break
            else:
                no_progress_count = 0
            prev_count = len(models)
            
            # Rate limiting
            time.sleep(0.3)
            
            if len(batch) < batch_size:
                break
                
        except Exception as e:
            print(f"[ERROR] Models fetch failed: {e}")
            break
    
    return models[:limit]


def fetch_top_datasets(limit: int = 500, min_downloads: int = 1000) -> List[Dict[str, Any]]:
    """Fetch top datasets from HuggingFace API sorted by downloads."""
    print(f"[CROVIA] Fetching top {limit} datasets...")
    
    datasets: List[Dict[str, Any]] = []
    seen_ids: set = set()
    offset = 0
    batch_size = 100
    
    prev_count = 0
    no_progress_count = 0
    
    while len(datasets) < limit:
        url = f"{HF_API_BASE}/datasets?sort=downloads&direction=-1&limit={batch_size}&skip={offset}"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                print(f"[WARN] Datasets API returned {r.status_code} at offset {offset}")
                break
            
            batch = r.json()
            if not batch:
                break
            
            for d in batch:
                downloads = d.get("downloads", 0) or 0
                if downloads < min_downloads:
                    continue
                
                dataset_id = d.get("id")
                if not dataset_id or dataset_id in seen_ids:
                    continue
                
                seen_ids.add(dataset_id)
                datasets.append({
                    "target_id": dataset_id,
                    "tipo_target": "dataset",
                    "downloads": downloads,
                    "likes": d.get("likes", 0),
                    "gated": d.get("gated"),
                    "private": d.get("private"),
                    "fetched_at": _now_iso(),
                })
            
            offset += batch_size
            print(f"[CROVIA] Datasets: {len(datasets)} unique (offset={offset})")
            
            # Exit if no progress for 3 consecutive batches
            if len(datasets) == prev_count:
                no_progress_count += 1
                if no_progress_count >= 3:
                    print(f"[CROVIA] No more datasets with >={min_downloads} downloads. Stopping.")
                    break
            else:
                no_progress_count = 0
            prev_count = len(datasets)
            
            time.sleep(0.3)
            
            if len(batch) < batch_size:
                break
                
        except Exception as e:
            print(f"[ERROR] Datasets fetch failed: {e}")
            break
    
    return datasets[:limit]


def load_existing_targets(path: str) -> List[Dict[str, Any]]:
    """Load existing targets from JSON file."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "targets" in data:
            return data["targets"]
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def fetch_registry_targets(registry_url: str = TPR_REGISTRY_URL) -> List[Dict[str, Any]]:
    """Fetch targets from TPR Registry API."""
    print(f"[CROVIA] Fetching targets from registry...")
    try:
        r = requests.get(registry_url, timeout=30)
        if r.status_code != 200:
            print(f"[WARN] Registry API returned {r.status_code}")
            return []
        
        data = r.json()
        targets = data.get("targets", [])
        
        result: List[Dict[str, Any]] = []
        for t in targets:
            target_id = t.get("target_id")
            if not target_id:
                continue
            result.append({
                "target_id": target_id,
                "tipo_target": t.get("tipo_target", "model"),
                "downloads": t.get("downloads", 0),
                "likes": t.get("likes", 0),
                "source": "registry",
                "fetched_at": _now_iso(),
            })
        
        print(f"[CROVIA] Registry: {len(result)} targets loaded")
        return result
        
    except Exception as e:
        print(f"[ERROR] Registry fetch failed: {e}")
        return []


def merge_targets(existing: List[Dict], new_models: List[Dict], new_datasets: List[Dict]) -> List[Dict[str, Any]]:
    """Merge existing targets with new ones, using (target_id, tipo_target) as unique key."""
    
    # Index by (target_id, tipo_target) tuple to avoid models/datasets collision
    merged: Dict[tuple, Dict[str, Any]] = {}
    
    # Add existing first
    for t in existing:
        tid = t.get("target_id")
        ttype = t.get("tipo_target", "unknown")
        if tid:
            merged[(tid, ttype)] = t
    
    # Override with new models
    for t in new_models:
        tid = t.get("target_id")
        ttype = t.get("tipo_target", "model")
        if tid:
            merged[(tid, ttype)] = t
    
    # Override with new datasets
    for t in new_datasets:
        tid = t.get("target_id")
        ttype = t.get("tipo_target", "dataset")
        if tid:
            merged[(tid, ttype)] = t
    
    # Sort by downloads descending
    result = sorted(merged.values(), key=lambda x: -(x.get("downloads") or 0))
    
    return result


def main() -> int:
    if sys.version_info < (3, 6):
        raise SystemExit("Requires Python 3.6+")
    
    # Config - 70% models, 30% datasets as per strategic analysis
    models_limit = int(os.getenv("CROVIA_MODELS_LIMIT", "1500"))
    datasets_limit = int(os.getenv("CROVIA_DATASETS_LIMIT", "500"))
    min_downloads = int(os.getenv("CROVIA_MIN_DOWNLOADS", "100"))
    include_registry = os.getenv("CROVIA_INCLUDE_REGISTRY", "1") == "1"
    
    dataset_root = os.getenv("CROVIA_OPEN_DATASET_DIR") or os.getenv("CROVIA_DATASET_DIR") or os.getcwd()
    
    # Output path
    output_path = os.path.join(dataset_root, "crovia-automation", "targets_unified.json")
    
    # 1. Fetch from TPR Registry (curated targets - ALWAYS included first)
    registry_targets: List[Dict[str, Any]] = []
    if include_registry:
        registry_targets = fetch_registry_targets()
    
    # 2. Fetch top models/datasets from HuggingFace
    models = fetch_top_models(limit=models_limit, min_downloads=min_downloads)
    datasets = fetch_top_datasets(limit=datasets_limit, min_downloads=min_downloads)
    
    # 3. Merge: Registry first (priority), then HF models, then HF datasets
    # Registry targets are preserved even if not in top downloads
    seen: set = set()
    merged: List[Dict[str, Any]] = []
    
    # Add registry targets first (they have priority)
    for t in registry_targets:
        key = (t.get("target_id"), t.get("tipo_target"))
        if key not in seen:
            seen.add(key)
            merged.append(t)
    
    # Add HF models (skip if already from registry)
    for t in models:
        key = (t.get("target_id"), t.get("tipo_target"))
        if key not in seen:
            seen.add(key)
            merged.append(t)
    
    # Add HF datasets (skip if already from registry)
    for t in datasets:
        key = (t.get("target_id"), t.get("tipo_target"))
        if key not in seen:
            seen.add(key)
            merged.append(t)
    
    # Sort by downloads descending
    merged = sorted(merged, key=lambda x: -(x.get("downloads") or 0))
    
    # Count by type
    models_count = len([t for t in merged if t.get("tipo_target") == "model"])
    datasets_count = len([t for t in merged if t.get("tipo_target") == "dataset"])
    
    # Build output
    output = {
        "schema": "crovia.targets.unified.v1",
        "generated_at": _now_iso(),
        "source": "registry+huggingface_api",
        "config": {
            "models_limit": models_limit,
            "datasets_limit": datasets_limit,
            "min_downloads": min_downloads,
            "include_registry": include_registry,
        },
        "stats": {
            "registry_targets": len(registry_targets),
            "hf_models_fetched": len(models),
            "hf_datasets_fetched": len(datasets),
            "total_unified": len(merged),
            "final_models": models_count,
            "final_datasets": datasets_count,
        },
        "targets": merged,
    }
    
    # Write output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n[CROVIA] ═══════════════════════════════════════════")
    print(f"[CROVIA]  UNIFIED TARGET POOL GENERATED")
    print(f"[CROVIA] ═══════════════════════════════════════════")
    print(f"[CROVIA]  Registry targets:    {len(registry_targets)}")
    print(f"[CROVIA]  HF Models fetched:   {len(models)}")
    print(f"[CROVIA]  HF Datasets fetched: {len(datasets)}")
    print(f"[CROVIA] ───────────────────────────────────────────")
    print(f"[CROVIA]  TOTAL UNIFIED:       {len(merged)}")
    print(f"[CROVIA]    → Models:          {models_count}")
    print(f"[CROVIA]    → Datasets:        {datasets_count}")
    print(f"[CROVIA] ═══════════════════════════════════════════")
    print(f"[CROVIA]  Output: {output_path}")
    
    # Show top 10
    print(f"\n[CROVIA] Top 10 by downloads:")
    for i, t in enumerate(merged[:10], 1):
        dl = t.get("downloads", 0)
        dl_str = f"{dl/1_000_000:.1f}M" if dl >= 1_000_000 else f"{dl/1_000:.0f}K"
        src = "®" if t.get("source") == "registry" else "HF"
        print(f"  {i}. [{src}] {t.get('target_id')} ({t.get('tipo_target')}) - {dl_str}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
