# Section 04: The API Layer - How the Web Interface Works

## 🎯 Learning Goals
By the end of this section, you will understand:
- What FastAPI is and why we use it
- How HTTP endpoints work
- The structure of our API
- How to test API endpoints

---

## 📺 Video Transcript

### Introduction to the API Layer

Hello again! In this section, we're going to explore the API layer - the part of our system that talks to the outside world.

### What is an API?

API stands for **Application Programming Interface**. Think of it like a waiter in a restaurant:

- You (the customer) want food
- The kitchen has the food
- The waiter takes your order to the kitchen and brings back your food

In our system:
- Users want claim data
- Our database has the data
- The API takes requests and returns data

### What is FastAPI?

FastAPI is a modern Python framework for building APIs. We chose it because:

1. **Fast** - It's one of the fastest Python web frameworks
2. **Easy to use** - Python type hints make code clear
3. **Auto-documentation** - Creates interactive docs automatically
4. **Validation** - Checks that data is correct before processing

### Let's Look at the Code!

Open `app/main.py`. This is where our API starts:

```python
# app/main.py

from fastapi import FastAPI
from app.api import claims_router, policies_router, health_router, admin_router

# Create the FastAPI application
app = FastAPI(
    title="Agentic-AI Insurance Claims",
    description="API for processing insurance claims with AI",
    version="0.1.0",
)

# Add routes (different URL paths)
app.include_router(health_router)                      # /health
app.include_router(claims_router, prefix="/api/v1")    # /api/v1/claims/...
app.include_router(policies_router, prefix="/api/v1")  # /api/v1/policies/...
app.include_router(admin_router, prefix="/api/v1")     # /api/v1/admin/...
```

**What's happening here?**

1. We create a FastAPI app with a title and description
2. We add "routers" - groups of related endpoints
3. Each router handles a different part of the API

### Understanding Routers

Think of routers like departments in a company:

| Router | Path | Purpose |
|--------|------|---------|
| health_router | `/health` | Check if system is running |
| claims_router | `/api/v1/claims` | All claim operations |
| policies_router | `/api/v1/policies` | All policy operations |
| admin_router | `/api/v1/admin` | Admin operations |

### Exploring the Claims Router

Let's look at `app/api/claims.py` - the heart of our API:

```python
# app/api/claims.py

from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/claims", tags=["claims"])

@router.get("/{claim_id}")
async def get_claim_bundle(
    claim_id: str,
    include_llm_summary: bool = Query(default=False),
    force_refresh: bool = Query(default=False),
):
    """
    Get the full canonical bundle for a claim.
    """
    # ... code to fetch claim data ...
```

**Breaking this down:**

1. **`@router.get("/{claim_id}")`** 
   - This is a "decorator" that says "when someone visits GET /claims/something, run this function"
   - `{claim_id}` is a placeholder - it captures whatever is in the URL

2. **`async def get_claim_bundle(...)`**
   - The function that handles the request
   - `async` means it can run without blocking (good for performance)

3. **Parameters:**
   - `claim_id: str` - Captured from the URL
   - `include_llm_summary: bool = Query(default=False)` - Optional query parameter

### The Complete Claims API

Here are all the endpoints in our claims router:

```
GET  /api/v1/claims/                  → List all claims
GET  /api/v1/claims/{claim_id}        → Get one claim (full bundle)
POST /api/v1/claims/{claim_id}/refresh → Refresh claim data
```

Let me explain each one:

#### 1. List Claims
```
GET /api/v1/claims/?status=pending&page=1&page_size=20
```

Returns a list of claims. You can filter and paginate:
- `status` - Filter by claim status (pending, approved, denied)
- `page` - Which page of results (for large lists)
- `page_size` - How many claims per page

**Example response:**
```json
[
  {
    "id": "uuid-1",
    "claim_number": "CLM-2024-001",
    "status": "pending",
    "claim_amount": 5000,
    "filed_date": "2024-01-15"
  },
  {
    "id": "uuid-2",
    "claim_number": "CLM-2024-002",
    "status": "approved",
    "claim_amount": 3500,
    "filed_date": "2024-01-16"
  }
]
```

#### 2. Get Claim Bundle
```
GET /api/v1/claims/CLM-2024-001
GET /api/v1/claims/CLM-2024-001?include_llm_summary=true
```

Returns EVERYTHING about a claim:
- Structured facts (amount, status, dates)
- All documents from all sources
- Deduplication info
- Optional AI summary

