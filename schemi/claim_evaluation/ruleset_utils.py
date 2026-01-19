"""
Ruleset Utilities
==================

Utilities for ruleset manifest handling, canonical hashing, and availability checks.
"""

import hashlib
import json
import os
from typing import Dict


class RulesetNotFoundError(Exception):
    """Raised when a ruleset manifest is not available"""
    pass


def calculate_ruleset_hash(manifest_path: str) -> str:
    """
    Calculate deterministic hash of ruleset manifest.
    
    Uses canonical JSON serialization with:
    - ensure_ascii=True (prevents unicode encoding issues)
    - UTF-8 encoding
    - Whitespace stripping
    - Sorted keys
    """
    with open(manifest_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()  # Remove trailing whitespace
        manifest = json.loads(content)
    
    # Canonical JSON serialization
    canonical = json.dumps(
        manifest,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True  # Prevent unicode encoding issues
    )
    
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def verify_ruleset_availability(ruleset_hash: str, rulesets_dir: str = "rulesets") -> bool:
    """
    Check if ruleset manifest is available.
    
    Args:
        ruleset_hash: SHA256 hash of ruleset manifest
        rulesets_dir: Directory containing ruleset manifests
    
    Returns:
        True if manifest exists, False otherwise
    """
    manifest_path = os.path.join(rulesets_dir, f"{ruleset_hash}.json")
    return os.path.exists(manifest_path)


def load_ruleset_manifest(ruleset_hash: str, rulesets_dir: str = "rulesets") -> Dict:
    """
    Load ruleset manifest with availability check.
    
    Args:
        ruleset_hash: SHA256 hash of ruleset manifest
        rulesets_dir: Directory containing ruleset manifests
    
    Returns:
        Ruleset manifest as dictionary
    
    Raises:
        RulesetNotFoundError: If manifest is not available
    """
    if not verify_ruleset_availability(ruleset_hash, rulesets_dir):
        raise RulesetNotFoundError(
            f"Ruleset manifest {ruleset_hash} not found in {rulesets_dir}. "
            f"Evaluation cannot proceed without ruleset definition."
        )
    
    manifest_path = os.path.join(rulesets_dir, f"{ruleset_hash}.json")
    with open(manifest_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_ruleset_manifest(manifest: Dict) -> bool:
    """
    Validate ruleset manifest structure.
    
    Required fields:
    - manifest_version
    - ruleset_id
    - rules (dict)
    """
    required_fields = ['manifest_version', 'ruleset_id', 'rules']
    
    for field in required_fields:
        if field not in manifest:
            raise ValueError(f"Ruleset manifest missing required field: {field}")
    
    if not isinstance(manifest['rules'], dict):
        raise ValueError("Ruleset 'rules' must be a dictionary")
    
    return True
