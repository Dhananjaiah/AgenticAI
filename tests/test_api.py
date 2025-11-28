"""
Tests for API endpoints.
"""

import pytest
from httpx import AsyncClient

from app.db.models import Claim


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Test root endpoint returns API info."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "docs" in data


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    """Test health endpoint."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_ready_endpoint(async_client: AsyncClient):
    """Test readiness endpoint."""
    response = await async_client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert "ready" in data


@pytest.mark.asyncio
async def test_live_endpoint(async_client: AsyncClient):
    """Test liveness endpoint."""
    response = await async_client.get("/live")
    assert response.status_code == 200
    data = response.json()
    assert data["alive"] is True


@pytest.mark.asyncio
async def test_get_claim_not_found(async_client: AsyncClient):
    """Test getting a non-existent claim returns 404."""
    response = await async_client.get("/api/v1/claims/non-existent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_claim_by_id(async_client: AsyncClient, sample_claim: Claim):
    """Test getting a claim by ID."""
    response = await async_client.get(f"/api/v1/claims/{sample_claim.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == sample_claim.id
    assert data["claim_number"] == sample_claim.claim_number


@pytest.mark.asyncio
async def test_get_claim_by_number(async_client: AsyncClient, sample_claim: Claim):
    """Test getting a claim by claim number."""
    response = await async_client.get(f"/api/v1/claims/{sample_claim.claim_number}")
    assert response.status_code == 200
    data = response.json()
    assert data["claim_number"] == sample_claim.claim_number


@pytest.mark.asyncio
async def test_get_claim_detail(async_client: AsyncClient, sample_claim: Claim):
    """Test getting claim detail."""
    response = await async_client.get(f"/api/v1/claims/{sample_claim.id}/detail")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_claim.id
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_list_claims(async_client: AsyncClient, sample_claim: Claim):
    """Test listing claims."""
    response = await async_client.get("/api/v1/claims/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_policy_not_found(async_client: AsyncClient):
    """Test getting a non-existent policy returns 404."""
    response = await async_client.get("/api/v1/policies/non-existent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_policy_claims(async_client: AsyncClient, sample_claim: Claim):
    """Test getting claims for a policy."""
    response = await async_client.get(
        f"/api/v1/policies/{sample_claim.policy_id}/claims"
    )
    assert response.status_code == 200
    data = response.json()
    assert "claims" in data
    assert len(data["claims"]) >= 1


@pytest.mark.asyncio
async def test_refresh_claim(async_client: AsyncClient, sample_claim: Claim):
    """Test triggering claim refresh."""
    response = await async_client.post(f"/api/v1/claims/{sample_claim.id}/refresh")
    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == sample_claim.id
    assert data["refresh_started"] is True


@pytest.mark.asyncio
async def test_index_status(async_client: AsyncClient):
    """Test getting index status."""
    response = await async_client.get("/api/v1/admin/index/status")
    assert response.status_code == 200
    data = response.json()
    assert "sources" in data
    assert "documents" in data


@pytest.mark.asyncio
async def test_list_duplicate_reviews(async_client: AsyncClient):
    """Test listing duplicate reviews."""
    response = await async_client.get("/api/v1/admin/review/duplicates")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
