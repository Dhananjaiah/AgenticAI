"""
OCR service abstraction.

Provides a unified interface for OCR processing with implementations for:
- Tesseract (default, local)
- Azure Form Recognizer (production)
"""

import io
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any
import time

from PIL import Image

from app.config import get_settings
from app.schemas.documents import OCRResult
from app.observability.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class OCREngine(ABC):
    """Abstract base class for OCR engines."""

    @abstractmethod
    async def process_image(self, image_data: bytes) -> OCRResult:
        """
        Process an image and extract text.

        Args:
            image_data: Raw image bytes

        Returns:
            OCRResult: Extracted text and metadata
        """
        pass

    @abstractmethod
    async def process_pdf(self, pdf_data: bytes) -> OCRResult:
        """
        Process a PDF document and extract text.

        Args:
            pdf_data: Raw PDF bytes

        Returns:
            OCRResult: Extracted text and metadata
        """
        pass


class TesseractEngine(OCREngine):
    """Tesseract-based OCR engine for local development."""

    def __init__(self) -> None:
        """Initialize Tesseract engine."""
        self._tesseract_available = False
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = settings.ocr.tesseract_cmd
            self._tesseract_available = True
        except Exception as e:
            logger.warning("Tesseract not available", error=str(e))

    async def process_image(self, image_data: bytes) -> OCRResult:
        """Process an image using Tesseract."""
        start_time = time.time()

        if not self._tesseract_available:
            return OCRResult(
                document_id="",
                text="",
                confidence=0.0,
                pages=1,
                extracted_entities={},
                processing_time_ms=0,
                engine_used="tesseract_stub",
            )

        try:
            import pytesseract

            image = Image.open(io.BytesIO(image_data))
            # Get detailed OCR data including confidence
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

            # Extract text
            text = pytesseract.image_to_string(image)

            # Calculate average confidence
            confidences = [
                conf for conf in data["conf"] if isinstance(conf, (int, float)) and conf > 0
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            processing_time = (time.time() - start_time) * 1000

            return OCRResult(
                document_id="",
                text=text.strip(),
                confidence=avg_confidence / 100.0,  # Normalize to 0-1
                pages=1,
                extracted_entities=self._extract_entities(text),
                processing_time_ms=processing_time,
                engine_used="tesseract",
            )
        except Exception as e:
            logger.error("Tesseract OCR failed", error=str(e))
            raise

    async def process_pdf(self, pdf_data: bytes) -> OCRResult:
        """Process a PDF using Tesseract (via pdf2image)."""
        start_time = time.time()

        if not self._tesseract_available:
            return OCRResult(
                document_id="",
                text="",
                confidence=0.0,
                pages=0,
                extracted_entities={},
                processing_time_ms=0,
                engine_used="tesseract_stub",
            )

        try:
            from pdf2image import convert_from_bytes
            import pytesseract

            # Convert PDF to images
            images = convert_from_bytes(pdf_data)

            all_text = []
            all_confidences = []

            for image in images:
                text = pytesseract.image_to_string(image)
                all_text.append(text)

                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                confidences = [
                    conf for conf in data["conf"]
                    if isinstance(conf, (int, float)) and conf > 0
                ]
                all_confidences.extend(confidences)

            combined_text = "\n\n--- Page Break ---\n\n".join(all_text)
            avg_confidence = (
                sum(all_confidences) / len(all_confidences)
                if all_confidences else 0.0
            )

            processing_time = (time.time() - start_time) * 1000

            return OCRResult(
                document_id="",
                text=combined_text.strip(),
                confidence=avg_confidence / 100.0,
                pages=len(images),
                extracted_entities=self._extract_entities(combined_text),
                processing_time_ms=processing_time,
                engine_used="tesseract",
            )
        except Exception as e:
            logger.error("Tesseract PDF OCR failed", error=str(e))
            raise

    def _extract_entities(self, text: str) -> dict[str, Any]:
        """
        Extract basic entities from text using simple patterns.

        Args:
            text: OCR text

        Returns:
            dict: Extracted entities
        """
        import re

        entities: dict[str, Any] = {}

        # Extract dates
        date_pattern = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        dates = re.findall(date_pattern, text)
        if dates:
            entities["dates"] = dates[:5]  # Limit to first 5

        # Extract amounts (currency patterns)
        amount_pattern = r"\$[\d,]+\.?\d*"
        amounts = re.findall(amount_pattern, text)
        if amounts:
            entities["amounts"] = amounts[:5]

        # Extract claim/policy numbers (alphanumeric patterns)
        id_pattern = r"(?:CLM|POL|REF)[#-]?\d{6,}"
        ids = re.findall(id_pattern, text, re.IGNORECASE)
        if ids:
            entities["reference_ids"] = ids

        return entities


class AzureFormRecognizerEngine(OCREngine):
    """Azure Form Recognizer OCR engine for production use."""

    def __init__(self) -> None:
        """Initialize Azure Form Recognizer client."""
        self._client = None
        if (
            settings.ocr.azure_form_recognizer_endpoint
            and settings.ocr.azure_form_recognizer_key
        ):
            try:
                from azure.ai.formrecognizer import DocumentAnalysisClient
                from azure.core.credentials import AzureKeyCredential

                self._client = DocumentAnalysisClient(
                    endpoint=settings.ocr.azure_form_recognizer_endpoint,
                    credential=AzureKeyCredential(settings.ocr.azure_form_recognizer_key),
                )
            except Exception as e:
                logger.warning("Azure Form Recognizer not available", error=str(e))

    async def process_image(self, image_data: bytes) -> OCRResult:
        """Process an image using Azure Form Recognizer."""
        if not self._client:
            raise RuntimeError("Azure Form Recognizer not configured")

        start_time = time.time()

        try:
            poller = self._client.begin_analyze_document(
                "prebuilt-read", document=io.BytesIO(image_data)
            )
            result = poller.result()

            text_parts = []
            confidences = []

            for page in result.pages:
                for line in page.lines:
                    text_parts.append(line.content)
                    if hasattr(line, "confidence"):
                        confidences.append(line.confidence)

            combined_text = "\n".join(text_parts)
            avg_confidence = (
                sum(confidences) / len(confidences) if confidences else 0.9
            )

            processing_time = (time.time() - start_time) * 1000

            return OCRResult(
                document_id="",
                text=combined_text,
                confidence=avg_confidence,
                pages=len(result.pages),
                extracted_entities=self._extract_azure_entities(result),
                processing_time_ms=processing_time,
                engine_used="azure_form_recognizer",
            )
        except Exception as e:
            logger.error("Azure Form Recognizer failed", error=str(e))
            raise

    async def process_pdf(self, pdf_data: bytes) -> OCRResult:
        """Process a PDF using Azure Form Recognizer."""
        # Same implementation as process_image - Azure handles both
        return await self.process_image(pdf_data)

    def _extract_azure_entities(self, result: Any) -> dict[str, Any]:
        """Extract entities from Azure Form Recognizer result."""
        entities: dict[str, Any] = {}

        if hasattr(result, "key_value_pairs"):
            entities["key_value_pairs"] = [
                {
                    "key": kvp.key.content if kvp.key else None,
                    "value": kvp.value.content if kvp.value else None,
                }
                for kvp in result.key_value_pairs[:10]
            ]

        if hasattr(result, "tables"):
            entities["tables_count"] = len(result.tables)

        return entities


class OCRService:
    """
    Main OCR service that abstracts over different OCR engines.

    Automatically selects the appropriate engine based on configuration.
    """

    def __init__(self) -> None:
        """Initialize OCR service with configured engine."""
        if settings.ocr.engine == "azure_form_recognizer":
            self._engine: OCREngine = AzureFormRecognizerEngine()
        else:
            self._engine = TesseractEngine()

        logger.info("OCR service initialized", engine=settings.ocr.engine)

    async def process_document(
        self,
        file_path: str | Path | None = None,
        file_data: bytes | None = None,
        file_type: str = "image",
    ) -> OCRResult:
        """
        Process a document for OCR.

        Args:
            file_path: Path to the file (if not providing data directly)
            file_data: Raw file bytes
            file_type: Type of file ("image", "pdf")

        Returns:
            OCRResult: Extracted text and metadata
        """
        if file_data is None and file_path:
            with open(file_path, "rb") as f:
                file_data = f.read()

        if file_data is None:
            raise ValueError("Either file_path or file_data must be provided")

        logger.info("Processing document for OCR", file_type=file_type)

        if file_type.lower() == "pdf":
            return await self._engine.process_pdf(file_data)
        else:
            return await self._engine.process_image(file_data)

    async def process_file(self, file_path: str | Path) -> OCRResult:
        """
        Process a file for OCR, auto-detecting file type.

        Args:
            file_path: Path to the file

        Returns:
            OCRResult: Extracted text and metadata
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            file_type = "pdf"
        elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"):
            file_type = "image"
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

        return await self.process_document(file_path=path, file_type=file_type)
