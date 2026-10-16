# Production-Quality LLM Gateway

A robust, enterprise-grade unified LLM Gateway built from scratch with **FastAPI**, **Pydantic v2**, **Redis caching**, **intelligent model routing**, **circuit breaking**, **automatic fallback**, and **persistent request observability**.

---

## 1. System Overview & Key Features

- **Unified OpenAI-Compatible API (`POST /v1/chat/completions`)**: Accepts standardized requests and returns a normalized response contract regardless of upstream provider.
- **Multi-Provider Adapter Architecture**: Pluggable adapters for real OpenAI-compatible endpoints (OpenAI, Groq, Together, DeepInfra, vLLM) and a deterministic `MockProvider` supporting latency and error simulations for CI and local development without paid credentials.
- **Intelligent Deterministic Routing**: Model alias resolution (`cheap`, `balanced`, `powerful`), prompt-length escalation, task-hint routing (`summarization`, `coding`, `chat`), cost awareness, and circuit-breaker state skipping.
- **Deterministic Redis Response Caching**:
  - Stable SHA-256 cache key generated from canonicalized request JSON.
  - Request-level bypass (`cache: false` or `X-Cache-Bypass: true`) and configurable TTL.
  - Single-flight locking to prevent cache stampedes under concurrent traffic.
  - Graceful degradation: If Redis is offline, the gateway logs a warning and degrades seamlessly without crashing.
- **Resilience Engine**:
  - Per-provider 3-state Circuit Breaker (`CLOSED`, `OPEN`, `HALF_OPEN`).
  - Exponential backoff with jitter and `Retry-After` header respect for transient errors (429, 500, 502, 503, 504).
  - Immediate fail-fast without retry on permanent errors (400, 401, 403).
  - Ordered fallback chain: Automatically switches to eligible backup providers within an overall request deadline.
- **Observability & Cost Accounting**:
  - Async SQLite request audit logging using SQLAlchemy 2.x and `aiosqlite`.
  - Aggregated operational metrics: request counts, cache hits/misses, fallback counts, latency percentiles (`p50`, `p95`, `p99`), token usage, and estimated USD cost based on configurable per-model token prices.
  - Prometheus metrics exposition (`GET /metrics`).
  - Strict secret redaction: API keys, tokens, and authorization headers are never logged or exposed.

---

## 2. Architecture & Request Lifecycle

```
[ Client Request ]
       │
       ▼
[ FastAPI App ] ─── (CORS, Auth Guard, Request ID, Timing Middleware)
       │
       ▼
[ Model Router ] ─── (Alias Resolution: cheap/balanced/powerful, Task hints, Circuit-check)
       │
       ├─────────────────────────────────────────────┐
       ▼ (If cache eligible)                         ▼ (If cache miss or bypass)
[ Redis Cache ]                               [ Fallback Orchestrator ]
  - Check SHA-256 key                           - Overall Request Deadline
  - Single-flight lock                          - Attempt Primary Provider
  - Cache Hit? ──> Return Normalized Response   - If 429/5xx: Exponential Backoff Retry
                                                - If Breaker OPEN / Exhausted:
                                                  Failover to Next Fallback Provider
                                                       │
                                                       ▼
                                              [ Provider Adapter ]
                                                - MockProvider or OpenAICompatibleProvider
                                                       │
                                                       ▼
                                              [ Normalization & Costing ]
                                                - Normalize Choices & Token Usage
                                                - Calculate USD Cost per 1K Tokens
                                                - Cache Result in Redis
                                                - Async Persist in SQLite Log
                                                       │
                                                       ▼
                                              [ Normalized Response ]
```

---

## 3. Quick Start & Local Setup

### Prerequisites
- Python 3.12+ (tested on Python 3.13)
- Optional: Docker and Docker Compose
- Optional: Redis server (gateway automatically falls back to in-memory cache if Redis is not running)

### Local Virtual Environment Setup
```powershell
# 1. Clone / Navigate to llm-gateway
cd llm-gateway

# 2. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install pinned dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env

# 5. Run the gateway with Uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The gateway starts instantly with mock providers enabled by default, requiring **zero external API keys**.

### Running with Docker Compose
```bash
docker compose up --build -d
```
This launches:
- `llm_gateway_api` on port `8000`
- `llm_gateway_redis` on port `6379` with health checks and persistence

---

## 4. API Reference & Representative Examples

### 1. Unified Chat Completion
`POST /v1/chat/completions`

**Request:**
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "cheap",
    "messages": [
      {"role": "user", "content": "Explain consistent hashing in distributed systems."}
    ],
    "temperature": 0.7,
    "max_tokens": 256,
    "cache": true
  }'
```

