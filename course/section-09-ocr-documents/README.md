# Section 09: OCR and Document Processing

## 🎯 Learning Goals
By the end of this section, you will understand:
- What OCR is and why we need it
- How Tesseract OCR works
- How Azure Form Recognizer works
- How we extract text from PDFs and images

---

## 📺 Video Transcript

### Welcome to the OCR Section!

Hello everyone! In this section, we'll learn about OCR - Optical Character Recognition. This is how we read text from images and scanned documents.

### What is OCR?

OCR stands for **Optical Character Recognition**. It's technology that:
- Looks at an image
- Finds letters and numbers
- Converts them to text you can search and edit

**Example:**

```
📷 Image of a document      →     "Patient Name: John Smith
[Photo of medical report]   OCR    Date: January 15, 2024
                            →      Diagnosis: Minor injury"
```

### Why Do We Need OCR?

Insurance claims often include:
- Scanned police reports
- Photos of damage
- Handwritten forms
- Medical records (often PDFs that are actually images)

Without OCR, we can't:
- Search through these documents
- Include them in AI summaries
- Find duplicates by content

### Our OCR Implementation

Open `app/services/ocr.py`. We have two OCR engines:

```python
# Two options for OCR

class TesseractEngine(OCREngine):
    """Free, local OCR using Tesseract."""
    pass

class AzureFormRecognizerEngine(OCREngine):
    """Paid, cloud OCR using Azure (more accurate)."""
    pass
```

### The OCRResult Class

All OCR results have the same format:

```python
@dataclass
class OCRResult:
    """Result from OCR processing."""
    
    document_id: str           # Which document was processed
    text: str                  # The extracted text
    confidence: float          # How sure we are (0.0 to 1.0)
    pages: int                 # Number of pages processed
    extracted_entities: dict   # Dates, amounts, IDs found
    processing_time_ms: float  # How long it took
    engine_used: str           # "tesseract" or "azure_form_recognizer"
```

### Tesseract Engine

Tesseract is free and runs locally:

```python
class TesseractEngine(OCREngine):
    """Tesseract-based OCR engine for local development."""
    
    def __init__(self):
        self._tesseract_available = False
        try:
            import pytesseract
            pytesseract.tesseract_cmd = "/usr/bin/tesseract"
            self._tesseract_available = True
        except Exception as e:
            logger.warning("Tesseract not available", error=str(e))
    
    async def process_image(self, image_data: bytes) -> OCRResult:
        """Process an image using Tesseract."""
        start_time = time.time()
        
        if not self._tesseract_available:
            # Return empty result if Tesseract not installed
            return OCRResult(
                document_id="",
                text="",
                confidence=0.0,
                pages=1,
                engine_used="tesseract_stub",
            )
        
        import pytesseract
        from PIL import Image
        import io
        
        # Load the image
        image = Image.open(io.BytesIO(image_data))
        
        # Get detailed OCR data
        data = pytesseract.image_to_data(
            image, 
            output_type=pytesseract.Output.DICT
        )
        
        # Extract the text
        text = pytesseract.image_to_string(image)
        
        # Calculate average confidence
        confidences = [
            conf for conf in data["conf"] 
            if isinstance(conf, (int, float)) and conf > 0
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
```

### Processing PDFs

PDFs need to be converted to images first:

```python
async def process_pdf(self, pdf_data: bytes) -> OCRResult:
    """Process a PDF using Tesseract (via pdf2image)."""
    start_time = time.time()
    
    import pytesseract
    from pdf2image import convert_from_bytes
    
    # Convert PDF pages to images
    images = convert_from_bytes(pdf_data)
    
    all_text = []
    all_confidences = []
    
    # Process each page
    for image in images:
        text = pytesseract.image_to_string(image)
        all_text.append(text)
        
        data = pytesseract.image_to_data(
            image, 
            output_type=pytesseract.Output.DICT
        )
        confidences = [
            conf for conf in data["conf"]
            if isinstance(conf, (int, float)) and conf > 0
        ]
        all_confidences.extend(confidences)
    
    # Combine pages with separator
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
```

### Extracting Entities

OCR can also find specific information:

```python
def _extract_entities(self, text: str) -> dict:
    """Extract basic entities from text using patterns."""
    import re
    
    entities = {}
    
    # Find dates (MM/DD/YYYY or MM-DD-YYYY)
    date_pattern = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    dates = re.findall(date_pattern, text)
    if dates:
        entities["dates"] = dates[:5]  # First 5 dates
    
    # Find money amounts ($1,234.56)
    amount_pattern = r"\$[\d,]+\.?\d*"
    amounts = re.findall(amount_pattern, text)
    if amounts:
        entities["amounts"] = amounts[:5]  # First 5 amounts
    
    # Find claim/policy numbers (CLM-123456, POL-789012)
    id_pattern = r"(?:CLM|POL|REF)[#-]?\d{6,}"
    ids = re.findall(id_pattern, text, re.IGNORECASE)
    if ids:
        entities["reference_ids"] = ids
    
    return entities
```

**Example output:**

```python
{
    "dates": ["01/15/2024", "01/20/2024"],
    "amounts": ["$5,000.00", "$750.00"],
    "reference_ids": ["CLM-2024-001234"]
}
```

This is useful for automatically linking documents to claims!

### Azure Form Recognizer

