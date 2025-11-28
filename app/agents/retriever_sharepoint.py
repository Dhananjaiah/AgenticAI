"""
SharePoint Retriever Agent.

Autogen agent for retrieving documents from SharePoint.
Supports both real Microsoft Graph API and local simulation.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.observability.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class SharePointRetrieverAgent:
    """
    Autogen agent for SharePoint document retrieval.

    Provides:
    - Metadata-first access to documents
    - List PDFs/CSVs by metadata
    - On-demand content fetching
    - Support for both real SharePoint and local simulation
    """

    def __init__(self) -> None:
        """Initialize the SharePoint retriever agent."""
        self._config = self._build_config()
        self._local_path = Path(settings.sharepoint.local_path)
        self._use_local = not settings.sharepoint.client_id
        logger.info(
            "SharePoint retriever agent initialized",
            use_local=self._use_local,
        )

    def _build_config(self) -> dict[str, Any]:
        """Build Autogen configuration for SharePoint retriever."""
        return {
            "name": "SharePointRetriever",
            "system_message": """You are a SharePoint document retrieval agent. Your role is to
            fetch claim-related documents from SharePoint efficiently.

            When asked to retrieve documents:
            1. First list available documents by metadata
            2. Do not fetch content unless explicitly requested
            3. Support PDF, CSV, and other document types
            4. Return metadata with document references
            5. Tag documents with claimId/policyId
            """,
            "human_input_mode": "NEVER",
        }

    async def retrieve_by_claim_id(
        self,
        claim_id: str,
        include_content: bool = False,
    ) -> dict[str, Any]:
        """
        Retrieve documents for a claim from SharePoint.

        Args:
            claim_id: Claim ID or claim number
            include_content: Whether to include document content

        Returns:
            dict: Retrieved documents with metadata
        """
        logger.info(
            "SharePoint retrieval by claim_id",
            claim_id=claim_id,
            include_content=include_content,
        )

        if self._use_local:
            return await self._retrieve_local(claim_id, include_content)
        else:
            return await self._retrieve_graph_api(claim_id, include_content)

    async def retrieve_by_policy_id(
        self,
        policy_id: str,
        include_content: bool = False,
    ) -> dict[str, Any]:
        """
        Retrieve documents for a policy from SharePoint.

        Args:
            policy_id: Policy ID or policy number
            include_content: Whether to include document content

        Returns:
            dict: Retrieved documents with metadata
        """
        logger.info(
            "SharePoint retrieval by policy_id",
            policy_id=policy_id,
            include_content=include_content,
        )

        if self._use_local:
            return await self._retrieve_local_by_policy(policy_id, include_content)
        else:
            return await self._retrieve_graph_api_by_policy(policy_id, include_content)

    async def _retrieve_local(
        self,
        claim_id: str,
        include_content: bool,
    ) -> dict[str, Any]:
        """Retrieve from local simulation directory."""
        documents = []

        # Check if local path exists
        if not self._local_path.exists():
            logger.warning("Local SharePoint path does not exist", path=str(self._local_path))
            return {
                "success": True,
                "source": "sharepoint_local",
                "metadata": {
                    "claim_id": claim_id,
                    "retrieved_at": datetime.utcnow().isoformat(),
                    "document_count": 0,
                },
                "documents": [],
            }

        # Look for claim-specific folder or files
        claim_folder = self._local_path / claim_id
        if claim_folder.exists():
            documents = await self._scan_folder(claim_folder, claim_id, include_content)
        else:
            # Scan all files looking for claim references
            documents = await self._scan_for_claim(self._local_path, claim_id, include_content)

        return {
            "success": True,
            "source": "sharepoint_local",
            "metadata": {
                "claim_id": claim_id,
                "retrieved_at": datetime.utcnow().isoformat(),
                "document_count": len(documents),
            },
            "documents": documents,
        }

    async def _retrieve_local_by_policy(
        self,
        policy_id: str,
        include_content: bool,
    ) -> dict[str, Any]:
        """Retrieve from local simulation by policy ID."""
        documents = []

        if not self._local_path.exists():
            return {
                "success": True,
                "source": "sharepoint_local",
                "metadata": {
                    "policy_id": policy_id,
                    "retrieved_at": datetime.utcnow().isoformat(),
                    "document_count": 0,
                },
                "documents": [],
            }

        # Scan for policy references
        documents = await self._scan_for_policy(self._local_path, policy_id, include_content)

        return {
            "success": True,
            "source": "sharepoint_local",
            "metadata": {
                "policy_id": policy_id,
                "retrieved_at": datetime.utcnow().isoformat(),
                "document_count": len(documents),
            },
            "documents": documents,
        }

    async def _scan_folder(
        self,
        folder: Path,
        claim_id: str,
        include_content: bool,
    ) -> list[dict[str, Any]]:
        """Scan a folder for documents."""
        documents = []

        for path in folder.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                doc = await self._create_document_entry(path, claim_id, include_content)
                if doc:
                    documents.append(doc)

        return documents

    async def _scan_for_claim(
        self,
        folder: Path,
        claim_id: str,
        include_content: bool,
    ) -> list[dict[str, Any]]:
        """Scan for files related to a claim."""
        documents = []

        # Look for metadata files
        metadata_file = folder / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
                for doc_info in metadata.get("documents", []):
                    if doc_info.get("claim_id") == claim_id:
                        doc_path = folder / doc_info["filename"]
                        if doc_path.exists():
                            doc = await self._create_document_entry(
                                doc_path, claim_id, include_content
                            )
                            if doc:
                                doc.update(doc_info)
                                documents.append(doc)

        # Also scan for files with claim ID in name
        for path in folder.rglob("*"):
            if path.is_file() and claim_id in path.name:
                doc = await self._create_document_entry(path, claim_id, include_content)
                if doc:
                    documents.append(doc)

        return documents

    async def _scan_for_policy(
        self,
        folder: Path,
        policy_id: str,
        include_content: bool,
    ) -> list[dict[str, Any]]:
        """Scan for files related to a policy."""
        documents = []

        # Look for metadata files
        metadata_file = folder / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
                for doc_info in metadata.get("documents", []):
                    if doc_info.get("policy_id") == policy_id:
                        doc_path = folder / doc_info["filename"]
                        if doc_path.exists():
                            doc = await self._create_document_entry(
                                doc_path, None, include_content
                            )
                            if doc:
                                doc["policy_id"] = policy_id
                                doc.update(doc_info)
                                documents.append(doc)

        return documents

    async def _create_document_entry(
        self,
        path: Path,
        claim_id: str | None,
        include_content: bool,
    ) -> dict[str, Any] | None:
        """Create a document entry from a file path."""
        if not path.exists():
            return None

        stat = path.stat()
        suffix = path.suffix.lower()

        # Determine file type
        file_type = "unknown"
        if suffix == ".pdf":
            file_type = "pdf"
        elif suffix in (".csv", ".xlsx", ".xls"):
            file_type = "spreadsheet"
        elif suffix in (".doc", ".docx"):
            file_type = "document"
        elif suffix in (".png", ".jpg", ".jpeg", ".tiff"):
            file_type = "image"
        elif suffix in (".txt", ".md"):
            file_type = "text"

        doc = {
            "id": f"sp_{path.stem}_{hash(str(path)) % 10000}",
            "filename": path.name,
            "file_type": file_type,
            "source_type": "sharepoint",
            "source_path": str(path.relative_to(self._local_path)),
            "file_size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "claim_id": claim_id,
        }

        if include_content and file_type == "text":
            try:
                with open(path) as f:
                    doc["content"] = f.read()
            except Exception as e:
                logger.warning("Failed to read file content", path=str(path), error=str(e))

        return doc

    async def _retrieve_graph_api(
        self,
        claim_id: str,
        include_content: bool,
    ) -> dict[str, Any]:
        """Retrieve from real SharePoint via Microsoft Graph API."""
        # This would use msgraph-core for real implementation
        logger.info("Graph API retrieval requested", claim_id=claim_id)

        # Placeholder for real implementation
        return {
            "success": False,
            "source": "sharepoint_graph",
            "error": "Graph API integration not configured",
            "metadata": {
                "claim_id": claim_id,
                "retrieved_at": datetime.utcnow().isoformat(),
            },
            "documents": [],
        }

    async def _retrieve_graph_api_by_policy(
        self,
        policy_id: str,
        include_content: bool,
    ) -> dict[str, Any]:
        """Retrieve from real SharePoint by policy ID."""
        return {
            "success": False,
            "source": "sharepoint_graph",
            "error": "Graph API integration not configured",
            "metadata": {
                "policy_id": policy_id,
                "retrieved_at": datetime.utcnow().isoformat(),
            },
            "documents": [],
        }

    async def fetch_content(self, document_id: str) -> bytes | None:
        """
        Fetch document content on-demand.

        Args:
            document_id: Document ID

        Returns:
            bytes: Document content or None
        """
        logger.info("Fetching document content", document_id=document_id)

        # In local mode, would look up the file and return content
        # In production, would use Graph API to download

        return None

    def get_metadata_only(self, claim_id: str) -> dict[str, Any]:
        """
        Get metadata-only response for a claim.

        Args:
            claim_id: Claim ID

        Returns:
            dict: Metadata about available documents
        """
        return {
            "source": "sharepoint",
            "claim_id": claim_id,
            "available_types": ["pdf", "csv", "docx", "xlsx"],
            "fetch_content": self.fetch_content,
        }
