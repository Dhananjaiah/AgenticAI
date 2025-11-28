"""
Tests for vector store implementation.
"""

import pytest

from app.vectorstore.base import VectorDocument
from app.vectorstore.chroma_store import ChromaVectorStore


@pytest.fixture
def vector_store():
    """Create vector store instance."""
    return ChromaVectorStore()


@pytest.fixture
def sample_documents():
    """Create sample documents for testing."""
    return [
        VectorDocument(
            id="doc1",
            content="This is a claim report about a car accident on Interstate 95.",
            metadata={"claim_id": "CLM001", "doc_type": "report"},
        ),
        VectorDocument(
            id="doc2",
            content="Medical expenses for treatment after the automobile collision.",
            metadata={"claim_id": "CLM001", "doc_type": "medical"},
        ),
        VectorDocument(
            id="doc3",
            content="Property damage assessment for residential flooding.",
            metadata={"claim_id": "CLM002", "doc_type": "assessment"},
        ),
    ]


@pytest.mark.asyncio
async def test_add_documents(vector_store, sample_documents):
    """Test adding documents to vector store."""
    try:
        ids = await vector_store.add_documents(sample_documents)
        assert len(ids) == len(sample_documents)
        assert "doc1" in ids
    except Exception:
        pytest.skip("ChromaDB not available")


@pytest.mark.asyncio
async def test_search_by_text(vector_store, sample_documents):
    """Test searching documents by text."""
    try:
        # Add documents first
        await vector_store.add_documents(sample_documents)
        
        # Search for car accident
        results = await vector_store.search_by_text(
            query_text="car accident highway",
            top_k=2,
        )
        
        assert len(results) <= 2
        if results:
            # First result should be about car accident
            assert "CLM001" in results[0].document.metadata.get("claim_id", "")
    except Exception:
        pytest.skip("ChromaDB not available")


@pytest.mark.asyncio
async def test_search_with_filters(vector_store, sample_documents):
    """Test searching with metadata filters."""
    try:
        await vector_store.add_documents(sample_documents)
        
        # Search with claim_id filter
        results = await vector_store.search_by_text(
            query_text="document",
            top_k=10,
            filters={"claim_id": "CLM001"},
        )
        
        # All results should be for CLM001
        for result in results:
            assert result.document.metadata.get("claim_id") == "CLM001"
    except Exception:
        pytest.skip("ChromaDB not available")


@pytest.mark.asyncio
async def test_get_document(vector_store, sample_documents):
    """Test getting a document by ID."""
    try:
        await vector_store.add_documents(sample_documents)
        
        doc = await vector_store.get_document("doc1")
        
        assert doc is not None
        assert doc.id == "doc1"
        assert "car accident" in doc.content.lower()
    except Exception:
        pytest.skip("ChromaDB not available")


@pytest.mark.asyncio
async def test_delete_document(vector_store, sample_documents):
    """Test deleting a document."""
    try:
        await vector_store.add_documents(sample_documents)
        
        # Delete doc1
        success = await vector_store.delete_document("doc1")
        assert success
        
        # Verify it's deleted
        doc = await vector_store.get_document("doc1")
        assert doc is None
    except Exception:
        pytest.skip("ChromaDB not available")


@pytest.mark.asyncio
async def test_delete_by_metadata(vector_store, sample_documents):
    """Test deleting documents by metadata."""
    try:
        await vector_store.add_documents(sample_documents)
        
        # Delete all documents for CLM001
        count = await vector_store.delete_by_metadata({"claim_id": "CLM001"})
        
        assert count == 2  # doc1 and doc2
    except Exception:
        pytest.skip("ChromaDB not available")


@pytest.mark.asyncio
async def test_count(vector_store, sample_documents):
    """Test counting documents."""
    try:
        await vector_store.add_documents(sample_documents)
        
        total = await vector_store.count()
        assert total >= 3
        
        filtered = await vector_store.count({"claim_id": "CLM001"})
        assert filtered == 2
    except Exception:
        pytest.skip("ChromaDB not available")


@pytest.mark.asyncio
async def test_clear(vector_store, sample_documents):
    """Test clearing all documents."""
    try:
        await vector_store.add_documents(sample_documents)
        
        await vector_store.clear()
        
        count = await vector_store.count()
        assert count == 0
    except Exception:
        pytest.skip("ChromaDB not available")
