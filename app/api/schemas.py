"""Pydantic v2 schemas for API requests and normalized responses."""

import time
import uuid
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

RoleType = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    """Single chat message representing role and textual content."""

    role: RoleType = Field(..., description="Role of the message author")
    content: str = Field(
        ..., min_length=1, max_length=100000, description="Text content of the message"
    )


class ChatCompletionRequest(BaseModel):
    """Normalized chat completion request payload."""

    model: str = Field(..., min_length=1, description="Model identifier or routing alias")
    messages: List[ChatMessage] = Field(
        ..., min_length=1, description="List of messages in conversation"
    )
    temperature: Optional[float] = Field(
        default=0.7, ge=0.0, le=2.0, description="Sampling temperature"
    )
    max_tokens: Optional[int] = Field(
        default=1024, gt=0, le=32768, description="Max tokens to generate"
    )
    timeout: Optional[float] = Field(
        default=None, gt=0.0, le=120.0, description="Optional request timeout in seconds"
    )
    cache: Optional[bool] = Field(
        default=True, description="Enable or bypass Redis caching for this request"
    )
    stream: Optional[bool] = Field(
        default=False, description="Enable Server-Sent Events (SSE) streaming"
    )
    task_type: Optional[str] = Field(
        default=None, description="Optional hint for routing rules (e.g. summarization, coding)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Arbitrary client metadata"
    )

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages: List[ChatMessage]) -> List[ChatMessage]:
        if not messages:
            raise ValueError("messages list must contain at least one message")
        return messages

    model_config = {
        "json_schema_extra": {
            "example": {
                "model": "balanced",
                "messages": [
                    {"role": "system", "content": "You are a concise technical architect."},
                    {"role": "user", "content": "Explain single-flight cache locking in one sentence."},
                ],
                "temperature": 0.7,
                "max_tokens": 128,
                "cache": True,
                "task_type": "chat",
            }
        }
    }


class UsageInfo(BaseModel):
    """Token usage tracking and cost estimation."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    is_estimated: bool = Field(
        default=False, description="True if tokens were heuristically estimated"
    )


class ChoiceMessage(BaseModel):
    """Choice message contained in normalized response."""

    role: str = "assistant"
    content: str = ""


class ChatChoice(BaseModel):
    """Individual completion choice."""

    index: int = 0
    message: ChoiceMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    """Normalized response schema returned across all providers and cached responses."""

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    request_id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    provider: str
    choices: List[ChatChoice]
    usage: UsageInfo
    cached: bool = False
    latency_ms: float = 0.0
    cost_usd: Optional[float] = None
    routing_reason: Optional[str] = None


class ErrorDetail(BaseModel):
    """Structured error payload."""

    code: str
    message: str
    request_id: str
    is_retryable: bool = False
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standardized API error response body."""

    error: ErrorDetail


class HealthResponse(BaseModel):
    """Application health status."""

    status: str = "ok"
    app: str
    environment: str
    timestamp: float


class DependencyStatus(BaseModel):
    """Individual component readiness."""

    status: str
    message: Optional[str] = None


class ReadyResponse(BaseModel):
    """Application readiness status."""

    status: str
    dependencies: Dict[str, DependencyStatus]
    offline_mode: bool = False


class ProviderSummary(BaseModel):
    """Safe provider configuration and status report."""

    name: str
    type: str
    enabled: bool
    healthy: bool
    circuit_state: str
    failure_count: int


class ModelConfigSummary(BaseModel):
    """Safe model metadata and cost config report."""

    name: str
    tier: str
    capabilities: List[str]
    primary_provider: str
    fallback_providers: List[str]
    input_cost_per_1k: float
    output_cost_per_1k: float


class GatewayStatsResponse(BaseModel):
    """Aggregated operational statistics."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float
    fallback_count: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_estimated_cost_usd: float


class RequestLogItem(BaseModel):
    """Single request log record for audit endpoints."""

    request_id: str
    timestamp: str
    model: str
    provider: str
    status: str
    cache_hit: bool
    attempt_count: int
    fallback_count: int
    latency_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    routing_reason: Optional[str] = None
    error_message: Optional[str] = None


class PaginatedLogsResponse(BaseModel):
    """Paginated list of request logs."""

    items: List[RequestLogItem]
    total: int
    page: int
    page_size: int


class EmbeddingRequest(BaseModel):
    """Normalized OpenAI-compatible embedding request payload."""

    input: Union[str, List[str]] = Field(..., description="String or array of strings to embed")
    model: str = Field(default="text-embedding-3-small", description="Model to use for embedding")
    user: Optional[str] = None
    encoding_format: Optional[str] = "float"


class EmbeddingData(BaseModel):
    """Individual embedding vector result."""

    object: str = "embedding"
    index: int
    embedding: List[float]


class EmbeddingResponse(BaseModel):
    """Normalized embedding response payload."""

    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: Dict[str, int]
    cached: bool = False


class CompareRequest(BaseModel):
    """Request payload for multi-model concurrent comparison."""

    models: List[str] = Field(..., min_length=2, max_length=5, description="List of 2-5 models to compare")
    messages: List[ChatMessage] = Field(..., min_length=1, description="Messages to send to each model")
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 512


class ModelComparisonResult(BaseModel):
    """Side-by-side comparison result for one model."""

    model: str
    provider: str
    content: str
    latency_ms: float
    tokens: int
    cost_usd: float
    cached: bool
    error: Optional[str] = None


class CompareResponse(BaseModel):
    """Aggregated side-by-side comparison response."""

    prompt: str
    results: List[ModelComparisonResult]


class ReloadModelsResponse(BaseModel):
    """Response returned after hot-reloading models.yaml."""

    status: str
    models_count: int
    message: str
