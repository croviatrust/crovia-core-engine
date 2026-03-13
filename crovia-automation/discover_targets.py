#!/usr/bin/env python3
"""
discover_targets.py — Multi-source AI model discovery (no auth needed)

Discovers models via 7 strategies:
  1. Global sort (downloads, likes, trending, lastModified)
  2. By pipeline_tag (text-generation, image-classification, etc.)
  3. By library (transformers, diffusers, sentence-transformers, etc.)
  4. By high-impact organization (meta-llama, google, microsoft, etc.)
  5. Papers With Code cross-reference (aggressive only)
  6. GitHub ML repos cross-reference (aggressive only)
  7. Ollama known model mapping (always)

All queries use PUBLIC APIs — no authentication required.
PWC/GitHub names are used as search terms on HF to find actual model IDs.
The HF account block does NOT affect this script.

Usage:
    python3 discover_targets.py --output targets_unified.json --limit 500
    python3 discover_targets.py --output targets_unified.json --limit 500 --aggressive
"""

import json
import os
import sys
import time
import requests
from datetime import datetime, timezone
from typing import List, Dict, Set, Optional

HF_API = "https://huggingface.co/api/models"
TIMEOUT = 20
DELAY = 0.6  # conservative: ~100 req/min

# Multi-source APIs (public, no auth needed)
PWC_API = "https://paperswithcode.com/api/v1"
GITHUB_API = "https://api.github.com"
OLLAMA_HF_MAP = {
    "llama3": "meta-llama/Meta-Llama-3-8B",
    "llama3.1": "meta-llama/Llama-3.1-8B",
    "llama3.2": "meta-llama/Llama-3.2-3B",
    "llama3.3": "meta-llama/Llama-3.3-70B-Instruct",
    "llama2": "meta-llama/Llama-2-7b-hf",
    "mistral": "mistralai/Mistral-7B-v0.3",
    "mixtral": "mistralai/Mixtral-8x7B-v0.1",
    "phi3": "microsoft/Phi-3-mini-4k-instruct",
    "phi3.5": "microsoft/Phi-3.5-mini-instruct",
    "gemma": "google/gemma-7b",
    "gemma2": "google/gemma-2-9b",
    "qwen": "Qwen/Qwen-7B",
    "qwen2": "Qwen/Qwen2-7B",
    "qwen2.5": "Qwen/Qwen2.5-7B",
    "codellama": "meta-llama/CodeLlama-7b-hf",
    "deepseek-coder": "deepseek-ai/deepseek-coder-6.7b-base",
    "deepseek-coder-v2": "deepseek-ai/DeepSeek-Coder-V2-Lite-Base",
    "yi": "01-ai/Yi-1.5-9B",
    "vicuna": "lmsys/vicuna-7b-v1.5",
    "neural-chat": "Intel/neural-chat-7b-v3-1",
    "starling-lm": "Nexusflow/Starling-LM-7B-beta",
    "orca-mini": "pankajmathur/orca_mini_3b",
    "llava": "llava-hf/llava-1.5-7b-hf",
    "stablelm": "stabilityai/stablelm-2-1_6b",
    "starcoder2": "bigcode/starcoder2-7b",
    "command-r": "CohereForAI/c4ai-command-r-v01",
    "falcon": "tiiuae/falcon-7b",
    "solar": "upstage/SOLAR-10.7B-v1.0",
    "openchat": "openchat/openchat-3.5-0106",
    "dolphin-mixtral": "cognitivecomputations/dolphin-2.6-mixtral-8x7b",
    "nous-hermes2": "NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO",
    "wizard-math": "WizardLMTeam/WizardMath-7B-V1.1",
}

# GitHub search queries for ML repos
GITHUB_ML_QUERIES = [
    "topic:machine-learning topic:model stars:>1000",
    "topic:deep-learning topic:pretrained-models stars:>500",
    "topic:transformer topic:nlp stars:>500",
    "topic:computer-vision topic:model stars:>500",
    "topic:large-language-model stars:>500",
    "topic:diffusion-model stars:>200",
]

# ── Discovery dimensions ──────────────────────────────────────────

SORT_CRITERIA = ["downloads", "likes", "lastModified", "trending"]

PIPELINE_TAGS = [
    "text-generation", "text2text-generation", "text-classification",
    "token-classification", "question-answering", "summarization",
    "translation", "fill-mask", "conversational",
    "feature-extraction", "sentence-similarity",
    "image-classification", "object-detection", "image-segmentation",
    "image-to-text", "text-to-image", "image-to-image",
    "automatic-speech-recognition", "text-to-speech", "audio-classification",
    "zero-shot-classification", "table-question-answering",
    "reinforcement-learning", "depth-estimation",
    "video-classification", "document-question-answering",
]

