import asyncio
import json
import logging
import re
import time
from typing import Optional, Dict, Any, List

from database import (
    get_db_connection,
    fetch_pending_messages,
    update_queue_status,
    get_all_rules,
    get_setting,
    is_human_takeover_active,
    is_cooldown_active,
    record_reply_timestamp,
    is_number_excluded,
    get_phone_for_lid,
    get_conversation_history,
    save_conversation_turn,
)
from rule_engine import match_inbound_message
from ai_engine import generate_ai_response
from rate_governor import check_and_apply_rate_limit
from waha_client import WAHAClient

# =============================================================================
# Code-Level Pre-Filter Constants & Guard Logic
# =============================================================================

_ACK_PHRASES = {
    "ok", "okay", "k", "g", "ji", "hm", "hmm", "ha", "han", "haan",
    "theek", "theek ha", "theek hai", "thik ha", "thik hai", "thk", "thk ha", "thk hai",
    "accha", "acha", "achha", "acha ji", "accha ji", "achha ji",
    "thanks", "thank you", "thx", "shukriya", "shukria", "jazakallah", "jazak allah",
    "noted", "got it", "seen", "read", "received",
    "inshallah", "inshaallah", "insha allah", "mashallah", "mashaallah",
    "welcome", "wc", "np", "no problem", "done",
    "👍", "✅", "🙏", "👌", "😊", "❤️"
}

_ADDRESS_KEYWORDS = {
    "gali", "mohalla", "street", "road", "block", "sector", "phase",
    "house", "flat", "floor", "near", "opposite", "opp",
    "colony", "town", "city", "district", "tehsil", "lahore", "karachi",
    "islamabad", "rawalpindi", "faisalabad", "multan", "gujranwala",
    "peshawar", "quetta", "sialkot", "gujrat", "postal", "zip",
    "village", "chak", "teh", "distt", "dakkhana", "post office",
}


def _should_prefilter_message(body: str, is_voice: bool) -> Optional[str]:
    """
    Checks if an inbound text message should be filtered out at code-level before reaching AI.
    Returns a reason string ('acknowledgement' or 'address') if it should be dropped, or None if it should proceed.
    """
    if is_voice or not body:
        return None

    body_clean = body.strip().lower()

    # 1. Pure acknowledgement check (exact or clean punctuation)
    clean_punc = re.sub(r'[^\w\s]', '', body_clean).strip()
    if body_clean in _ACK_PHRASES or clean_punc in _ACK_PHRASES:
        return "pure acknowledgement"

    words = clean_punc.split()
    if 1 <= len(words) <= 3 and all(w in _ACK_PHRASES for w in words):
        return f"acknowledgement phrase ('{clean_punc}')"

    # 2. Address / Contact details check
    has_phone_or_postal = bool(re.search(r'\b\d{7,13}\b', body))
    body_words_set = set(re.findall(r'[a-zA-Z]+', body_clean))
    matching_addr_words = body_words_set & _ADDRESS_KEYWORDS

    # Case A: Contains phone/postal digits AND at least one address keyword (e.g. house, street, city)
    if has_phone_or_postal and len(matching_addr_words) >= 1:
        return f"address with phone number ({', '.join(matching_addr_words)})"

    # Case B: Contains 2 or more distinct address keywords (e.g. 'house 4 street 2' or 'near bilal masjid gali 3')
    if len(matching_addr_words) >= 2:
        return f"address details ({', '.join(matching_addr_words)})"

    return None



class SettingsCache:
    """Fast in-memory cache for SQLite system settings with 3-second TTL."""
    def __init__(self, ttl_seconds: float = 3.0):
        self.ttl = ttl_seconds
        self._cache: Dict[str, str] = {}
        self._last_fetch = 0.0

    def get(self, key: str, default: str = "") -> str:
        now = time.time()
        if now - self._last_fetch > self.ttl:
            self._refresh()
        return self._cache.get(key, default)

    def _refresh(self):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT setting_key, setting_val FROM system_settings;")
            self._cache = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()
            self._last_fetch = time.time()
        except Exception:
            pass


