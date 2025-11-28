"""
Claims Orchestrator Service.

Central orchestration for claim data retrieval and processing.
Coordinates retriever agents, deduplication, and LLM integration.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.models import CanonicalClaimBundle as CanonicalClaimBundleModel
from app.db.models import Claim
from app.observability.logging_config import get_logger
from app.schemas.claims import (
    CanonicalClaimBundle,
    DedupeInfo,
    DocumentInfo,
    LLMContextBundle,
)
from app.schemas.common import SourceProvenance
from app.services.cache import CacheService
from app.services.deduper import DeduplicationService, DocumentCandidate
from app.services.rag import RAGService

settings = get_settings()
logger = get_logger(__name__)


class ClaimsOrchestrator:
    """
    Central orchestrator for claim data retrieval and processing.

    Coordinates:
    - Retriever agents (SQL, SharePoint, Blob)
    - Metadata-first retrieval
    - Deduplication and entity resolution
    - LLM summarization
    """

    def __init__(self) -> None:
        """Initialize the orchestrator."""
        self._cache = CacheService()
        self._deduper = DeduplicationService()
        self._rag = RAGService()

    async def build_claim_bundle(
        self,
        claim_id: str,
        include_llm_summary: bool = False,
        db: AsyncSession | None = None,
    ) -> CanonicalClaimBundle:
        """
        Build a complete canonical bundle for a claim.

        Args:
            claim_id: Claim ID
            include_llm_summary: Whether to include LLM summary
            db: Database session

        Returns:
            CanonicalClaimBundle: Complete claim bundle
        """
        logger.info(
            "Building claim bundle",
            claim_id=claim_id,
            include_llm_summary=include_llm_summary,
        )

        # Check cache first
        cached_bundle = await self._cache.get_claim_bundle(claim_id)
        if cached_bundle:
            logger.info("Returning cached bundle", claim_id=claim_id)
            return CanonicalClaimBundle(**cached_bundle)

        if db is None:
            from app.db.session import get_db_context
            async with get_db_context() as db:
                return await self._build_bundle_internal(claim_id, include_llm_summary, db)
        else:
            return await self._build_bundle_internal(claim_id, include_llm_summary, db)

    async def _build_bundle_internal(
        self,
        claim_id: str,
        include_llm_summary: bool,
        db: AsyncSession,
    ) -> CanonicalClaimBundle:
        """Internal implementation of bundle building."""
        # Fetch claim with related data
        stmt = select(Claim).where(Claim.id == claim_id).options(
            selectinload(Claim.policy),
            selectinload(Claim.documents),
            selectinload(Claim.payments),
            selectinload(Claim.status_history),
        )
        result = await db.execute(stmt)
        claim = result.scalar_one_or_none()

        if not claim:
            raise ValueError(f"Claim {claim_id} not found")

        # Build structured facts
        structured_facts = self._extract_structured_facts(claim)

        # Get documents from all sources
        documents = await self._retrieve_all_documents(claim, db)

        # Build document list
        document_list = [
            DocumentInfo(
                id=doc["id"],
                filename=doc["filename"],
                file_type=doc["file_type"],
                source_type=doc["source_type"],
                source_path=doc["source_path"],
                file_size=doc.get("file_size"),
                ocr_confidence=doc.get("ocr_confidence"),
                tags=doc.get("tags", []),
                extracted_entities=doc.get("extracted_entities", {}),
                created_at=doc["created_at"],
            )
            for doc in documents
        ]

        # Perform deduplication
        dedupe_info = await self._run_deduplication(documents)

        # Build source provenance
        source_provenance = [
            SourceProvenance(
                source_type="sql",
                source_path="claims_table",
                retrieved_at=datetime.utcnow(),
                confidence=1.0,
            )
        ]
        for doc in documents[:5]:  # Limit provenance entries
            source_provenance.append(
                SourceProvenance(
                    source_type=doc["source_type"],
                    source_path=doc["source_path"],
                    retrieved_at=datetime.utcnow(),
                    checksum=doc.get("checksum"),
                    confidence=1.0,
                )
            )

        # Build LLM context
        llm_context = None
        llm_summary = None
        if include_llm_summary:
            llm_context = await self._build_llm_context(structured_facts, documents)
            llm_summary = await self._rag.generate_summary(llm_context)

        bundle = CanonicalClaimBundle(
            claim_id=claim.id,
            claim_number=claim.claim_number,
            structured_facts=structured_facts,
            document_list=document_list,
            dedupe_info=dedupe_info,
            llm_context=llm_context,
            llm_summary=llm_summary,
            source_provenance=source_provenance,
            confidence_score=1.0 - (len(dedupe_info.low_confidence_pairs) * 0.05),
            computed_at=datetime.utcnow(),
            is_stale=False,
        )

        # Cache the bundle
        await self._cache.set_claim_bundle(
            claim_id,
            bundle.model_dump(mode="json"),
        )

        # Store in database
        await self._store_bundle(claim.id, bundle, db)

        return bundle

    def _extract_structured_facts(self, claim: Claim) -> dict[str, Any]:
        """Extract structured facts from claim."""
        facts = {
            "claim_id": claim.id,
            "claim_number": claim.claim_number,
            "status": claim.status.value,
            "claim_type": claim.claim_type,
            "claim_amount": claim.claim_amount,
            "approved_amount": claim.approved_amount,
            "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
            "filed_date": claim.filed_date.isoformat() if claim.filed_date else None,
            "resolved_date": claim.resolved_date.isoformat() if claim.resolved_date else None,
            "description": claim.description,
        }

        if claim.policy:
            facts["policy_number"] = claim.policy.policy_number
            facts["policy_type"] = claim.policy.policy_type
            facts["coverage_amount"] = claim.policy.coverage_amount

            if claim.policy.customer:
                facts["customer_name"] = (
                    f"{claim.policy.customer.first_name} {claim.policy.customer.last_name}"
                )

        if claim.payments:
            facts["total_payments"] = sum(p.amount for p in claim.payments)
            facts["payment_count"] = len(claim.payments)

        return facts

    async def _retrieve_all_documents(
        self,
        claim: Claim,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """Retrieve documents from all sources."""
        documents = []

        # Get documents from database
        for doc in claim.documents:
            documents.append({
                "id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "source_type": doc.source_type.value,
                "source_path": doc.source_path,
                "file_size": doc.file_size,
                "checksum": doc.checksum,
                "ocr_confidence": doc.ocr_confidence,
                "tags": doc.tags or [],
                "extracted_entities": doc.extracted_entities or {},
                "created_at": doc.created_at,
            })

        # In production, would also call retriever agents:
        # - SQL Retriever
        # - SharePoint Retriever
        # - Blob/S3 Retriever

        return documents

    async def _run_deduplication(
        self,
        documents: list[dict[str, Any]],
    ) -> DedupeInfo:
        """Run deduplication on documents."""
        if len(documents) < 2:
            return DedupeInfo()

        # Convert to candidates
        candidates = [
            DocumentCandidate(
                id=doc["id"],
                claim_id=doc.get("claim_id"),
                policy_id=doc.get("policy_id"),
                filename=doc["filename"],
                source_type=doc["source_type"],
                checksum=doc.get("checksum"),
                content_hash=None,
                created_at=doc["created_at"],
                metadata=doc.get("extracted_entities", {}),
            )
            for doc in documents
        ]

        # Find duplicates
        duplicates = await self._deduper.find_duplicates(candidates)

        # Separate by confidence
        merged_ids = []
        low_confidence_pairs = []

        for dup in duplicates:
            if dup.recommendation == "merge":
                merged_ids.append(dup.document_id_2)
            elif dup.recommendation == "review":
                low_confidence_pairs.append({
                    "doc_1": dup.document_id_1,
                    "doc_2": dup.document_id_2,
                    "score": dup.similarity_score,
                })

        return DedupeInfo(
            merged_document_ids=merged_ids,
            duplicate_candidates=[
                {
                    "doc_1": d.document_id_1,
                    "doc_2": d.document_id_2,
                    "score": d.similarity_score,
                    "fields": d.matching_fields,
                }
                for d in duplicates
            ],
            confidence_score=1.0 - (len(low_confidence_pairs) * 0.1),
            low_confidence_pairs=low_confidence_pairs,
        )

    async def _build_llm_context(
        self,
        structured_facts: dict[str, Any],
        documents: list[dict[str, Any]],
    ) -> LLMContextBundle:
        """Build LLM context from claim data."""
        # Extract OCR text snippets
        ocr_snippets = []
        for doc in documents:
            if doc.get("ocr_text"):
                ocr_snippets.append(doc["ocr_text"][:500])

        # In production, would retrieve from vector DB
        relevant_chunks: list[str] = []

        return await self._rag.build_context(
            structured_facts=structured_facts,
            document_texts=[],
            ocr_snippets=ocr_snippets,
            relevant_chunks=relevant_chunks,
        )

    async def _store_bundle(
        self,
        claim_id: str,
        bundle: CanonicalClaimBundle,
        db: AsyncSession,
    ) -> None:
        """Store bundle in database."""
        stmt = select(CanonicalClaimBundleModel).where(
            CanonicalClaimBundleModel.claim_id == claim_id
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.structured_facts = bundle.structured_facts
            existing.document_list = [d.model_dump(mode="json") for d in bundle.document_list]
            existing.dedupe_info = bundle.dedupe_info.model_dump(mode="json")
            existing.llm_context = (
                bundle.llm_context.structured_facts.get("description")
                if bundle.llm_context else None
            )
            existing.llm_summary = bundle.llm_summary.summary if bundle.llm_summary else None
            existing.confidence_score = bundle.confidence_score
            existing.source_provenance = [p.model_dump(mode="json") for p in bundle.source_provenance]
            existing.computed_at = bundle.computed_at
            existing.is_stale = False
        else:
            new_bundle = CanonicalClaimBundleModel(
                id=str(uuid.uuid4()),
                claim_id=claim_id,
                structured_facts=bundle.structured_facts,
                document_list=[d.model_dump(mode="json") for d in bundle.document_list],
                dedupe_info=bundle.dedupe_info.model_dump(mode="json"),
                llm_context=(
                    bundle.llm_context.structured_facts.get("description")
                    if bundle.llm_context else None
                ),
                llm_summary=bundle.llm_summary.summary if bundle.llm_summary else None,
                confidence_score=bundle.confidence_score,
                source_provenance=[p.model_dump(mode="json") for p in bundle.source_provenance],
                computed_at=bundle.computed_at,
                is_stale=False,
            )
            db.add(new_bundle)

        await db.commit()

    async def queue_refresh_job(self, claim_id: str) -> str:
        """
        Queue a refresh job for a claim.

        Args:
            claim_id: Claim ID

        Returns:
            str: Job ID
        """
        job_id = str(uuid.uuid4())
        logger.info("Refresh job queued", claim_id=claim_id, job_id=job_id)

        # In production, would publish to Kafka
        # await self._publish_refresh_event(claim_id, job_id)

        # Invalidate cache
        await self._cache.invalidate_claim(claim_id)

        return job_id
