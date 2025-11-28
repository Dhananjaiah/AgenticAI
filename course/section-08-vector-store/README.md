# Section 08: Vector Store and Semantic Search

## 🎯 Learning Goals
By the end of this section, you will understand:
- What vector embeddings are
- How semantic search works
- What ChromaDB is
- How we use vectors to find similar documents

---

## 📺 Video Transcript

### Welcome to Vector Databases!

Hello again! This section is about one of the coolest parts of modern AI systems - vector databases and semantic search. Don't worry, I'll explain it simply!

### What is a Vector?

A **vector** is just a list of numbers. For example:

```
[0.1, 0.5, -0.3, 0.8]
```

That's a vector with 4 numbers. Simple!

### What are Embeddings?

An **embedding** is a way to represent text (or images) as a vector. Think of it as translating words into a language that computers understand better.

**Example:**

```
"The car was damaged in the accident"
    ↓ (AI magic)
[0.12, -0.45, 0.78, 0.34, ... 1536 numbers total]
```

The key insight: **Similar sentences have similar embeddings!**

```
"The vehicle was damaged in the crash"  → [0.11, -0.44, 0.79, ...]  (very similar!)
"I love pizza"                          → [0.95, 0.22, -0.61, ...]  (very different!)
```

### Why Use Embeddings?

Traditional search is keyword-based:
- Search for "car accident" → Only finds exact words "car" and "accident"
- Misses "vehicle crash" even though it means the same thing!

**Semantic search** with embeddings:
- Search for "car accident" → Finds "vehicle crash", "auto collision", etc.
- Understands *meaning*, not just words!

### What is ChromaDB?

ChromaDB is a **vector database**. It stores embeddings and lets you search by similarity.

Think of it like a library where books are organized by meaning, not alphabetically:
- All books about "adventure" are near each other
- All books about "cooking" are in a different area
- If you want "adventure", you search near the adventure area

### Our Vector Store Implementation

Open `app/vectorstore/base.py` to see the interface:

```python
class VectorStore(ABC):
    """Abstract base class for vector storage."""
    
    @abstractmethod
    async def add_documents(self, documents: list[VectorDocument]) -> list[str]:
        """Add documents to the vector store."""
        pass
    
    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict = None,
    ) -> list[SearchResult]:
        """Search for similar documents by embedding."""
        pass
    
    @abstractmethod
    async def search_by_text(
        self,
        query_text: str,
        top_k: int = 5,
        filters: dict = None,
    ) -> list[SearchResult]:
        """Search for similar documents by text."""
        pass
```

This is an **interface** - it defines what any vector store must do, without saying *how*.

### The VectorDocument Class

```python
@dataclass
class VectorDocument:
    """Represents a document in the vector store."""
    
    id: str                           # Unique identifier
    content: str                      # The actual text
    embedding: list[float] | None     # The vector (optional)
    metadata: dict | None             # Extra info (claim_id, source, etc.)
```

### ChromaDB Implementation

Open `app/vectorstore/chroma_store.py`:

```python
class ChromaVectorStore(VectorStore):
    """ChromaDB-based vector store implementation."""
    
    def __init__(self):
        self._client = None
        self._collection = None
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Initialize Chroma on first use."""
        if self._initialized:
            return
        
        import chromadb
        from chromadb.config import Settings
        
        self._client = chromadb.Client(Settings(
            persist_directory="./data/chroma",
            anonymized_telemetry=False,
        ))
        
        self._collection = self._client.get_or_create_collection(
            name="claims_documents",
            metadata={"hnsw:space": "cosine"},  # Use cosine similarity
        )
        
        self._initialized = True
```

**Key points:**
- `persist_directory` - Where to save the data
- `get_or_create_collection` - Like a folder for related documents
- `cosine` - How we measure similarity (more on this below)

### Adding Documents

```python
async def add_documents(self, documents: list[VectorDocument]) -> list[str]:
    """Add documents to the vector store."""
    await self._ensure_initialized()
    
    ids = []
    documents_data = []
    embeddings_data = []
    metadatas = []
    
    for doc in documents:
        ids.append(doc.id)
        documents_data.append(doc.content)
        if doc.embedding:
            embeddings_data.append(doc.embedding)
        metadatas.append(doc.metadata or {})
    
    # Add to Chroma
    self._collection.add(
        ids=ids,
        documents=documents_data,
        embeddings=embeddings_data,  # If provided
        metadatas=metadatas,
    )
    
    return ids
```

If you don't provide embeddings, ChromaDB generates them for you!

### Searching by Embedding

```python
async def search(
    self,
    query_embedding: list[float],
    top_k: int = 5,
    filters: dict = None,
) -> list[SearchResult]:
    """Search for similar documents by embedding."""
    await self._ensure_initialized()
    
    results = self._collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=filters,  # e.g., {"claim_id": "CLM-001"}
        include=["documents", "metadatas", "distances"],
    )
    
    return self._parse_results(results)
```

### Searching by Text

Even simpler - you give text, Chroma generates the embedding:

```python
async def search_by_text(
    self,
    query_text: str,
    top_k: int = 5,
    filters: dict = None,
) -> list[SearchResult]:
    """Search for similar documents by text."""
    await self._ensure_initialized()
    
    results = self._collection.query(
        query_texts=[query_text],  # Note: texts, not embeddings
        n_results=top_k,
        where=filters,
        include=["documents", "metadatas", "distances"],
    )
    
    return self._parse_results(results)
```

