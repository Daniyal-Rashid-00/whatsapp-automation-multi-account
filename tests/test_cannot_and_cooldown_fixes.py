import pytest
from ai_engine import sanitize_ai_reply
from database import (
    init_db,
    clear_db,
    record_reply_timestamp,
    is_cooldown_active,
    was_recently_replied_by_bot,
    was_recently_sent_same_message,
    remember_lid_mapping,
    save_conversation_turn,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    clear_db()


def test_sanitize_blocks_cannot_variants():
    """Verify that any variant of CANNOT or CANNOT_ANSWER is silenced to an empty string."""
    assert sanitize_ai_reply("CANNOT") == ""
    assert sanitize_ai_reply("cannot") == ""
    assert sanitize_ai_reply("CANNOT.") == ""
    assert sanitize_ai_reply("cannot.") == ""
    assert sanitize_ai_reply("CAN NOT") == ""
    assert sanitize_ai_reply("can not") == ""
    assert sanitize_ai_reply("CANNOT_ANSWER") == ""
    assert sanitize_ai_reply("cannot_answer.") == ""
    assert sanitize_ai_reply("i cannot") == ""
    assert sanitize_ai_reply("I cannot answer.") == ""
    assert sanitize_ai_reply("cannot answer") == ""
    assert sanitize_ai_reply("(no response)") == ""
    assert sanitize_ai_reply("[no response]") == ""


def test_sanitize_allows_valid_customer_replies():
    """Ensure legitimate Urdu responses pass through unchanged."""
    valid_1 = "Delivery 3 se 5 din lagti hai, inshallah jaldi aa jia ga."
    valid_2 = "Fix ha, already best price ha."
    valid_3 = "Price 1650 and 200 delivery charges"

    assert sanitize_ai_reply(valid_1) == valid_1
    assert sanitize_ai_reply(valid_2) == valid_2
    assert sanitize_ai_reply(valid_3) == valid_3


def test_was_recently_sent_same_message():
    """Verify exact duplicate response detection within anti-repetition window."""
    chat_id = "test_rep_998877@lid"
    reply_text = "Fix ha, already best price ha."

    # Before saving, should be False
    assert was_recently_sent_same_message(chat_id, reply_text, within_minutes=5.0) is False

    # Save turn
    save_conversation_turn(chat_id, "default", "assistant", reply_text)

    # Now should detect exact duplicate
    assert was_recently_sent_same_message(chat_id, reply_text, within_minutes=5.0) is True
    assert was_recently_sent_same_message(chat_id, "fix ha, already  best price ha.", within_minutes=5.0) is True

    # Different message text should not trigger duplicate
    assert was_recently_sent_same_message(chat_id, "Delivery 3 se 5 din lagti hai", within_minutes=5.0) is False


def test_cooldown_lid_phone_dual_tracking():
    """Verify cooldown records and checks seamlessly across linked @lid and @c.us JIDs."""
    lid_jid = "8899001122@lid"
    phone_jid = "923119988776@c.us"
    phone_digits = "923119988776"

    # Map LID to phone
    remember_lid_mapping(lid_jid, phone_digits)

    # Record reply using LID
    record_reply_timestamp(lid_jid)

    # Cooldown should be active for BOTH LID and phone JID!
    assert is_cooldown_active(lid_jid, cooldown_seconds=60.0) is True
    assert is_cooldown_active(phone_jid, cooldown_seconds=60.0) is True
    assert was_recently_replied_by_bot(phone_jid, within_seconds=30) is True
