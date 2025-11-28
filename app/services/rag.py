"""
RAG (Retrieval-Augmented Generation) Service.

Provides functionality for:
- Building RAG prompts from structured facts and documents
- Integrating with Azure OpenAI (configurable)
- Stub mode for local development
"""

from datetime import datetime
from typing import Any

from app.config import get_settings
from app.schemas.claims import LLMContextBundle, LLMSummary
from app.observability.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class RAGService:
    """
    Service for RAG-based claim summarization and decisioning.

    Supports:
    - Azure OpenAI integration
    - OpenAI API integration
    - Stub mode for local development
    """

    def __init__(self) -> None:
        """Initialize RAG service with configured LLM backend."""
        self._mode = settings.llm.mode
        self._client = None

        if self._mode == "azure":
            self._init_azure_client()
        elif self._mode == "openai":
            self._init_openai_client()
        else:
            logger.info("RAG service initialized in stub mode")

    def _init_azure_client(self) -> None:
        """Initialize Azure OpenAI client."""
        try:
            from openai import AzureOpenAI

            self._client = AzureOpenAI(
                api_key=settings.azure_openai.api_key,
                api_version=settings.azure_openai.api_version,
                azure_endpoint=settings.azure_openai.endpoint,
            )
            logger.info("Azure OpenAI client initialized")
        except Exception as e:
            logger.warning("Failed to initialize Azure OpenAI", error=str(e))
            self._mode = "stub"

    def _init_openai_client(self) -> None:
        """Initialize standard OpenAI client."""
        try:
            from openai import OpenAI

            self._client = OpenAI()
            logger.info("OpenAI client initialized")
        except Exception as e:
            logger.warning("Failed to initialize OpenAI", error=str(e))
            self._mode = "stub"

    async def build_context(
        self,
        structured_facts: dict[str, Any],
        document_texts: list[str],
        ocr_snippets: list[str],
        relevant_chunks: list[str],
    ) -> LLMContextBundle:
        """
        Build LLM context from claim data.

        Args:
            structured_facts: Structured claim facts
            document_texts: Full document texts
            ocr_snippets: OCR extracted text snippets
            relevant_chunks: Vector DB retrieved chunks

        Returns:
            LLMContextBundle: Assembled context for LLM
        """
        # Estimate token count (rough approximation)
        total_text = (
            str(structured_facts)
            + " ".join(document_texts)
            + " ".join(ocr_snippets)
            + " ".join(relevant_chunks)
        )
        estimated_tokens = len(total_text) // 4  # Rough token estimate

        return LLMContextBundle(
            structured_facts=structured_facts,
            document_summaries=document_texts[:5],  # Limit summaries
            ocr_snippets=ocr_snippets[:10],  # Limit snippets
            relevant_chunks=relevant_chunks[:settings.rag.top_k],
            total_tokens=estimated_tokens,
        )

    async def generate_summary(
        self,
        context: LLMContextBundle,
        prompt_type: str = "summarize",
    ) -> LLMSummary:
        """
        Generate a summary or decision using LLM.

        Args:
            context: LLM context bundle
            prompt_type: Type of prompt ("summarize", "decide", "analyze")

        Returns:
            LLMSummary: Generated summary
        """
        logger.info(
            "Generating LLM summary",
            mode=self._mode,
            prompt_type=prompt_type,
            tokens=context.total_tokens,
        )

        if self._mode == "stub":
            return self._generate_stub_summary(context, prompt_type)

        # Build the prompt
        prompt = self._build_prompt(context, prompt_type)

        try:
            if self._mode == "azure":
                response = await self._call_azure_openai(prompt)
            else:
                response = await self._call_openai(prompt)

            return LLMSummary(
                summary=response["content"],
                decision=response.get("decision"),
                confidence=response.get("confidence", 0.8),
                explanation=response.get("explanation"),
                generated_at=datetime.utcnow(),
                model_used=response.get("model"),
            )
        except Exception as e:
            logger.error("LLM generation failed", error=str(e))
            return self._generate_stub_summary(context, prompt_type)

    def _build_prompt(
        self,
        context: LLMContextBundle,
        prompt_type: str,
    ) -> str:
        """Build prompt for LLM based on context and type."""
        base_prompt = f"""You are an insurance claims analyst assistant. Analyze the following claim information and provide a {prompt_type}.

## Structured Facts
{self._format_facts(context.structured_facts)}

## Document Summaries
{self._format_list(context.document_summaries)}

## OCR Extracted Text
{self._format_list(context.ocr_snippets)}

## Relevant Context
{self._format_list(context.relevant_chunks)}

"""

        if prompt_type == "summarize":
            base_prompt += """
Please provide a concise summary of this claim including:
1. Key facts about the claim
2. Current status and timeline
3. Supporting documentation overview
4. Any notable findings or concerns
"""
        elif prompt_type == "decide":
            base_prompt += """
Based on the information provided, assess the claim and recommend a decision:
1. Recommended action (approve/deny/investigate)
2. Confidence level (high/medium/low)
3. Key factors supporting this recommendation
4. Any additional information needed
"""
        elif prompt_type == "analyze":
            base_prompt += """
Perform a detailed analysis of this claim:
1. Identify any inconsistencies or red flags
2. Assess the documentation completeness
3. Compare against typical claim patterns
4. Provide risk assessment
"""

        return base_prompt

    def _format_facts(self, facts: dict[str, Any]) -> str:
        """Format structured facts for prompt."""
        lines = []
        for key, value in facts.items():
            if value is not None:
                lines.append(f"- {key}: {value}")
        return "\n".join(lines) if lines else "No structured facts available."

    def _format_list(self, items: list[str]) -> str:
        """Format list items for prompt."""
        if not items:
            return "None available."
        return "\n".join(f"- {item}" for item in items)

    async def _call_azure_openai(self, prompt: str) -> dict[str, Any]:
        """Call Azure OpenAI API."""
        if not self._client:
            raise RuntimeError("Azure OpenAI client not initialized")

        response = self._client.chat.completions.create(
            model=settings.azure_openai.deployment_name,
            messages=[
                {"role": "system", "content": "You are an expert insurance claims analyst."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
        )

        return {
            "content": response.choices[0].message.content,
            "model": settings.azure_openai.deployment_name,
            "confidence": 0.85,
        }

    async def _call_openai(self, prompt: str) -> dict[str, Any]:
        """Call OpenAI API."""
        if not self._client:
            raise RuntimeError("OpenAI client not initialized")

        response = self._client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert insurance claims analyst."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
        )

        return {
            "content": response.choices[0].message.content,
            "model": "gpt-4",
            "confidence": 0.85,
        }

    def _generate_stub_summary(
        self,
        context: LLMContextBundle,
        prompt_type: str,
    ) -> LLMSummary:
        """Generate a stub summary for local development."""
        claim_info = context.structured_facts

        if prompt_type == "summarize":
            summary = f"""[STUB MODE] Claim Summary:
- Claim Number: {claim_info.get('claim_number', 'N/A')}
- Type: {claim_info.get('claim_type', 'N/A')}
- Amount: ${claim_info.get('claim_amount', 0):,.2f}
- Status: {claim_info.get('status', 'N/A')}
- Documents: {len(context.document_summaries)} attached
- This is a stub response for local development."""
        elif prompt_type == "decide":
            summary = f"""[STUB MODE] Claim Decision:
- Recommendation: Under Review
- Confidence: Medium
- Reason: This is a stub response for local development.
- Claim Amount: ${claim_info.get('claim_amount', 0):,.2f}"""
        else:
            summary = f"""[STUB MODE] Claim Analysis:
- Claim appears complete based on available documents.
- No obvious red flags detected in stub mode.
- Full analysis requires LLM connection."""

        return LLMSummary(
            summary=summary,
            decision="pending_review" if prompt_type == "decide" else None,
            confidence=0.5,
            explanation="Generated in stub mode - no LLM connection",
            generated_at=datetime.utcnow(),
            model_used="stub",
        )

    async def generate_embeddings(self, text: str) -> list[float]:
        """
        Generate embeddings for text.

        Args:
            text: Input text

        Returns:
            list: Embedding vector
        """
        if self._mode == "stub":
            # Return zero vector for stub mode
            return [0.0] * 1536

        if self._mode == "azure" and self._client:
            try:
                response = self._client.embeddings.create(
                    model=settings.azure_openai.embedding_deployment,
                    input=text,
                )
                return response.data[0].embedding
            except Exception as e:
                logger.error("Embedding generation failed", error=str(e))
                return [0.0] * 1536

        return [0.0] * 1536

    async def chunk_text(
        self,
        text: str,
        chunk_size: int | None = None,
        overlap: int | None = None,
    ) -> list[str]:
        """
        Split text into chunks for embedding.

        Args:
            text: Input text
            chunk_size: Size of each chunk
            overlap: Overlap between chunks

        Returns:
            list: Text chunks
        """
        chunk_size = chunk_size or settings.rag.chunk_size
        overlap = overlap or settings.rag.chunk_overlap

        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind(".")
                if last_period > chunk_size // 2:
                    chunk = chunk[: last_period + 1]
                    end = start + last_period + 1

            chunks.append(chunk.strip())
            start = end - overlap

        return chunks
