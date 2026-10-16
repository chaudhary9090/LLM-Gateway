# Changelog

All notable changes to the LLM Gateway project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-10-16

### Added
- **Full Offline Operation**:
  - `LocalProvider` adapter supporting Ollama, LM Studio, vLLM, and llama.cpp via OpenAI-compatible endpoints with $0.00 cost configuration.
  - Global `OFFLINE_MODE=true` enforcement restricting all outbound traffic to local models and mock test doubles.
  - Automatic Ollama model auto-discovery on startup (`/api/tags` and `/v1/models`).
- **Developer Experience & Tooling**:
  - Unified CLI (`gateway.py`) with subcommands: `init`, `doctor`, `start`, `models`, `chat`, and `stats`.
  - Python SDK (`gateway_client/`) featuring both synchronous (`GatewayClient`) and asynchronous (`AsyncGatewayClient`) clients.
  - Drop-in compatibility with the official `openai` Python SDK (just change `base_url`).
  - Single-click Windows start and install batch scripts (`run_gateway.bat`, `install_requirements.bat`).
- **Advanced Platform Features**:
  - Real-time Server-Sent Events (SSE) streaming (`POST /v1/chat/completions` with `stream=true`), including streaming cache replay and fallback failover.
  - Vector embeddings endpoint (`POST /v1/embeddings`) with caching and multi-provider adapter support.
  - Offline dense vector `SemanticCache` layer with cosine similarity matching.
  - Multi-tenant API key management with token bucket rate limits (RPM), daily token/cost budgets, and allowed models.
  - Guardrails subsystem: PII redaction (email, phone, credit card numbers) and prompt injection detection (allow/flag/block).
  - Parallel model evaluation endpoint (`POST /v1/compare`).
  - Runtime model configuration hot-reloading (`POST /v1/models/reload`).
  - Optional OpenTelemetry tracing integration (`trace_span`).
- **Production Polish & Observability**:
  - Multi-stage Docker container build with non-root security user (`appuser`).
  - Docker Compose stack with Redis, Vite React frontend, Prometheus, Grafana dashboards, and optional Ollama profile.
  - Comprehensive GitHub Actions CI workflow (linting with Ruff, pytest coverage matrix for Python 3.12 and 3.13, and Docker verification).
  - Automated micro-benchmarking and load testing scripts with verified performance metrics.

---

## [1.0.0] - 2026-10-16

### Added
- Initial release of the LLM Gateway.
- Normalized chat completion endpoint (`POST /v1/chat/completions`).
- Provider adapter abstraction with `MockProvider` and `OpenAICompatibleProvider`.
- Circuit breaker pattern and automatic fallback chains.
- Redis response caching with SHA-256 fingerprinting.
- SQLite audit persistence with SQLAlchemy 2.x.
- Prometheus `/metrics` exposition and JSON structured logging.
- React 18 + TypeScript production dashboard with analytics and interactive playground.
