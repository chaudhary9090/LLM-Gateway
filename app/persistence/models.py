"""SQLAlchemy ORM models for request audit logging and telemetry."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.database import Base


class RequestLog(Base):
    """Stores full execution telemetry for every gateway chat completion request."""

    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False,
    )
    requested_model: Mapped[str] = mapped_column(String(64), nullable=False)
    target_model: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # "success" or "failure"
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    fallback_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    routing_reason: Mapped[str] = mapped_column(String(256), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_request_logs_provider_model", "provider", "target_model"),
        Index("ix_request_logs_timestamp_status", "timestamp", "status"),
    )
