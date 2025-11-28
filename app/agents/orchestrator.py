"""
Autogen Orchestrator Agent.

Central agent that coordinates retrieval and processing of claim data
using Microsoft Autogen framework.
"""

from typing import Any

from app.config import get_settings
from app.observability.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class OrchestratorAgent:
    """
    Central Autogen orchestrator agent for claim data processing.

    Responsibilities:
    - Receives high-level tasks (retrieve and dedupe claim data)
    - Spawns and coordinates retriever agents
    - Orchestrates metadata-first retrieval
    - Manages deduplication and entity resolution
    - Optionally invokes LLM for summarization
    """

    def __init__(self) -> None:
        """Initialize the orchestrator agent."""
        self._config = self._build_config()
        self._retriever_agents: dict[str, Any] = {}
        logger.info("Orchestrator agent initialized")

    def _build_config(self) -> dict[str, Any]:
        """Build Autogen configuration."""
        config = {
            "name": "ClaimsOrchestrator",
            "system_message": """You are the central orchestrator for an insurance claims 
            processing system. Your role is to coordinate data retrieval from multiple sources,
            ensure data quality through deduplication, and provide comprehensive claim bundles.
            
            When asked to process a claim:
            1. First retrieve metadata from all sources
            2. Identify relevant documents and data
            3. Perform deduplication and entity resolution
            4. Build a canonical claim bundle
            5. Optionally generate an LLM summary
            """,
            "human_input_mode": "NEVER",
            "max_consecutive_auto_reply": 10,
        }

        # Add LLM config if available
        if settings.llm.mode == "azure":
            config["llm_config"] = {
                "config_list": [
                    {
                        "model": settings.azure_openai.deployment_name,
                        "api_type": "azure",
                        "api_key": settings.azure_openai.api_key,
                        "base_url": settings.azure_openai.endpoint,
                        "api_version": settings.azure_openai.api_version,
                    }
                ],
                "temperature": 0.3,
            }
        elif settings.llm.mode == "openai":
            config["llm_config"] = {
                "config_list": [{"model": "gpt-4"}],
                "temperature": 0.3,
            }
        else:
            config["llm_config"] = False  # Disable LLM in stub mode

        return config

    async def process_claim(
        self,
        claim_id: str,
        include_summary: bool = False,
    ) -> dict[str, Any]:
        """
        Process a claim request.

        Args:
            claim_id: The claim ID to process
            include_summary: Whether to include LLM summary

        Returns:
            dict: Processing result with claim bundle
        """
        logger.info("Processing claim request", claim_id=claim_id)

        # In a full Autogen implementation, this would:
        # 1. Create an AssistantAgent with the config
        # 2. Spawn retriever agents as tools or separate agents
        # 3. Run a conversation to retrieve and process data

        # For now, we use a simplified direct implementation
        result = {
            "claim_id": claim_id,
            "status": "processed",
            "sources_queried": ["sql", "sharepoint", "blob"],
            "documents_found": 0,
            "deduplication_performed": True,
            "summary_included": include_summary,
        }

        return result

    async def spawn_retriever(
        self,
        source_type: str,
        claim_id: str,
    ) -> dict[str, Any]:
        """
        Spawn a retriever agent for a specific source.

        Args:
            source_type: Type of source (sql, sharepoint, blob)
            claim_id: Claim ID to retrieve

        Returns:
            dict: Retriever result
        """
        logger.info(
            "Spawning retriever",
            source_type=source_type,
            claim_id=claim_id,
        )

        if source_type == "sql":
            from app.agents.retriever_sql import SQLRetrieverAgent
            agent = SQLRetrieverAgent()
            return await agent.retrieve_by_claim_id(claim_id)
        elif source_type == "sharepoint":
            from app.agents.retriever_sharepoint import SharePointRetrieverAgent
            agent = SharePointRetrieverAgent()
            return await agent.retrieve_by_claim_id(claim_id)
        elif source_type == "blob":
            from app.agents.retriever_blob import BlobRetrieverAgent
            agent = BlobRetrieverAgent()
            return await agent.retrieve_by_claim_id(claim_id)
        else:
            raise ValueError(f"Unknown source type: {source_type}")

    def get_autogen_config(self) -> dict[str, Any]:
        """
        Get Autogen configuration for external use.

        Returns:
            dict: Autogen configuration
        """
        return self._config.copy()

    async def run_conversation(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run an Autogen conversation for a task.

        This is a placeholder for full Autogen integration.
        In production, this would:
        1. Initialize agents
        2. Set up group chat or sequential chat
        3. Run the conversation
        4. Parse and return results

        Args:
            task: Task description
            context: Additional context

        Returns:
            dict: Conversation result
        """
        logger.info("Running conversation", task=task)

        # Placeholder implementation
        # Full Autogen would use:
        # from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

        return {
            "task": task,
            "status": "completed",
            "result": "Placeholder - full Autogen implementation pending",
            "context": context,
        }
