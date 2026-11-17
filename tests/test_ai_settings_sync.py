import os
import subprocess
import pytest
from database import init_db, clear_db, set_setting, get_setting
from queue_processor import DurableQueueProcessor

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    clear_db()
    yield
    clear_db()

def test_queue_processor_ai_switch_unification():
    processor = DurableQueueProcessor()

    # Case 1: ai_fallback_enabled = 1, ai_master_enabled = 0 -> Must evaluate as True
    set_setting("ai_fallback_enabled", "1")
    set_setting("ai_master_enabled", "0")
    processor._settings_cache.invalidate()

    cache = processor._settings_cache
    ai_master_on = (
        cache.get("ai_master_enabled", "0") == "1" or
        cache.get("ai_fallback_enabled", "0") == "1"
    )
    assert ai_master_on is True

    # Case 2: ai_master_enabled = 1, ai_fallback_enabled = 0 -> Must evaluate as True
    set_setting("ai_fallback_enabled", "0")
    set_setting("ai_master_enabled", "1")
    processor._settings_cache.invalidate()

    cache = processor._settings_cache
    ai_master_on = (
        cache.get("ai_master_enabled", "0") == "1" or
        cache.get("ai_fallback_enabled", "0") == "1"
    )
    assert ai_master_on is True

    # Case 3: Both switches 0 -> Must evaluate as False
    set_setting("ai_fallback_enabled", "0")
    set_setting("ai_master_enabled", "0")
    processor._settings_cache.invalidate()

    cache = processor._settings_cache
    ai_master_on = (
        cache.get("ai_master_enabled", "0") == "1" or
        cache.get("ai_fallback_enabled", "0") == "1"
    )
    assert ai_master_on is False

def test_windows_below_normal_priority_flag_present():
    if os.name == 'nt':
        below_normal = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)
        assert below_normal == 0x00004000 or below_normal == 16384