**Example response:**
```json
{
  "claim_id": "uuid-1",
  "claim_number": "CLM-2024-001",
  "structured_facts": {
    "claim_type": "auto",
    "claim_amount": 5000,
    "status": "pending",
    "incident_date": "2024-01-10"
  },
  "document_list": [
    {
      "id": "doc-1",
      "filename": "police_report.pdf",
      "source_type": "sharepoint"
    },
    {
      "id": "doc-2", 
      "filename": "damage_photo.jpg",
      "source_type": "blob"
    }
  ],
  "dedupe_info": {
    "duplicates_found": 1,
    "duplicates_removed": 1
  },
  "llm_summary": {
    "summary": "Auto collision claim for $5,000. Police report included."
  }
}
```

#### 3. Refresh Claim
```
POST /api/v1/claims/CLM-2024-001/refresh
```

Re-fetches all data for a claim:
- Checks all sources again
- Re-runs deduplication
- Updates the cached bundle

**Example response:**
```json
{
  "claim_id": "uuid-1",
  "message": "Refresh job queued successfully",
  "refresh_started": true,
  "job_id": "job-uuid"
}
```

### Understanding HTTP Methods

**GET** - Retrieve data (doesn't change anything)
- "Give me the claim information"

**POST** - Create or trigger actions
- "Start a refresh job"

**PUT** - Update data (not used much in our API)

**DELETE** - Remove data (not used much in our API)

### Query Parameters vs Path Parameters

**Path parameters** are in the URL path:
```
/claims/CLM-2024-001
        ^^^^^^^^^^^^^ This is a path parameter
```

**Query parameters** come after `?`:
```
/claims/?status=pending&page=1
         ^^^^^^^^^^^^^^^ These are query parameters
```

### How Validation Works

FastAPI automatically validates input. Look at this:

```python
@router.get("/")
async def list_claims(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),           # Must be >= 1
    page_size: int = Query(default=20, ge=1, le=100),  # 1 to 100
):
```

If someone tries:
- `page=-1` → Error! "Page must be >= 1"
- `page_size=500` → Error! "Page size must be <= 100"

This prevents bad data from reaching our system!

### The Interactive Documentation

Here's the coolest thing about FastAPI. Go to:

```
http://localhost:8000/docs
```

You'll see beautiful, interactive documentation! You can:
- See all available endpoints
- Read descriptions
- Test endpoints directly in your browser
- See example responses

This is automatically generated from our code. No extra work needed!

### Health and Metrics Endpoints

The health router (`app/api/health.py`) provides:

```
GET /health   → Full system health
GET /ready    → Is the app ready? (for Kubernetes)
GET /live     → Is the app alive? (for Kubernetes)
GET /metrics  → Prometheus metrics (for monitoring)
```

**Example health response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "components": {
    "database": "healthy",
    "cache": "healthy"
  }
}
```

### Error Handling

When something goes wrong, we return proper HTTP status codes:

| Code | Meaning | When we use it |
|------|---------|----------------|
| 200 | OK | Request succeeded |
| 404 | Not Found | Claim doesn't exist |
| 400 | Bad Request | Invalid input |
| 500 | Server Error | Something broke |

```python
from fastapi import HTTPException

if not claim:
    raise HTTPException(
        status_code=404,
        detail=f"Claim {claim_id} not found"
    )
```

### Testing the API

You can test with curl (command line):

```bash
# List claims
curl http://localhost:8000/api/v1/claims/

# Get specific claim
curl http://localhost:8000/api/v1/claims/CLM-2024-001

# With query parameter
curl "http://localhost:8000/api/v1/claims/CLM-2024-001?include_llm_summary=true"

# Trigger refresh
curl -X POST http://localhost:8000/api/v1/claims/CLM-2024-001/refresh
```

Or use the interactive docs at `/docs`!

---

## 📝 Key Takeaways

1. **FastAPI** creates our web API quickly and safely
2. **Routers** group related endpoints together
3. **Decorators** like `@router.get()` define which URLs do what
4. **Path parameters** (`{claim_id}`) capture values from URLs
5. **Query parameters** (`?status=pending`) add optional filters
6. **Validation** happens automatically
7. **Interactive docs** at `/docs` let you test the API

---

## ❓ Practice Questions

1. What's the difference between GET and POST?
2. How do you access the interactive API documentation?
3. What happens if you request a claim that doesn't exist?
4. What's the difference between `/claims/123` and `/claims/?id=123`?

---

## 💻 Try It Yourself

1. Start the server: `uvicorn app.main:app --reload`
2. Open http://localhost:8000/docs
3. Try the health endpoint
4. Look at the available claims endpoints
5. Try making a request (even though there's no data yet, you'll see the structure)

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | Main application, includes all routers |
| `app/api/claims.py` | Claims endpoints |
| `app/api/policies.py` | Policy endpoints |
| `app/api/admin.py` | Admin endpoints |
| `app/api/health.py` | Health check endpoints |

---

[← Previous: Architecture](../section-03-architecture/README.md) | [Next: AI Agents →](../section-05-agents/README.md)
