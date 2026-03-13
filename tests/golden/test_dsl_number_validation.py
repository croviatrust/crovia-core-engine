"""
Golden Tests - DSL Number Validation
=====================================

Tests for DSLNumber overflow protection and validation.
"""

import sys
from pathlib import Path

# Add schemas to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "crovia-tpr"))

from schemas.claim_dsl_v1 import DSLNumber


def test_dsl_number_max_scale():
    """DSLNumber rejects scale > MAX_SCALE"""
    try:
        num = DSLNumber("0.123456789012345678901", 21)  # scale > 18
        assert False, "Should have raised ValueError for scale > MAX_SCALE"
    except ValueError as e:
        assert "exceeds maximum" in str(e)
        print(f"✓ MAX_SCALE validation works: {e}")


def test_dsl_number_valid_decimal():
    """DSLNumber accepts valid decimal"""
    num = DSLNumber("0.95", 2)
    assert num.to_fixed_point() == 95
    print(f"✓ Valid decimal: 0.95 → fixed-point 95")


def test_dsl_number_valid_integer():
    """DSLNumber accepts valid integer"""
    num = DSLNumber("95", 0)
    assert num.to_fixed_point() == 95
    print(f"✓ Valid integer: 95 → fixed-point 95")


def test_dsl_number_scale_mismatch():
    """DSLNumber rejects scale mismatch"""
    try:
        num = DSLNumber("0.95", 3)  # Has 2 decimals but scale=3
        assert False, "Should have raised ValueError for scale mismatch"
    except ValueError as e:
        assert "Scale mismatch" in str(e)
        print(f"✓ Scale mismatch detection works")


def test_dsl_number_from_decimal():
    """DSLNumber.from_decimal creates correct instance"""
    num = DSLNumber.from_decimal("0.95")
    assert num.value_str == "0.95"
    assert num.scale == 2
    assert num.to_fixed_point() == 95
    print(f"✓ from_decimal: 0.95 → scale=2, fixed-point=95")


def test_dsl_number_overflow_protection():
    """DSLNumber prevents overflow with MAX_SCALE"""
    try:
        num = DSLNumber.from_decimal("0.1234567890123456789")  # 19 decimals
        assert False, "Should have raised ValueError for precision > MAX_SCALE"
    except ValueError as e:
        assert "exceeds max" in str(e)
        print(f"✓ Overflow protection works")


if __name__ == "__main__":
    print("Running Golden Tests - DSL Number Validation\n")
    test_dsl_number_max_scale()
    test_dsl_number_valid_decimal()
    test_dsl_number_valid_integer()
    test_dsl_number_scale_mismatch()
    test_dsl_number_from_decimal()
    test_dsl_number_overflow_protection()
    print("\n✓ All DSL number validation tests passed")
