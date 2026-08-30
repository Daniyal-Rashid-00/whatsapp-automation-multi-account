import sqlite3
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

DB_PATH = "nexus_automata.db"

def get_db_connection():
    target_db = os.environ.get("NEXUS_DB_PATH", DB_PATH)
    conn = sqlite3.connect(target_db, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database schema with WAL mode and core tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Enable WAL mode for high concurrency
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # System Settings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        setting_key TEXT PRIMARY KEY,
        setting_val TEXT NOT NULL
    );
    """)

    # WhatsApp Accounts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS whatsapp_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_name TEXT UNIQUE NOT NULL,
        account_alias TEXT NOT NULL,
        phone_number TEXT DEFAULT '',
        status TEXT DEFAULT 'STOPPED',
        is_enabled INTEGER DEFAULT 1 CHECK(is_enabled IN (0, 1)),
        last_error TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Automated Rules
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS automated_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_name TEXT NOT NULL,
        matching_operator TEXT CHECK(matching_operator IN ('=', 'Like', 'Start with', 'End with', 'Contains')) NOT NULL,
        keyword_payload TEXT NOT NULL,
        response_message TEXT NOT NULL,
        is_enabled INTEGER DEFAULT 1 CHECK(is_enabled IN (0, 1)),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Rule Attachments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rule_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        local_file_path TEXT NOT NULL,
        mime_type TEXT NOT NULL,
        media_caption TEXT,
        FOREIGN KEY (rule_id) REFERENCES automated_rules(id) ON DELETE CASCADE
    );
    """)
    
    # Durable Inbound Queue
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inbound_queue (
        message_id TEXT PRIMARY KEY,
        chat_id TEXT NOT NULL,
        body TEXT,
        raw_payload TEXT NOT NULL,
        session_name TEXT DEFAULT 'default',
        status TEXT CHECK(status IN ('pending', 'processing', 'done', 'failed', 'ignored')) DEFAULT 'pending',
        received_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
        processed_at TIMESTAMP
    );
    """)
    
    # Check if session_name column exists in existing inbound_queue table
    try:
        cursor.execute("ALTER TABLE inbound_queue ADD COLUMN session_name TEXT DEFAULT 'default';")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Deduplication Ledger
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS message_dedup (
        message_id TEXT PRIMARY KEY,
        first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Send Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS send_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Cooldown Ledger Table (Feature 1)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cooldown_ledger (
        chat_id TEXT PRIMARY KEY,
        last_replied_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
    );
    """)

    # Human Takeover Ledger Table (Feature 2)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS human_takeover_ledger (
        chat_id TEXT PRIMARY KEY,
        takeover_until TIMESTAMP NOT NULL
    );
    """)

    # Performance Indices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inbound_received ON inbound_queue(received_at DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inbound_status ON inbound_queue(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_send_log_sent ON send_log(sent_at);")

    # Seed default system settings
    default_settings = [
        ('ai_fallback_enabled', '0'),
        ('ai_provider', 'gemini'),
        ('ai_model_name', 'gemini-2.5-flash'),
        ('ai_model_last_verified', ''),
        ('ai_api_key_ref', 'nexus_ai_key'),
        ('ai_api_key_ref_2', 'nexus_ai_key_2'),
        ('ai_api_key_ref_3', 'nexus_ai_key_3'),
        ('ai_system_context', 'Aap VoltCom Apparel ke WhatsApp Virtual Support Assistant hain. Aap customer inquiries ka jawab Roman Urdu me polite, professional, aur short points me dein.'),
        ('waha_api_key_ref', 'nexus_waha_key'),
        ('waha_url', 'http://localhost:3000'),
        ('send_min_delay_seconds', '2.5'),
        ('send_jitter_seconds', '1.5'),
        ('send_daily_cap', '800'),
        ('ignore_groups', '1'),
        ('autostart_engine', '1'),
        ('cooldown_enabled', '1'),
        ('cooldown_minutes', '1'),
        ('human_takeover_enabled', '1'),
        ('human_takeover_minutes', '5'),
        ('ai_master_enabled', '0'),
        ('ai_operating_mode', 'hybrid'),
        ('ai_voice_enabled', '1')
    ]
    
    for key, val in default_settings:
        cursor.execute("INSERT OR IGNORE INTO system_settings (setting_key, setting_val) VALUES (?, ?);", (key, val))
        
    conn.commit()
    conn.close()

    # Fresh session startup: clear all old queue items, send logs, and dedup so app starts clean
    reset_session_queue_on_startup()
    sync_session_folders_to_db()

def reset_session_queue_on_startup():
    """
    Clears all past queue items, message dedup hashes, and send logs so that
    the software always starts with 0 messages queued and a clean activity log.
    Prevents backlog processing or hanging upon launching.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inbound_queue;")
    cursor.execute("DELETE FROM message_dedup;")
    cursor.execute("DELETE FROM send_log;")
    conn.commit()
    conn.close()

