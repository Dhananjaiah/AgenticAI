# Section 12: Configuration and Environment

## 🎯 Learning Goals
By the end of this section, you will understand:
- How to configure the application
- What environment variables are
- How to manage different environments (dev/prod)
- Security best practices for configuration

---

## 📺 Video Transcript

### Welcome to Configuration!

Hello everyone! In this section, we'll learn how to configure our application properly. This is crucial for security and flexibility.

### Why Configuration Matters

Imagine you hardcode your database password in the code:

```python
# BAD! Never do this!
DATABASE_URL = "postgresql://admin:SuperSecret123@db.company.com/claims"
```

Problems:
1. Password is visible in Git history forever
2. Can't use different passwords for dev/test/prod
3. Anyone with code access has database access

**Solution: Environment variables!**

### What Are Environment Variables?

Environment variables are settings that exist outside your code:

```bash
# Set in your terminal
export DATABASE_URL="postgresql://user:pass@localhost/db"
export REDIS_URL="redis://localhost:6379"
export LLM_MODE="stub"

# Then run your app
python -m uvicorn app.main:app
```

Your app reads these variables at runtime.

### The .env File

For development, we use a `.env` file:

```bash
# .env file (DO NOT commit to Git!)

# Database
DATABASE_URL=postgresql+asyncpg://claims_user:claims_password@localhost:5432/claims_db

# Redis
REDIS_URL=redis://localhost:6379/0
CACHE_TTL_SECONDS=300

# LLM Mode (stub, azure, openai)
LLM_MODE=stub

# Azure OpenAI (only if LLM_MODE=azure)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
```

**Important:** Add `.env` to `.gitignore`!

### Our Configuration System

Open `app/config.py`:

```python
from pydantic_settings import BaseSettings

class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    database_url: str = Field(
        default="postgresql+asyncpg://...",
        alias="DATABASE_URL",  # Environment variable name
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://...",
        alias="DATABASE_URL_SYNC",
    )
```

**pydantic-settings** automatically:
- Reads from environment variables
- Validates types
- Provides defaults

### Settings Groups

We organize settings into groups:

```python
class Settings(BaseSettings):
    """Main application settings."""
    
    # Application info
    app_name: str = "Agentic-AI Insurance Claims"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # Nested settings groups
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
```

### Accessing Settings

```python
from app.config import get_settings

settings = get_settings()

# Use settings
print(settings.app_name)
print(settings.database.database_url)
print(settings.redis.redis_url)
print(settings.llm.mode)
```

### LRU Cache for Performance

```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    """Get application settings with caching."""
    return Settings()
```

**@lru_cache** means settings are only loaded once, not on every access.

### All Configuration Options

Here's a complete reference:

#### Database Settings
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
DATABASE_URL_SYNC=postgresql+psycopg2://user:pass@host:5432/db
METADATA_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/metadata_db
```

#### Redis Settings
```bash
REDIS_URL=redis://localhost:6379/0
CACHE_TTL_SECONDS=300  # 5 minutes
```

#### Kafka Settings
```bash
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_CLAIMS=claims-events
KAFKA_TOPIC_INDEXING=indexing-events
KAFKA_CONSUMER_GROUP=claims-processor
```

#### LLM Settings
```bash
LLM_MODE=stub  # Options: stub, azure, openai

# For Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

#### Vector DB Settings
```bash
VECTOR_DB_TYPE=chroma  # Options: chroma, faiss
CHROMA_PERSIST_DIRECTORY=./data/chroma
CHROMA_COLLECTION_NAME=claims_documents
```

#### OCR Settings
```bash
OCR_ENGINE=tesseract  # Options: tesseract, azure_form_recognizer
TESSERACT_CMD=/usr/bin/tesseract

# For Azure Form Recognizer
AZURE_FORM_RECOGNIZER_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_FORM_RECOGNIZER_KEY=your-key
```

#### SharePoint Settings
```bash
# For production
SHAREPOINT_TENANT_ID=your-tenant-id
SHAREPOINT_CLIENT_ID=your-client-id
SHAREPOINT_CLIENT_SECRET=your-client-secret
SHAREPOINT_SITE_URL=https://your-org.sharepoint.com/sites/claims

# For local development
LOCAL_SHAREPOINT_PATH=./data/sharepoint
```

