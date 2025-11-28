"""
Message queue module for event-driven processing.
"""

from app.queue.kafka_client import KafkaClient, KafkaProducer, KafkaConsumer

__all__ = ["KafkaClient", "KafkaProducer", "KafkaConsumer"]
