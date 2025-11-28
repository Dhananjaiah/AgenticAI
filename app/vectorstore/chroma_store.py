"""
Chroma vector store implementation.

Provides a concrete implementation of the VectorStore interface
using ChromaDB for local vector storage.
"""

from typing import Any

from app.config import get_settings
from app.observability.logging_config import get_logger
from app.vectorstore.base import SearchResult, VectorDocument, VectorStore

settings = get_settings()
logger = get_logger(__name__)


class ChromaVectorStore(VectorStore):
    """
    ChromaDB-based vector store implementation.

    Features:
    - Persistent local storage
    - Metadata filtering
    - Embedding storage and retrieval
    """

    def __init__(self) -> None:
        """Initialize Chroma vector store."""
        self._client = None
        self._collection = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure the store is initialized."""
        if self._initialized:
            return

        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self._client = chromadb.Client(
                ChromaSettings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=settings.vectordb.chroma_persist_directory,
                    anonymized_telemetry=False,
                )
            )

            self._collection = self._client.get_or_create_collection(
                name=settings.vectordb.chroma_collection_name,
                metadata={"hnsw:space": "cosine"},
            )

            self._initialized = True
            logger.info(
                "Chroma vector store initialized",
                collection=settings.vectordb.chroma_collection_name,
            )
        except Exception as e:
            logger.error("Failed to initialize Chroma", error=str(e))
            raise

    async def add_documents(
        self,
        documents: list[VectorDocument],
    ) -> list[str]:
        """Add documents to the vector store."""
        await self._ensure_initialized()

        ids = []
        documents_data = []
        embeddings_data = []
        metadatas = []

        for doc in documents:
            ids.append(doc.id)
            documents_data.append(doc.content)
            if doc.embedding:
                embeddings_data.append(doc.embedding)
            metadatas.append(doc.metadata or {})

        try:
            if embeddings_data and len(embeddings_data) == len(documents):
                self._collection.add(
                    ids=ids,
                    documents=documents_data,
                    embeddings=embeddings_data,
                    metadatas=metadatas,
                )
            else:
                # Let Chroma generate embeddings
                self._collection.add(
                    ids=ids,
                    documents=documents_data,
                    metadatas=metadatas,
                )

            logger.info("Added documents to vector store", count=len(documents))
            return ids
        except Exception as e:
            logger.error("Failed to add documents", error=str(e))
            raise

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents by embedding."""
        await self._ensure_initialized()

        try:
            where_filter = self._build_where_filter(filters) if filters else None

            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            return self._parse_results(results)
        except Exception as e:
            logger.error("Search failed", error=str(e))
            return []

    async def search_by_text(
        self,
        query_text: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents by text."""
        await self._ensure_initialized()

        try:
            where_filter = self._build_where_filter(filters) if filters else None

            results = self._collection.query(
                query_texts=[query_text],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            return self._parse_results(results)
        except Exception as e:
            logger.error("Text search failed", error=str(e))
            return []

    async def get_document(self, document_id: str) -> VectorDocument | None:
        """Get a document by ID."""
        await self._ensure_initialized()

        try:
            results = self._collection.get(
                ids=[document_id],
                include=["documents", "metadatas", "embeddings"],
            )

            if not results["ids"]:
                return None

            return VectorDocument(
                id=results["ids"][0],
                content=results["documents"][0] if results["documents"] else "",
                embedding=results["embeddings"][0] if results.get("embeddings") else None,
                metadata=results["metadatas"][0] if results["metadatas"] else None,
            )
        except Exception as e:
            logger.error("Get document failed", error=str(e))
            return None

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document by ID."""
        await self._ensure_initialized()

        try:
            self._collection.delete(ids=[document_id])
            logger.info("Deleted document", document_id=document_id)
            return True
        except Exception as e:
            logger.error("Delete document failed", error=str(e))
            return False

    async def delete_by_metadata(self, filters: dict[str, Any]) -> int:
        """Delete documents matching metadata filters."""
        await self._ensure_initialized()

        try:
            where_filter = self._build_where_filter(filters)

            # Get matching IDs first
            results = self._collection.get(
                where=where_filter,
                include=[],
            )

            if not results["ids"]:
                return 0

            self._collection.delete(ids=results["ids"])
            count = len(results["ids"])
            logger.info("Deleted documents by metadata", count=count)
            return count
        except Exception as e:
            logger.error("Delete by metadata failed", error=str(e))
            return 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count documents in the store."""
        await self._ensure_initialized()

        try:
            if filters:
                where_filter = self._build_where_filter(filters)
                results = self._collection.get(where=where_filter, include=[])
                return len(results["ids"])
            else:
                return self._collection.count()
        except Exception as e:
            logger.error("Count failed", error=str(e))
            return 0

    async def clear(self) -> None:
        """Clear all documents from the store."""
        await self._ensure_initialized()

        try:
            # Delete and recreate collection
            self._client.delete_collection(settings.vectordb.chroma_collection_name)
            self._collection = self._client.create_collection(
                name=settings.vectordb.chroma_collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("Cleared vector store")
        except Exception as e:
            logger.error("Clear failed", error=str(e))
            raise

    async def close(self) -> None:
        """Close connections and cleanup resources."""
        if self._client:
            # Chroma doesn't require explicit closing
            self._client = None
            self._collection = None
            self._initialized = False
            logger.info("Closed vector store connection")

    def _build_where_filter(self, filters: dict[str, Any]) -> dict[str, Any]:
        """Build Chroma where filter from dict."""
        if not filters:
            return {}

        if len(filters) == 1:
            key, value = next(iter(filters.items()))
            return {key: value}

        # Multiple filters require $and
        conditions = [{k: v} for k, v in filters.items()]
        return {"$and": conditions}

    def _parse_results(self, results: dict[str, Any]) -> list[SearchResult]:
        """Parse Chroma query results into SearchResult objects."""
        search_results = []

        if not results["ids"] or not results["ids"][0]:
            return search_results

        ids = results["ids"][0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, doc_id in enumerate(ids):
            doc = VectorDocument(
                id=doc_id,
                content=documents[i] if i < len(documents) else "",
                metadata=metadatas[i] if i < len(metadatas) else None,
            )

            distance = distances[i] if i < len(distances) else 0.0
            # Convert distance to similarity score (cosine distance)
            score = 1.0 - distance

            search_results.append(
                SearchResult(
                    document=doc,
                    score=score,
                    distance=distance,
                )
            )

        return search_results
