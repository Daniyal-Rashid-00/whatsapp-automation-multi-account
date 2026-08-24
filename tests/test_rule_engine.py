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
        {"id": 1, "rule_name": "R1", "matching_operator": "Start with", "keyword_payload": "hi", "response_message": "Hello!", "is_enabled": 1},
        {"id": 2, "rule_name": "R2", "matching_operator": "Contains", "keyword_payload": "price", "response_message": "Price is 100", "is_enabled": 1}
    ]
    matched = match_inbound_message("hi, what is the price?", rules)
    assert matched is not None
    assert matched["id"] == 1
