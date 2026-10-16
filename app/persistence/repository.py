"""Data access repository for request logs and aggregated metrics."""

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import case, desc, func, select

from app.api.schemas import GatewayStatsResponse, RequestLogItem
from app.core.logging import logger
from app.persistence.database import AsyncSessionLocal
from app.persistence.models import RequestLog


class RequestLogRepository:
    """Handles asynchronous recording and analytical querying of request logs."""

    @staticmethod
    async def log_request(
        request_id: str,
        requested_model: str,
        target_model: str,
        provider: str,
        status: str,
        cache_hit: bool,
        attempt_count: int,
        fallback_count: int,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        estimated_cost_usd: float,
        routing_reason: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Persists a single request execution record asynchronously."""
        try:
            async with AsyncSessionLocal() as session:
                log_entry = RequestLog(
                    request_id=request_id,
                    requested_model=requested_model,
                    target_model=target_model,
                    provider=provider,
                    status=status,
                    cache_hit=cache_hit,
                    attempt_count=attempt_count,
                    fallback_count=fallback_count,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    estimated_cost_usd=estimated_cost_usd,
                    routing_reason=routing_reason,
                    error_message=error_message,
                )
                session.add(log_entry)
                await session.commit()
        except Exception as e:
            # Telemetry logging must never break or crash the client's request
            logger.error(f"Failed to persist request log for {request_id}: {e}")

    @staticmethod
    async def get_paginated_logs(
        page: int = 1,
        page_size: int = 20,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[List[RequestLogItem], int]:
        """Returns paginated request logs with optional filters."""
        try:
            async with AsyncSessionLocal() as session:
                query = select(RequestLog)

                if provider:
                    query = query.where(RequestLog.provider == provider)
                if model:
                    query = query.where(RequestLog.target_model == model)
                if status:
                    query = query.where(RequestLog.status == status)
                if start_time:
                    query = query.where(RequestLog.timestamp >= start_time)
                if end_time:
                    query = query.where(RequestLog.timestamp <= end_time)

                # Count total matching
                count_query = select(func.count()).select_from(query.subquery())
                total = (await session.execute(count_query)).scalar_one()

                # Pagination
                offset = (max(1, page) - 1) * page_size
                query = query.order_by(desc(RequestLog.timestamp)).offset(offset).limit(page_size)
                records = (await session.execute(query)).scalars().all()

                items = [
                    RequestLogItem(
                        request_id=r.request_id,
                        timestamp=r.timestamp.isoformat(),
                        model=r.target_model,
                        provider=r.provider,
                        status=r.status,
                        cache_hit=r.cache_hit,
                        attempt_count=r.attempt_count,
                        fallback_count=r.fallback_count,
                        latency_ms=round(r.latency_ms, 2),
                        input_tokens=r.input_tokens,
                        output_tokens=r.output_tokens,
                        total_tokens=r.total_tokens,
                        estimated_cost_usd=round(r.estimated_cost_usd, 6),
                        routing_reason=r.routing_reason,
                        error_message=r.error_message,
                    )
                    for r in records
                ]
                return items, total
        except Exception as e:
            logger.error(f"Error fetching paginated logs: {e}")
            return [], 0

    @staticmethod
    async def get_aggregated_stats() -> GatewayStatsResponse:
        """Calculates aggregate metrics across all historical requests."""
        try:
            async with AsyncSessionLocal() as session:
                # Basic counts and sums
                stats_query = select(
                    func.count(RequestLog.id).label("total"),
                    func.sum(case((RequestLog.status == "success", 1), else_=0)).label("successes"),
                    func.sum(case((RequestLog.status == "failure", 1), else_=0)).label("failures"),
                    func.sum(case((RequestLog.cache_hit.is_(True), 1), else_=0)).label("cache_hits"),
                    func.sum(case((RequestLog.cache_hit.is_(False), 1), else_=0)).label("cache_misses"),
                    func.sum(RequestLog.fallback_count).label("total_fallbacks"),
                    func.sum(RequestLog.input_tokens).label("total_input_tokens"),
                    func.sum(RequestLog.output_tokens).label("total_output_tokens"),
                    func.sum(RequestLog.total_tokens).label("total_tokens"),
                    func.sum(RequestLog.estimated_cost_usd).label("total_cost"),
                )
                res = (await session.execute(stats_query)).one()

                total_requests = res.total or 0
                successful_requests = res.successes or 0
                failed_requests = res.failures or 0
                cache_hits = res.cache_hits or 0
                cache_misses = res.cache_misses or 0
                fallback_count = res.total_fallbacks or 0
                total_input_tokens = res.total_input_tokens or 0
                total_output_tokens = res.total_output_tokens or 0
                total_tokens = res.total_tokens or 0
                total_estimated_cost_usd = round(float(res.total_cost or 0.0), 6)

                cache_hit_rate = (
                    round(cache_hits / total_requests, 4) if total_requests > 0 else 0.0
                )

                # Latency percentiles
                latency_query = select(RequestLog.latency_ms)
                latencies = (await session.execute(latency_query)).scalars().all()

                if latencies:
                    lat_arr = sorted([float(x) for x in latencies])
                    n = len(lat_arr)

                    def get_p(p_ratio: float) -> float:
                        idx = int(p_ratio * (n - 1))
                        return lat_arr[idx]

                    p50 = get_p(0.50)
                    p95 = get_p(0.95)
                    p99 = get_p(0.99)
                else:
                    p50, p95, p99 = 0.0, 0.0, 0.0

                return GatewayStatsResponse(
                    total_requests=total_requests,
                    successful_requests=successful_requests,
                    failed_requests=failed_requests,
                    cache_hits=cache_hits,
                    cache_misses=cache_misses,
                    cache_hit_rate=cache_hit_rate,
                    fallback_count=fallback_count,
                    latency_p50_ms=round(p50, 2),
                    latency_p95_ms=round(p95, 2),
                    latency_p99_ms=round(p99, 2),
                    total_input_tokens=total_input_tokens,
                    total_output_tokens=total_output_tokens,
                    total_tokens=total_tokens,
                    total_estimated_cost_usd=total_estimated_cost_usd,
                )
        except Exception as e:
            logger.error(f"Error computing aggregated stats: {e}")
            return GatewayStatsResponse(
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                cache_hits=0,
                cache_misses=0,
                cache_hit_rate=0.0,
                fallback_count=0,
                latency_p50_ms=0.0,
                latency_p95_ms=0.0,
                latency_p99_ms=0.0,
                total_input_tokens=0,
                total_output_tokens=0,
                total_tokens=0,
                total_estimated_cost_usd=0.0,
            )
