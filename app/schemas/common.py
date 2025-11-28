"""
Common Pydantic schemas used across the application.
"""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MessageResponse(BaseModel):
    """Generic message response schema."""

    message: str
    success: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    version: str
    database: str
    cache: str
    queue: str
    vector_db: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response schema."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class ErrorDetail(BaseModel):
    """Error detail schema."""

    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str
    details: list[ErrorDetail] | None = None
    correlation_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MetricsResponse(BaseModel):
    """Metrics response schema."""

    request_count: int
    error_count: int
    cache_hit_rate: float
    llm_call_count: int
    avg_latency_ms: float
    uptime_seconds: float
    claims_processed: int


class SourceProvenance(BaseModel):
    """Source provenance tracking schema."""

    source_type: str
    source_path: str
    retrieved_at: datetime
    checksum: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)
