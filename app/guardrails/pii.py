"""PII Redaction Guardrail for sensitive credentials and user data."""

import re

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def redact_pii(text: str) -> str:
    """Redacts emails, phone numbers, credit cards, and SSNs from text."""
    if not text:
        return text

    text = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    text = CREDIT_CARD_PATTERN.sub("[REDACTED_CARD]", text)
    text = SSN_PATTERN.sub("[REDACTED_SSN]", text)
    text = PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    return text
