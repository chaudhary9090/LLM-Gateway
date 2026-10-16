"""Unit tests for schema validation and sensitive credential redaction."""

import pytest
from pydantic import ValidationError

from app.api.schemas import ChatCompletionRequest, ChatMessage
from app.core.logging import redact_sensitive_string


def test_schema_valid_request():
    req = ChatCompletionRequest(
        model="gpt-4o",
        messages=[ChatMessage(role="user", content="Hello")],
        temperature=1.0,
        max_tokens=1000,
    )
    assert req.model == "gpt-4o"
    assert req.temperature == 1.0


def test_schema_invalid_temperature():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="Hello")],
            temperature=2.5,  # Max allowed is 2.0
        )


def test_schema_empty_messages():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            model="gpt-4o",
            messages=[],  # Must have >= 1 message
        )


def test_schema_invalid_role():
    with pytest.raises(ValidationError):
        ChatMessage(role="superadmin", content="Hello")  # Role must be system, user, assistant


def test_redact_sensitive_strings():
    # OpenAI key pattern
    raw_log = "Sending request with authorization: sk-proj-1234567890abcdef1234567890 to endpoint"
    redacted = redact_sensitive_string(raw_log)
    assert "sk-proj-1234567890abcdef1234567890" not in redacted
    assert "[REDACTED_SECRET]" in redacted

    # Bearer token
    raw_bearer = "Authorization: Bearer mySecretToken123456789"
    redacted_bearer = redact_sensitive_string(raw_bearer)
    assert "mySecretToken123456789" not in redacted_bearer

    # Groq key
    raw_groq = "Using gsk_abcdef1234567890"
    redacted_groq = redact_sensitive_string(raw_groq)
    assert "gsk_abcdef1234567890" not in redacted_groq
