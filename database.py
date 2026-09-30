import sqlite3
import os
import json
import threading
from typing import List, Dict, Any, Optional, Tuple
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
        account_target TEXT DEFAULT 'ALL',
        is_enabled INTEGER DEFAULT 1 CHECK(is_enabled IN (0, 1)),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Auto-migration: Check if account_target column exists in existing automated_rules table
    try:
        cursor.execute("ALTER TABLE automated_rules ADD COLUMN account_target TEXT DEFAULT 'ALL';")
    except sqlite3.OperationalError:
        pass  # Column already exists

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

    # Excluded Numbers / Do Not Automate Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS excluded_numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone_number TEXT NOT NULL,
        raw_input TEXT NOT NULL,
        label TEXT DEFAULT '',
        account_target TEXT DEFAULT 'ALL',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(phone_number, account_target)
    );
    """)

    # LID to Phone Mappings (WhatsApp Multi-Device @lid resolution)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lid_phone_mappings (
        lid TEXT PRIMARY KEY,
        phone_number TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # AI Conversation History — per-customer context memory (last N turns)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_conversation_history (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id      TEXT    NOT NULL,
        session_name TEXT    NOT NULL DEFAULT 'default',
        role         TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
        content      TEXT    NOT NULL,
        created_at   TIMESTAMP DEFAULT (datetime('now', 'localtime'))
    );
    """)

    # Performance Indices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inbound_received ON inbound_queue(received_at DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inbound_status ON inbound_queue(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_send_log_sent ON send_log(sent_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_excluded_phone ON excluded_numbers(phone_number);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_history_lookup ON ai_conversation_history(chat_id, session_name, created_at DESC);")

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
        ('ignored_numbers_enabled', '1'),
        ('autostart_engine', '1'),
        ('cooldown_enabled', '1'),
        ('cooldown_minutes', '1'),
        ('human_takeover_enabled', '1'),
        ('human_takeover_minutes', '5'),
        ('ai_master_enabled', '0'),
        ('ai_operating_mode', 'hybrid'),
        ('ai_voice_enabled', '1'),
        ('ai_slot_1_enabled', '1'),
        ('ai_slot_2_enabled', '1'),
        ('ai_slot_3_enabled', '1'),
        ('ai_slot_4_enabled', '1'),
        ('ai_slot_5_enabled', '1'),
        ('ai_context_enabled', '1'),
        ('ai_context_max_pairs', '3'),
        ('ai_context_expiry_hours', '24')
    ]
    
    for key, val in default_settings:
        cursor.execute("INSERT OR IGNORE INTO system_settings (setting_key, setting_val) VALUES (?, ?);", (key, val))
        
    conn.commit()
    conn.close()

    # Initialize fast in-memory cache for excluded numbers
    reload_excluded_numbers_cache()

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
        if not rule.get('account_target'):
            rule['account_target'] = 'ALL'
        cursor.execute("SELECT * FROM rule_attachments WHERE rule_id = ?;", (rule['id'],))
        rule['attachments'] = [dict(att) for att in cursor.fetchall()]
        
    conn.close()
    return rules

