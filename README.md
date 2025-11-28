# Agentic-AI Insurance Claims Architecture

A production-ready backend for an Agentic AI Insurance Claims system using Microsoft Autogen. This system retrieves claim data from multiple sources (SQL, SharePoint, Blob/S3), performs entity resolution and deduplication, and optionally generates LLM summaries.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Gateway (FastAPI)                          │
│  /claims/{id} | /policies/{id}/claims | /claims/refresh | /health | /metrics│
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Autogen Orchestrator Agent                          │
│  Coordinates retrieval, deduplication, and LLM calls                        │
└─────────────────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ SQL Retriever   │  │SharePoint Agent │  │ Blob/S3 Agent   │
│ (PostgreSQL)    │  │(Graph API/Local)│  │(Azure/AWS/Local)│
└─────────────────┘  └─────────────────┘  └─────────────────┘
           │                    │                    │
           └────────────────────┼────────────────────┘
                                │
           ┌────────────────────┼────────────────────┐
           ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Metadata Store  │  │   Vector DB     │  │      Cache      │
│  (PostgreSQL)   │  │    (Chroma)     │  │    (Redis)      │
└─────────────────┘  └─────────────────┘  └─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Entity Resolution & Deduplication                        │
│  Candidate generation | Pairwise scoring | Merge policy | Human review      │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LLM / RAG Layer                                     │
│  Azure OpenAI | OpenAI | Stub mode for local development                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Code to Components Mapping

| Component | Code Location |
|-----------|---------------|
| API Gateway | `app/api/` (claims.py, policies.py, admin.py, health.py) |
| Orchestrator Agent | `app/agents/orchestrator.py`, `app/services/orchestrator.py` |
| SQL Retriever | `app/agents/retriever_sql.py` |
| SharePoint Retriever | `app/agents/retriever_sharepoint.py` |
| Blob/S3 Retriever | `app/agents/retriever_blob.py` |
| Ingest & OCR Pipeline | `app/services/ocr.py`, `workers/ocr_worker.py` |
| Vector DB | `app/vectorstore/` (base.py, chroma_store.py) |
| Metadata Store | `app/db/models.py` (Document, IndexingState) |
| Entity Resolution | `app/services/deduper.py` |
| Queue | `app/queue/kafka_client.py` |
| Cache | `app/services/cache.py` |
| LLM/RAG | `app/services/rag.py` |
| Observability | `app/observability/` (logging_config.py, metrics.py) |

## Requirements

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+
- Kafka (or Azure Service Bus in production)

## Local Setup

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <repository-url>
cd agentic-ai-claims

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
```

### 2. Start Infrastructure Services

```bash
# Start PostgreSQL, Redis, Kafka
cd infra
docker-compose up -d postgres redis kafka

# Wait for services to be healthy
docker-compose ps
```

### 3. Apply Database Migrations

```bash
# Run Alembic migrations
alembic upgrade head
```

### 4. Run the API Server

```bash
# Development mode with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or run the full stack with Docker
cd infra
docker-compose up -d
```

### 5. Access the API

- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics

## Example Flows

### Get Claim Bundle

```bash
# Create sample data first (see tests for examples)

# Get full canonical bundle for a claim
curl http://localhost:8000/api/v1/claims/CLM-2024-001

# With LLM summary (requires Azure OpenAI configuration)
curl "http://localhost:8000/api/v1/claims/CLM-2024-001?include_llm_summary=true"
```

### Get Policy Claims

```bash
# List all claims for a policy
curl http://localhost:8000/api/v1/policies/POL-2024-001/claims
```

### Trigger Claim Refresh

```bash
# Re-fetch and re-dedupe claim data
curl -X POST http://localhost:8000/api/v1/claims/CLM-2024-001/refresh
```

### Trigger Index Rebuild

```bash
# Rebuild entire index
curl -X POST "http://localhost:8000/api/v1/admin/index/rebuild?full_rebuild=true"

# Rebuild specific source
curl -X POST "http://localhost:8000/api/v1/admin/index/rebuild?source_type=sharepoint"
```

### Review Duplicates

```bash
# List pending duplicate reviews
curl http://localhost:8000/api/v1/admin/review/duplicates

# Submit review decision
curl -X POST "http://localhost:8000/api/v1/admin/review/duplicates/{review_id}?reviewed_by=admin" \
  -H "Content-Type: application/json" \
  -d '{"decision": "merge", "notes": "Same document from different sources"}'
