"""
Tests for deduplication service.
"""

from datetime import datetime

import pytest

from app.services.deduper import DeduplicationService, DocumentCandidate


@pytest.fixture
def deduper():
    """Create deduplication service instance."""
    return DeduplicationService()


@pytest.fixture
def sample_candidates():
    """Create sample document candidates for testing."""
    return [
        DocumentCandidate(
            id="doc1",
            claim_id="CLM001",
            policy_id="POL001",
            filename="accident_report.pdf",
            source_type="sharepoint",
            checksum="abc123",
            content_hash=None,
            created_at=datetime(2024, 1, 15, 10, 30),
            metadata={"type": "accident_report"},
        ),
        DocumentCandidate(
            id="doc2",
            claim_id="CLM001",
            policy_id="POL001",
            filename="accident_report_copy.pdf",
            source_type="blob",
            checksum="abc123",  # Same checksum - duplicate
            content_hash=None,
            created_at=datetime(2024, 1, 15, 10, 35),
            metadata={"type": "accident_report"},
        ),
        DocumentCandidate(
            id="doc3",
            claim_id="CLM001",
            policy_id="POL001",
            filename="medical_bill.pdf",
            source_type="sharepoint",
            checksum="def456",
            content_hash=None,
            created_at=datetime(2024, 1, 16, 14, 0),
            metadata={"type": "medical"},
        ),
        DocumentCandidate(
            id="doc4",
            claim_id="CLM002",
            policy_id="POL002",
            filename="claim_form.pdf",
            source_type="sql",
            checksum="ghi789",
            content_hash=None,
            created_at=datetime(2024, 1, 17, 9, 0),
            metadata={"type": "claim_form"},
        ),
    ]


@pytest.mark.asyncio
async def test_find_duplicates_by_checksum(deduper, sample_candidates):
    """Test finding duplicates by checksum match."""
    duplicates = await deduper.find_duplicates(sample_candidates)

    # Should find at least the checksum duplicate
    assert len(duplicates) > 0

    # Find the checksum duplicate
    checksum_dup = next(
        (d for d in duplicates if "checksum" in d.matching_fields),
        None
    )
    assert checksum_dup is not None
    assert checksum_dup.similarity_score >= 0.9


@pytest.mark.asyncio
async def test_find_duplicates_by_claim_id(deduper, sample_candidates):
    """Test finding candidates with same claim ID."""
    duplicates = await deduper.find_duplicates(sample_candidates)

    # Documents with same claim_id should be grouped
    claim_matches = [
        d for d in duplicates
        if d.claim_id_1 == d.claim_id_2 and d.claim_id_1 == "CLM001"
    ]
    assert len(claim_matches) > 0


@pytest.mark.asyncio
async def test_get_recommendation_merge(deduper, sample_candidates):
    """Test merge recommendation for high-similarity pairs."""
    duplicates = await deduper.find_duplicates(sample_candidates)

    # Checksum match should get merge recommendation
    checksum_dup = next(
        (d for d in duplicates if d.matching_fields.get("checksum")),
        None
    )
    if checksum_dup:
        assert checksum_dup.recommendation == "merge"


@pytest.mark.asyncio
async def test_empty_candidates(deduper):
    """Test with empty candidates list."""
    duplicates = await deduper.find_duplicates([])
    assert duplicates == []


@pytest.mark.asyncio
async def test_single_candidate(deduper, sample_candidates):
    """Test with single candidate."""
    duplicates = await deduper.find_duplicates([sample_candidates[0]])
    assert duplicates == []


@pytest.mark.asyncio
async def test_resolve_entity(deduper):
    """Test entity resolution."""
    candidates = [
        {"id": "ent1", "name": "John Smith", "email": "john@example.com"},
        {"id": "ent2", "name": "John Smith", "email": "jsmith@example.com"},
    ]

    result = await deduper.resolve_entity(
        source_id="source1",
        entity_type="customer",
        candidates=candidates,
    )

    assert result.source_id == "source1"
    assert result.entity_type == "customer"


@pytest.mark.asyncio
async def test_merge_documents(deduper):
    """Test document merging."""
    result = await deduper.merge_documents(
        primary_id="doc1",
        secondary_ids=["doc2", "doc3"],
        merge_strategy="latest",
    )

    assert result["canonical_id"] == "doc1"
    assert "doc2" in result["merged_ids"]
    assert "doc3" in result["merged_ids"]
    assert result["strategy"] == "latest"


@pytest.mark.asyncio
async def test_flag_for_review(deduper):
    """Test flagging for human review."""
    review_id = await deduper.flag_for_review(
        document_id_1="doc1",
        document_id_2="doc2",
        similarity_score=0.75,
        matching_fields={"filename_similarity": 0.8},
    )

    assert review_id is not None
    assert len(review_id) > 0
