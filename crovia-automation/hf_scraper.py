#!/usr/bin/env python3
"""
hf_scraper.py — HF-independent model card fetcher

Fetches model metadata and card text via PUBLIC HTTP endpoints.
No HF token, no HfApi, no authentication required.

Replaces:
  - HfApi().model_info(model_id)
  - ModelCard.load(model_id)

Public endpoints used:
  - https://huggingface.co/api/models/{model_id}  (JSON metadata)
  - https://huggingface.co/{model_id}/raw/main/README.md  (raw card text)
"""

import json
import re
import time
import hashlib
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

HF_API_BASE = "https://huggingface.co/api/models"
HF_RAW_BASE = "https://huggingface.co"
REQUEST_TIMEOUT = 15
RATE_LIMIT_DELAY = 1.0  # seconds between requests
USER_AGENT = "CroviaTrust-Observatory/1.0 (https://croviatrust.com)"


# ═══════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════

@dataclass
class ModelMetadata:
    """Parsed model metadata from public HF API."""
    model_id: str
    author: str
    license: str
    datasets: List[str]
    tags: List[str]
    pipeline_tag: str
    downloads: int
    likes: int
    created_at: str
    last_modified: str
    card_text: str
    fetch_method: str  # "api+card", "api_only", "card_only", "cached"
    fetched_at: str
    raw_api: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════
# Scraper
# ═══════════════════════════════════════════════════════════════

