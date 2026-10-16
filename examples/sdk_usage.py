"""Example usage of the LLM Gateway Python Client SDK."""

import asyncio
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway_client import AsyncGatewayClient, GatewayClient


def sync_example():
    print("=== 1. Synchronous GatewayClient Example ===")
    client = GatewayClient(base_url="http://localhost:8000")

    # 1. Check health
    health = client.health()
    print(f"Gateway Status: {health.get('status')} | App: {health.get('app')}")

    # 2. List models
    models = client.models()
    print(f"Registered Models: {len(models)} found. First 3: {[m['name'] for m in models[:3]]}")

    # 3. Create chat completion (Fresh request)
    print("\nSending chat completion for model 'cheap'...")
    resp = client.chat.completions.create(
        model="cheap",
        messages=[{"role": "user", "content": "Explain what an LLM Gateway is in one punchy sentence."}],
        temperature=0.7,
        max_tokens=60,
    )
    print(f"Response: {resp['choices'][0]['message']['content']}")
    print(f"Metadata: Provider={resp['provider']} | Model={resp['model']} | Cached={resp['cached']} | Latency={resp['latency_ms']}ms | Cost=${resp['cost_usd']:.6f}")

    # 4. Create identical chat completion (Expect cache hit)
    print("\nSending identical request to test Redis/in-memory cache...")
    resp_cached = client.chat.completions.create(
        model="cheap",
        messages=[{"role": "user", "content": "Explain what an LLM Gateway is in one punchy sentence."}],
        temperature=0.7,
        max_tokens=60,
    )
    print(f"Cached Response: Cached={resp_cached['cached']} | Latency={resp_cached['latency_ms']}ms (Near-instant!)")


async def async_example():
    print("\n=== 2. Asynchronous AsyncGatewayClient Example ===")
    async_client = AsyncGatewayClient(base_url="http://localhost:8000")

    resp = await async_client.chat.completions.create(
        model="balanced",
        messages=[{"role": "user", "content": "Say 'Async is working!'"}],
    )
    print(f"Async Reply: {resp['choices'][0]['message']['content']}")
    print(f"Provider: {resp['provider']} | Tokens: {resp['usage']['total_tokens']}")


if __name__ == "__main__":
    sync_example()
    asyncio.run(async_example())
