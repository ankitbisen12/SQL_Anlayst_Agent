"""
Output guardrail: redact personal / secret information before anything leaves the backend.

This is the last line of defence. Even if a sensitive value reaches a result set (e.g. through a free-text
column such as review comments), it is masked before being sent to the LLM or to the browser.
"""

import re

from utils.config import get_settings

REDACTED = "[REDACTED]"

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("api_key", re.compile(r"\b(?:sk|pk|rk)[-_](?:live[-_]|test[-_]|proj[-_])?[A-Za-z0-9_-]{16,}\b")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("bearer", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}=*", re.IGNORECASE)),
    ("password_kv", re.compile(r"\b(password|passwd|pwd|secret|token|api_key)\s*[:=]\s*\S+", re.IGNORECASE)),
    ("phone", re.compile(r"(?<![\w.])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{3,4})[\s.-]\d{3,4}[\s.-]\d{3,4}(?!\w|\.\d)")),
]

_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _redact_cards(text: str) -> str:
    def repl(match: re.Match) -> str:
        digits = re.sub(r"\D", "", match.group())
        return REDACTED if 13 <= len(digits) <= 19 and _luhn_ok(digits) else match.group()

    return _CARD_RE.sub(repl, text)


def redact_text(text: str) -> str:
    if not text:
        return text
    for _, pattern in _PATTERNS:
        text = pattern.sub(REDACTED, text)
    return _redact_cards(text)


def redact_value(value):
    return redact_text(value) if isinstance(value, str) else value


def redact_result(result: dict) -> dict:
    """Mask whole columns whose name is sensitive and scrub PII patterns from every string cell."""
    sensitive = get_settings().sensitive_column_set
    columns = result.get("columns", [])
    masked_idx = {i for i, c in enumerate(columns) if c.lower() in sensitive}
    rows = [
        [REDACTED if i in masked_idx else redact_value(v) for i, v in enumerate(row)]
        for row in result.get("rows", [])
    ]
    return {**result, "rows": rows}
