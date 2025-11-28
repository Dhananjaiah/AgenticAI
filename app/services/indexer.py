"""
Indexer service for document ingestion and vector indexing.

Handles:
- Ingesting new/updated documents
- Running OCR on PDFs/images
- Generating embeddings
- Updating Vector DB and Metadata Store
"""

import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.observability.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class IndexerService:
    """
    Service for document indexing and ingestion.

    Coordinates between:
    - OCR processing
    - Embedding generation
    - Vector DB storage
    - Metadata store updates
    """

    def __init__(self) -> None:
        """Initialize the indexer service."""
        self._pending_jobs: dict[str, dict[str, Any]] = {}

    async def queue_rebuild_job(
        self,
        source_type: str | None = None,
        full_rebuild: bool = False,
    ) -> str:
        """
        Queue an index rebuild job.

        Args:
            source_type: Optional source type to rebuild
            full_rebuild: Whether to do full rebuild

        Returns:
            str: Job ID
        """
        job_id = str(uuid.uuid4())

        self._pending_jobs[job_id] = {
            "id": job_id,
            "type": "rebuild",
            "source_type": source_type,
            "full_rebuild": full_rebuild,
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            "Index rebuild job queued",
            job_id=job_id,
            source_type=source_type,
            full_rebuild=full_rebuild,
        )

        # In production, this would publish to Kafka
        # await self._publish_to_queue(self._pending_jobs[job_id])

        return job_id

    async def index_document(
        self,
        document_id: str,
        file_path: str | Path,
        claim_id: str | None = None,
        policy_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Index a single document.

        Args:
            document_id: Document ID
            file_path: Path to the document file
            claim_id: Associated claim ID
            policy_id: Associated policy ID
            metadata: Additional metadata

        Returns:
            dict: Indexing result with status
        """
        logger.info("Indexing document", document_id=document_id, file_path=str(file_path))

        path = Path(file_path)
        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "document_id": document_id,
            }

        # Calculate checksum
        with open(path, "rb") as f:
            file_data = f.read()
        checksum = hashlib.sha256(file_data).hexdigest()

        # Determine file type
        suffix = path.suffix.lower()
        file_type = self._get_file_type(suffix)

        result = {
            "success": True,
            "document_id": document_id,
            "file_type": file_type,
            "file_size": len(file_data),
            "checksum": checksum,
            "indexed_at": datetime.utcnow().isoformat(),
        }

        # Process OCR for images and PDFs
        if file_type in ("pdf", "image"):
            try:
                from app.services.ocr import OCRService
                ocr_service = OCRService()
                ocr_result = await ocr_service.process_document(
                    file_data=file_data,
                    file_type=file_type,
                )
                result["ocr_text"] = ocr_result.text[:1000]  # Truncate for result
                result["ocr_confidence"] = ocr_result.confidence
                result["extracted_entities"] = ocr_result.extracted_entities
            except Exception as e:
                logger.warning("OCR processing failed", document_id=document_id, error=str(e))
                result["ocr_error"] = str(e)

        # Generate embeddings (placeholder - would use actual embedding service)
        # embeddings = await self._generate_embeddings(result.get("ocr_text", ""))

        # Store in vector DB (placeholder - would use actual vector store)
        # await self._store_in_vector_db(document_id, embeddings, metadata)

        return result

    async def index_batch(
        self,
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Index a batch of documents.

        Args:
            documents: List of document metadata dicts

        Returns:
            list: Results for each document
        """
        results = []
        for doc in documents:
            result = await self.index_document(
                document_id=doc.get("id", str(uuid.uuid4())),
                file_path=doc["file_path"],
                claim_id=doc.get("claim_id"),
                policy_id=doc.get("policy_id"),
                metadata=doc.get("metadata"),
            )
            results.append(result)
        return results

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """
        Get the status of an indexing job.

        Args:
            job_id: Job ID

        Returns:
            dict: Job status or None if not found
        """
        return self._pending_jobs.get(job_id)

    def _get_file_type(self, suffix: str) -> str:
        """Determine file type from suffix."""
        if suffix == ".pdf":
            return "pdf"
        elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"):
            return "image"
        elif suffix in (".csv", ".xlsx", ".xls"):
            return "spreadsheet"
        elif suffix in (".doc", ".docx"):
            return "document"
        elif suffix in (".txt", ".md"):
            return "text"
        else:
            return "unknown"

    async def _generate_embeddings(self, text: str) -> list[float]:
        """
        Generate embeddings for text.

        Args:
            text: Input text

        Returns:
            list: Embedding vector
        """
        # Placeholder - would use actual embedding model
        # In production, this would call Azure OpenAI embeddings
        return [0.0] * 1536  # Default embedding size for ada-002

    async def incremental_index(
        self,
        source_type: str,
        since: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Perform incremental indexing for a source.

        Args:
            source_type: Type of source to index
            since: Only index items updated since this time

        Returns:
            dict: Indexing summary
        """
        logger.info(
            "Starting incremental index",
            source_type=source_type,
            since=since.isoformat() if since else None,
        )

        # Placeholder - would query for new/updated items and index them
        return {
            "source_type": source_type,
            "items_processed": 0,
            "items_indexed": 0,
            "errors": 0,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }
