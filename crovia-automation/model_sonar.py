#!/usr/bin/env python3
"""
Model Sonar v1 — Deep Provenance Chain Builder
================================================

Multi-signal analysis of AI model training provenance using PUBLIC data only.
No inference API needed. No authentication required.

Signals analyzed per model:
  1. README/model card — extract training dataset mentions
  2. HF tags — dataset:xxx tags reveal training sources
  3. Base model chain — detect finetune → base → training data lineage
  4. Config.json — model configs sometimes reference training data
  5. ArXiv citations — follow paper references to training details

Output: provenance_chain.json with full lineage per model.

Author: Crovia Engineering
"""

import json
import os
import re
import sys
import time
import hashlib
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict

HF_API = "https://huggingface.co/api/models"
HF_README_URL = "https://huggingface.co/{model_id}/raw/main/README.md"
HF_CONFIG_URL = "https://huggingface.co/{model_id}/raw/main/config.json"
TIMEOUT = 20
DELAY = 0.8

CACHE_DIR = os.environ.get("SONAR_CACHE_DIR", "/opt/crovia/volume/sonar/cache")
CACHE_TTL_DAYS = int(os.environ.get("SONAR_CACHE_TTL_DAYS", "7"))

# Known dataset patterns in model cards
DATASET_PATTERNS = [
    # HuggingFace dataset references
    r"(?:trained|fine-?tuned|pre-?trained)\s+(?:on|using|with)\s+[`\"]?([a-zA-Z0-9_\-/]+/[a-zA-Z0-9_\-]+)",
    r"(?:dataset|data):\s*[`\"]?([a-zA-Z0-9_\-/]+/[a-zA-Z0-9_\-]+)",
    r"\[([a-zA-Z0-9_\-/]+)\]\(https://huggingface\.co/datasets/",
    # Common dataset names
    r"(?:trained|fine-?tuned|pre-?trained)\s+(?:on|using|with)\s+(?:the\s+)?([A-Z][a-zA-Z0-9\-_]+(?:\s+[A-Z][a-zA-Z0-9\-_]+)*)\s+(?:dataset|corpus|data)",
    # Inline mentions
    r"(?:Wikipedia|BookCorpus|Common\s*Crawl|C4|The\s+Pile|LAION|OpenWebText|RedPajama|SlimPajama|FineWeb|Dolma|StarCoder|The\s+Stack)",
]

# Known base model patterns
BASE_MODEL_PATTERNS = [
    r"(?:based\s+on|fine-?tuned\s+(?:from|on)|built\s+(?:on|from)|derived\s+from)\s+[`\[\"]?([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-\.]+)",
    r"base[_\s]model[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-\.]+)",
]

# Well-known training datasets (canonical names)
KNOWN_DATASETS = {
    "wikipedia", "bookcorpus", "common crawl", "c4", "the pile", "laion",
    "openwebtext", "redpajama", "slimpajama", "fineweb", "dolma",
    "starcoder", "the stack", "roots", "oscar", "mc4", "cc-100",
    "wikitext", "squad", "glue", "superglue", "imagenet", "coco",
    "voc", "cifar", "mnist", "arxiv", "pubmed", "github code",
    "refinedweb", "falcon refinedweb", "ultrachat", "open-orca",
    "wizardlm", "alpaca", "sharegpt", "lmsys-chat", "openassistant",
}


@dataclass
class ProvenanceSignal:
    """A single provenance signal detected from a model."""
    signal_type: str     # readme, tag, config, base_model, arxiv
    source: str          # where we found it
    value: str           # what we found
    confidence: float    # 0-1
    raw_context: str     # surrounding text for verification


@dataclass
class ProvenanceChain:
    """Full provenance chain for a model."""
    model_id: str
    scanned_at: str
    signals: List[ProvenanceSignal]
    declared_datasets: List[str]
    inferred_datasets: List[str]
    base_model: Optional[str]
    base_model_chain: List[str]  # full chain: model → base → base's base...
    training_section_present: bool
    license: Optional[str]
    provenance_score: float  # 0-1, how much provenance info is available
    provenance_hash: str

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["signals"] = [asdict(s) for s in self.signals]
        return d


def _cache_path(model_id: str) -> str:
    """Return path to cache file for a model."""
    safe = model_id.replace("/", "__")
    return os.path.join(CACHE_DIR, safe + ".json")


