"""
Pydantic schemas for claims-related data.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import SourceProvenance


class ClaimBase(BaseModel):
    """Base claim schema."""

    claim_number: str
    claim_type: str
    claim_amount: float
    description: str | None = None
    incident_date: datetime


class ClaimCreate(ClaimBase):
    """Schema for creating a new claim."""

    policy_id: str


class ClaimSummary(BaseModel):
    """Summary schema for claim listings."""

    id: str
    claim_number: str
    status: str
    claim_type: str
    claim_amount: float
    filed_date: datetime
    policy_number: str | None = None

    class Config:
        from_attributes = True


class ClaimStatusInfo(BaseModel):
    """Claim status information schema."""

    current_status: str
    previous_status: str | None = None
    changed_at: datetime | None = None
    changed_by: str | None = None


class ClaimDetail(BaseModel):
    """Detailed claim information schema."""

    id: str
    claim_number: str
    policy_id: str
    policy_number: str | None = None
    customer_name: str | None = None
    status: str
    claim_type: str
    claim_amount: float
    approved_amount: float | None = None
    description: str | None = None
    incident_date: datetime
    filed_date: datetime
    resolved_date: datetime | None = None
    adjuster_notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status_history: list[ClaimStatusInfo] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentInfo(BaseModel):
    """Document information within a claim bundle."""

    id: str
    filename: str
    file_type: str
    source_type: str
    source_path: str
    file_size: int | None = None
    ocr_confidence: float | None = None
    tags: list[str] = Field(default_factory=list)
    extracted_entities: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DedupeInfo(BaseModel):
    """Deduplication information schema."""

    merged_document_ids: list[str] = Field(default_factory=list)
    duplicate_candidates: list[dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = 1.0
    low_confidence_pairs: list[dict[str, Any]] = Field(default_factory=list)


class LLMContextBundle(BaseModel):
    """LLM-ready context bundle schema."""

    structured_facts: dict[str, Any]
    document_summaries: list[str] = Field(default_factory=list)
    ocr_snippets: list[str] = Field(default_factory=list)
    relevant_chunks: list[str] = Field(default_factory=list)
    total_tokens: int = 0


class LLMSummary(BaseModel):
    """LLM-generated summary schema."""

    summary: str
    decision: str | None = None
    confidence: float = 0.0
    explanation: str | None = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_used: str | None = None


class CanonicalClaimBundle(BaseModel):
    """Complete canonical claim bundle response schema."""

    claim_id: str
    claim_number: str
    structured_facts: dict[str, Any]
    document_list: list[DocumentInfo] = Field(default_factory=list)
    dedupe_info: DedupeInfo = Field(default_factory=DedupeInfo)
    llm_context: LLMContextBundle | None = None
    llm_summary: LLMSummary | None = None
    source_provenance: list[SourceProvenance] = Field(default_factory=list)
    confidence_score: float = 1.0
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    is_stale: bool = False


class ClaimRefreshResponse(BaseModel):
    """Response for claim refresh operations."""

    claim_id: str
    message: str
    refresh_started: bool
    job_id: str | None = None
    estimated_completion: datetime | None = None
