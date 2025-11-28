"""
SQLAlchemy ORM models for the Insurance Claims system.

Includes models for:
- Claims and claim statuses
- Policies and customers
- Documents and metadata
- Indexing state tracking
- Deduplication review
"""

import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid4())


class ClaimStatus(enum.Enum):
    """Enum for claim status values."""

    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    DENIED = "denied"
    CLOSED = "closed"


class DocumentSourceType(enum.Enum):
    """Enum for document source types."""

    SQL = "sql"
    SHAREPOINT = "sharepoint"
    BLOB = "blob"
    S3 = "s3"


class Customer(Base):
    """Customer model representing insurance policy holders."""

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    address: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    policies: Mapped[list["Policy"]] = relationship("Policy", back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer {self.first_name} {self.last_name}>"


class Policy(Base):
    """Insurance policy model."""

    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    policy_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("customers.id"), index=True
    )
    policy_type: Mapped[str] = mapped_column(String(100), nullable=False)
    coverage_amount: Mapped[float] = mapped_column(Float, nullable=False)
    premium: Mapped[float] = mapped_column(Float, nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="policies")
    claims: Mapped[list["Claim"]] = relationship("Claim", back_populates="policy")

    def __repr__(self) -> str:
        return f"<Policy {self.policy_number}>"


class Claim(Base):
    """Insurance claim model."""

    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    claim_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    policy_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("policies.id"), index=True
    )
    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus), default=ClaimStatus.PENDING
    )
    claim_type: Mapped[str] = mapped_column(String(100), nullable=False)
    claim_amount: Mapped[float] = mapped_column(Float, nullable=False)
    approved_amount: Mapped[Optional[float]] = mapped_column(Float)
    description: Mapped[Optional[str]] = mapped_column(Text)
    incident_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    filed_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    adjuster_notes: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    policy: Mapped["Policy"] = relationship("Policy", back_populates="claims")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="claim")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="claim")
    status_history: Mapped[list["ClaimStatusHistory"]] = relationship(
        "ClaimStatusHistory", back_populates="claim"
    )

    __table_args__ = (
        Index("ix_claims_status_filed_date", "status", "filed_date"),
        Index("ix_claims_policy_status", "policy_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Claim {self.claim_number}>"


class ClaimStatusHistory(Base):
    """Tracks claim status changes over time."""

    __tablename__ = "claim_status_history"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    claim_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("claims.id"), index=True
    )
    previous_status: Mapped[Optional[ClaimStatus]] = mapped_column(Enum(ClaimStatus))
    new_status: Mapped[ClaimStatus] = mapped_column(Enum(ClaimStatus), nullable=False)
    changed_by: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    claim: Mapped["Claim"] = relationship("Claim", back_populates="status_history")


class Payment(Base):
    """Payment records for claims."""

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    claim_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("claims.id"), index=True
    )
    payment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
    reference_number: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    claim: Mapped["Claim"] = relationship("Claim", back_populates="payments")


class Document(Base):
    """Document metadata model for tracking all claim-related documents."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    claim_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("claims.id"), index=True
    )
    policy_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("policies.id"), index=True
    )
    source_type: Mapped[DocumentSourceType] = mapped_column(
        Enum(DocumentSourceType), nullable=False
    )
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    checksum: Mapped[Optional[str]] = mapped_column(String(64))
    ocr_text: Mapped[Optional[str]] = mapped_column(Text)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float)
    extracted_entities: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    is_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    claim: Mapped[Optional["Claim"]] = relationship("Claim", back_populates="documents")

    __table_args__ = (
        Index("ix_documents_source_claim", "source_type", "claim_id"),
        Index("ix_documents_indexed", "is_indexed", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Document {self.filename}>"


class IndexingState(Base):
    """Tracks indexing state for incremental updates."""

    __tablename__ = "indexing_state"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    source_type: Mapped[DocumentSourceType] = mapped_column(
        Enum(DocumentSourceType), unique=True, nullable=False
    )
    last_indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_cdc_marker: Mapped[Optional[str]] = mapped_column(String(255))
    items_indexed: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="idle")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class DuplicateReview(Base):
    """Stores low-confidence duplicate pairs for human review."""

    __tablename__ = "duplicate_reviews"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    document_id_1: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("documents.id"), index=True
    )
    document_id_2: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("documents.id"), index=True
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    matching_fields: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    review_decision: Mapped[Optional[str]] = mapped_column(String(50))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_duplicate_reviews_pending", "is_reviewed", "created_at"),
    )


class CanonicalClaimBundle(Base):
    """Stores pre-computed canonical claim bundles for fast retrieval."""

    __tablename__ = "canonical_claim_bundles"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    claim_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("claims.id"), unique=True, index=True
    )
    structured_facts: Mapped[dict] = mapped_column(JSON, nullable=False)
    document_list: Mapped[list] = mapped_column(JSON, default=list)
    dedupe_info: Mapped[dict] = mapped_column(JSON, default=dict)
    llm_context: Mapped[Optional[str]] = mapped_column(Text)
    llm_summary: Mapped[Optional[str]] = mapped_column(Text)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    source_provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
