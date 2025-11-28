# Section 05: AI Agents and Retrievers - The Smart Workers

## 🎯 Learning Goals
By the end of this section, you will understand:
- What an AI "agent" is
- How the Orchestrator coordinates agents
- How each retriever agent works
- The metadata-first approach

---

## 📺 Video Transcript

### Welcome to the World of AI Agents!

Hello everyone! This is one of the most exciting sections of our course. We're going to learn about AI agents - the smart workers that make our system intelligent.

### What is an AI Agent?

An **agent** is a piece of software that can:
1. **Perceive** - Understand what's being asked
2. **Decide** - Figure out what to do
3. **Act** - Execute the action
4. **Learn** - Improve over time (optionally)

Think of agents like specialists in a hospital:
- A cardiologist knows hearts
- A neurologist knows brains
- They each have expertise but work together for the patient

Our agents:
- SQL Agent knows databases
- SharePoint Agent knows SharePoint
- Blob Agent knows cloud storage
- They work together for the claim!

### Microsoft Autogen Framework

We use **Microsoft Autogen** to build our agents. Autogen is a framework that helps AI agents work together.

**Key concepts in Autogen:**
- **AssistantAgent** - An AI that can chat and reason
- **UserProxyAgent** - Represents a human (or other system)
- **GroupChat** - Multiple agents talking together
- **Tools** - Functions that agents can call

### The Orchestrator: The Manager

Open `app/agents/orchestrator.py`. This is our manager agent:

```python
# app/agents/orchestrator.py

class OrchestratorAgent:
    """
    Central Autogen orchestrator agent for claim data processing.
    
    Responsibilities:
    - Receives high-level tasks (retrieve and dedupe claim data)
    - Spawns and coordinates retriever agents
    - Orchestrates metadata-first retrieval
    - Manages deduplication and entity resolution
    """
    
    def __init__(self) -> None:
        self._config = self._build_config()
        self._retriever_agents = {}
```

**What does the Orchestrator do?**

1. **Receives a task**: "Get me claim CLM-2024-001"
2. **Plans the work**: "I need to check SQL, SharePoint, and Blob storage"
3. **Calls agents**: Sends each agent to do their job
4. **Collects results**: Gathers all the data
5. **Combines everything**: Creates one complete picture

### The Orchestrator Configuration

```python
def _build_config(self) -> dict:
    config = {
        "name": "ClaimsOrchestrator",
        "system_message": """You are the central orchestrator for an 
        insurance claims processing system. Your role is to coordinate 
        data retrieval from multiple sources, ensure data quality 
        through deduplication, and provide comprehensive claim bundles.
        """,
        "human_input_mode": "NEVER",  # No human input needed
        "max_consecutive_auto_reply": 10,
    }
    
    # Add LLM config if we're using Azure OpenAI
    if settings.llm.mode == "azure":
        config["llm_config"] = {
            "config_list": [{
                "model": settings.azure_openai.deployment_name,
                "api_type": "azure",
                # ... more settings
            }],
            "temperature": 0.3,  # Lower = more focused
        }
    
    return config
```

**Key settings:**
- `system_message` - Tells the AI what its job is
- `human_input_mode: "NEVER"` - Runs automatically without asking humans
- `temperature: 0.3` - Makes responses more consistent (less creative)

### Spawning Retriever Agents

When the Orchestrator needs data, it spawns retriever agents:

```python
async def spawn_retriever(self, source_type: str, claim_id: str):
    """Spawn a retriever agent for a specific source."""
    
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
```

This is like the manager saying: "SQL Agent, go find this claim in the database!"

### SQL Retriever Agent

Let's explore `app/agents/retriever_sql.py`:

```python
class SQLRetrieverAgent:
    """
    Autogen agent for SQL data retrieval.
    
    Provides parameterized queries with pagination for:
    - Claims
    - Customers  
    - Policies
    - Payments
    - Statuses
    """
    
    async def retrieve_by_claim_id(
        self,
        claim_id: str,
        include_related: bool = True,
        page: int = 1,
        page_size: int = 100,
    ):
        """Retrieve claim data by claim ID."""
        
        async with get_db_context() as db:
            # Build the query
            stmt = select(Claim).where(
                (Claim.id == claim_id) | (Claim.claim_number == claim_id)
            )
            
            # Include related data if requested
            if include_related:
                stmt = stmt.options(
                    selectinload(Claim.policy),
                    selectinload(Claim.documents),
                    selectinload(Claim.payments),
                )
            
            result = await db.execute(stmt)
            claim = result.scalar_one_or_none()
            
            if not claim:
                return {
                    "success": False,
                    "error": f"Claim {claim_id} not found",
                    "source": "sql",
                }
            
            return {
                "success": True,
                "source": "sql",
                "rows": [self._serialize_claim(claim)],
            }
```

**What's happening here?**

1. **Parameterized queries** - The `claim_id` is safely inserted (prevents SQL injection attacks!)
2. **Related data loading** - `selectinload` grabs connected data (policy, documents, payments)
3. **Pagination** - For when there's lots of data
4. **Serialization** - Converts database objects to simple dictionaries

### SharePoint Retriever Agent

Now let's look at `app/agents/retriever_sharepoint.py`:

```python
class SharePointRetrieverAgent:
    """
    Autogen agent for SharePoint document retrieval.
    
    Provides:
    - Metadata-first access to documents
    - List PDFs/CSVs by metadata
    - On-demand content fetching
    """
    
    def __init__(self):
        self._local_path = Path(settings.sharepoint.local_path)
        self._use_local = not settings.sharepoint.client_id
    
    async def retrieve_by_claim_id(
        self,
        claim_id: str,
        include_content: bool = False,  # Important! Default is False
    ):
        """Retrieve documents for a claim from SharePoint."""
        
        if self._use_local:
            return await self._retrieve_local(claim_id, include_content)
        else:
            return await self._retrieve_graph_api(claim_id, include_content)
```

