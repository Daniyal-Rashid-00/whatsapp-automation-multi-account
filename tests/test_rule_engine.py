import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from rule_engine import evaluate_rule_match, match_inbound_message

def test_exact_match():
    assert evaluate_rule_match("hello", "=", "hello") is True
    assert evaluate_rule_match("Hello", "=", "hello") is True
    assert evaluate_rule_match("hello world", "=", "hello") is False

def test_contains_match():
    assert evaluate_rule_match("what is the price today?", "Contains", "price") is True
    assert evaluate_rule_match("discount code", "Contains", "price, discount, promo") is True
    assert evaluate_rule_match("something else", "Contains", "price") is False

def test_start_with_match():
    assert evaluate_rule_match("hi there", "Start with", "hi, hello") is True
    assert evaluate_rule_match("say hi", "Start with", "hi") is False

def test_end_with_match():
    assert evaluate_rule_match("need refund", "End with", "refund") is True
    assert evaluate_rule_match("refund please", "End with", "refund") is False

def test_sql_like_wildcard_matching():
    # TRD Section 3.3 test cases
    assert evaluate_rule_match("50% off today", "Like", "50%off") is False
    assert evaluate_rule_match("discount code applies", "Like", "disc%applies") is True
    assert evaluate_rule_match("cat", "Like", "c_t") is True
    assert evaluate_rule_match("cot", "Like", "c_t") is True
    assert evaluate_rule_match("ct", "Like", "c_t") is False

def test_match_inbound_message_priority():
    rules = [
        {"id": 1, "rule_name": "R1", "matching_operator": "Start with", "keyword_payload": "hi", "response_message": "Hello!", "is_enabled": 1, "account_target": "ALL"},
        {"id": 2, "rule_name": "R2", "matching_operator": "Contains", "keyword_payload": "price", "response_message": "Price is 100", "is_enabled": 1, "account_target": "ALL"}
    ]
    matched = match_inbound_message("hi, what is the price?", rules)
    assert matched is not None
    assert matched["id"] == 1

def test_account_specific_rule_matching_and_isolation():
    rules = [
        {"id": 10, "rule_name": "Global Price", "matching_operator": "Contains", "keyword_payload": "price", "response_message": "Global Price is 100", "is_enabled": 1, "account_target": "ALL"},
        {"id": 11, "rule_name": "GC-003 Special", "matching_operator": "Contains", "keyword_payload": "vip", "response_message": "GC-003 VIP reply", "is_enabled": 1, "account_target": "account_gc-003"},
        {"id": 12, "rule_name": "HG Exclusive", "matching_operator": "Contains", "keyword_payload": "vip", "response_message": "HG VIP reply", "is_enabled": 1, "account_target": "account_hg"},
        {"id": 13, "rule_name": "HG Custom Price", "matching_operator": "Contains", "keyword_payload": "price", "response_message": "HG Wholesale Price is 70", "is_enabled": 1, "account_target": "account_hg"}
    ]

    # Case 1: Message on account_gc-003 with keyword "vip" -> Should match rule 11 ONLY
    m_gc = match_inbound_message("I am a vip customer", rules, session_name="account_gc-003")
    assert m_gc is not None
    assert m_gc["id"] == 11

    # Case 2: Message on account_hg with keyword "vip" -> Should match rule 12 ONLY
    m_hg = match_inbound_message("I am a vip customer", rules, session_name="account_hg")
    assert m_hg is not None
    assert m_hg["id"] == 12

    # Case 3: Message on account_other with keyword "vip" -> Should match None (since rules 11 & 12 are account-specific)
    m_other = match_inbound_message("I am a vip customer", rules, session_name="account_other")
    assert m_other is None

    # Case 4: Account-specific priority over global rule
    # account_hg with "price" matches rule 13 (specific) over rule 10 (global)
    m_hg_price = match_inbound_message("what is the price?", rules, session_name="account_hg")
    assert m_hg_price is not None
    assert m_hg_price["id"] == 13
    assert m_hg_price["response_message"] == "HG Wholesale Price is 70"

    # Case 5: account_gc-003 with "price" falls back to rule 10 (global) because it has no specific price rule
    m_gc_price = match_inbound_message("what is the price?", rules, session_name="account_gc-003")
    assert m_gc_price is not None
    assert m_gc_price["id"] == 10
    assert m_gc_price["response_message"] == "Global Price is 100"

