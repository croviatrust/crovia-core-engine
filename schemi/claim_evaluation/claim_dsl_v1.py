"""
Claim DSL V1 Schema
===================

Defines the DSL for structured claims with deterministic evaluation.
Uses fixed-point arithmetic to avoid floating-point precision issues.
"""

from dataclasses import dataclass
from typing import ClassVar, List, Dict, Any
import json


@dataclass
class DSLNumber:
    """
    Deterministic number representation for DSL claims.
    
    Uses fixed-point arithmetic to avoid float precision issues.
    value_str: "95" or "0.95"
    scale: 0 for "95", 2 for "0.95"
    """
    value_str: str
    scale: int
    
    MAX_SCALE: ClassVar[int] = 18  # Maximum decimal places (prevents overflow)
    
    def __post_init__(self):
        """Validate scale and value_str format"""
        if self.scale < 0:
            raise ValueError(f"Scale must be non-negative, got {self.scale}")
        
        if self.scale > self.MAX_SCALE:
            raise ValueError(f"Scale {self.scale} exceeds maximum {self.MAX_SCALE}")
        
        # Validate value_str format
        if '.' in self.value_str:
            parts = self.value_str.split('.')
            if len(parts) != 2:
                raise ValueError(f"Invalid decimal format: {self.value_str}")
            if len(parts[1]) != self.scale:
                raise ValueError(f"Scale mismatch: {self.value_str} has {len(parts[1])} decimals, expected {self.scale}")
        elif self.scale != 0:
            raise ValueError(f"Integer value {self.value_str} must have scale=0")
        
        # Validate numeric content
        try:
            float(self.value_str)
        except ValueError:
            raise ValueError(f"value_str must be numeric: {self.value_str}")
    
    def to_fixed_point(self) -> int:
        """Convert to fixed-point integer for deterministic comparison"""
        return int(self.value_str.replace('.', ''))
    
    @classmethod
    def from_decimal(cls, decimal_str: str) -> 'DSLNumber':
        """Create DSLNumber from decimal string"""
        if '.' in decimal_str:
            parts = decimal_str.split('.')
            scale = len(parts[1])
            if scale > cls.MAX_SCALE:
                raise ValueError(f"Decimal precision {scale} exceeds max {cls.MAX_SCALE}")
            return cls(decimal_str, scale)
        else:
            return cls(decimal_str, 0)


@dataclass
class DSLStatement:
    """Single DSL statement for claim verification"""
    field: str
    op: str  # ">=", "<=", "==", "!=", "in", "not_in"
    value: Any  # DSLNumber, string, list, etc.
    type: str  # "number", "string", "set", "boolean"


@dataclass
class ClaimDSLV1:
    """
    Claim DSL V1 - Structured claim format
    
    version: "dsl-v1.0.0"
    statements: List of DSL statements
    """
    version: str
    statements: List[Dict[str, Any]]
    
    def to_canonical_json(self) -> str:
        """Convert to canonical JSON for hashing"""
        data = {
            "version": self.version,
            "statements": self.statements
        }
        return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    
    def to_hash(self) -> str:
        """Generate deterministic hash of claim DSL"""
        import hashlib
        canonical = self.to_canonical_json()
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


# Canonical operator mappings
CANONICAL_OPS = {
    ">=": "gte",
    "<=": "lte",
    "==": "eq",
    "!=": "neq",
    "in": "in",
    "not_in": "not_in"
}


def canonicalize_op(op: str) -> str:
    """Canonicalize operator to standard form"""
    return CANONICAL_OPS.get(op, op)
