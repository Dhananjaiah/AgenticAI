"""
Pydantic schemas module for API I/O and internal DTOs.
"""

from app.schemas.claims import (
    CanonicalClaimBundle,
    ClaimBase,
    ClaimCreate,
    ClaimDetail,
    ClaimRefreshResponse,
    ClaimSummary,
)
from app.schemas.documents import DocumentMetadata, DocumentResponse
from app.schemas.policies import PolicyBase, PolicyDetail, PolicyWithClaims
from app.schemas.common import (
    HealthResponse,
    MessageResponse,
    PaginatedResponse,
)
from app.schemas.deduplication import DuplicateReviewItem, DuplicateReviewResponse

__all__ = [
    "CanonicalClaimBundle",
    "ClaimBase",
    "ClaimCreate",
    "ClaimDetail",
    "ClaimRefreshResponse",
    "ClaimSummary",
    "DocumentMetadata",
    "DocumentResponse",
    "PolicyBase",
    "PolicyDetail",
    "PolicyWithClaims",
    "HealthResponse",
    "MessageResponse",
    "PaginatedResponse",
    "DuplicateReviewItem",
    "DuplicateReviewResponse",
]
