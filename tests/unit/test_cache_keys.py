"""Unit tests for deterministic cache key generation."""

from app.api.schemas import ChatCompletionRequest, ChatMessage
from app.cache.keys import generate_cache_key


def test_cache_key_deterministic():
    req1 = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[
            ChatMessage(role="user", content="Hello world"),
        ],
        temperature=0.5,
        max_tokens=100,
    )
    req2 = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[
            ChatMessage(role="user", content="Hello world"),
        ],
        temperature=0.5,
        max_tokens=100,
    )
    key1 = generate_cache_key(req1, "gpt-4o-mini")
    key2 = generate_cache_key(req2, "gpt-4o-mini")
    assert key1 == key2
    assert key1.startswith("llm_cache:v1:gpt-4o-mini:")


def test_cache_key_sensitivity_to_parameters():
    base_req = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Hello world")],
        temperature=0.5,
        max_tokens=100,
    )
    base_key = generate_cache_key(base_req, "gpt-4o-mini")

    # Different temperature
    diff_temp = base_req.model_copy(update={"temperature": 0.8})
    assert generate_cache_key(diff_temp, "gpt-4o-mini") != base_key

    # Different max_tokens
    diff_tokens = base_req.model_copy(update={"max_tokens": 200})
    assert generate_cache_key(diff_tokens, "gpt-4o-mini") != base_key

    # Different message content
    diff_msg = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Different prompt")],
        temperature=0.5,
        max_tokens=100,
    )
    assert generate_cache_key(diff_msg, "gpt-4o-mini") != base_key

    # Different role
    diff_role = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="system", content="Hello world")],
        temperature=0.5,
        max_tokens=100,
    )
    assert generate_cache_key(diff_role, "gpt-4o-mini") != base_key


def test_cache_key_ignores_volatile_metadata():
    req1 = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Hello")],
        metadata={"user_session": "123", "client_ip": "1.2.3.4"},
    )
    req2 = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Hello")],
        metadata={"user_session": "999", "client_ip": "5.6.7.8"},
    )
    assert generate_cache_key(req1, "gpt-4o-mini") == generate_cache_key(req2, "gpt-4o-mini")
