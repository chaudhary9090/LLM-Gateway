"""Repeatable asynchronous load test for LLM Gateway."""

import argparse
import asyncio
import random
import sys
import time
from typing import Any, Dict, List
import httpx


PROMPT_POOL = [
    # Fixed repeated prompts (~30% of total volume)
    "Explain the difference between synchronous and asynchronous programming.",
    "Write a Python function to check if a string is a palindrome.",
    "Summarize the benefits of caching in distributed microservices.",
    "What are the ACID properties in database transaction management?",
    # Dynamic varied prompts
    "Generate a SQL query to find top 5 customers by sales volume.",
    "Explain what a circuit breaker pattern is in distributed systems.",
    "How does token bucket rate limiting differ from leaky bucket?",
    "Write a quicksort implementation in Python.",
    "Describe the Raft consensus algorithm.",
    "What is the role of Redis Sentinel vs Redis Cluster?",
    "Explain exponential backoff with full jitter.",
    "How does HTTP/2 multiplexing improve throughput over HTTP/1.1?",
    "Write a unit test for a FastAPI dependency.",
    "What is the difference between latency and throughput?",
]


async def send_single_request(
    client: httpx.AsyncClient,
    base_url: str,
    prompt: str,
    cache_enabled: bool,
    simulate_error: bool,
    model: str = "mock-model",
) -> Dict[str, Any]:
    """Sends a single completion request and measures latency and status."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 128,
        "cache": cache_enabled,
        "metadata": {"simulate_error": "500" if simulate_error else None},
    }
    start = time.perf_counter()
    try:
        resp = await client.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            timeout=15.0,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        success = (resp.status_code == 200)
        data = resp.json() if success else {}
        cached = data.get("cached", False)
        cost_usd = data.get("cost_usd", 0.0) or 0.0
        provider = data.get("provider", "unknown")
        fallback = (provider == "mock-secondary")
        return {
            "success": success,
            "status_code": resp.status_code,
            "latency_ms": elapsed_ms,
            "cached": cached,
            "cost_usd": cost_usd,
            "fallback": fallback,
            "error": None if success else resp.text[:100],
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "success": False,
            "status_code": 0,
            "latency_ms": elapsed_ms,
            "cached": False,
            "cost_usd": 0.0,
            "fallback": False,
            "error": str(exc),
        }


async def run_load_batch(
    base_url: str,
    total_requests: int,
    concurrency: int,
    cache_mode: bool,
    failure_rate: float,
    seed: int,
) -> Dict[str, Any]:
    """Executes a load test batch with controlled concurrency and prompt distribution."""
    random.seed(seed)
    semaphore = asyncio.Semaphore(concurrency)

    # 30% repeated prompts, 70% selected from full pool
    repeated_prompts = PROMPT_POOL[:4]

    requests_spec = []
    for _ in range(total_requests):
        if random.random() < 0.30:
            prompt = random.choice(repeated_prompts)
        else:
            prompt = random.choice(PROMPT_POOL)

        simulate_error = (random.random() < failure_rate)
        # Mix in 10% explicit cache bypass requests
        req_cache = cache_mode and (random.random() > 0.10)
        requests_spec.append((prompt, req_cache, simulate_error))

    results: List[Dict[str, Any]] = []

    async def worker(spec):
        prompt, req_cache, sim_err = spec
        async with semaphore:
            return await send_single_request(client, base_url, prompt, req_cache, sim_err)

    batch_start = time.perf_counter()
    async with httpx.AsyncClient(timeout=20.0) as client:
        tasks = [asyncio.create_task(worker(spec)) for spec in requests_spec]
        results = await asyncio.gather(*tasks)

    total_time_s = time.perf_counter() - batch_start

    # Compute percentiles and metrics
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    cache_hits = [r for r in successes if r["cached"]]
    fallbacks = [r for r in successes if r["fallback"]]
    total_cost = sum(r["cost_usd"] for r in successes)

    latencies = sorted([r["latency_ms"] for r in results])
    n = len(latencies)

    def p(pct):
        if not latencies:
            return 0.0
        return latencies[int(pct * (n - 1))]

    throughput = len(results) / total_time_s if total_time_s > 0 else 0.0
    error_rate = (len(failures) / len(results) * 100.0) if results else 0.0
    cache_hit_rate = (len(cache_hits) / len(successes) * 100.0) if successes else 0.0

    return {
        "cache_mode": "ENABLED" if cache_mode else "DISABLED",
        "total_requests": len(results),
        "total_time_s": round(total_time_s, 2),
        "throughput_req_per_s": round(throughput, 2),
        "successful_requests": len(successes),
        "failed_requests": len(failures),
        "error_rate_pct": round(error_rate, 2),
        "cache_hits": len(cache_hits),
        "cache_hit_rate_pct": round(cache_hit_rate, 2),
        "fallback_count": len(fallbacks),
        "p50_latency_ms": round(p(0.50), 2),
        "p95_latency_ms": round(p(0.95), 2),
        "p99_latency_ms": round(p(0.99), 2),
        "total_cost_usd": round(total_cost, 6),
    }


def print_report_table(report: Dict[str, Any], title: str = "LOAD TEST RESULTS"):
    print("\n" + "=" * 60)
    print(f" {title} - Cache: {report['cache_mode']}")
    print("=" * 60)
    print(f" Total Requests:         {report['total_requests']}")
    print(f" Total Duration:         {report['total_time_s']} s")
    print(f" Throughput:             {report['throughput_req_per_s']} req/s")
    print(f" Successful Requests:    {report['successful_requests']}")
    print(f" Failed Requests:        {report['failed_requests']} ({report['error_rate_pct']}%)")
    print(f" Cache Hits:             {report['cache_hits']} ({report['cache_hit_rate_pct']}%)")
    print(f" Fallbacks Triggered:    {report['fallback_count']}")
    print(f" Latency p50:            {report['p50_latency_ms']} ms")
    print(f" Latency p95:            {report['p95_latency_ms']} ms")
    print(f" Latency p99:            {report['p99_latency_ms']} ms")
    print(f" Estimated Total Cost:   ${report['total_cost_usd']:.6f} USD")
    print("=" * 60 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="Repeatable Load Test for LLM Gateway")
    parser.add_argument("--requests", type=int, default=200, help="Total requests (minimum 200)")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent workers")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000", help="Gateway URL")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--failure-rate", type=float, default=0.05, help="Simulated error rate (0.0 to 1.0)")
    parser.add_argument("--compare-cache", action="store_true", default=True, help="Compare Cache Enabled vs Disabled")
    args = parser.parse_args()

    print(f"Checking gateway readiness at {args.base_url}...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{args.base_url}/health", timeout=5.0)
            if resp.status_code != 200:
                print(f"Gateway health check returned status {resp.status_code}. Please start the gateway first.")
                sys.exit(1)
    except Exception as exc:
        print(f"Could not connect to gateway at {args.base_url}: {exc}")
        print("Tip: Run 'uvicorn app.main:app --port 8000' before running load test.")
        sys.exit(1)

    print(f"\n[1/2] Running load test batch with CACHE ENABLED ({args.requests} requests, concurrency {args.concurrency})...")
    cache_enabled_report = await run_load_batch(
        base_url=args.base_url,
        total_requests=args.requests,
        concurrency=args.concurrency,
        cache_mode=True,
        failure_rate=args.failure_rate,
        seed=args.seed,
    )
    print_report_table(cache_enabled_report, "RUN A: CACHE ENABLED")

    if args.compare_cache:
        print(f"[2/2] Running load test batch with CACHE DISABLED ({args.requests} requests, concurrency {args.concurrency})...")
        cache_disabled_report = await run_load_batch(
            base_url=args.base_url,
            total_requests=args.requests,
            concurrency=args.concurrency,
            cache_mode=False,
            failure_rate=args.failure_rate,
            seed=args.seed,
        )
        print_report_table(cache_disabled_report, "RUN B: CACHE DISABLED")

        # Comparison summary
        speedup = (
            cache_disabled_report["p50_latency_ms"] / cache_enabled_report["p50_latency_ms"]
            if cache_enabled_report["p50_latency_ms"] > 0 else 1.0
        )
        print("COMPARATIVE PERFORMANCE SUMMARY:")
        print(f" - Throughput: {cache_enabled_report['throughput_req_per_s']} req/s (Cache) vs {cache_disabled_report['throughput_req_per_s']} req/s (No Cache)")
        print(f" - p50 Latency: {cache_enabled_report['p50_latency_ms']} ms (Cache) vs {cache_disabled_report['p50_latency_ms']} ms (No Cache) -> {speedup:.2f}x speedup")
        print(f" - Cache Hit Rate: {cache_enabled_report['cache_hit_rate_pct']}%")


if __name__ == "__main__":
    asyncio.run(main())
