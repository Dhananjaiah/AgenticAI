"""
Integration tests for the claims processing flow.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer, Policy, Claim, Document, ClaimStatus, DocumentSourceType


@pytest.mark.asyncio
async def test_full_claim_flow(async_db_session: AsyncSession, async_client):
    """
    Integration test for the full claim processing flow.
    
    This test:
    1. Creates sample data (customer, policy, claim, documents)
    2. Calls the /claims/{claim_id} endpoint
    3. Verifies a canonical bundle is produced
    """
    # Create customer
    customer = Customer(
        id=str(uuid4()),
        external_id="INT-CUST-001",
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
    )
    async_db_session.add(customer)
    
    # Create policy
    policy = Policy(
        id=str(uuid4()),
        policy_number="INT-POL-001",
        customer_id=customer.id,
        policy_type="Comprehensive Auto",
        coverage_amount=75000.0,
        premium=950.0,
        start_date=datetime.utcnow() - timedelta(days=365),
        end_date=datetime.utcnow() + timedelta(days=365),
        is_active=True,
    )
    async_db_session.add(policy)
    
    # Create claim
    claim = Claim(
        id=str(uuid4()),
        claim_number="INT-CLM-001",
        policy_id=policy.id,
        status=ClaimStatus.UNDER_REVIEW,
        claim_type="Collision",
        claim_amount=12500.0,
        description="Rear-end collision at intersection",
        incident_date=datetime.utcnow() - timedelta(days=14),
        filed_date=datetime.utcnow() - timedelta(days=10),
    )
    async_db_session.add(claim)
    
    # Create documents
    doc1 = Document(
        id=str(uuid4()),
        claim_id=claim.id,
        policy_id=policy.id,
        source_type=DocumentSourceType.SHAREPOINT,
        source_path="/claims/INT-CLM-001/police_report.pdf",
        filename="police_report.pdf",
        file_type="pdf",
        file_size=256000,
        is_indexed=True,
        indexed_at=datetime.utcnow(),
    )
    
    doc2 = Document(
        id=str(uuid4()),
        claim_id=claim.id,
        policy_id=policy.id,
        source_type=DocumentSourceType.BLOB,
        source_path="/claims/INT-CLM-001/damage_photo.jpg",
        filename="damage_photo.jpg",
        file_type="image",
        file_size=1024000,
        is_indexed=True,
        indexed_at=datetime.utcnow(),
    )
    
    async_db_session.add_all([doc1, doc2])
    await async_db_session.commit()
    
    # Call the API endpoint
    response = await async_client.get(f"/api/v1/claims/{claim.id}")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    
    # Verify claim info
    assert data["claim_id"] == claim.id
    assert data["claim_number"] == "INT-CLM-001"
    
    # Verify structured facts
    assert "structured_facts" in data
    assert data["structured_facts"]["claim_amount"] == 12500.0
    assert data["structured_facts"]["status"] == "under_review"
    
    # Verify document list
    assert "document_list" in data
    assert len(data["document_list"]) == 2
    
    # Verify dedupe info
    assert "dedupe_info" in data
    
    # Verify confidence score
    assert "confidence_score" in data
    assert data["confidence_score"] >= 0 and data["confidence_score"] <= 1


@pytest.mark.asyncio
async def test_policy_claims_retrieval(async_db_session: AsyncSession, async_client):
    """
    Integration test for retrieving claims by policy.
    """
    # Create customer and policy
    customer = Customer(
        id=str(uuid4()),
        first_name="Bob",
        last_name="Wilson",
        email="bob.wilson@example.com",
    )
    async_db_session.add(customer)
    
    policy = Policy(
        id=str(uuid4()),
        policy_number="INT-POL-002",
        customer_id=customer.id,
        policy_type="Home Insurance",
        coverage_amount=250000.0,
        premium=1800.0,
        start_date=datetime.utcnow() - timedelta(days=180),
        end_date=datetime.utcnow() + timedelta(days=185),
        is_active=True,
    )
    async_db_session.add(policy)
    
    # Create multiple claims for the policy
    for i in range(3):
        claim = Claim(
            id=str(uuid4()),
            claim_number=f"INT-CLM-10{i}",
            policy_id=policy.id,
            status=ClaimStatus.PENDING if i == 0 else ClaimStatus.CLOSED,
            claim_type="Water Damage",
            claim_amount=5000.0 * (i + 1),
            incident_date=datetime.utcnow() - timedelta(days=30 * (i + 1)),
            filed_date=datetime.utcnow() - timedelta(days=28 * (i + 1)),
        )
        async_db_session.add(claim)
    
    await async_db_session.commit()
    
    # Call the API endpoint
    response = await async_client.get(f"/api/v1/policies/{policy.id}/claims")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    
    # Verify policy info
    assert data["policy_number"] == "INT-POL-002"
    
    # Verify claims
    assert "claims" in data
    assert len(data["claims"]) == 3
    
    # Verify aggregates
    assert "total_claims_amount" in data
    assert data["total_claims_amount"] == 30000.0  # 5000 + 10000 + 15000
    
    assert "active_claims_count" in data
    assert data["active_claims_count"] == 1  # Only the pending one


@pytest.mark.asyncio
async def test_claim_refresh_flow(async_db_session: AsyncSession, async_client, sample_claim: Claim):
    """
    Integration test for claim refresh flow.
    """
    # Trigger refresh
    response = await async_client.post(f"/api/v1/claims/{sample_claim.id}/refresh")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["claim_id"] == sample_claim.id
    assert data["refresh_started"] is True
    assert data["job_id"] is not None
