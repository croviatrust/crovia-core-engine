import pytest
from croviapro.sonar_v2.oras_engine import (
    normalize_response,
    compute_affinity,
    execute_oras_epoch,
    generate_real_entities,
    generate_phantom_entities
)

def test_refusal_stripping():
    assert normalize_response("As an AI, I cannot provide this.") == set()
    assert normalize_response("I apologize, but I am unable to assist with that.") == set()
    assert normalize_response("This is against my programming.") == set()
    assert normalize_response("I'm unable to do that.") == set()
    
def test_normalization_invariance():
    # Formatting and case should not matter
    r1 = "The Ischemia refers to blood restriction!"
    r2 = "the ischemia refers to... blood restriction"
    assert normalize_response(r1) == normalize_response(r2)
    assert "ischemia" in normalize_response(r1)

def test_affinity_calculation():
    # 4 identical responses -> collision on all -> affinity 1.0
    resps = ["apple banana", "apple banana", "apple banana", "apple banana"]
    assert compute_affinity(resps) == 1.0
    
    # 4 completely different responses -> no collisions -> affinity 0.0
    resps_diff = ["apple", "banana", "cherry", "date"]
    assert compute_affinity(resps_diff) == 0.0
    
    # Partial collision: "apple" in 2, "banana" in 1 -> U=2, I=1 -> 0.5
    resps_partial = ["apple", "apple", "banana", ""]
    assert compute_affinity(resps_partial) == 0.5
    
def test_duplicate_probe_safety():
    # If the model repeats the exact same word 10 times in ONE response, 
    # it shouldn't count as a collision across angles.
    resps = ["apple apple apple", "banana", "cherry", "date"]
    assert compute_affinity(resps) == 0.0

def test_execute_oras_epoch_determinism():
    mock_data = {
        "real": {
            "entity1": {"completion": "test test", "question": "test test", "reverse": "test", "context": "test"}
        },
        "phantom": {
            "entity1": {"completion": "a", "question": "b", "reverse": "c", "context": "d"}
        }
    }
    
    # Run 1
    res1 = execute_oras_epoch("test/model", 100, is_mock=True, mock_data=mock_data)
    
    # Run 2
    res2 = execute_oras_epoch("test/model", 100, is_mock=True, mock_data=mock_data)
    
    assert res1["canonical_input_hash"] == res2["canonical_input_hash"]
    assert res1["artifact_hash"] == res2["artifact_hash"]
    
    # Check baseline correctness (real > phantom -> positive)
    assert res1["value"] >= 0.0

def test_chain_root_seed_binding():
    """Verify that changing the chain_root_hash changes the canonical input hash."""
    mock_data = {
        "status_code": 200,
        "real_entities": ["entity1"],
        "phantom_entities": ["phantom1"],
        "real": {
            "entity1": {"completion": "ok", "question": "ok", "reverse": "ok", "context": "ok"}
        },
        "phantom": {
            "phantom1": {"completion": "ok", "question": "ok", "reverse": "ok", "context": "ok"}
        }
    }
    res1 = execute_oras_epoch("test/model", 100, chain_root_hash="aaa", is_mock=True, mock_data=mock_data)
    res2 = execute_oras_epoch("test/model", 100, chain_root_hash="bbb", is_mock=True, mock_data=mock_data)
    
    assert res1["status"] == "OK"
    assert res2["status"] == "OK"
    assert res1["canonical_input_hash"] != res2["canonical_input_hash"]
    
def test_timeout_and_refusal_rates():
    """Verify that failures and refusals are tracked distinctly."""
    mock_data = {
        "status_code": 200, # Operational preflight
        "real_entities": ["entity1"],
        "phantom_entities": [],
        "real": {
            "entity1": {
                # We inject _status to force a 500 (failure, but not a lockout)
                "completion": "_STATUS:500", 
                "question": "As an AI, I cannot provide this", # Refusal
                "reverse": "valid words test", # Success
                "context": "valid words test"  # Success
            }
        },
        "phantom": {}
    }
    
    # We must patch the mock evaluation loop to respect _STATUS
    import croviapro.sonar_v2.oras_engine as engine
    original_eval = engine._evaluate_entities
    
    def patched_eval(entities, model_id, hf_token, is_mock, mock_responses, mock_status_code):
        # We manually process the mock data to set status codes
        results = []
        affinities = []
        refusal_count = 0
        failure_count = 0
        
        for entity in entities:
            angles = engine.build_orthogonal_prompts(entity)
            angle_results = {}
            responses = []
            for angle_name, prompt in angles.items():
                resp = mock_responses.get(entity, {}).get(angle_name, "")
                status = mock_status_code
                if resp.startswith("_STATUS:"):
                    status = int(resp.split(":")[1])
                    resp = ""
                    
                if status == 500:
                    failure_count += 1
                    norm_set = set()
                elif "As an AI" in resp:
                    refusal_count += 1
                    norm_set = set()
                else:
                    norm_set = engine.normalize_response(resp)
                    
                responses.append(resp)
                angle_results[angle_name] = {
                    "prompt_hash": "hash",
                    "raw_response_hash": "hash",
                    "normalized_token_set": sorted(list(norm_set)),
                    "status_code": status
                }
                
            aff = engine.compute_affinity(responses)
            affinities.append(aff)
            results.append({"entity": entity, "angles": angle_results, "affinity": aff})
            
        return results, sum(affinities)/len(affinities) if affinities else 0.0, refusal_count/4.0, failure_count/4.0, 0.0, False, None, None

    from unittest.mock import patch
    with patch("croviapro.sonar_v2.oras_engine._evaluate_entities", side_effect=patched_eval):
        res = engine.execute_oras_epoch("test/model", 100, is_mock=True, mock_data=mock_data, k_real=1, k_phantom=0)
        
    metrics = res["evidence_pack"]["metrics"]
    
    assert metrics["failure_rate_real"] == 0.25
    assert metrics["refusal_rate_real"] == 0.25

