"""OpenTelemetry compatible request tracing support."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Optional

from app.core.config import settings

_OTEL_AVAILABLE = False
try:
    from opentelemetry import trace
    _tracer = trace.get_tracer("llm-gateway", "0.2.0")
    _OTEL_AVAILABLE = True
except ImportError:
    _tracer = None


@asynccontextmanager
async def trace_span(span_name: str, attributes: Optional[Dict[str, str]] = None) -> AsyncGenerator[None, None]:
    """Context manager for tracing operations with OpenTelemetry if enabled."""
    if _OTEL_AVAILABLE and _tracer and getattr(settings, "otel_enabled", False):
        with _tracer.start_as_current_span(span_name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, str(v))
            yield
    else:
        yield
