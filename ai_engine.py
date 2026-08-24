import asyncio
import logging
import httpx
from typing import Optional, Dict, Any
from database import get_setting, get_all_rules
from vault import retrieve_secret

DEFAULT_FALLBACK_REPLY = ""

# Default system context used only when user has NOT configured one in the AI Settings page.
_DEFAULT_SYSTEM_CONTEXT = (
    "You are a WhatsApp Business support assistant.\n"
    "Reply in polite English or Roman Urdu (Urdu written in English letters), matching the language the customer used.\n"
    "Keep replies short, clear, and professional."
)


def build_llm_request(rules_context: str, context_box_text: str, sender_id: str, source_hint, inbound_body: str, model_id: str) -> dict:
    """
    Builds the LLM request payload.
    The AI is grounded to the Pre-configured Answers and Knowledge Base.
    Matches semantic customer intent in Roman Urdu or English.
    If the customer message is completely unrelated to any known topic, outputs CANNOT_ANSWER.
    """
    base_system = context_box_text.strip() if context_box_text and context_box_text.strip() else _DEFAULT_SYSTEM_CONTEXT

    system_instruction = (
        f"{base_system}\n\n"
        "=== OPERATING GUIDELINES ===\n"
        "1. SEMANTIC INTENT MATCHING: Customers will ask questions in Roman Urdu (e.g. 'ha?', 'milega?', 'price kya ha?', 'customize shirt ha?'), Urdu, or English with typos or natural phrasing. If their message refers to any Topic / Product in the list below, provide that product's pre-configured details and price.\n"
        "2. NATURAL & POLITE: Reply politely in Roman Urdu or English matching the customer's language. Keep replies concise and formatted with WhatsApp bold (*bold*) where helpful.\n"
        "3. ACCURACY & GROUNDING: Use ONLY the information, pricing, and policies from the list below. Do not invent new prices or make up fake products.\n"
        "4. UNRELATED INQUIRIES: If the customer asks something completely unrelated to any topic in the list below (e.g., random chit-chat, weather, unrelated services), respond with ONLY the exact word: CANNOT_ANSWER\n\n"
        "=== [PRE-CONFIGURED PRODUCTS & ANSWERS] ===\n"
        f"{rules_context}\n\n"
        "=== [ADDITIONAL KNOWLEDGE BASE] ===\n"
        f"{base_system}"
    )

    metadata_note = f"Customer WhatsApp ID: {sender_id}."
    if source_hint:
        metadata_note += f" Channel: {source_hint}."

    return {
        "model": model_id,
        "system_instruction": system_instruction,
        "messages": [
            {"role": "user", "content": f"{metadata_note}\n\nCustomer message: \"{inbound_body}\""}
        ],
        "generation_config": {
            "max_output_tokens": 350,
            "temperature": 0.2
        }
    }

async def generate_ai_response(sender_id: str, inbound_body: str, source_hint: Optional[str] = None) -> str:
    """
    Generates AI response using Gemini or OpenRouter API.
    Combines Rule Book + Knowledge Sandbox for accurate Roman Urdu replies.
    Uses gemini-3.5-flash-lite as the default for high-speed, high-volume business automation.
    """
    # Recommended free fast model for high-volume WhatsApp chat automation (Google Gemini 3.5 series)
    _BEST_FREE_MODEL = "gemini-3.5-flash-lite"

    provider = get_setting("ai_provider", "gemini").lower()
    model_name = get_setting("ai_model_name", _BEST_FREE_MODEL)
    # Normalize deprecated model names to the active working free model
    if model_name in ("gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"):
        model_name = _BEST_FREE_MODEL
    context_text = get_setting("ai_system_context", "")  # User-configured from Settings page
    key_ref = get_setting("ai_api_key_ref", "nexus_ai_key")
    api_key = retrieve_secret(key_ref)

    if not api_key:
        logging.warning("AI Fallback triggered but no API key stored in vault.")
        return DEFAULT_FALLBACK_REPLY

    # Fetch active rules to provide AI with live Rule Book context
    rules = get_all_rules()
    rules_lines = []
    for r in rules:
        if r.get('is_enabled', 1):
            rules_lines.append(f"- Topic / Product: '{r['rule_name']}' | Keywords: {r['keyword_payload']} | Pre-configured Answer: \"{r['response_message']}\"")
    rules_context = "\n".join(rules_lines) if rules_lines else "No static rules configured."

    req_payload = build_llm_request(rules_context, context_text, sender_id, source_hint, inbound_body, model_name)
    
    # Provider-specific endpoint & payload translation
    if provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": req_payload["messages"][0]["content"]}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": req_payload["system_instruction"]}]
            },
            "generationConfig": req_payload["generation_config"]
        }
        headers = {"Content-Type": "application/json"}
    else: # OpenRouter / OpenAI compatible
        url = "https://openrouter.ai/api/v1/chat/completions"
        body = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": req_payload["system_instruction"]},
                {"role": "user", "content": req_payload["messages"][0]["content"]}
            ],
            "max_tokens": req_payload["generation_config"]["max_output_tokens"],
            "temperature": req_payload["generation_config"]["temperature"]
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(url, json=body, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if provider == "gemini":
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                reply = parts[0].get("text", "").strip()
                                if "CANNOT_ANSWER" in reply:
                                    logging.info(f"AI could not answer from Rule Book for message from {sender_id}. Silently ignoring.")
                                    return DEFAULT_FALLBACK_REPLY
                                return reply
                    else:
                        choices = data.get("choices", [])
                        if choices:
                            reply = choices[0].get("message", {}).get("content", "").strip()
                            if "CANNOT_ANSWER" in reply:
                                logging.info(f"AI could not answer from Rule Book for message from {sender_id}. Silently ignoring.")
                                return DEFAULT_FALLBACK_REPLY
                            return reply
                logging.warning(f"AI API request failed attempt {attempt+1}: Status {resp.status_code} {resp.text}")
                
                # If Gemini returned 404 (deprecated model), auto-switch to the working lite model
                if provider == "gemini" and resp.status_code == 404 and model_name != _BEST_FREE_MODEL:
                    logging.info(f"Model {model_name} returned 404 (deprecated). Auto-switching to {_BEST_FREE_MODEL}")
                    model_name = _BEST_FREE_MODEL
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        except Exception as e:
            logging.warning(f"AI API request exception attempt {attempt+1}: {e}")
        
        if attempt == 0:
            await asyncio.sleep(1.0)

    return DEFAULT_FALLBACK_REPLY