### Understanding Similarity Scores

We use **cosine similarity**:

```
Similarity = cos(angle between two vectors)

1.0 = Identical (0° angle)
0.0 = Unrelated (90° angle)
-1.0 = Opposite (180° angle)
```

**In code:**

```python
def _parse_results(self, results):
    """Parse Chroma results into SearchResult objects."""
    search_results = []
    
    for i, doc_id in enumerate(results["ids"][0]):
        distance = results["distances"][0][i]
        
        # Convert distance to similarity
        # (Chroma returns distance, lower = more similar)
        score = 1.0 - distance
        
        search_results.append(SearchResult(
            document=VectorDocument(id=doc_id, content=...),
            score=score,        # 0 to 1
            distance=distance,  # Raw distance
        ))
    
    return search_results
```

### Filtering by Metadata

You can filter results:

```python
# Find documents for a specific claim
results = await vector_store.search_by_text(
    query_text="damage assessment report",
    top_k=5,
    filters={"claim_id": "CLM-2024-001"},
)

# Find documents from a specific source
results = await vector_store.search_by_text(
    query_text="medical expenses",
    top_k=5,
    filters={"source_type": "sharepoint"},
)
```

### How Documents Get Indexed

In our indexer worker (`workers/indexer_worker.py`):

```python
async def _store_in_vector_db(self, document_id: str, text: str, metadata: dict):
    """Store document text in vector database."""
    
    rag = RAGService()
    
    # Split long text into chunks
    chunks = await rag.chunk_text(text)
    
    documents = []
    for i, chunk in enumerate(chunks):
        doc = VectorDocument(
            id=f"{document_id}_chunk_{i}",
            content=chunk,
            metadata={
                "document_id": document_id,
                "chunk_index": i,
                "claim_id": metadata.get("claim_id"),
                "source_type": metadata.get("source_type"),
            },
        )
        documents.append(doc)
    
    await self._vector_store.add_documents(documents)
```

**Flow:**
1. Document text arrives
2. Text is split into chunks (e.g., 1000 characters each)
3. Each chunk becomes a VectorDocument
4. ChromaDB generates embeddings and stores them

### Real-World Example

Let's trace a semantic search:

```python
# User searches for "car damage photos"
query = "car damage photos"

# ChromaDB:
# 1. Converts query to embedding: [0.45, -0.23, 0.67, ...]
# 2. Compares to all stored embeddings
# 3. Returns top 5 most similar

results = await vector_store.search_by_text(query, top_k=5)

# Results might include:
# - "Photo showing front bumper damage" (score: 0.92)
# - "Vehicle collision images attached" (score: 0.88)
# - "Pictures of auto body damage" (score: 0.85)
```

Notice: None contain the exact words "car damage photos", but they're all relevant!

### Managing the Collection

```python
async def count(self, filters: dict = None) -> int:
    """Count documents in the store."""
    if filters:
        results = self._collection.get(where=filters, include=[])
        return len(results["ids"])
    else:
        return self._collection.count()

async def clear(self) -> None:
    """Clear all documents from the store."""
    self._client.delete_collection("claims_documents")
    self._collection = self._client.create_collection(
        name="claims_documents",
        metadata={"hnsw:space": "cosine"},
    )

async def delete_document(self, document_id: str) -> bool:
    """Delete a document by ID."""
    self._collection.delete(ids=[document_id])
    return True
```

---

## 📝 Key Takeaways

1. **Vectors** are lists of numbers that represent meaning
2. **Embeddings** convert text to vectors
3. **Similar meanings = similar vectors**
4. **Semantic search** finds documents by meaning, not keywords
5. **ChromaDB** stores and searches vectors efficiently
6. **Cosine similarity** measures how similar two vectors are
7. **Metadata filtering** narrows down search results

---

## ❓ Practice Questions

1. What is the difference between keyword search and semantic search?
2. Why do we chunk documents before storing them?
3. What does a similarity score of 0.95 mean?
4. How would you find all documents related to "medical expenses" for claim CLM-001?
5. Why is cosine similarity a good measure for text embeddings?

---

## 💻 Code Exercise

Try adding a document and searching for it:

```python
from app.vectorstore.chroma_store import ChromaVectorStore
from app.vectorstore.base import VectorDocument

# Create store
store = ChromaVectorStore()
await store._ensure_initialized()

# Add a document
doc = VectorDocument(
    id="test-doc-1",
    content="The vehicle sustained significant damage to the front bumper.",
    metadata={"claim_id": "CLM-TEST", "source": "test"},
)
await store.add_documents([doc])

# Search for it
results = await store.search_by_text("car bumper damage", top_k=3)
for result in results:
    print(f"Score: {result.score}, Content: {result.document.content[:50]}...")
```

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `app/vectorstore/base.py` | Abstract interface for vector stores |
| `app/vectorstore/chroma_store.py` | ChromaDB implementation |
| `app/services/rag.py` | Generates embeddings (via OpenAI) |

---

[← Previous: Database](../section-07-database/README.md) | [Next: OCR & Documents →](../section-09-ocr-documents/README.md)
