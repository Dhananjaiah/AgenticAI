"""
Claims API endpoints.

Provides endpoints for:
- GET /claims/{claim_id} - Get full canonical bundle for a claim
- POST /claims/{claim_id}/refresh - Trigger re-index/re-dedupe for a claim
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Claim, CanonicalClaimBundle as CanonicalClaimBundleModel
from app.db.session import get_db
from app.schemas.claims import (
    CanonicalClaimBundle,
    ClaimDetail,
    ClaimRefreshResponse,
    ClaimSummary,
    DedupeInfo,
    DocumentInfo,
    LLMContextBundle,
    LLMSummary,
)
from app.schemas.common import SourceProvenance
from app.services.orchestrator import ClaimsOrchestrator
from app.observability.logging_config import get_logger

router = APIRouter(prefix="/claims", tags=["claims"])
logger = get_logger(__name__)


async def get_orchestrator() -> ClaimsOrchestrator:
    """Dependency to get the claims orchestrator."""
    return ClaimsOrchestrator()


@router.get("/{claim_id}", response_model=CanonicalClaimBundle)
async def get_claim_bundle(
    claim_id: str,
    include_llm_summary: bool = Query(default=False, description="Include LLM-generated summary"),
    force_refresh: bool = Query(default=False, description="Force refresh from sources"),
    db: AsyncSession = Depends(get_db),
    orchestrator: ClaimsOrchestrator = Depends(get_orchestrator),
) -> CanonicalClaimBundle:
    """
    Get the full canonical bundle for a claim.

    Returns structured facts, document list, dedupe info, LLM-ready context,
    and optionally an LLM summary.

    Args:
        claim_id: The claim ID or claim number
        include_llm_summary: Whether to include LLM-generated summary
        force_refresh: Force refresh from all sources
        db: Database session
        orchestrator: Claims orchestrator instance

    Returns:
        CanonicalClaimBundle: Complete claim bundle
    """
    logger.info("Retrieving claim bundle", claim_id=claim_id, include_llm_summary=include_llm_summary)

    # Try to find claim by ID or claim number
    stmt = select(Claim).where(
        (Claim.id == claim_id) | (Claim.claim_number == claim_id)
    ).options(
        selectinload(Claim.policy),
        selectinload(Claim.documents),
        selectinload(Claim.payments),
        selectinload(Claim.status_history),
    )
    result = await db.execute(stmt)
    claim = result.scalar_one_or_none()

    if not claim:
        logger.warning("Claim not found", claim_id=claim_id)
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    # Check for cached canonical bundle if not forcing refresh
    if not force_refresh:
        bundle_stmt = select(CanonicalClaimBundleModel).where(
            CanonicalClaimBundleModel.claim_id == claim.id
        )
        bundle_result = await db.execute(bundle_stmt)
        cached_bundle = bundle_result.scalar_one_or_none()

        if cached_bundle and not cached_bundle.is_stale:
            logger.info("Returning cached bundle", claim_id=claim_id)
            return _convert_db_bundle_to_response(cached_bundle, claim, include_llm_summary)

    # Use orchestrator to build fresh bundle
    bundle = await orchestrator.build_claim_bundle(
        claim_id=claim.id,
        include_llm_summary=include_llm_summary,
        db=db,
    )

    return bundle


@router.get("/{claim_id}/detail", response_model=ClaimDetail)
async def get_claim_detail(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
) -> ClaimDetail:
    """
    Get detailed information for a specific claim.

    Args:
        claim_id: The claim ID or claim number
        db: Database session

    Returns:
        ClaimDetail: Detailed claim information
    """
    stmt = select(Claim).where(
        (Claim.id == claim_id) | (Claim.claim_number == claim_id)
    ).options(
        selectinload(Claim.policy),
        selectinload(Claim.status_history),
    )
    result = await db.execute(stmt)
    claim = result.scalar_one_or_none()

    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    customer_name = None
    if claim.policy and claim.policy.customer:
        customer = claim.policy.customer
        customer_name = f"{customer.first_name} {customer.last_name}"

    return ClaimDetail(
        id=claim.id,
        claim_number=claim.claim_number,
        policy_id=claim.policy_id,
        policy_number=claim.policy.policy_number if claim.policy else None,
        customer_name=customer_name,
        status=claim.status.value,
        claim_type=claim.claim_type,
        claim_amount=claim.claim_amount,
        approved_amount=claim.approved_amount,
        description=claim.description,
        incident_date=claim.incident_date,
        filed_date=claim.filed_date,
        resolved_date=claim.resolved_date,
        adjuster_notes=claim.adjuster_notes,
        metadata=claim.metadata_json or {},
        status_history=[],
        created_at=claim.created_at,
        updated_at=claim.updated_at,
    )


@router.post("/{claim_id}/refresh", response_model=ClaimRefreshResponse)
async def refresh_claim(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    orchestrator: ClaimsOrchestrator = Depends(get_orchestrator),
) -> ClaimRefreshResponse:
    """
    Trigger re-index and re-dedupe for a claim.

    This will:
    - Re-fetch data from all sources
    - Re-run OCR on documents if needed
    - Re-compute deduplication
    - Update the canonical bundle

    Args:
        claim_id: The claim ID or claim number
        db: Database session
        orchestrator: Claims orchestrator instance

    Returns:
        ClaimRefreshResponse: Refresh operation status
    """
    logger.info("Triggering claim refresh", claim_id=claim_id)

    # Verify claim exists
    stmt = select(Claim).where(
        (Claim.id == claim_id) | (Claim.claim_number == claim_id)
    )
    result = await db.execute(stmt)
    claim = result.scalar_one_or_none()

    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    # Mark existing bundle as stale
    bundle_stmt = select(CanonicalClaimBundleModel).where(
        CanonicalClaimBundleModel.claim_id == claim.id
    )
    bundle_result = await db.execute(bundle_stmt)
    cached_bundle = bundle_result.scalar_one_or_none()

    if cached_bundle:
        cached_bundle.is_stale = True
        await db.commit()

    # Queue refresh job (in production, this would go to Kafka)
    job_id = await orchestrator.queue_refresh_job(claim.id)

    return ClaimRefreshResponse(
        claim_id=claim.id,
        message="Refresh job queued successfully",
        refresh_started=True,
        job_id=job_id,
        estimated_completion=datetime.utcnow(),
    )


@router.get("/", response_model=list[ClaimSummary])
async def list_claims(
    status: str | None = Query(default=None, description="Filter by status"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
) -> list[ClaimSummary]:
    """
    List claims with optional filtering.

    Args:
        status: Optional status filter
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session

    Returns:
        list[ClaimSummary]: List of claim summaries
    """
    stmt = select(Claim).options(selectinload(Claim.policy))

    if status:
        stmt = stmt.where(Claim.status == status)

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.order_by(Claim.filed_date.desc())

    result = await db.execute(stmt)
    claims = result.scalars().all()

    return [
        ClaimSummary(
            id=claim.id,
            claim_number=claim.claim_number,
            status=claim.status.value,
            claim_type=claim.claim_type,
            claim_amount=claim.claim_amount,
            filed_date=claim.filed_date,
            policy_number=claim.policy.policy_number if claim.policy else None,
        )
        for claim in claims
    ]


def _convert_db_bundle_to_response(
    bundle: CanonicalClaimBundleModel,
    claim: Claim,
    include_llm_summary: bool,
) -> CanonicalClaimBundle:
    """Convert database bundle model to response schema."""
    document_list = []
    for doc_data in bundle.document_list or []:
        document_list.append(DocumentInfo(**doc_data))

    dedupe_info = DedupeInfo(**bundle.dedupe_info) if bundle.dedupe_info else DedupeInfo()

    llm_context = None
    if bundle.llm_context:
        llm_context = LLMContextBundle(
            structured_facts=bundle.structured_facts,
            document_summaries=[],
            ocr_snippets=[],
            relevant_chunks=[bundle.llm_context] if bundle.llm_context else [],
        )

    llm_summary = None
    if include_llm_summary and bundle.llm_summary:
        llm_summary = LLMSummary(
            summary=bundle.llm_summary,
            generated_at=bundle.computed_at,
        )

    source_provenance = []
    for prov_data in bundle.source_provenance or []:
        source_provenance.append(SourceProvenance(**prov_data))

    return CanonicalClaimBundle(
        claim_id=claim.id,
        claim_number=claim.claim_number,
        structured_facts=bundle.structured_facts,
        document_list=document_list,
        dedupe_info=dedupe_info,
        llm_context=llm_context,
        llm_summary=llm_summary,
        source_provenance=source_provenance,
        confidence_score=bundle.confidence_score,
        computed_at=bundle.computed_at,
        is_stale=bundle.is_stale,
    )
