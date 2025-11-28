"""
Base interface for vector stores.

Provides an abstract interface that can be implemented by
different vector databases (Chroma, FAISS, Pinecone, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class VectorDocument:
    """Represents a document in the vector store."""

    id: str
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class SearchResult:
    """Represents a search result from the vector store."""

    document: VectorDocument
    score: float
    distance: float | None = None


class VectorStore(ABC):
    """
    Abstract base class for vector stores.

    Provides a clean interface for:
    - Adding documents with embeddings
    - Semantic search
    - Filtering by metadata
    - Managing collections
    """

    @abstractmethod
    async def add_documents(
        self,
        documents: list[VectorDocument],
    ) -> list[str]:
        """
        Add documents to the vector store.

        Args:
            documents: List of documents to add

        Returns:
            list: IDs of added documents
        """
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Search for similar documents.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filters: Metadata filters

        Returns:
            list: Search results with scores
        """
        pass

    @abstractmethod
    async def search_by_text(
        self,
        query_text: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Search for similar documents using text query.

        The implementation should handle embedding generation.

        Args:
            query_text: Text query
            top_k: Number of results to return
            filters: Metadata filters

        Returns:
            list: Search results with scores
        """
        pass

    @abstractmethod
    async def get_document(self, document_id: str) -> VectorDocument | None:
        """
        Get a document by ID.

        Args:
            document_id: Document ID

        Returns:
            VectorDocument or None
        """
        pass

    @abstractmethod
    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document by ID.

        Args:
            document_id: Document ID

        Returns:
            bool: True if deleted
        """
        pass

    @abstractmethod
    async def delete_by_metadata(self, filters: dict[str, Any]) -> int:
        """
        Delete documents matching metadata filters.

        Args:
            filters: Metadata filters

        Returns:
            int: Number of deleted documents
        """
        pass

    @abstractmethod
    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """
        Count documents in the store.

        Args:
            filters: Optional metadata filters

        Returns:
            int: Document count
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all documents from the store."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connections and cleanup resources."""
        pass