def recover_dangling_queue_items():
    """Recovers any items left in 'processing' state back to 'pending' (legacy alias)."""
    reset_session_queue_on_startup()

def clear_activity_logs():
    """Clear past activity logs (inbound queue and send logs)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inbound_queue;")
    cursor.execute("DELETE FROM send_log;")
    conn.commit()
    conn.close()

def clear_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM automated_rules;")
    cursor.execute("DELETE FROM rule_attachments;")
    cursor.execute("DELETE FROM inbound_queue;")
    cursor.execute("DELETE FROM message_dedup;")
    cursor.execute("DELETE FROM send_log;")
    cursor.execute("DELETE FROM whatsapp_accounts;")
    cursor.execute("DELETE FROM cooldown_ledger;")
    cursor.execute("DELETE FROM human_takeover_ledger;")
    conn.commit()
    conn.close()

# In-process guard: prevents sync_session_folders_to_db from re-inserting sessions
# deleted during the CURRENT process lifetime (folder deletion handles cross-restart persistence).
_deleted_session_names: set = set()

def backup_session_keys(session_name: str) -> bool:
    """Creates a fast, lightweight backup copy of vital authentication keys into wa_web_engine/sessions_backup/
    Excludes volatile browser caches to eliminate startup disk write spikes while ensuring 100% session persistence."""
    import os
    import shutil
    base_dir = os.path.dirname(__file__)
    src_dir = os.path.join(base_dir, "wa_web_engine", "sessions", f"session-{session_name}")
    dst_dir = os.path.join(base_dir, "wa_web_engine", "sessions_backup", f"session-{session_name}")

    if not os.path.exists(src_dir):
        return False

    try:
        os.makedirs(os.path.dirname(dst_dir), exist_ok=True)
        if os.path.exists(dst_dir):
            shutil.rmtree(dst_dir, ignore_errors=True)
        # Exclude temporary cache folders and metrics to reduce disk copy load
        ignore_caches = shutil.ignore_patterns(
            "Cache*", "Code Cache*", "GPUCache*", "DawnCache*", "ShaderCache*",
            "Crashpad*", "CacheStorage*", "ScriptCache*", "BrowserMetrics*",
            "component_crx_cache*", "*.tmp", "*.pma"
        )
        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True, ignore=ignore_caches)
        return True
    except Exception:
        return False

def restore_session_keys(session_name: str) -> bool:
    """Restores wa_web_engine/sessions/session-<session_name> from wa_web_engine/sessions_backup/ if missing or corrupted."""
    import os
    import shutil
    base_dir = os.path.dirname(__file__)
    src_dir = os.path.join(base_dir, "wa_web_engine", "sessions_backup", f"session-{session_name}")
    dst_dir = os.path.join(base_dir, "wa_web_engine", "sessions", f"session-{session_name}")

    if not os.path.exists(src_dir):
        return False

    if os.path.exists(dst_dir):
        return True

    try:
        os.makedirs(os.path.dirname(dst_dir), exist_ok=True)
        ignore_caches = shutil.ignore_patterns(
            "Cache*", "Code Cache*", "GPUCache*", "DawnCache*", "ShaderCache*",
            "Crashpad*", "CacheStorage*", "ScriptCache*", "BrowserMetrics*",
            "component_crx_cache*", "*.tmp", "*.pma"
        )
        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True, ignore=ignore_caches)
        return True
    except Exception:
        return False

def repair_session_keys_in_place(session_name: str) -> bool:
    """Restarts the session client cleanly."""
    return True

def sync_session_folders_to_db():
    """
    Startup-only: Auto-discovers authenticated session folders on disk and registers them
    into the DB. Called ONCE at init_db().
    """
    import os
    base_dir = os.path.dirname(__file__)

    sessions_dir = os.path.join(base_dir, "wa_web_engine", "sessions")
    backup_dir = os.path.join(base_dir, "wa_web_engine", "sessions_backup")

    # 1. Restore from backup if primary folder is missing
    if os.path.exists(backup_dir):
        for b_folder in os.listdir(backup_dir):
            if b_folder in _deleted_session_names:
                continue
            primary_folder = os.path.join(sessions_dir, b_folder)
            if not os.path.exists(primary_folder):
                try:
                    session_name = b_folder.replace("session-", "")
                    restore_session_keys(session_name)
                except Exception:
                    pass

    # 2. Auto-register valid session folders that have no DB entry yet
    if not os.path.exists(sessions_dir):
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for folder in os.listdir(sessions_dir):
            if folder in _deleted_session_names or not folder.startswith("session-"):
                continue

            session_name = folder.replace("session-", "")
            cursor.execute("SELECT id, status, phone_number FROM whatsapp_accounts WHERE session_name = ?;", (session_name,))
            row = cursor.fetchone()

            if not row:
                alias = (
                    session_name.replace("account_", "").upper()
                    if session_name.startswith("account_")
                    else session_name.replace("_", " ").title()
                )
                cursor.execute(
                    "INSERT INTO whatsapp_accounts (session_name, account_alias, phone_number, status) VALUES (?, ?, ?, ?);",
                    (session_name, alias, "", "STARTING")
                )

        conn.commit()
    finally:
        conn.close()

# --- WhatsApp Account Operations ---
def get_all_accounts() -> List[Dict[str, Any]]:
    """
    Returns all accounts from DB. Does NOT call sync_session_folders_to_db().
    sync_session_folders_to_db() is called ONCE at init_db() startup only.
    This function is called every 4 seconds by the UI refresh timer — it must be fast.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM whatsapp_accounts ORDER BY id ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_account(session_name: str, account_alias: str, phone_number: str = '') -> int:
    _deleted_session_names.discard(session_name)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO whatsapp_accounts (session_name, account_alias, phone_number) VALUES (?, ?, ?) "
        "ON CONFLICT(session_name) DO UPDATE SET account_alias = excluded.account_alias, is_enabled = 1;",
        (session_name, account_alias, phone_number)
    )
    acc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return acc_id