LIBRARIES = [
    "transformers", "diffusers", "sentence-transformers", "timm",
    "spacy", "allennlp", "flair", "fastai", "stable-baselines3",
    "adapter-transformers", "setfit", "peft", "gguf", "mlx",
]

HIGH_IMPACT_ORGS = [
    "meta-llama", "google", "microsoft", "openai", "mistralai",
    "stabilityai", "huggingface", "EleutherAI", "bigscience",
    "facebook", "BAAI", "Qwen", "deepseek-ai", "tiiuae",
    "allenai", "nvidia", "databricks", "Salesforce", "mosaicml",
    "01-ai", "internlm", "openbmb", "bigcode", "CohereForAI",
    "NousResearch", "teknium", "Open-Orca", "lmsys", "THUDM",
    "amazon", "apple", "cerebras", "togethercomputer", "upstage",
    "abacusai", "Writer", "AI21Labs", "anthropic",
]

# ── Fetch helpers ─────────────────────────────────────────────────

def fetch_page(params: Dict, retries: int = 2) -> List[Dict]:
    """Fetch a single page from HF API with retry."""
    for attempt in range(retries + 1):
        try:
            r = requests.get(HF_API, params=params, timeout=TIMEOUT,
                             headers={"User-Agent": "CroviaTrust/1.0"})
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 30))
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                return []
            return r.json() or []
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
            else:
                print(f"    Error: {e}")
    return []


def fetch_models(sort: str = "downloads", limit: int = 200,
                 pipeline_tag: Optional[str] = None,
                 library: Optional[str] = None,
                 author: Optional[str] = None,
                 search: Optional[str] = None) -> List[Dict]:
    """Fetch models with pagination and optional filters."""
    results = []
    offset = 0
    per_page = min(limit, 100)

    while len(results) < limit:
        params = {
            "sort": sort,
            "direction": "-1",
            "limit": per_page,
            "offset": offset,
        }
        if pipeline_tag:
            params["pipeline_tag"] = pipeline_tag
        if library:
            params["library"] = library
        if author:
            params["author"] = author
        if search:
            params["search"] = search

        batch = fetch_page(params)
        if not batch:
            break
        results.extend(batch)
        offset += per_page
        time.sleep(DELAY)

        # If we got less than per_page, there's no more
        if len(batch) < per_page:
            break

    return results[:limit]


def extract_model_info(m: Dict) -> Optional[Dict]:
    """Extract standardized model info from HF API response."""
    mid = m.get("id", "")
    if not mid or "/" not in mid:
        return None
    return {
        "model_id": mid,
        "author": m.get("author", ""),
        "downloads": m.get("downloads", 0),
        "likes": m.get("likes", 0),
        "pipeline_tag": m.get("pipeline_tag", ""),
        "last_modified": m.get("lastModified", ""),
        "library_name": m.get("library_name", ""),
        "tags": m.get("tags", [])[:5],
    }


# ── Main discovery ────────────────────────────────────────────────

