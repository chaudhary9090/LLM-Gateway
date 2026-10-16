"""Prometheus metrics generation for the /metrics endpoint."""

from app.persistence.repository import RequestLogRepository


async def generate_prometheus_metrics() -> str:
    """Generates standard Prometheus text exposition format metrics from current statistics."""
    stats = await RequestLogRepository.get_aggregated_stats()

    lines = [
        "# HELP llm_gateway_requests_total Total number of chat completion requests.",
        "# TYPE llm_gateway_requests_total counter",
        f"llm_gateway_requests_total {stats.total_requests}",
        "",
        "# HELP llm_gateway_successful_requests_total Total number of successful requests.",
        "# TYPE llm_gateway_successful_requests_total counter",
        f"llm_gateway_successful_requests_total {stats.successful_requests}",
        "",
        "# HELP llm_gateway_failed_requests_total Total number of failed requests.",
        "# TYPE llm_gateway_failed_requests_total counter",
        f"llm_gateway_failed_requests_total {stats.failed_requests}",
        "",
        "# HELP llm_gateway_cache_hits_total Total number of cache hits.",
        "# TYPE llm_gateway_cache_hits_total counter",
        f"llm_gateway_cache_hits_total {stats.cache_hits}",
        "",
        "# HELP llm_gateway_cache_misses_total Total number of cache misses.",
        "# TYPE llm_gateway_cache_misses_total counter",
        f"llm_gateway_cache_misses_total {stats.cache_misses}",
        "",
        "# HELP llm_gateway_cache_hit_ratio Ratio of cache hits to total requests.",
        "# TYPE llm_gateway_cache_hit_ratio gauge",
        f"llm_gateway_cache_hit_ratio {stats.cache_hit_rate:.4f}",
        "",
        "# HELP llm_gateway_fallbacks_total Total provider fallback occurrences.",
        "# TYPE llm_gateway_fallbacks_total counter",
        f"llm_gateway_fallbacks_total {stats.fallback_count}",
        "",
        "# HELP llm_gateway_latency_ms Latency percentiles in milliseconds.",
        "# TYPE llm_gateway_latency_ms gauge",
        f'llm_gateway_latency_ms{{quantile="0.50"}} {stats.latency_p50_ms:.2f}',
        f'llm_gateway_latency_ms{{quantile="0.95"}} {stats.latency_p95_ms:.2f}',
        f'llm_gateway_latency_ms{{quantile="0.99"}} {stats.latency_p99_ms:.2f}',
        "",
        "# HELP llm_gateway_input_tokens_total Cumulative prompt tokens consumed.",
        "# TYPE llm_gateway_input_tokens_total counter",
        f"llm_gateway_input_tokens_total {stats.total_input_tokens}",
        "",
        "# HELP llm_gateway_output_tokens_total Cumulative completion tokens produced.",
        "# TYPE llm_gateway_output_tokens_total counter",
        f"llm_gateway_output_tokens_total {stats.total_output_tokens}",
        "",
        "# HELP llm_gateway_estimated_cost_usd_total Cumulative estimated cost in USD.",
        "# TYPE llm_gateway_estimated_cost_usd_total counter",
        f"llm_gateway_estimated_cost_usd_total {stats.total_estimated_cost_usd:.6f}",
    ]

    return "\n".join(lines) + "\n"
