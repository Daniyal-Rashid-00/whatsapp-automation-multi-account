import time
from unittest.mock import patch, MagicMock
import pytest
from database import init_db, clear_db, get_db_connection
from queue_processor import DurableQueueProcessor

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    clear_db()
    yield
    clear_db()

def test_database_connection_pragmas():
    conn = get_db_connection()
    sync_mode = conn.execute("PRAGMA synchronous;").fetchone()[0]
    cache_size = conn.execute("PRAGMA cache_size;").fetchone()[0]
    conn.close()

    # In SQLite, NORMAL is 1
    assert sync_mode == 1
    assert cache_size == -8000

def test_get_cached_rules_avoids_repeated_disk_reads():
    processor = DurableQueueProcessor()

    with patch("queue_processor.get_all_rules") as mock_get_rules:
        mock_get_rules.return_value = [{"id": 1, "rule_name": "Test Rule", "keyword": "hi"}]

        # First call loads rules
        rules1 = processor.get_cached_rules()
        assert len(rules1) == 1
        assert mock_get_rules.call_count == 1

        # Second and third calls within 3s TTL return cached copy without disk read
        rules2 = processor.get_cached_rules()
        rules3 = processor.get_cached_rules()
        assert mock_get_rules.call_count == 1
        assert rules2 == rules1
        assert rules3 == rules1

        # Force expiry
        processor._rules_last_fetch = time.time() - 4.0
        rules4 = processor.get_cached_rules()
        assert mock_get_rules.call_count == 2
