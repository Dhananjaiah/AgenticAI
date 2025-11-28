"""
Admin API endpoints.

Provides endpoints for:
- POST /index/rebuild - Rebuild or backfill index
- GET /review/duplicates - List low-confidence duplicate pairs
- POST /review/duplicates/{id} - Submit review decision
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DuplicateReview, IndexingState, DocumentSourceType
from app.db.session import get_db
from app.schemas.common import MessageResponse
from app.schemas.deduplication import (
    DuplicateReviewItem,
    DuplicateReviewResponse,
    DuplicateReviewDecision,
)
from app.services.indexer import IndexerService
from app.observability.logging_config import get_logger

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger(__name__)


async def get_indexer() -> IndexerService:
    """Dependency to get the indexer service."""
    return IndexerService()


@router.post("/index/rebuild", response_model=MessageResponse)
async def rebuild_index(
    source_type: str | None = Query(
        default=None, description="Specific source to rebuild (sql, sharepoint, blob)"
    ),
    full_rebuild: bool = Query(default=False, description="Perform full rebuild vs incremental"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    indexer: IndexerService = Depends(get_indexer),
) -> MessageResponse:
    """
    Trigger index rebuild or backfill.

    This endpoint fires-and-forgets the index rebuild via the message queue.
    The actual work is done by background workers.

    Args:
        source_type: Optional specific source to rebuild
        full_rebuild: Whether to do full rebuild or incremental
        background_tasks: FastAPI background tasks
        db: Database session
        indexer: Indexer service instance

    Returns:
        MessageResponse: Operation status
    """
    logger.info(
        "Index rebuild requested",
        source_type=source_type,
        full_rebuild=full_rebuild,
    )

    # Queue the rebuild job
    job_id = await indexer.queue_rebuild_job(
        source_type=source_type,
        full_rebuild=full_rebuild,
    )

    return MessageResponse(
        message=f"Index rebuild job queued with ID: {job_id}",
        success=True,
        timestamp=datetime.utcnow(),
    )


@router.get("/index/status")
async def get_index_status(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get current indexing status for all sources.

    Args:
        db: Database session

    Returns:
        dict: Indexing status per source
    """
    stmt = select(IndexingState)
    result = await db.execute(stmt)
    states = result.scalars().all()

    status = {}
    for state in states:
        status[state.source_type.value] = {
            "last_indexed_at": state.last_indexed_at,
            "items_indexed": state.items_indexed,
            "status": state.status,
            "last_error": state.last_error,
        }

    # Count documents by index status
    indexed_count_stmt = select(func.count(Document.id)).where(Document.is_indexed == True)  # noqa: E712
    not_indexed_count_stmt = select(func.count(Document.id)).where(Document.is_indexed == False)  # noqa: E712

    indexed_result = await db.execute(indexed_count_stmt)
    not_indexed_result = await db.execute(not_indexed_count_stmt)

    return {
        "sources": status,
        "documents": {
            "indexed": indexed_result.scalar_one(),
            "pending": not_indexed_result.scalar_one(),
        },
    }


@router.get("/review/duplicates", response_model=DuplicateReviewResponse)
async def list_duplicate_reviews(
    pending_only: bool = Query(default=True, description="Show only pending reviews"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
) -> DuplicateReviewResponse:
    """
    List low-confidence duplicate pairs for human review.

    Args:
        pending_only: Whether to show only pending reviews
        page: Page number
        page_size: Items per page
        db: Database session

    Returns:
        DuplicateReviewResponse: List of duplicate review items
    """
    logger.info("Listing duplicate reviews", pending_only=pending_only)

    stmt = select(DuplicateReview)

    if pending_only:
        stmt = stmt.where(DuplicateReview.is_reviewed == False)  # noqa: E712

    # Get total counts
    total_stmt = select(func.count(DuplicateReview.id))
    pending_stmt = select(func.count(DuplicateReview.id)).where(
        DuplicateReview.is_reviewed == False  # noqa: E712
    )
    reviewed_stmt = select(func.count(DuplicateReview.id)).where(
        DuplicateReview.is_reviewed == True  # noqa: E712
    )

    total_result = await db.execute(total_stmt)
    pending_result = await db.execute(pending_stmt)
    reviewed_result = await db.execute(reviewed_stmt)

    # Get paginated results
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.order_by(DuplicateReview.similarity_score.desc())

    result = await db.execute(stmt)
    reviews = result.scalars().all()

    items = [
        DuplicateReviewItem(
            id=review.id,
            document_id_1=review.document_id_1,
            document_id_2=review.document_id_2,
            similarity_score=review.similarity_score,
            matching_fields=review.matching_fields or {},
            is_reviewed=review.is_reviewed,
            review_decision=review.review_decision,
            reviewed_by=review.reviewed_by,
            reviewed_at=review.reviewed_at,
            notes=review.notes,
            created_at=review.created_at,
        )
        for review in reviews
    ]

    return DuplicateReviewResponse(
        items=items,
        total=total_result.scalar_one(),
        pending_count=pending_result.scalar_one(),
        reviewed_count=reviewed_result.scalar_one(),
    )


@router.post("/review/duplicates/{review_id}", response_model=MessageResponse)
async def submit_duplicate_review(
    review_id: str,
    decision: DuplicateReviewDecision,
    reviewed_by: str = Query(description="User submitting the review"),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Submit a review decision for a duplicate pair.

    Args:
        review_id: The duplicate review ID
        decision: The review decision
        reviewed_by: User submitting the review
        db: Database session

    Returns:
        MessageResponse: Operation status
    """
    logger.info(
        "Submitting duplicate review decision",
        review_id=review_id,
        decision=decision.decision,
        reviewed_by=reviewed_by,
    )

    stmt = select(DuplicateReview).where(DuplicateReview.id == review_id)
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")

    if review.is_reviewed:
        raise HTTPException(
            status_code=400,
            detail="This review has already been processed",
        )

    # Update review
    review.is_reviewed = True
    review.review_decision = decision.decision
    review.reviewed_by = reviewed_by
    review.reviewed_at = datetime.utcnow()
    review.notes = decision.notes

    await db.commit()

    # Handle the decision (in production, this would trigger document merging etc.)
    if decision.decision == "merge":
        logger.info(
            "Documents marked for merge",
            doc_1=review.document_id_1,
            doc_2=review.document_id_2,
        )

    return MessageResponse(
        message=f"Review decision '{decision.decision}' recorded successfully",
        success=True,
        timestamp=datetime.utcnow(),
    )
