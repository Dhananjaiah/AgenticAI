# Section 03: Understanding the Architecture

## 🎯 Learning Goals
By the end of this section, you will understand:
- The overall system architecture
- How data flows through the system
- What each component does
- How components communicate with each other

---

## 📺 Video Transcript

### The Big Picture

Welcome back! Now that we have everything set up, let's understand how our system works. I'll draw you a picture with words.

### Think of It Like a Restaurant

Before we look at the technical diagram, let me use a simple analogy.

**A restaurant has:**
- **Customers** who order food
- **Waiters** who take orders to the kitchen
- **Kitchen** with specialized cooks (one for pasta, one for grills, etc.)
- **Manager** who coordinates everything
- **Storage** areas for ingredients

**Our system is similar:**
- **Users/Clients** who request claim information
- **API Gateway** (like waiters) that receives requests
- **Agents** (like specialized cooks) that fetch data
- **Orchestrator** (like the manager) that coordinates agents
- **Databases** (like storage) that hold all the data

### The Architecture Diagram

Let's look at the actual system:

```
┌─────────────────────────────────────────────────────────────────┐
│                     USERS / CLIENTS                             │
│              (Web browsers, mobile apps, other systems)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API GATEWAY (FastAPI)                        │
│                                                                 │
│   /claims/{id}  /policies/{id}/claims  /health  /metrics        │
│                                                                 │
│   • Receives HTTP requests                                      │
│   • Validates input                                             │
│   • Returns responses                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ORCHESTRATOR AGENT                             │
│                                                                 │
│   • The "manager" of all agents                                 │
│   • Decides which agents to call                                │
│   • Combines results from multiple agents                       │
│   • Uses Microsoft Autogen framework                            │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   SQL AGENT      │ │ SHAREPOINT AGENT │ │   BLOB AGENT     │
│                  │ │                  │ │                  │
│ • Queries        │ │ • Reads files    │ │ • Gets images    │
│   PostgreSQL     │ │   from SharePoint│ │   from cloud     │
│ • Gets claims,   │ │ • PDFs, CSVs,    │ │ • Photos, scans  │
│   policies,      │ │   Word docs      │ │ • Azure Blob or  │
│   payments       │ │                  │ │   AWS S3         │
└──────────────────┘ └──────────────────┘ └──────────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SERVICES LAYER                               │
│                                                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ Deduplication│ │    OCR      │ │    RAG      │ │   Cache   │  │
│  │   Service    │ │  Service    │ │  Service    │ │  Service  │  │
│  │             │ │             │ │             │ │           │  │
│  │ • Finds     │ │ • Reads     │ │ • AI        │ │ • Makes   │  │
│  │   duplicates│ │   text from │ │   summaries │ │   things  │  │
│  │ • Merges    │ │   images    │ │ • Answers   │ │   fast    │  │
│  │   records   │ │   and PDFs  │ │   questions │ │           │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA STORAGE LAYER                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  PostgreSQL  │  │   ChromaDB   │  │    Redis     │           │
│  │              │  │              │  │              │           │
│  │  • Claims    │  │  • Vector    │  │  • Fast      │           │
│  │  • Policies  │  │    embeddings│  │    cache     │           │
│  │  • Customers │  │  • AI search │  │  • Sessions  │           │
│  │  • Documents │  │              │  │              │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

### Let's Follow a Request

Here's what happens when someone asks for a claim:

**Step 1: Request arrives**
```
User sends: GET /api/v1/claims/CLM-2024-001
```

**Step 2: API Gateway receives it**
- FastAPI checks: "Is this a valid request?"
- Routes to the claims handler

**Step 3: Orchestrator takes over**
- Orchestrator says: "I need data for CLM-2024-001"
- Creates a plan: "I'll ask all three agents"

**Step 4: Agents do their jobs**
- SQL Agent: "Found claim in database! Amount: $5,000"
- SharePoint Agent: "Found 3 PDFs related to this claim"
- Blob Agent: "Found 5 photos of the damage"

**Step 5: Services process the data**
- Deduplication: "2 of those PDFs are duplicates. Removing one."
- OCR: "I extracted text from the remaining documents"
- Cache: "I'll save this result for next time"

**Step 6: Response sent**
```json
{
  "claim_id": "CLM-2024-001",
  "claim_number": "CLM-2024-001",
  "status": "under_review",
  "claim_amount": 5000,
  "documents": [
    {"filename": "damage_report.pdf", "source": "sharepoint"},
    {"filename": "photo1.jpg", "source": "blob"}
  ]
}
```

### Understanding Each Layer

#### Layer 1: API Gateway (FastAPI)

**What it does:**
- Listens for HTTP requests (GET, POST, etc.)
- Validates that requests are correct
- Returns responses in JSON format

**Key files:**
- `app/main.py` - The main entry point
- `app/api/claims.py` - Claim-related endpoints
- `app/api/policies.py` - Policy-related endpoints
- `app/api/health.py` - Health check endpoints

**Example endpoints:**
| Endpoint | What it does |
|----------|--------------|
| `GET /claims/{id}` | Get a specific claim |
| `GET /policies/{id}/claims` | Get all claims for a policy |
| `POST /claims/{id}/refresh` | Re-process a claim |
| `GET /health` | Check system health |

#### Layer 2: Orchestrator Agent

**What it does:**
- Coordinates all the retriever agents
- Decides which agents to call
- Combines results from multiple sources
- Uses Microsoft Autogen framework

**Key file:** `app/agents/orchestrator.py`

**Think of it like a project manager:**
- "SQL Agent, get me the claim details"
- "SharePoint Agent, find related documents"
- "Blob Agent, look for any images"
- "Now let me combine all your results"

#### Layer 3: Retriever Agents

We have three specialized agents:

**SQL Retriever Agent (`app/agents/retriever_sql.py`):**
- Talks to PostgreSQL database
- Gets: claims, policies, customers, payments
- Uses secure parameterized queries (prevents hacking!)

**SharePoint Retriever Agent (`app/agents/retriever_sharepoint.py`):**
- Connects to Microsoft SharePoint
- Gets: PDFs, Word docs, Excel files
- Works with local files for development

**Blob Retriever Agent (`app/agents/retriever_blob.py`):**
- Connects to cloud storage (Azure Blob or AWS S3)
- Gets: images, scans, large files
- Extracts EXIF metadata from photos

#### Layer 4: Services

**Deduplication Service (`app/services/deduper.py`):**
- Finds duplicate documents
- Uses checksums (like fingerprints for files)
- Can flag uncertain cases for human review

**OCR Service (`app/services/ocr.py`):**
- Reads text from images (Optical Character Recognition)
- Supports PDF files too
- Uses Tesseract (free) or Azure Form Recognizer (paid)

**RAG Service (`app/services/rag.py`):**
- RAG = Retrieval Augmented Generation
- Takes documents and creates AI summaries
- Can answer questions about claims

**Cache Service (`app/services/cache.py`):**
- Stores frequently accessed data in Redis
- Makes repeated requests super fast
- Automatically expires old data

#### Layer 5: Data Storage

**PostgreSQL:**
- Main database for all structured data
- Claims, policies, customers, payments
- Reliable and supports complex queries

**ChromaDB:**
- Vector database for AI search
- Stores document embeddings (AI representations)
- Enables semantic search (finding similar content)

**Redis:**
- Super-fast cache (keeps data in memory)
- Stores recent claim bundles
- Reduces database load

### How Components Talk to Each Other

```
┌─────────────────────────────────────────────────────────────┐
│                    COMMUNICATION                            │
│                                                             │
│  API → Orchestrator     : Direct function calls             │
│  Orchestrator → Agents  : Direct function calls             │
│  Services → Databases   : Async database connections        │
│  Workers → Queue        : Kafka messages (for background jobs)│
│  Cache → Services       : Redis protocol                    │
└─────────────────────────────────────────────────────────────┘
```

Most communication happens through **direct function calls** - one Python function calling another. This is simple and fast.

For background jobs (like processing new documents), we use **Kafka** message queue. This allows:
- Jobs to be processed even if they take a long time
- Retrying failed jobs automatically
- Scaling by adding more workers

---

## 📝 Key Takeaways

1. **Layered architecture** = Each layer has one job
2. **API Gateway** = Receives and validates requests
3. **Orchestrator** = Coordinates agents
4. **Agents** = Specialized data fetchers
5. **Services** = Business logic (dedup, OCR, cache)
6. **Storage** = PostgreSQL + ChromaDB + Redis

---

## ❓ Practice Questions

1. What's the role of the Orchestrator?
2. Name the three retriever agents
3. What's the difference between PostgreSQL and ChromaDB?
4. Why do we use Redis cache?
5. How does data flow from a user request to a response?

---

## 🗺️ Code Mapping

| Component | Code Location |
|-----------|---------------|
| API Gateway | `app/api/*.py` |
| Orchestrator | `app/agents/orchestrator.py` |
| SQL Agent | `app/agents/retriever_sql.py` |
| SharePoint Agent | `app/agents/retriever_sharepoint.py` |
| Blob Agent | `app/agents/retriever_blob.py` |
| Deduplication | `app/services/deduper.py` |
| OCR | `app/services/ocr.py` |
| RAG/LLM | `app/services/rag.py` |
| Cache | `app/services/cache.py` |
| Database Models | `app/db/models.py` |
| Vector Store | `app/vectorstore/*.py` |

---

[← Previous: Getting Started](../section-02-getting-started/README.md) | [Next: API Layer →](../section-04-api-layer/README.md)
