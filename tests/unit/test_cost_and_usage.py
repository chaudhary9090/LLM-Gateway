"""Unit tests for cost calculations and usage normalization."""

from app.api.schemas import ChatMessage
from app.services.cost import calculate_estimated_cost_usd
from app.services.usage import (
    estimate_tokens_from_messages,
    estimate_tokens_from_text,
    normalize_usage,
)


def test_calculate_estimated_cost():
    # 1,000 input tokens at $0.002 / 1K, 500 output tokens at $0.010 / 1K
    cost = calculate_estimated_cost_usd(
        input_tokens=1000,
        output_tokens=500,
        input_cost_per_1k=0.002,
        output_cost_per_1k=0.010,
    )
    # Expected: (1 * 0.002) + (0.5 * 0.010) = 0.002 + 0.005 = 0.007
    assert cost == 0.007


def test_zero_tokens_cost():
    cost = calculate_estimated_cost_usd(0, 0, 0.002, 0.010)
    assert cost == 0.0


def test_token_estimation():
    msgs = [
        ChatMessage(role="system", content="You are a helper."),
        ChatMessage(role="user", content="What is the capital of France?"),
    ]
    tokens = estimate_tokens_from_messages(msgs)
    assert tokens > 0
    assert isinstance(tokens, int)

    text_tokens = estimate_tokens_from_text("Paris is the capital of France.")
    assert text_tokens > 0


def test_normalize_usage():
    usage = normalize_usage(prompt_tokens=10, completion_tokens=20, is_estimated=False)
    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 20
    assert usage.total_tokens == 30
    assert usage.is_estimated is False
