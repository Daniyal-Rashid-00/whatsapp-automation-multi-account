import asyncio
import logging
import httpx
import base64
import re
from typing import Optional, Dict, Any, Tuple
from database import get_setting, get_all_rules
from vault import retrieve_secret

from ai_key_pool import key_pool

DEFAULT_FALLBACK_REPLY = ""

# Default system context used only when user has NOT configured one in the AI Settings page.
_DEFAULT_SYSTEM_CONTEXT = (
    "You are a WhatsApp Business support assistant.\n"
    "Reply in polite English or Roman Urdu (Urdu written in English letters), matching the language the customer used.\n"
    "Keep replies short, clear, and professional."
)

_IGNORE_PHRASES = {
    "cannot_answer", "cannot answer", "(no response)", "[no response]", "no response",
    "(no reply)", "[no reply]", "no reply", "(ignored)", "[ignored]", "ignored",
    "n/a", "none", "null"
}


def sanitize_ai_reply(reply: str) -> str:
    """
    Sanitizes raw AI output.
    Strips internal thinking blocks (<think>...</think>), orphaned closing tags (</think>),
    reasoning scratchpads, system prompt echoes, and filters out meta-responses like '(No response)' or 'CANNOT_ANSWER'.
    Also detects and blocks untagged chain-of-thought leaks from reasoning models (Nemotron, GPT-OSS, DeepSeek).
    Returns clean string to send to customer, or empty string "" to silently ignore.
    """
    if not reply or not reply.strip():
        return ""

    text = reply.strip()

    # 1. Remove XML/HTML thinking tags: <think>...</think> or <reasoning>...</reasoning>
    text = re.sub(r"<(think|reasoning|thought|scratchpad)>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()

    # 2. Handle orphaned closing tags: if </think> or </reasoning> appears, everything before it was reasoning!
    if re.search(r"</(?:think|reasoning|thought|scratchpad)>", text, flags=re.IGNORECASE):
        parts = re.split(r"</(?:think|reasoning|thought|scratchpad)>", text, flags=re.IGNORECASE)
        text = parts[-1].strip()

    # 3. Handle orphaned opening tags: if <think> or <reasoning> is present without a closing tag, generation got cut off inside thought
    if re.search(r"<(?:think|reasoning|thought|scratchpad)>", text, flags=re.IGNORECASE):
        return ""

    if not text:
        return ""

    lower_text = text.lower()

    # 4. Detect untagged chain-of-thought / reasoning leaks from thinking models.
    #    These models (Nemotron, GPT-OSS, DeepSeek) sometimes output their scratchpad as
    #    plain text without any <think> tags. Detect by checking if the output contains
    #    clear meta-analysis phrases that no real reply would ever contain.
    untagged_reasoning_signals = (
        # Referencing the system prompt / guidelines directly
        "the guideline:",
        "the guidelines:",
        "guideline says",
        "according to the guideline",
        "according to guidelines",
        "operating guidelines",
        "pre-configured products",
        "pre-configured answer",
        "pre-configured answer:",
        "system knowledge base",
        # Reasoning about what to reply (not an actual reply)
        "we could respond",
        "we should respond",
        "we can respond",
        "we need to respond",
        "we need to follow",
        "we need to reply",
        "we should reply",
        "we should ignore",
        "we can use the pre-",
        "we must not invent",
        "also we must not",
        "also \"few days\"",
        "the customer says it",
        "the customer says they",
        "they expected",
        "they say it",
        "with answer:",
        "with answer: \"",
        # Referencing rule names or rule contents verbatim
        "few days\" with answer",
        "\"few days ma aya ga\"",
        "topic / product:",
        "keyword_payload",
        "response_message",
        "rule_name",
        "matching_operator",
        # Thinking process markers
        "here's a thinking process",
        "thinking process:",
        "chain of thought",
        "let me think",
        "let me reason",
        "the customer is asking about",
        "i need to check",
        "i should check",
    )

    for signal in untagged_reasoning_signals:
        if signal in lower_text:
            logging.warning(f"[sanitize] Blocked untagged reasoning leak detected (signal: {signal!r}). Raw: {text[:80]!r}")
            return ""

    # 5. Strip leading reasoning lines or meta-reasoning scratchpads
    lower_start = lower_text
    reasoning_prefixes = (
        "here's a thinking process",
        "we need to follow",
        "we need to respond",
        "we should ignore",
        "thinking process:",
        "according to guidelines",
        "the customer says",
        "the customer is",
        "let me think",
        "let me reason",
        "i need to check",
    )
    if any(lower_start.startswith(p) for p in reasoning_prefixes):
        match = re.search(r"(?:Thus answer:|Answer:|Final Reply:|Reply:)\s*[\"']?(.*?)[\"']?$", text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()
        else:
            return ""

    # 6. Check for exact ignore tokens
    lower_clean = text.lower().strip().strip("\"'.,;:")
    if lower_clean in _IGNORE_PHRASES:
        return ""

    # 7. Check if text contains CANNOT_ANSWER or meta-response phrases
    if "cannot_answer" in lower_clean or "cannot answer" in lower_clean:
        return ""
    if "(no response)" in lower_clean or "[no response]" in lower_clean or "(no reply)" in lower_clean or "no response" == lower_clean:
        return ""

    # 8. Prevent system prompt echoes (if model regurgitates prompt text)
    if ("operating guidelines" in lower_clean or
        "pre-configured products & answers" in lower_clean or
        "system knowledge base" in lower_clean or
        "pre-configured answer:" in lower_clean):
        return ""

    return text



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
        "4. UNRELATED INQUIRIES & SILENCE: If the customer sends an address, personal name, random chit-chat, or something unrelated to any topic in the list below, respond with ONLY the exact single word: CANNOT_ANSWER. Never output your internal thinking, chain of thought, explanations, or phrases like '(No response)'.\n"
        "5. CRITICAL — NO REASONING OUTPUT: You MUST output ONLY the final reply to send to the customer. NEVER output your thought process, analysis, guidelines references, rule names, or any meta-commentary. Do not write things like 'The customer says...', 'The guideline says...', 'We could respond with...', 'According to the rules...'. Output ONLY the actual message text.\n\n"
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


async def transcribe_audio_groq(audio_base64: str, mime_type: str = "audio/ogg") -> Optional[str]:
    """
    Transcribes audio using Groq Cloud Whisper Large V3 in ~300ms for free.
    Returns the clean text transcript in Urdu / English / Roman Urdu, or None if failed.
    """
    groq_key = key_pool.get_groq_key()
    if not groq_key or not audio_base64:
        return None

    try:
        raw_bytes = base64.b64decode(audio_base64)
        if not raw_bytes or len(raw_bytes) < 100:
            return None

        # Determine clean filename and content-type
        clean_ext = "ogg"
        if "wav" in mime_type:
            clean_ext = "wav"
        elif "mp3" in mime_type or "mpeg" in mime_type:
            clean_ext = "mp3"
        elif "m4a" in mime_type or "mp4" in mime_type:
            clean_ext = "m4a"

        files = {
            "file": (f"audio.{clean_ext}", raw_bytes, mime_type or "audio/ogg")
        }
        data = {
            "model": "whisper-large-v3",
            "prompt": "Urdu, Punjabi, Roman Urdu WhatsApp voice message regarding product prices, delivery time, and location.",
            "response_format": "json"
        }
        headers = {
            "Authorization": f"Bearer {groq_key}"
        }

        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post("https://api.groq.com/openai/v1/audio/transcriptions", files=files, data=data, headers=headers)
            if resp.status_code == 200:
                transcript = resp.json().get("text", "").strip()
                if transcript:
                    logging.info(f"🎙️ Groq Whisper V3 successfully transcribed voice note in 0.3s: \"{transcript}\"")
                    return transcript
            else:
                logging.warning(f"Groq Whisper transcription HTTP {resp.status_code}: {resp.text[:120]}")
    except Exception as e:
        logging.warning(f"Groq Whisper transcription exception: {e}")
    return None

async def generate_ai_response(
    sender_id: str,
    inbound_body: str,
    source_hint: Optional[str] = None,
    audio_base64: Optional[str] = None,
    audio_mime_type: Optional[str] = None,
    session_name: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Generates AI response using a 3-Tier Multi-Provider Cascade:
      Tier 1: Google Gemini (3 Slots, Round-Robin)
      Tier 2: OpenRouter Failover (Slot 4 - Llama 3.3 70B / DeepSeek)
      Tier 3: Groq Cloud Failover (Slot 5 - Llama 3.3 70B Versatile)
    For voice notes: automatically uses Groq Whisper Large V3 (0.3s transcription) with Gemini multimodal fallback.
    conversation_history: Optional list of prior turns [{"role": "user"|"assistant", "content": "..."}]
                          injected into all provider requests for contextual awareness.
    """
    _BEST_FREE_GEMINI_MODEL = "gemini-3.5-flash-lite"

    # Check if voice auto-reply is enabled in settings
    voice_enabled = get_setting("ai_voice_enabled", "1") == "1"
    if audio_base64 and not voice_enabled:
        logging.info(f"Voice Note auto-reply is disabled in settings. Skipping message from {sender_id}.")
        return DEFAULT_FALLBACK_REPLY

    # Step 1: If it's a voice note and Groq key is present, transcribe it in 0.3s!
    if audio_base64:
        transcript = await transcribe_audio_groq(audio_base64, audio_mime_type or "audio/ogg")
        if transcript:
            inbound_body = transcript
            audio_base64 = None  # Now converted to text — 95% token savings & 100% provider compatibility!

    # Fetch active rules to provide AI with live Rule Book context (filtered for current account)
    rules = get_all_rules()
    rules_lines = []
    for r in rules:
        if not r.get('is_enabled', 1):
            continue
        target = r.get('account_target', 'ALL')
        # Include if global rule OR matches the current session
        if not target or target.upper() == 'ALL' or (session_name and target == session_name):
            rules_lines.append(f"- Topic / Product: '{r['rule_name']}' | Keywords: {r['keyword_payload']} | Pre-configured Answer: \"{r['response_message']}\"")
    rules_context = "\n".join(rules_lines) if rules_lines else "No static rules configured."
    context_text = get_setting("ai_system_context", "")

    # =========================================================================
    # TIER 1: GOOGLE GEMINI (Slots 1, 2, 3 in Round-Robin)
    # =========================================================================
    gemini_keys = key_pool.get_gemini_keys()
    if gemini_keys:
        active_gemini_model = "gemini-3.5-flash" if audio_base64 else _BEST_FREE_GEMINI_MODEL
        req_payload = build_llm_request(rules_context, context_text, sender_id, source_hint, inbound_body, active_gemini_model)

        user_parts = []
        if audio_base64:
            clean_mime = audio_mime_type.split(";")[0].strip() if audio_mime_type else "audio/ogg"
            user_parts.append({
                "text": (
                    f"Customer WhatsApp ID: {sender_id}.\n"
                    "The customer sent the attached audio voice message. Listen carefully to what the customer is saying in Urdu, Roman Urdu, Punjabi, or English.\n"
                    "Answer their inquiry politely and concisely in Roman Urdu using our products, pricing, delivery policies, and business information."
                )
            })
            user_parts.append({
                "inlineData": {
                    "mimeType": clean_mime,
                    "data": audio_base64
                }
            })
            sys_text = (
                f"{context_text}\n\n"
                "=== VOICE NOTE OPERATING INSTRUCTIONS ===\n"
                "1. Understand the customer's spoken words in Urdu, Punjabi, Roman Urdu, or English.\n"
                "2. Answer their questions directly, politely, and realistically in concise Roman Urdu.\n"
                "3. Keep the reply short and natural like a real human support assistant.\n\n"
                "=== [PRE-CONFIGURED PRODUCTS & ANSWERS] ===\n"
                f"{rules_context}\n\n"
                "=== [KNOWLEDGE BASE] ===\n"
                f"{context_text}"
            )
        else:
            user_parts.append({"text": req_payload["messages"][0]["content"]})
            sys_text = req_payload["system_instruction"]

        gen_config = dict(req_payload["generation_config"])
        if audio_base64:
            gen_config["temperature"] = 0.4
            gen_config["max_output_tokens"] = 350

        # Build Gemini contents array — inject conversation history for text-mode requests.
        # NOTE: Gemini uses "model" role (not "assistant"). History is skipped for voice/audio
        # because the multimodal format uses inline binary data, not plain-text turns.
        if conversation_history and not audio_base64:
            gemini_contents = []
            for turn in conversation_history:
                gemini_role = "model" if turn["role"] == "assistant" else "user"
                gemini_contents.append({
                    "role": gemini_role,
                    "parts": [{"text": turn["content"]}]
                })
            gemini_contents.append({"role": "user", "parts": user_parts})
        else:
            gemini_contents = [{"role": "user", "parts": user_parts}]

        gemini_body = {
            "contents": gemini_contents,
            "systemInstruction": {"parts": [{"text": sys_text}]},
            "generationConfig": gen_config
        }

        # Try up to 3 Gemini attempts across available keys
        for attempt in range(min(3, len(gemini_keys) * 2)):
            current_k = key_pool.get_next_gemini_key()
            if not current_k:
                break
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{active_gemini_model}:generateContent?key={current_k}"
            req_timeout = 25.0 if audio_base64 else 12.0

            try:
                async with httpx.AsyncClient(timeout=req_timeout) as client:
                    resp = await client.post(url, json=gemini_body, headers={"Content-Type": "application/json"})
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            for cand in candidates:
                                finish_reason = cand.get("finishReason", "")
                                parts = cand.get("content", {}).get("parts", [])
                                if not parts and finish_reason in ("STOP", "SAFETY", "BLOCKLIST"):
                                    logging.info(f"Gemini returned empty stop ({finish_reason}). Silently ignoring message from {sender_id}.")
                                    return DEFAULT_FALLBACK_REPLY
                                for p in parts:
                                    raw_reply = p.get("text", "")
                                    clean_reply = sanitize_ai_reply(raw_reply)
                                    if clean_reply:
                                        return clean_reply
                                    elif clean_reply == "" and raw_reply.strip():
                                        logging.info(f"AI returned ignore token ({raw_reply[:30]!r}). Silently ignoring for {sender_id}.")
                                        return DEFAULT_FALLBACK_REPLY

                    # Handle 429 Rate Limiting or 401/403/400 Account Errors
                    if resp.status_code == 429:
                        err_text = resp.text.lower()
                        is_quota = "quota" in err_text or "resource_exhausted" in err_text
                        cooldown = 1800.0 if is_quota else 30.0
                        key_pool.mark_rate_limited(current_k, cooldown_seconds=cooldown)
                        logging.warning(f"Tier 1 (Gemini) key 429 limit. Trying next slot...")
                    elif resp.status_code in (400, 401, 403):
                        key_pool.mark_rate_limited(current_k, cooldown_seconds=86400.0)
                        logging.warning(f"Tier 1 (Gemini) key unauthorized/disabled (HTTP {resp.status_code}). Removing key from rotation.")
                    else:
                        logging.warning(f"Tier 1 (Gemini) attempt {attempt+1} status {resp.status_code}: {resp.text[:100]}")
            except Exception as e:
                logging.warning(f"Tier 1 (Gemini) exception attempt {attempt+1}: {e}")
                key_pool.mark_rate_limited(current_k, cooldown_seconds=30.0)

    # =========================================================================
    # TIER 2: OPENROUTER (Slot 4 Failover)
    # =========================================================================
    openrouter_key = key_pool.get_openrouter_key()
    if openrouter_key:
        or_model = get_setting("openrouter_model_name", "nvidia/nemotron-3-super-120b-a12b:free").strip() or "nvidia/nemotron-3-super-120b-a12b:free"
        logging.info(f"🔄 Cascading to Tier 2: OpenRouter Failover (Slot 4, Model: {or_model})...")
        req_payload = build_llm_request(rules_context, context_text, sender_id, source_hint, inbound_body, or_model)

        # Build OpenRouter messages with conversation history injected.
        # OpenRouter/Groq use OpenAI-compatible format — "user"/"assistant" roles are correct as-is.
        or_messages = [{"role": "system", "content": req_payload["system_instruction"]}]
        if conversation_history:
            for turn in conversation_history:
                or_messages.append({"role": turn["role"], "content": turn["content"]})
        or_messages.append({"role": "user", "content": req_payload["messages"][0]["content"]})

        or_body = {
            "model": or_model,
            "messages": or_messages,
            "max_tokens": 350,
            "temperature": 0.2
        }
        or_headers = {
            "Authorization": f"Bearer {openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "CyberSolu Auto"
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post("https://openrouter.ai/api/v1/chat/completions", json=or_body, headers=or_headers)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        raw_reply = choices[0].get("message", {}).get("content", "")
                        clean_reply = sanitize_ai_reply(raw_reply)
                        if clean_reply:
                            logging.info(f"✅ Reply successfully generated by Tier 2 (OpenRouter {or_model})!")
                            return clean_reply
                        elif clean_reply == "" and raw_reply.strip():
                            logging.info(f"OpenRouter returned ignore token ({raw_reply[:30]!r}). Silently ignoring for {sender_id}.")
                            return DEFAULT_FALLBACK_REPLY
                elif resp.status_code == 429:
                    key_pool.mark_rate_limited(openrouter_key, cooldown_seconds=60.0)
                elif resp.status_code in (400, 401, 403):
                    key_pool.mark_rate_limited(openrouter_key, cooldown_seconds=86400.0)
                logging.warning(f"Tier 2 (OpenRouter) failed: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            logging.warning(f"Tier 2 (OpenRouter) exception: {e}")
            key_pool.mark_rate_limited(openrouter_key, cooldown_seconds=30.0)

    # =========================================================================
    # TIER 3: GROQ CLOUD (Slot 5 Failover - OpenAI GPT OSS 20B / 120B)
    # =========================================================================
    groq_key = key_pool.get_groq_key()
    if groq_key:
        groq_model = get_setting("groq_model_name", "openai/gpt-oss-20b").strip() or "openai/gpt-oss-20b"
        logging.info(f"🔄 Cascading to Tier 3: Groq Cloud Failover (Slot 5, Model: {groq_model})...")
        req_payload = build_llm_request(rules_context, context_text, sender_id, source_hint, inbound_body, groq_model)

        # Build Groq messages with conversation history injected (same OpenAI-compatible format as OpenRouter).
        groq_messages = [{"role": "system", "content": req_payload["system_instruction"]}]
        if conversation_history:
            for turn in conversation_history:
                groq_messages.append({"role": turn["role"], "content": turn["content"]})
        groq_messages.append({"role": "user", "content": req_payload["messages"][0]["content"]})

        groq_body = {
            "model": groq_model,
            "messages": groq_messages,
            "max_tokens": 350,
            "temperature": 0.2
        }
        groq_headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post("https://api.groq.com/openai/v1/chat/completions", json=groq_body, headers=groq_headers)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        raw_reply = choices[0].get("message", {}).get("content", "")
                        clean_reply = sanitize_ai_reply(raw_reply)
                        if clean_reply:
                            logging.info(f"✅ Reply successfully generated by Tier 3 (Groq {groq_model})!")
                            return clean_reply
                        elif clean_reply == "" and raw_reply.strip():
                            logging.info(f"Groq returned ignore token ({raw_reply[:30]!r}). Silently ignoring for {sender_id}.")
                            return DEFAULT_FALLBACK_REPLY
                elif resp.status_code == 429:
                    key_pool.mark_rate_limited(groq_key, cooldown_seconds=60.0)
                elif resp.status_code in (400, 401, 403):
                    key_pool.mark_rate_limited(groq_key, cooldown_seconds=86400.0)
                logging.warning(f"Tier 3 (Groq) failed: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            logging.warning(f"Tier 3 (Groq) exception: {e}")
            key_pool.mark_rate_limited(groq_key, cooldown_seconds=30.0)

    logging.warning("All AI tiers (Gemini, OpenRouter, Groq) failed or returned empty response.")
    return DEFAULT_FALLBACK_REPLY


async def test_ai_connection(api_key: str, model_name: str = "gemini-3.5-flash-lite", provider: str = "gemini") -> Tuple[bool, str, float]:
    """
    Sends a test ping to the AI provider to verify connectivity and measure latency.
    Returns (success: bool, message: str, latency_seconds: float).
    """
    import time
    start_t = time.time()
    prov = provider.lower()
    try:
        if prov == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            body = {
                "contents": [{"role": "user", "parts": [{"text": "Say 'OK' in one word."}]}],
                "generationConfig": {"max_output_tokens": 10, "temperature": 0.0}
            }
            headers = {"Content-Type": "application/json"}
        elif prov == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
            body = {
                "model": model_name,
                "messages": [{"role": "user", "content": "Say 'OK' in one word."}],
                "max_tokens": 10,
                "temperature": 0.0
            }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        else: # openrouter
            url = "https://openrouter.ai/api/v1/chat/completions"
            body = {
                "model": model_name,
                "messages": [{"role": "user", "content": "Say 'OK' in one word."}],
                "max_tokens": 10,
                "temperature": 0.0
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "CyberSolu Auto"
            }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=body, headers=headers)
            elapsed = time.time() - start_t
            if resp.status_code == 200:
                return True, f"Connection verified in {elapsed:.2f}s!", elapsed
            else:
                return False, f"HTTP {resp.status_code}: {resp.text[:100]}", elapsed
    except Exception as e:
        elapsed = time.time() - start_t
        err_msg = str(e) or type(e).__name__
        return False, f"Network Error: {err_msg[:100]}", elapsed


