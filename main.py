import sys
import os
import asyncio
import threading
import logging
from urllib.parse import urlparse
from PyQt6.QtWidgets import QApplication

from database import init_db, get_setting, get_all_accounts
from webhook_server import run_webhook_server, set_message_enqueued_callback
from queue_processor import DurableQueueProcessor
from main_window import MainWindow
from waha_launcher import WAHALauncher

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def start_webhook_background_thread():
    t = threading.Thread(target=run_webhook_server, kwargs={"host": "127.0.0.1", "port": 8000}, daemon=True)
    t.start()
    logging.info("FastAPI Webhook Server background thread started on http://127.0.0.1:8000")

def start_queue_worker_thread(processor: DurableQueueProcessor):
    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(processor.start_worker_loop())

    t = threading.Thread(target=run_loop, daemon=True)
    t.start()
    logging.info("Durable Queue Processor worker thread started.")

def auto_start_engine():
    w_url = get_setting("waha_url", "http://localhost:3000")
    try:
        parsed = urlparse(w_url)
        port = parsed.port or 3000
    except Exception:
        port = 3000
    success, msg = WAHALauncher.start_waha_engine(port=port)
    logging.info(f"Auto-Start Engine: {msg}")


def kickstart_all_sessions():
    """
    After the engine boots, send a /api/sessions/start request for every account in the DB
    that has previously been authenticated (has a phone number).
    This ensures sessions auto-reconnect on restart without user interaction.
    Runs in a background thread with a short delay to let the engine fully initialize.
    """
    import time
    import httpx
    time.sleep(2.0)

    w_url = get_setting("waha_url", "http://localhost:3000").rstrip("/")
    try:
        parsed = urlparse(w_url)
        port = parsed.port or 3000
    except Exception:
        port = 3000

    # Ensure engine is up before making requests
    if not WAHALauncher.is_waha_server_running(port=port):
        WAHALauncher.start_waha_engine(port=port)
        time.sleep(2.0)

    accounts = get_all_accounts()

    for acc in accounts:
        session_name = acc["session_name"]
        phone = acc.get("phone_number", "")
        is_enabled = acc.get("is_enabled", 1) == 1

        # Only kickstart accounts that were previously linked (have a phone number) and are enabled
        if not is_enabled or not phone:
            continue

        try:
            resp = httpx.post(
                f"{w_url}/api/sessions/start",
                json={"session": session_name, "scan_qr": False},
                timeout=8.0
            )
            if resp.status_code == 200:
                logging.info(f"Auto-kickstart sent for session [{session_name}] (phone: {phone})")
            else:
                logging.warning(f"Auto-kickstart failed for [{session_name}]: {resp.status_code}")
        except Exception as e:
            logging.warning(f"Auto-kickstart request failed for [{session_name}]: {e}")

def main():
    # 1. Initialize SQLite database and WAL mode (also runs sync_session_folders_to_db ONCE)
    init_db()
    logging.info("SQLite Database initialized with WAL mode.")

    # 2. Start Webhook Gateway Server
    start_webhook_background_thread()

    # 3. Start Durable Queue Consumer Loop (Event-Driven & Parallel)
    processor = DurableQueueProcessor(max_concurrent_workers=4)
    set_message_enqueued_callback(processor.notify_new_message)
    start_queue_worker_thread(processor)

    # 4. Auto-start WhatsApp Engine in background (non-blocking for instant GUI launch)
    threading.Thread(target=auto_start_engine, daemon=True).start()

    # 5. Kickstart all previously-linked sessions in background (non-blocking)
    threading.Thread(target=kickstart_all_sessions, daemon=True).start()

    # 6. Launch PyQt6 Desktop Application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(queue_processor=processor)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
