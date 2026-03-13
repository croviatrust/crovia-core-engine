"""
Golden Tests - Ruleset Utils
==============================

Tests for ruleset canonical hash and availability check.
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# Add schemas to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "crovia-tpr"))

from schemas.ruleset_utils import (
    calculate_ruleset_hash,
    verify_ruleset_availability,
    load_ruleset_manifest,
    RulesetNotFoundError
)


def test_ruleset_hash_deterministic():
    """Ruleset hash is deterministic with canonical JSON"""
    # Create temp manifest
    manifest = {
        "manifest_version": "v1.0.0",
        "ruleset_id": "test-ruleset",
        "rules": {
            "rule1": {"required": True},
            "rule2": {"required": False}
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(manifest, f)
        temp_path = f.name
    
    try:
        hash1 = calculate_ruleset_hash(temp_path)
        hash2 = calculate_ruleset_hash(temp_path)
        
        assert hash1 == hash2, "Ruleset hash must be deterministic"
        assert len(hash1) == 64, "Hash must be 64 hex chars"
        print(f"✓ Ruleset hash deterministic: {hash1}")
    finally:
        os.unlink(temp_path)


def test_ruleset_availability_check():
    """Ruleset availability check works"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test manifest
        manifest = {"manifest_version": "v1.0.0", "ruleset_id": "test", "rules": {}}
        test_hash = "abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
        
        manifest_path = os.path.join(temp_dir, f"{test_hash}.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)
        
        # Should find it
        assert verify_ruleset_availability(test_hash, temp_dir) == True
        
        # Should not find non-existent
        assert verify_ruleset_availability("nonexistent", temp_dir) == False
        
        print(f"✓ Ruleset availability check works")


def test_ruleset_load_with_availability():
    """Load ruleset with availability check"""
    with tempfile.TemporaryDirectory() as temp_dir:
        manifest = {
            "manifest_version": "v1.0.0",
            "ruleset_id": "test-ruleset",
            "rules": {"rule1": {"required": True}}
        }
        test_hash = "abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
        
        manifest_path = os.path.join(temp_dir, f"{test_hash}.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)
        
        # Should load successfully
        loaded = load_ruleset_manifest(test_hash, temp_dir)
        assert loaded == manifest
        print(f"✓ Ruleset loaded successfully")


def test_ruleset_not_found_error():
    """RulesetNotFoundError raised when manifest missing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            load_ruleset_manifest("nonexistent_hash", temp_dir)
            assert False, "Should have raised RulesetNotFoundError"
        except RulesetNotFoundError as e:
            assert "not found" in str(e)
            print(f"✓ RulesetNotFoundError raised correctly")


def test_ruleset_hash_unicode_handling():
    """Ruleset hash handles unicode correctly with ensure_ascii"""
    manifest = {
        "manifest_version": "v1.0.0",
        "ruleset_id": "test-unicode",
        "rules": {
            "rule1": {"description": "Test with unicode: café"}
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False)
        temp_path = f.name
    
    try:
        hash_result = calculate_ruleset_hash(temp_path)
        assert len(hash_result) == 64
        assert all(c in '0123456789abcdef' for c in hash_result.lower())
        print(f"✓ Unicode handling with ensure_ascii works")
    finally:
        os.unlink(temp_path)


if __name__ == "__main__":
    print("Running Golden Tests - Ruleset Utils\n")
    test_ruleset_hash_deterministic()
    test_ruleset_availability_check()
    test_ruleset_load_with_availability()
    test_ruleset_not_found_error()
    test_ruleset_hash_unicode_handling()
    print("\n✓ All ruleset utils tests passed")
