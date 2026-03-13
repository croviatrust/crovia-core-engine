#!/usr/bin/env python3
"""
CROVIA Model Card Analyzer
==========================

Fetches and analyzes REAL model card content from HuggingFace.
No hardcoded values - genuine observation of what's present or absent.

Checks:
1. Training data section
2. Dataset references
3. License clarity
4. Evaluation metrics
5. Limitations/risks
6. Intended use
7. Carbon footprint
8. Languages
9. Author/contact
10. Bias/fairness

Author: Crovia Engineering
"""

import re
import json
import os
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import urllib.request
import urllib.error
import time

@dataclass
class ModelCardAnalysis:
    """Results of analyzing a model card."""
    target_id: str
    repo_type: str  # model or dataset
    
    # Raw content
    readme_found: bool
    readme_length: int
    
    # Section detection (REAL checks)
    has_training_section: bool
    has_dataset_references: bool
    has_evaluation_section: bool
    has_limitations_section: bool
    has_intended_use_section: bool
    has_bias_section: bool
    has_environmental_section: bool
    
    # Metadata checks
    has_license: bool
    license_value: Optional[str]
    has_languages: bool
    languages: List[str]
    has_tags: bool
    tags_count: int
    has_model_index: bool  # Evaluation metrics
    
    # Author/contact
    has_author: bool
    author: Optional[str]
    
    # Computed score (0-100)
    completeness_score: int
    missing_sections: List[str]
    
    # Metadata
    analyzed_at: str
    analysis_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ModelCardAnalyzer:
    """Fetches and analyzes model cards from HuggingFace."""
    
    # Section patterns to detect
    SECTION_PATTERNS = {
        "training": [
            r"##\s*train",
            r"##\s*data",
            r"training\s*data",
            r"trained\s*on",
            r"training\s*procedure",
            r"training\s*details",
        ],
        "dataset": [
            r"dataset",
            r"corpus",
            r"trained\s*on\s*\[",
            r"data\s*sources",
        ],
        "evaluation": [
            r"##\s*eval",
            r"##\s*results",
            r"##\s*performance",
            r"##\s*benchmark",
            r"accuracy",
            r"f1[\s\-]score",
            r"bleu",
            r"rouge",
        ],
        "limitations": [
            r"##\s*limit",
            r"##\s*risk",
            r"##\s*warning",
            r"##\s*caveat",
            r"out[\s\-]of[\s\-]scope",
            r"should\s*not\s*be\s*used",
        ],
        "intended_use": [
            r"##\s*intended",
            r"##\s*use",
            r"##\s*application",
            r"designed\s*for",
            r"meant\s*for",
        ],
        "bias": [
            r"##\s*bias",
            r"##\s*fair",
            r"##\s*ethic",
            r"demographic",
            r"stereotype",
        ],
        "environmental": [
            r"##\s*environment",
            r"##\s*carbon",
            r"##\s*co2",
            r"##\s*energy",
            r"gpu[\s\-]hours",
        ],
    }
    
    def __init__(self, hf_token: Optional[str] = None):
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        self.cache: Dict[str, ModelCardAnalysis] = {}
        self.stats = {"analyzed": 0, "errors": 0, "cached": 0}
    
    def _fetch_readme(self, repo_id: str, repo_type: str = "model") -> Tuple[Optional[str], Optional[Dict]]:
        """Fetch README.md content from HuggingFace."""
        if repo_type == "dataset":
            readme_url = f"https://huggingface.co/datasets/{repo_id}/raw/main/README.md"
            api_url = f"https://huggingface.co/api/datasets/{repo_id}"
        else:
            readme_url = f"https://huggingface.co/{repo_id}/raw/main/README.md"
            api_url = f"https://huggingface.co/api/models/{repo_id}"
        
        headers = {"User-Agent": "CroviaTrust/1.0"}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        
        readme_content = None
        api_data = None
        
        # Fetch README
        try:
            req = urllib.request.Request(readme_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                readme_content = resp.read().decode("utf-8", errors="replace")
        except:
            pass
        
        # Fetch API metadata
        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                api_data = json.loads(resp.read().decode("utf-8"))
        except:
            pass
        
        return readme_content, api_data
    
    def _detect_section(self, content: str, section_type: str) -> bool:
        """Detect if a section type exists in the content."""
        if not content:
            return False
        
        patterns = self.SECTION_PATTERNS.get(section_type, [])
        content_lower = content.lower()
        
        for pattern in patterns:
            if re.search(pattern, content_lower):
                return True
        return False
    
    def _extract_datasets(self, content: str) -> List[str]:
        """Extract dataset references from content."""
        if not content:
            return []
        
        datasets = []
        # Look for HuggingFace dataset links
        hf_pattern = r"huggingface\.co/datasets/([^\s\)\"\']+)"
        datasets.extend(re.findall(hf_pattern, content))
        
        # Look for common dataset names
        known_datasets = [
            "wikipedia", "common crawl", "c4", "pile", "laion", 
            "imagenet", "coco", "squad", "glue", "superglue",
            "wmt", "openwebtext", "bookcorpus", "cc-100"
        ]
        content_lower = content.lower()
        for ds in known_datasets:
            if ds in content_lower:
                datasets.append(ds)
        
        return list(set(datasets))
    
    def analyze(self, repo_id: str, repo_type: str = "model") -> ModelCardAnalysis:
        """Analyze a model/dataset card and return genuine observations."""
        cache_key = f"{repo_type}:{repo_id}"
        
        if cache_key in self.cache:
            self.stats["cached"] += 1
            return self.cache[cache_key]
        
        readme_content, api_data = self._fetch_readme(repo_id, repo_type)
        
        # Initialize with defaults
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Analyze README content
        readme_found = bool(readme_content)
        readme_length = len(readme_content) if readme_content else 0
        
        has_training = self._detect_section(readme_content, "training")
        has_dataset = self._detect_section(readme_content, "dataset")
        has_eval = self._detect_section(readme_content, "evaluation")
        has_limits = self._detect_section(readme_content, "limitations")
        has_intended = self._detect_section(readme_content, "intended_use")
        has_bias = self._detect_section(readme_content, "bias")
        has_env = self._detect_section(readme_content, "environmental")
        
        # Extract from API data
        has_license = False
        license_value = None
        has_languages = False
        languages = []
        has_tags = False
        tags_count = 0
        has_model_index = False
        has_author = False
        author = None
        
        if api_data:
            # License
            license_value = api_data.get("license") or api_data.get("cardData", {}).get("license")
            has_license = bool(license_value)
            
            # Languages
            languages = api_data.get("languages") or api_data.get("cardData", {}).get("language") or []
            if isinstance(languages, str):
                languages = [languages]
            has_languages = len(languages) > 0
            
            # Tags
            tags = api_data.get("tags") or []
            tags_count = len(tags)
            has_tags = tags_count > 0
            
            # Model index (evaluation)
            model_index = api_data.get("model-index") or api_data.get("cardData", {}).get("model-index")
            has_model_index = bool(model_index)
            
            # Author
            author = api_data.get("author") or repo_id.split("/")[0]
            has_author = bool(author)
        
        # Calculate missing sections
        missing = []
        checks = [
            (has_training or has_dataset, "Training data"),
            (has_license, "License"),
            (has_eval or has_model_index, "Evaluation metrics"),
            (has_limits, "Limitations/risks"),
            (has_intended, "Intended use"),
            (has_bias, "Bias/fairness analysis"),
        ]
        
        for present, name in checks:
            if not present:
                missing.append(name)
        
        # Completeness score (0-100)
        total_checks = len(checks)
        passed_checks = total_checks - len(missing)
        completeness_score = int((passed_checks / total_checks) * 100)
        
        # Create hash
        content_hash = hashlib.sha256(
            f"{repo_id}{readme_length}{has_training}{has_license}".encode()
        ).hexdigest()[:16]
        
        analysis = ModelCardAnalysis(
            target_id=repo_id,
            repo_type=repo_type,
            readme_found=readme_found,
            readme_length=readme_length,
            has_training_section=has_training,
            has_dataset_references=has_dataset,
            has_evaluation_section=has_eval,
            has_limitations_section=has_limits,
            has_intended_use_section=has_intended,
            has_bias_section=has_bias,
            has_environmental_section=has_env,
            has_license=has_license,
            license_value=license_value,
            has_languages=has_languages,
            languages=languages[:5],  # Limit to 5
            has_tags=has_tags,
            tags_count=tags_count,
            has_model_index=has_model_index,
            has_author=has_author,
            author=author,
            completeness_score=completeness_score,
            missing_sections=missing,
            analyzed_at=now,
            analysis_hash=content_hash,
        )
        
        self.cache[cache_key] = analysis
        self.stats["analyzed"] += 1
        
        return analysis
    
    def get_stats(self) -> Dict[str, Any]:
        return self.stats


def format_analysis_for_enhancement(analysis: ModelCardAnalysis) -> Dict[str, Any]:
    """Format analysis results for use in enhancement generator."""
    return {
        "has_training_section": analysis.has_training_section or analysis.has_dataset_references,
        "has_license": analysis.has_license,
        "license": analysis.license_value,
        "has_evaluation": analysis.has_evaluation_section or analysis.has_model_index,
        "has_limitations": analysis.has_limitations_section,
        "has_intended_use": analysis.has_intended_use_section,
        "has_bias_section": analysis.has_bias_section,
        "has_environmental": analysis.has_environmental_section,
        "languages": analysis.languages,
        "author": analysis.author,
        "completeness_score": analysis.completeness_score,
        "missing_sections": analysis.missing_sections,
        "readme_found": analysis.readme_found,
    }


# ========== CLI ==========

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CROVIA Model Card Analyzer")
    parser.add_argument("repo_id", nargs="?", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--type", choices=["model", "dataset"], default="model")
    args = parser.parse_args()
    
    print("=" * 60)
    print("CROVIA Model Card Analyzer")
    print("=" * 60)
    
    analyzer = ModelCardAnalyzer()
    
    print(f"\nAnalyzing: {args.repo_id} ({args.type})")
    print("-" * 60)
    
    analysis = analyzer.analyze(args.repo_id, args.type)
    
    print(f"\n📄 README: {'Found' if analysis.readme_found else 'NOT FOUND'} ({analysis.readme_length} chars)")
    
    print(f"\n✅ PRESENT:")
    if analysis.has_training_section: print("   • Training section")
    if analysis.has_dataset_references: print("   • Dataset references")
    if analysis.has_evaluation_section: print("   • Evaluation section")
    if analysis.has_model_index: print("   • Model index (metrics)")
    if analysis.has_limitations_section: print("   • Limitations section")
    if analysis.has_intended_use_section: print("   • Intended use section")
    if analysis.has_bias_section: print("   • Bias/fairness section")
    if analysis.has_environmental_section: print("   • Environmental impact")
    if analysis.has_license: print(f"   • License: {analysis.license_value}")
    if analysis.has_languages: print(f"   • Languages: {', '.join(analysis.languages)}")
    if analysis.has_author: print(f"   • Author: {analysis.author}")
    
    print(f"\n❌ MISSING:")
    for section in analysis.missing_sections:
        print(f"   • {section}")
    
    print(f"\n📊 Completeness Score: {analysis.completeness_score}%")
    print("=" * 60)
