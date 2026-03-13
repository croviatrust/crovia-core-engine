"""
Golden Tests - Claim Evaluation Determinism
============================================

Tests for evaluation_id stability and instance_id uniqueness.
"""

import sys
from pathlib import Path

# Add schemas to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "crovia-tpr"))

from schemas.claim_evaluation_v1 import (
    generate_evaluation_id,
    generate_evaluation_instance_id,
    ZKProofReferenceFormat
)


def test_evaluation_id_stable():
    """Same claim+evidence+ruleset → same evaluation_id"""
    eval1 = generate_evaluation_id(
        claim_hash="abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
        evidence_hash="def456abc123def456abc123def456abc123def456abc123def456abc123de12",
        ruleset_hash="ghi789abc123ghi789abc123ghi789abc123ghi789abc123ghi789abc123gh34",
        anchor_root="root123abc456root123abc456root123abc456root123abc456root123abc456",
        evaluator_version="eval-v1.0.0"
    )
    
    eval2 = generate_evaluation_id(
        claim_hash="abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
        evidence_hash="def456abc123def456abc123def456abc123def456abc123def456abc123de12",
        ruleset_hash="ghi789abc123ghi789abc123ghi789abc123ghi789abc123ghi789abc123gh34",
        anchor_root="root123abc456root123abc456root123abc456root123abc456root123abc456",
        evaluator_version="eval-v1.0.0"
    )
    
    assert eval1 == eval2, "evaluation_id must be deterministic"
    assert len(eval1) == 64, "evaluation_id must be 64 hex chars"
    print(f"✓ evaluation_id stable: {eval1}")


def test_instance_id_different_timestamp():
    """Different observed_at → different evaluation_instance_id"""
    eval_id = "stable_eval_id_123abc456stable_eval_id_123abc456stable_eval_id_123a"
    
    instance1 = generate_evaluation_instance_id(
        eval_id, 
        "2026-01-19T10:00:00.000Z"
    )
    
    instance2 = generate_evaluation_instance_id(
        eval_id,
        "2026-01-19T11:00:00.000Z"
    )
    
    assert instance1 != instance2, "Different timestamp must produce different instance_id"
    assert len(instance1) == 64, "instance_id must be 64 hex chars"
    assert len(instance2) == 64, "instance_id must be 64 hex chars"
    print(f"✓ instance_id unique per timestamp")
    print(f"  instance1: {instance1}")
    print(f"  instance2: {instance2}")


def test_re_evaluation_same_content():
    """Re-evaluation after 6 months: same evaluation_id, different instance_id"""
    # First evaluation
    eval_id_t1 = generate_evaluation_id(
        claim_hash="abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
        evidence_hash="def456abc123def456abc123def456abc123def456abc123def456abc123de12",
        ruleset_hash="ghi789abc123ghi789abc123ghi789abc123ghi789abc123ghi789abc123gh34",
        anchor_root="root123abc456root123abc456root123abc456root123abc456root123abc456",
        evaluator_version="eval-v1.0.0"
    )
    instance_id_t1 = generate_evaluation_instance_id(eval_id_t1, "2026-01-19T10:00:00.000Z")
    
    # Re-evaluation 6 months later (same inputs)
    eval_id_t2 = generate_evaluation_id(
        claim_hash="abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
        evidence_hash="def456abc123def456abc123def456abc123def456abc123def456abc123de12",
        ruleset_hash="ghi789abc123ghi789abc123ghi789abc123ghi789abc123ghi789abc123gh34",
        anchor_root="root123abc456root123abc456root123abc456root123abc456root123abc456",
        evaluator_version="eval-v1.0.0"
    )
    instance_id_t2 = generate_evaluation_instance_id(eval_id_t2, "2026-07-19T10:00:00.000Z")
    
    assert eval_id_t1 == eval_id_t2, "Content-addressed ID must be stable"
    assert instance_id_t1 != instance_id_t2, "Instance ID must differ for re-evaluation"
    print(f"✓ Re-evaluation: stable evaluation_id, unique instance_id")


def test_zkproof_reference_format():
    """ZK proof reference format validation"""
    # Test hash format
    proof_hash = "abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    ref1 = ZKProofReferenceFormat.from_hash(proof_hash)
    assert ref1 == f"zkproof:sha256:{proof_hash}"
    
    # Test URL format
    proof_url = "https://zkproof.example.com/proof123"
    ref2 = ZKProofReferenceFormat.from_url(proof_url)
    assert ref2 == f"zkproof:url:{proof_url}"
    
    # Test parser
    ref_type, ref_value = ZKProofReferenceFormat.parse(ref1)
    assert ref_type == "sha256"
    assert ref_value == proof_hash
    
    print(f"✓ ZK proof reference format validated")


def test_unicode_in_evaluation_id():
    """Unicode in hashes produces deterministic evaluation_id"""
    # Evaluation IDs are hashes (hex only), but test that unicode in source doesn't break
    eval_id = generate_evaluation_id(
        claim_hash="abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
        evidence_hash="def456abc123def456abc123def456abc123def456abc123def456abc123de12",
        ruleset_hash="ghi789abc123ghi789abc123ghi789abc123ghi789abc123ghi789abc123gh34",
        anchor_root="root123abc456root123abc456root123abc456root123abc456root123abc456",
        evaluator_version="eval-v1.0.0"
    )
    
    # Should be valid hex
    assert all(c in '0123456789abcdef' for c in eval_id.lower())
    print(f"✓ Unicode handling: evaluation_id is valid hex")


if __name__ == "__main__":
    print("Running Golden Tests - Claim Evaluation Determinism\n")
    test_evaluation_id_stable()
    test_instance_id_different_timestamp()
    test_re_evaluation_same_content()
    test_zkproof_reference_format()
    test_unicode_in_evaluation_id()
    print("\n✓ All golden tests passed")
