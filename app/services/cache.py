"""
Redis-backed caching service.

Provides caching functionality for:
- Claim bundles for hot claimIds/policyIds
- Time-based and event-based invalidation
"""

import json
from datetime import datetime
from typing import Any

import redis.asyncio as redis
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.observability.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class CacheService:
    """Redis-based caching service for claim bundles and other data."""

    def __init__(self) -> None:
        """Initialize the cache service."""
        self._client: redis.Redis | None = None
        self._stats = {"hits": 0, "misses": 0}

    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(
                settings.redis.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def ping(self) -> bool:
        """
        Check Redis connectivity.

        Returns:
            bool: True if Redis is reachable
        """
        try:
            client = await self._get_client()
            await client.ping()
            return True
        except Exception as e:
            logger.warning("Redis ping failed", error=str(e))
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def get(self, key: str) -> Any | None:
        """
        Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (defaults to config value)

        Returns:
            bool: True if successful
        """
        try:
            client = await self._get_client()
            ttl = ttl or settings.redis.cache_ttl_seconds
            serialized = json.dumps(value, default=str)
            await client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete a key from cache.

        Args:
            key: Cache key

        Returns:
            bool: True if successful
        """
        try:
            client = await self._get_client()
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False

    async def invalidate_claim(self, claim_id: str) -> bool:
        """
        Invalidate all cache entries for a claim.

        Args:
            claim_id: Claim ID to invalidate

        Returns:
            bool: True if successful
        """
        try:
            client = await self._get_client()
            # Find and delete all keys matching the claim
            pattern = f"claim:{claim_id}:*"
            async for key in client.scan_iter(match=pattern):
                await client.delete(key)

            # Also delete the main claim bundle key
            await client.delete(f"claim_bundle:{claim_id}")
            logger.info("Cache invalidated for claim", claim_id=claim_id)
            return True
        except Exception as e:
            logger.warning("Cache invalidation failed", claim_id=claim_id, error=str(e))
            return False

    async def invalidate_policy(self, policy_id: str) -> bool:
        """
        Invalidate all cache entries for a policy.

        Args:
            policy_id: Policy ID to invalidate

        Returns:
            bool: True if successful
        """
        try:
            client = await self._get_client()
            pattern = f"policy:{policy_id}:*"
            async for key in client.scan_iter(match=pattern):
                await client.delete(key)
            logger.info("Cache invalidated for policy", policy_id=policy_id)
            return True
        except Exception as e:
            logger.warning("Cache invalidation failed", policy_id=policy_id, error=str(e))
            return False

    async def get_claim_bundle(self, claim_id: str) -> dict | None:
        """
        Get cached claim bundle.

        Args:
            claim_id: Claim ID

        Returns:
            Cached bundle or None
        """
        return await self.get(f"claim_bundle:{claim_id}")

    async def set_claim_bundle(
        self,
        claim_id: str,
        bundle: dict,
        ttl: int | None = None,
    ) -> bool:
        """
        Cache a claim bundle.

        Args:
            claim_id: Claim ID
            bundle: Bundle data to cache
            ttl: Time to live in seconds

        Returns:
            bool: True if successful
        """
        return await self.set(f"claim_bundle:{claim_id}", bundle, ttl)

    async def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            dict: Cache statistics including hit rate
        """
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate,
        }

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