def discover(limit: int = 200, aggressive: bool = False) -> Dict[str, Dict]:
    """Discover models from multiple strategies. Returns {model_id: info}."""
    all_models = {}
    stats = {"queries": 0, "api_calls": 0}

    def ingest(models: List[Dict], label: str):
        before = len(all_models)
        for m in models:
            info = extract_model_info(m)
            if info and info["model_id"] not in all_models:
                all_models[info["model_id"]] = info
        new = len(all_models) - before
        stats["queries"] += 1
        if new > 0:
            print(f"    +{new} new (total {len(all_models)})")

    # Strategy 1: Global sort
    print("\n[Strategy 1] Global sort...")
    for sort_by in SORT_CRITERIA:
        print(f"  Top {limit} by {sort_by}...")
        models = fetch_models(sort=sort_by, limit=limit)
        ingest(models, f"sort:{sort_by}")

    # Strategy 2: By pipeline_tag
    tag_limit = limit if aggressive else min(limit, 100)
    tags = PIPELINE_TAGS if aggressive else PIPELINE_TAGS[:12]
    print(f"\n[Strategy 2] By pipeline_tag ({len(tags)} tags, {tag_limit}/tag)...")
    for tag in tags:
        print(f"  {tag}...")
        models = fetch_models(sort="downloads", limit=tag_limit, pipeline_tag=tag)
        ingest(models, f"tag:{tag}")

    # Strategy 3: By library
    lib_limit = limit if aggressive else min(limit, 100)
    libs = LIBRARIES if aggressive else LIBRARIES[:6]
    print(f"\n[Strategy 3] By library ({len(libs)} libs, {lib_limit}/lib)...")
    for lib in libs:
        print(f"  {lib}...")
        models = fetch_models(sort="downloads", limit=lib_limit, library=lib)
        ingest(models, f"lib:{lib}")

    # Strategy 4: By organization
    org_limit = min(limit, 200) if aggressive else min(limit, 50)
    orgs = HIGH_IMPACT_ORGS if aggressive else HIGH_IMPACT_ORGS[:20]
    print(f"\n[Strategy 4] By organization ({len(orgs)} orgs, {org_limit}/org)...")
    for org in orgs:
        print(f"  {org}...")
        models = fetch_models(sort="downloads", limit=org_limit, author=org)
        ingest(models, f"org:{org}")

    # Strategy 5: Papers With Code cross-reference (aggressive only)
    if aggressive:
        print(f"\n[Strategy 5] Papers With Code cross-reference...")
        pwc_names = fetch_pwc_model_names(limit=200)
        if pwc_names:
            print(f"  Got {len(pwc_names)} PWC model names, searching HF...")
            for name in pwc_names:
                models = fetch_models(sort="downloads", limit=5, search=name)
                ingest(models, f"pwc:{name}")
                # Lighter delay for search queries
                time.sleep(DELAY)

    # Strategy 6: GitHub ML repos cross-reference (aggressive only)
    if aggressive:
        print(f"\n[Strategy 6] GitHub ML repos cross-reference...")
        gh_names = fetch_github_ml_names()
        if gh_names:
            print(f"  Got {len(gh_names)} GitHub ML org/repo names, searching HF...")
            for name in gh_names:
                models = fetch_models(sort="downloads", limit=10, search=name)
                ingest(models, f"github:{name}")
                time.sleep(DELAY)

    # Strategy 7: Ollama known models (always, fast)
    print(f"\n[Strategy 7] Ollama known models...")
    for ollama_name, hf_id in OLLAMA_HF_MAP.items():
        if hf_id not in all_models:
            # Try to fetch from HF to get full metadata
            models = fetch_models(sort="downloads", limit=1, search=hf_id.split("/")[-1])
            for m in models:
                info = extract_model_info(m)
                if info and info["model_id"] == hf_id:
                    all_models[hf_id] = info
                    print(f"    +1 from Ollama: {hf_id}")
                    break
            else:
                # Add directly if HF search didn't find exact match
                all_models[hf_id] = {
                    "model_id": hf_id,
                    "author": hf_id.split("/")[0],
                    "downloads": 0,
                    "likes": 0,
                    "pipeline_tag": "text-generation",
                    "last_modified": "",
                    "library_name": "",
                    "tags": [],
                }
            time.sleep(0.3)

    print(f"\n{'='*60}")
    print(f"Discovery complete: {len(all_models)} unique models from {stats['queries']} queries")
    return all_models


# ── Multi-source helpers ─────────────────────────────────────────

def fetch_pwc_model_names(limit: int = 200) -> List[str]:
    """Fetch popular model names from Papers With Code API."""
    names = set()
    try:
        page = 1
        per_page = 50
        while len(names) < limit:
            url = f"{PWC_API}/models/?page={page}&items_per_page={per_page}"
            r = requests.get(url, timeout=TIMEOUT,
                             headers={"User-Agent": "CroviaTrust/1.0"})
            if r.status_code != 200:
                print(f"    PWC API error: {r.status_code}")
                break
            data = r.json()
            results = data.get("results", [])
            if not results:
                break
            for item in results:
                name = item.get("name", "").strip()
                if name and len(name) > 2:
                    names.add(name)
            page += 1
            time.sleep(1.0)  # PWC rate limit: be conservative
            if not data.get("next"):
                break
    except Exception as e:
        print(f"    PWC fetch error: {e}")
    return list(names)[:limit]


def fetch_github_ml_names() -> List[str]:
    """Fetch popular ML repo org names from GitHub to search on HF."""
    org_names = set()
    try:
        for query in GITHUB_ML_QUERIES:
            url = f"{GITHUB_API}/search/repositories?q={query}&sort=stars&order=desc&per_page=30"
            r = requests.get(url, timeout=TIMEOUT, headers={
                "User-Agent": "CroviaTrust/1.0",
                "Accept": "application/vnd.github.v3+json",
            })
            if r.status_code == 403:
                print(f"    GitHub rate limited, skipping remaining queries")
                break
            if r.status_code != 200:
                continue
            for repo in r.json().get("items", []):
                org = repo.get("full_name", "").split("/")[0]
                if org and org.lower() not in {"github", "actions", "dependabot"}:
                    org_names.add(org)
            time.sleep(2.0)  # GitHub unauthenticated: 10 req/min
    except Exception as e:
        print(f"    GitHub fetch error: {e}")
    return list(org_names)


