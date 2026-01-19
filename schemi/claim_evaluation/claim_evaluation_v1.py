"""
ClaimEvaluation V1 Schema
==========================

Defines the ClaimEvaluation artifact with stable content-addressed ID
and unique instance ID for re-evaluations.
"""

import hashlib
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ClaimEvaluationV1:
    """
    ClaimEvaluation V1 - Immutable evaluation artifact
    
    evaluation_id: Stable content-addressed ID (NO timestamp)
    evaluation_instance_id: Unique instance ID (includes timestamp)
    """
    
    # STABLE CONTENT-ADDRESSED ID (no timestamp)
    evaluation_id: str
    
    # INSTANCE ID for re-evaluations (includes timestamp)
    evaluation_instance_id: str
    
    # Core fields
    claim_commitment_hash: str
    evidence_hash: str
    ruleset_hash: str
    verdict: str  # "COMPATIBLE"|"INCOMPATIBLE"|"INDETERMINATE"
    evaluator_version: str
    observed_at: str  # ISO UTC timestamp (NOT in evaluation_id)
    anchor_root: str  # canonical_root_v1 AT EVALUATION TIME
    zk_proof_reference: str  # Format: "zkproof:sha256:<hash>"
    refs: Optional[List[str]] = None


def generate_evaluation_id(
    claim_hash: str,
    evidence_hash: str,
    ruleset_hash: str,
    anchor_root: str,
    evaluator_version: str
) -> str:
    """
    Generate stable content-addressed evaluation ID.
    
    NO timestamp included - same inputs always produce same ID.
    """
    canonical = f"{claim_hash}|{evidence_hash}|{ruleset_hash}|{anchor_root}|{evaluator_version}"
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def generate_evaluation_instance_id(evaluation_id: str, observed_at: str) -> str:
    """
    Generate unique instance ID for re-evaluations.
    
    Includes timestamp - allows same evaluation_id to be re-evaluated.
    """
    canonical = f"{evaluation_id}|{observed_at}"
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


class ZKProofReferenceFormat:
    """Standardized format for ZK proof references"""
    
    @staticmethod
    def from_hash(proof_hash: str) -> str:
        """Format: zkproof:sha256:<hash>"""
        if len(proof_hash) != 64:
            raise ValueError("Proof hash must be 64 hex chars")
        if not all(c in '0123456789abcdef' for c in proof_hash.lower()):
            raise ValueError("Proof hash must be valid hex")
        return f"zkproof:sha256:{proof_hash}"
    
    @staticmethod
    def from_url(proof_url: str) -> str:
        """Format: zkproof:url:<url>"""
        if not proof_url.startswith('https://'):
            raise ValueError("Proof URL must use HTTPS")
        return f"zkproof:url:{proof_url}"
    
    @staticmethod
    def parse(reference: str) -> tuple:
        """Parse reference into (type, value)"""
        if not reference.startswith('zkproof:'):
            raise ValueError("Invalid zkproof reference format")
        
        parts = reference.split(':', 2)
        if len(parts) != 3:
            raise ValueError("Invalid zkproof reference format")
        
        return parts[1], parts[2]  # (type, value)
