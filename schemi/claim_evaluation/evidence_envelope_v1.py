"""
Evidence Envelope V1 Schema
============================

Defines the evidence envelope with issuer signature and verification method.
"""

import hashlib
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class VerificationMethodType(str, Enum):
    """Verification method types for evidence envelope signatures"""
    URL = "url"           # HTTPS URL to public key
    JWK = "jwk"          # JSON Web Key embedded
    DID = "did"          # Decentralized Identifier
    X509 = "x509"        # X.509 certificate reference


@dataclass
class EvidenceEnvelopeV1:
    """
    Evidence Envelope V1 - Signed evidence container
    
    Provides cryptographic attestation of evidence issuer and integrity.
    """
    envelope_version: str           # "envelope-v1.0.0"
    evidence_hash: str              # SHA256 of actual evidence content
    issuer_id: str                 # Identity of evidence issuer
    issued_at: str                 # ISO UTC timestamp (millisecond precision)
    issuer_signature: str          # Digital signature
    signature_algorithm: str       # "RS256", "ES256", etc.
    verification_method: str       # Public key or reference
    verification_method_type: VerificationMethodType  # Enum: url|jwk|did|x509
    
    def __post_init__(self):
        """Validate envelope fields"""
        if len(self.evidence_hash) != 64:
            raise ValueError("evidence_hash must be 64 hex chars (SHA256)")
        
        if not all(c in '0123456789abcdef' for c in self.evidence_hash.lower()):
            raise ValueError("evidence_hash must be valid hex")
        
        if not self.issuer_id:
            raise ValueError("issuer_id cannot be empty")
        
        # Validate timestamp format (ISO 8601 with milliseconds)
        try:
            datetime.fromisoformat(self.issued_at.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f"Invalid ISO timestamp: {self.issued_at}")
        
        # Validate verification_method_type is enum
        if not isinstance(self.verification_method_type, VerificationMethodType):
            raise ValueError(f"verification_method_type must be VerificationMethodType enum")
    
    def canonical_hash(self) -> str:
        """Hash dell'envelope per referencing"""
        canonical = f"{self.evidence_hash}|{self.issuer_id}|{self.issued_at}|{self.issuer_signature}|{self.verification_method_type.value}"
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