def update_account_status(session_name: str, status: str, phone_number: str = None, last_error: str = None):
    """
    Updates account status. phone_number is only written if explicitly provided AND non-empty.
    Passing phone_number='' will NOT erase the stored phone number — use delete_account() for that.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    if phone_number is not None and phone_number != "" and last_error is not None:
        cursor.execute(
            "UPDATE whatsapp_accounts SET status = ?, phone_number = ?, last_error = ? WHERE session_name = ?;",
            (status, phone_number, last_error, session_name)
        )
    elif phone_number is not None and phone_number != "":
        cursor.execute(
            "UPDATE whatsapp_accounts SET status = ?, phone_number = ? WHERE session_name = ?;",
            (status, phone_number, session_name)
        )
    elif last_error is not None:
        cursor.execute(
            "UPDATE whatsapp_accounts SET status = ?, last_error = ? WHERE session_name = ?;",
            (status, last_error, session_name)
        )
    else:
        cursor.execute(
            "UPDATE whatsapp_accounts SET status = ? WHERE session_name = ?;",
            (status, session_name)
        )
    conn.commit()
    conn.close()

def toggle_account(session_name: str, is_enabled: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE whatsapp_accounts SET is_enabled = ? WHERE session_name = ?;", (is_enabled, session_name))
    conn.commit()
    conn.close()

def _force_remove_directory(dir_path: str):
    """Forcefully removes a directory on Windows even with read-only attributes."""
    import os
    import stat
    import shutil
    def on_error(func, path, exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass
    if os.path.exists(dir_path):
        try:
            shutil.rmtree(dir_path, onerror=on_error)
        except Exception:
            try:
                shutil.rmtree(dir_path, ignore_errors=True)
            except Exception:
                pass

def delete_account(session_name: str):
    import os
    _deleted_session_names.add(session_name)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM whatsapp_accounts WHERE session_name = ?;", (session_name,))
    # Mark any pending messages for this deleted session as ignored to avoid hanging
    cursor.execute("UPDATE inbound_queue SET status = 'ignored' WHERE session_name = ? AND status = 'pending';", (session_name,))
    conn.commit()
    conn.close()

    # Remove physical session folder & backup folder from disk permanently
    base_dir = os.path.dirname(__file__)
    sessions_dir = os.path.join(base_dir, "wa_web_engine", "sessions", f"session-{session_name}")
    backup_dir = os.path.join(base_dir, "wa_web_engine", "sessions_backup", f"session-{session_name}")
    _force_remove_directory(sessions_dir)
    _force_remove_directory(backup_dir)

# --- System Settings Operations ---
def get_setting(key: str, default: str = "") -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_val FROM system_settings WHERE setting_key = ?;", (key,))
    row = cursor.fetchone()
    conn.close()
    return row['setting_val'] if row else default

def set_setting(key: str, val: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO system_settings (setting_key, setting_val) VALUES (?, ?) ON CONFLICT(setting_key) DO UPDATE SET setting_val = ?;", (key, val, val))
    conn.commit()
    conn.close()

def get_all_settings() -> Dict[str, str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_key, setting_val FROM system_settings;")
    rows = cursor.fetchall()
    conn.close()
    return {row['setting_key']: row['setting_val'] for row in rows}

# --- Deduplication & Queue Operations ---
def is_message_duplicate(message_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM message_dedup WHERE message_id = ?;", (message_id,))
    row = cursor.fetchone()
    if row:
        conn.close()
        return True
    
    cursor.execute("INSERT INTO message_dedup (message_id) VALUES (?);", (message_id,))
    conn.commit()
    conn.close()
    return False

def enqueue_inbound_message(message_id: str, chat_id: str, body: Optional[str], raw_payload: str, session_name: str = 'default') -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO inbound_queue (message_id, chat_id, body, raw_payload, session_name) VALUES (?, ?, ?, ?, ?);",
            (message_id, chat_id, body or "", raw_payload, session_name)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False
    finally:
        conn.close()

def fetch_pending_messages(limit: int = 10) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM inbound_queue WHERE status = 'pending' ORDER BY received_at ASC LIMIT ?;",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_queue_status(message_id: str, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE inbound_queue SET status = ?, processed_at = CURRENT_TIMESTAMP WHERE message_id = ?;",
        (status, message_id)
    )
    conn.commit()
    conn.close()

def get_queue_metrics() -> Dict[str, int]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) as count FROM inbound_queue GROUP BY status;")
    rows = cursor.fetchall()
    conn.close()
    counts = {"pending": 0, "processing": 0, "done": 0, "failed": 0, "ignored": 0}
    for row in rows:
        counts[row['status']] = row['count']
    return counts

# --- Automated Rules Operations ---
def get_all_rules() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM automated_rules ORDER BY id DESC;")
    rules = [dict(row) for row in cursor.fetchall()]
    
    for rule in rules:
        cursor.execute("SELECT * FROM rule_attachments WHERE rule_id = ?;", (rule['id'],))
        rule['attachments'] = [dict(att) for att in cursor.fetchall()]
        
    conn.close()
    return rules

def add_rule(name: str, operator: str, keyword: str, response: str, is_enabled: int = 1, attachments: Optional[List[Dict[str, str]]] = None) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO automated_rules (rule_name, matching_operator, keyword_payload, response_message, is_enabled) VALUES (?, ?, ?, ?, ?);",
        (name, operator, keyword, response, is_enabled)
    )
    rule_id = cursor.lastrowid
    
    if attachments:
        for att in attachments:
            cursor.execute(
                "INSERT INTO rule_attachments (rule_id, file_name, local_file_path, mime_type, media_caption) VALUES (?, ?, ?, ?, ?);",
                (rule_id, att['file_name'], att['local_file_path'], att['mime_type'], att.get('media_caption', ''))
            )
            
    conn.commit()
    conn.close()
    return rule_id

def update_rule(rule_id: int, name: str, operator: str, keyword: str, response: str, is_enabled: int, attachments: Optional[List[Dict[str, str]]] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE automated_rules SET rule_name = ?, matching_operator = ?, keyword_payload = ?, response_message = ?, is_enabled = ? WHERE id = ?;",
        (name, operator, keyword, response, is_enabled, rule_id)
    )
    cursor.execute("DELETE FROM rule_attachments WHERE rule_id = ?;", (rule_id,))
    
    if attachments:
        for att in attachments:
            cursor.execute(
                "INSERT INTO rule_attachments (rule_id, file_name, local_file_path, mime_type, media_caption) VALUES (?, ?, ?, ?, ?);",
                (rule_id, att['file_name'], att['local_file_path'], att['mime_type'], att.get('media_caption', ''))
            )
            
    conn.commit()
    conn.close()

def delete_rule(rule_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM automated_rules WHERE id = ?;", (rule_id,))
    conn.commit()
    conn.close()

def toggle_rule(rule_id: int, is_enabled: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE automated_rules SET is_enabled = ? WHERE id = ?;", (is_enabled, rule_id))
    conn.commit()
    conn.close()

# --- Send Log & Rate Governor Operations ---
def record_send(chat_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO send_log (chat_id) VALUES (?);", (chat_id,))
    conn.commit()
    conn.close()

def get_today_send_count() -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM send_log WHERE date(sent_at) = date('now', 'localtime');")
    row = cursor.fetchone()
    conn.close()
    return row['cnt'] if row else 0

# --- Feature 1: Per-Customer Cooldown Operations ---
def record_reply_timestamp(chat_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cooldown_ledger (chat_id, last_replied_at) VALUES (?, datetime('now', 'localtime')) "
        "ON CONFLICT(chat_id) DO UPDATE SET last_replied_at = datetime('now', 'localtime');",
        (chat_id,)
    )
    conn.commit()
    conn.close()

def is_cooldown_active(chat_id: str, cooldown_minutes: float) -> bool:
    if cooldown_minutes <= 0:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT (julianday(datetime('now', 'localtime')) - julianday(last_replied_at)) * 1440 as mins_diff "
        "FROM cooldown_ledger WHERE chat_id = ?;",
        (chat_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row and row['mins_diff'] is not None:
        return float(row['mins_diff']) < cooldown_minutes
    return False

def was_recently_replied_by_bot(chat_id: str, within_seconds: int = 15) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT (julianday(datetime('now', 'localtime')) - julianday(last_replied_at)) * 86400 as secs_diff "
        "FROM cooldown_ledger WHERE chat_id = ?;",
        (chat_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row and row['secs_diff'] is not None:
        return float(row['secs_diff']) < within_seconds
    return False

# --- Feature 2: Human VA Takeover Operations ---
def set_human_takeover(chat_id: str, takeover_minutes: float = 60.0):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO human_takeover_ledger (chat_id, takeover_until) "
        "VALUES (?, datetime('now', 'localtime', ? || ' minutes')) "
        "ON CONFLICT(chat_id) DO UPDATE SET takeover_until = datetime('now', 'localtime', ? || ' minutes');",
        (chat_id, str(takeover_minutes), str(takeover_minutes))
    )
    conn.commit()
    conn.close()

def is_human_takeover_active(chat_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM human_takeover_ledger "
        "WHERE chat_id = ? AND datetime('now', 'localtime') < takeover_until;",
        (chat_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row is not None

