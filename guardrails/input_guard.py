"""
Deterministic input guardrail for the user's question.

Runs BEFORE any LLM call, so obviously malicious requests are rejected instantly and for free.
Nuanced cases are handled afterwards by the LLM intent classifier in the `curate_question` node.
"""

import re
from dataclasses import dataclass

from utils.config import get_settings

MODIFY_PATTERNS = [
    r"\b(drop|truncate|alter)\s+(table|database|schema|column|view|index|role|user)\b",
    r"\bdelete\s+from\b",
    r"\binsert\s+into\b",
    r"\bupdate\s+\w+\s+set\b",
    r"\b(grant|revoke)\s+\w+",
    r"\bcreate\s+(table|database|schema|view|index|role|user|function|trigger)\b",
    r";\s*(drop|delete|insert|update|alter|truncate|create|grant)\b",
    r"\b(delete|remove|erase|wipe|purge|destroy|drop|change|modify|update|edit|overwrite|insert|add|set)\s+"
    r"(all\s+|the\s+|this\s+|these\s+|those\s+|a\s+|an\s+|every\s+|some\s+)?(\w+\s+)?"
    r"(records?|rows?|tables?|data|database|entr(y|ies)|listings?|bookings?|reviews?|hosts?|guests?|prices?)\b",
]

SENSITIVE_PATTERNS = [
    r"\be-?mails?\b", r"\bemail\s+address", r"\bphone(\s+numbers?)?\b", r"\bmobile\s+numbers?\b",
    r"\bpass(word|wd|code)s?\b", r"\bcredentials?\b", r"\bapi[\s_-]?keys?\b", r"\bsecrets?\b",
    r"\b(access|auth|bearer)\s+tokens?\b", r"\bssn\b", r"\bsocial\s+security\b",
    r"\bcredit\s+cards?\b", r"\bcard\s+numbers?\b", r"\bcontact\s+(details|info(rmation)?)\b",
    r"\bhome\s+address(es)?\b",
]

INJECTION_PATTERNS = [
    r"\bignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier|your)\s+(instructions?|prompts?|rules?)",
    r"\bdisregard\s+(all\s+|the\s+|your\s+)?(previous|prior|above|instructions?|rules?)",
    r"\b(reveal|show|print|repeat)\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions)\b",
    r"\bsystem\s+prompt\b", r"\byou\s+are\s+now\b", r"\bjailbreak\b", r"\bdeveloper\s+mode\b",
    r"\bDAN\b", r"\bpretend\s+(you\s+are|to\s+be)\b", r"\bbypass\s+(the\s+)?(guardrails?|rules|safety|filters?)\b",
]

REFUSAL_MESSAGES = {
    "modify_request": (
        "I can only read and analyse data. Requests that create, change or delete anything in the "
        "database are not allowed."
    ),
    "sensitive_request": (
        "I can't share personal or sensitive information such as emails, phone numbers, passwords or "
        "other credentials. I'm happy to answer aggregate questions instead."
    ),
    "prompt_injection": "That request tries to override my instructions, so I can't process it.",
    "off_topic": (
        "I'm an analyst for the Airbnb database. Ask me about listings, hosts, prices, bookings, "
        "reviews or neighbourhoods."
    ),
    "invalid": "Please enter a question.",
    "too_long": "Your question is too long. Please shorten it and try again.",
}


@dataclass
class InputGuardResult:
    allowed: bool
    category: str = "ok"
    message: str = ""


def _matches(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def check_user_input(question: str) -> InputGuardResult:
    settings = get_settings()
    text = (question or "").strip()

    if not text:
        return InputGuardResult(False, "invalid", REFUSAL_MESSAGES["invalid"])
    if len(text) > settings.max_question_chars:
        return InputGuardResult(False, "too_long", REFUSAL_MESSAGES["too_long"])
    if _matches(INJECTION_PATTERNS, text):
        return InputGuardResult(False, "prompt_injection", REFUSAL_MESSAGES["prompt_injection"])
    if _matches(MODIFY_PATTERNS, text):
        return InputGuardResult(False, "modify_request", REFUSAL_MESSAGES["modify_request"])
    if _matches(SENSITIVE_PATTERNS, text):
        return InputGuardResult(False, "sensitive_request", REFUSAL_MESSAGES["sensitive_request"])
    return InputGuardResult(True)
