"""
Pydantic schemas for policy-related data.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.claims import ClaimSummary


class PolicyBase(BaseModel):
    """Base policy schema."""

    policy_number: str
    policy_type: str
    coverage_amount: float
    premium: float
    start_date: datetime
    end_date: datetime


class PolicyCreate(PolicyBase):
    """Schema for creating a new policy."""

    customer_id: str


class PolicyDetail(BaseModel):
    """Detailed policy information schema."""

    id: str
    policy_number: str
    customer_id: str
    customer_name: str | None = None
    policy_type: str
    coverage_amount: float
    premium: float
    start_date: datetime
    end_date: datetime
    is_active: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PolicyWithClaims(PolicyDetail):
    """Policy detail with associated claims."""

    claims: list[ClaimSummary] = Field(default_factory=list)
    total_claims_amount: float = 0.0
    total_approved_amount: float = 0.0
    active_claims_count: int = 0
