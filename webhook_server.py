import json
import logging
import asyncio
from typing import Dict, Any, Callable, Optional
from fastapi import FastAPI, Request, Response, BackgroundTasks
import uvicorn

from database import (
    get_setting,
    is_message_duplicate,
    enqueue_inbound_message,
    set_human_takeover,
    was_recently_replied_by_bot
)

app = FastAPI(title="NexusAutomata Webhook Gateway")

# Per-session status registry — supports multi-account (session_name -> status string)
_session_status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
_message_enqueued_callback: Optional[Callable[[], None]] = None
_session_statuses: Dict[str, str] = {}  # session_name -> status

def set_session_status_callback(cb: Callable[[str, Dict[str, Any]], None]):
    global _session_status_callback
    _session_status_callback = cb

def set_message_enqueued_callback(cb: Callable[[], None]):
    global _message_enqueued_callback
    _message_enqueued_callback = cb

def get_current_session_status(session_name: str = None) -> str:
    """Returns the live status for a specific session, or 'STARTING' if unknown."""
    if session_name:
        return _session_statuses.get(session_name, "STARTING")
    # Legacy compatibility: return the first known session status or STARTING
    if _session_statuses:
        return next(iter(_session_statuses.values()))
    return "STARTING"

def get_all_session_statuses() -> Dict[str, str]:
    """Returns the full per-session status snapshot (session_name -> status)."""
    return dict(_session_statuses)

@app.get("/health")
async def health_check():
    return {"status": "ok", "sessions": _session_statuses}

@app.post("/webhook")
async def receive_webhook(request: Request):
    try:
        data = await request.json()
    except Exception as e:
        logging.error(f"Invalid JSON in webhook request: {e}")
        return Response(content="Invalid JSON", status_code=400)

    event_type = data.get("event")
    session = data.get("session", "default")
    payload = data.get("payload", {})

    # Handle session.status events
    if event_type == "session.status":
        status = payload.get("status") or data.get("status", "UNKNOWN")
        _session_statuses[session] = status  # Per-session update
        logging.info(f"Session status update: [{session}] → {status}")
        if _session_status_callback:
            _session_status_callback(status, payload)
        return {"status": "received"}

    # Handle message events (FR-08)
    if event_type == "message":
        message_id = payload.get("id")
        chat_id = payload.get("from")
        body = payload.get("body", "")
        from_me = payload.get("fromMe", False)
        msg_type = str(payload.get("type", "")).lower()
        has_media = bool(payload.get("hasMedia", False))
        media_data = payload.get("mediaData")
        is_voice = bool(payload.get("isVoice", False)) or msg_type in ["ptt", "audio", "voice"] or bool(media_data)

        # If message was manually sent by Human VA from phone/web, activate Human Takeover (Feature 2)
        if from_me:
            customer_chat_id = payload.get("to") or payload.get("chatId") or chat_id
            if customer_chat_id:
                # 1. Ignore if bot recently sent an automated reply to this customer within 15 seconds
                if was_recently_replied_by_bot(customer_chat_id, within_seconds=15):
                    return {"status": "ignored_bot_reply"}

                # 2. Ignore historical sync messages older than 60 seconds
                msg_timestamp = payload.get("t") or payload.get("timestamp")
                is_historical = False
                if msg_timestamp:
                    import time
                    try:
                        if time.time() - float(msg_timestamp) > 60:
                            is_historical = True
                    except Exception:
                        pass

                if not is_historical:
                    takeover_on = get_setting("human_takeover_enabled", "1") == "1"
                    if takeover_on:
                        try:
                            takeover_mins = float(get_setting("human_takeover_minutes", "60"))
                        except ValueError:
                            takeover_mins = 60.0
                        set_human_takeover(customer_chat_id, takeover_mins)
                        logging.info(f"🤝 Human agent manual reply to {customer_chat_id} via [{session}]. Bot auto-reply paused for {takeover_mins} mins.")
            return {"status": "ignored_self"}

        logging.info(f"📩 Webhook received message {message_id} from {chat_id} (body: '{body[:60]}', isVoice: {is_voice}) via [{session}]")

        if not message_id or not chat_id:
            logging.warning("Received message payload without id or from")
            return {"status": "ignored_invalid"}

        # Ignore Status Broadcasts
        if "@broadcast" in chat_id or chat_id == "status@broadcast":
            return {"status": "ignored_broadcast"}

        # Ignore Group Messages Filter (Setting: ignore_groups)
        ignore_groups = get_setting("ignore_groups", "1") == "1"
        if ignore_groups and (chat_id.endswith("@g.us") or "@g.us" in chat_id):
            logging.info(f"Ignore group filter active: dropped message from group {chat_id}")
            return {"status": "ignored_group"}

        # Ignore empty/undecrypted placeholders awaiting retry decryption (unless it is a voice note)
        if not from_me and not body and not has_media and not is_voice:
            logging.info(f"⏳ Ignoring empty/undecrypted placeholder for message {message_id}, waiting for decrypted update...")
            return {"status": "ignored_empty"}

        # Ignore media-only messages without text caption (silent images, stickers, videos), but ALLOW voice notes
        if not from_me and not body.strip() and has_media and not is_voice:
            logging.info(f"📷 Dropping inbound media-only message {message_id} from {chat_id} (no text caption)")
            return {"status": "ignored_media_no_body"}

        # Ignore historical sync messages older than 60 seconds (synced during startup)
        msg_timestamp = payload.get("timestamp") or payload.get("t")
        if msg_timestamp:
            import time
            try:
                if time.time() - float(msg_timestamp) > 60:
                    logging.info(f"⌛ Dropping historical synced message {message_id} ({time.time() - float(msg_timestamp):.0f}s old)")
                    return {"status": "ignored_historical"}
            except Exception:
                pass

        # Deduplication Filter (Section 3.1 & FR-08)
        if is_message_duplicate(message_id):
            logging.info(f"Deduplication filter dropped repeat message: {message_id}")
            return {"status": "duplicate_dropped"}

        # Enqueue into durable SQLite-WAL queue
        raw_json = json.dumps(data)
        success = enqueue_inbound_message(message_id, chat_id, body, raw_json, session_name=session)
        if success:
            logging.info(f"Message enqueued: {message_id} from {chat_id} via session [{session}]")
            if _message_enqueued_callback:
                try:
                    _message_enqueued_callback()
                except Exception as e:
                    logging.warning(f"Error calling message enqueued callback: {e}")
            return {"status": "enqueued"}
        else:
            return {"status": "enqueue_failed"}

    return {"status": "ignored_event"}

def run_webhook_server(host: str = "127.0.0.1", port: int = 8000):
    config = uvicorn.Config(app=app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()
