"""API Route definitions for the unified LLM Gateway."""

import time
import uuid
from datetime import datetime
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.api.dependencies import get_gateway_service, verify_api_key
from app.api.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    CompareRequest,
    CompareResponse,
    DependencyStatus,
    EmbeddingRequest,
    EmbeddingResponse,
    GatewayStatsResponse,
    HealthResponse,
    ModelConfigSummary,
    PaginatedLogsResponse,
    ProviderSummary,
    ReadyResponse,
    ReloadModelsResponse,
)
from app.core.config import settings
from app.persistence.database import engine
from app.persistence.repository import RequestLogRepository
from app.services.gateway import GatewayService
from app.services.metrics import generate_prometheus_metrics

router = APIRouter()


@router.post(
    "/v1/chat/completions",
    response_model=None,
    summary="Create chat completion",
    tags=["Chat Completions"],
    dependencies=[Depends(verify_api_key)],
)
async def create_chat_completion(
    request: ChatCompletionRequest,
    req: Request,
    gateway_service: GatewayService = Depends(get_gateway_service),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
    x_cache_bypass: Optional[str] = Header(None, alias="X-Cache-Bypass"),
) -> Union[ChatCompletionResponse, StreamingResponse]:
    """Unified OpenAI-compatible chat completion endpoint with caching, routing, fallback, and streaming."""
    client_request_id = x_request_id or f"req-{uuid.uuid4().hex[:12]}"

    # Check tenant policy rate limits if attached
    policy = getattr(req.state, "api_key_policy", None)
    if policy:
        policy.check_and_record_request(request.model)

    # Check header cache bypass
    if x_cache_bypass and x_cache_bypass.lower() in ("1", "true", "yes"):
        request.cache = False

    if request.stream:
        return StreamingResponse(
            gateway_service.complete_stream(
                request=request,
                client_request_id=client_request_id,
            ),
            media_type="text/event-stream",
            headers={"X-Request-ID": client_request_id},
        )

    response = await gateway_service.complete(
        request=request,
        client_request_id=client_request_id,
    )
    if policy:
        policy.record_usage(response.usage.total_tokens, response.cost_usd or 0.0)
    return response


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Basic liveness check",
    tags=["System & Readiness"],
)
async def health_check() -> HealthResponse:
    """Liveness probe returning application status."""
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
        timestamp=time.time(),
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe for dependencies",
    tags=["System & Readiness"],
)
async def readiness_check(
    req: Request,
    gateway_service: GatewayService = Depends(get_gateway_service),
) -> ReadyResponse:
    """Readiness probe checking database, cache, and provider availability."""
    dependencies = {}

    # 1. Database check
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        dependencies["database"] = DependencyStatus(
            status="healthy", message="SQLite database accessible"
        )
    except Exception as e:
        dependencies["database"] = DependencyStatus(status="degraded", message=str(e))

    # 2. Cache check
    try:
        cache_ok = await gateway_service.cache.health_check()
        dependencies["cache"] = DependencyStatus(
            status="healthy" if cache_ok else "degraded",
            message="Cache reachable" if cache_ok else "Cache backend degraded or offline",
        )
    except Exception as e:
        dependencies["cache"] = DependencyStatus(status="degraded", message=str(e))

    # 3. Provider checks
    try:
        provider_health = await gateway_service.orchestrator.registry.health_check_all()
        healthy_count = sum(1 for v in provider_health.values() if v)
        dependencies["providers"] = DependencyStatus(
            status="healthy" if healthy_count > 0 else "degraded",
            message=f"{healthy_count}/{len(provider_health)} providers healthy",
        )
    except Exception as e:
        dependencies["providers"] = DependencyStatus(status="degraded", message=str(e))

    overall_status = (
        "healthy" if any(d.status == "healthy" for d in dependencies.values()) else "unhealthy"
    )

    return ReadyResponse(
        status=overall_status,
        dependencies=dependencies,
        offline_mode=settings.offline_mode,
    )


@router.get(
    "/stats",
    response_model=GatewayStatsResponse,
    summary="Aggregated operational stats",
    tags=["Observability & Telemetry"],
)
async def get_gateway_stats(
    _: bool = Depends(verify_api_key),
) -> GatewayStatsResponse:
    """Returns aggregated request counts, cache hits, fallbacks, latencies, and token costs."""
    return await RequestLogRepository.get_aggregated_stats()


