"""
Pydantic schemas for document-related data.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Document metadata schema for metadata-first access."""

    id: str
    claim_id: str | None = None
    policy_id: str | None = None
    source_type: str
    source_path: str
    filename: str
    file_type: str
    file_size: int | None = None
    checksum: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentResponse(DocumentMetadata):
    """Full document response with content availability."""

    ocr_text: str | None = None
    ocr_confidence: float | None = None
    extracted_entities: dict[str, Any] = Field(default_factory=dict)
    is_indexed: bool = False
    indexed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentContent(BaseModel):
    """Document content schema for on-demand retrieval."""

    id: str
    filename: str
    content_type: str
    content: bytes | None = None
    text_content: str | None = None
    ocr_text: str | None = None


class DocumentChunk(BaseModel):
    """Document chunk schema for vector storage."""

    id: str
    document_id: str
    chunk_index: int
    text: str
    embedding: list[float] | None = None
    page_number: int | None = None
    start_offset: int
    end_offset: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class OCRResult(BaseModel):
    """OCR processing result schema."""

    document_id: str
    text: str
    confidence: float
    pages: int
    language: str | None = None
    extracted_entities: dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float
    engine_used: str
