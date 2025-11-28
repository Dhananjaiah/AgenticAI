# Section 13: Running the Complete System

## 🎯 Learning Goals
By the end of this section, you will be able to:
- Run the complete system end-to-end
- Test all the components
- Deploy using Docker
- Monitor and troubleshoot issues

---

## 📺 Video Transcript

### Congratulations!

You've made it to the final section! Now we're going to put everything together and run the complete system.

### System Overview

Let's recap what we're running:

```
┌─────────────────────────────────────────────────────────────┐
│                    COMPLETE SYSTEM                          │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   FastAPI   │  │   Workers   │  │   Kafka     │         │
│  │    (API)    │  │  (Indexer)  │  │  (Queue)    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ PostgreSQL  │  │   Redis     │  │  ChromaDB   │         │
│  │ (Database)  │  │  (Cache)    │  │  (Vectors)  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Method 1: Running Locally (Development)

#### Step 1: Start Infrastructure

```bash
# Navigate to infrastructure directory
cd infra

# Start PostgreSQL, Redis, and Kafka
docker-compose up -d postgres redis kafka

# Check they're running
docker-compose ps
```

You should see:
```
NAME                STATUS
claims_postgres     Up 30 seconds
claims_redis        Up 30 seconds
claims_kafka        Up 30 seconds
```

#### Step 2: Apply Database Migrations

```bash
# Go back to project root
cd ..

# Activate virtual environment
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Run migrations
alembic upgrade head
```

#### Step 3: Start the API Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Step 4: Start Workers (in new terminals)

```bash
# Terminal 2: Start indexer worker
source venv/bin/activate
python -m workers.indexer_worker

# Terminal 3: Start OCR worker (optional)
source venv/bin/activate
python -m workers.ocr_worker
```

#### Step 5: Verify Everything Works

```bash
# Check health
curl http://localhost:8000/health

# Check API docs
open http://localhost:8000/docs
```

### Method 2: Docker Compose (Full Stack)

This is the easier way - one command starts everything!

```bash
cd infra

# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f api
```

The docker-compose.yml defines everything:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: claims_user
      POSTGRES_PASSWORD: claims_password
      POSTGRES_DB: claims_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  kafka:
    image: confluentinc/cp-kafka:latest
    # ... kafka config
  
  api:
    build:
      context: ..
      dockerfile: infra/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://claims_user:claims_password@postgres:5432/claims_db
      - REDIS_URL=redis://redis:6379/0
      - LLM_MODE=stub
    depends_on:
      - postgres
      - redis
  
  indexer-worker:
    build:
      context: ..
      dockerfile: infra/Dockerfile
    command: python -m workers.indexer_worker
    depends_on:
      - postgres
      - redis
      - kafka

volumes:
  postgres_data:
```

### Testing the System

#### 1. Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
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

#### 2. Create Sample Data

First, let's add some test data. You can use the database directly or create an admin endpoint:

```sql
-- Connect to PostgreSQL
psql -h localhost -U claims_user -d claims_db

-- Insert a customer
INSERT INTO customers (id, first_name, last_name, email)
VALUES ('cust-001', 'John', 'Smith', 'john.smith@example.com');

-- Insert a policy
INSERT INTO policies (id, policy_number, customer_id, policy_type, coverage_amount, premium, start_date, end_date)
VALUES ('pol-001', 'POL-2024-001', 'cust-001', 'auto', 50000, 500, '2024-01-01', '2025-01-01');

-- Insert a claim
INSERT INTO claims (id, claim_number, policy_id, status, claim_type, claim_amount, incident_date)
VALUES ('claim-001', 'CLM-2024-001', 'pol-001', 'pending', 'collision', 5000, '2024-01-15');
```

#### 3. Fetch a Claim

```bash
curl http://localhost:8000/api/v1/claims/CLM-2024-001
```

#### 4. List Claims

```bash
curl http://localhost:8000/api/v1/claims/
```

#### 5. Trigger Refresh