def _cache_load(model_id: str) -> Optional[Dict]:
    """Load cached scan result if fresh enough."""
    path = _cache_path(model_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            d = json.load(f)
        scanned_at = d.get("scanned_at", "")
        if scanned_at:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(scanned_at.replace("Z", "+00:00"))).days
            if age <= CACHE_TTL_DAYS:
                return d
    except Exception:
        pass
    return None


def _cache_save(chain_dict: Dict) -> None:
    """Persist a scan result to disk cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(chain_dict["model_id"])
    try:
        with open(path, "w") as f:
            json.dump(chain_dict, f, ensure_ascii=False)
    except Exception:
        pass


class ModelSonar:
    """Deep provenance analysis using only public data."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "CroviaTrust/1.0 ModelSonar"})
        self._cache = {}

    def _get(self, url: str) -> Optional[requests.Response]:
        """GET with caching and rate limiting."""
        if url in self._cache:
            return self._cache[url]
        try:
            r = self.session.get(url, timeout=TIMEOUT)
            self._cache[url] = r
            time.sleep(DELAY)
            return r
        except Exception:
            return None

    def _fetch_model_meta(self, model_id: str) -> Optional[Dict]:
        """Fetch model metadata from HF API."""
        r = self._get(f"{HF_API}/{model_id}")
        if r and r.status_code == 200:
            return r.json()
        return None

    def _fetch_readme(self, model_id: str) -> Optional[str]:
        """Fetch model README/card."""
        url = HF_README_URL.format(model_id=model_id)
        r = self._get(url)
        if r and r.status_code == 200:
            return r.text
        return None

    def _fetch_config(self, model_id: str) -> Optional[Dict]:
        """Fetch model config.json."""
        url = HF_CONFIG_URL.format(model_id=model_id)
        r = self._get(url)
        if r and r.status_code == 200:
            try:
                return r.json()
            except Exception:
                pass
        return None

    # ── Signal extraction ──

    def _extract_tag_signals(self, meta: Dict) -> List[ProvenanceSignal]:
        """Extract provenance signals from HF tags."""
        signals = []
        tags = meta.get("tags", [])
        for tag in tags:
            if tag.startswith("dataset:"):
                ds = tag.split(":", 1)[1]
                signals.append(ProvenanceSignal(
                    signal_type="tag",
                    source="hf_api_tags",
                    value=ds,
                    confidence=0.95,
                    raw_context=f"Tag: {tag}",
                ))
            elif tag.startswith("base_model:"):
                bm = tag.split(":", 1)[1]
                signals.append(ProvenanceSignal(
                    signal_type="base_model_tag",
                    source="hf_api_tags",
                    value=bm,
                    confidence=0.99,
                    raw_context=f"Tag: {tag}",
                ))
        return signals

    def _extract_readme_signals(self, readme: str) -> List[ProvenanceSignal]:
        """Extract provenance signals from README text."""
        signals = []

        # Check for training section
        has_training = bool(re.search(
            r"(?i)(##?\s*(?:training|pre-?training|fine-?tuning|data))", readme
        ))

        # Extract dataset references
        found_datasets = set()
        for pattern in DATASET_PATTERNS:
            for match in re.finditer(pattern, readme, re.IGNORECASE):
                ds = match.group(1) if match.lastindex else match.group(0)
                ds = ds.strip("`\"'[]")
                if ds and len(ds) > 2 and ds.lower() not in found_datasets:
                    found_datasets.add(ds.lower())
                    # Get context
                    start = max(0, match.start() - 50)
                    end = min(len(readme), match.end() + 50)
                    context = readme[start:end].replace("\n", " ").strip()
                    signals.append(ProvenanceSignal(
                        signal_type="readme_dataset",
                        source="model_card",
                        value=ds,
                        confidence=0.8 if "/" in ds else 0.6,
                        raw_context=context[:200],
                    ))

        # Extract base model references
        for pattern in BASE_MODEL_PATTERNS:
            for match in re.finditer(pattern, readme, re.IGNORECASE):
                bm = match.group(1).strip("`\"'[]")
                if bm and "/" in bm:
                    start = max(0, match.start() - 50)
                    end = min(len(readme), match.end() + 50)
                    context = readme[start:end].replace("\n", " ").strip()
                    signals.append(ProvenanceSignal(
                        signal_type="readme_base_model",
                        source="model_card",
                        value=bm,
                        confidence=0.85,
                        raw_context=context[:200],
                    ))

        # Check for well-known dataset mentions
        readme_lower = readme.lower()
        for known in KNOWN_DATASETS:
            if known in readme_lower:
                # Find context
                idx = readme_lower.index(known)
                start = max(0, idx - 50)
                end = min(len(readme), idx + len(known) + 50)
                context = readme[start:end].replace("\n", " ").strip()
                signals.append(ProvenanceSignal(
                    signal_type="known_dataset",
                    source="model_card",
                    value=known,
                    confidence=0.7,
                    raw_context=context[:200],
                ))

        if has_training:
            signals.append(ProvenanceSignal(
                signal_type="training_section",
                source="model_card",
                value="present",
                confidence=1.0,
                raw_context="Training section found in README",
            ))

        return signals

    def _extract_config_signals(self, config: Dict) -> List[ProvenanceSignal]:
        """Extract provenance signals from config.json."""
        signals = []

        # Check for _name_or_path (often reveals base model)
        name_or_path = config.get("_name_or_path", "")
        if name_or_path and "/" in name_or_path:
            signals.append(ProvenanceSignal(
                signal_type="config_base",
                source="config.json",
                value=name_or_path,
                confidence=0.9,
                raw_context=f"_name_or_path: {name_or_path}",
            ))

        # Check for model_type
        model_type = config.get("model_type", "")
        if model_type:
            signals.append(ProvenanceSignal(
                signal_type="model_type",
                source="config.json",
                value=model_type,
                confidence=0.5,
                raw_context=f"model_type: {model_type}",
            ))

        return signals

    def _resolve_base_model_chain(self, model_id: str, max_depth: int = 5) -> List[str]:
        """Follow base model chain to build full lineage."""
        chain = []
        current = model_id
        visited = {model_id}

        for _ in range(max_depth):
            meta = self._fetch_model_meta(current)
            if not meta:
                break

            # Check tags for base_model
            base = None
            for tag in meta.get("tags", []):
                if tag.startswith("base_model:"):
                    base = tag.split(":", 1)[1]
                    break

            # Check cardData
            card_data = meta.get("cardData", {}) or {}
            if not base:
                base = card_data.get("base_model")
                if isinstance(base, list):
                    base = base[0] if base else None

            if not base or base in visited:
                break

            chain.append(base)
            visited.add(base)
            current = base

        return chain

    # ── Main scan ──

    def scan(self, model_id: str) -> ProvenanceChain:
        """Full provenance scan of a single model."""
        scanned_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        all_signals = []

        # 1. Fetch metadata
        meta = self._fetch_model_meta(model_id)
        if meta:
            all_signals.extend(self._extract_tag_signals(meta))

        # 2. Fetch and parse README
        readme = self._fetch_readme(model_id)
        has_training = False
        if readme:
            readme_signals = self._extract_readme_signals(readme)
            all_signals.extend(readme_signals)
            has_training = any(s.signal_type == "training_section" for s in readme_signals)

        # 3. Fetch and parse config.json
        config = self._fetch_config(model_id)
        if config:
            all_signals.extend(self._extract_config_signals(config))

        # 4. Resolve base model chain
        base_chain = self._resolve_base_model_chain(model_id)
        base_model = base_chain[0] if base_chain else None

        # If we have a base model, scan it too for inherited datasets
        inherited_datasets = []
        if base_model:
            base_readme = self._fetch_readme(base_model)
            if base_readme:
                base_signals = self._extract_readme_signals(base_readme)
                for s in base_signals:
                    if s.signal_type in ("readme_dataset", "known_dataset"):
                        s.signal_type = f"inherited_{s.signal_type}"
                        s.source = f"base_model:{base_model}"
                        s.confidence *= 0.8  # slightly lower confidence for inherited
                        all_signals.append(s)
                        inherited_datasets.append(s.value)

        # Compile results
        declared_ds = list(set(
            s.value for s in all_signals
            if s.signal_type in ("tag", "readme_dataset") and s.confidence >= 0.7
        ))
        inferred_ds = list(set(
            s.value for s in all_signals
            if s.signal_type in ("known_dataset", "inherited_readme_dataset", "inherited_known_dataset")
        ))

        license_val = None
        if meta:
            card_data = meta.get("cardData", {}) or {}
            license_val = card_data.get("license") or meta.get("license")
            if isinstance(license_val, list):
                license_val = license_val[0] if license_val else None

        # Calculate provenance score
        score = 0.0
        if has_training:
            score += 0.3
        if declared_ds:
            score += min(0.3, len(declared_ds) * 0.1)
        if license_val:
            score += 0.1
        if base_model:
            score += 0.1
        if inferred_ds:
            score += min(0.2, len(inferred_ds) * 0.05)
        score = min(1.0, score)

        # Build hash for integrity
        hash_input = json.dumps({
            "model_id": model_id,
            "scanned_at": scanned_at,
            "signals_count": len(all_signals),
            "declared": sorted(declared_ds),
            "inferred": sorted(inferred_ds),
        }, sort_keys=True)
        prov_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        return ProvenanceChain(
            model_id=model_id,
            scanned_at=scanned_at,
            signals=all_signals,
            declared_datasets=declared_ds,
            inferred_datasets=inferred_ds,
            base_model=base_model,
            base_model_chain=base_chain,
            training_section_present=has_training,
            license=license_val,
            provenance_score=score,
            provenance_hash=prov_hash,
        )

    def batch_scan(self, model_ids: List[str], progress: bool = True, use_cache: bool = True) -> List[ProvenanceChain]:
        """Scan multiple models, using disk cache when available."""
        results = []
        cached_count = 0
        for i, mid in enumerate(model_ids):
            if progress:
                print(f"  [{i+1}/{len(model_ids)}] {mid}...", end=" ", flush=True)
            try:
                if use_cache:
                    cached = _cache_load(mid)
                    if cached is not None:
                        signals = [ProvenanceSignal(**s) for s in cached.get("signals", [])]
                        chain = ProvenanceChain(
                            model_id=cached["model_id"],
                            scanned_at=cached["scanned_at"],
                            signals=signals,
                            declared_datasets=cached.get("declared_datasets", []),
                            inferred_datasets=cached.get("inferred_datasets", []),
                            base_model=cached.get("base_model"),
                            base_model_chain=cached.get("base_model_chain", []),
                            training_section_present=cached.get("training_section_present", False),
                            license=cached.get("license"),
                            provenance_score=cached.get("provenance_score", 0.0),
                            provenance_hash=cached.get("provenance_hash", ""),
                        )
                        results.append(chain)
                        cached_count += 1
                        if progress:
                            print(f"[CACHE] score={chain.provenance_score:.1%}")
                        continue
                chain = self.scan(mid)
                results.append(chain)
                if use_cache:
                    _cache_save(chain.to_dict())
                if progress:
                    ds_count = len(chain.declared_datasets) + len(chain.inferred_datasets)
                    base = f" -> {chain.base_model}" if chain.base_model else ""
                    print(f"score={chain.provenance_score:.1%} ds={ds_count}{base}")
            except Exception as e:
                if progress:
                    print(f"ERROR: {e}")
        if progress and cached_count:
            print(f"\n  (cache hits: {cached_count}/{len(model_ids)}, HTTP calls saved)")
        return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Model Sonar — Deep Provenance Chain Builder")
    parser.add_argument("--targets", type=str, help="Path to targets JSON file")
    parser.add_argument("--model", type=str, help="Single model ID to scan")
    parser.add_argument("--limit", type=int, default=100, help="Max models to scan (default 100)")
    parser.add_argument("--no-cache", action="store_true", help="Disable disk cache, always re-scan")
    parser.add_argument("--output", type=str, default="provenance_chains.json", help="Output file")
    parser.add_argument("--min-score", type=float, default=0.0, help="Only output models with score >= this")
    args = parser.parse_args()

    print("=" * 60)
    print("MODEL SONAR v1 — Deep Provenance Chain Builder")
    print("No auth needed. Public signals only.")
    print("=" * 60)

    use_cache = not args.no_cache
    sonar = ModelSonar()

    if args.model:
        # Single model scan
        print(f"\nScanning: {args.model}")
        chain = sonar.scan(args.model)
        print(f"\n{'='*60}")
        print(f"Model:     {chain.model_id}")
        print(f"Score:     {chain.provenance_score:.1%}")
        print(f"Training:  {'YES' if chain.training_section_present else 'NO'}")
        print(f"License:   {chain.license or 'Not declared'}")
        print(f"Base:      {chain.base_model or 'None detected'}")
        print(f"Chain:     {' -> '.join([chain.model_id] + chain.base_model_chain) if chain.base_model_chain else chain.model_id}")
        print(f"Declared:  {', '.join(chain.declared_datasets) or 'None'}")
        print(f"Inferred:  {', '.join(chain.inferred_datasets) or 'None'}")
        print(f"Signals:   {len(chain.signals)}")
        print(f"Hash:      {chain.provenance_hash[:16]}...")
        print(f"{'='*60}")

        with open(args.output, "w") as f:
            json.dump(chain.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"Saved to {args.output}")

    elif args.targets:
        # Batch scan from targets file
        with open(args.targets) as f:
            data = json.load(f)

        model_ids = []
        # Support both list format and wrapped object {"targets": [...]}
        items = data if isinstance(data, list) else data.get("targets", data.get("models", []))
        for item in items:
            if isinstance(item, dict):
                mid = item.get("target_id", item.get("model_id", ""))
                tipo = item.get("tipo_target", item.get("type", "model"))
                if mid and "/" in mid and tipo == "model":
                    model_ids.append(mid)
            elif isinstance(item, str) and "/" in item:
                model_ids.append(item)

        # Prioritize: uncached first, then oldest cached (so new models from daily pipeline get scanned first)
        if len(model_ids) > args.limit:
            import os as _os
            uncached = [m for m in model_ids if not _os.path.exists(_cache_path(m))]
            cached_existing = [m for m in model_ids if _os.path.exists(_cache_path(m))]
            # Sort cached by mtime ascending (oldest first = due for refresh)
            cached_existing.sort(key=lambda m: _os.path.getmtime(_cache_path(m)))
            prioritized = uncached + cached_existing
            model_ids = prioritized[:args.limit]
            print(f"  Priority: {min(len(uncached), args.limit)} uncached + {max(0, args.limit-len(uncached))} oldest cached")

        print(f"\nScanning {len(model_ids)} models... (cache={'ON' if use_cache else 'OFF'}, dir={CACHE_DIR})")
        results = sonar.batch_scan(model_ids, use_cache=use_cache)

        # Filter by min score
        if args.min_score > 0:
            results = [r for r in results if r.provenance_score >= args.min_score]

        # Summary
        print(f"\n{'='*60}")
        print(f"SONAR SUMMARY")
        print(f"{'='*60}")
        print(f"Models scanned:    {len(model_ids)}")
        print(f"With training:     {sum(1 for r in results if r.training_section_present)}")
        print(f"With datasets:     {sum(1 for r in results if r.declared_datasets)}")
        print(f"With base model:   {sum(1 for r in results if r.base_model)}")
        print(f"With license:      {sum(1 for r in results if r.license)}")
        avg_score = sum(r.provenance_score for r in results) / max(len(results), 1)
        print(f"Avg prov. score:   {avg_score:.1%}")

        # Top transparent
        top = sorted(results, key=lambda r: r.provenance_score, reverse=True)[:10]
        print(f"\nTop 10 most transparent:")
        for r in top:
            print(f"  {r.provenance_score:.0%} {r.model_id} ds={len(r.declared_datasets)}")

        # Bottom opaque
        bottom = sorted(results, key=lambda r: r.provenance_score)[:10]
        print(f"\nTop 10 most opaque:")
        for r in bottom:
            print(f"  {r.provenance_score:.0%} {r.model_id}")

        # Save
        output = {
            "schema": "crovia.sonar.provenance_scan.v1",
            "scanned_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "models_scanned": len(model_ids),
            "summary": {
                "with_training_section": sum(1 for r in results if r.training_section_present),
                "with_declared_datasets": sum(1 for r in results if r.declared_datasets),
                "with_base_model": sum(1 for r in results if r.base_model),
                "with_license": sum(1 for r in results if r.license),
                "avg_provenance_score": round(avg_score, 3),
            },
            "chains": [r.to_dict() for r in results],
        }

        with open(args.output, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\nSaved {len(results)} chains to {args.output}")

    else:
        # Demo: scan well-known models
        demo_models = [
            "meta-llama/Llama-3.1-8B-Instruct",
            "mistralai/Mistral-7B-v0.3",
            "google/gemma-2-9b",
            "Qwen/Qwen2.5-7B",
            "microsoft/Phi-3-mini-4k-instruct",
            "stabilityai/stable-diffusion-xl-base-1.0",
            "sentence-transformers/all-MiniLM-L6-v2",
            "openai/clip-vit-base-patch32",
            "bigscience/bloom",
            "EleutherAI/gpt-neox-20b",
        ]
        print(f"\nDemo scan: {len(demo_models)} well-known models")
        results = sonar.batch_scan(demo_models)

        for r in results:
            print(f"\n  {r.model_id}")
            print(f"    Score: {r.provenance_score:.0%} | Training: {'Y' if r.training_section_present else 'N'} | Base: {r.base_model or '-'}")
            if r.declared_datasets:
                print(f"    Declared: {', '.join(r.declared_datasets[:5])}")
            if r.inferred_datasets:
                print(f"    Inferred: {', '.join(r.inferred_datasets[:5])}")


if __name__ == "__main__":
    main()
