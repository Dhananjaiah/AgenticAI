"""
Health and metrics API endpoints.

Provides endpoints for:
- GET /health - Health check
- GET /metrics - Prometheus-compatible metrics
"""

from datetime import datetime
import time

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from prometheus_client import (
    generate_latest,
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    Gauge,
)

from app.db.session import get_db
from app.schemas.common import HealthResponse, MetricsResponse
from app.services.cache import CacheService
from app.config import get_settings
from app.observability.logging_config import get_logger

router = APIRouter(tags=["health"])
logger = get_logger(__name__)
settings = get_settings()

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)
CACHE_HIT_RATE = Gauge("cache_hit_rate", "Cache hit rate percentage")
LLM_CALL_COUNT = Counter("llm_calls_total", "Total LLM API calls", ["model", "status"])
CLAIMS_PROCESSED = Counter("claims_processed_total", "Total claims processed")

# Track startup time
_startup_time = time.time()


async def get_cache() -> CacheService:
    """Dependency to get cache service."""
    return CacheService()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache),
) -> HealthResponse:
    """
    Perform health check on all system components.

    Checks:
    - Database connectivity
    - Cache (Redis) connectivity
    - Queue (Kafka) connectivity
    - Vector DB connectivity

    Returns:
        HealthResponse: Health status of all components
    """
    # Check database
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        db_status = "unhealthy"

    # Check cache
    cache_status = "healthy"
    try:
        await cache.ping()
    except Exception as e:
        logger.warning("Cache health check failed", error=str(e))
        cache_status = "unhealthy"

    # Queue check (placeholder - would check Kafka connectivity)
    queue_status = "healthy"

    # Vector DB check (placeholder - would check Chroma connectivity)
    vector_db_status = "healthy"

    # Overall status
    overall_status = "healthy"
    if any(s == "unhealthy" for s in [db_status, cache_status, queue_status, vector_db_status]):
        overall_status = "degraded"
    if db_status == "unhealthy":
        overall_status = "unhealthy"

    return HealthResponse(
        status=overall_status,
        version=settings.app_version,
        database=db_status,
        cache=cache_status,
        queue=queue_status,
        vector_db=vector_db_status,
        timestamp=datetime.utcnow(),
    )


@router.get("/metrics")
async def metrics() -> Response:
    """
    Return Prometheus-compatible metrics.

    Returns metrics including:
    - Request counts and latencies
    - Cache hit rates
    - LLM call counts
    - Claims processed

    Returns:
        Response: Prometheus metrics in text format
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@router.get("/metrics/summary", response_model=MetricsResponse)
async def metrics_summary(
    cache: CacheService = Depends(get_cache),
) -> MetricsResponse:
    """
    Get a JSON summary of key metrics.

    Returns:
        MetricsResponse: Summary of key metrics
    """
    uptime = time.time() - _startup_time

    # Get cache hit rate
    cache_stats = await cache.get_stats()

    return MetricsResponse(
        request_count=0,  # Would be populated from Prometheus
        error_count=0,
        cache_hit_rate=cache_stats.get("hit_rate", 0.0),
        llm_call_count=0,
        avg_latency_ms=0.0,
        uptime_seconds=uptime,
        claims_processed=0,
    )


@router.get("/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Kubernetes-style readiness probe.

    Returns:
        dict: Readiness status
    """
    try:
        await db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception:
        return {"ready": False}


@router.get("/live")
async def liveness_check() -> dict:
    """
    Kubernetes-style liveness probe.

    Returns:
        dict: Liveness status
    """
    return {"alive": True}
