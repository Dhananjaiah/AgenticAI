# Section 11: Background Workers

## 🎯 Learning Goals
By the end of this section, you will understand:
- What background workers are
- Why we need asynchronous processing
- How our indexer worker works
- How Kafka message queues work

---

## 📺 Video Transcript

### Welcome to Background Workers!

Hello everyone! In this section, we'll learn about background workers - programs that run behind the scenes to do work that shouldn't block the main application.

### Why Background Workers?

Imagine you're uploading a 50MB PDF document. Would you want to:

**Option A (Bad):**
- Wait 2 minutes while the server processes it
- Stare at a loading spinner
- Hope your connection doesn't drop

**Option B (Good):**
- Upload the file instantly
- Get a message "Processing started!"
- Continue working while processing happens in background

Background workers enable Option B!

### What Tasks Run in Background?

In our system:
1. **OCR Processing** - Reading text from images (slow!)
2. **Embedding Generation** - Creating vectors for search
3. **Document Indexing** - Adding to vector database
4. **Claim Refresh** - Re-fetching from all sources
5. **Duplicate Detection** - Comparing many documents

These tasks can take seconds to minutes. We don't want users waiting!

### Message Queues

Background workers use **message queues** to receive work:

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   API       │ ──────► │   Queue     │ ──────► │   Worker    │
│  (sends job)│         │  (stores)   │         │  (processes)│
└─────────────┘         └─────────────┘         └─────────────┘
```

Think of it like a restaurant:
- Waiter (API) takes order
- Order goes to kitchen queue
- Cook (Worker) processes when ready

### Kafka Message Queue

We use **Apache Kafka** as our message queue:

```python
# In app/queue/kafka_client.py

class KafkaProducer:
    """Sends messages to Kafka."""
    
    async def send(self, topic: str, message: dict):
        # Send to Kafka
        pass

class KafkaConsumer:
    """Receives messages from Kafka."""
    
    async def consume_batch(self, max_messages: int = 10):
        # Get messages from Kafka
        pass
```

**Why Kafka?**
- Handles millions of messages
- Messages are persisted (won't lose them)
- Multiple workers can share the load

### The Indexer Worker

Open `workers/indexer_worker.py`:

```python
class IndexerWorker:
    """
    Worker for processing indexing jobs.
    
    Handles:
    - Document indexing events
    - OCR processing
    - Embedding generation
    - Vector store updates
    """
    
    def __init__(self):
        self._running = False
        self._consumer = KafkaConsumer([settings.kafka.topic_indexing])
        self._indexer = IndexerService()
        self._ocr = OCRService()
        self._vector_store = ChromaVectorStore()
        
        # Register handlers for different event types
        self._consumer.register_handler("index", self._handle_index_event)
        self._consumer.register_handler("reindex", self._handle_reindex_event)
        self._consumer.register_handler("delete", self._handle_delete_event)
```

### Worker Lifecycle

```python
async def start(self):
    """Start the worker."""
    self._running = True
    logger.info("Indexer worker starting")
    
    # Set up signal handlers (for graceful shutdown)
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, self._handle_shutdown)
    
    try:
        while self._running:
            # Get a batch of messages
            messages = await self._consumer.consume_batch(
                max_messages=10,
                timeout_ms=1000,
            )
            
            if messages:
                logger.info("Processed batch", count=len(messages))
            else:
                # No messages - wait a bit
                await asyncio.sleep(1)
                
    except Exception as e:
        logger.error("Worker error", error=str(e))
        raise
    finally:
        await self._cleanup()
```

**The worker loop:**
1. Check for messages
2. Process any found
3. If none, wait briefly
4. Repeat until shutdown

### Handling Index Events

When a new document needs indexing:

```python
async def _handle_index_event(self, event: dict):
    """Handle a document index event."""
    document_id = event.get("document_id")
    source_type = event.get("source_type")
    data = event.get("data", {})
    
    logger.info("Processing index event", document_id=document_id)
    
    try:
        file_path = data.get("file_path")
        if not file_path:
            logger.warning("No file path in event")
            return
        
        # Run indexing
        result = await self._indexer.index_document(
            document_id=document_id,
            file_path=file_path,
            claim_id=data.get("claim_id"),
            policy_id=data.get("policy_id"),
        )
        
        if result.get("success"):
            # Store in vector DB
            ocr_text = result.get("ocr_text")
            if ocr_text:
                await self._store_in_vector_db(
                    document_id, 
                    ocr_text, 
                    data
                )
            logger.info("Document indexed", document_id=document_id)
        else:
            logger.error("Indexing failed", error=result.get("error"))
            
    except Exception as e:
        logger.error("Index event failed", document_id=document_id, error=str(e))
```

### Storing in Vector Database

```python
async def _store_in_vector_db(
    self,
    document_id: str,
    text: str,
    metadata: dict,
):
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
    
    if documents:
        await self._vector_store.add_documents(documents)
        logger.info("Stored chunks", document_id=document_id, chunks=len(documents))
