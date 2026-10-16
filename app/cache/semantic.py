"""Semantic Caching Layer using Offline Vector Cosine Similarity."""

import hashlib
import math
from typing import List, Optional, Tuple

from app.api.schemas import ChatCompletionResponse
from app.core.logging import logger


def _text_to_dense_vector(text: str, dim: int = 128) -> List[float]:
    """Generates a normalized deterministic dense embedding vector for text without external dependencies."""
    words = text.lower().strip().split()
    if not words:
        return [0.0] * dim

    vec = [0.0] * dim

    # Character n-grams and word hashing
    for word in words:
        # Word hash projection
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) == 0 else -1.0
        vec[idx] += sign * 1.5

        # Subword trigrams
        if len(word) >= 3:
            for i in range(len(word) - 2):
                tri = word[i : i + 3]
                th = int(hashlib.sha256(tri.encode("utf-8")).hexdigest(), 16)
                tidx = th % dim
                tsign = 1.0 if ((th >> 8) & 1) == 0 else -1.0
                vec[tidx] += tsign * 0.8

    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0.0:
        return [v / norm for v in vec]
    return vec


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculates cosine similarity between two unit vectors."""
    if len(v1) != len(v2) or not v1:
        return 0.0
    return sum(a * b for a, b in zip(v1, v2))


class SemanticCache:
    """In-memory semantic vector index for fuzzy/similarity cache lookups."""

    def __init__(self, threshold: float = 0.88):
        self.threshold = threshold
        # List of (model, vector, prompt_text, ChatCompletionResponse)
        self._entries: List[Tuple[str, List[float], str, ChatCompletionResponse]] = []

    def lookup(self, model: str, prompt: str) -> Optional[Tuple[ChatCompletionResponse, float]]:
        """Finds closest cached response if similarity exceeds threshold."""
        if not prompt.strip():
            return None

        query_vec = _text_to_dense_vector(prompt)
        best_match: Optional[ChatCompletionResponse] = None
        best_sim = 0.0

        for entry_model, entry_vec, _, resp in self._entries:
            if entry_model != model:
                continue
            sim = _cosine_similarity(query_vec, entry_vec)
            if sim > best_sim:
                best_sim = sim
                best_match = resp

        if best_sim >= self.threshold and best_match is not None:
            logger.info(f"Semantic Cache HIT (similarity: {best_sim:.3f} >= {self.threshold})")
            return best_match.model_copy(deep=True), best_sim

        return None

    def store(self, model: str, prompt: str, response: ChatCompletionResponse) -> None:
        """Stores a prompt vector and response in the semantic cache."""
        if not prompt.strip():
            return

        vec = _text_to_dense_vector(prompt)
        # Keep recent 500 entries to bound memory usage
        if len(self._entries) >= 500:
            self._entries.pop(0)

        self._entries.append((model, vec, prompt, response.model_copy(deep=True)))