class HFScraper:
    """
    Fetches HuggingFace model data via public HTTP endpoints.
    No authentication required.
    """

    def __init__(self, cache_dir: Optional[str] = None, delay: float = RATE_LIMIT_DELAY):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.delay = delay
        self.cache: Dict[str, ModelMetadata] = {}
        self._last_request = 0.0

    def _rate_limit(self):
        """Respect rate limits."""
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.time()

    def fetch_api_metadata(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch model metadata from public API.
        GET https://huggingface.co/api/models/{model_id}
        """
        self._rate_limit()
        url = f"{HF_API_BASE}/{model_id}"
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401 or resp.status_code == 403:
                # Gated model — metadata not available without auth
                return None
            elif resp.status_code == 404:
                return None
            else:
                return None
        except Exception:
            return None

    def fetch_card_text(self, model_id: str) -> Optional[str]:
        """
        Fetch raw model card (README.md) via public URL.
        Tries multiple endpoints for gated/non-gated models.
        """
        # Try 1: raw endpoint (works for non-gated models)
        self._rate_limit()
        for path in [
            f"{HF_RAW_BASE}/{model_id}/raw/main/README.md",
            f"{HF_RAW_BASE}/{model_id}/resolve/main/README.md",
        ]:
            try:
                resp = self.session.get(path, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                if resp.status_code == 200 and len(resp.text) > 20:
                    return resp.text
            except Exception:
                pass

        # Try 2: parse card from API cardData field (has YAML metadata at minimum)
        # Already handled by fetch_api_metadata, so return None here
        return None

    def fetch_model(self, model_id: str, use_cache: bool = True) -> ModelMetadata:
        """
        Fetch complete model data: API metadata + card text.
        Falls back gracefully if either source fails.
        """
        if use_cache and model_id in self.cache:
            cached = self.cache[model_id]
            cached.fetch_method = "cached"
            return cached

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Fetch API metadata
        api_data = self.fetch_api_metadata(model_id)

        # Fetch card text
        card_text = self.fetch_card_text(model_id)

        # Parse API metadata
        if api_data:
            author = api_data.get("author", "")
            card_data = api_data.get("cardData", {}) or {}
            license_val = card_data.get("license") or api_data.get("license", "")
            datasets = card_data.get("datasets", []) or []
            tags = api_data.get("tags", []) or []
            pipeline_tag = api_data.get("pipeline_tag", "") or card_data.get("pipeline_tag", "")
            downloads = api_data.get("downloads", 0) or 0
            likes = api_data.get("likes", 0) or 0
            created_at = api_data.get("createdAt", "")
            last_modified = api_data.get("lastModified", "")
        else:
            # Fallback: parse YAML front matter from card text
            author = model_id.split("/")[0] if "/" in model_id else ""
            license_val = ""
            datasets = []
            tags = []
            pipeline_tag = ""
            downloads = 0
            likes = 0
            created_at = ""
            last_modified = ""

            if card_text:
                yaml_data = self._parse_yaml_front_matter(card_text)
                license_val = yaml_data.get("license", "")
                datasets = yaml_data.get("datasets", []) or []
                tags = yaml_data.get("tags", []) or []
                pipeline_tag = yaml_data.get("pipeline_tag", "")

        # Determine fetch method
        if api_data and card_text:
            method = "api+card"
        elif api_data:
            method = "api_only"
        elif card_text:
            method = "card_only"
        else:
            method = "failed"

        metadata = ModelMetadata(
            model_id=model_id,
            author=author,
            license=license_val,
            datasets=datasets if isinstance(datasets, list) else [datasets],
            tags=tags,
            pipeline_tag=pipeline_tag,
            downloads=downloads,
            likes=likes,
            created_at=created_at,
            last_modified=last_modified,
            card_text=card_text or "",
            fetch_method=method,
            fetched_at=now,
            raw_api=api_data or {},
        )

        self.cache[model_id] = metadata
        return metadata

    def fetch_batch(self, model_ids: List[str], progress: bool = True) -> List[ModelMetadata]:
        """Fetch metadata for a batch of models."""
        results = []
        total = len(model_ids)
        for i, mid in enumerate(model_ids):
            if progress:
                print(f"  [{i+1}/{total}] {mid} ...", end=" ", flush=True)
            meta = self.fetch_model(mid)
            results.append(meta)
            if progress:
                print(f"{meta.fetch_method} ({len(meta.datasets)} datasets)")
        return results

    def _parse_yaml_front_matter(self, text: str) -> Dict[str, Any]:
        """Parse YAML front matter from model card text."""
        match = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
        if not match:
            return {}

        yaml_text = match.group(1)
        result = {}

        # Simple YAML parsing (no pyyaml dependency)
        current_key = None
        current_list = None

        for line in yaml_text.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Key: value
            kv_match = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)', line)
            if kv_match and not line.startswith(" ") and not line.startswith("\t"):
                current_key = kv_match.group(1)
                val = kv_match.group(2).strip()
                if val:
                    # Remove quotes
                    val = val.strip("'\"")
                    result[current_key] = val
                else:
                    result[current_key] = []
                    current_list = current_key
                continue

            # List item
            list_match = re.match(r'^\s*-\s+(.*)', line)
            if list_match and current_list:
                val = list_match.group(1).strip().strip("'\"")
                if isinstance(result.get(current_list), list):
                    result[current_list].append(val)

        return result


# ═══════════════════════════════════════════════════════════════
# Oracle-compatible analysis (drop-in replacement)
# ═══════════════════════════════════════════════════════════════

NECESSITY_CANON = {
    "NEC#1": {"name": "Missing data provenance", "description": "No training dataset declaration", "severity": 75, "eu_ai_act": "Article 10(2)"},
    "NEC#2": {"name": "Missing license attribution", "description": "No license or unclear terms", "severity": 80, "eu_ai_act": "Article 10(5)"},
    "NEC#7": {"name": "Missing usage scope", "description": "No intended use cases declared", "severity": 45, "eu_ai_act": "Article 13(3)"},
    "NEC#10": {"name": "Missing temporal validity", "description": "No version or date information", "severity": 40, "eu_ai_act": "Article 12(1)"},
    "NEC#13": {"name": "Missing accountable entity", "description": "No responsible organization declared", "severity": 70, "eu_ai_act": "Article 16"},
}


def analyze_model_offline(meta: ModelMetadata) -> Dict[str, Any]:
    """
    Analyze a model for NEC# violations using scraped metadata.
    Drop-in replacement for crovia.oracle.analyze_model().
    """
    violations = []

    if not meta.datasets:
        violations.append("NEC#1")
    if not meta.license:
        violations.append("NEC#2")

    has_use = any("task" in t.lower() or "use" in t.lower() for t in meta.tags)
    if not has_use and not meta.pipeline_tag:
        violations.append("NEC#7")
    if not meta.created_at:
        violations.append("NEC#10")
    if not meta.author:
        violations.append("NEC#13")

    total_severity = sum(NECESSITY_CANON.get(v, {}).get("severity", 30) for v in violations)
    score = max(0, min(100, 100 - int(total_severity * 0.15)))

    if score >= 90:
        badge = "GOLD"
    elif score >= 75:
        badge = "SILVER"
    elif score >= 60:
        badge = "BRONZE"
    else:
        badge = "UNVERIFIED"

    evidence_data = f"{meta.model_id}:{score}:{','.join(sorted(violations))}"
    evidence_hash = hashlib.sha256(evidence_data.encode()).hexdigest()[:16]

    return {
        "model_id": meta.model_id,
        "score": score,
        "badge": badge,
        "violations": violations,
        "violation_details": [
            {
                "code": v,
                "name": NECESSITY_CANON[v]["name"],
                "description": NECESSITY_CANON[v]["description"],
                "severity": NECESSITY_CANON[v]["severity"],
                "eu_ai_act": NECESSITY_CANON[v]["eu_ai_act"],
            }
            for v in violations
        ],
        "metadata": {
            "author": meta.author or "Unknown",
            "license": meta.license or "Not declared",
            "datasets": meta.datasets,
            "downloads": meta.downloads,
            "likes": meta.likes,
        },
        "evidence": {
            "hash": evidence_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engine_version": "2.1.0-offline",
            "fetch_method": meta.fetch_method,
        },
    }


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CROVIA HF Scraper — no API token needed")
    parser.add_argument("model_id", nargs="?", help="Model ID to fetch (e.g. meta-llama/Llama-3.1-8B)")
    parser.add_argument("--batch", type=str, help="JSONL file with target_id fields")
    parser.add_argument("--output", type=str, help="Output JSON file")
    parser.add_argument("--analyze", action="store_true", help="Run NEC# analysis")
    args = parser.parse_args()

    scraper = HFScraper()

    print("=" * 60)
    print("CROVIA HF Scraper (no token required)")
    print("=" * 60)

    if args.model_id:
        # Single model
        meta = scraper.fetch_model(args.model_id)
        print(f"\nModel: {meta.model_id}")
        print(f"Method: {meta.fetch_method}")
        print(f"Author: {meta.author}")
        print(f"License: {meta.license}")
        print(f"Datasets: {meta.datasets}")
        print(f"Tags: {meta.tags[:5]}")
        print(f"Downloads: {meta.downloads}")
        print(f"Card length: {len(meta.card_text)} chars")

        if args.analyze:
            result = analyze_model_offline(meta)
            print(f"\nScore: {result['score']} ({result['badge']})")
            print(f"Violations: {result['violations']}")
            print(f"Evidence hash: {result['evidence']['hash']}")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(meta.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"\nSaved to {args.output}")

    elif args.batch:
        # Batch mode
        model_ids = []
        with open(args.batch, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    tid = rec.get("target_id", rec.get("repo_id", rec.get("model_id", "")))
                    # Clean target_id format "hf:model:org/name" -> "org/name"
                    if tid.startswith("hf:model:"):
                        tid = tid[len("hf:model:"):]
                    if tid and "/" in tid and tid not in model_ids:
                        model_ids.append(tid)

        print(f"\nTargets: {len(model_ids)}")
        results = scraper.fetch_batch(model_ids)

        stats = {"api+card": 0, "api_only": 0, "card_only": 0, "failed": 0, "cached": 0}
        for r in results:
            stats[r.fetch_method] = stats.get(r.fetch_method, 0) + 1

        print(f"\nResults: {stats}")

        if args.output:
            output = [r.to_dict() for r in results]
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"Saved to {args.output}")

        if args.analyze:
            analyses = [analyze_model_offline(r) for r in results if r.fetch_method != "failed"]
            if args.output:
                analysis_path = args.output.replace(".json", "_analysis.json")
                with open(analysis_path, "w", encoding="utf-8") as f:
                    json.dump(analyses, f, indent=2, ensure_ascii=False)
                print(f"Analysis saved to {analysis_path}")

    else:
        print("\nUsage:")
        print("  python hf_scraper.py meta-llama/Llama-3.1-8B --analyze")
        print("  python hf_scraper.py --batch sent_discussions.jsonl --output scraped.json --analyze")

    print("=" * 60)
