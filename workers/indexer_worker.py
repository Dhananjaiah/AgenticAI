"""
Indexer Worker for document processing and indexing.

This worker:
- Consumes messages from the indexing queue
- Processes new/updated documents
- Runs OCR on PDFs/images
- Generates embeddings
- Updates Vector DB and Metadata Store
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.observability.logging_config import configure_logging, get_logger
from app.queue.kafka_client import KafkaConsumer
from app.services.indexer import IndexerService
from app.services.ocr import OCRService
from app.services.rag import RAGService
from app.vectorstore.base import VectorDocument
from app.vectorstore.chroma_store import ChromaVectorStore

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


class IndexerWorker:
    """
    Worker for processing indexing jobs.

    Handles:
    - Document indexing events
    - OCR processing
    - Embedding generation
    - Vector store updates
    """

    def __init__(self) -> None:
        """Initialize the indexer worker."""
        self._running = False
        self._consumer = KafkaConsumer([settings.kafka.topic_indexing])
        self._indexer = IndexerService()
        self._ocr = OCRService()
        self._vector_store = ChromaVectorStore()

        # Register handlers
        self._consumer.register_handler("index", self._handle_index_event)
        self._consumer.register_handler("reindex", self._handle_reindex_event)
        self._consumer.register_handler("delete", self._handle_delete_event)
        self._consumer.register_handler("batch_index", self._handle_batch_index_event)

        logger.info("Indexer worker initialized")

    async def start(self) -> None:
        """Start the worker."""
        self._running = True
        logger.info("Indexer worker starting")

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown)

        try:
            while self._running:
                # Consume messages in batches
                messages = await self._consumer.consume_batch(
                    max_messages=10,
                    timeout_ms=1000,
                )

                if messages:
                    logger.info("Processed batch", count=len(messages))

                # Small delay if no messages
                if not messages:
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error("Worker error", error=str(e))
            raise
        finally:
            await self._cleanup()

    async def stop(self) -> None:
        """Stop the worker."""
        logger.info("Indexer worker stopping")
        self._running = False

    async def _handle_index_event(self, event: dict) -> None:
        """
        Handle a document index event.

        Args:
            event: Event data with document_id and source info
        """
        document_id = event.get("document_id")
        source_type = event.get("source_type")
        data = event.get("data", {})

        logger.info(
            "Processing index event",
            document_id=document_id,
            source_type=source_type,
        )

        try:
            # Get file path from event data
            file_path = data.get("file_path")
            if not file_path:
                logger.warning("No file path in index event", document_id=document_id)
                return

            # Run indexing
            result = await self._indexer.index_document(
                document_id=document_id,
                file_path=file_path,
                claim_id=data.get("claim_id"),
                policy_id=data.get("policy_id"),
                metadata=data.get("metadata"),
            )

            if result.get("success"):
                # Store in vector DB if OCR text available
                ocr_text = result.get("ocr_text")
                if ocr_text:
                    await self._store_in_vector_db(document_id, ocr_text, data)

                logger.info(
                    "Document indexed successfully",
                    document_id=document_id,
                )
            else:
                logger.error(
                    "Document indexing failed",
                    document_id=document_id,
                    error=result.get("error"),
                )
        except Exception as e:
            logger.error(
                "Index event processing failed",
                document_id=document_id,
                error=str(e),
            )

    async def _handle_reindex_event(self, event: dict) -> None:
        """
        Handle a document reindex event.

        Args:
            event: Event data
        """
        document_id = event.get("document_id")
        logger.info("Processing reindex event", document_id=document_id)

        # Delete existing vector entries
        await self._vector_store.delete_by_metadata({"document_id": document_id})

        # Re-run indexing
        await self._handle_index_event(event)

    async def _handle_delete_event(self, event: dict) -> None:
        """
        Handle a document delete event.

        Args:
            event: Event data
        """
        document_id = event.get("document_id")
        logger.info("Processing delete event", document_id=document_id)

        # Delete from vector store
        deleted = await self._vector_store.delete_by_metadata(
            {"document_id": document_id}
        )
        logger.info("Deleted from vector store", document_id=document_id, count=deleted)

    async def _handle_batch_index_event(self, event: dict) -> None:
        """
        Handle a batch index event.

        Args:
            event: Event data with list of documents
        """
        documents = event.get("data", {}).get("documents", [])
        logger.info("Processing batch index event", count=len(documents))

        for doc_data in documents:
            doc_event = {
                "document_id": doc_data.get("id"),
                "source_type": doc_data.get("source_type"),
                "data": doc_data,
            }
            await self._handle_index_event(doc_event)

    async def _store_in_vector_db(
        self,
        document_id: str,
        text: str,
        metadata: dict,
    ) -> None:
        """
        Store document text in vector database.

        Args:
            document_id: Document ID
            text: Document text
            metadata: Document metadata
        """
        rag = RAGService()

        # Chunk the text
        chunks = await rag.chunk_text(text)

        documents = []
        for i, chunk in enumerate(chunks):
            doc = VectorDocument(
                id=f"{document_id}_chunk_{i}",
                content=chunk,
                metadata={
                    "document_id": document_id,
                    "chunk_index": i,
                    "claim_id": metadata.get("claim_id"),
                    "policy_id": metadata.get("policy_id"),
                    "source_type": metadata.get("source_type"),
                },
            )
            documents.append(doc)

        if documents:
            await self._vector_store.add_documents(documents)
            logger.info(
                "Stored document chunks in vector DB",
                document_id=document_id,
                chunks=len(documents),
            )

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info("Shutdown signal received")
        self._running = False

    async def _cleanup(self) -> None:
        """Cleanup resources."""
        await self._consumer.close()
        await self._vector_store.close()
        logger.info("Indexer worker cleaned up")


async def run_worker() -> None:
    """Run the indexer worker."""
    worker = IndexerWorker()
    await worker.start()


def main() -> None:
    """Entry point for the indexer worker."""
    logger.info("Starting indexer worker")
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Indexer worker interrupted")
    except Exception as e:
        logger.error("Indexer worker failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
