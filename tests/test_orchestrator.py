"""
Tests for orchestrator service.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.orchestrator import ClaimsOrchestrator
from app.db.models import Claim, Policy, Customer, ClaimStatus


@pytest.fixture
def orchestrator():
    """Create orchestrator instance."""
    return ClaimsOrchestrator()


@pytest.fixture
def mock_claim():
    """Create a mock claim for testing."""
    customer = MagicMock(spec=Customer)
    customer.first_name = "John"
    customer.last_name = "Smith"
    
    policy = MagicMock(spec=Policy)
    policy.customer = customer
    policy.policy_number = "POL-001"
    policy.policy_type = "Auto"
    policy.coverage_amount = 100000
    
    claim = MagicMock(spec=Claim)
    claim.id = "claim-123"
    claim.claim_number = "CLM-001"
    claim.policy = policy
    claim.policy_id = "policy-123"
    claim.status = ClaimStatus.PENDING
    claim.claim_type = "Auto Accident"
    claim.claim_amount = 5000.0
    claim.approved_amount = None
    claim.incident_date = datetime(2024, 1, 15)
    claim.filed_date = datetime(2024, 1, 16)
    claim.resolved_date = None
    claim.description = "Minor accident"
    claim.documents = []
    claim.payments = []
    claim.status_history = []
    
    return claim


def test_orchestrator_initialization(orchestrator):
    """Test orchestrator initializes correctly."""
    assert orchestrator is not None
    assert orchestrator._cache is not None
    assert orchestrator._deduper is not None
    assert orchestrator._rag is not None


def test_extract_structured_facts(orchestrator, mock_claim):
    """Test extracting structured facts from claim."""
    facts = orchestrator._extract_structured_facts(mock_claim)
    
    assert facts["claim_id"] == "claim-123"
    assert facts["claim_number"] == "CLM-001"
    assert facts["status"] == "pending"
    assert facts["claim_type"] == "Auto Accident"
    assert facts["claim_amount"] == 5000.0


@pytest.mark.asyncio
async def test_queue_refresh_job(orchestrator):
    """Test queuing a refresh job."""
    with patch.object(orchestrator._cache, "invalidate_claim", new_callable=AsyncMock) as mock_invalidate:
        mock_invalidate.return_value = True
        
        job_id = await orchestrator.queue_refresh_job("claim-123")
        
        assert job_id is not None
        assert len(job_id) > 0
        mock_invalidate.assert_called_once_with("claim-123")


@pytest.mark.asyncio
async def test_run_deduplication_empty(orchestrator):
    """Test deduplication with no documents."""
    result = await orchestrator._run_deduplication([])
    
    assert result.merged_document_ids == []
    assert result.confidence_score == 1.0


@pytest.mark.asyncio
async def test_run_deduplication_single_doc(orchestrator):
    """Test deduplication with single document."""
    documents = [{
        "id": "doc1",
        "filename": "test.pdf",
        "source_type": "sharepoint",
        "created_at": datetime.utcnow(),
    }]
    
    result = await orchestrator._run_deduplication(documents)
    
    assert result.merged_document_ids == []


@pytest.mark.asyncio
async def test_build_llm_context(orchestrator):
    """Test building LLM context."""
    structured_facts = {
        "claim_id": "123",
        "claim_number": "CLM-001",
        "description": "Test claim",
    }
    
    documents = [
        {"id": "doc1", "ocr_text": "This is OCR text from document 1"},
        {"id": "doc2", "ocr_text": "This is OCR text from document 2"},
    ]
    
    context = await orchestrator._build_llm_context(structured_facts, documents)
    
    assert context is not None
    assert context.structured_facts == structured_facts
    assert len(context.ocr_snippets) == 2
