import pytest
from unittest.mock import patch, MagicMock
from croviapro.sonar_v2.oras_engine import _query_model, _check_endpoint_availability, execute_oras_epoch

def test_router_client_mocked_success():
    """Mock a 200 OK from the router to verify parsing and OpenAI compat."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.json.return_value = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": " This is a mocked answer  "
            },
            "finish_reason": "stop"
        }]
    }
    
    with patch("requests.post", return_value=mock_resp) as mock_post:
        text, status, error, retry = _query_model("some/model", "test prompt", "hf_mock_token")
        
        # Must strip and collapse whitespace
        assert text == "This is a mocked answer"
        assert status == 200
        assert error == ""
        
        # Verify kwargs
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["model"] == "some/model"
        assert call_kwargs["json"]["messages"][0]["content"] == "test prompt"
        assert "Authorization" in call_kwargs["headers"]

def test_local_prefix_disabled_by_default():
    """Verify that using the local: prefix without explicit env var fails cleanly."""
    import os
    if "ORAS_ALLOW_LOCAL" in os.environ:
        del os.environ["ORAS_ALLOW_LOCAL"]
        
    text, status, error, retry = _query_model("local:gpt2", "test", None)
    assert status == 403
    assert error == "local_disabled"
    assert text == ""
    
    avail, status_pre, retry_pre = _check_endpoint_availability("local:gpt2", None)
    assert avail is False
    assert status_pre == 403

def test_smoke_stops_on_first_success():
    """This logic is tested via the CLI in oras_smoke.py. 
    Here we just verify that a simulated NO_ENDPOINT returns properly without crashing."""
    mock_data = {"status_code": 404} # Simulate NO_ENDPOINT
    res = execute_oras_epoch("nonexistent/model", 100, is_mock=True, mock_data=mock_data)
    assert res["status"] == "NO_ENDPOINT"
