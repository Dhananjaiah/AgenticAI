# Section 10: Caching and Performance

## 🎯 Learning Goals
By the end of this section, you will understand:
- What caching is and why it's important
- How Redis works
- How we cache claim bundles
- Cache invalidation strategies

---

## 📺 Video Transcript

### Welcome to the Caching Section!

Hello everyone! In this section, we're going to learn about caching - one of the most important techniques for making applications fast.

### What is Caching?

**Caching** is storing data so you don't have to recompute it every time.

**Without cache:**
```
Request #1: "Give me claim CLM-001"
- Query database (100ms)
- Query SharePoint (200ms)  
- Query Blob storage (150ms)
- Deduplicate (50ms)
- Build bundle (50ms)
Total: 550ms

Request #2: "Give me claim CLM-001" (same claim!)
- Query database (100ms)
- Query SharePoint (200ms)
... same work again!
Total: 550ms
```

**With cache:**
```
Request #1: "Give me claim CLM-001"
- Query database (100ms)
- Query SharePoint (200ms)
- Build bundle (50ms)
- Save to cache (5ms)
Total: 555ms

Request #2: "Give me claim CLM-001"
- Check cache → Found!
- Return cached bundle (5ms)
Total: 5ms! 🚀
```

That's a 99% improvement!

### What is Redis?

Redis is an **in-memory database**. That means it stores data in RAM, not on a hard drive.

**Why RAM?**
- Hard drive read: ~10ms
- RAM read: ~0.1ms (100x faster!)

Redis is perfect for caching because:
1. Super fast (in-memory)
2. Simple key-value storage
3. Automatic expiration
4. Handles millions of operations per second

### Our Cache Service

Open `app/services/cache.py`:

```python
import redis.asyncio as redis
from tenacity import retry, stop_after_attempt, wait_exponential

class CacheService:
    """Redis-based caching service for claim bundles and other data."""
    
    def __init__(self):
        self._client = None
        self._stats = {"hits": 0, "misses": 0}
    
    async def _get_client(self):
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(
                settings.redis.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client
```

### Basic Cache Operations

**Setting a value:**
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential())
async def set(
    self,
    key: str,
    value: Any,
    ttl: int = None,  # Time to live (seconds)
) -> bool:
    """Set a value in cache."""
    try:
        client = await self._get_client()
        ttl = ttl or settings.redis.cache_ttl_seconds  # Default: 300 (5 min)
        
        # Convert Python object to JSON
        serialized = json.dumps(value, default=str)
        
        # Store with expiration
        await client.setex(key, ttl, serialized)
        return True
    except Exception as e:
        logger.warning("Cache set failed", key=key, error=str(e))
        return False
```

**Getting a value:**
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential())
async def get(self, key: str) -> Any | None:
    """Get a value from cache."""
    try:
        client = await self._get_client()
        value = await client.get(key)
        
        if value:
            self._stats["hits"] += 1
            return json.loads(value)
        
        self._stats["misses"] += 1
        return None
    except Exception as e:
        logger.warning("Cache get failed", key=key, error=str(e))
        return None
```

**What's `@retry`?**
If Redis is temporarily unavailable, we retry a few times before giving up. This makes our app more resilient!

### Caching Claim Bundles

```python
async def get_claim_bundle(self, claim_id: str) -> dict | None:
    """Get cached claim bundle."""
    return await self.get(f"claim_bundle:{claim_id}")

async def set_claim_bundle(
    self,
    claim_id: str,
    bundle: dict,
    ttl: int = None,
) -> bool:
    """Cache a claim bundle."""
    return await self.set(f"claim_bundle:{claim_id}", bundle, ttl)
```

**Key naming convention:**
```
claim_bundle:CLM-2024-001
claim:CLM-2024-001:documents
policy:POL-001:claims
```

Using colons `:` groups related keys together!

### Cache Invalidation

When data changes, we need to clear the old cache:

```python
async def invalidate_claim(self, claim_id: str) -> bool:
    """Invalidate all cache entries for a claim."""
    try:
        client = await self._get_client()
        
        # Find all keys for this claim
        pattern = f"claim:{claim_id}:*"
        async for key in client.scan_iter(match=pattern):
            await client.delete(key)
        
        # Also delete the main bundle
        await client.delete(f"claim_bundle:{claim_id}")
        
        logger.info("Cache invalidated for claim", claim_id=claim_id)
        return True
    except Exception as e:
        logger.warning("Cache invalidation failed", claim_id=claim_id)
        return False
```

### When to Invalidate?

1. **When data changes:**
   - Claim status updated
   - New document uploaded
   - Payment processed

