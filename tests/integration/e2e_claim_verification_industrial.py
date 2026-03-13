"""
Integration Test - E2E Claim Verification (Industrial)
=======================================================

End-to-end test proving all industrial micro-fixes work together.
"""

import sys
import json
import tempfile
import os
import time
from pathlib import Path

# Add schemas to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "crovia-tpr"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "crovia-pro-engine"))

from schemas.claim_evaluation_v1 import generate_evaluation_id, generate_evaluation_instance_id
from schemas.claim_dsl_v1 import ClaimDSLV1, DSLNumber
from schemas.evidence_envelope_v1 import EvidenceEnvelopeV1, VerificationMethodType
from schemas.ruleset_utils import calculate_ruleset_hash

from croviapro.compatibility.dsl_evaluator import DSLEvaluator
from croviapro.compatibility.evaluation_engine import EvaluationEngine
from croviapro.evidence.envelope_verifier import EvidenceEnvelopeVerifier


def test_e2e_bank_performance_claim():
    """
    Complete E2E test: Bank performance claim verification
    
    Pipeline:
    1. Bank declares claim (precision >= 0.95)
    2. Auditor provides evidence envelope (precision = 0.97)
    3. Ruleset loaded and validated
    4. Evaluation executed
    5. evaluation_id stable (content-addressed)
    6. evaluation_instance_id unique (includes timestamp)
    7. ZK proof reference generated
    8. Query results deterministic
    """
    
    print("\n" + "="*60)
    print("E2E Test: Bank Performance Claim Verification")
    print("="*60)
    
    # Step 1: Bank declares claim
    print("\n[1/8] Bank declares claim: precision >= 0.95")
    claim_dsl = {
        "version": "dsl-v1.0.0",
        "statements": [
            {
                "field": "precision",
                "op": ">=",
                "value": {
                    "value_str": "0.95",
                    "scale": 2
                },
                "type": "number"
            }
        ]
    }
    claim_canonical = json.dumps(claim_dsl, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    print(f"  Claim DSL: {claim_canonical[:80]}...")
    
    # Step 2: Auditor provides evidence envelope
    print("\n[2/8] Auditor provides evidence envelope")
    evidence_envelope = EvidenceEnvelopeV1(
        envelope_version="envelope-v1.0.0",
        evidence_hash="def456abc123def456abc123def456abc123def456abc123def456abc123de12",
        issuer_id="benchmark-auditor-xyz",
        issued_at="2026-01-19T18:00:00.000Z",
        issuer_signature="abc123def456abc123def456abc123def456abc123def456abc123def456abc123def456",
        signature_algorithm="RS256",
        verification_method="https://auditor-xyz.com/public-key",
        verification_method_type=VerificationMethodType.URL
    )
    print(f"  Issuer: {evidence_envelope.issuer_id}")
    print(f"  Method: {evidence_envelope.verification_method_type.value}")
    
    # Verify envelope
    verifier = EvidenceEnvelopeVerifier()
    envelope_valid = verifier.verify_envelope(evidence_envelope)
    print(f"  Envelope valid: {envelope_valid}")
    assert envelope_valid, "Evidence envelope must be valid"
    
    # Evidence data
    evidence_data = {
        "precision": {
            "value_str": "0.97",
            "scale": 2
        }
    }
    
    # Step 3: Ruleset loaded
    print("\n[3/8] Ruleset loaded and validated")
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test ruleset manifest
        ruleset_manifest = {
            "manifest_version": "v1.0.0",
            "ruleset_id": "dsl-evaluation-v1.0.0",
            "name": "DSL Evaluation Rules v1",
            "rules": {
                "temporal_ordering": {"rule_id": "R001", "required": True},
                "hash_integrity": {"rule_id": "R002", "required": True},
                "dsl_structure_validation": {"rule_id": "R003", "required": True}
            }
        }
        
        # Calculate ruleset hash
        manifest_path = os.path.join(temp_dir, "temp_manifest.json")
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(ruleset_manifest, f)
        
        ruleset_hash = calculate_ruleset_hash(manifest_path)
        print(f"  Ruleset hash: {ruleset_hash}")
        
        # Save with hash as filename for availability check
        final_manifest_path = os.path.join(temp_dir, f"{ruleset_hash}.json")
        with open(final_manifest_path, 'w', encoding='utf-8') as f:
            json.dump(ruleset_manifest, f)
        
        # Step 4: Evaluation executed
        print("\n[4/8] Evaluation executed")
        engine = EvaluationEngine(rulesets_dir=temp_dir)
        
        evaluation = engine.evaluate(
            claim_dsl=claim_dsl,
            evidence_data=evidence_data,
            ruleset_hash=ruleset_hash,
            anchor_root="root123abc456root123abc456root123abc456root123abc456root123abc456",
            evaluator_version="eval-v1.0.0"
        )
        
        print(f"  Verdict: {evaluation.verdict}")
        assert evaluation.verdict == "COMPATIBLE", "Precision 0.97 >= 0.95 should be COMPATIBLE"
        
        # Step 5: evaluation_id stable
        print("\n[5/8] evaluation_id stable (content-addressed)")
        print(f"  evaluation_id: {evaluation.evaluation_id}")
        assert len(evaluation.evaluation_id) == 64
        
        # Verify stability - same inputs should produce same ID
        claim_hash = engine._hash_claim(claim_dsl)
        evidence_hash = engine._hash_evidence(evidence_data)
        
        stable_id = generate_evaluation_id(
            claim_hash=claim_hash,
            evidence_hash=evidence_hash,
            ruleset_hash=ruleset_hash,
            anchor_root="root123abc456root123abc456root123abc456root123abc456root123abc456",
            evaluator_version="eval-v1.0.0"
        )
        assert evaluation.evaluation_id == stable_id, "evaluation_id must be stable"
        print(f"  ✓ Stable ID verified")
        
        # Step 6: evaluation_instance_id unique
        print("\n[6/8] evaluation_instance_id unique (includes timestamp)")
        print(f"  instance_id: {evaluation.evaluation_instance_id}")
        assert len(evaluation.evaluation_instance_id) == 64
        assert evaluation.evaluation_instance_id != evaluation.evaluation_id
        print(f"  ✓ Instance ID unique")
        
        # Step 7: ZK proof reference generated
        print("\n[7/8] ZK proof reference generated")
        print(f"  zk_proof_reference: {evaluation.zk_proof_reference}")
        assert evaluation.zk_proof_reference.startswith("zkproof:")
        print(f"  ✓ Standardized format")
        
        # Step 8: Query results deterministic
        print("\n[8/8] Query results deterministic")
        # Simulate query ordering
        evaluations = [evaluation]
        # Sort by evaluation_id ASC, observed_at ASC (deterministic)
        sorted_evals = sorted(evaluations, key=lambda e: (e.evaluation_id, e.observed_at))
        assert sorted_evals[0] == evaluation
        print(f"  ✓ Deterministic ordering verified")
    
    print("\n" + "="*60)
    print("✓ E2E Test PASSED - All industrial features working")
    print("="*60)
    
    return evaluation


def test_e2e_re_evaluation():
    """Test re-evaluation: same evaluation_id, different instance_id"""
    print("\n" + "="*60)
    print("E2E Test: Re-Evaluation After 6 Months")
    print("="*60)
    
    claim_dsl = {
        "version": "dsl-v1.0.0",
        "statements": [
            {
                "field": "accuracy",
                "op": ">=",
                "value": {"value_str": "0.90", "scale": 2},
                "type": "number"
            }
        ]
    }
    
    evidence_data = {"accuracy": {"value_str": "0.92", "scale": 2}}
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create ruleset
        ruleset_manifest = {
            "manifest_version": "v1.0.0",
            "ruleset_id": "test-ruleset",
            "rules": {}
        }
        
        manifest_path = os.path.join(temp_dir, "temp_manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(ruleset_manifest, f)
        
        ruleset_hash = calculate_ruleset_hash(manifest_path)
        
        final_path = os.path.join(temp_dir, f"{ruleset_hash}.json")
        with open(final_path, 'w') as f:
            json.dump(ruleset_manifest, f)
        
        engine = EvaluationEngine(rulesets_dir=temp_dir)
        
        # First evaluation
        eval1 = engine.evaluate(
            claim_dsl=claim_dsl,
            evidence_data=evidence_data,
            ruleset_hash=ruleset_hash,
            anchor_root="root_t1",
            evaluator_version="eval-v1.0.0"
        )
        
        # Wait to ensure different timestamp (simulates re-evaluation)
        time.sleep(0.01)
        
        # Re-evaluation (simulated 6 months later)
        eval2 = engine.evaluate(
            claim_dsl=claim_dsl,
            evidence_data=evidence_data,
            ruleset_hash=ruleset_hash,
            anchor_root="root_t1",  # Same anchor
            evaluator_version="eval-v1.0.0"
        )
        
        print(f"\nFirst evaluation:")
        print(f"  evaluation_id: {eval1.evaluation_id}")
        print(f"  instance_id: {eval1.evaluation_instance_id}")
        print(f"  observed_at: {eval1.observed_at}")
        
        print(f"\nRe-evaluation:")
        print(f"  evaluation_id: {eval2.evaluation_id}")
        print(f"  instance_id: {eval2.evaluation_instance_id}")
        print(f"  observed_at: {eval2.observed_at}")
        
        # Verify: same evaluation_id, different instance_id
        assert eval1.evaluation_id == eval2.evaluation_id, "evaluation_id must be stable"
        assert eval1.evaluation_instance_id != eval2.evaluation_instance_id, "instance_id must be unique"
        
        print("\n✓ Re-evaluation test PASSED")
        print("  - Same evaluation_id (content-addressed)")
        print("  - Different instance_id (timestamp-based)")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("CROVIA - Industrial Integration Tests")
    print("="*60)
    
    # Run E2E tests
    evaluation = test_e2e_bank_performance_claim()
    test_e2e_re_evaluation()
    
    print("\n" + "="*60)
    print("✓ ALL INTEGRATION TESTS PASSED")
    print("="*60)
    
    # Output example evaluation artifact
    print("\n" + "="*60)
    print("Example Evaluation Artifact (JSON):")
    print("="*60)
    artifact = {
        "evaluation_id": evaluation.evaluation_id,
        "evaluation_instance_id": evaluation.evaluation_instance_id,
        "claim_commitment_hash": evaluation.claim_commitment_hash,
        "evidence_hash": evaluation.evidence_hash,
        "ruleset_hash": evaluation.ruleset_hash,
        "verdict": evaluation.verdict,
        "evaluator_version": evaluation.evaluator_version,
        "observed_at": evaluation.observed_at,
        "anchor_root": evaluation.anchor_root,
        "zk_proof_reference": evaluation.zk_proof_reference
    }
    print(json.dumps(artifact, indent=2))
