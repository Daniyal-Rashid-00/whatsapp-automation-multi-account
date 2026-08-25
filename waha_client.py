import base64
import os
import logging
import httpx
from typing import Dict, Any, Optional, List
from database import get_setting
from vault import retrieve_secret

logger = logging.getLogger(__name__)

class WAHAClient:
    def __init__(self):
        pass

    def _get_headers(self) -> Dict[str, str]:
        key_ref = get_setting("waha_api_key_ref", "nexus_waha_key")
        api_key = retrieve_secret(key_ref) or ""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-Api-Key"] = api_key
        return headers

    def _get_base_url(self) -> str:
        url = get_setting("waha_url", "http://localhost:3000").rstrip("/")
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"http://{url}"
        return url

    async def start_session(self, session: str = "default") -> bool:
        base_url = self._get_base_url()
        url = f"{base_url}/api/sessions/start"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json={"session": session}, headers=self._get_headers())
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to start session {session} at {url}: {e}")
            return False

    async def logout_session(self, session: str = "default") -> bool:
        base_url = self._get_base_url()
        url = f"{base_url}/api/sessions/logout"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json={"session": session}, headers=self._get_headers())
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to logout session {session} at {url}: {e}")
            return False

    async def delete_session(self, session: str = "default") -> bool:
        base_url = self._get_base_url()
        url = f"{base_url}/api/sessions/{session}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(url, headers=self._get_headers())
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to delete session {session} at {url}: {e}")
            return False

    async def send_text(self, chat_id: str, text: str, session: str = "default") -> bool:
        import asyncio
        base_url = self._get_base_url()
        url = f"{base_url}/api/sendText"
        payload = {
            "chatId": chat_id,
            "text": text,
            "session": session
        }
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json=payload, headers=self._get_headers())
                    if resp.status_code in (200, 201):
                        logger.info(f"Successfully sent reply to {chat_id} via session [{session}]")
                        return True
                    logger.error(f"WAHA sendText failed to {url}: Status {resp.status_code} - {resp.text}")
                    return False
            except Exception as e:
                if attempt == 0:
                    await asyncio.sleep(2.0)
                else:
                    logger.error(f"WAHA sendText exception connecting to {url}: {e}")
                    return False
        return False

    async def send_file(self, chat_id: str, local_path: str, mime_type: str, filename: str, caption: str = "", session: str = "default") -> bool:
        import asyncio
        base_url = self._get_base_url()
        url = f"{base_url}/api/sendFile"
        
        if not os.path.exists(local_path):
            logger.error(f"File not found for send_file: {local_path}")
            return False

        payload = {
            "chatId": chat_id,
            "filePath": local_path,
            "caption": caption,
            "session": session
        }

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=payload, headers=self._get_headers())
                    if resp.status_code in (200, 201):
                        logger.info(f"Successfully sent file attachment {filename} to {chat_id} via session [{session}]")
                        return True
                    logger.error(f"WAHA sendFile failed to {url}: Status {resp.status_code} - {resp.text}")
                    return False
            except Exception as e:
                if attempt == 0:
                    await asyncio.sleep(2.0)
                else:
                    logger.error(f"WAHA sendFile exception connecting to {url}: {e}")
                    return False
        return False

    async def get_all_sessions(self) -> List[Dict[str, Any]]:
        base_url = self._get_base_url()
        url = f"{base_url}/api/sessions"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=self._get_headers())
                if resp.status_code == 200:
                    return resp.json()
                return []
        except Exception:
            return []