**Representative Response:**
```json
{
  "id": "mock-cmpl-020588e620c3",
  "request_id": "req-c1cbe9bddfc4",
  "object": "chat.completion",
  "created": 1792134212,
  "model": "mock-model",
  "provider": "mock-primary",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Mock response from [mock-primary] for model [mock-model]: Received 'Explain consistent hashing in distributed sy...'"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 8,
    "completion_tokens": 15,
    "total_tokens": 23,
    "is_estimated": false
  },
  "cached": false,
  "latency_ms": 17.53,
  "cost_usd": 0.000004,
  "routing_reason": "alias:cheap->mock-model"
}
```

*Subsequent identical request returns `"cached": true`, `"latency_ms": 0.75`.*

### 2. Cache Bypass
Add header `X-Cache-Bypass: true` or set `"cache": false` in request body.

### 3. Application Health & Readiness
- `GET /health`: Liveness probe (`{"status":"ok", "app":"LLM-Gateway"}`).
- `GET /ready`: Dependency readiness probe inspecting database, cache, and provider availability.

### 4. Aggregated Operational Statistics
`GET /stats`
```json
{
  "total_requests": 204,
  "successful_requests": 200,
  "failed_requests": 4,
  "cache_hits": 163,
  "cache_misses": 41,
  "cache_hit_rate": 0.799,
  "fallback_count": 0,
  "latency_p50_ms": 1.25,
  "latency_p95_ms": 78.4,
  "latency_p99_ms": 142.1,
  "total_input_tokens": 2450,
  "total_output_tokens": 3120,
  "total_tokens": 5570,
  "total_estimated_cost_usd": 0.000782
}
```

### 5. Configured Providers (Safe Inspection)
`GET /providers` reports configured providers, health, and circuit breaker states without leaking secrets.

### 6. Configured Models & Pricing
`GET /models` returns catalog entries, supported primary/fallback providers, and token pricing.

### 7. Paginated Audit Logs
`GET /logs?page=1&page_size=20&status=success`
Returns sanitized request metadata without storing or exposing unrestricted prompt text.

### 8. Prometheus Metrics
`GET /metrics` exposes standard Prometheus text metrics (`llm_gateway_requests_total`, `llm_gateway_cache_hits_total`, `llm_gateway_latency_ms{quantile="0.50"}`, etc.).

---

## 5. Automated Test Suite

The test suite covers 43 distinct automated test cases across unit, integration, and end-to-end scenarios.

```bash
# Run pytest with verbose output
pytest -v
```

### Test Coverage Highlights
| Category | File | Cases Tested |
|---|---|---|
| **Unit** | `tests/unit/test_cache_keys.py` | Deterministic SHA-256 hashing, parameter sensitivity, metadata isolation |
| **Unit** | `tests/unit/test_cost_and_usage.py` | Token estimation, usage normalization, USD cost formulas |
| **Unit** | `tests/unit/test_circuit_breaker.py` | Closed -> Open -> Half-Open transitions, reset timeouts |
| **Unit** | `tests/unit/test_routing.py` | Explicit models, aliases, task hints, circuit breaker skipping |
| **Unit** | `tests/unit/test_retry_and_exceptions.py` | Transient vs permanent classification, backoff & Retry-After |
| **Unit** | `tests/unit/test_schemas_and_redaction.py` | Pydantic v2 validation, API key and Bearer token redaction |
| **Integration** | `tests/integration/test_adapters.py` | OpenAICompatibleProvider with mocked HTTP transport (200, 401, 429, 500) |
| **Integration** | `tests/integration/test_cache.py` | Cache hits, bypass, stampede single-flight locking, Redis degradation |
| **Integration** | `tests/integration/test_persistence.py` | SQLite async logging, pagination, filtering, percentile stats |
| **E2E** | `tests/e2e/test_api_endpoints.py` | `/health`, `/ready`, `/stats`, `/providers`, `/models`, `/logs`, `/metrics` |
| **E2E** | `tests/e2e/test_fallback_and_deadline.py` | Primary failure -> fallback to secondary, all providers failing, deadline timeout |

