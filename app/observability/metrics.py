"""
Prometheus-compatible metrics collection.

Provides:
- Request latency tracking
- Error counting
- Cache hit rate
- LLM call tracking
- Custom business metrics
"""

import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, Info

from app.observability.logging_config import get_logger

logger = get_logger(__name__)


# Application info
APP_INFO = Info("app", "Application information")

# Request metrics
REQUEST_COUNT = Counter(
    "claims_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "claims_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Cache metrics
CACHE_HITS = Counter("claims_cache_hits_total", "Cache hit count", ["cache_type"])
CACHE_MISSES = Counter("claims_cache_misses_total", "Cache miss count", ["cache_type"])
CACHE_HIT_RATE = Gauge("claims_cache_hit_rate", "Cache hit rate", ["cache_type"])

# LLM metrics
LLM_CALLS = Counter(
    "claims_llm_calls_total",
    "Total LLM API calls",
    ["model", "operation", "status"],
)
LLM_LATENCY = Histogram(
    "claims_llm_call_duration_seconds",
    "LLM call latency in seconds",
    ["model", "operation"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
LLM_TOKENS = Counter(
    "claims_llm_tokens_total",
    "Total LLM tokens used",
    ["model", "token_type"],  # prompt or completion
)

# Business metrics
CLAIMS_PROCESSED = Counter(
    "claims_processed_total",
    "Total claims processed",
    ["status", "claim_type"],
)
DOCUMENTS_INDEXED = Counter(
    "claims_documents_indexed_total",
    "Total documents indexed",
    ["source_type", "file_type"],
)
DEDUPLICATION_RUNS = Counter(
    "claims_deduplication_runs_total",
    "Total deduplication runs",
    ["result"],  # merged, flagged, none
)

# Database metrics
DB_QUERY_LATENCY = Histogram(
    "claims_db_query_duration_seconds",
    "Database query latency",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

# Queue metrics
QUEUE_MESSAGES_PUBLISHED = Counter(
    "claims_queue_messages_published_total",
    "Messages published to queue",
    ["topic"],
)
QUEUE_MESSAGES_CONSUMED = Counter(
    "claims_queue_messages_consumed_total",
    "Messages consumed from queue",
    ["topic", "status"],
)


class MetricsCollector:
    """
    Centralized metrics collector for the application.

    Provides helper methods for recording metrics with proper labels.
    """

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self._start_time = time.time()
        APP_INFO.info({
            "version": "0.1.0",
            "name": "agentic-ai-claims",
        })

    def record_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float,
    ) -> None:
        """
        Record an HTTP request.

        Args:
            method: HTTP method
            endpoint: Request endpoint
            status: Response status code
            duration: Request duration in seconds
        """
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

    def record_cache_access(
        self,
        cache_type: str,
        hit: bool,
    ) -> None:
        """
        Record a cache access.

        Args:
            cache_type: Type of cache (claim_bundle, document, etc.)
            hit: Whether it was a cache hit
        """
        if hit:
            CACHE_HITS.labels(cache_type=cache_type).inc()
        else:
            CACHE_MISSES.labels(cache_type=cache_type).inc()

    def update_cache_hit_rate(
        self,
        cache_type: str,
        hit_rate: float,
    ) -> None:
        """
        Update cache hit rate gauge.

        Args:
            cache_type: Type of cache
            hit_rate: Hit rate (0.0 to 1.0)
        """
        CACHE_HIT_RATE.labels(cache_type=cache_type).set(hit_rate)

    def record_llm_call(
        self,
        model: str,
        operation: str,
        success: bool,
        duration: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """
        Record an LLM API call.

        Args:
            model: Model name
            operation: Operation type (summarize, decide, embed)
            success: Whether the call succeeded
            duration: Call duration in seconds
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
        """
        status = "success" if success else "error"
        LLM_CALLS.labels(model=model, operation=operation, status=status).inc()
        LLM_LATENCY.labels(model=model, operation=operation).observe(duration)

        if prompt_tokens > 0:
            LLM_TOKENS.labels(model=model, token_type="prompt").inc(prompt_tokens)
        if completion_tokens > 0:
            LLM_TOKENS.labels(model=model, token_type="completion").inc(completion_tokens)

    def record_claim_processed(
        self,
        status: str,
        claim_type: str,
    ) -> None:
        """
        Record a claim processing event.

        Args:
            status: Claim status
            claim_type: Type of claim
        """
        CLAIMS_PROCESSED.labels(status=status, claim_type=claim_type).inc()

    def record_document_indexed(
        self,
        source_type: str,
        file_type: str,
    ) -> None:
        """
        Record a document indexing event.

        Args:
            source_type: Source type (sql, sharepoint, blob)
            file_type: File type (pdf, image, etc.)
        """
        DOCUMENTS_INDEXED.labels(source_type=source_type, file_type=file_type).inc()

    def record_deduplication(
        self,
        result: str,
    ) -> None:
        """
        Record a deduplication run.

        Args:
            result: Result type (merged, flagged, none)
        """
        DEDUPLICATION_RUNS.labels(result=result).inc()

    def record_db_query(
        self,
        operation: str,
        duration: float,
    ) -> None:
        """
        Record a database query.

        Args:
            operation: Query operation type
            duration: Query duration in seconds
        """
        DB_QUERY_LATENCY.labels(operation=operation).observe(duration)

    def record_queue_publish(self, topic: str) -> None:
        """Record a message published to queue."""
        QUEUE_MESSAGES_PUBLISHED.labels(topic=topic).inc()

    def record_queue_consume(self, topic: str, success: bool) -> None:
        """Record a message consumed from queue."""
        status = "success" if success else "error"
        QUEUE_MESSAGES_CONSUMED.labels(topic=topic, status=status).inc()

    def get_uptime(self) -> float:
        """Get application uptime in seconds."""
        return time.time() - self._start_time


def track_latency(metric_name: str) -> Callable:
    """
    Decorator to track function latency.

    Args:
        metric_name: Name for the metric

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.time() - start
                DB_QUERY_LATENCY.labels(operation=metric_name).observe(duration)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start
                DB_QUERY_LATENCY.labels(operation=metric_name).observe(duration)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Global metrics collector instance
metrics = MetricsCollector()
