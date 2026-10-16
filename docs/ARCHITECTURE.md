# LLM Gateway System Architecture

This document describes the architectural design, core subsystems, data flow, resilience strategies, and operational characteristics of the Production LLM Gateway.

---

## 1. High-Level Architecture Overview

```mermaid
flowchart TD
    Client(["HTTP Client / SDK / UI Dashboard"]) --> Gateway["FastAPI LLM Gateway (:8000)"]

    subgraph "Core Gateway Subsystems"
        Auth["API Key & Rate Limiting Engine<br/>(Token Bucket / Quotas)"]
        Guard["Guardrails Pipeline<br/>(PII Redaction / Injection Defense)"]
        Router["Model Router<br/>(Aliases / Capabilities / Offline Rules)"]
        CacheMgr["Multi-Tier Caching Layer<br/>(SHA-256 Redis + Offline Semantic)"]
        Orchestrator["Fallback Orchestrator & Circuit Breakers"]
    end

    Gateway --> Auth
    Auth --> Guard
    Guard --> Router
    Router --> CacheMgr

    CacheMgr -- "Cache Hit" --> Gateway
    CacheMgr -- "Cache Miss" --> Orchestrator

    subgraph "Provider Adapters"
        LocalEng["LocalProvider<br/>(Ollama / LM Studio / vLLM)"]
        MockEng["MockProvider<br/>(Unit Testing / Zero Dep)"]
        OpenAIEng["OpenAICompatibleProvider<br/>(OpenAI / Groq / Anthropic Proxy)"]
    end

    Orchestrator --> LocalEng
    Orchestrator --> MockEng
    Orchestrator --> OpenAIEng

    subgraph "Persistence & Observability"
        DB[(SQLite / SQLAlchemy 2.x<br/>Audits & Keys)]
        RedisCache[(Redis Cluster / Cache)]
        Prometheus[Prometheus Metrics]
        Grafana[Grafana Dashboards]
    end

    Gateway --> DB
    CacheMgr --> RedisCache
    Gateway --> Prometheus
    Prometheus --> Grafana
```

---

## 2. Request Lifecycle & Sequence Flow

```mermaid
sequenceDiagram
    autonumber
    actor Caller as Client (OpenAI SDK / React UI / CLI)
    participant GW as LLM Gateway (FastAPI)
    participant Auth as Tenant & Rate Limiter
    participant Guard as Guardrails Engine
    participant Cache as Hybrid Cache (Redis & Semantic)
    participant Orch as Fallback Orchestrator
    participant CB as Circuit Breaker Registry
    participant Provider as LLM Engine (Local / Cloud)
    participant DB as SQLite Audit Logger

    Caller->>GW: POST /v1/chat/completions (model, messages, stream)
    GW->>Auth: Validate API Key & Evaluate Rate Limit (RPM / Cost / Token Budget)
    alt Rate Limit Exceeded
        Auth-->>Caller: HTTP 429 Too Many Requests (Retry-After)
    end
    GW->>Guard: Scan prompt for PII (redact) & Injection attempts (block/flag)
    alt Prompt Injection Blocked
        Guard-->>Caller: HTTP 400 Bad Request (Injection policy triggered)
    end
    GW->>Cache: Evaluate Exact Match (SHA-256) & Semantic Similarity
    alt Cache Hit
        Cache-->>GW: Return Cached Completion
        alt stream=true
            GW-->>Caller: SSE Stream Chunks (Token Replay)
        else
            GW-->>Caller: HTTP 200 JSON Response (cached=true)
        end
    else Cache Miss
        GW->>Orch: Route Request (Primary Provider)
        Orch->>CB: Check Provider State
        alt CB is OPEN
            Orch->>Orch: Advance to Next Provider in Fallback Chain
        end
        Orch->>Provider: Dispatch Asynchronous HTTP Generation
        alt Primary Fails (5xx / 429 / Timeout)
            Provider-->>Orch: Exception / Error
            Orch->>CB: Record Failure (Trip if Threshold Exceeded)
            Orch->>Provider: Fallback to Secondary Provider
            Provider-->>Orch: Successful Completion
        else Primary Succeeds
            Provider-->>Orch: Successful Completion
            Orch->>CB: Record Success
        end
        Orch->>Cache: Asynchronously store in Redis & Semantic index
        Orch->>DB: Log transaction audit (tokens, latency, cost, routing reason)
        GW-->>Caller: HTTP 200 Normalized Response
    end
```

---

## 3. Subsystem Breakdown

### A. Provider Adapter Layer (`app/providers/`)
All downstream model engines conform to the abstract base interface [`BaseProvider`](file:///c:/Users/Inno/Desktop/lucky/llm-gateway/app/providers/base.py):
- **`LocalProvider`** (`app/providers/local.py`): Connects to local instances of Ollama, LM Studio, vLLM, or llama.cpp over standard REST interfaces. Operates at `$0.00` cost with automatic token estimation.
- **`MockProvider`** (`app/providers/mock.py`): Deterministic test double supporting latency simulation and configurable error injection for chaotic failover testing.
- **`OpenAICompatibleProvider`** (`app/providers/openai.py`): Direct integration with OpenAI, Groq, DeepSeek, or any OpenAI-compatible remote provider.

### B. Fallback Orchestrator & Circuit Breakers (`app/resilience/`)
- **Circuit Breaker**: Implements a three-state finite state machine (`CLOSED`, `OPEN`, `HALF_OPEN`). Providers experiencing consecutive failures beyond threshold (default 3) are tripped `OPEN` for a recovery duration (default 30s) to eliminate outbound latency penalties.
- **Ordered Failover**: Routes through an explicit chain of providers defined in `config/models.yaml` (e.g. `openai -> groq -> local -> mock-secondary`), ensuring continuous availability.
- **Deadline Management**: Implements two-layer timeout cancellation using `asyncio.timeout` for per-provider requests and overall request lifecycles.

### C. Multi-Tier Hybrid Caching (`app/cache/`)
- **Tier 1 (Exact SHA-256)**: Canonical JSON serialization of sorted messages, model name, and generation hyperparameters hashed with SHA-256. Lookups execute in `< 0.05ms` via Redis or in-memory fallback.
- **Tier 2 (Offline Semantic Index)**: Fast subword trigram vector projection mapping text to 128-dimensional unit spheres. High-confidence cosine similarity matches (`>= 0.85`) bypass the LLM completely.
- **Streaming Cache Replay**: Deconstructs cached strings into Server-Sent Event delta tokens streamed back with artificial pacing.

### D. Multi-Tenant API Key Management (`app/persistence/api_keys.py`)
- Supports tenant segmentation with dedicated policies:
  - Sliding-window Requests Per Minute (RPM) rate limits.
  - Daily cost caps (USD) and token allowances.
  - Whitelisted model restrictions.
- Rejects violations with standard HTTP 429 status codes and compliant `Retry-After` headers.

### E. Guardrails & Safety Pipeline (`app/guardrails/`)
- **PII Redaction**: Regex-based zero-allocation scanning and masking for Email Addresses, Phone Numbers (E.164 and domestic formats), and Credit Card / Payment Card Account Numbers.
- **Injection Mitigation**: Multi-heuristic scoring engine identifying prompt escape attempts, role manipulation, and delimiter smuggling with configurable actions (`allow`, `flag`, `block`).
