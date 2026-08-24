import re
from typing import Optional, Dict, Any, List

def evaluate_rule_match(inbound_message: str, operator: str, keyword_target: str) -> bool:
    """
    Evaluates whether inbound_message matches keyword_target using operator.
    Supports '=', 'Contains', 'Start with', 'End with', and SQL-style 'Like' (% and _ wildcards).
    Keyword targets can be comma-separated list of keywords.
    """
    if not inbound_message:
        return False
        
    text = inbound_message.strip().lower()
    keyword = keyword_target.strip().lower()

    # Explode multi-keywords split via comma
    keywords = [k.strip() for k in keyword.split(",") if k.strip()]
    if not keywords:
        keywords = [keyword]

    for kw in keywords:
        if operator == '=':
            if text == kw:
                return True
        elif operator == 'Contains':
            if kw in text:
                return True
        elif operator == 'Start with':
            if text.startswith(kw):
                return True
        elif operator == 'End with':
            if text.endswith(kw):
                return True
        elif operator == 'Like':
            # Split on SQL wildcards FIRST, escape each literal segment,
            # THEN rejoin with regex equivalents.
            pattern_parts = []
            buffer = ""
            for ch in kw:
                if ch == '%':
                    pattern_parts.append(re.escape(buffer))
                    pattern_parts.append('.*')
                    buffer = ""
                elif ch == '_':
                    pattern_parts.append(re.escape(buffer))
                    pattern_parts.append('.')
                    buffer = ""
                else:
                    buffer += ch
            pattern_parts.append(re.escape(buffer))
            regex_pattern = "^" + "".join(pattern_parts) + "$"
            if re.search(regex_pattern, text):
                return True

    return False

def match_inbound_message(inbound_body: str, rules: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Scans active rules in priority order and returns the first matching rule or None.
    """
    for rule in rules:
        if not rule.get('is_enabled', 1):
            continue
        if evaluate_rule_match(inbound_body, rule['matching_operator'], rule['keyword_payload']):
            return rule
    return None
