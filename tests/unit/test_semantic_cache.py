"""Unit tests for offline SemanticCache and vector similarity."""

from app.api.schemas import (
    ChatChoice,
    ChatCompletionResponse,
    ChoiceMessage,
    UsageInfo,
)
from app.cache.semantic import SemanticCache, _cosine_similarity, _text_to_dense_vector


def test_dense_vector_and_cosine_similarity():
    # Identical texts must yield similarity 1.0
    v1 = _text_to_dense_vector("What is Redis response caching?")
    v2 = _text_to_dense_vector("What is Redis response caching?")
    sim_identical = _cosine_similarity(v1, v2)
    assert round(sim_identical, 3) == 1.0

    # Very similar texts must have high similarity (> 0.65)
    v3 = _text_to_dense_vector("Explain Redis response caching")
    sim_close = _cosine_similarity(v1, v3)
    assert sim_close > 0.65

    # Unrelated texts must have lower similarity
    v4 = _text_to_dense_vector("How do I make chocolate chip pancakes from scratch?")
    sim_distant = _cosine_similarity(v1, v4)
    assert sim_distant < 0.40


def test_semantic_cache_store_and_lookup():
    cache = SemanticCache(threshold=0.65)
    dummy_resp = ChatCompletionResponse(
        id="cmpl-sem-1",
        request_id="req-sem-1",
        created=1700000000,
        model="gpt-4o-mini",
        provider="mock-primary",
        choices=[
            ChatChoice(
                index=0,
                message=ChoiceMessage(role="assistant", content="Redis is an in-memory key-value store."),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(prompt_tokens=8, completion_tokens=8, total_tokens=16),
        cached=False,
        latency_ms=10.0,
        cost_usd=0.0001,
    )

    cache.store("gpt-4o-mini", "What is Redis response caching?", dummy_resp)

    # Similar query lookup should hit
    hit = cache.lookup("gpt-4o-mini", "Explain Redis response caching")
    assert hit is not None
    resp, sim = hit
    assert sim >= 0.65
    assert "Redis is an in-memory" in resp.choices[0].message.content

    # Unrelated query should miss
    miss = cache.lookup("gpt-4o-mini", "Bake chocolate chip cookies recipe")
    assert miss is None

