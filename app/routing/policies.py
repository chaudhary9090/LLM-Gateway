"""Routing models and decision data structures."""

from typing import List

from pydantic import BaseModel, Field


class RoutingDecision(BaseModel):
    """Encapsulates the deterministic routing decision for a chat completion request."""

    requested_model: str
    target_model: str
    primary_provider: str
    fallback_providers: List[str] = Field(default_factory=list)
    routing_reason: str
    cost_tier: str = "default"
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0


class ModelCatalogEntry(BaseModel):
    """Metadata entry for a model configured in models.yaml."""

    name: str
    description: str = ""
    tier: str = "balanced"
    max_tokens: int = 4096
    capabilities: List[str] = Field(default_factory=list)
    input_cost_per_1k: float = 0.001
    output_cost_per_1k: float = 0.002
    primary_provider: str = "mock-primary"
    fallback_providers: List[str] = Field(default_factory=list)
