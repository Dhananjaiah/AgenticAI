"""
Blob/S3 Retriever Agent.

Autogen agent for retrieving documents from Azure Blob Storage or AWS S3.
Supports both real cloud storage and local simulation.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.observability.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class BlobRetrieverAgent:
    """
    Autogen agent for Blob/S3 storage retrieval.

    Provides:
    - Metadata-first access to images and scans
    - EXIF/timestamp extraction
    - On-demand content fetching
    - Support for Azure Blob, AWS S3, and local simulation
    """

    def __init__(self) -> None:
        """Initialize the Blob retriever agent."""
        self._config = self._build_config()
        self._local_path = Path(settings.blob_storage.local_path)
        self._use_local = not (
            settings.blob_storage.azure_connection_string
            or settings.blob_storage.aws_access_key_id
        )
        logger.info(
            "Blob retriever agent initialized",
            use_local=self._use_local,
        )

    def _build_config(self) -> dict[str, Any]:
        """Build Autogen configuration for Blob retriever."""
        return {
            "name": "BlobRetriever",
            "system_message": """You are a blob storage retrieval agent. Your role is to
            fetch claim-related images, scans, and documents from blob storage efficiently.

            When asked to retrieve files:
            1. First list available files by metadata
            2. Extract EXIF and timestamp information
            3. Do not fetch content unless explicitly requested
            4. Return metadata with file references
            5. Tag files with claimId/policyId
            """,
            "human_input_mode": "NEVER",
        }

    async def retrieve_by_claim_id(
        self,
        claim_id: str,
        include_content: bool = False,
    ) -> dict[str, Any]:
        """
        Retrieve files for a claim from blob storage.

        Args:
            claim_id: Claim ID or claim number
            include_content: Whether to include file content

        Returns:
            dict: Retrieved files with metadata
        """
        logger.info(
            "Blob retrieval by claim_id",
            claim_id=claim_id,
            include_content=include_content,
        )

        if self._use_local:
            return await self._retrieve_local(claim_id, include_content)
        elif settings.blob_storage.azure_connection_string:
            return await self._retrieve_azure_blob(claim_id, include_content)
        else:
            return await self._retrieve_s3(claim_id, include_content)

    async def retrieve_by_policy_id(
        self,
        policy_id: str,
        include_content: bool = False,
    ) -> dict[str, Any]:
        """
        Retrieve files for a policy from blob storage.

        Args:
            policy_id: Policy ID or policy number
            include_content: Whether to include file content

        Returns:
            dict: Retrieved files with metadata
        """
        logger.info(
            "Blob retrieval by policy_id",
            policy_id=policy_id,
            include_content=include_content,
        )

        if self._use_local:
            return await self._retrieve_local_by_policy(policy_id, include_content)
        elif settings.blob_storage.azure_connection_string:
            return await self._retrieve_azure_blob_by_policy(policy_id, include_content)
        else:
            return await self._retrieve_s3_by_policy(policy_id, include_content)

    async def _retrieve_local(
        self,
        claim_id: str,
        include_content: bool,
    ) -> dict[str, Any]:
        """Retrieve from local simulation directory."""
        files = []

        if not self._local_path.exists():
            logger.warning("Local blob path does not exist", path=str(self._local_path))
            return {
                "success": True,
                "source": "blob_local",
                "metadata": {
                    "claim_id": claim_id,
                    "retrieved_at": datetime.utcnow().isoformat(),
                    "file_count": 0,
                },
                "files": [],
            }

        # Look for claim-specific folder or files
        claim_folder = self._local_path / claim_id
        if claim_folder.exists():
            files = await self._scan_folder(claim_folder, claim_id, include_content)
        else:
            # Scan all files looking for claim references
            files = await self._scan_for_claim(self._local_path, claim_id, include_content)

        return {
            "success": True,
            "source": "blob_local",
            "metadata": {
                "claim_id": claim_id,
                "retrieved_at": datetime.utcnow().isoformat(),
                "file_count": len(files),
            },
            "files": files,
        }

    async def _retrieve_local_by_policy(
        self,
        policy_id: str,
        include_content: bool,
    ) -> dict[str, Any]:
        """Retrieve from local simulation by policy ID."""
        files = []

        if not self._local_path.exists():
            return {
                "success": True,
                "source": "blob_local",
                "metadata": {
                    "policy_id": policy_id,
                    "retrieved_at": datetime.utcnow().isoformat(),
                    "file_count": 0,
                },
                "files": [],
            }

        # Scan for policy references
        files = await self._scan_for_policy(self._local_path, policy_id, include_content)

        return {
            "success": True,
            "source": "blob_local",
            "metadata": {
                "policy_id": policy_id,
                "retrieved_at": datetime.utcnow().isoformat(),
                "file_count": len(files),
            },
            "files": files,
        }

    async def _scan_folder(
        self,
        folder: Path,
        claim_id: str,
        include_content: bool,
    ) -> list[dict[str, Any]]:
        """Scan a folder for files."""
        files = []

        for path in folder.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                file_entry = await self._create_file_entry(path, claim_id, include_content)
                if file_entry:
                    files.append(file_entry)

        return files

    async def _scan_for_claim(
        self,
        folder: Path,
        claim_id: str,
        include_content: bool,
    ) -> list[dict[str, Any]]:
        """Scan for files related to a claim."""
        files = []

        # Look for metadata files
        metadata_file = folder / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
                for file_info in metadata.get("files", []):
                    if file_info.get("claim_id") == claim_id:
                        file_path = folder / file_info["filename"]
                        if file_path.exists():
                            file_entry = await self._create_file_entry(
                                file_path, claim_id, include_content
                            )
                            if file_entry:
                                file_entry.update(file_info)
                                files.append(file_entry)

        # Also scan for files with claim ID in name
        for path in folder.rglob("*"):
            if path.is_file() and claim_id in path.name:
                file_entry = await self._create_file_entry(path, claim_id, include_content)
                if file_entry:
                    files.append(file_entry)

        return files

    async def _scan_for_policy(
        self,
        folder: Path,
        policy_id: str,
        include_content: bool,
    ) -> list[dict[str, Any]]:
        """Scan for files related to a policy."""
        files = []

        # Look for metadata files
        metadata_file = folder / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
                for file_info in metadata.get("files", []):
                    if file_info.get("policy_id") == policy_id:
                        file_path = folder / file_info["filename"]
                        if file_path.exists():
                            file_entry = await self._create_file_entry(
                                file_path, None, include_content
                            )
                            if file_entry:
                                file_entry["policy_id"] = policy_id
                                file_entry.update(file_info)
                                files.append(file_entry)

        return files

    async def _create_file_entry(
        self,
        path: Path,
        claim_id: str | None,
        include_content: bool,
    ) -> dict[str, Any] | None:
        """Create a file entry from a file path."""
        if not path.exists():
            return None

        stat = path.stat()
        suffix = path.suffix.lower()

        # Determine file type
        file_type = "unknown"
        if suffix in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"):
            file_type = "image"
        elif suffix == ".pdf":
            file_type = "pdf"
        elif suffix in (".csv", ".xlsx", ".xls"):
            file_type = "spreadsheet"

        # Calculate checksum
        with open(path, "rb") as f:
            content = f.read()
            checksum = hashlib.md5(content).hexdigest()

        file_entry = {
            "id": f"blob_{path.stem}_{hash(str(path)) % 10000}",
            "filename": path.name,
            "file_type": file_type,
            "source_type": "blob",
            "source_path": str(path.relative_to(self._local_path)),
            "file_size": stat.st_size,
            "checksum": checksum,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "claim_id": claim_id,
        }

        # Extract EXIF data for images
        if file_type == "image":
            exif_data = await self._extract_exif(path)
            if exif_data:
                file_entry["exif"] = exif_data

        if include_content:
            file_entry["content_base64"] = None  # Would include base64 content

        return file_entry

    async def _extract_exif(self, path: Path) -> dict[str, Any] | None:
        """Extract EXIF data from an image."""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            with Image.open(path) as img:
                exif_data = img._getexif()
                if not exif_data:
                    return None

                result = {}
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if isinstance(value, (str, int, float)):
                        result[tag] = value

                return result if result else None
        except Exception as e:
            logger.debug("Failed to extract EXIF", path=str(path), error=str(e))
            return None

    async def _retrieve_azure_blob(
        self,
        claim_id: str,
        include_content: bool,
    ) -> dict[str, Any]:
        """Retrieve from Azure Blob Storage."""
        logger.info("Azure Blob retrieval requested", claim_id=claim_id)

        # Placeholder for real implementation
        # Would use azure-storage-blob SDK
        return {
            "success": False,
            "source": "azure_blob",
            "error": "Azure Blob integration not configured",
            "metadata": {
                "claim_id": claim_id,
                "retrieved_at": datetime.utcnow().isoformat(),
            },
            "files": [],
        }

    async def _retrieve_azure_blob_by_policy(
        self,
        policy_id: str,
        include_content: bool,
    ) -> dict[str, Any]:
        """Retrieve from Azure Blob by policy ID."""
        return {
            "success": False,
            "source": "azure_blob",
            "error": "Azure Blob integration not configured",
            "metadata": {
                "policy_id": policy_id,
                "retrieved_at": datetime.utcnow().isoformat(),
            },
            "files": [],
        }

    async def _retrieve_s3(
        self,
        claim_id: str,
        include_content: bool,
    ) -> dict[str, Any]:
        """Retrieve from AWS S3."""
        logger.info("S3 retrieval requested", claim_id=claim_id)

        # Placeholder for real implementation
        # Would use boto3 SDK
        return {
            "success": False,
            "source": "s3",
            "error": "S3 integration not configured",
            "metadata": {
                "claim_id": claim_id,
                "retrieved_at": datetime.utcnow().isoformat(),
            },
            "files": [],
        }

    async def _retrieve_s3_by_policy(
        self,
        policy_id: str,
        include_content: bool,
    ) -> dict[str, Any]:
        """Retrieve from S3 by policy ID."""
        return {
            "success": False,
            "source": "s3",
            "error": "S3 integration not configured",
            "metadata": {
                "policy_id": policy_id,
                "retrieved_at": datetime.utcnow().isoformat(),
            },
            "files": [],
        }

    async def fetch_content(self, file_id: str) -> bytes | None:
        """
        Fetch file content on-demand.

        Args:
            file_id: File ID

        Returns:
            bytes: File content or None
        """
        logger.info("Fetching file content", file_id=file_id)

        # In local mode, would look up the file and return content
        # In production, would use Azure Blob or S3 SDK to download

        return None

    def get_metadata_only(self, claim_id: str) -> dict[str, Any]:
        """
        Get metadata-only response for a claim.

        Args:
            claim_id: Claim ID

        Returns:
            dict: Metadata about available files
        """
        return {
            "source": "blob",
            "claim_id": claim_id,
            "available_types": ["image", "pdf", "scan"],
            "fetch_content": self.fetch_content,
        }
