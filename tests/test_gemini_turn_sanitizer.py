import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from database import init_db, clear_db
from ai_engine import build_gemini_contents, generate_ai_response, key_pool

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    clear_db()
    yield
    clear_db()

def test_build_gemini_contents_empty_history():
    user_parts = [{"text": "Hello, LED frame price?"}]
    contents = build_gemini_contents(None, user_parts)
    assert len(contents) == 1
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"] == user_parts

def test_build_gemini_contents_merges_consecutive_user_turns():
    # Customer sent two messages in a row
    history = [
        {"role": "user", "content": "Price of LED frame?"},
        {"role": "user", "content": "Also delivery charges?"}
    ]
    user_parts = [{"text": "Delivery kab hogi?"}]
    contents = build_gemini_contents(history, user_parts)

    # All three are user turns; they should be merged into a single user turn to maintain Gemini validity
    assert len(contents) == 1
    assert contents[0]["role"] == "user"
    assert len(contents[0]["parts"]) == 3
    assert contents[0]["parts"][0]["text"] == "Price of LED frame?"
    assert contents[0]["parts"][1]["text"] == "Also delivery charges?"
    assert contents[0]["parts"][2]["text"] == "Delivery kab hogi?"

def test_build_gemini_contents_drops_leading_model_turn():
    # History accidentally starts with an assistant turn
    history = [
        {"role": "assistant", "content": "Assalam o Alaikum, kaise madad karoon?"},
        {"role": "user", "content": "LED Frame kitne ka hai?"},
        {"role": "assistant", "content": "LED Frame 2350 total hai."}
    ]
    user_parts = [{"text": "Delivery time kitna lagta hai?"}]
    contents = build_gemini_contents(history, user_parts)

    # First turn must be 'user'
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0]["text"] == "LED Frame kitne ka hai?"
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][0]["text"] == "LED Frame 2350 total hai."
    assert contents[2]["role"] == "user"
    assert contents[2]["parts"][0]["text"] == "Delivery time kitna lagta hai?"

def test_build_gemini_contents_alternating_turns():
    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "Price?"},
        {"role": "assistant", "content": "Fix ha"}
    ]
    user_parts = [{"text": "Order karna hai"}]
    contents = build_gemini_contents(history, user_parts)

    assert len(contents) == 5
    roles = [c["role"] for c in contents]
    assert roles == ["user", "model", "user", "model", "user"]

def test_gemini_http_400_does_not_ban_key():
    # Test that HTTP 400 does NOT ban key for 86400s
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "Bad Request: role alternating constraint violated"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch.object(key_pool, "get_gemini_keys", return_value=["test-key-1"]), \
         patch.object(key_pool, "get_next_gemini_key", return_value="test-key-1"), \
         patch.object(key_pool, "mark_rate_limited") as mock_rate_limit, \
         patch("httpx.AsyncClient", return_value=mock_client):

        asyncio.run(generate_ai_response(
            sender_id="923001234567",
            inbound_body="Test 400 error handling",
            conversation_history=[]
        ))

        # Ensure mark_rate_limited was NOT called with 86400 on HTTP 400
        calls_86400 = [call for call in mock_rate_limit.call_args_list if call.kwargs.get("cooldown_seconds") == 86400.0]
        assert len(calls_86400) == 0

def test_gemini_http_401_bans_invalid_key():
    # Test that HTTP 401 DOES ban invalid key
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized: API_KEY_INVALID"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch.object(key_pool, "get_gemini_keys", return_value=["test-key-invalid"]), \
         patch.object(key_pool, "get_next_gemini_key", return_value="test-key-invalid"), \
         patch.object(key_pool, "mark_rate_limited") as mock_rate_limit, \
         patch("httpx.AsyncClient", return_value=mock_client):

        asyncio.run(generate_ai_response(
            sender_id="923001234567",
            inbound_body="Test 401 invalid key",
            conversation_history=[]
        ))

        # Ensure mark_rate_limited WAS called with 86400 on HTTP 401
        calls_86400 = [call for call in mock_rate_limit.call_args_list if call.kwargs.get("cooldown_seconds") == 86400.0]
        assert len(calls_86400) > 0