**Test Result:** `43 passed in 21.73s`

---

## 6. Benchmarking & Load Testing

### Micro-Benchmarks (`scripts/benchmark.py`)
Measures internal non-network pipeline throughput:
```
Cache key SHA-256 generation: 10,000 ops in 0.0607s (164,649 ops/sec)
Model routing resolution:      10,000 ops in 0.0370s (270,542 ops/sec)
```

### End-to-End Load Test (`scripts/load_test.py`)
Simulates 200 requests with 10 concurrent workers, 30% repeated prompts, mixed cache bypass, and injected transient failures:
```bash
python scripts/load_test.py --requests 200 --concurrency 10
```

**Actual Measured Benchmark Results:**
| Metric | Cache Enabled | Cache Disabled | Performance Gain |
|---|---|---|---|
| **Total Requests** | 200 | 200 | - |
| **Throughput** | 40.21 req/s | 45.22 req/s | - |
| **Successful Requests** | 198 (99.0%) | 193 (96.5%) | +2.5% reliability |
| **Failed Requests** | 2 (1.0%) | 7 (3.5%) | Reduced failures |
| **Cache Hits** | 162 (81.82%) | 0 (0.0%) | - |
| **p50 Latency** | **63.80 ms** | **74.75 ms** | **1.17x faster** |
| **p95 Latency** | **144.37 ms** | **151.26 ms** | Lower tail latency |
| **p99 Latency** | **237.73 ms** | **1861.92 ms** | **7.8x tail latency reduction** |
| **Estimated Cost** | $0.000770 USD | $0.000756 USD | Tracked |

---

## 7. Configuration Reference (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `APP_NAME` | `LLM-Gateway` | Gateway instance name |
| `ENVIRONMENT` | `development` | Deployment environment |
| `DEBUG` | `false` | Enable verbose debugging |
| `GATEWAY_API_KEY` | `None` | Inbound API key (if set, requires `X-API-Key` or `Authorization: Bearer`) |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins list |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `CACHE_ENABLED` | `true` | Enable global response caching |
| `CACHE_DEFAULT_TTL_SECONDS` | `3600` | Default cache TTL (1 hour) |
| `CACHE_LOCK_TIMEOUT_SECONDS` | `10.0` | Stampede lock expiration duration |
| `DATABASE_URL` | `sqlite+aiosqlite:///./gateway.db` | SQLAlchemy async database connection |
| `REQUEST_OVERALL_TIMEOUT_SECONDS` | `30.0` | Maximum overall request budget across all retries |
| `PROVIDER_TIMEOUT_SECONDS` | `10.0` | Maximum timeout for a single provider attempt |
| `MAX_RETRIES` | `3` | Maximum retry attempts per provider |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Consecutive failures before tripping OPEN |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS` | `30.0` | Cooldown before probing HALF_OPEN |
| `OPENAI_MAIN_ENABLED` | `false` | Enable primary OpenAI provider |
| `OPENAI_MAIN_API_KEY` | `None` | OpenAI API key |
| `OPENAI_BACKUP_ENABLED` | `false` | Enable secondary provider (Groq/Together/vLLM) |
| `MOCK_PRIMARY_ENABLED` | `true` | Enable mock primary provider |
| `MOCK_SECONDARY_ENABLED` | `true` | Enable mock secondary fallback provider |

---

## 8. Production Hardening & Deployment Guidelines

1. **Distributed Circuit Breaker & Rate Limiting**:
   - The current circuit breaker is thread-safe and scoped to the ASGI worker process. For multi-replica Kubernetes deployments, state can be synced using Redis Hashes.
2. **PostgreSQL Migration**:
   - For ultra-high write volumes (>5,000 req/s), transition `DATABASE_URL` from SQLite to PostgreSQL (`postgresql+asyncpg://...`) using SQLAlchemy's async driver.
3. **Semantic Caching**:
   - Exact-match SHA-256 canonical caching is implemented. Semantic vector similarity caching can be attached as a secondary cache layer.
4. **Secrets Management**:
   - In production, inject provider API keys via AWS Secrets Manager, Vault, or Kubernetes Secrets rather than plain `.env` files.