class DurableQueueProcessor:
    def __init__(self, max_concurrent_workers: int = 4):
        self.waha_client = WAHAClient()
        self.is_running = False
        self._global_automation_enabled = True
        self._max_workers = max_concurrent_workers
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._chat_locks: Dict[str, asyncio.Lock] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._wake_event: Optional[asyncio.Event] = None
        self._settings_cache = SettingsCache(ttl_seconds=3.0)

    def set_global_automation(self, enabled: bool):
        self._global_automation_enabled = enabled
        self.notify_new_message()

    def get_global_automation(self) -> bool:
        return self._global_automation_enabled

    def notify_new_message(self):
        """Thread-safe notification to wake up the queue processor immediately."""
        if self._loop and self._wake_event:
            try:
                self._loop.call_soon_threadsafe(self._wake_event.set)
            except Exception:
                pass

    async def start_worker_loop(self):
        self.is_running = True
        self._loop = asyncio.get_running_loop()
        self._wake_event = asyncio.Event()
        self._semaphore = asyncio.Semaphore(self._max_workers)
        logging.info(f"Durable Queue Processor started (Parallel Workers: {self._max_workers}, Event-Driven Zero Polling).")

        while self.is_running:
            try:
                # Pause if global toggle is OFF
                if not self._global_automation_enabled:
                    await asyncio.sleep(1.0)
                    continue

                pending_msgs = fetch_pending_messages(limit=self._max_workers * 2)
                if not pending_msgs:
                    # Sleep until notified by webhook or backup timer (15s) with 0% CPU consumption
                    try:
                        await asyncio.wait_for(self._wake_event.wait(), timeout=15.0)
                    except asyncio.TimeoutError:
                        pass
                    finally:
                        self._wake_event.clear()
                    continue

                # Process available batch concurrently with per-customer ordering safety
                tasks = [self._process_single_message(m) for m in pending_msgs]
                await asyncio.gather(*tasks, return_exceptions=True)

            except Exception as e:
                logging.error(f"Error in queue processor loop: {e}")
                await asyncio.sleep(1.0)

    async def _process_single_message(self, msg: dict):
        """Wrapper ensuring bounded concurrency + per-chat sequential lock."""
        chat_id = msg.get('chat_id', '')
        if not chat_id:
            return

        if chat_id not in self._chat_locks:
            self._chat_locks[chat_id] = asyncio.Lock()
        chat_lock = self._chat_locks[chat_id]

        async with self._semaphore:
            async with chat_lock:
                await self._execute_message_pipeline(msg)

    async def _execute_message_pipeline(self, msg: dict):
        msg_id = msg['message_id']
        chat_id = msg['chat_id']
        body = msg['body'] or ""

        try:
            # Extract receiving session_name
            session_name = msg.get('session_name') or 'default'
            raw_data = {}
            try:
                raw_data = json.loads(msg.get('raw_payload', '{}'))
                if not session_name or session_name == 'default':
                    session_name = (
                        raw_data.get('session') or
                        raw_data.get('payload', {}).get('session') or
                        'default'
                    )
            except Exception:
                session_name = session_name or 'default'

            payload_dict = raw_data.get('payload', {})
            is_voice = payload_dict.get('isVoice', False) or bool(payload_dict.get('mediaData'))
            audio_base64 = payload_dict.get('mediaData')
            audio_mime = payload_dict.get('mimeType') or 'audio/ogg'

            # Mark message as processing
            update_queue_status(msg_id, "processing")

            # Guard: Skip media-only or empty messages without text caption (unless voice note)
            if not body.strip() and not is_voice:
                logging.info(f"📷 Media-only/empty message {msg_id} from {chat_id} ignored cleanly.")
                update_queue_status(msg_id, "ignored")
                return

            # Guard: Pre-filter trivial acknowledgements and address submissions (prevent unnecessary AI calls & spam replies)
            prefilter_reason = _should_prefilter_message(body, is_voice)
            if prefilter_reason:
                logging.info(f"🔕 Pre-filter: Dropped {prefilter_reason} message {msg_id} from {chat_id} ('{body[:35]}')")
                update_queue_status(msg_id, "ignored")
                return

            # Guard: Ignored Numbers / Do Not Automate
            sender_phone = payload_dict.get('phone') or payload_dict.get('realPhone') or ''
            real_phone = payload_dict.get('realPhone') or ''
            if (
                is_number_excluded(chat_id, session_name=session_name) or
                (sender_phone and is_number_excluded(sender_phone, session_name=session_name)) or
                (real_phone and is_number_excluded(real_phone, session_name=session_name))
            ):
                logging.info(f"🛡️ Ignored Numbers filter (queue worker): Dropping {msg_id} from {chat_id} (phone: {sender_phone}) via [{session_name}]")
                update_queue_status(msg_id, "ignored")
                return

            # Check Feature 2: Human VA Takeover (using cached settings)
            takeover_enabled = self._settings_cache.get("human_takeover_enabled", "1") == "1"
            if takeover_enabled and is_human_takeover_active(chat_id):
                logging.info(f"🤝 Human VA Takeover active for {chat_id}. Skipping automated reply.")
                update_queue_status(msg_id, "ignored")
                return

            # Check Feature 1: Per-Customer Cooldown
            cooldown_enabled = self._settings_cache.get("cooldown_enabled", "1") == "1"
            if cooldown_enabled:
                try:
                    cd_val = self._settings_cache.get("cooldown_seconds", "")
                    if cd_val:
                        cd_secs = float(cd_val)
                    else:
                        cd_secs = float(self._settings_cache.get("cooldown_minutes", "1")) * 60.0
                except (ValueError, TypeError):
                    cd_secs = 30.0
                if is_cooldown_active(chat_id, cd_secs):
                    logging.info(f"🔁 Cooldown active for {chat_id} ({cd_secs:.0f}s). Skipping repeat auto-reply.")
                    update_queue_status(msg_id, "ignored")
                    return

            # Check AI Master Switch & Operating Mode
            ai_master_on = self._settings_cache.get("ai_master_enabled", self._settings_cache.get("ai_fallback_enabled", "0")) == "1"
            ai_mode = self._settings_cache.get("ai_operating_mode", "hybrid")

            # Fetch conversation context settings
            context_enabled = self._settings_cache.get("ai_context_enabled", "1") == "1"
            try:
                context_max_pairs = int(self._settings_cache.get("ai_context_max_pairs", "3"))
                context_expiry_hours = int(self._settings_cache.get("ai_context_expiry_hours", "24"))
            except (ValueError, TypeError):
                context_max_pairs = 3
                context_expiry_hours = 24

            if ai_master_on and ai_mode == "ai_only":
                # Mode 2: Exclusive AI Mode (Rules Bypassed)
                logging.info(f"Exclusive AI Mode active for {msg_id} via session [{session_name}] (is_voice: {is_voice})")

                # Fetch per-customer conversation history if context is enabled
                history = []
                if context_enabled:
                    try:
                        history = get_conversation_history(chat_id, session_name, max_pairs=context_max_pairs, max_age_hours=context_expiry_hours)
                    except Exception as hist_err:
                        logging.warning(f"[context] Failed to load history for {chat_id}: {hist_err}")

                ai_reply = await generate_ai_response(
                    sender_id=chat_id,
                    inbound_body=body or "[Customer sent a voice note]",
                    audio_base64=audio_base64,
                    audio_mime_type=audio_mime,
                    session_name=session_name,
                    conversation_history=history or None
                )

                if not ai_reply or not ai_reply.strip():
                    logging.info(f"AI response empty/failsafe for message {msg_id}. Message ignored cleanly.")
                    update_queue_status(msg_id, "ignored")
                    return

                allowed, reason = await check_and_apply_rate_limit(chat_id)
                if not allowed:
                    logging.warning(f"Rate governor blocked AI dispatch for {msg_id}: {reason}")
                    update_queue_status(msg_id, "failed")
                    return

                sent_ok = await self.waha_client.send_text(chat_id, ai_reply, session=session_name)
                if sent_ok:
                    update_queue_status(msg_id, "done")
                    record_reply_timestamp(chat_id)
                    # Save conversation turns for next message's context
                    if context_enabled and body.strip():
                        try:
                            save_conversation_turn(chat_id, session_name, "user", body.strip(), max_pairs=context_max_pairs)
                            save_conversation_turn(chat_id, session_name, "assistant", ai_reply, max_pairs=context_max_pairs)
                        except Exception as save_err:
                            logging.warning(f"[context] Failed to save turns for {chat_id}: {save_err}")
                else:
                    logging.error(f"Failed to dispatch AI reply for message {msg_id} via session [{session_name}]")
                    update_queue_status(msg_id, "failed")

            else:
                # Mode 1: Hybrid Mode (Rules First, AI Fallback)
                rules_master_on = self._settings_cache.get("rules_master_enabled", "1") == "1"
                matched_rule = None
                if rules_master_on and not is_voice:
                    rules = get_all_rules()
                    matched_rule = match_inbound_message(body, rules, session_name=session_name)
                elif not rules_master_on:
                    logging.info(f"Rules Master Switch is OFF. Skipping static rule matching for message {msg_id}.")

                if matched_rule:
                    logging.info(f"Rule matched for message {msg_id}: Rule '{matched_rule['rule_name']}' (Target: {matched_rule.get('account_target', 'ALL')}) via session [{session_name}]")
                    allowed, reason = await check_and_apply_rate_limit(chat_id)
                    if not allowed:
                        logging.warning(f"Rate governor blocked dispatch for {msg_id}: {reason}")
                        update_queue_status(msg_id, "failed")
                        return

                    # Dispatch text response using exact receiving session
                    resp_text = matched_rule.get('response_message', '')
                    send_success = True
                    if resp_text:
                        send_success = await self.waha_client.send_text(chat_id, resp_text, session=session_name)

                    # Dispatch file attachments if linked
                    attachments = matched_rule.get('attachments', [])
                    resolved_phone = ""
                    if chat_id.endswith("@lid"):
                        resolved_phone = get_phone_for_lid(chat_id) or ""
                        if not resolved_phone and payload_dict:
                            p = payload_dict.get("payload", {})
                            rp = p.get("realPhone") or p.get("phone") or ""
                            clean_rp = "".join(ch for ch in str(rp) if ch.isdigit())
                            lid_digits = "".join(ch for ch in str(chat_id).split("@")[0] if ch.isdigit())
                            if clean_rp and clean_rp != lid_digits:
                                resolved_phone = clean_rp

                    for att in attachments:
                        file_ok = await self.waha_client.send_file(
                            chat_id=chat_id,
                            local_path=att['local_file_path'],
                            mime_type=att['mime_type'],
                            filename=att['file_name'],
                            caption=att.get('media_caption', ''),
                            session=session_name,
                            phone=resolved_phone
                        )
                        if not file_ok:
                            send_success = False

                    if send_success:
                        update_queue_status(msg_id, "done")
                        record_reply_timestamp(chat_id)
                        # Save rule reply to history so AI knows what was told to customer
                        if context_enabled and body.strip() and resp_text:
                            try:
                                save_conversation_turn(chat_id, session_name, "user", body.strip(), max_pairs=context_max_pairs)
                                save_conversation_turn(chat_id, session_name, "assistant", resp_text, max_pairs=context_max_pairs)
                            except Exception as save_err:
                                logging.warning(f"[context] Failed to save rule turns for {chat_id}: {save_err}")
                    else:
                        logging.error(f"Failed to dispatch rule response/attachment for message {msg_id} via session [{session_name}]")
                        update_queue_status(msg_id, "failed")

                elif ai_master_on:
                    # Hybrid Mode: No rule matched (or is voice note) -> trigger AI fallback
                    logging.info(f"Hybrid Mode: Triggering AI response for message {msg_id} via session [{session_name}] (is_voice: {is_voice})")

                    # Fetch per-customer conversation history if context is enabled
                    history = []
                    if context_enabled:
                        try:
                            history = get_conversation_history(chat_id, session_name, max_pairs=context_max_pairs, max_age_hours=context_expiry_hours)
                        except Exception as hist_err:
                            logging.warning(f"[context] Failed to load history for {chat_id}: {hist_err}")

                    ai_reply = await generate_ai_response(
                        sender_id=chat_id,
                        inbound_body=body or "[Customer sent a voice note]",
                        audio_base64=audio_base64,
                        audio_mime_type=audio_mime,
                        session_name=session_name,
                        conversation_history=history or None
                    )

                    if not ai_reply or not ai_reply.strip():
                        logging.info(f"AI response empty/failsafe for message {msg_id}. Message ignored cleanly.")
                        update_queue_status(msg_id, "ignored")
                        return

                    allowed, reason = await check_and_apply_rate_limit(chat_id)
                    if not allowed:
                        logging.warning(f"Rate governor blocked AI dispatch for {msg_id}: {reason}")
                        update_queue_status(msg_id, "failed")
                        return

                    sent_ok = await self.waha_client.send_text(chat_id, ai_reply, session=session_name)
                    if sent_ok:
                        update_queue_status(msg_id, "done")
                        record_reply_timestamp(chat_id)
                        # Save conversation turns for next message's context
                        if context_enabled and body.strip():
                            try:
                                save_conversation_turn(chat_id, session_name, "user", body.strip(), max_pairs=context_max_pairs)
                                save_conversation_turn(chat_id, session_name, "assistant", ai_reply, max_pairs=context_max_pairs)
                            except Exception as save_err:
                                logging.warning(f"[context] Failed to save turns for {chat_id}: {save_err}")
                    else:
                        logging.error(f"Failed to dispatch AI fallback reply for message {msg_id} via session [{session_name}]")
                        update_queue_status(msg_id, "failed")
                else:
                    logging.info(f"⚠️ NO RULE MATCHED for message {msg_id} ('{body[:60]}'). AI Master Switch is OFF.")
                    update_queue_status(msg_id, "ignored")


        except Exception as msg_err:
            logging.error(f"Error processing message {msg_id}: {msg_err}")
            update_queue_status(msg_id, "failed")

    def stop(self):
        self.is_running = False
        self.notify_new_message()
