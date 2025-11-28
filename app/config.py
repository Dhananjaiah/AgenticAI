"""
Configuration management for Agentic-AI Insurance Claims Architecture.

Uses pydantic-settings for environment variable loading with validation.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    database_url: str = Field(
        default="postgresql+asyncpg://claims_user:claims_password@localhost:5432/claims_db",
        alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://claims_user:claims_password@localhost:5432/claims_db",
        alias="DATABASE_URL_SYNC",
    )
    metadata_database_url: str = Field(
        default="postgresql+asyncpg://claims_user:claims_password@localhost:5432/claims_metadata_db",
        alias="METADATA_DATABASE_URL",
    )


class RedisSettings(BaseSettings):
    """Redis cache configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    cache_ttl_seconds: int = Field(default=300, alias="CACHE_TTL_SECONDS")


class KafkaSettings(BaseSettings):
    """Kafka message queue configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    bootstrap_servers: str = Field(
        default="localhost:9092", alias="KAFKA_BOOTSTRAP_SERVERS"
    )
    topic_claims: str = Field(default="claims-events", alias="KAFKA_TOPIC_CLAIMS")
    topic_indexing: str = Field(default="indexing-events", alias="KAFKA_TOPIC_INDEXING")
    consumer_group: str = Field(default="claims-processor", alias="KAFKA_CONSUMER_GROUP")


class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    endpoint: str = Field(
        default="https://your-resource.openai.azure.com/",
        alias="AZURE_OPENAI_ENDPOINT",
    )
    api_key: str = Field(default="", alias="AZURE_OPENAI_API_KEY")
    deployment_name: str = Field(default="gpt-4", alias="AZURE_OPENAI_DEPLOYMENT_NAME")
    embedding_deployment: str = Field(
        default="text-embedding-ada-002", alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
    )
    api_version: str = Field(
        default="2024-02-15-preview", alias="AZURE_OPENAI_API_VERSION"
    )


class LLMSettings(BaseSettings):
    """LLM mode configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    mode: Literal["azure", "openai", "stub"] = Field(default="stub", alias="LLM_MODE")


class VectorDBSettings(BaseSettings):
    """Vector database configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    db_type: Literal["chroma", "faiss"] = Field(default="chroma", alias="VECTOR_DB_TYPE")
    chroma_persist_directory: str = Field(
        default="./data/chroma", alias="CHROMA_PERSIST_DIRECTORY"
    )
    chroma_collection_name: str = Field(
        default="claims_documents", alias="CHROMA_COLLECTION_NAME"
    )


class OCRSettings(BaseSettings):
    """OCR engine configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    engine: Literal["tesseract", "azure_form_recognizer"] = Field(
        default="tesseract", alias="OCR_ENGINE"
    )
    tesseract_cmd: str = Field(default="/usr/bin/tesseract", alias="TESSERACT_CMD")
    azure_form_recognizer_endpoint: str = Field(
        default="", alias="AZURE_FORM_RECOGNIZER_ENDPOINT"
    )
    azure_form_recognizer_key: str = Field(
        default="", alias="AZURE_FORM_RECOGNIZER_KEY"
    )


class SharePointSettings(BaseSettings):
    """SharePoint configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    tenant_id: str = Field(default="", alias="SHAREPOINT_TENANT_ID")
    client_id: str = Field(default="", alias="SHAREPOINT_CLIENT_ID")
    client_secret: str = Field(default="", alias="SHAREPOINT_CLIENT_SECRET")
    site_url: str = Field(default="", alias="SHAREPOINT_SITE_URL")
    local_path: str = Field(default="./data/sharepoint", alias="LOCAL_SHAREPOINT_PATH")


class BlobStorageSettings(BaseSettings):
    """Blob storage configuration settings for Azure and AWS."""

    model_config = SettingsConfigDict(env_prefix="")

    azure_connection_string: str = Field(
        default="", alias="AZURE_BLOB_CONNECTION_STRING"
    )
    azure_container_name: str = Field(
        default="claims-documents", alias="AZURE_BLOB_CONTAINER_NAME"
    )
    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket_name: str = Field(default="claims-documents", alias="S3_BUCKET_NAME")
    local_path: str = Field(default="./data/blobs", alias="LOCAL_BLOB_PATH")


class SecuritySettings(BaseSettings):
    """API security configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    api_key_secret: str = Field(
        default="your-super-secret-api-key-change-in-production",
        alias="API_KEY_SECRET",
    )
    jwt_secret_key: str = Field(
        default="your-jwt-secret-key-change-in-production", alias="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiration_minutes: int = Field(default=30, alias="JWT_EXPIRATION_MINUTES")


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: Literal["json", "text"] = Field(default="json", alias="LOG_FORMAT")


class ObservabilitySettings(BaseSettings):
    """Observability configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_service_name: str = Field(
        default="agentic-ai-claims", alias="OTEL_SERVICE_NAME"
    )
    otel_exporter_endpoint: str = Field(
        default="http://localhost:4317", alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )


class DeduplicationSettings(BaseSettings):
    """Deduplication engine configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    similarity_threshold: float = Field(
        default=0.85, alias="DEDUPE_SIMILARITY_THRESHOLD"
    )
    exact_match_fields: str = Field(
        default="claim_id,policy_id", alias="DEDUPE_EXACT_MATCH_FIELDS"
    )


class RAGSettings(BaseSettings):
    """RAG retrieval configuration settings."""

    model_config = SettingsConfigDict(env_prefix="")

    top_k: int = Field(default=5, alias="RAG_TOP_K")
    chunk_size: int = Field(default=1000, alias="RAG_CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="RAG_CHUNK_OVERLAP")


class Settings(BaseSettings):
    """Main application settings aggregating all configuration groups."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application info
    app_name: str = "Agentic-AI Insurance Claims"
    app_version: str = "0.1.0"
    debug: bool = False

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    azure_openai: AzureOpenAISettings = Field(default_factory=AzureOpenAISettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    vectordb: VectorDBSettings = Field(default_factory=VectorDBSettings)
    ocr: OCRSettings = Field(default_factory=OCRSettings)
    sharepoint: SharePointSettings = Field(default_factory=SharePointSettings)
    blob_storage: BlobStorageSettings = Field(default_factory=BlobStorageSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    deduplication: DeduplicationSettings = Field(default_factory=DeduplicationSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)


@lru_cache
def get_settings() -> Settings:
    """
    Get application settings with caching.

    Returns:
        Settings: Cached settings instance
    """
    return Settings()
