"""
Kafka client abstraction for message queue operations.

Provides producer and consumer functionality for:
- Claim events (created, updated)
- Indexing events
- Document processing events
"""

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.config import get_settings
from app.observability.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class KafkaProducer:
    """
    Kafka producer for publishing messages.

    Abstracts aiokafka producer with error handling and serialization.
    """

    def __init__(self) -> None:
        """Initialize Kafka producer."""
        self._producer = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure producer is initialized."""
        if self._initialized:
            return

        try:
            from aiokafka import AIOKafkaProducer

            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            )
            await self._producer.start()
            self._initialized = True
            logger.info("Kafka producer initialized")
        except Exception as e:
            logger.warning("Kafka producer initialization failed", error=str(e))
            # Continue without Kafka for local development
            self._producer = None

    async def publish(
        self,
        topic: str,
        message: dict[str, Any],
        key: str | None = None,
    ) -> bool:
        """
        Publish a message to a topic.

        Args:
            topic: Topic name
            message: Message payload
            key: Optional message key

        Returns:
            bool: True if published successfully
        """
        await self._ensure_initialized()

        if not self._producer:
            logger.debug("Kafka not available, message not published", topic=topic)
            return False

        try:
            key_bytes = key.encode("utf-8") if key else None
            await self._producer.send_and_wait(
                topic,
                value=message,
                key=key_bytes,
            )
            logger.debug("Message published", topic=topic, key=key)
            return True
        except Exception as e:
            logger.error("Failed to publish message", topic=topic, error=str(e))
            return False

    async def publish_claim_event(
        self,
        claim_id: str,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> bool:
        """
        Publish a claim event.

        Args:
            claim_id: Claim ID
            event_type: Event type (created, updated, etc.)
            data: Additional event data

        Returns:
            bool: True if published
        """
        message = {
            "claim_id": claim_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {},
        }
        return await self.publish(
            settings.kafka.topic_claims,
            message,
            key=claim_id,
        )

    async def publish_indexing_event(
        self,
        document_id: str,
        event_type: str,
        source_type: str,
        data: dict[str, Any] | None = None,
    ) -> bool:
        """
        Publish an indexing event.

        Args:
            document_id: Document ID
            event_type: Event type (index, reindex, delete)
            source_type: Source type (sql, sharepoint, blob)
            data: Additional event data

        Returns:
            bool: True if published
        """
        message = {
            "document_id": document_id,
            "event_type": event_type,
            "source_type": source_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {},
        }
        return await self.publish(
            settings.kafka.topic_indexing,
            message,
            key=document_id,
        )

    async def close(self) -> None:
        """Close the producer connection."""
        if self._producer:
            await self._producer.stop()
            self._producer = None
            self._initialized = False
            logger.info("Kafka producer closed")


class KafkaConsumer:
    """
    Kafka consumer for processing messages.

    Abstracts aiokafka consumer with error handling and deserialization.
    """

    def __init__(self, topics: list[str] | None = None) -> None:
        """
        Initialize Kafka consumer.

        Args:
            topics: Topics to subscribe to
        """
        self._consumer = None
        self._initialized = False
        self._topics = topics or [
            settings.kafka.topic_claims,
            settings.kafka.topic_indexing,
        ]
        self._handlers: dict[str, Callable] = {}

    async def _ensure_initialized(self) -> None:
        """Ensure consumer is initialized."""
        if self._initialized:
            return

        try:
            from aiokafka import AIOKafkaConsumer

            self._consumer = AIOKafkaConsumer(
                *self._topics,
                bootstrap_servers=settings.kafka.bootstrap_servers,
                group_id=settings.kafka.consumer_group,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="earliest",
            )
            await self._consumer.start()
            self._initialized = True
            logger.info("Kafka consumer initialized", topics=self._topics)
        except Exception as e:
            logger.warning("Kafka consumer initialization failed", error=str(e))
            self._consumer = None

    def register_handler(
        self,
        event_type: str,
        handler: Callable,
    ) -> None:
        """
        Register a handler for an event type.

        Args:
            event_type: Event type to handle
            handler: Handler function
        """
        self._handlers[event_type] = handler
        logger.info("Handler registered", event_type=event_type)

    async def consume(self) -> None:
        """
        Start consuming messages.

        Runs indefinitely, processing messages with registered handlers.
        """
        await self._ensure_initialized()

        if not self._consumer:
            logger.warning("Kafka not available, consume loop not started")
            return

        try:
            async for message in self._consumer:
                await self._process_message(message)
        except Exception as e:
            logger.error("Consumer error", error=str(e))
            raise

    async def consume_batch(
        self,
        max_messages: int = 100,
        timeout_ms: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Consume a batch of messages.

        Args:
            max_messages: Maximum messages to consume
            timeout_ms: Timeout in milliseconds

        Returns:
            list: Consumed messages
        """
        await self._ensure_initialized()

        if not self._consumer:
            return []

        try:
            messages = []
            batch = await self._consumer.getmany(
                timeout_ms=timeout_ms,
                max_records=max_messages,
            )

            for topic_partition, records in batch.items():
                for record in records:
                    messages.append(record.value)
                    await self._process_message(record)

            return messages
        except Exception as e:
            logger.error("Batch consume error", error=str(e))
            return []

    async def _process_message(self, message: Any) -> None:
        """Process a single message."""
        try:
            value = message.value
            event_type = value.get("event_type")

            if event_type and event_type in self._handlers:
                handler = self._handlers[event_type]
                await handler(value)
                logger.debug("Message processed", event_type=event_type)
            else:
                logger.debug("No handler for event type", event_type=event_type)
        except Exception as e:
            logger.error("Message processing failed", error=str(e))

    async def close(self) -> None:
        """Close the consumer connection."""
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
            self._initialized = False
            logger.info("Kafka consumer closed")


class KafkaClient:
    """
    Combined Kafka client for producer and consumer operations.

    Provides a unified interface for message queue operations.
    """

    def __init__(self) -> None:
        """Initialize Kafka client."""
        self._producer = KafkaProducer()
        self._consumer: KafkaConsumer | None = None

    @property
    def producer(self) -> KafkaProducer:
        """Get the producer instance."""
        return self._producer

    def get_consumer(self, topics: list[str] | None = None) -> KafkaConsumer:
        """
        Get or create a consumer instance.

        Args:
            topics: Topics to subscribe to

        Returns:
            KafkaConsumer: Consumer instance
        """
        if self._consumer is None:
            self._consumer = KafkaConsumer(topics)
        return self._consumer

    async def publish(
        self,
        topic: str,
        message: dict[str, Any],
        key: str | None = None,
    ) -> bool:
        """
        Publish a message.

        Args:
            topic: Topic name
            message: Message payload
            key: Optional message key

        Returns:
            bool: True if published
        """
        return await self._producer.publish(topic, message, key)

    async def close(self) -> None:
        """Close all connections."""
        await self._producer.close()
        if self._consumer:
            await self._consumer.close()
        logger.info("Kafka client closed")