```bash
curl -X POST http://localhost:8000/api/v1/claims/CLM-2024-001/refresh
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_api.py -v

# Run with output
pytest -v -s
```

### Monitoring

#### View Logs

```bash
# All logs
docker-compose logs -f

# Specific service
docker-compose logs -f api

# Last 100 lines
docker-compose logs --tail=100 api
```

#### Check Metrics

```bash
curl http://localhost:8000/metrics
```

Output:
```
# HELP claims_http_requests_total Total HTTP requests
# TYPE claims_http_requests_total counter
claims_http_requests_total{endpoint="/claims",method="GET"} 42

# HELP claims_cache_hit_rate Cache hit rate
claims_cache_hit_rate 0.85
```

#### Check Redis

```bash
docker exec -it claims_redis redis-cli
> KEYS *
> GET claim_bundle:CLM-2024-001
```

### Troubleshooting Common Issues

#### "Cannot connect to database"

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Try connecting directly
psql -h localhost -U claims_user -d claims_db
```

#### "Redis connection refused"

```bash
# Check Redis is running
docker-compose ps redis

# Try connecting
redis-cli ping
```

#### "Worker not processing messages"

```bash
# Check Kafka is running
docker-compose ps kafka

# Check worker logs
docker-compose logs indexer-worker
```

#### "API returns 500 error"

```bash
# Check API logs
docker-compose logs api

# Run in debug mode
DEBUG=true uvicorn app.main:app --reload
```

### Scaling for Production

#### Scale Workers

```bash
docker-compose up -d --scale indexer-worker=3
```

#### Use Production Database

```yaml
# docker-compose.prod.yml
services:
  api:
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@production-db.cloud.com/claims
```

#### Enable HTTPS

Use a reverse proxy like Nginx:

```nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Quick Reference: Common Commands

```bash
# Start everything
cd infra && docker-compose up -d

# Stop everything
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

# View logs
docker-compose logs -f api

# Run migrations
alembic upgrade head

# Run tests
pytest

# Check API health
curl http://localhost:8000/health

# Scale workers
docker-compose up -d --scale indexer-worker=3
```

---

## 📝 Key Takeaways

1. **Docker Compose** makes running the full stack easy
2. **Health endpoints** tell you if services are working
3. **Logs** are your best friend for debugging
4. **Scale workers** horizontally for more processing power
5. **Metrics** help you monitor performance
6. **Test thoroughly** before deploying

---

## ❓ Final Practice Questions

1. What command starts all services with Docker?
2. How do you check if the database is healthy?
3. How would you scale to handle more documents?
4. What's the difference between running locally vs Docker?
5. How do you view API logs in Docker?

---

## 🎓 Course Complete!

Congratulations! You've completed the Agentic AI Insurance Claims course!

### What You've Learned

1. **Introduction** - What Agentic AI is
2. **Getting Started** - Setting up your environment
3. **Architecture** - How all pieces fit together
4. **API Layer** - FastAPI and endpoints
5. **Agents** - The AI workers
6. **Services** - Business logic (deduplication, RAG)
7. **Database** - SQLAlchemy and PostgreSQL
8. **Vector Store** - Semantic search with ChromaDB
9. **OCR** - Reading text from images
10. **Caching** - Redis for performance
11. **Workers** - Background processing
12. **Configuration** - Environment management
13. **Running** - Putting it all together

### Next Steps

1. **Try extending the system:**
   - Add new agents (email, API integrations)
   - Add new deduplication rules
   - Create a frontend UI

2. **Learn more about:**
   - Microsoft Autogen (advanced agents)
   - LangChain (alternative framework)
   - Kubernetes (production deployment)

3. **Build your own projects:**
   - Legal document analysis
   - Medical record processing
   - Customer support automation

### Thank You!

Thank you for taking this course. I hope it's helped you understand how to build AI-powered systems.

Remember: The best way to learn is to build. Start with something small, and keep improving!

Good luck on your AI journey! 🚀

---

[← Previous: Configuration](../section-12-configuration/README.md) | [Back to Course Home →](../README.md)