def test_preflight_endpoint_unavailable():
    """Verify that models throwing 410 Gone fail gracefully without full execution."""
    mock_data = {"status_code": 410} # Unavailable preflight
    
    res = execute_oras_epoch("test/model_gone", 100, is_mock=True, mock_data=mock_data)
    
    assert res["status"] == "NO_ENDPOINT"
    assert res["value"] == 0.0
    
    metrics = res["evidence_pack"]["metrics"]
    assert metrics["endpoint_unavailable_rate_real"] == 1.0
    assert metrics["endpoint_unavailable_rate_phantom"] == 1.0
    assert metrics["failure_rate_real"] == 0.0

def test_preflight_lockout():
    """Verify that models throwing 429 trigger a lockout immediately."""
    mock_data = {"status_code": 429} # Lockout preflight
    
    res = execute_oras_epoch("test/model_rate_limited", 100, is_mock=True, mock_data=mock_data)
    
    assert res["status"] == "LOCKOUT"
    assert res["value"] == 0.0
    
    metrics = res["evidence_pack"]["metrics"]
    assert metrics["lockout_triggered"] is True
    assert metrics["lockout_code"] == 429
    assert metrics["retry_after_s"] >= 60

def test_fail_fast_on_429():
    """Verify that if an evaluation gets a 429, it breaks the loop and bubbles up a lockout."""
    # Start with 200, but when asking for real entity, hit 429
    mock_data = {
        "status_code": 200, # Preflight passes
        "real_entities": ["entity1"],
        "phantom_entities": [],
        "real": {
            "entity1": {
                "completion": "", # Fail but not lockout
                "question": "As an AI, I cannot provide this", # Refusal
                "reverse": "", # Will map to 408 timeout which triggers lockout in evaluation
                "context": ""  # Should not be reached
            }
        },
        "phantom": {}
    }
    
    res = execute_oras_epoch("test/model", 100, is_mock=True, mock_data=mock_data, k_real=1, k_phantom=0)
    
    assert res["status"] == "LOCKOUT"
    assert res["value"] == 0.0
    
    metrics = res["evidence_pack"]["metrics"]
    assert metrics["lockout_triggered"] is True
    assert metrics["lockout_code"] == 408

def test_real_entities_deterministic_ordering():
    """Verify that multiple calls with the same seed return identical lists (including exact order)."""
    # This also exercises the ordered deduplication logic inside generate_real_entities
    res1 = generate_real_entities(seed=12345, count=15)
    res2 = generate_real_entities(seed=12345, count=15)
    assert res1 == res2, "Real entity generation must be strictly deterministic including order"

def test_empty_probe_library_safety():
    """Verify fallback behavior if the valid words pool is artificially emptied."""
    from unittest.mock import patch
    
    # We patch the latent_probes json reading to return an empty dict
    with patch("json.load", return_value={}):
        res = generate_real_entities(seed=42, count=5)
        assert len(res) == 5, "Must fallback to exact requested count"
        assert all(r.startswith("fallback_entity_") for r in res)
        
        # Second call should match exactly
        res2 = generate_real_entities(seed=42, count=5)
        assert res == res2

def test_phantom_generation_tiny_vocab():
    """Verify generate_phantom_entities handles a tiny vocab tokenizer without infinite loops and uses fallbacks to reach exact count."""
    class MockTinyTokenizer:
        def __init__(self):
            # Only one valid token
            self.vocab = {0: "valid", 1: "!", 2: "   "}
        def __len__(self):
            return len(self.vocab)
        def decode(self, ids):
            return self.vocab.get(ids[0], "")
            
    from unittest.mock import patch, MagicMock
    
    # Patch the tokenizer loading to return our tiny mock
    mock_from_pretrained = MagicMock(return_value=MockTinyTokenizer())
    
    with patch("transformers.AutoTokenizer.from_pretrained", mock_from_pretrained):
        # We request 5 phantoms, but there is only 1 valid token, so it will fail to generate 5 unique combinations
        res = generate_phantom_entities(
            model_id="mock/tiny", 
            seed=123, 
            real_entities=["some", "real", "words"], 
            count=5
        )
        assert len(res) == 5, "Must fallback to exact requested count when generation runs out of unique combos"
        # It shouldn't crash, it should just pad with fallbacks
        assert any("phantom_" in r and "_token" in r for r in res)
