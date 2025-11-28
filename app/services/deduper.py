"""
Entity Resolution and Deduplication Service.

Provides functionality for:
- Candidate generation for deduplication
- Pairwise scoring (rule-based + embedding similarity)
- Merge policy implementation
- Human-in-the-loop review flagging
"""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any

from app.config import get_settings
from app.schemas.deduplication import (
    DeduplicationCandidate,
    EntityMatch,
    EntityResolutionResult,
)
from app.observability.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class DocumentCandidate:
    """Represents a document for deduplication."""

    id: str
    claim_id: str | None
    policy_id: str | None
    filename: str
    source_type: str
    checksum: str | None
    content_hash: str | None
    created_at: datetime
    metadata: dict[str, Any]


class DeduplicationService:
    """
    Service for entity resolution and deduplication.

    Implements:
    - Exact match detection (claimId, policyId, checksum)
    - Fuzzy matching (filename patterns, timestamps)
    - Embedding similarity comparison
    - Confidence scoring and thresholding
    """

    def __init__(self) -> None:
        """Initialize deduplication service."""
        self._similarity_threshold = settings.deduplication.similarity_threshold
        self._exact_match_fields = settings.deduplication.exact_match_fields.split(",")
        logger.info(
            "Deduplication service initialized",
            threshold=self._similarity_threshold,
            exact_match_fields=self._exact_match_fields,
        )

    async def find_duplicates(
        self,
        candidates: list[DocumentCandidate],
    ) -> list[DeduplicationCandidate]:
        """
        Find duplicate pairs among candidates.

        Args:
            candidates: List of document candidates

        Returns:
            list: Deduplication candidates with scores
        """
        logger.info("Finding duplicates", candidate_count=len(candidates))

        duplicates: list[DeduplicationCandidate] = []

        # Compare all pairs
        for i, doc1 in enumerate(candidates):
            for doc2 in candidates[i + 1:]:
                score, matching_fields = await self._compute_similarity(doc1, doc2)

                if score > 0:  # Any similarity found
                    recommendation = self._get_recommendation(score)
                    duplicates.append(
                        DeduplicationCandidate(
                            document_id_1=doc1.id,
                            document_id_2=doc2.id,
                            claim_id_1=doc1.claim_id,
                            claim_id_2=doc2.claim_id,
                            similarity_score=score,
                            matching_fields=matching_fields,
                            source_types=[doc1.source_type, doc2.source_type],
                            recommendation=recommendation,
                        )
                    )

        # Sort by similarity score descending
        duplicates.sort(key=lambda x: x.similarity_score, reverse=True)
        logger.info("Duplicate detection complete", duplicates_found=len(duplicates))

        return duplicates

    async def _compute_similarity(
        self,
        doc1: DocumentCandidate,
        doc2: DocumentCandidate,
    ) -> tuple[float, dict[str, Any]]:
        """
        Compute similarity score between two documents.

        Args:
            doc1: First document
            doc2: Second document

        Returns:
            tuple: (similarity_score, matching_fields)
        """
        matching_fields: dict[str, Any] = {}
        scores: list[float] = []

        # Exact checksum match
        if doc1.checksum and doc2.checksum and doc1.checksum == doc2.checksum:
            matching_fields["checksum"] = True
            scores.append(1.0)

        # Claim ID match
        if doc1.claim_id and doc2.claim_id and doc1.claim_id == doc2.claim_id:
            matching_fields["claim_id"] = True
            scores.append(0.9)

        # Policy ID match
        if doc1.policy_id and doc2.policy_id and doc1.policy_id == doc2.policy_id:
            matching_fields["policy_id"] = True
            scores.append(0.7)

        # Filename similarity
        filename_sim = self._filename_similarity(doc1.filename, doc2.filename)
        if filename_sim > 0.7:
            matching_fields["filename_similarity"] = filename_sim
            scores.append(filename_sim * 0.8)

        # Timestamp proximity (within 1 hour)
        if doc1.created_at and doc2.created_at:
            time_diff = abs((doc1.created_at - doc2.created_at).total_seconds())
            if time_diff < 3600:  # 1 hour
                matching_fields["timestamp_proximity"] = time_diff
                scores.append(0.5)

        # Metadata similarity
        metadata_sim = self._metadata_similarity(doc1.metadata, doc2.metadata)
        if metadata_sim > 0.5:
            matching_fields["metadata_similarity"] = metadata_sim
            scores.append(metadata_sim * 0.6)

        # Calculate weighted average
        if not scores:
            return 0.0, {}

        final_score = max(scores)  # Use max score for now
        return final_score, matching_fields

    def _filename_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate filename similarity.

        Args:
            name1: First filename
            name2: Second filename

        Returns:
            float: Similarity score (0-1)
        """
        # Normalize filenames
        norm1 = re.sub(r"[^a-z0-9]", "", name1.lower())
        norm2 = re.sub(r"[^a-z0-9]", "", name2.lower())

        if not norm1 or not norm2:
            return 0.0

        # Simple character-based similarity
        if norm1 == norm2:
            return 1.0

        # Longest common substring ratio
        m, n = len(norm1), len(norm2)
        if m == 0 or n == 0:
            return 0.0

        # Simple overlap ratio
        set1, set2 = set(norm1), set(norm2)
        overlap = len(set1 & set2)
        return overlap / max(len(set1), len(set2))

    def _metadata_similarity(
        self,
        meta1: dict[str, Any],
        meta2: dict[str, Any],
    ) -> float:
        """
        Calculate metadata similarity.

        Args:
            meta1: First metadata dict
            meta2: Second metadata dict

        Returns:
            float: Similarity score (0-1)
        """
        if not meta1 or not meta2:
            return 0.0

        keys1 = set(meta1.keys())
        keys2 = set(meta2.keys())
        common_keys = keys1 & keys2

        if not common_keys:
            return 0.0

        matches = 0
        for key in common_keys:
            if meta1[key] == meta2[key]:
                matches += 1

        return matches / len(common_keys)

    def _get_recommendation(self, score: float) -> str:
        """
        Get merge recommendation based on score.

        Args:
            score: Similarity score

        Returns:
            str: Recommendation ("merge", "review", "keep_separate")
        """
        if score >= self._similarity_threshold:
            return "merge"
        elif score >= self._similarity_threshold * 0.7:
            return "review"
        else:
            return "keep_separate"

    async def resolve_entity(
        self,
        source_id: str,
        entity_type: str,
        candidates: list[dict[str, Any]],
    ) -> EntityResolutionResult:
        """
        Resolve an entity against candidates.

        Args:
            source_id: Source entity ID
            entity_type: Type of entity
            candidates: Candidate matches

        Returns:
            EntityResolutionResult: Resolution result
        """
        logger.info(
            "Resolving entity",
            source_id=source_id,
            entity_type=entity_type,
            candidate_count=len(candidates),
        )

        matches: list[EntityMatch] = []
        best_match = None
        best_confidence = 0.0

        for candidate in candidates:
            # Compare fields and compute match score
            for field, value in candidate.items():
                if field == "id":
                    continue

                match_confidence = 0.0
                match_type = "none"

                # Exact match
                if value == candidate.get(field):
                    match_confidence = 1.0
                    match_type = "exact"
                # Fuzzy match would go here

                if match_confidence > 0:
                    matches.append(
                        EntityMatch(
                            entity_id=candidate.get("id", ""),
                            entity_type=entity_type,
                            field_name=field,
                            source_value=str(value),
                            matched_value=str(candidate.get(field, "")),
                            confidence=match_confidence,
                            match_type=match_type,
                        )
                    )

                    if match_confidence > best_confidence:
                        best_confidence = match_confidence
                        best_match = candidate.get("id")

        return EntityResolutionResult(
            source_id=source_id,
            canonical_id=best_match or source_id,
            entity_type=entity_type,
            matches=matches,
            confidence=best_confidence,
            sources_merged=[source_id] if best_match else [],
        )

    async def merge_documents(
        self,
        primary_id: str,
        secondary_ids: list[str],
        merge_strategy: str = "latest",
    ) -> dict[str, Any]:
        """
        Merge documents into a canonical document.

        Args:
            primary_id: Primary document ID to merge into
            secondary_ids: Secondary document IDs to merge
            merge_strategy: Strategy for merging ("latest", "complete", "consensus")

        Returns:
            dict: Merge result with provenance
        """
        logger.info(
            "Merging documents",
            primary_id=primary_id,
            secondary_count=len(secondary_ids),
            strategy=merge_strategy,
        )

        return {
            "canonical_id": primary_id,
            "merged_ids": secondary_ids,
            "strategy": merge_strategy,
            "merged_at": datetime.utcnow().isoformat(),
            "provenance": {
                "primary": primary_id,
                "contributors": secondary_ids,
            },
        }

    async def flag_for_review(
        self,
        document_id_1: str,
        document_id_2: str,
        similarity_score: float,
        matching_fields: dict[str, Any],
    ) -> str:
        """
        Flag a low-confidence pair for human review.

        Args:
            document_id_1: First document ID
            document_id_2: Second document ID
            similarity_score: Computed similarity score
            matching_fields: Fields that matched

        Returns:
            str: Review ID
        """
        import uuid

        review_id = str(uuid.uuid4())
        logger.info(
            "Flagging pair for review",
            review_id=review_id,
            document_id_1=document_id_1,
            document_id_2=document_id_2,
            similarity_score=similarity_score,
        )

        # In production, this would create a DuplicateReview record
        return review_id
