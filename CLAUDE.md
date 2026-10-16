# CLAUDE.md — LLM Gateway Developer Reference

## Overview
A production-grade, highly reliable, unified LLM Gateway built with FastAPI, Pydantic v2, HTTPX, Redis caching, SQLite persistent telemetry, Tenacity retries, and Circuit Breaker pattern. It routes normalized chat completion requests across OpenAI-compatible providers, fallbacks automatically on failure, deduplicates identical requests via Redis cache (with cache stampede protection), tracks token usage, calculates estimated costs, and stores complete audit logs.

## Quick Commands
- Virtual Environment: `.\.venv\Scripts\Activate.ps1` or run via `.\.venv\Scripts\python.exe`
- Install dependencies: `pip install -r requirements.txt`
- Run gateway locally: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- Run test suite: `pytest` or `pytest -v`
- Run linting: `ruff check .`
- Run load test: `python scripts/load_test.py --requests 200 --concurrency 10`
- Run benchmark: `python scripts/benchmark.py`
- Docker Compose: `docker-compose up --build`

## Key Architecture
- `app/api`: FastAPI routes, request/response schemas, API key & dependency injection
- `app/core`: Configuration (`pydantic-settings`), structured JSON logging, domain exceptions
- `app/providers`: Provider adapters (`BaseProvider`, `OpenAICompatibleProvider`, `MockProvider`), registry
- `app/routing`: Intelligent routing engine, model alias resolution, capability/cost/fallback policies
- `app/cache`: Deterministic SHA-256 cache key canonicalization, async Redis cache, single-flight locking
- `app/resilience`: Circuit breaker (Closed/Open/Half-Open), exponential backoff retries, fallback orchestrator
- `app/services`: Gateway orchestration service, token usage normalization, cost estimation, Prometheus metrics
- `app/persistence`: Async SQLite database, SQLAlchemy 2.x models, request logging & aggregated stats repository
- `config/models.yaml`: Declarative model catalog, capabilities, routing hints, pricing per 1K tokens

## Code Conventions
- Strict typing with Python 3.12+ annotations
- Async I/O for all I/O operations (HTTPX, Redis, aiosqlite)
- Graceful degradation: Gateway functions even if Redis or SQLite is temporarily unavailable
- Zero secret leakage: Never log or expose API keys, credentials, or sensitive headers
