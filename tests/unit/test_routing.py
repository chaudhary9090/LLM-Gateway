"""Unit tests for ModelRouter and policy decisions."""

import pytest

from app.api.schemas import ChatCompletionRequest, ChatMessage
from app.core.exceptions import ModelNotFoundError
from app.routing.router import ModelRouter


def test_explicit_model_routing():
    router = ModelRouter("config/models.yaml")
    req = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Hello")],
    )
    decision = router.route(req)
    assert decision.target_model == "gpt-4o-mini"
    assert decision.primary_provider in ("mock-primary", "openai-main")
    assert "direct_model_selection" in decision.routing_reason


def test_alias_routing():
    router = ModelRouter("config/models.yaml")
    req = ChatCompletionRequest(
        model="cheap",
        messages=[ChatMessage(role="user", content="Hello")],
    )
    decision = router.route(req)
    assert decision.target_model == "mock-model"
    assert "alias:cheap" in decision.routing_reason


def test_task_hint_routing():
    router = ModelRouter("config/models.yaml")
    req = ChatCompletionRequest(
        model="default",
        task_type="coding",
        messages=[ChatMessage(role="user", content="def sort_numbers():")],
    )
    decision = router.route(req)
    assert decision.target_model == "gpt-4o"
    assert "task_hint:coding" in decision.routing_reason


def test_circuit_breaker_skipping():
    router = ModelRouter("config/models.yaml")
    req = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Hello")],
    )
    # mock-primary circuit is open
    decision = router.route(
        req,
        circuit_open_checker=lambda p: p == "mock-primary",
    )
    # Primary should be chosen from next available fallback (e.g. mock-secondary)
    assert decision.primary_provider != "mock-primary"


def test_unknown_model_raises_or_defaults():
    router = ModelRouter("config/models.yaml")
    # Temporarily remove default alias to ensure error on unknown
    del router.aliases["default"]
    req = ChatCompletionRequest(
        model="non-existent-super-model-xyz",
        messages=[ChatMessage(role="user", content="Hello")],
    )
    with pytest.raises(ModelNotFoundError):
        router.route(req)
