"""
OCR Worker for processing documents.

This worker focuses on OCR processing of documents
and can be scaled independently from the indexer worker.
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.observability.logging_config import configure_logging, get_logger
from app.services.ocr import OCRService

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


class OCRWorker:
    """
    Worker for processing OCR jobs.

    Handles:
    - PDF OCR processing
    - Image text extraction
    - Entity extraction from OCR text
    """

    def __init__(self) -> None:
        """Initialize the OCR worker."""
        self._running = False
        self._ocr = OCRService()
        logger.info("OCR worker initialized")

    async def start(self) -> None:
        """Start the worker."""
        self._running = True
        logger.info("OCR worker starting")

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown)

        try:
            while self._running:
                # In production, this would consume from a queue
                # For now, it just stays alive for demonstration
                await asyncio.sleep(5)
        except Exception as e:
            logger.error("Worker error", error=str(e))
            raise
        finally:
            await self._cleanup()

    async def stop(self) -> None:
        """Stop the worker."""
        logger.info("OCR worker stopping")
        self._running = False

    async def process_file(self, file_path: str | Path) -> dict:
        """
        Process a file for OCR.

        Args:
            file_path: Path to the file

        Returns:
            dict: OCR result
        """
        logger.info("Processing file for OCR", file_path=str(file_path))

        try:
            result = await self._ocr.process_file(file_path)
            return {
                "success": True,
                "text": result.text,
                "confidence": result.confidence,
                "pages": result.pages,
                "entities": result.extracted_entities,
                "engine": result.engine_used,
                "processing_time_ms": result.processing_time_ms,
            }
        except Exception as e:
            logger.error("OCR processing failed", file_path=str(file_path), error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    async def process_batch(self, file_paths: list[str | Path]) -> list[dict]:
        """
        Process a batch of files for OCR.

        Args:
            file_paths: List of file paths

        Returns:
            list: OCR results for each file
        """
        logger.info("Processing batch for OCR", count=len(file_paths))
        results = []
        for file_path in file_paths:
            result = await self.process_file(file_path)
            results.append(result)
        return results

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info("Shutdown signal received")
        self._running = False

    async def _cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("OCR worker cleaned up")


async def run_worker() -> None:
    """Run the OCR worker."""
    worker = OCRWorker()
    await worker.start()


def main() -> None:
    """Entry point for the OCR worker."""
    logger.info("Starting OCR worker")
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("OCR worker interrupted")
    except Exception as e:
        logger.error("OCR worker failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
