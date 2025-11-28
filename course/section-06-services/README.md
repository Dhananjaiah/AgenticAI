# Section 06: Services - The Business Logic Layer

## 🎯 Learning Goals
By the end of this section, you will understand:
- What services are and why we use them
- How deduplication works
- How the RAG (AI summary) service works
- How caching makes things faster

---

## 📺 Video Transcript

### Welcome to the Services Layer!

Hello again! In this section, we'll explore the services layer - where the "business logic" lives. Think of services as the brains that process data.

### What is the Services Layer?

If agents are like workers who gather raw materials, services are like factories that process them:

- **Agents** fetch data (raw materials)
- **Services** process data (factories)

Our main services:
1. **Orchestrator Service** - Coordinates everything
2. **Deduplication Service** - Removes duplicates
3. **RAG Service** - Creates AI summaries
4. **Cache Service** - Makes things fast

### The Claims Orchestrator Service

Open `app/services/orchestrator.py`. This is different from the Orchestrator Agent - it's the service layer version:

```python
class ClaimsOrchestrator:
    """
    High-level service for building canonical claim bundles.
    
    Coordinates:
    - Data retrieval from all sources
    - Deduplication
    - Bundle assembly
    - LLM summarization (optional)
    """
    
    async def build_claim_bundle(
        self,
        claim_id: str,
        include_llm_summary: bool = False,
        db: AsyncSession = None,
    ):
        # Step 1: Get claim from database
        # Step 2: Retrieve documents from all sources
        # Step 3: Run deduplication
        # Step 4: Build the canonical bundle
        # Step 5: Optionally add LLM summary
```

This service brings everything together!

### The Deduplication Service

Open `app/services/deduper.py`. This is really important:

```python
class DeduplicationService:
    """
    Service for entity resolution and deduplication.
    
    Implements:
    - Exact match detection (claimId, policyId, checksum)
    - Fuzzy matching (filename patterns, timestamps)
    - Embedding similarity comparison
    - Confidence scoring and thresholding
    """
```

### What is Deduplication?

Imagine you have the same document in three places:
- Email attachment
- SharePoint folder
- Cloud storage

Without deduplication, you'd process it three times! That wastes time and money.

**Deduplication** = Finding and removing duplicates

### How Deduplication Works

Let's walk through the code:

```python
async def find_duplicates(
    self,
    candidates: list[DocumentCandidate],
) -> list[DeduplicationCandidate]:
    """Find duplicate pairs among candidates."""
    
    duplicates = []
    
    # Compare all pairs
    for i, doc1 in enumerate(candidates):
        for doc2 in candidates[i + 1:]:
            score, matching_fields = await self._compute_similarity(doc1, doc2)
            
            if score > 0:
                recommendation = self._get_recommendation(score)
                duplicates.append(
                    DeduplicationCandidate(
                        document_id_1=doc1.id,
                        document_id_2=doc2.id,
                        similarity_score=score,
                        matching_fields=matching_fields,
                        recommendation=recommendation,
                    )
                )
    
    return duplicates
```

**The algorithm:**

1. Take every document
2. Compare it to every other document
3. Calculate a similarity score
4. If similar enough, mark as duplicate

### Similarity Scoring

How do we know if two documents are the same?

```python
async def _compute_similarity(self, doc1, doc2):
    """Compute similarity score between two documents."""
    
    matching_fields = {}
    scores = []
    
    # 1. Exact checksum match (most reliable!)
    if doc1.checksum and doc2.checksum and doc1.checksum == doc2.checksum:
        matching_fields["checksum"] = True
        scores.append(1.0)  # 100% sure it's the same!
    
    # 2. Same claim ID?
    if doc1.claim_id and doc2.claim_id and doc1.claim_id == doc2.claim_id:
        matching_fields["claim_id"] = True
        scores.append(0.9)  # 90% likely related
    
    # 3. Same policy ID?
    if doc1.policy_id and doc2.policy_id and doc1.policy_id == doc2.policy_id:
        matching_fields["policy_id"] = True
        scores.append(0.7)  # 70% likely related
    
    # 4. Similar filename?
    filename_sim = self._filename_similarity(doc1.filename, doc2.filename)
    if filename_sim > 0.7:
        matching_fields["filename_similarity"] = filename_sim
        scores.append(filename_sim * 0.8)
    
    # 5. Created around same time?
    if doc1.created_at and doc2.created_at:
        time_diff = abs((doc1.created_at - doc2.created_at).total_seconds())
        if time_diff < 3600:  # Within 1 hour
            matching_fields["timestamp_proximity"] = time_diff
            scores.append(0.5)
    
    # Return the highest score
    final_score = max(scores) if scores else 0.0
    return final_score, matching_fields
```

**Scoring explained:**

| Match Type | Score | Why |
|------------|-------|-----|
| Same checksum | 1.0 | Files are identical! |
| Same claim ID | 0.9 | Very likely related |
| Same policy ID | 0.7 | Probably related |
| Similar filename | 0.8 × similarity | Could be same file |
| Same time | 0.5 | Might be related |

### Recommendations

What do we do with potential duplicates?

```python
def _get_recommendation(self, score: float) -> str:
    """Get merge recommendation based on score."""
    
    if score >= 0.85:          # Very similar
        return "merge"          # Automatically merge
    elif score >= 0.60:        # Somewhat similar  
        return "review"         # Human should check
    else:
        return "keep_separate"  # Probably not duplicates
```

This creates a **human-in-the-loop** system:
- High confidence → Automatic action
- Medium confidence → Human review
- Low confidence → Keep both

### The RAG Service

RAG = Retrieval Augmented Generation

Open `app/services/rag.py`:

