import asyncio
import random
import logging
from typing import Tuple
from database import get_setting, get_today_send_count, record_send

async def check_and_apply_rate_limit(chat_id: str) -> Tuple[bool, str]:
    """
    Checks daily send cap and enforces minimum delay + jitter before outbound send.
    Returns (allowed: bool, reason: str).
    """
    try:
        daily_cap = int(get_setting("send_daily_cap", "800"))
    except ValueError:
        daily_cap = 800

    current_sends = get_today_send_count()
    if current_sends >= daily_cap:
        msg = f"Send blocked: Daily cap reached ({current_sends}/{daily_cap})"
        logging.warning(msg)
        return False, msg

    try:
        min_delay = float(get_setting("send_min_delay_seconds", "2.5"))
    except ValueError:
        min_delay = 2.5

    try:
        jitter = float(get_setting("send_jitter_seconds", "1.5"))
    except ValueError:
        jitter = 1.5

    # Compute delay with jitter — allow 0.0s when min_delay and jitter are set to 0
    actual_delay = min_delay + random.uniform(-jitter, jitter)
    actual_delay = max(0.0, actual_delay)

    if actual_delay > 0.001:
        await asyncio.sleep(actual_delay)
    
    # Record send in database log
    record_send(chat_id)
    return True, "OK"