```

### Reindex and Delete Events

```python
async def _handle_reindex_event(self, event: dict):
    """Handle a document reindex event."""
    document_id = event.get("document_id")
    
    # Delete old entries
    await self._vector_store.delete_by_metadata({"document_id": document_id})
    
    # Re-run indexing
    await self._handle_index_event(event)

async def _handle_delete_event(self, event: dict):
    """Handle a document delete event."""
    document_id = event.get("document_id")
    
    deleted = await self._vector_store.delete_by_metadata(
        {"document_id": document_id}
    )
    logger.info("Deleted from vector store", document_id=document_id, count=deleted)
```

### Graceful Shutdown

Workers should shut down cleanly:

```python
def _handle_shutdown(self):
    """Handle shutdown signal."""
    logger.info("Shutdown signal received")
    self._running = False  # This stops the main loop

async def _cleanup(self):
    """Cleanup resources."""
    await self._consumer.close()
    await self._vector_store.close()
    logger.info("Indexer worker cleaned up")
```

**Why graceful shutdown matters:**
- Finish processing current message
- Don't lose work in progress
- Close connections properly

### Running the Worker

```python
# Entry point

async def run_worker():
    """Run the indexer worker."""
    worker = IndexerWorker()
    await worker.start()

def main():
    """Entry point for the indexer worker."""
    logger.info("Starting indexer worker")
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Indexer worker interrupted")
    except Exception as e:
        logger.error("Indexer worker failed", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**To run:**
```bash
python -m workers.indexer_worker
```

### The OCR Worker

There's also an OCR-specific worker (`workers/ocr_worker.py`):

```python
class OCRWorker:
    """
    Worker for OCR processing jobs.
    
    Handles:
    - Image OCR requests
    - PDF OCR requests
    - Entity extraction
    """
    
    async def _handle_ocr_event(self, event: dict):
        document_id = event.get("document_id")
        file_path = event.get("file_path")
        
        # Run OCR
        result = await self._ocr.process_file(file_path)
        
        # Store result in database
        await self._update_document(
            document_id,
            ocr_text=result.text,
            ocr_confidence=result.confidence,
            extracted_entities=result.extracted_entities,
        )
```

### Scaling Workers

Need more processing power? Just run more workers!

```bash
# Run 3 indexer workers
python -m workers.indexer_worker &
python -m workers.indexer_worker &
python -m workers.indexer_worker &
```

Kafka automatically distributes messages across workers!

With Docker:
```bash
docker-compose up -d --scale indexer-worker=3
```

### Monitoring Workers

Add logging and metrics:

```python
# Track processing time
start_time = time.time()
await process_document(...)
duration = time.time() - start_time
logger.info("Processed document", duration_ms=duration * 1000)

# Track queue size
queue_size = await consumer.get_queue_size()
metrics.gauge("queue_size", queue_size)
```

### Event Schema

Our events follow a consistent format:

```python
{
    "event_type": "index",           # What to do
    "document_id": "doc-123",        # Which document
    "source_type": "sharepoint",     # Where it came from
    "timestamp": "2024-01-15T...",   # When sent
    "data": {
        "file_path": "/path/to/file.pdf",
        "claim_id": "CLM-001",
        "policy_id": "POL-001",
    }
}
```

---

## 📝 Key Takeaways

1. **Background workers** process jobs asynchronously
2. **Message queues** (Kafka) reliably deliver jobs to workers
3. **Batch processing** is more efficient than one-at-a-time
4. **Graceful shutdown** prevents data loss
5. **Multiple workers** can scale horizontally
6. **Event handlers** route different job types

---

## ❓ Practice Questions

1. Why don't we process documents synchronously?
2. What happens if a worker crashes mid-processing?
3. How does Kafka distribute work across multiple workers?
4. What is graceful shutdown?
5. How would you add a new event type to the worker?

---

## 💻 Code Exercise

Add a batch index handler:

```python
async def _handle_batch_index_event(self, event: dict):
    """Handle indexing multiple documents at once."""
    documents = event.get("data", {}).get("documents", [])
    
    logger.info("Batch indexing", count=len(documents))
    
    for doc in documents:
        # Create individual event for each document
        single_event = {
            "document_id": doc.get("id"),
            "source_type": doc.get("source_type"),
            "data": doc,
        }
        await self._handle_index_event(single_event)
    
    logger.info("Batch complete", count=len(documents))
```

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `workers/indexer_worker.py` | Document indexing worker |
| `workers/ocr_worker.py` | OCR processing worker |
| `app/queue/kafka_client.py` | Kafka producer/consumer |
| `infra/docker-compose.yml` | Kafka container setup |

---

[← Previous: Caching](../section-10-caching/README.md) | [Next: Configuration →](../section-12-configuration/README.md)