#### Blob Storage Settings
```bash
# For Azure
AZURE_BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
AZURE_BLOB_CONTAINER_NAME=claims-documents

# For AWS S3
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
S3_BUCKET_NAME=claims-documents

# For local development
LOCAL_BLOB_PATH=./data/blobs
```

#### Security Settings
```bash
API_KEY_SECRET=your-super-secret-api-key
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=30
```

#### RAG Settings
```bash
RAG_TOP_K=5          # How many chunks to retrieve
RAG_CHUNK_SIZE=1000  # Characters per chunk
RAG_CHUNK_OVERLAP=200  # Overlap between chunks
```

#### Deduplication Settings
```bash
DEDUPE_SIMILARITY_THRESHOLD=0.85
DEDUPE_EXACT_MATCH_FIELDS=claim_id,policy_id
```

#### Logging Settings
```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json  # json, text
```

### Environment-Specific Configs

Create different .env files:

```
.env.development    # For local development
.env.staging        # For staging environment
.env.production     # For production (never in Git!)
```

Load the right one:
```bash
# Linux/Mac
export ENV_FILE=.env.production
python -m uvicorn app.main:app
```

### Type Validation

pydantic validates settings automatically:

```python
class RAGSettings(BaseSettings):
    top_k: int = Field(default=5, alias="RAG_TOP_K")
    chunk_size: int = Field(default=1000, alias="RAG_CHUNK_SIZE")
```

If you set `RAG_TOP_K=five` (string instead of number), you get an error at startup!

### Literal Types for Options

```python
class LLMSettings(BaseSettings):
    mode: Literal["azure", "openai", "stub"] = Field(default="stub", alias="LLM_MODE")
```

Only "azure", "openai", or "stub" are allowed. Anything else = error.

### Security Best Practices

1. **Never commit secrets to Git**
   ```gitignore
   # .gitignore
   .env
   .env.*
   !.env.example
   ```

2. **Use .env.example as template**
   ```bash
   # .env.example (safe to commit)
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
   AZURE_OPENAI_API_KEY=<your-azure-openai-api-key>
   ```

3. **Use secrets managers in production**
   - AWS Secrets Manager
   - Azure Key Vault
   - HashiCorp Vault

4. **Rotate secrets regularly**

5. **Different secrets per environment**
   - Dev, staging, production all have different credentials

### Docker Configuration

In Docker, set environment variables in docker-compose.yml:

```yaml
services:
  api:
    build: .
    environment:
      - DATABASE_URL=postgresql+asyncpg://claims_user:password@postgres:5432/claims_db
      - REDIS_URL=redis://redis:6379/0
      - LLM_MODE=stub
```

Or use an env_file:
```yaml
services:
  api:
    build: .
    env_file:
      - .env.production
```

---

## 📝 Key Takeaways

1. **Environment variables** keep secrets out of code
2. **.env files** make local development easy
3. **pydantic-settings** validates and types configuration
4. **Groups** organize related settings together
5. **Never commit secrets** to version control
6. **Different environments** need different configs

---

## ❓ Practice Questions

1. Why shouldn't you hardcode passwords in source code?
2. What is the purpose of .env.example?
3. What happens if you set an invalid type in an environment variable?
4. How does @lru_cache help with configuration?
5. How would you manage secrets in production?

---

## 💻 Code Exercise

Add a new configuration group for email notifications:

```python
class EmailSettings(BaseSettings):
    """Email notification settings."""
    
    model_config = SettingsConfigDict(env_prefix="")
    
    smtp_host: str = Field(default="localhost", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    from_email: str = Field(default="noreply@example.com", alias="FROM_EMAIL")
    enabled: bool = Field(default=False, alias="EMAIL_ENABLED")
```

Then add it to the main Settings class!

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `app/config.py` | All configuration settings |
| `.env.example` | Template for environment variables |
| `.env` | Your local settings (not in Git!) |
| `.gitignore` | Excludes .env from Git |

---

[← Previous: Workers](../section-11-workers/README.md) | [Next: Running the System →](../section-13-running-system/README.md)
