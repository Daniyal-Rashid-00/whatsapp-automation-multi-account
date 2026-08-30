import httpx
import logging
import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from database import get_setting
from vault import retrieve_secret

logger = logging.getLogger(__name__)

POSTEX_BASE_URL = "https://api.postex.pk/services/integration"

class PostExClient:
    """
    Asynchronous client for PostEx Courier APIs (Integration Guide v4.1.9).
    Provides Order Tracking, Recent Orders Lookup, and Connectivity Testing.
    """
    _cache: Dict[str, Tuple[float, Any]] = {}  # key -> (timestamp, data)
    _orders_cache: Tuple[float, List[Dict[str, Any]]] = (0.0, [])

    def __init__(self, token: Optional[str] = None):
        self._custom_token = token

    def _get_token(self) -> str:
        if self._custom_token:
            return self._custom_token
        # Try vault first, then database
        token = retrieve_secret("postex_api_token")
        if not token:
            token = get_setting("postex_api_token", "")
        return token.strip() if token else ""

    def _get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        tok = token or self._get_token()
        return {
            "token": tok,
            "Content-Type": "application/json"
        }

    async def test_connection(self, token: Optional[str] = None) -> Tuple[bool, str]:
        """
        Tests API connectivity using PostEx Operational Cities API.
        Returns (is_valid: bool, message: str).
        """
        tok = token or self._get_token()
        if not tok:
            return False, "PostEx API token is empty."

        url = f"{POSTEX_BASE_URL}/api/order/v2/get-operational-city"
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(url, headers=self._get_headers(tok))
                if resp.status_code == 200:
                    data = resp.json()
                    status_code = str(data.get("statusCode", ""))
                    if status_code in ("200", "201", "SUCCESS"):
                        return True, "Successfully connected to PostEx Merchant API! 🚀"
                    elif status_code == "401":
                        return False, "PostEx API returned: Token is invalid."
                    return True, f"Connected: {data.get('statusMessage', 'OK')}"
                elif resp.status_code == 401:
                    return False, "401 Unauthorized: Invalid PostEx API Token."
                else:
                    return False, f"HTTP {resp.status_code}: {resp.text[:120]}"
        except httpx.ConnectTimeout:
            return False, "Connection timed out connecting to api.postex.pk."
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    async def track_order(self, tracking_number: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Tracks a parcel by its PostEx tracking number (e.g. CX-123456789 or 2412...).
        API Section 3.8: GET /api/order/v1/track-order/{trackingNumber}
        """
        clean_track = tracking_number.strip().upper()
        if not clean_track:
            return None

        # Check in-memory cache (TTL: 3 minutes)
        cache_key = f"track_{clean_track}"
        now = time.time()
        if cache_key in self._cache:
            ts, cached_data = self._cache[cache_key]
            if now - ts < 180:
                return cached_data

        tok = token or self._get_token()
        if not tok:
            logger.warning("PostEx track_order skipped: No API token configured.")
            return None

        url = f"{POSTEX_BASE_URL}/api/order/v1/track-order/{clean_track}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=self._get_headers(tok))
                if resp.status_code == 200:
                    data = resp.json()
                    status_code = str(data.get("statusCode", ""))
                    if status_code in ("200", "201"):
                        dist = data.get("dist")
                        if dist and isinstance(dist, dict):
                            self._cache[cache_key] = (now, dist)
                            return dist
                elif resp.status_code in (404, 400):
                    logger.info(f"PostEx order {clean_track} not found (Status {resp.status_code}).")
                    return None
        except Exception as e:
            logger.error(f"Exception tracking PostEx order {clean_track}: {e}")
            return None
        return None

    async def get_recent_orders(self, days: int = 21, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches recent orders list from PostEx.
        API Section 3.16: GET /api/order/v1/get-all-order
        Cached for 5 minutes.
        """
        now = time.time()
        last_fetch, cached_orders = self._orders_cache
        if cached_orders and (now - last_fetch < 300):
            return cached_orders

        tok = token or self._get_token()
        if not tok:
            return []

        today = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        url = f"{POSTEX_BASE_URL}/api/order/v1/get-all-order"
        params = {
            "orderStatusID": 0,
            "fromDate": from_date,
            "toDate": today
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url, headers=self._get_headers(tok), params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if str(data.get("statusCode")) in ("200", "201"):
                        raw_list = data.get("dist", [])
                        orders = []
                        for item in raw_list:
                            if isinstance(item, dict):
                                if "trackingResponse" in item and isinstance(item["trackingResponse"], dict):
                                    orders.append(item["trackingResponse"])
                                else:
                                    orders.append(item)
                        self._orders_cache = (now, orders)
                        return orders
        except Exception as e:
            logger.warning(f"Error fetching PostEx recent orders: {e}")
        return cached_orders or []

    async def find_order_by_ref_or_phone(
        self,
        order_ref: str = "",
        phone: str = "",
        token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Searches recent PostEx orders by merchant Order ID (orderRefNumber) or customer phone.
        Returns the order detail dictionary or None if not found (e.g. TCS parcel).
        """
        clean_ref = order_ref.strip()
        clean_phone = "".join(filter(str.isdigit, phone))
        if len(clean_phone) > 10:
            clean_phone_short = clean_phone[-10:]
        else:
            clean_phone_short = clean_phone

        orders = await self.get_recent_orders(days=21, token=token)
        if not orders:
            return None

        # 1. Match by Order Ref Number (exact or stripped)
        if clean_ref:
            for o in orders:
                o_ref = str(o.get("orderRefNumber") or "").strip()
                if o_ref and (o_ref == clean_ref or o_ref.lstrip("#0") == clean_ref.lstrip("#0")):
                    return o

        # 2. Match by Customer Phone Number
        if clean_phone_short:
            for o in orders:
                o_phone = "".join(filter(str.isdigit, str(o.get("customerPhone") or "")))
                if o_phone and (clean_phone_short in o_phone or o_phone.endswith(clean_phone_short)):
                    return o

        return None