**Key concepts:**

1. **Local vs Production mode**: Uses local files for development, real SharePoint for production
2. **include_content = False**: This is the metadata-first approach!

### The Metadata-First Approach

This is a crucial concept. Let me explain:

**Problem**: Documents can be huge. Downloading everything is slow and expensive.

**Solution**: Metadata-first approach

1. **First, get metadata only**:
   ```python
   # "What documents exist?"
   result = await agent.retrieve_by_claim_id("CLM-001", include_content=False)
   # Returns: [{"filename": "report.pdf", "size": 5000000}, ...]
   ```

2. **Then, fetch content only if needed**:
   ```python
   # "Now give me the actual file"
   content = await agent.fetch_content(document_id)
   ```

It's like a library catalog:
- First, you check what books exist
- Then, you only get the books you need

### Blob Retriever Agent

The `app/agents/retriever_blob.py` handles cloud storage:

```python
class BlobRetrieverAgent:
    """
    Autogen agent for Blob/S3 storage retrieval.
    
    Provides:
    - Metadata-first access to images and scans
    - EXIF/timestamp extraction
    - On-demand content fetching
    """
    
    async def _create_file_entry(
        self,
        path: Path,
        claim_id: str,
        include_content: bool,
    ):
        """Create a file entry from a file path."""
        
        stat = path.stat()
        suffix = path.suffix.lower()
        
        # Determine file type
        if suffix in (".png", ".jpg", ".jpeg"):
            file_type = "image"
        elif suffix == ".pdf":
            file_type = "pdf"
        
        # Calculate checksum (like a fingerprint)
        with open(path, "rb") as f:
            content = f.read()
            checksum = hashlib.md5(content).hexdigest()
        
        file_entry = {
            "id": f"blob_{path.stem}_{hash(str(path)) % 10000}",
            "filename": path.name,
            "file_type": file_type,
            "file_size": stat.st_size,
            "checksum": checksum,  # Important for deduplication!
            "claim_id": claim_id,
        }
        
        # Extract EXIF data for images
        if file_type == "image":
            exif_data = await self._extract_exif(path)
            if exif_data:
                file_entry["exif"] = exif_data
        
        return file_entry
```

**Special features:**

1. **Checksum calculation** - A unique fingerprint for each file
2. **EXIF extraction** - Gets metadata from photos (date taken, camera, etc.)
3. **File type detection** - Knows what kind of file it is

### How Agents Work Together

Here's a complete flow:

```python
# In the Orchestrator

async def process_claim(self, claim_id: str, include_summary: bool = False):
    """Process a claim request."""
    
    # Step 1: Gather data from all sources
    sql_result = await self.spawn_retriever("sql", claim_id)
    sp_result = await self.spawn_retriever("sharepoint", claim_id)
    blob_result = await self.spawn_retriever("blob", claim_id)
    
    # Step 2: Combine results
    all_documents = (
        sp_result.get("documents", []) + 
        blob_result.get("files", [])
    )
    
    # Step 3: Return combined data
    return {
        "claim_id": claim_id,
        "status": "processed",
        "sources_queried": ["sql", "sharepoint", "blob"],
        "documents_found": len(all_documents),
    }
```

### The Response Format

All agents return data in a consistent format:

```python
{
    "success": True,           # Did it work?
    "source": "sql",           # Where did this come from?
    "metadata": {
        "claim_id": "CLM-001",
        "retrieved_at": "2024-01-15T10:30:00Z",
        "record_count": 1,
    },
    "rows": [...] or "documents": [...] or "files": [...]
}
```

This consistency makes it easy to combine results!

### Error Handling in Agents

Agents handle errors gracefully:

```python
if not claim:
    return {
        "success": False,
        "error": f"Claim {claim_id} not found",
        "source": "sql",
        "metadata": {},
        "rows": [],
    }
```

Even when something goes wrong, we return a proper response. The orchestrator can then decide what to do.

---

## 📝 Key Takeaways

1. **Agents** are specialized workers with specific jobs
2. **Orchestrator** coordinates all agents like a manager
3. **Metadata-first** approach saves bandwidth and time
4. **Consistent response format** makes combining data easy
5. **Checksums** enable deduplication across sources
6. **Local mode** allows development without real cloud services

---

## ❓ Practice Questions

1. What is the role of the Orchestrator agent?
2. Why do we use metadata-first approach?
3. What is a checksum and why is it useful?
4. How does the SQL agent prevent SQL injection attacks?
5. What's the difference between local mode and production mode?

---

## 💻 Code Exercise

Try adding a new retriever agent for email:

```python
# app/agents/retriever_email.py

class EmailRetrieverAgent:
    """Agent for retrieving claim-related emails."""
    
    async def retrieve_by_claim_id(self, claim_id: str):
        # What would you put here?
        pass
```

Hint: Think about what metadata you'd want (sender, subject, date, attachments).

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `app/agents/orchestrator.py` | The manager agent |
| `app/agents/retriever_sql.py` | Database queries |
| `app/agents/retriever_sharepoint.py` | SharePoint documents |
| `app/agents/retriever_blob.py` | Cloud storage files |

---

[← Previous: API Layer](../section-04-api-layer/README.md) | [Next: Services →](../section-06-services/README.md)