def load_existing_targets(path: str) -> Set[str]:
    """Load existing target IDs from targets_unified.json or sent_discussions.jsonl."""
    ids = set()
    if not os.path.exists(path):
        return ids

    if path.endswith(".json"):
        with open(path, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    tid = item.get("target_id", item.get("repo_id", item.get("model_id", "")))
                    if tid:
                        if ":" in tid:
                            tid = tid.split(":")[-1]
                        ids.add(tid)
    elif path.endswith(".jsonl"):
        with open(path, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        rec = json.loads(line)
                        tid = rec.get("target_id", rec.get("repo_id", ""))
                        if tid:
                            if ":" in tid:
                                tid = tid.split(":")[-1]
                            ids.add(tid)
                    except json.JSONDecodeError:
                        pass
    return ids


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Discover new HF model targets (no auth)")
    parser.add_argument("--output", type=str, default="targets_unified.json")
    parser.add_argument("--existing", type=str, help="Path to existing targets file")
    parser.add_argument("--limit", type=int, default=500, help="Models per query (default 500)")
    parser.add_argument("--aggressive", action="store_true",
                        help="Use all tags/libs/orgs with higher limits (slower, more models)")
    parser.add_argument("--dry-run", action="store_true", help="Print stats only, don't save")
    args = parser.parse_args()

    print("=" * 60)
    print("CROVIA Target Discovery v3 — Multi-Source (no auth)")
    print(f"Mode: {'AGGRESSIVE' if args.aggressive else 'STANDARD'}")
    print(f"Limit per query: {args.limit}")
    print(f"Sources: HuggingFace" + (" + Papers With Code + GitHub" if args.aggressive else "") + " + Ollama")
    print("=" * 60)

    # Load existing
    existing_ids = set()
    if args.existing and os.path.exists(args.existing):
        existing_ids = load_existing_targets(args.existing)
        print(f"Existing targets: {len(existing_ids)}")

    # Also check sent_discussions.jsonl
    for jsonl_path in [
        os.path.join(os.path.dirname(args.output), "sent_discussions.jsonl"),
        os.path.join(os.path.dirname(__file__), "sent_discussions.jsonl"),
    ]:
        if os.path.exists(jsonl_path):
            more = load_existing_targets(jsonl_path)
            existing_ids.update(more)
            print(f"From {os.path.basename(jsonl_path)}: +{len(more)} IDs")

    # Discover
    discovered = discover(limit=args.limit, aggressive=args.aggressive)
    print(f"\nTotal unique models discovered: {len(discovered)}")

    # Find new ones
    new_models = {mid: info for mid, info in discovered.items() if mid not in existing_ids}
    print(f"NEW models (not in existing targets): {len(new_models)}")

    if args.dry_run:
        print("\n[DRY RUN] No changes written.")
        # Print top 20 new by downloads
        top_new = sorted(new_models.values(), key=lambda x: x["downloads"], reverse=True)[:20]
        if top_new:
            print("\nTop 20 new models by downloads:")
            for m in top_new:
                print(f"  {m['model_id']:50s} dl={m['downloads']:>12,} tag={m['pipeline_tag']}")
        return

    # Build unified target list
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Load existing output if present
    targets = []
    if os.path.exists(args.output):
        with open(args.output, "r") as f:
            raw = json.load(f)
            if isinstance(raw, list):
                for t in raw:
                    if isinstance(t, dict):
                        targets.append(t)
                    elif isinstance(t, str):
                        targets.append({"target_id": t, "repo_type": "model", "source": "legacy"})

    existing_in_output = set()
    for t in targets:
        tid = t.get("target_id", t.get("model_id", ""))
        if tid:
            existing_in_output.add(tid)

    added = 0
    for mid, info in new_models.items():
        if mid not in existing_in_output:
            targets.append({
                "target_id": mid,
                "tipo_target": "model",
                "repo_type": "model",
                "source": "discovery_v2",
                "discovered_at": now,
                "downloads": info["downloads"],
                "likes": info["likes"],
                "pipeline_tag": info["pipeline_tag"],
                "library_name": info.get("library_name", ""),
            })
            added += 1

    # Save
    with open(args.output, "w") as f:
        json.dump(targets, f, indent=2, ensure_ascii=False)

    print(f"\nAdded {added} new targets to {args.output}")
    print(f"Total targets in file: {len(targets)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
