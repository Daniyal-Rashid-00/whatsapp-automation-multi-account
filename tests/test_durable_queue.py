import os
import sys
import pytest
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import (
    init_db,
    clear_db,
    is_message_duplicate,
    enqueue_inbound_message,
    fetch_pending_messages,
    update_queue_status,
    get_queue_metrics
)

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    clear_db()

def test_deduplication():
    msg_id = "test_msg_unique_101"
    assert is_message_duplicate(msg_id) is False
    # Second time should return True (duplicate)
    assert is_message_duplicate(msg_id) is True

def test_queue_persistence_and_status():
    import uuid
    msg_id = f"test_queue_msg_{uuid.uuid4().hex}"
    chat_id = "123456789@c.us"
    body = "Test body content"
    raw_payload = '{"event": "message"}'

    # Enqueue
    success = enqueue_inbound_message(msg_id, chat_id, body, raw_payload)
    assert success is True

    # Duplicate enqueue should return False
    duplicate_success = enqueue_inbound_message(msg_id, chat_id, body, raw_payload)
    assert duplicate_success is False

    # Fetch pending
    pending = fetch_pending_messages(limit=10)
    assert any(m['message_id'] == msg_id for m in pending)

    # Update status to done
    update_queue_status(msg_id, "done")
    
    metrics = get_queue_metrics()
    assert metrics['done'] >= 1

def test_queue_failed_status():
    import uuid
    msg_id = f"test_failed_msg_{uuid.uuid4().hex}"
    chat_id = "987654321@c.us"
    body = "Fail test"
    raw_payload = '{"event": "message"}'

    assert enqueue_inbound_message(msg_id, chat_id, body, raw_payload) is True
    update_queue_status(msg_id, "failed")

    metrics = get_queue_metrics()
    assert metrics['failed'] >= 1