@router.get(
    "/providers",
    response_model=List[ProviderSummary],
    summary="Configured providers",
    tags=["Providers & Models"],
)
async def list_providers(
    gateway_service: GatewayService = Depends(get_gateway_service),
    _: bool = Depends(verify_api_key),
) -> List[ProviderSummary]:
    """Returns safe summary of configured providers without exposing secrets."""
    results = []
    providers = gateway_service.orchestrator.registry.list_all()
    circuit_breakers = gateway_service.orchestrator.circuit_breakers

    for provider in providers:
        breaker = circuit_breakers.get_or_create(provider.name)
        healthy = await provider.health_check() if provider.enabled else False
        results.append(
            ProviderSummary(
                name=provider.name,
                type=provider.provider_type,
                enabled=provider.enabled,
                healthy=healthy,
                circuit_state=breaker.state.value,
                failure_count=breaker.failure_count,
            )
        )
    return results


@router.get(
    "/models",
    response_model=List[ModelConfigSummary],
    summary="Configured models and pricing",
    tags=["Providers & Models"],
)
async def list_models(
    gateway_service: GatewayService = Depends(get_gateway_service),
    _: bool = Depends(verify_api_key),
) -> List[ModelConfigSummary]:
    """Returns catalog of configured models, capabilities, fallback providers, and pricing per 1K tokens."""
    catalog = gateway_service.router.get_catalog()
    return [
        ModelConfigSummary(
            name=entry.name,
            tier=entry.tier,
            capabilities=entry.capabilities,
            primary_provider=entry.primary_provider,
            fallback_providers=entry.fallback_providers,
            input_cost_per_1k=entry.input_cost_per_1k,
            output_cost_per_1k=entry.output_cost_per_1k,
        )
        for entry in catalog.values()
    ]


@router.get(
    "/logs",
    response_model=PaginatedLogsResponse,
    summary="Paginated request audit logs",
    tags=["Audit Logging"],
)
async def get_logs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    provider: Optional[str] = Query(None, description="Filter by provider name"),
    model: Optional[str] = Query(None, description="Filter by target model"),
    status: Optional[str] = Query(None, description="Filter by status (success/failure)"),
    start_time: Optional[datetime] = Query(None, description="ISO timestamp filter"),
    end_time: Optional[datetime] = Query(None, description="ISO timestamp filter"),
    _: bool = Depends(verify_api_key),
) -> PaginatedLogsResponse:
    """Returns paginated request metadata without raw user prompts."""
    items, total = await RequestLogRepository.get_paginated_logs(
        page=page,
        page_size=page_size,
        provider=provider,
        model=model,
        status=status,
        start_time=start_time,
        end_time=end_time,
    )
    return PaginatedLogsResponse(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Prometheus metrics",
    tags=["Observability & Telemetry"],
)
async def get_metrics() -> str:
    """Exposes Prometheus-compatible operational metrics."""
    return await generate_prometheus_metrics()


@router.post(
    "/v1/embeddings",
    response_model=EmbeddingResponse,
    summary="Create text embeddings",
    tags=["Embeddings"],
    dependencies=[Depends(verify_api_key)],
)
async def create_embeddings(
    request: EmbeddingRequest,
    gateway_service: GatewayService = Depends(get_gateway_service),
) -> EmbeddingResponse:
    """Generates embedding vectors with automatic caching and offline local support."""
    return await gateway_service.create_embeddings(request)


@router.post(
    "/v1/compare",
    response_model=CompareResponse,
    summary="Compare multiple models side-by-side",
    tags=["Model Comparison"],
    dependencies=[Depends(verify_api_key)],
)
async def compare_models(
    request: CompareRequest,
    gateway_service: GatewayService = Depends(get_gateway_service),
) -> CompareResponse:
    """Runs the prompt concurrently across multiple models and returns answers, latencies, and costs."""
    return await gateway_service.compare_models(request)


@router.post(
    "/v1/models/reload",
    response_model=ReloadModelsResponse,
    summary="Hot-reload models.yaml",
    tags=["Providers & Models"],
    dependencies=[Depends(verify_api_key)],
)
async def reload_models(
    gateway_service: GatewayService = Depends(get_gateway_service),
) -> ReloadModelsResponse:
    """Hot-reloads model catalog and routing aliases from models.yaml without restarting."""
    gateway_service.router.reload_config()
    count = len(gateway_service.router.get_catalog())
    return ReloadModelsResponse(
        status="success",
        models_count=count,
        message=f"Reloaded {count} models from {gateway_service.router.config_path}",
    )
