"""
SQL Retriever Agent.

Autogen agent for retrieving claim data from PostgreSQL database.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Claim, Customer, Policy, Payment, Document
from app.db.session import get_db_context
from app.config import get_settings
from app.observability.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class SQLRetrieverAgent:
    """
    Autogen agent for SQL data retrieval.

    Provides parameterized queries with pagination for:
    - Claims
    - Customers
    - Policies
    - Payments
    - Statuses
    """

    def __init__(self) -> None:
        """Initialize the SQL retriever agent."""
        self._config = self._build_config()
        logger.info("SQL retriever agent initialized")

    def _build_config(self) -> dict[str, Any]:
        """Build Autogen configuration for SQL retriever."""
        return {
            "name": "SQLRetriever",
            "system_message": """You are a SQL data retrieval agent. Your role is to 
            fetch claim-related data from the PostgreSQL database efficiently.
            
            When asked to retrieve data:
            1. Use parameterized queries for security
            2. Apply pagination for large result sets
            3. Include related entities as needed
            4. Return metadata with rows
            5. Tag data with claimId/policyId
            """,
            "human_input_mode": "NEVER",
        }

    async def retrieve_by_claim_id(
        self,
        claim_id: str,
        include_related: bool = True,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """
        Retrieve claim data by claim ID.

        Args:
            claim_id: Claim ID or claim number
            include_related: Whether to include related entities
            page: Page number
            page_size: Page size

        Returns:
            dict: Retrieved data with metadata
        """
        logger.info(
            "SQL retrieval by claim_id",
            claim_id=claim_id,
            include_related=include_related,
        )

        async with get_db_context() as db:
            return await self._fetch_claim_data(
                db, claim_id, include_related, page, page_size
            )

    async def retrieve_by_policy_id(
        self,
        policy_id: str,
        include_claims: bool = True,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """
        Retrieve policy data by policy ID.

        Args:
            policy_id: Policy ID or policy number
            include_claims: Whether to include related claims
            page: Page number
            page_size: Page size

        Returns:
            dict: Retrieved data with metadata
        """
        logger.info(
            "SQL retrieval by policy_id",
            policy_id=policy_id,
            include_claims=include_claims,
        )

        async with get_db_context() as db:
            return await self._fetch_policy_data(
                db, policy_id, include_claims, page, page_size
            )

    async def _fetch_claim_data(
        self,
        db: AsyncSession,
        claim_id: str,
        include_related: bool,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """Internal method to fetch claim data."""
        stmt = select(Claim).where(
            (Claim.id == claim_id) | (Claim.claim_number == claim_id)
        )

        if include_related:
            stmt = stmt.options(
                selectinload(Claim.policy).selectinload(Policy.customer),
                selectinload(Claim.documents),
                selectinload(Claim.payments),
                selectinload(Claim.status_history),
            )

        result = await db.execute(stmt)
        claim = result.scalar_one_or_none()

        if not claim:
            return {
                "success": False,
                "error": f"Claim {claim_id} not found",
                "source": "sql",
                "metadata": {},
                "rows": [],
            }

        # Build response
        claim_data = self._serialize_claim(claim)

        return {
            "success": True,
            "source": "sql",
            "metadata": {
                "claim_id": claim.id,
                "claim_number": claim.claim_number,
                "policy_id": claim.policy_id,
                "retrieved_at": "now",
                "record_count": 1,
            },
            "rows": [claim_data],
        }

    async def _fetch_policy_data(
        self,
        db: AsyncSession,
        policy_id: str,
        include_claims: bool,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """Internal method to fetch policy data."""
        stmt = select(Policy).where(
            (Policy.id == policy_id) | (Policy.policy_number == policy_id)
        )

        if include_claims:
            stmt = stmt.options(
                selectinload(Policy.customer),
                selectinload(Policy.claims),
            )

        result = await db.execute(stmt)
        policy = result.scalar_one_or_none()

        if not policy:
            return {
                "success": False,
                "error": f"Policy {policy_id} not found",
                "source": "sql",
                "metadata": {},
                "rows": [],
            }

        # Build response
        policy_data = self._serialize_policy(policy)

        return {
            "success": True,
            "source": "sql",
            "metadata": {
                "policy_id": policy.id,
                "policy_number": policy.policy_number,
                "retrieved_at": "now",
                "record_count": 1,
            },
            "rows": [policy_data],
        }

    def _serialize_claim(self, claim: Claim) -> dict[str, Any]:
        """Serialize claim to dictionary."""
        data = {
            "id": claim.id,
            "claim_number": claim.claim_number,
            "policy_id": claim.policy_id,
            "status": claim.status.value,
            "claim_type": claim.claim_type,
            "claim_amount": claim.claim_amount,
            "approved_amount": claim.approved_amount,
            "description": claim.description,
            "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
            "filed_date": claim.filed_date.isoformat() if claim.filed_date else None,
            "resolved_date": claim.resolved_date.isoformat() if claim.resolved_date else None,
            "created_at": claim.created_at.isoformat() if claim.created_at else None,
        }

        if claim.policy:
            data["policy"] = self._serialize_policy(claim.policy)

        if claim.documents:
            data["documents"] = [
                self._serialize_document(doc) for doc in claim.documents
            ]

        if claim.payments:
            data["payments"] = [
                self._serialize_payment(payment) for payment in claim.payments
            ]

        return data

    def _serialize_policy(self, policy: Policy) -> dict[str, Any]:
        """Serialize policy to dictionary."""
        data = {
            "id": policy.id,
            "policy_number": policy.policy_number,
            "customer_id": policy.customer_id,
            "policy_type": policy.policy_type,
            "coverage_amount": policy.coverage_amount,
            "premium": policy.premium,
            "start_date": policy.start_date.isoformat() if policy.start_date else None,
            "end_date": policy.end_date.isoformat() if policy.end_date else None,
            "is_active": policy.is_active,
        }

        if policy.customer:
            data["customer"] = {
                "id": policy.customer.id,
                "name": f"{policy.customer.first_name} {policy.customer.last_name}",
                "email": policy.customer.email,
            }

        return data

    def _serialize_document(self, doc: Document) -> dict[str, Any]:
        """Serialize document to dictionary."""
        return {
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "source_type": doc.source_type.value,
            "source_path": doc.source_path,
            "checksum": doc.checksum,
            "is_indexed": doc.is_indexed,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }

    def _serialize_payment(self, payment: Payment) -> dict[str, Any]:
        """Serialize payment to dictionary."""
        return {
            "id": payment.id,
            "payment_type": payment.payment_type,
            "amount": payment.amount,
            "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
            "reference_number": payment.reference_number,
        }

    def get_metadata_only(self, claim_id: str) -> dict[str, Any]:
        """
        Get metadata-only response for a claim.

        This is the first step in metadata-first retrieval.

        Args:
            claim_id: Claim ID

        Returns:
            dict: Metadata about available data
        """
        return {
            "source": "sql",
            "claim_id": claim_id,
            "available_tables": ["claims", "policies", "customers", "payments", "documents"],
            "fetch_content": self.retrieve_by_claim_id,
        }
