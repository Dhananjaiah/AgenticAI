"""
Policies API endpoints.

Provides endpoints for:
- GET /policies/{policy_id}/claims - Get related claims for a policy
- GET /policies/{policy_id} - Get policy details
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Policy
from app.db.session import get_db
from app.observability.logging_config import get_logger
from app.schemas.claims import ClaimSummary
from app.schemas.policies import PolicyDetail, PolicyWithClaims

router = APIRouter(prefix="/policies", tags=["policies"])
logger = get_logger(__name__)


@router.get("/{policy_id}", response_model=PolicyDetail)
async def get_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
) -> PolicyDetail:
    """
    Get detailed information for a specific policy.

    Args:
        policy_id: The policy ID or policy number
        db: Database session

    Returns:
        PolicyDetail: Detailed policy information
    """
    stmt = select(Policy).where(
        (Policy.id == policy_id) | (Policy.policy_number == policy_id)
    ).options(
        selectinload(Policy.customer),
    )
    result = await db.execute(stmt)
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    customer_name = None
    if policy.customer:
        customer_name = f"{policy.customer.first_name} {policy.customer.last_name}"

    return PolicyDetail(
        id=policy.id,
        policy_number=policy.policy_number,
        customer_id=policy.customer_id,
        customer_name=customer_name,
        policy_type=policy.policy_type,
        coverage_amount=policy.coverage_amount,
        premium=policy.premium,
        start_date=policy.start_date,
        end_date=policy.end_date,
        is_active=policy.is_active,
        metadata=policy.metadata_json or {},
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.get("/{policy_id}/claims", response_model=PolicyWithClaims)
async def get_policy_claims(
    policy_id: str,
    status: str | None = Query(default=None, description="Filter by claim status"),
    db: AsyncSession = Depends(get_db),
) -> PolicyWithClaims:
    """
    Get related claims for a policy.

    Args:
        policy_id: The policy ID or policy number
        status: Optional claim status filter
        db: Database session

    Returns:
        PolicyWithClaims: Policy details with list of related claims
    """
    logger.info("Retrieving claims for policy", policy_id=policy_id)

    stmt = select(Policy).where(
        (Policy.id == policy_id) | (Policy.policy_number == policy_id)
    ).options(
        selectinload(Policy.customer),
        selectinload(Policy.claims),
    )
    result = await db.execute(stmt)
    policy = result.scalar_one_or_none()

    if not policy:
        logger.warning("Policy not found", policy_id=policy_id)
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    # Filter claims by status if provided
    claims = policy.claims
    if status:
        claims = [c for c in claims if c.status.value == status]

    # Calculate totals
    total_claims_amount = sum(c.claim_amount for c in claims)
    total_approved_amount = sum(c.approved_amount or 0 for c in claims)
    active_claims_count = sum(
        1 for c in claims if c.status.value in ("pending", "under_review")
    )

    customer_name = None
    if policy.customer:
        customer_name = f"{policy.customer.first_name} {policy.customer.last_name}"

    claim_summaries = [
        ClaimSummary(
            id=claim.id,
            claim_number=claim.claim_number,
            status=claim.status.value,
            claim_type=claim.claim_type,
            claim_amount=claim.claim_amount,
            filed_date=claim.filed_date,
            policy_number=policy.policy_number,
        )
        for claim in claims
    ]

    return PolicyWithClaims(
        id=policy.id,
        policy_number=policy.policy_number,
        customer_id=policy.customer_id,
        customer_name=customer_name,
        policy_type=policy.policy_type,
        coverage_amount=policy.coverage_amount,
        premium=policy.premium,
        start_date=policy.start_date,
        end_date=policy.end_date,
        is_active=policy.is_active,
        metadata=policy.metadata_json or {},
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        claims=claim_summaries,
        total_claims_amount=total_claims_amount,
        total_approved_amount=total_approved_amount,
        active_claims_count=active_claims_count,
    )


@router.get("/", response_model=list[PolicyDetail])
async def list_policies(
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
) -> list[PolicyDetail]:
    """
    List policies with optional filtering.

    Args:
        is_active: Optional active status filter
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session

    Returns:
        list[PolicyDetail]: List of policy details
    """
    stmt = select(Policy).options(selectinload(Policy.customer))

    if is_active is not None:
        stmt = stmt.where(Policy.is_active == is_active)

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.order_by(Policy.created_at.desc())

    result = await db.execute(stmt)
    policies = result.scalars().all()

    return [
        PolicyDetail(
            id=policy.id,
            policy_number=policy.policy_number,
            customer_id=policy.customer_id,
            customer_name=(
                f"{policy.customer.first_name} {policy.customer.last_name}"
                if policy.customer else None
            ),
            policy_type=policy.policy_type,
            coverage_amount=policy.coverage_amount,
            premium=policy.premium,
            start_date=policy.start_date,
            end_date=policy.end_date,
            is_active=policy.is_active,
            metadata=policy.metadata_json or {},
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
        for policy in policies
    ]
