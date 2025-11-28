"""
Pydantic schemas for deduplication and entity resolution.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DuplicateReviewItem(BaseModel):
    """Single duplicate review item schema."""

    id: str
    document_id_1: str
    document_id_2: str
    document_1_filename: str | None = None
    document_2_filename: str | None = None
    similarity_score: float
    matching_fields: dict[str, Any] = Field(default_factory=dict)
    is_reviewed: bool = False
    review_decision: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class DuplicateReviewResponse(BaseModel):
    """Response for duplicate review listings."""

    items: list[DuplicateReviewItem]
    total: int
    pending_count: int
    reviewed_count: int


class DuplicateReviewDecision(BaseModel):
    """Schema for submitting a duplicate review decision."""

    decision: str  # "merge", "keep_both", "ignore"
    notes: str | None = None


class EntityMatch(BaseModel):
    """Entity matching result schema."""

    entity_id: str
    entity_type: str
    field_name: str
    source_value: str
    matched_value: str
    confidence: float
    match_type: str  # "exact", "fuzzy", "embedding"


class EntityResolutionResult(BaseModel):
    """Entity resolution result schema."""

    source_id: str
    canonical_id: str
    entity_type: str
    matches: list[EntityMatch] = Field(default_factory=list)
    confidence: float
    sources_merged: list[str] = Field(default_factory=list)
    resolved_at: datetime = Field(default_factory=datetime.utcnow)


class DeduplicationCandidate(BaseModel):
    """Deduplication candidate pair schema."""

    document_id_1: str
    document_id_2: str
    claim_id_1: str | None = None
    claim_id_2: str | None = None
    similarity_score: float
    matching_fields: dict[str, Any] = Field(default_factory=dict)
    source_types: list[str] = Field(default_factory=list)
    recommendation: str  # "merge", "review", "keep_separate"
