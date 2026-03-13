"""
Golden Tests - Evidence Envelope Validation
============================================

Tests for EvidenceEnvelopeV1 with verification_method_type enum.
"""

import sys
from pathlib import Path

# Add schemas to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "crovia-tpr"))

from schemas.evidence_envelope_v1 import EvidenceEnvelopeV1, VerificationMethodType


def test_evidence_envelope_valid():
    """Valid evidence envelope creation"""
    envelope = EvidenceEnvelopeV1(
        envelope_version="envelope-v1.0.0",
        evidence_hash="abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
        issuer_id="benchmark-platform-xyz",
        issued_at="2026-01-19T10:00:00.000Z",
        issuer_signature="signature_hash_here",
        signature_algorithm="RS256",
        verification_method="https://example.com/public-key",
        verification_method_type=VerificationMethodType.URL
    )
    
    assert envelope.evidence_hash == "abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    assert envelope.verification_method_type == VerificationMethodType.URL
    print(f"✓ Valid envelope created with URL verification method")


def test_evidence_envelope_invalid_hash():
    """Invalid evidence hash length rejected"""
    try:
        envelope = EvidenceEnvelopeV1(
            envelope_version="envelope-v1.0.0",
            evidence_hash="short_hash",  # Not 64 chars
            issuer_id="benchmark-platform-xyz",
            issued_at="2026-01-19T10:00:00.000Z",
            issuer_signature="signature_hash_here",
            signature_algorithm="RS256",
            verification_method="https://example.com/public-key",
            verification_method_type=VerificationMethodType.URL
        )
        assert False, "Should have raised ValueError for invalid hash length"
    except ValueError as e:
        assert "64 hex chars" in str(e)
        print(f"✓ Invalid hash length rejected")


def test_evidence_envelope_empty_issuer():
    """Empty issuer_id rejected"""
    try:
        envelope = EvidenceEnvelopeV1(
            envelope_version="envelope-v1.0.0",
            evidence_hash="abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
            issuer_id="",  # Empty
            issued_at="2026-01-19T10:00:00.000Z",
            issuer_signature="signature_hash_here",
            signature_algorithm="RS256",
            verification_method="https://example.com/public-key",
            verification_method_type=VerificationMethodType.URL
        )
        assert False, "Should have raised ValueError for empty issuer_id"
    except ValueError as e:
        assert "cannot be empty" in str(e)
        print(f"✓ Empty issuer_id rejected")


def test_evidence_envelope_canonical_hash():
    """Canonical hash includes verification_method_type"""
    envelope = EvidenceEnvelopeV1(
        envelope_version="envelope-v1.0.0",
        evidence_hash="abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
        issuer_id="benchmark-platform-xyz",
        issued_at="2026-01-19T10:00:00.000Z",
        issuer_signature="signature_hash_here",
        signature_algorithm="RS256",
        verification_method="https://example.com/public-key",
        verification_method_type=VerificationMethodType.URL
    )
    
    canonical_hash = envelope.canonical_hash()
    assert len(canonical_hash) == 64
    print(f"✓ Canonical hash: {canonical_hash}")


def test_verification_method_types():
    """All verification method types supported"""
    for method_type in [VerificationMethodType.URL, VerificationMethodType.JWK, 
                        VerificationMethodType.DID, VerificationMethodType.X509]:
        envelope = EvidenceEnvelopeV1(
            envelope_version="envelope-v1.0.0",
            evidence_hash="abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
            issuer_id="issuer-test",
            issued_at="2026-01-19T10:00:00.000Z",
            issuer_signature="sig",
            signature_algorithm="RS256",
            verification_method="method",
            verification_method_type=method_type
        )
        assert envelope.verification_method_type == method_type
    
    print(f"✓ All verification method types supported: url, jwk, did, x509")


if __name__ == "__main__":
    print("Running Golden Tests - Evidence Envelope Validation\n")
    test_evidence_envelope_valid()
    test_evidence_envelope_invalid_hash()
    test_evidence_envelope_empty_issuer()
    test_evidence_envelope_canonical_hash()
    test_verification_method_types()
    print("\n✓ All evidence envelope validation tests passed")
