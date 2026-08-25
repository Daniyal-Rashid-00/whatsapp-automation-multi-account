import threading
import time
import logging
from typing import List, Dict, Optional
from database import get_setting
from vault import retrieve_secret

KEY_REFS = ["nexus_ai_key", "nexus_ai_key_2", "nexus_ai_key_3"]

class AIKeyPool:
    """
    Thread-safe API Key Pool for round-robin load distribution across multiple
    Gemini / OpenRouter API keys. Automatically skips rate-limited (HTTP 429) keys.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(AIKeyPool, cls).__new__(cls)
                    cls._instance._init_pool()
        return cls._instance

    def _init_pool(self):
        self._current_index = 0
        self._rate_limited_until: Dict[str, float] = {}

    def get_configured_keys(self) -> List[dict]:
        """
        Returns list of configured key objects:
        [{'ref': 'nexus_ai_key', 'slot': 1, 'key': 'AIza...', 'masked': 'AIza...XXXX', 'rate_limited': False}, ...]
        """
        now = time.time()
        result = []
        for idx, ref in enumerate(KEY_REFS, start=1):
            key_val = retrieve_secret(ref)
            if key_val and key_val.strip():
                clean_k = key_val.strip()
                masked = f"{clean_k[:6]}...{clean_k[-4:]}" if len(clean_k) > 10 else "***"
                is_limited = now < self._rate_limited_until.get(clean_k, 0.0)
                result.append({
                    "slot": idx,
                    "ref": ref,
                    "key": clean_k,
                    "masked": masked,
                    "rate_limited": is_limited
                })
        return result

    def get_all_active_keys(self) -> List[str]:
        """Returns list of all non-empty API keys from vault."""
        keys = []
        for ref in KEY_REFS:
            k = retrieve_secret(ref)
            if k and k.strip():
                keys.append(k.strip())
        return keys

    def get_next_key(self) -> Optional[str]:
        """
        Thread-safely gets the next available API key in round-robin sequence.
        Skips keys that are currently marked rate-limited.
        """
        keys = self.get_all_active_keys()
        if not keys:
            return None

        if len(keys) == 1:
            return keys[0]

        now = time.time()
        with self._lock:
            # Check which keys are NOT rate-limited right now
            usable_keys = [k for k in keys if now >= self._rate_limited_until.get(k, 0.0)]
            if not usable_keys:
                # If all are temporarily rate-limited, fall back to all keys
                usable_keys = keys

            self._current_index = (self._current_index + 1) % len(usable_keys)
            chosen_key = usable_keys[self._current_index]
            return chosen_key

    def mark_rate_limited(self, api_key: str, cooldown_seconds: float = 60.0):
        """Marks a key as rate-limited (HTTP 429) for cooldown_seconds."""
        if not api_key:
            return
        with self._lock:
            self._rate_limited_until[api_key] = time.time() + cooldown_seconds
            masked = f"...{api_key[-4:]}" if len(api_key) >= 4 else "key"
            logging.warning(f"⚠️ API Key {masked} marked rate-limited (429) for {cooldown_seconds}s. Rotating to next key.")

    def get_active_count(self) -> int:
        return len(self.get_all_active_keys())

# Global singleton
key_pool = AIKeyPool()
