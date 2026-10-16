# ADR 002: Multi-Tier Caching (Exact SHA-256 and Offline Semantic Similarity)

## Status
Accepted

## Context
High LLM call volumes incur significant financial cost and user-perceived latency (often 500ms to several seconds per call). Many incoming queries are identical or semantically equivalent. While exact hash caching achieves microsecond retrieval, it fails when queries differ slightly by phrasing, punctuation, or capitalization. Furthermore, traditional semantic caching systems often depend on cloud embedding APIs, violating offline requirements and adding network hops.

## Decision
We implemented a two-tier hybrid caching pipeline:
1. **Tier 1: Deterministic Exact-Match Cache**:
   - Generates a SHA-256 fingerprint over normalized request payloads: model, role-delineated message contents, temperature, and token parameters.
   - Backed by Redis with configurable TTL (default 3600s) and automatic, non-blocking in-memory fallback if Redis is unavailable.
   - Sub-millisecond lookup (< 0.01 ms key generation, > 130,000 ops/sec).
2. **Tier 2: Offline Semantic Similarity Cache**:
   - Projects prompt text into dense unit vectors using a deterministic subword n-gram and token hashing kernel without external embedding API dependencies.
   - Evaluates similarity against recent cached responses using cosine similarity against a configurable threshold (default 0.85).
   - Serves near-duplicate queries with zero provider roundtrips while preserving offline compatibility.
3. **Streaming Cache Replay**:
   - When a client issues a streaming request (`stream=true`) that results in a cache hit, the gateway parses the cached completion text, tokenizes it into SSE delta chunks (`chat.completion.chunk`), and streams it with artificial cadence, matching standard OpenAI SSE behavior.

## Consequences
- **Positive**: Drastic cost reduction (up to 75%+ in high repetition workloads), sub-30ms p50 latency on cache hits, and zero cloud lock-in for semantic matching.
- **Trade-offs**: Cache invalidation must be handled by callers using explicit `cache: false` flags or TTL expiration.
