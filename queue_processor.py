import asyncio
import json
import logging
from typing import Optional

from database import (
    fetch_pending_messages,
    update_queue_status,
    get_all_rules,
    get_setting,
    is_human_takeover_active,
    is_cooldown_active,
    record_reply_timestamp
)
from rule_engine import match_inbound_message
from ai_engine import generate_ai_response
from rate_governor import check_and_apply_rate_limit
from waha_client import WAHAClient
from webhook_server import get_current_session_status


class DurableQueueProcessor:
    def __init__(self):
        self.waha_client = WAHAClient()
        self.is_running = False
        self._global_automation_enabled = True

    def set_global_automation(self, enabled: bool):
        self._global_automation_enabled = enabled

    def get_global_automation(self) -> bool:
        return self._global_automation_enabled

    async def start_worker_loop(self):
        self.is_running = True
        logging.info("Durable Queue Processor loop started.")

        while self.is_running:
            try:
                # Pause if global toggle is OFF
                if not self._global_automation_enabled:
                    await asyncio.sleep(1.0)
                    continue

                pending_msgs = fetch_pending_messages(limit=5)
                if not pending_msgs:
                    await asyncio.sleep(0.5)
                    continue

                for msg in pending_msgs:
                    msg_id = msg['message_id']
                    chat_id = msg['chat_id']
                    body = msg['body'] or ""

                    try:
                        # Extract receiving session_name to send replies via the exact same account
                        session_name = msg.get('session_name') or 'default'
                        if not session_name or session_name == 'default':
                            try:
                                raw_data = json.loads(msg.get('raw_payload', '{}'))
                                session_name = (
                                    raw_data.get('session') or
                                    raw_data.get('payload', {}).get('session') or
                                    'default'
                                )
                            except Exception:
                                session_name = 'default'

                        # Mark message as processing
                        update_queue_status(msg_id, "processing")

                        # Check Feature 2: Human VA Takeover
                        takeover_enabled = get_setting("human_takeover_enabled", "1") == "1"
                        if takeover_enabled and is_human_takeover_active(chat_id):
                            logging.info(f"🤝 Human VA Takeover active for {chat_id}. Skipping automated reply.")
                            update_queue_status(msg_id, "done")
                            continue

                        # Check Feature 1: Per-Customer Cooldown
                        cooldown_enabled = get_setting("cooldown_enabled", "1") == "1"
                        if cooldown_enabled:
                            try:
                                cd_mins = float(get_setting("cooldown_minutes", "10"))
                            except ValueError:
                                cd_mins = 10.0
                            if is_cooldown_active(chat_id, cd_mins):
                                logging.info(f"🔁 Cooldown active for {chat_id} ({cd_mins} mins). Skipping repeat auto-reply.")
                                update_queue_status(msg_id, "done")
                                continue

                        # Check AI Master Switch & Operating Mode
                        ai_master_on = get_setting("ai_master_enabled", get_setting("ai_fallback_enabled", "0")) == "1"
                        ai_mode = get_setting("ai_operating_mode", "hybrid")

                        if ai_master_on and ai_mode == "ai_only":
                            # Mode 2: Exclusive AI Mode (Rules Bypassed)
                            logging.info(f"Exclusive AI Mode active for {msg_id} via session [{session_name}]")
                            ai_reply = await generate_ai_response(sender_id=chat_id, inbound_body=body)

                            if not ai_reply or not ai_reply.strip():
                                logging.info(f"AI response empty/failsafe for message {msg_id}. Message ignored cleanly.")
                                update_queue_status(msg_id, "done")
                                continue

                            allowed, reason = await check_and_apply_rate_limit(chat_id)
                            if not allowed:
                                logging.warning(f"Rate governor blocked AI dispatch for {msg_id}: {reason}")
                                update_queue_status(msg_id, "failed")
                                continue

                            sent_ok = await self.waha_client.send_text(chat_id, ai_reply, session=session_name)
                            if sent_ok:
                                update_queue_status(msg_id, "done")
                                record_reply_timestamp(chat_id)
                            else:
                                logging.error(f"Failed to dispatch AI reply for message {msg_id} via session [{session_name}]")
                                update_queue_status(msg_id, "failed")

                        else:
                            # Mode 1: Hybrid Mode (Rules First, AI Fallback)
                            rules_master_on = get_setting("rules_master_enabled", "1") == "1"
                            matched_rule = None
                            if rules_master_on:
                                rules = get_all_rules()
                                matched_rule = match_inbound_message(body, rules)
                            else:
                                logging.info(f"Rules Master Switch is OFF. Skipping static rule matching for message {msg_id}.")

                            if matched_rule:
                                logging.info(f"Rule matched for message {msg_id}: Rule '{matched_rule['rule_name']}' via session [{session_name}]")
                                allowed, reason = await check_and_apply_rate_limit(chat_id)
                                if not allowed:
                                    logging.warning(f"Rate governor blocked dispatch for {msg_id}: {reason}")
                                    update_queue_status(msg_id, "failed")
                                    continue

                                # Dispatch text response using exact receiving session
                                resp_text = matched_rule.get('response_message', '')
                                send_success = True
                                if resp_text:
                                    send_success = await self.waha_client.send_text(chat_id, resp_text, session=session_name)

                                # Dispatch file attachments if linked
                                attachments = matched_rule.get('attachments', [])
                                for att in attachments:
                                    file_ok = await self.waha_client.send_file(
                                        chat_id=chat_id,
                                        local_path=att['local_file_path'],
                                        mime_type=att['mime_type'],
                                        filename=att['file_name'],
                                        caption=att.get('media_caption', ''),
                                        session=session_name
                                    )
                                    if not file_ok:
                                        send_success = False

                                if send_success:
                                    update_queue_status(msg_id, "done")
                                    record_reply_timestamp(chat_id)
                                else:
                                    logging.error(f"Failed to dispatch rule response/attachment for message {msg_id} via session [{session_name}]")
                                    update_queue_status(msg_id, "failed")

                            elif ai_master_on:
                                # Hybrid Mode: No rule matched -> trigger AI fallback
                                logging.info(f"Hybrid Mode: No static rule matched. Triggering AI fallback for message {msg_id} via session [{session_name}]")
                                ai_reply = await generate_ai_response(sender_id=chat_id, inbound_body=body)

                                if not ai_reply or not ai_reply.strip():
                                    logging.info(f"AI response empty/failsafe for message {msg_id}. Message ignored cleanly.")
                                    update_queue_status(msg_id, "done")
                                    continue

                                allowed, reason = await check_and_apply_rate_limit(chat_id)
                                if not allowed:
                                    logging.warning(f"Rate governor blocked AI dispatch for {msg_id}: {reason}")
                                    update_queue_status(msg_id, "failed")
                                    continue

                                sent_ok = await self.waha_client.send_text(chat_id, ai_reply, session=session_name)
                                if sent_ok:
                                    update_queue_status(msg_id, "done")
                                    record_reply_timestamp(chat_id)
                                else:
                                    logging.error(f"Failed to dispatch AI fallback reply for message {msg_id} via session [{session_name}]")
                                    update_queue_status(msg_id, "failed")
                            else:
                                logging.info(f"⚠️ NO RULE MATCHED for message {msg_id} ('{body[:60]}'). AI Master Switch is OFF.")
                                update_queue_status(msg_id, "done")

                    except Exception as msg_err:
                        logging.error(f"Error processing message {msg_id}: {msg_err}")
                        update_queue_status(msg_id, "failed")

            except Exception as e:
                logging.error(f"Error in queue processor loop: {e}")
                await asyncio.sleep(1.0)

    def stop(self):
        self.is_running = False
