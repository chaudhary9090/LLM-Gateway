# ADR 003: Fault Tolerance, Circuit Breakers, and Automatic Fallbacks

## Status
Accepted

## Context
Upstream LLM providers suffer from intermittent HTTP 5xx errors, rate limits (HTTP 429), connection timeouts, and regional service degradations. Without intelligent resilience, user requests fail completely or hang indefinitely, degrading the availability of downstream applications.

## Decision
We implemented a resilient orchestration architecture featuring:
1. **Per-Provider Circuit Breakers**:
   - Implements state-machine transitions: `CLOSED` -> `OPEN` (after consecutive failures exceed threshold) -> `HALF_OPEN` (after recovery cooldown) -> `CLOSED` (on consecutive successes).
   - Fast-fails requests routed to open providers immediately, avoiding connection timeout penalties.
2. **Provider Failover Chains**:
   - Each model configuration declares a primary provider and an ordered fallback chain (e.g. `openai -> groq -> local -> mock-secondary`).
   - If an error occurs (5xx, 429, timeout, network exception) or if the primary breaker is open, the gateway logs the incident, increments the Prometheus `llm_gateway_fallbacks_total` counter, and automatically invokes the next healthy provider in the sequence.
3. **Deadlines and Timeouts**:
   - Enforces dual timeout tiers: a tight per-provider timeout preventing slow providers from exhausting connection pools, and a global end-to-end deadline capping total orchestration duration.
4. **Transparent Routing Auditing**:
   - All responses include `routing_reason`, `provider`, and `latency_ms` headers and payload metadata for full observability.

## Consequences
- **Positive**: 99.9%+ availability under provider failure; self-healing circuit breakers prevent catastrophic failure cascades.
- **Trade-offs**: Fallbacks across differing foundation model architectures can produce slightly different completion styles or formats.
