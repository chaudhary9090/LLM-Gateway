# ADR 001: Offline-First Architecture & Local Model Orchestration

## Status
Accepted

## Context
Production AI applications frequently suffer from third-party vendor outages, rate limits, network latency spikes, data privacy constraints, and ongoing cloud costs. Developers and organizations need an LLM Gateway that can operate entirely offline without external internet connectivity while supporting real local LLM weights (e.g. via Ollama, LM Studio, vLLM, or llama.cpp) alongside mock providers for zero-dependency testing.

## Decision
We implemented a first-class `LocalProvider` adapter adhering to standard OpenAI-compatible HTTP schemas (`/v1/chat/completions`, `/v1/embeddings`) with a global `OFFLINE_MODE` configuration toggle:
1. **Zero Outbound Calls**: When `OFFLINE_MODE=true`, the Gateway router strictly filters eligible providers to local engines (`local`, `mock-primary`, `mock-secondary`). Any request routed to external APIs is intercepted and rejected with a clear operational reason.
2. **Auto-Discovery Service**: At startup, the Gateway initiates a discovery sweep against local engines (e.g., Ollama `/api/tags` and `/v1/models`), automatically populating the live catalog with installed models.
3. **Cost Invariance**: All local model inferences are configured with `$0.00` per-token costs.
4. **Resilient Local Fallback**: Model configurations support fallback chains that transition gracefully from cloud models to local instances or mock providers when network degradation occurs.

## Consequences
- **Positive**: Complete operational autonomy in air-gapped environments or during cloud outages; zero secret requirements for offline development; seamless drop-in transition from cloud to edge.
- **Trade-offs**: Local inference throughput and concurrency are bounded by the host machine's GPU/VRAM hardware constraints.
