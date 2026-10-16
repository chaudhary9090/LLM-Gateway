"""FastAPI application entry point, lifecycle management, and exception handlers."""

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.api.schemas import ErrorDetail, ErrorResponse
from app.cache.base import BaseCache
from app.cache.redis_cache import InMemoryCache, RedisCache
from app.core.config import settings
from app.core.exceptions import GatewayException
from app.core.logging import logger
from app.persistence.database import close_db, init_db
from app.providers.registry import build_provider_registry
from app.resilience.circuit_breaker import CircuitBreakerRegistry
from app.resilience.fallback import FallbackOrchestrator
from app.routing.router import ModelRouter
from app.services.gateway import GatewayService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and graceful shutdown lifecycle."""
    logger.info(f"Starting {settings.app_name} in {settings.environment} mode...")

    # 1. Initialize persistent SQLite tables
    await init_db()

    # 2. Build provider adapters
    registry = build_provider_registry(settings)

    # 3. Initialize circuit breaker registry
    circuit_breakers = CircuitBreakerRegistry(
        default_failure_threshold=settings.circuit_breaker_failure_threshold,
        default_recovery_timeout=settings.circuit_breaker_recovery_timeout_seconds,
        default_half_open_successes=settings.circuit_breaker_half_open_successes,
    )

    # 4. Initialize fallback orchestrator
    orchestrator = FallbackOrchestrator(
        registry=registry,
        circuit_breakers=circuit_breakers,
        max_retries=settings.max_retries,
        overall_timeout_seconds=settings.request_overall_timeout_seconds,
        provider_timeout_seconds=settings.provider_timeout_seconds,
        min_wait=settings.retry_min_wait_seconds,
        max_wait=settings.retry_max_wait_seconds,
    )

    # 5. Initialize model router
    router = ModelRouter(config_path=settings.models_config_path)

    # 6. Initialize cache layer with resilient fallback
    cache: BaseCache
    if settings.cache_enabled:
        redis_cache = RedisCache(redis_url=settings.redis_url)
        is_redis_up = await redis_cache.health_check()
        if is_redis_up:
            logger.info("Connected to Redis cache successfully.")
            cache = redis_cache
        else:
            logger.warning("Redis is unreachable. Falling back to in-memory cache.")
            cache = InMemoryCache()
    else:
        logger.info("Caching is globally disabled.")
        cache = InMemoryCache()

    # 7. Create Gateway Service and attach to app state
    gateway_service = GatewayService(
        settings=settings,
        router=router,
        orchestrator=orchestrator,
        cache=cache,
    )
    app.state.gateway_service = gateway_service
    app.state.cache = cache

    logger.info("Gateway service initialized and ready to accept traffic.")

    yield

    # Shutdown sequence
    logger.info("Shutting down Gateway service...")
    await cache.close()
    await close_db()
    logger.info("Gateway service terminated cleanly.")


def create_app() -> FastAPI:
    """Builds and configures the FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        description="Unified LLM Gateway with caching, routing, circuit breaking, and automatic fallback.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request tracking middleware
    @app.middleware("http")
    async def add_process_time_and_request_id(request: Request, call_next):
        start_time = time.perf_counter()
        req_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Process-Time-Ms"] = str(round(elapsed_ms, 2))
        return response

    # Exception Handlers
    @app.exception_handler(GatewayException)
    async def gateway_exception_handler(request: Request, exc: GatewayException):
        req_id = getattr(request.state, "request_id", f"req-{uuid.uuid4().hex[:8]}")
        logger.warning(f"GatewayException handled: {exc.error_code} - {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=exc.error_code,
                    message=exc.message,
                    request_id=req_id,
                    is_retryable=exc.is_retryable,
                    details=exc.details,
                )
            ).model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = getattr(request.state, "request_id", f"req-{uuid.uuid4().hex[:8]}")
        error_details = {"errors": exc.errors()}
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="validation_error",
                    message="Request payload failed schema validation.",
                    request_id=req_id,
                    is_retryable=False,
                    details=error_details,
                )
            ).model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", f"req-{uuid.uuid4().hex[:8]}")
        logger.error(f"Unhandled internal error for request {req_id}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="internal_server_error",
                    message="An unexpected internal gateway error occurred.",
                    request_id=req_id,
                    is_retryable=True,
                )
            ).model_dump(mode="json"),
        )

    # Register API routers
    app.include_router(api_router)

    return app


app = create_app()