```python
class RAGService:
    """
    Service for RAG-based claim summarization and decisioning.
    
    Supports:
    - Azure OpenAI integration
    - OpenAI API integration
    - Stub mode for local development
    """
```

### What is RAG?

RAG is a technique to make AI smarter:

**Without RAG:**
- AI: "Tell me about claim CLM-2024-001"
- LLM: "I don't know, I wasn't trained on your data"

**With RAG:**
- AI: "Here's the claim data. Now summarize it."
- LLM: "This is a $5,000 auto claim from January..."

We **retrieve** relevant data, then the AI **generates** a response.

### Building Context for the AI

```python
async def build_context(
    self,
    structured_facts: dict,    # The claim data
    document_texts: list[str],  # Text from documents
    ocr_snippets: list[str],    # Text from images
    relevant_chunks: list[str], # Related info from vector DB
) -> LLMContextBundle:
    """Build LLM context from claim data."""
    
    # Estimate how many tokens (words roughly)
    total_text = (
        str(structured_facts)
        + " ".join(document_texts)
        + " ".join(ocr_snippets)
        + " ".join(relevant_chunks)
    )
    estimated_tokens = len(total_text) // 4
    
    return LLMContextBundle(
        structured_facts=structured_facts,
        document_summaries=document_texts[:5],   # Limit to 5
        ocr_snippets=ocr_snippets[:10],          # Limit to 10
        relevant_chunks=relevant_chunks[:5],      # Limit to top 5
        total_tokens=estimated_tokens,
    )
```

**Why do we limit?**
- LLMs have token limits (like GPT-4 has 128K max)
- More tokens = more expensive
- We pick the most relevant pieces

### Generating AI Summaries

```python
async def generate_summary(
    self,
    context: LLMContextBundle,
    prompt_type: str = "summarize",
):
    """Generate a summary or decision using LLM."""
    
    if self._mode == "stub":
        # No real AI - return fake summary
        return self._generate_stub_summary(context, prompt_type)
    
    # Build the prompt
    prompt = self._build_prompt(context, prompt_type)
    
    # Call the AI
    if self._mode == "azure":
        response = await self._call_azure_openai(prompt)
    else:
        response = await self._call_openai(prompt)
    
    return LLMSummary(
        summary=response["content"],
        confidence=response.get("confidence", 0.8),
        generated_at=datetime.utcnow(),
        model_used=response.get("model"),
    )
```

### Different Prompt Types

The RAG service supports different tasks:

```python
if prompt_type == "summarize":
    prompt += """
    Please provide a concise summary of this claim including:
    1. Key facts about the claim
    2. Current status and timeline
    3. Supporting documentation overview
    4. Any notable findings or concerns
    """

elif prompt_type == "decide":
    prompt += """
    Based on the information provided, assess the claim:
    1. Recommended action (approve/deny/investigate)
    2. Confidence level (high/medium/low)
    3. Key factors supporting this recommendation
    """

elif prompt_type == "analyze":
    prompt += """
    Perform a detailed analysis:
    1. Identify any inconsistencies or red flags
    2. Assess the documentation completeness
    3. Compare against typical claim patterns
    """
```

### Stub Mode for Development

When developing locally, you don't want to pay for AI calls:

```python
def _generate_stub_summary(self, context, prompt_type):
    """Generate a stub summary for local development."""
    
    claim_info = context.structured_facts
    
    summary = f"""[STUB MODE] Claim Summary:
    - Claim Number: {claim_info.get('claim_number', 'N/A')}
    - Type: {claim_info.get('claim_type', 'N/A')}
    - Amount: ${claim_info.get('claim_amount', 0):,.2f}
    - Status: {claim_info.get('status', 'N/A')}
    - This is a stub response for local development."""
    
    return LLMSummary(
        summary=summary,
        confidence=0.5,
        model_used="stub",
    )
```

This lets you test everything without spending money!

### Text Chunking

For long documents, we split them into chunks:

```python
async def chunk_text(
    self,
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
):
    """Split text into chunks for embedding."""
    
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
                chunk = chunk[:last_period + 1]
                end = start + last_period + 1
        
        chunks.append(chunk.strip())
        start = end - overlap  # Overlap for context
    
    return chunks
```

**Why overlap?**
If a sentence spans two chunks, overlap ensures we don't lose meaning!

```
Chunk 1: "The accident happened on Main Street. The driver..."
         ----------------------------------------[overlap]----

Chunk 2:                                 "The driver was injured."
```

---

## 📝 Key Takeaways

1. **Services** contain business logic
2. **Deduplication** removes duplicate documents using checksums and similarity
3. **RAG** = Retrieval + Generation (AI summaries)
4. **Stub mode** lets you develop without AI costs
5. **Chunking** with overlap preserves context
6. **Human-in-the-loop** for medium-confidence duplicates

---

## ❓ Practice Questions

1. What's the difference between agents and services?
2. How does checksum-based deduplication work?
3. What does RAG stand for?
4. Why do we use overlap when chunking text?
5. When would a duplicate be flagged for human review?

---

## 💻 Code Exercise

Add a new similarity check to the deduper:

```python
# Check if file sizes are identical
if doc1.file_size and doc2.file_size and doc1.file_size == doc2.file_size:
    matching_fields["file_size"] = True
    scores.append(0.6)  # 60% - same size doesn't mean same file!
```

Think: Why is same file size only 0.6 confidence?

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `app/services/orchestrator.py` | Coordinates the full workflow |
| `app/services/deduper.py` | Finds and handles duplicates |
| `app/services/rag.py` | AI summaries and analysis |
| `app/services/cache.py` | Redis caching (next section) |
| `app/services/ocr.py` | Text extraction (OCR section) |

---

[← Previous: Agents](../section-05-agents/README.md) | [Next: Database →](../section-07-database/README.md)
