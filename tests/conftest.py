"""
Pytest configuration and fixtures.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Claim, ClaimStatus, Customer, Document, DocumentSourceType, Policy
from app.db.session import Base, get_db
from app.main import app

# Use SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_DATABASE_URL_SYNC = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_db_engine():
    """Create async database engine for testing."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def async_db_session(async_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for testing."""
    async_session_factory = async_sessionmaker(
        async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(async_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing."""
    async def override_get_db():
        yield async_db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sync_client() -> Generator[TestClient, None, None]:
    """Create sync HTTP client for basic testing."""
    with TestClient(app) as client:
        yield client


@pytest_asyncio.fixture
async def sample_customer(async_db_session: AsyncSession) -> Customer:
    """Create a sample customer for testing."""
    customer = Customer(
        id=str(uuid4()),
        external_id="CUST001",
        first_name="John",
        last_name="Smith",
        email="john.smith@example.com",
        phone="555-123-4567",
        address="123 Main Street, Anytown, USA",
    )
    async_db_session.add(customer)
    await async_db_session.commit()
    await async_db_session.refresh(customer)
    return customer


@pytest_asyncio.fixture
async def sample_policy(
    async_db_session: AsyncSession,
    sample_customer: Customer,
) -> Policy:
    """Create a sample policy for testing."""
    policy = Policy(
        id=str(uuid4()),
        policy_number="POL-2024-001",
        customer_id=sample_customer.id,
        policy_type="Auto Insurance",
        coverage_amount=100000.0,
        premium=1200.0,
        start_date=datetime.utcnow() - timedelta(days=180),
        end_date=datetime.utcnow() + timedelta(days=185),
        is_active=True,
    )
    async_db_session.add(policy)
    await async_db_session.commit()
    await async_db_session.refresh(policy)
    return policy


@pytest_asyncio.fixture
async def sample_claim(
    async_db_session: AsyncSession,
    sample_policy: Policy,
) -> Claim:
    """Create a sample claim for testing."""
    claim = Claim(
        id=str(uuid4()),
        claim_number="CLM-2024-001",
        policy_id=sample_policy.id,
        status=ClaimStatus.PENDING,
        claim_type="Auto Accident",
        claim_amount=5000.0,
        description="Minor fender bender in parking lot",
        incident_date=datetime.utcnow() - timedelta(days=7),
        filed_date=datetime.utcnow() - timedelta(days=5),
    )
    async_db_session.add(claim)
    await async_db_session.commit()
    await async_db_session.refresh(claim)
    return claim


@pytest_asyncio.fixture
async def sample_document(
    async_db_session: AsyncSession,
    sample_claim: Claim,
) -> Document:
    """Create a sample document for testing."""
    document = Document(
        id=str(uuid4()),
        claim_id=sample_claim.id,
        policy_id=sample_claim.policy_id,
        source_type=DocumentSourceType.SHAREPOINT,
        source_path="/claims/CLM-2024-001/accident_report.pdf",
        filename="accident_report.pdf",
        file_type="pdf",
        file_size=102400,
        checksum="abc123def456",
        is_indexed=False,
    )
    async_db_session.add(document)
    await async_db_session.commit()
    await async_db_session.refresh(document)
    return document