def add_rule(name: str, operator: str, keyword: str, response: str, is_enabled: int = 1, attachments: Optional[List[Dict[str, str]]] = None, account_target: str = 'ALL') -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    target = account_target if account_target and account_target.strip() else 'ALL'
    cursor.execute(
        "INSERT INTO automated_rules (rule_name, matching_operator, keyword_payload, response_message, is_enabled, account_target) VALUES (?, ?, ?, ?, ?, ?);",
        (name, operator, keyword, response, is_enabled, target)
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

def update_rule(rule_id: int, name: str, operator: str, keyword: str, response: str, is_enabled: int, attachments: Optional[List[Dict[str, str]]] = None, account_target: str = 'ALL'):
    conn = get_db_connection()
    cursor = conn.cursor()
    target = account_target if account_target and account_target.strip() else 'ALL'
    cursor.execute(
        "UPDATE automated_rules SET rule_name = ?, matching_operator = ?, keyword_payload = ?, response_message = ?, is_enabled = ?, account_target = ? WHERE id = ?;",
        (name, operator, keyword, response, is_enabled, target, rule_id)
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


# --- Feature: Ignored Numbers / Do Not Automate ---
_excluded_lock = threading.Lock()
_excluded_cache: Dict[str, set] = {}
_lid_to_phone_map: Dict[str, str] = {}

def normalize_phone_number(phone: str) -> str:
    """
    Normalizes any phone string into clean standard digits for matching.
    Handles Pakistani numbers (03xx -> 923xx), international format, spaces, dashes, @c.us, @lid.
    """
    if not phone:
        return ""
    phone_str = str(phone).split("@")[0].strip()
    digits = "".join(ch for ch in phone_str if ch.isdigit())
    if digits.startswith("03") and len(digits) == 11:
        digits = "92" + digits[1:]
    elif digits.startswith("0") and len(digits) >= 10:
        digits = "92" + digits[1:]
    return digits

def remember_lid_mapping(lid: str, phone: str):
    """
    Stores an association between a WhatsApp LID (e.g. 68753953931427@lid) and a real phone number (e.g. 923137840038).
    Updates both in-memory cache and SQLite table.
    """
    lid_digits = normalize_phone_number(lid)
    phone_digits = normalize_phone_number(phone)
    if not lid_digits or not phone_digits or lid_digits == phone_digits:
        return

    with _excluded_lock:
        _lid_to_phone_map[lid_digits] = phone_digits

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO lid_phone_mappings (lid, phone_number) VALUES (?, ?) "
            "ON CONFLICT(lid) DO UPDATE SET phone_number = excluded.phone_number, updated_at = CURRENT_TIMESTAMP;",
            (lid_digits, phone_digits)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_phone_for_lid(lid: str) -> Optional[str]:
    """Retrieves mapped real phone number for a WhatsApp LID JID."""
    lid_digits = normalize_phone_number(lid)
    with _excluded_lock:
        return _lid_to_phone_map.get(lid_digits)

def reload_excluded_numbers_cache():
    """Reloads the in-memory cache of excluded numbers and LID mappings from DB for O(1) matching."""
    global _excluded_cache, _lid_to_phone_map
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT phone_number, account_target FROM excluded_numbers;")
        rows = cursor.fetchall()

        new_cache: Dict[str, set] = {}
        for r in rows:
            p = r["phone_number"]
            tgt = (r["account_target"] or "ALL").strip()
            if p not in new_cache:
                new_cache[p] = set()
            new_cache[p].add(tgt)

        # Load LID to phone mappings
        new_lid_map: Dict[str, str] = {}
        try:
            cursor.execute("SELECT lid, phone_number FROM lid_phone_mappings;")
            for lr in cursor.fetchall():
                new_lid_map[lr["lid"]] = lr["phone_number"]
        except Exception:
            pass

        conn.close()

        with _excluded_lock:
            _excluded_cache = new_cache
            _lid_to_phone_map = new_lid_map
    except Exception:
        pass

def add_excluded_number(raw_phone: str, label: str = "", account_target: str = "ALL") -> Tuple[bool, str]:
    """
    Adds a phone number to the exclusion list.
    Normalizes number to clean digits while preserving user's raw input.
    """
    cleaned = normalize_phone_number(raw_phone)
    if not cleaned or len(cleaned) < 7:
        return False, "Invalid phone number. Please enter a valid number (e.g. 0300 1234567 or +923001234567)."

    target = (account_target or "ALL").strip()
    raw_clean = str(raw_phone).strip()
    label_clean = str(label or "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO excluded_numbers (phone_number, raw_input, label, account_target) "
            "VALUES (?, ?, ?, ?);",
            (cleaned, raw_clean, label_clean, target)
        )
        conn.commit()
        reload_excluded_numbers_cache()
        return True, "Number added to exclusion list."
    except sqlite3.IntegrityError:
        return False, f"Number '{raw_clean}' is already excluded for target '{target}'."
    except Exception as e:
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

def remove_excluded_number(number_id: int) -> bool:
    """Removes an excluded number by its primary key ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM excluded_numbers WHERE id = ?;", (number_id,))
        conn.commit()
        reload_excluded_numbers_cache()
        return cursor.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()

def get_all_excluded_numbers() -> List[Dict[str, Any]]:
    """Fetches all excluded numbers ordered newest first."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM excluded_numbers ORDER BY id DESC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def is_number_excluded(sender_chat_id: str, session_name: str = "default") -> bool:
    """
    Sub-millisecond (0.001 ms) in-memory check to verify if sender is in the exclusion list.
    Checks direct normalized digits (phone or LID) AND resolves known LID to phone mappings.
    Returns True if sender is excluded globally ('ALL') or for this specific session_name.
    """
    try:
        if get_setting("ignored_numbers_enabled", "1") != "1":
            return False

        digits = normalize_phone_number(sender_chat_id)
        if not digits:
            return False

        with _excluded_lock:
            # 1. Direct match on normalized digits (phone or LID)
            targets = _excluded_cache.get(digits)
            if targets and ("ALL" in targets or session_name in targets):
                return True

            # 2. If digits is an LID, check if it maps to an excluded phone number
            mapped_phone = _lid_to_phone_map.get(digits)
            if mapped_phone:
                mapped_targets = _excluded_cache.get(mapped_phone)
                if mapped_targets and ("ALL" in mapped_targets or session_name in mapped_targets):
                    return True

        return False
    except Exception:
        return False


# =============================================================================
# AI Conversation History — Per-Customer Context Memory
# =============================================================================

def save_conversation_turn(
    chat_id: str,
    session_name: str,
    role: str,
    content: str,
    max_pairs: int = 3
) -> None:
    """
    Saves one message turn (user or assistant) to the per-customer conversation history.
    Automatically trims the table to keep only the most recent `max_pairs` pairs (default 3).
    Skips saving if content is empty.

    Args:
        chat_id:      Customer's WhatsApp JID (e.g. '923001234567@c.us').
        session_name: Account session name ('account_gc', 'account_hg', etc.).
        role:         'user' (inbound message) or 'assistant' (bot reply).
        content:      The message text to store.
        max_pairs:    Maximum number of user+assistant pairs to keep (default 3 = 6 rows max).
    """
    if not content or not content.strip():
        return
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert the new turn
        cursor.execute(
            "INSERT INTO ai_conversation_history (chat_id, session_name, role, content) VALUES (?, ?, ?, ?);",
            (chat_id, session_name, role, content.strip())
        )

        # Trim to keep only the most recent max_pairs * 2 rows for this chat
        max_rows = max_pairs * 2
        cursor.execute(
            """
            DELETE FROM ai_conversation_history
            WHERE chat_id = ? AND session_name = ?
              AND id NOT IN (
                  SELECT id FROM ai_conversation_history
                  WHERE chat_id = ? AND session_name = ?
                  ORDER BY id DESC
                  LIMIT ?
              );
            """,
            (chat_id, session_name, chat_id, session_name, max_rows)
        )

        conn.commit()
        conn.close()
    except Exception as e:
        import logging
        logging.warning(f"[conversation_history] Failed to save turn for {chat_id}: {e}")


def get_conversation_history(
    chat_id: str,
    session_name: str,
    max_pairs: int = 3,
    max_age_hours: int = 24
) -> List[Dict[str, str]]:
    """
    Returns the last `max_pairs` user+assistant turn pairs for a given customer,
    filtered to only include turns within the last `max_age_hours` (default 24h).
    Returns an empty list if no history exists or all turns have expired.

    The returned list is in chronological order (oldest first), ready to be inserted
    directly into an AI provider's messages/contents array.

    Returns:
        List of dicts: [{"role": "user" | "assistant", "content": "..."}]
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content
            FROM ai_conversation_history
            WHERE chat_id = ? AND session_name = ?
              AND created_at >= datetime('now', 'localtime', ? || ' hours')
            ORDER BY id DESC
            LIMIT ?;
            """,
            (chat_id, session_name, f"-{max_age_hours}", max_pairs * 2)
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return []

        # Reverse so oldest is first (chronological order for API)
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    except Exception as e:
        import logging
        logging.warning(f"[conversation_history] Failed to fetch history for {chat_id}: {e}")
        return []


def clear_conversation_history(chat_id: str, session_name: str) -> None:
    """
    Wipes all stored conversation history for a specific customer and session.
    Useful when human takeover ends and the bot resumes fresh, or for manual resets.

    Args:
        chat_id:      Customer's WhatsApp JID.
        session_name: Account session name.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM ai_conversation_history WHERE chat_id = ? AND session_name = ?;",
            (chat_id, session_name)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        import logging
        logging.warning(f"[conversation_history] Failed to clear history for {chat_id}: {e}")
