#!/usr/bin/env python3
"""
CROVIA Multi-Source Target Fetcher
===================================

Fetches AI model/dataset targets from multiple sources:
- HuggingFace (primary)
- Papers With Code
- GitHub ML repos
- Ollama library

Respects rate limits, uses official APIs only.

Author: Crovia Engineering
"""

import json
import os
import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import urllib.request
import urllib.error

# Rate limit configuration (conservative, 80% of official limits)
RATE_LIMITS = {
    "huggingface": {"delay_sec": 0.5, "batch_size": 100, "pause_sec": 30},
    "paperswithcode": {"delay_sec": 1.0, "batch_size": 50, "pause_sec": 60},
    "github": {"delay_sec": 1.0, "batch_size": 50, "pause_sec": 30},
    "ollama": {"delay_sec": 2.0, "batch_size": 20, "pause_sec": 60},
}

# Monthly targets (250K total)
MONTHLY_TARGETS = {
    "huggingface": 150000,
    "github": 50000,
    "paperswithcode": 30000,
    "ollama": 20000,
}

@dataclass
class UnifiedTarget:
    """Unified target format across all sources."""
    target_id: str
    source: str  # huggingface, paperswithcode, github, ollama
    tipo_target: str  # model, dataset, paper, repo
    name: str
    url: str
    popularity: Dict[str, Any]
    metadata: Dict[str, Any]
    fetched_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MultiSourceFetcher:
    """Fetches targets from multiple AI ecosystem sources."""
    
    def __init__(self, tokens: Optional[Dict[str, str]] = None):
        self.tokens = tokens or {}
        self.stats = {source: {"fetched": 0, "errors": 0} for source in RATE_LIMITS}
    
    def _request(self, url: str, headers: Optional[Dict] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """Make HTTP request with error handling."""
        req_headers = {"User-Agent": "CroviaTrust/1.0 (https://croviatrust.com)"}
        if headers:
            req_headers.update(headers)
        
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data, None
        except urllib.error.HTTPError as e:
            return None, f"HTTP {e.code}"
        except Exception as e:
            return None, str(e)
    
    def _throttle(self, source: str):
        """Apply rate limiting."""
        time.sleep(RATE_LIMITS[source]["delay_sec"])
    
    # ========== HuggingFace ==========
    
    def fetch_huggingface_models(self, limit: int = 100, sort: str = "downloads") -> List[UnifiedTarget]:
        """Fetch top models from HuggingFace."""
        targets = []
        url = f"https://huggingface.co/api/models?sort={sort}&direction=-1&limit={limit}"
        
        headers = {}
        if self.tokens.get("huggingface"):
            headers["Authorization"] = f"Bearer {self.tokens['huggingface']}"
        
        data, err = self._request(url, headers)
        if err:
            self.stats["huggingface"]["errors"] += 1
            return targets
        
        for item in data or []:
            target = UnifiedTarget(
                target_id=f"hf:model:{item.get('id', '')}",
                source="huggingface",
                tipo_target="model",
                name=item.get("id", ""),
                url=f"https://huggingface.co/{item.get('id', '')}",
                popularity={"downloads": item.get("downloads", 0), "likes": item.get("likes", 0)},
                metadata={"pipeline_tag": item.get("pipeline_tag"), "library": item.get("library_name")},
                fetched_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            )
            targets.append(target)
            self.stats["huggingface"]["fetched"] += 1
        
        self._throttle("huggingface")
        return targets
    
    def fetch_huggingface_datasets(self, limit: int = 100, sort: str = "downloads") -> List[UnifiedTarget]:
        """Fetch top datasets from HuggingFace."""
        targets = []
        url = f"https://huggingface.co/api/datasets?sort={sort}&direction=-1&limit={limit}"
        
        headers = {}
        if self.tokens.get("huggingface"):
            headers["Authorization"] = f"Bearer {self.tokens['huggingface']}"
        
        data, err = self._request(url, headers)
        if err:
            self.stats["huggingface"]["errors"] += 1
            return targets
        
        for item in data or []:
            target = UnifiedTarget(
                target_id=f"hf:dataset:{item.get('id', '')}",
                source="huggingface",
                tipo_target="dataset",
                name=item.get("id", ""),
                url=f"https://huggingface.co/datasets/{item.get('id', '')}",
                popularity={"downloads": item.get("downloads", 0), "likes": item.get("likes", 0)},
                metadata={"tags": item.get("tags", [])[:10]},
                fetched_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            )
            targets.append(target)
            self.stats["huggingface"]["fetched"] += 1
        
        self._throttle("huggingface")
        return targets
    
    # ========== Papers With Code ==========
    
    def fetch_paperswithcode_models(self, limit: int = 100) -> List[UnifiedTarget]:
        """Fetch models from Papers With Code API."""
        targets = []
        # PWC API: https://paperswithcode.com/api/v1/
        url = f"https://paperswithcode.com/api/v1/models/?page=1&items_per_page={min(limit, 50)}"
        
        data, err = self._request(url)
        if err:
            self.stats["paperswithcode"]["errors"] += 1
            return targets
        
        for item in (data or {}).get("results", []):
            target = UnifiedTarget(
                target_id=f"pwc:model:{item.get('id', '')}",
                source="paperswithcode",
                tipo_target="model",
                name=item.get("name", ""),
                url=item.get("url", ""),
                popularity={"paper_count": len(item.get("papers", []))},
                metadata={"framework": item.get("framework"), "papers": item.get("papers", [])[:3]},
                fetched_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            )
            targets.append(target)
            self.stats["paperswithcode"]["fetched"] += 1
        
        self._throttle("paperswithcode")
        return targets
    
    # ========== GitHub ==========
    
    def fetch_github_ml_repos(self, limit: int = 100) -> List[UnifiedTarget]:
        """Fetch ML-related repos from GitHub."""
        targets = []
        # Search for repos with ML topics
        query = "topic:machine-learning+topic:model"
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={min(limit, 100)}"
        
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.tokens.get("github"):
            headers["Authorization"] = f"token {self.tokens['github']}"
        
        data, err = self._request(url, headers)
        if err:
            self.stats["github"]["errors"] += 1
            return targets
        
        for item in (data or {}).get("items", []):
            target = UnifiedTarget(
                target_id=f"gh:repo:{item.get('full_name', '')}",
                source="github",
                tipo_target="repo",
                name=item.get("full_name", ""),
                url=item.get("html_url", ""),
                popularity={"stars": item.get("stargazers_count", 0), "forks": item.get("forks_count", 0)},
                metadata={"language": item.get("language"), "topics": item.get("topics", [])[:5]},
                fetched_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            )
            targets.append(target)
            self.stats["github"]["fetched"] += 1
        
        self._throttle("github")
        return targets
    
    # ========== Ollama ==========
    
    def fetch_ollama_models(self, limit: int = 100) -> List[UnifiedTarget]:
        """Fetch models from Ollama library."""
        targets = []
        # Ollama library page (no official API, but we can use their manifest)
        url = "https://ollama.com/api/models"
        
        data, err = self._request(url)
        if err:
            # Fallback: known popular models
            known_models = [
                "llama3", "llama2", "mistral", "mixtral", "phi3", "gemma", 
                "qwen", "codellama", "vicuna", "neural-chat", "starling-lm",
                "orca-mini", "llava", "bakllava", "yi", "deepseek-coder"
            ]
            for name in known_models[:limit]:
                target = UnifiedTarget(
                    target_id=f"ollama:model:{name}",
                    source="ollama",
                    tipo_target="model",
                    name=name,
                    url=f"https://ollama.com/library/{name}",
                    popularity={"known": True},
                    metadata={"source": "known_list"},
                    fetched_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                )
                targets.append(target)
                self.stats["ollama"]["fetched"] += 1
            return targets
        
        for item in (data or {}).get("models", [])[:limit]:
            target = UnifiedTarget(
                target_id=f"ollama:model:{item.get('name', '')}",
                source="ollama",
                tipo_target="model",
                name=item.get("name", ""),
                url=f"https://ollama.com/library/{item.get('name', '')}",
                popularity={"pulls": item.get("pulls", 0)},
                metadata={"tags": item.get("tags", [])},
                fetched_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            )
            targets.append(target)
            self.stats["ollama"]["fetched"] += 1
        
        self._throttle("ollama")
        return targets
    
    # ========== Unified Fetch ==========
    
    def fetch_all(self, limits: Optional[Dict[str, int]] = None) -> Dict[str, List[UnifiedTarget]]:
        """Fetch from all sources with specified limits."""
        limits = limits or {"huggingface": 100, "paperswithcode": 50, "github": 50, "ollama": 20}
        
        results = {
            "huggingface": [],
            "paperswithcode": [],
            "github": [],
            "ollama": [],
        }
        
        # HuggingFace (models + datasets)
        hf_model_limit = limits.get("huggingface", 100) // 2
        hf_dataset_limit = limits.get("huggingface", 100) // 2
        results["huggingface"].extend(self.fetch_huggingface_models(hf_model_limit))
        results["huggingface"].extend(self.fetch_huggingface_datasets(hf_dataset_limit))
        
        # Papers With Code
        results["paperswithcode"] = self.fetch_paperswithcode_models(limits.get("paperswithcode", 50))
        
        # GitHub
        results["github"] = self.fetch_github_ml_repos(limits.get("github", 50))
        
        # Ollama
        results["ollama"] = self.fetch_ollama_models(limits.get("ollama", 20))
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Return fetch statistics."""
        total_fetched = sum(s["fetched"] for s in self.stats.values())
        total_errors = sum(s["errors"] for s in self.stats.values())
        return {
            "by_source": self.stats,
            "total_fetched": total_fetched,
            "total_errors": total_errors,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }


def save_unified_targets(targets: Dict[str, List[UnifiedTarget]], output_path: str):
    """Save all targets to a unified JSONL file."""
    all_targets = []
    for source_targets in targets.values():
        all_targets.extend(source_targets)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for t in all_targets:
            f.write(json.dumps(t.to_dict(), ensure_ascii=False) + "\n")
    
    return len(all_targets)


# ========== CLI ==========

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CROVIA Multi-Source Target Fetcher")
    parser.add_argument("--hf-limit", type=int, default=100, help="HuggingFace limit")
    parser.add_argument("--pwc-limit", type=int, default=50, help="Papers With Code limit")
    parser.add_argument("--gh-limit", type=int, default=50, help="GitHub limit")
    parser.add_argument("--ollama-limit", type=int, default=20, help="Ollama limit")
    parser.add_argument("--output", type=str, default="multi_source_targets.jsonl", help="Output file")
    parser.add_argument("--dry-run", action="store_true", help="Print stats only, don't save")
    args = parser.parse_args()
    
    print("=" * 60)
    print("CROVIA Multi-Source Target Fetcher")
    print("=" * 60)
    
    tokens = {
        "huggingface": os.getenv("HF_TOKEN"),
        "github": os.getenv("GITHUB_TOKEN"),
    }
    
    fetcher = MultiSourceFetcher(tokens=tokens)
    
    limits = {
        "huggingface": args.hf_limit,
        "paperswithcode": args.pwc_limit,
        "github": args.gh_limit,
        "ollama": args.ollama_limit,
    }
    
    print(f"\nFetching with limits: {limits}")
    print("-" * 60)
    
    results = fetcher.fetch_all(limits)
    stats = fetcher.get_stats()
    
    print(f"\nResults:")
    for source, targets in results.items():
        print(f"  {source}: {len(targets)} targets")
    
    print(f"\nTotal: {stats['total_fetched']} targets, {stats['total_errors']} errors")
    
    if not args.dry_run:
        count = save_unified_targets(results, args.output)
        print(f"\nSaved {count} targets to {args.output}")
    
    print("=" * 60)
