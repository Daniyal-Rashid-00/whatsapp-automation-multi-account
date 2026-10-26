import pytest
from rule_engine import is_session_target_match, match_inbound_message
from queue_processor import _should_prefilter_message
from database import cleanup_stale_records, get_setting
from ai_engine import build_llm_request

def test_session_target_matching():
    assert is_session_target_match("account_gc", "account_gc") is True
    assert is_session_target_match("account_gc", "gc") is True
    assert is_session_target_match("gc", "account_gc") is True
    assert is_session_target_match("GC", "account_gc") is True
    assert is_session_target_match("account_gc", "GC") is True
    assert is_session_target_match("account_hg", "account_gc") is False
    assert is_session_target_match("hg", "account_gc") is False

def test_rule_matching_with_session_normalization():
    rules = [
        {
            "id": 1,
            "rule_name": "GC Watch",
            "matching_operator": "Contains",
            "keyword_payload": "watch price",
            "response_message": "Watch is 1850",
            "account_target": "account_gc",
            "is_enabled": 1
        },
        {
            "id": 2,
            "rule_name": "Global COD",
            "matching_operator": "Contains",
            "keyword_payload": "cod",
            "response_message": "COD available",
            "account_target": "ALL",
            "is_enabled": 1
        }
    ]

    # Session passed as 'gc' matches rule targeted to 'account_gc'
    m1 = match_inbound_message("watch price kya hai?", rules, session_name="gc")
    assert m1 is not None
    assert m1["rule_name"] == "GC Watch"

    # Session passed as 'account_gc' also matches
    m2 = match_inbound_message("watch price kya hai?", rules, session_name="account_gc")
    assert m2 is not None
    assert m2["rule_name"] == "GC Watch"

    # Session passed as 'account_hg' does NOT match GC rule, falls to None or global
    m3 = match_inbound_message("watch price kya hai?", rules, session_name="account_hg")
    assert m3 is None

def test_prefilter_does_not_drop_inquiries():
    # Inquiries mentioning cities or near should NOT be dropped as addresses
    assert _should_prefilter_message("kya lahore near gulberg delivery ho jaye gi?", is_voice=False) is None
    assert _should_prefilter_message("gujranwala delivery charges kitne hain?", is_voice=False) is None
    assert _should_prefilter_message("karachi deliver karte ho?", is_voice=False) is None

    # Pure acknowledgements SHOULD still be dropped
    assert _should_prefilter_message("ok", is_voice=False) == "pure acknowledgement"
    assert _should_prefilter_message("theek hai thanks", is_voice=False) is not None

    # Genuine address submissions SHOULD still be dropped
    real_addr = "house 14 street 2 near bilal masjid lahore 03001234567"
    assert _should_prefilter_message(real_addr, is_voice=False) is not None

def test_ai_temperature_and_guidelines():
    req = build_llm_request(
        rules_context="- Topic: Test",
        context_box_text="Test base system",
        sender_id="923001234567@c.us",
        source_hint=None,
        inbound_body="hello",
        model_id="gemini-3.5-flash-lite"
    )
    assert req["generation_config"]["temperature"] == 0.35
    assert "ANTI-REPETITION" in req["system_instruction"]

def test_cleanup_stale_records_runs_safely():
    cleanup_stale_records()
