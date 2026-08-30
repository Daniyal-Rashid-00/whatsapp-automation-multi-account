import re
import logging
from typing import Optional, Dict, Any, Tuple
from database import get_setting
from postex_client import PostExClient

logger = logging.getLogger(__name__)

TRACKING_KEYWORDS = [
    "track", "tracking", "parcel", "status", "kahan", "pohancha", "kab milega",
    "kab tak", "deliver", "delivery", "dispatch", "courier", "postex", "rider",
    "order status", "mera order", "mera parcel", "order kahan", "order kab",
    "bhai parcel", "bhai order", "order details", "dispatched", "shipping"
]

def is_tracking_intent(text: str) -> bool:
    """Checks if the message text contains order tracking or parcel inquiry intent."""
    clean = text.lower().strip()
    if not clean:
        return False
    
    # Check if text contains PostEx tracking number format
    if re.search(r'\b(cx-?[a-z0-9]{6,16})\b', clean):
        return True

    for kw in TRACKING_KEYWORDS:
        if kw in clean:
            return True
    return False

def extract_order_id_from_contact(contact_name: str) -> Optional[str]:
    """
    Extracts Order ID if customer contact is saved as an Order ID number.
    e.g. '2250', '121012', '#2250', '2250 - Ali', 'Order 2250' -> '2250'
    """
    if not contact_name:
        return None
    
    clean = contact_name.strip()
    # 1. Pure number contact name (e.g. '2250', '121012')
    if clean.isdigit() and len(clean) <= 8:
        return clean

    # 2. Match patterns like '#2250', 'Order 2250', '2250 Ali', '2250-Name'
    m = re.search(r'^(?:#|order\s*)?(\d{3,8})\b', clean, re.IGNORECASE)
    if m:
        return m.group(1)
    
    # Match any isolated 3-8 digit number
    m2 = re.search(r'\b(\d{3,8})\b', clean)
    if m2:
        return m2.group(1)
    
    return None

def extract_identifiers(body: str, contact_name: str = "", phone: str = "") -> Dict[str, str]:
    """
    Extracts tracking number, order ID, and phone from message and contact name.
    """
    results = {
        "tracking_number": "",
        "order_id": "",
        "phone": phone
    }

    # Check for tracking number in text (e.g. CX-123456789 or CX123456)
    m_track = re.search(r'\b(CX-?[A-Za-z0-9]{6,16})\b', body, re.IGNORECASE)
    if m_track:
        results["tracking_number"] = m_track.group(1).upper().replace(" ", "")

    # Check for Order ID in message body (e.g. 'Order #2250', '#2250', 'Order 121012')
    m_body_order = re.search(r'(?:order|ord|#)\s*#?\s*(\d{3,8})\b', body, re.IGNORECASE)
    if m_body_order:
        results["order_id"] = m_body_order.group(1)
    elif body.strip().isdigit() and len(body.strip()) <= 8:
        results["order_id"] = body.strip()

    # If no order ID in body, extract from saved contact name
    if not results["order_id"] and contact_name:
        c_order = extract_order_id_from_contact(contact_name)
        if c_order:
            results["order_id"] = c_order

    return results

def should_attempt_tracking(body: str) -> bool:
    """
    Ensures we only attempt tracking if the message is actually asking about a parcel/order
    or explicitly giving an order/tracking number. Non-tracking questions (e.g. price) are bypassed.
    """
    if is_tracking_intent(body):
        return True
    if re.search(r'\b(cx-?[a-z0-9]{6,16})\b', body, re.IGNORECASE):
        return True
    clean = body.strip().lower()
    if clean.isdigit() and len(clean) <= 8:
        return True
    if re.match(r'^(?:#|order\s*#?)\s*\d{3,8}$', clean):
        return True
    return False