For production, we use Azure Form Recognizer (more accurate):

```python
class AzureFormRecognizerEngine(OCREngine):
    """Azure Form Recognizer OCR engine for production use."""
    
    def __init__(self):
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
                    credential=AzureKeyCredential(
                        settings.ocr.azure_form_recognizer_key
                    ),
                )
            except Exception as e:
                logger.warning("Azure Form Recognizer not available")
    
    async def process_image(self, image_data: bytes) -> OCRResult:
        """Process an image using Azure Form Recognizer."""
        if not self._client:
            raise RuntimeError("Azure Form Recognizer not configured")
        
        start_time = time.time()
        
        # Send to Azure
        poller = self._client.begin_analyze_document(
            "prebuilt-read",  # Use built-in reading model
            document=io.BytesIO(image_data)
        )
        result = poller.result()
        
        # Extract text from result
        text_parts = []
        confidences = []
        
        for page in result.pages:
            for line in page.lines:
                text_parts.append(line.content)
                if hasattr(line, "confidence"):
                    confidences.append(line.confidence)
        
        combined_text = "\n".join(text_parts)
        avg_confidence = (
            sum(confidences) / len(confidences) 
            if confidences else 0.9
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
```

### Azure vs Tesseract

| Feature | Tesseract | Azure Form Recognizer |
|---------|-----------|----------------------|
| Cost | Free | Pay per page |
| Accuracy | Good | Excellent |
| Speed | Depends on CPU | Fast (cloud) |
| Handwriting | Poor | Good |
| Tables | Limited | Excellent |
| Languages | Many | Many |
| Setup | Install locally | Cloud API |

**Recommendation:**
- Development: Use Tesseract
- Production: Use Azure Form Recognizer

### The OCR Service

The main service picks the right engine:

```python
class OCRService:
    """Main OCR service that abstracts over different OCR engines."""
    
    def __init__(self):
        if settings.ocr.engine == "azure_form_recognizer":
            self._engine = AzureFormRecognizerEngine()
        else:
            self._engine = TesseractEngine()
        
        logger.info("OCR service initialized", engine=settings.ocr.engine)
    
    async def process_document(
        self,
        file_path: str = None,
        file_data: bytes = None,
        file_type: str = "image",
    ) -> OCRResult:
        """Process a document for OCR."""
        
        if file_data is None and file_path:
            with open(file_path, "rb") as f:
                file_data = f.read()
        
        if file_data is None:
            raise ValueError("Either file_path or file_data required")
        
        if file_type.lower() == "pdf":
            return await self._engine.process_pdf(file_data)
        else:
            return await self._engine.process_image(file_data)
    
    async def process_file(self, file_path: str) -> OCRResult:
        """Process a file, auto-detecting file type."""
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        if suffix == ".pdf":
            file_type = "pdf"
        elif suffix in (".png", ".jpg", ".jpeg", ".tiff"):
            file_type = "image"
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
        
        return await self.process_document(file_path=path, file_type=file_type)
```

### Handling OCR in the Worker

The indexer worker uses OCR:

```python
# In workers/indexer_worker.py

async def _handle_index_event(self, event: dict):
    """Handle a document index event."""
    document_id = event.get("document_id")
    file_path = event.get("data", {}).get("file_path")
    
    # Run OCR
    ocr_service = OCRService()
    result = await ocr_service.process_file(file_path)
    
    if result.text:
        # Store OCR text in database
        # Index in vector store for search
        await self._store_in_vector_db(
            document_id, 
            result.text, 
            event.get("data", {})
        )
```

### Best Practices for OCR

1. **Clean images = better results**
   - High resolution (300 DPI minimum)
   - Good contrast
   - Straight (not skewed)

2. **Pre-process when needed**
   - Convert to grayscale
   - Remove noise
   - Deskew rotated images

3. **Validate results**
   - Check confidence scores
   - Flag low-confidence documents for human review

4. **Don't re-process unchanged documents**
   - Store OCR results in database
   - Only re-process if document changes

---

## 📝 Key Takeaways

1. **OCR** converts images to searchable text
2. **Tesseract** is free but less accurate
3. **Azure Form Recognizer** is paid but excellent
4. **Entity extraction** finds dates, amounts, IDs automatically
5. **Confidence scores** tell you how reliable the results are
6. **PDF processing** requires converting pages to images first

---

## ❓ Practice Questions

1. What does OCR stand for?
2. Why might a scanned PDF need OCR?
3. What's the difference between Tesseract and Azure Form Recognizer?
4. What entities can we extract from OCR text?
5. What does a confidence score of 0.85 mean?

---

## 💻 Code Exercise

Add a new entity pattern to extract phone numbers:

```python
# Add to _extract_entities method:

# Find phone numbers (xxx-xxx-xxxx or (xxx) xxx-xxxx)
phone_pattern = r"(?:\(\d{3}\)\s?|\d{3}[.-])\d{3}[.-]\d{4}"
phones = re.findall(phone_pattern, text)
if phones:
    entities["phone_numbers"] = phones[:3]
```

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `app/services/ocr.py` | Main OCR service and engines |
| `app/schemas/documents.py` | OCRResult schema |
| `workers/ocr_worker.py` | Background OCR processing |

---

[← Previous: Vector Store](../section-08-vector-store/README.md) | [Next: Caching →](../section-10-caching/README.md)
