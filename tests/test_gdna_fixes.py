import pytest
import numpy as np
import json
import hashlib
from croviapro.sonar_v2.geometric_dna import (
    mantel_test,
    AnchorSet,
    BatchResult,
    GeometricFingerprint,
    ProvenanceComparison,
    MantelResult,
    export_signed_report,
    _hash_fingerprint
)

def test_fingerprint_hash_changes_if_anchor_set_changes():
    """Verify that different anchor sets produce different hashes for the same matrix."""
    # Mock anchor sets
    anchors_a = AnchorSet(tokens=["a", "b"], domain_labels={}, neutral_indices=[], total_count=2)
    anchors_b = AnchorSet(tokens=["x", "y", "z"], domain_labels={}, neutral_indices=[], total_count=3)
    
    assert anchors_a.full_identity_hash() != anchors_b.full_identity_hash()
    
    # Mock matrix
    surface_mat = np.array([[1.0, 0.5], [0.5, 1.0]], dtype=np.float32)
    
    # Use the pure helper from the module
    hash_a = _hash_fingerprint(anchors_a, surface_mat, None)
    hash_b = _hash_fingerprint(anchors_b, surface_mat, None)
    
    assert hash_a != hash_b, "Hash should bind to full anchor set identity"

def test_fingerprint_hash_stable_same_inputs():
    """Verify that identical inputs produce the exact same fingerprint hash."""
    anchors = AnchorSet(tokens=["a", "b"], domain_labels={}, neutral_indices=[], total_count=2)
    surface_mat = np.array([[1.0, 0.5], [0.5, 1.0]], dtype=np.float32)
    deep_mat = np.array([[1.0, 0.2], [0.2, 1.0]], dtype=np.float32)
    
    # Use the pure helper from the module
    hash_1 = _hash_fingerprint(anchors, surface_mat, deep_mat)
    hash_2 = _hash_fingerprint(anchors, surface_mat, deep_mat)
    
    assert hash_1 == hash_2, "Hash must be perfectly stable for identical inputs"

def test_fingerprint_hash_dtype_invariant_for_hashing():
    """Verify that float64 vs float32 matrices produce the exact same fingerprint hash due to <f4 casting."""
    anchors = AnchorSet(tokens=["a", "b"], domain_labels={}, neutral_indices=[], total_count=2)
    
    # Same numeric values, different internal dtypes
    surface_mat_f32 = np.array([[1.0, 0.12345678], [0.12345678, 1.0]], dtype=np.float32)
    surface_mat_f64 = np.array([[1.0, 0.12345678], [0.12345678, 1.0]], dtype=np.float64)
    
    # Use the pure helper from the module
    hash_32 = _hash_fingerprint(anchors, surface_mat_f32, None)
    hash_64 = _hash_fingerprint(anchors, surface_mat_f64, None)
    
    assert hash_32 == hash_64, "Hash must be invariant to memory dtype of the matrix (must always cast to <f4)"

def test_matrix_serialization_deterministic():
    """Verify float32 little-endian deterministic serialization."""
    mat_f64 = np.array([[1.0, 0.123456789]], dtype=np.float64)
    mat_f32 = np.array([[1.0, 0.123456789]], dtype=np.float32)
    
    # When cast to <f4 (little-endian float32), both should produce exact same bytes
    bytes_f64_cast = mat_f64.astype("<f4").tobytes()
    bytes_f32_cast = mat_f32.astype("<f4").tobytes()
    
    assert bytes_f64_cast == bytes_f32_cast
    assert len(bytes_f32_cast) == 8  # 2 floats * 4 bytes
    
def test_mantel_two_sided_option():
    """Verify that two_sided flag correctly adjusts p-value."""
    # Create two matrices that are strongly negatively correlated
    n = 6 # (6*5)/2 = 15 elements (passes the < 10 check)
    mat_a = np.zeros((n, n))
    mat_b = np.zeros((n, n))
    
    # Fill upper tri with opposite arrays
    idx = np.triu_indices(n, 1)
    
    # 15 elements
    va_pad = np.arange(1, 16, dtype=np.float64)
    vb_pad = np.arange(15, 0, -1, dtype=np.float64)
    
    mat_a[idx] = va_pad
    mat_a[(idx[1], idx[0])] = va_pad
    mat_b[idx] = vb_pad
    mat_b[(idx[1], idx[0])] = vb_pad
    
    # One-sided test (default): checks if null >= observed (which is highly negative)
    # A highly negative observed value will be smaller than ~all null values, so p_value ≈ 1.0
    res_one_sided = mantel_test(mat_a, mat_b, n_perm=99, two_sided=False)
    assert res_one_sided.observed_r < -0.9
    assert res_one_sided.p_value > 0.9  # One sided test sees no POSITIVE correlation
    
    # Two-sided test: checks if abs(null) >= abs(observed)
    # The strong negative correlation should be detected as significant
    res_two_sided = mantel_test(mat_a, mat_b, n_perm=99, two_sided=True)
    assert res_two_sided.observed_r < -0.9
    assert res_two_sided.p_value < 0.1  # Two sided test sees SIGNIFICANT negative correlation

def test_report_json_contains_required_fields():
    """Verify the export output structure."""
    
    # Mock minimal batch result
    fp = GeometricFingerprint(
        model_id="test/m1", timestamp="2024", surface_matrix=np.ones((2,2)), deep_matrix=None,
        washing_deltas=None, valid_anchor_indices=[0,1], valid_anchor_tokens=["a","b"],
        anchor_coverage=1.0, deep_layer_index=None, vocab_size=100, hidden_dim=64, fingerprint_hash="hash"
    )
    
    res = BatchResult(
        run_id="run-123",
        timestamp="now",
        models_analyzed=["test/m1"],
        fingerprints={"test/m1": fp},
        comparisons={},
        washing_profiles={},
        anchor_set_hash="hash123",
        total_time_s=1.0
    )
    
    from unittest.mock import patch
    
    # Mock the internal signature function just to test structure assembly
    with patch('croviapro.sonar_v2.geometric_dna._sign_report', return_value={"sig": "abc"}):
        out = export_signed_report(res)
        
        assert "report" in out
        assert "signatures" in out
        
        rep = out["report"]
        assert rep["run_id"] == "run-123"
        assert rep["engine_version"] == "geometric-dna-v1.0.0"
        assert rep["anchor_set_hash"] == "hash123"
        assert "fingerprints" in rep