def format_tracking_response(order_info: Dict[str, Any], customer_name: str = "") -> str:
    """
    Formats PostEx order status into a clear, natural Urdu/Roman Urdu WhatsApp reply.
    """
    tracking_num = order_info.get("trackingNumber") or ""
    status_raw = str(order_info.get("transactionStatus") or order_info.get("orderStatus") or "").strip()
    status_history = order_info.get("transactionStatusHistory", [])
    
    latest_msg = ""
    latest_code = ""
    if status_history and isinstance(status_history, list):
        last_item = status_history[-1]
        if isinstance(last_item, dict):
            latest_msg = str(last_item.get("transactionStatusMessage") or "")
            latest_code = str(last_item.get("transactionStatusMessageCode") or "")

    status_lower = (status_raw + " " + latest_msg).lower()
    order_ref = str(order_info.get("orderRefNumber") or "").strip()
    
    # Avoid using raw numbers as customer name if contact is just '2250'
    cust_display = "Janab"
    if customer_name and not customer_name.strip().isdigit():
        cust_display = customer_name
    elif order_info.get("customerName") and not str(order_info.get("customerName")).strip().isdigit():
        cust_display = order_info.get("customerName")

    city = order_info.get("cityName") or ""
    city_str = f" ({city})" if city else ""
    tracking_link = f"https://postex.pk/tracking?cn={tracking_num}" if tracking_num else ""

    # 1. Out for Delivery / Package on Root
    if "out for delivery" in status_lower or "package on root" in status_lower or latest_code == "0004":
        return (
            f"Assalam-o-Alaikum {cust_display}! 🚚\n\n"
            f"Aapka parcel ({tracking_num}) is waqt *Out for Delivery* hai aur aaj PostEx rider deliver karega{city_str}.\n\n"
            f"Baraye meherbani apna phone active rakhein taakay rider aasaani se rabta kar sakay.\n\n"
            f"🔗 Live Tracking: {tracking_link}"
        ).strip()

    # 2. Delivered
    if "delivered" in status_lower or latest_code == "0005":
        return (
            f"Assalam-o-Alaikum {cust_display}! ✨\n\n"
            f"Aapka parcel ({tracking_num}) deliver ho chuka hai.\n\n"
            f"Humare saath shopping karne ka shukriya! Agar aapko mazeed koi madad chahiye to zaroor batayein."
        ).strip()

    # 3. Attempt Made / Rider rabta nahi kar saka
    if "attempt made" in status_lower or "attempted" in status_lower or latest_code == "0013" or latest_code == "17":
        reason = latest_msg.split(":")[-1].strip() if ":" in latest_msg else "Customer unavailable"
        return (
            f"Assalam-o-Alaikum {cust_display}! 🛵\n\n"
            f"PostEx courier rider ne aapki location par delivery attempt ki thi ({reason}).\n\n"
            f"InshaAllah aglay working day par dobara delivery attempt ki jayegi. Baraye meherbani phone on rakhein.\n\n"
            f"🔗 Tracking: {tracking_link}"
        ).strip()

    # 4. At Warehouse / In Transit / Booked
    if any(k in status_lower for k in ["warehouse", "in transit", "booked", "picked", "en-route", "0001", "0003", "15", "18"]):
        return (
            f"Assalam-o-Alaikum {cust_display}! 📦\n\n"
            f"Aapka parcel dispatch ho chuka hai aur is waqt courier transit mein hai{city_str}.\n"
            f"📌 Current Status: *{latest_msg or status_raw or 'In Transit'}*\n"
            f"InshaAllah 24 se 48 ghanton mein deliver ho jayega.\n\n"
            f"🔗 Live Tracking: {tracking_link}"
        ).strip()

    # 5. Returned / Return in process
    if any(k in status_lower for k in ["returned", "return", "0002", "0006", "0007", "16"]):
        return (
            f"Assalam-o-Alaikum {cust_display}!\n\n"
            f"Aapke parcel ({tracking_num}) ka status is waqt Return show ho raha hai.\n"
            f"Agar aap parcel dobara mangwana chahte hain to baraye meherbani humein batayein taakay hum update kar sakein."
        ).strip()

    # 6. Fallback General Status
    return (
        f"Assalam-o-Alaikum {cust_display}! 📦\n\n"
        f"Aapke order ka PostEx tracking status yeh hai:\n"
        f"📌 Status: *{status_raw or latest_msg or 'Dispatched'}*\n"
        f"📌 Tracking Number: {tracking_num}\n\n"
        f"🔗 Live Tracking Link: {tracking_link}"
    ).strip()

async def resolve_postex_tracking(
    inbound_body: str,
    contact_name: str = "",
    customer_phone: str = "",
    postex_client: Optional[PostExClient] = None
) -> Optional[str]:
    """
    Core engine resolution:
    1. Checks if PostEx tracking is enabled.
    2. Checks if message is actually a tracking inquiry or explicit order number.
    3. Queries PostEx API.
    4. Returns formatted WhatsApp reply string if found.
    5. Returns None if not a tracking query OR if the parcel is NOT on PostEx (e.g. TCS parcel).
    """
    # 1. Check Master Setting
    is_enabled = get_setting("postex_tracking_enabled", "1") == "1"
    if not is_enabled:
        return None

    # 2. Check Intent / Inquiry Requirement
    if not should_attempt_tracking(inbound_body):
        return None

    identifiers = extract_identifiers(inbound_body, contact_name, customer_phone)
    track_num = identifiers.get("tracking_number")
    order_id = identifiers.get("order_id")
    phone = identifiers.get("phone")

    client = postex_client or PostExClient()
    order_data = None

    # Step A: Direct tracking by tracking number (e.g. CX-123456789)
    if track_num:
        try:
            order_data = await client.track_order(track_num)
        except Exception as e:
            logger.warning(f"PostEx track_order error for {track_num}: {e}")

    # Step B: Lookup by Order ID (contact name or body text) or Customer Phone
    if not order_data and (order_id or phone):
        try:
            order_data = await client.find_order_by_ref_or_phone(order_ref=order_id, phone=phone)
        except Exception as e:
            logger.warning(f"PostEx find_order_by_ref_or_phone error (Order: {order_id}, Phone: {phone}): {e}")

    # If found on PostEx -> format clean reply!
    if order_data:
        reply_msg = format_tracking_response(order_data, customer_name=contact_name)
        logger.info(f"🚚 PostEx Tracking Resolved for {customer_phone or contact_name} (Tracking: {order_data.get('trackingNumber')})")
        return reply_msg

    # If NOT found on PostEx (e.g. TCS parcel or unbooked order) -> Return None gracefully!
    return None