2. **When refresh is triggered:**
   ```python
   # In claims API
   async def refresh_claim(claim_id: str):
       # Mark bundle as stale
       await cache.invalidate_claim(claim_id)
       # Re-fetch from all sources
       ...
   ```

3. **Automatically (TTL):**
   - After 5 minutes, cache expires
   - Next request gets fresh data

### Cache Statistics

Track how well your cache is working:

```python
async def get_stats(self) -> dict:
    """Get cache statistics."""
    total = self._stats["hits"] + self._stats["misses"]
    hit_rate = self._stats["hits"] / total if total > 0 else 0.0
    
    return {
        "hits": self._stats["hits"],
        "misses": self._stats["misses"],
        "hit_rate": hit_rate,  # 0.9 = 90% of requests hit cache
    }
```

**Good hit rates:**
- 90%+ = Excellent
- 70-90% = Good
- Below 70% = Review your caching strategy

### Health Check

Verify Redis is working:

```python
async def ping(self) -> bool:
    """Check Redis connectivity."""
    try:
        client = await self._get_client()
        await client.ping()
        return True
    except Exception as e:
        logger.warning("Redis ping failed", error=str(e))
        return False
```

This is called during startup and in `/health` endpoint.

### Using Cache in API

Here's how the claims API uses cache:

```python
# In app/api/claims.py

async def get_claim_bundle(
    claim_id: str,
    force_refresh: bool = False,
    cache: CacheService = Depends(get_cache),
):
    """Get claim bundle with caching."""
    
    # 1. Check cache first (unless force refresh)
    if not force_refresh:
        cached = await cache.get_claim_bundle(claim_id)
        if cached:
            logger.info("Cache hit", claim_id=claim_id)
            return cached
    
    logger.info("Cache miss", claim_id=claim_id)
    
    # 2. Build bundle from scratch
    bundle = await orchestrator.build_claim_bundle(claim_id)
    
    # 3. Store in cache for next time
    await cache.set_claim_bundle(claim_id, bundle)
    
    return bundle
```

### Cache Warming

Sometimes you want to pre-fill the cache:

```python
async def warm_cache(top_n: int = 100):
    """Pre-cache frequently accessed claims."""
    
    # Get most accessed claims
    top_claims = await get_frequently_accessed_claims(top_n)
    
    for claim_id in top_claims:
        bundle = await orchestrator.build_claim_bundle(claim_id)
        await cache.set_claim_bundle(claim_id, bundle)
    
    logger.info(f"Warmed cache with {len(top_claims)} claims")
```

This is useful after deploying new code or restarting the system.

### Best Practices

1. **Don't cache everything**
   - Cache things that are expensive to compute
   - Cache things that are accessed frequently
   - Don't cache things that change constantly

2. **Choose TTL wisely**
   - Too short: More cache misses
   - Too long: Stale data
   - Our default: 5 minutes (good balance)

3. **Handle cache failures gracefully**
   ```python
   bundle = await cache.get_claim_bundle(claim_id)
   if bundle is None:
       # Cache miss OR Redis down - both handled same way
       bundle = await build_bundle_from_scratch(claim_id)
   ```

4. **Monitor hit rates**
   - Add to dashboards
   - Alert if rate drops significantly

---

## 📝 Key Takeaways

1. **Caching** stores computed results for fast retrieval
2. **Redis** is an in-memory database (super fast!)
3. **TTL** (Time to Live) automatically expires cache entries
4. **Invalidation** clears cache when data changes
5. **Hit rate** measures cache effectiveness
6. **Always handle cache failures gracefully** - app should work even if Redis is down

---

## ❓ Practice Questions

1. Why is Redis faster than a traditional database?
2. What does TTL stand for and what does it do?
3. When should you invalidate a cache entry?
4. What is a good cache hit rate?
5. What happens if Redis is unavailable?

---

## 💻 Code Exercise

Add a method to cache policy data:

```python
async def get_policy_data(self, policy_id: str) -> dict | None:
    """Get cached policy data."""
    return await self.get(f"policy:{policy_id}")

async def set_policy_data(
    self,
    policy_id: str,
    data: dict,
    ttl: int = None,
) -> bool:
    """Cache policy data."""
    return await self.set(f"policy:{policy_id}", data, ttl)

async def invalidate_policy(self, policy_id: str) -> bool:
    """Invalidate all cache entries for a policy."""
    # Your code here - follow the invalidate_claim pattern!
```

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `app/services/cache.py` | Redis cache service |
| `app/config.py` | Redis configuration (url, TTL) |
| `infra/docker-compose.yml` | Redis container setup |

---

[← Previous: OCR](../section-09-ocr-documents/README.md) | [Next: Workers →](../section-11-workers/README.md)
