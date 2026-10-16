"""Token usage tracking and heuristic estimation."""

from typing import List

from app.api.schemas import ChatMessage, UsageInfo


def estimate_tokens_from_messages(messages: List[ChatMessage]) -> int:
    """Heuristic approximation: ~1.3 tokens per whitespace-delimited word."""
    total_words = sum(len(m.content.split()) for m in messages)
    return max(1, int(total_words * 1.3))


def estimate_tokens_from_text(text: str) -> int:
    """Heuristic approximation for completion text."""
    words = len(text.split())
    return max(1, int(words * 1.3))


def normalize_usage(
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    is_estimated: bool = False,
) -> UsageInfo:
    """Creates a normalized UsageInfo instance."""
    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens
    return UsageInfo(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        is_estimated=is_estimated,
    )
