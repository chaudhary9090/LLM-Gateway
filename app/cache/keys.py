"""Deterministic cache key canonicalization and hashing."""

import hashlib
import json
from typing import Any, Dict

from app.api.schemas import ChatCompletionRequest


def build_canonical_request_dict(
    request: ChatCompletionRequest, target_model: str, schema_version: str = "v1"
) -> Dict[str, Any]:
    """Extracts and canonicalizes all generation-affecting parameters into a stable dictionary."""
    canonical_messages = [
        {"role": m.role.strip().lower(), "content": m.content.strip()} for m in request.messages
    ]

    return {
        "v": schema_version,
        "model": target_model.strip().lower(),
        "messages": canonical_messages,
        "temperature": round(request.temperature, 4) if request.temperature is not None else 0.7,
        "max_tokens": request.max_tokens or 1024,
    }


def generate_cache_key(
    request: ChatCompletionRequest,
    target_model: str,
    schema_version: str = "v1",
) -> str:
    """Computes a deterministic SHA-256 cache key from canonicalized request parameters."""
    canonical_dict = build_canonical_request_dict(request, target_model, schema_version)
    # Sort keys for deterministic JSON serialization
    serialized = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    key_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"llm_cache:{schema_version}:{target_model}:{key_hash}"
