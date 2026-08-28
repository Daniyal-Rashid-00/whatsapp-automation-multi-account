import threading
import time
import logging
from typing import List, Dict, Optional
from database import get_setting
from vault import retrieve_secret

# 5 Dedicated Key Slots
GEMINI_KEY_REFS = ["nexus_ai_key", "nexus_ai_key_2", "nexus_ai_key_3"]
OPENROUTER_KEY_REF = "nexus_openrouter_key"
GROQ_KEY_REF = "nexus_groq_key"

ALL_KEY_REFS = [
    {"slot": 1, "ref": "nexus_ai_key", "name": "Gemini Key 1 (Primary)", "provider": "gemini"},
    {"slot": 2, "ref": "nexus_ai_key_2", "name": "Gemini Key 2 (Secondary)", "provider": "gemini"},
    {"slot": 3, "ref": "nexus_ai_key_3", "name": "Gemini Key 3 (Tertiary)", "provider": "gemini"},
    {"slot": 4, "ref": "nexus_openrouter_key", "name": "OpenRouter Key (Failover LLM)", "provider": "openrouter"},
    {"slot": 5, "ref": "nexus_groq_key", "name": "Groq Cloud Key (Whisper V3 & LLM)", "provider": "groq"},
]

KEY_REFS = [item["ref"] for item in ALL_KEY_REFS]


class AIKeyPool:
    """
    Thread-safe 5-Slot Smart Multi-Provider Key Pool.
    Distributes requests across 3 Gemini keys, auto-fails over to OpenRouter (Slot 4)
    and Groq Cloud (Slot 5), with ultra-fast Groq Whisper audio transcription.
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
        self._gemini_index = 0
        self._rate_limited_until: Dict[str, float] = {}

    def get_configured_keys(self) -> List[dict]:
        """
        Returns status for all 5 slots:
        [{'slot': 1, 'ref': 'nexus_ai_key', 'name': 'Gemini Key 1', 'key': 'AIza...', 'masked': 'AIza...XXXX', 'rate_limited': False}, ...]
        """
        now = time.time()
        result = []
        for item in ALL_KEY_REFS:
            ref = item["ref"]
            key_val = retrieve_secret(ref)
            clean_k = key_val.strip() if key_val else ""
            masked = f"{clean_k[:6]}...{clean_k[-4:]}" if len(clean_k) > 10 else ("***" if clean_k else "Not Configured")
            is_limited = now < self._rate_limited_until.get(clean_k, 0.0) if clean_k else False
            result.append({
                "slot": item["slot"],
                "ref": ref,
                "name": item["name"],
                "provider": item["provider"],
                "key": clean_k,
                "masked": masked,
                "rate_limited": is_limited,
                "is_active": bool(clean_k)
            })
        return result

    def get_all_active_keys(self) -> List[str]:
        """Returns list of all non-empty API keys across all slots."""
        keys = []
        for item in ALL_KEY_REFS:
            k = retrieve_secret(item["ref"])
            if k and k.strip():
                keys.append(k.strip())
        return keys

    def get_gemini_keys(self) -> List[str]:
        """Returns non-empty Gemini keys from Slots 1, 2, 3."""
        keys = []
        for ref in GEMINI_KEY_REFS:
            k = retrieve_secret(ref)
            if k and k.strip():
                keys.append(k.strip())
        return keys

    def get_next_gemini_key(self) -> Optional[str]:
        """Gets next available non-rate-limited Gemini key in round-robin."""
        keys = self.get_gemini_keys()
        if not keys:
            return None

        now = time.time()
        with self._lock:
            usable = [k for k in keys if now >= self._rate_limited_until.get(k, 0.0)]
            if not usable:
                # All Gemini keys are rate-limited or disabled -> Cascade to Tier 2 (OpenRouter) / Tier 3 (Groq)
                return None

            self._gemini_index = (self._gemini_index + 1) % len(usable)
            return usable[self._gemini_index]

    def get_openrouter_key(self) -> Optional[str]:
        """Returns Slot 4 OpenRouter key if configured and not rate-limited."""
        k = retrieve_secret(OPENROUTER_KEY_REF)
        if k and k.strip():
            clean_k = k.strip()
            if time.time() >= self._rate_limited_until.get(clean_k, 0.0):
                return clean_k
        return None

    def get_groq_key(self) -> Optional[str]:
        """Returns Slot 5 Groq Cloud key if configured and not rate-limited."""
        k = retrieve_secret(GROQ_KEY_REF)
        if k and k.strip():
            clean_k = k.strip()
            if time.time() >= self._rate_limited_until.get(clean_k, 0.0):
                return clean_k
        return None

    def get_next_key(self) -> Optional[str]:
        """Generic round robin for active keys."""
        gemini_k = self.get_next_gemini_key()
        if gemini_k:
            return gemini_k
        or_k = self.get_openrouter_key()
        if or_k:
            return or_k
        return self.get_groq_key()

    def mark_rate_limited(self, api_key: str, cooldown_seconds: float = 60.0):
        """Marks a key as rate-limited (HTTP 429) for cooldown_seconds."""
        if not api_key:
            return
        with self._lock:
            self._rate_limited_until[api_key] = time.time() + cooldown_seconds
            masked = f"...{api_key[-4:]}" if len(api_key) >= 4 else "key"
            logging.warning(f"⚠️ API Key {masked} marked cooling-down for {cooldown_seconds:.0f}s. Auto-routing to fallback slots.")

    def get_active_count(self) -> int:
        return len(self.get_all_active_keys())


# Global singleton
key_pool = AIKeyPool()
