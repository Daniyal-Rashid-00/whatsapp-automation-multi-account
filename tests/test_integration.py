import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import init_db, clear_db, get_all_rules, add_rule, fetch_pending_messages, update_queue_status
from webhook_server import app
from rule_engine import match_inbound_message

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    clear_db()

def test_webhook_ingestion_and_dedup():
    payload = {
        "event": "message",
        "session": "default",
        "engine": "NOWEB",
        "payload": {
            "id": "integration_msg_001",
            "timestamp": 1783637700,
            "type": "message",
            "from": "923009998877@c.us",
            "fromMe": False,
            "body": "What is the price of your special hoodie?",
            "hasMedia": False
        }
    }

    # First POST -> enqueued
    response = client.post("/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "enqueued"

    # Second POST -> duplicate dropped
    response_dup = client.post("/webhook", json=payload)
    assert response_dup.status_code == 200
    assert response_dup.json()["status"] == "duplicate_dropped"

    # Check pending message in queue
    pending = fetch_pending_messages(limit=10)
    assert any(m["message_id"] == "integration_msg_001" for m in pending)

def test_rule_matching_end_to_end():
    # Add rule
    add_rule(
        name="Hoodie Pricing",
        operator="Contains",
        keyword="hoodie, price",
        response="Our Special Edition Hoodie is *2500 PKR* with free shipping! 🔥",
        is_enabled=1
    )

    rules = get_all_rules()
    matched = match_inbound_message("What is the price of your special hoodie?", rules)
    assert matched is not None
    assert matched["rule_name"] == "Hoodie Pricing"
    assert "2500 PKR" in matched["response_message"]
