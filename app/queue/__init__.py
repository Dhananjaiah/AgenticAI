"""
Message queue module for event-driven processing.
"""

from app.queue.kafka_client import KafkaClient, KafkaConsumer, KafkaProducer

__all__ = ["KafkaClient", "KafkaProducer", "KafkaConsumer"]