```

## Configuration

### Azure OpenAI Setup

To enable LLM summarization:

```bash
# In .env file
LLM_MODE=azure
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
```

### SharePoint Integration

For production SharePoint access:

```bash
# In .env file
SHAREPOINT_TENANT_ID=your-tenant-id
SHAREPOINT_CLIENT_ID=your-client-id
SHAREPOINT_CLIENT_SECRET=your-client-secret
SHAREPOINT_SITE_URL=https://your-org.sharepoint.com/sites/claims
```

For local development, place files in `data/sharepoint/` directory.

### Azure Blob Storage

```bash
# In .env file
AZURE_BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
AZURE_BLOB_CONTAINER_NAME=claims-documents
```

For local development, place files in `data/blobs/` directory.

## Plugging Real Connectors

### SharePoint Connector

Replace local simulation with real Microsoft Graph API:

```python
# In app/agents/retriever_sharepoint.py

async def _retrieve_graph_api(self, claim_id: str, include_content: bool):
    from msgraph.core import GraphClient
    
    client = GraphClient(credential=your_credential)
    # Implement Graph API calls
```

### Blob Storage Connector

Replace local simulation with Azure Blob SDK:

```python
# In app/agents/retriever_blob.py

async def _retrieve_azure_blob(self, claim_id: str, include_content: bool):
    from azure.storage.blob import BlobServiceClient
    
    blob_service = BlobServiceClient.from_connection_string(conn_str)
    # Implement Blob operations
```

## Cost Control & PII Handling

### LLM Cost Control

1. **Token Limits**: Configure `RAG_TOP_K` to limit context size
2. **Caching**: Claim bundles are cached in Redis to avoid repeated LLM calls
3. **Stub Mode**: Use `LLM_MODE=stub` for development without API costs

```bash
# In .env
RAG_TOP_K=5          # Limit retrieved chunks
RAG_CHUNK_SIZE=1000  # Control chunk sizes
CACHE_TTL_SECONDS=300  # Cache duration
```

### PII Handling

1. **Redaction**: Implement in `app/services/rag.py`:

```python
def _redact_pii(self, text: str) -> str:
    """Redact PII before sending to LLM."""
    # Implement SSN, phone, email redaction
    pass
```

2. **Clear Separation**: PII fields are marked in models
3. **Logging**: Structured logging excludes PII fields

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_api.py

# Run integration tests
pytest tests/test_integration.py -v
```

## Running Workers

```bash
# Start indexer worker
python -m workers.indexer_worker

# Start OCR worker
python -m workers.ocr_worker
```

## Docker Deployment

```bash
# Build and run everything
cd infra
docker-compose up -d --build

# View logs
docker-compose logs -f api

# Scale workers
docker-compose up -d --scale indexer-worker=3
```

## Monitoring

### Health Checks

- `/health` - Full system health
- `/ready` - Kubernetes readiness probe
- `/live` - Kubernetes liveness probe

### Metrics

Prometheus-compatible metrics at `/metrics`:

- `claims_http_requests_total` - Request count by endpoint
- `claims_http_request_duration_seconds` - Request latency
- `claims_cache_hit_rate` - Cache effectiveness
- `claims_llm_calls_total` - LLM API usage
- `claims_documents_indexed_total` - Indexing progress

### Logging

Structured JSON logging with correlation IDs:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "info",
  "correlation_id": "abc-123",
  "claim_id": "CLM-001",
  "message": "Claim bundle retrieved"
}
```

## Project Structure

```
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── api/                  # API routers
│   │   ├── claims.py
│   │   ├── policies.py
│   │   ├── admin.py
│   │   └── health.py
│   ├── agents/               # Autogen agents
│   │   ├── orchestrator.py
│   │   ├── retriever_sql.py
│   │   ├── retriever_sharepoint.py
│   │   └── retriever_blob.py
│   ├── services/             # Business logic
│   │   ├── orchestrator.py
│   │   ├── deduper.py
│   │   ├── rag.py
│   │   ├── cache.py
│   │   ├── ocr.py
│   │   └── indexer.py
│   ├── db/                   # Database layer
│   │   ├── models.py
│   │   ├── session.py
│   │   └── migrations/
│   ├── vectorstore/          # Vector DB abstraction
│   │   ├── base.py
│   │   └── chroma_store.py
│   ├── queue/                # Message queue
│   │   └── kafka_client.py
│   ├── observability/        # Logging & metrics
│   │   ├── logging_config.py
│   │   └── metrics.py
│   └── schemas/              # Pydantic models
│       ├── claims.py
│       ├── policies.py
│       ├── documents.py
│       └── deduplication.py
├── workers/
│   ├── indexer_worker.py
│   └── ocr_worker.py
├── data/                     # Local simulation data
│   ├── sharepoint/
│   └── blobs/
├── infra/
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── init-db.sql
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_deduper.py
│   ├── test_vectorstore.py
│   ├── test_orchestrator.py
│   └── test_integration.py
├── alembic.ini
├── pyproject.toml
├── .env.example
└── README.md
```

## License

MIT License
