import logging
from typing import Optional

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

SERVICE_NAME = "NexusAutomata"

# In-memory fallback vault for environments where keyring backend is missing
_FALLBACK_VAULT = {}

def store_secret(ref_key: str, secret_val: str) -> bool:
    """Store secret in OS Keyring or database fallback vault."""
    if not ref_key:
        return False
    if KEYRING_AVAILABLE:
        try:
            keyring.set_password(SERVICE_NAME, ref_key, secret_val)
        except Exception as e:
            logging.warning(f"Keyring set_password failed: {e}. Using DB fallback.")
    _FALLBACK_VAULT[ref_key] = secret_val
    try:
        from database import set_setting
        set_setting(f"vault_{ref_key}", secret_val)
    except Exception:
        pass
    return True

def retrieve_secret(ref_key: str) -> Optional[str]:
    """Retrieve secret from OS Keyring, in-memory vault, or DB fallback."""
    if not ref_key:
        return None
    if KEYRING_AVAILABLE:
        try:
            val = keyring.get_password(SERVICE_NAME, ref_key)
            if val is not None and val != "":
                return val
        except Exception as e:
            logging.warning(f"Keyring get_password failed: {e}. Falling back.")
    if ref_key in _FALLBACK_VAULT:
        return _FALLBACK_VAULT[ref_key]
    try:
        from database import get_setting
        val = get_setting(f"vault_{ref_key}", "")
        if val:
            _FALLBACK_VAULT[ref_key] = val
            return val
    except Exception:
        pass
    return None

def delete_secret(ref_key: str) -> bool:
    """Delete secret from vault."""
    if not ref_key:
        return False
    if KEYRING_AVAILABLE:
        try:
            keyring.delete_password(SERVICE_NAME, ref_key)
        except Exception:
            pass
    _FALLBACK_VAULT.pop(ref_key, None)
    return True
