import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging

logging.getLogger("llm_gateway").setLevel(logging.WARNING)

from app.api.schemas import ChatCompletionRequest, ChatMessage  # noqa: E402
from app.cache.keys import generate_cache_key  # noqa: E402
from app.routing.router import ModelRouter  # noqa: E402


def benchmark_cache_key_generation(iterations: int = 10000):
    req = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[
            ChatMessage(role="system", content="You are an expert software architect."),
            ChatMessage(role="user", content="Explain how consistent hashing works in distributed caches."),
        ],
        temperature=0.7,
        max_tokens=1024,
    )
    start = time.perf_counter()
    for _ in range(iterations):
        generate_cache_key(req, "gpt-4o-mini")
    duration = time.perf_counter() - start
    ops_per_sec = iterations / duration
    print(f"Cache key SHA-256 generation: {iterations} ops in {duration:.4f}s ({ops_per_sec:,.0f} ops/sec)")


def benchmark_model_routing(iterations: int = 10000):
    router = ModelRouter("config/models.yaml")
    req = ChatCompletionRequest(
        model="cheap",
        messages=[ChatMessage(role="user", content="Quick task")],
    )
    start = time.perf_counter()
    for _ in range(iterations):
        router.route(req)
    duration = time.perf_counter() - start
    ops_per_sec = iterations / duration
    print(f"Model routing resolution:      {iterations} ops in {duration:.4f}s ({ops_per_sec:,.0f} ops/sec)")


if __name__ == "__main__":
    print("\n--- LLM Gateway Micro-Benchmarks ---")
    benchmark_cache_key_generation()
    benchmark_model_routing()
    print("------------------------------------\n")
