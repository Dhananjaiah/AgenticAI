# Section 07: Database and Data Models

## 🎯 Learning Goals
By the end of this section, you will understand:
- How we store data using PostgreSQL
- What SQLAlchemy ORM is
- The structure of our database tables
- How relationships between tables work

---

## 📺 Video Transcript

### Welcome to the Database Section!

Hello! In this section, we're going to explore how our system stores data. This is crucial because without a database, all our claim information would disappear when we turn off the computer!

### Why PostgreSQL?

We use **PostgreSQL** (often called "Postgres") as our main database. Why?

1. **Reliable** - Used by companies like Instagram, Spotify, Apple
2. **Powerful** - Handles complex queries well
3. **Open source** - Free to use!
4. **ACID compliant** - Data is safe even if the computer crashes

### What is an ORM?

ORM stands for **Object-Relational Mapping**. 

**Without ORM:**
```python
# You write raw SQL - error-prone!
cursor.execute("SELECT * FROM claims WHERE id = '" + claim_id + "'")
# Danger! SQL injection possible!
```

**With ORM (SQLAlchemy):**
```python
# You write Python - safe and clean!
claim = await db.get(Claim, claim_id)
```

The ORM translates Python objects to database operations automatically!

### Our Database Models

Open `app/db/models.py`. This file defines all our database tables as Python classes:

```python
# Each class = One database table

class Customer(Base):        # The customers table
class Policy(Base):          # The policies table
class Claim(Base):           # The claims table
class Document(Base):        # The documents table
class Payment(Base):         # The payments table
```

### The Customer Model

Let's start with customers:

```python
class Customer(Base):
    """Customer model representing insurance policy holders."""
    
    __tablename__ = "customers"  # This is the actual table name
    
    # Columns
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    policies: Mapped[list["Policy"]] = relationship("Policy", back_populates="customer")
```

**Breaking this down:**

| Part | Meaning |
|------|---------|
| `__tablename__` | The SQL table name |
| `id: Mapped[str]` | A column that holds a string |
| `primary_key=True` | This is the unique identifier |
| `nullable=False` | This field is required |
| `unique=True` | No duplicates allowed |
| `default=datetime.utcnow` | Auto-fills with current time |
| `relationship()` | Links to another table |

### The Policy Model

```python
class Policy(Base):
    """Insurance policy model."""
    
    __tablename__ = "policies"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    policy_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("customers.id"))
    policy_type: Mapped[str] = mapped_column(String(100), nullable=False)
    coverage_amount: Mapped[float] = mapped_column(Float, nullable=False)
    premium: Mapped[float] = mapped_column(Float, nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="policies")
    claims: Mapped[list["Claim"]] = relationship("Claim", back_populates="policy")
```

**New concepts:**

| Part | Meaning |
|------|---------|
| `ForeignKey("customers.id")` | Links to customers table |
| `index=True` | Faster searches on this column |
| `back_populates` | Two-way relationship |

### The Claim Model

This is our main model:

```python
class Claim(Base):
    """Insurance claim model."""
    
    __tablename__ = "claims"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    claim_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    policy_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("policies.id"))
    status: Mapped[ClaimStatus] = mapped_column(Enum(ClaimStatus), default=ClaimStatus.PENDING)
    claim_type: Mapped[str] = mapped_column(String(100), nullable=False)
    claim_amount: Mapped[float] = mapped_column(Float, nullable=False)
    approved_amount: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    incident_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    filed_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    policy: Mapped["Policy"] = relationship("Policy", back_populates="claims")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="claim")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="claim")
```

### Understanding Enums

We use enums for fixed choices:

```python
class ClaimStatus(enum.Enum):
    """Enum for claim status values."""
    
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    DENIED = "denied"
    CLOSED = "closed"
```

This prevents typos! You can't accidentally set status to "approvved".

### The Document Model

```python
class Document(Base):
    """Document metadata model."""
    
    __tablename__ = "documents"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    claim_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("claims.id"))
    policy_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("policies.id"))
    source_type: Mapped[DocumentSourceType] = mapped_column(Enum(DocumentSourceType))
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(64))
    ocr_text: Mapped[str | None] = mapped_column(Text)
    is_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
```

**Note:** Documents can be linked to claims OR policies (or both!).

### Database Relationships Visualized

```
CUSTOMER
    │
    │ has many
    ▼
POLICY
    │
    │ has many
    ▼
CLAIM ─────────────────────────────────────────
    │                     │                    │
    │ has many            │ has many           │ has many
    ▼                     ▼                    ▼
DOCUMENT              PAYMENT           STATUS_HISTORY
```

**In code, you can navigate relationships:**

```python
# Get a claim
claim = await db.get(Claim, claim_id)

# Get the policy for this claim
policy = claim.policy

# Get the customer for this policy
customer = policy.customer
print(f"{customer.first_name} {customer.last_name}")

# Get all documents for this claim
for doc in claim.documents:
    print(f"Document: {doc.filename}")
```

### Database Indexes

Indexes make searches faster:

```python
__table_args__ = (
    Index("ix_claims_status_filed_date", "status", "filed_date"),
    Index("ix_claims_policy_status", "policy_id", "status"),
)
```

Think of an index like the index at the back of a book. Instead of reading every page to find "claims", you look in the index and jump right there!

### The Session

Open `app/db/session.py`. This handles database connections:

```python
async def get_db():
    """Get a database session for dependency injection."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**What's happening:**
1. Opens a connection to the database
2. Gives you the session to use
3. Commits changes if everything works
4. Rolls back if there's an error (so partial changes don't stick)

### Using the Database

Here's how you query data:

```python
from sqlalchemy import select
from app.db.models import Claim
from app.db.session import get_db

async def get_claim_by_id(claim_id: str, db: AsyncSession):
    # Build the query
    stmt = select(Claim).where(Claim.id == claim_id)
    
    # Execute it
    result = await db.execute(stmt)
    
    # Get the result
    claim = result.scalar_one_or_none()
    
    return claim
```

**Common operations:**

```python
# Get one item
stmt = select(Claim).where(Claim.id == claim_id)
claim = (await db.execute(stmt)).scalar_one_or_none()

# Get multiple items
stmt = select(Claim).where(Claim.status == ClaimStatus.PENDING)
claims = (await db.execute(stmt)).scalars().all()

# With related data (eager loading)
stmt = select(Claim).options(
    selectinload(Claim.documents),
    selectinload(Claim.payments),
).where(Claim.id == claim_id)

# Pagination
stmt = select(Claim).offset(0).limit(20)

# Ordering
stmt = select(Claim).order_by(Claim.filed_date.desc())
```

### Database Migrations

When you change a model, you need to update the database. We use **Alembic** for this:

```bash
# Create a new migration
alembic revision --autogenerate -m "Add new column"

# Apply migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

Migrations track all changes to your database structure over time!

### The CanonicalClaimBundle Table

This is special - it stores pre-computed claim bundles:

```python
class CanonicalClaimBundle(Base):
    """Stores pre-computed canonical claim bundles for fast retrieval."""
    
    __tablename__ = "canonical_claim_bundles"
    
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), unique=True)
    structured_facts: Mapped[dict] = mapped_column(JSON, nullable=False)
    document_list: Mapped[list] = mapped_column(JSON, default=list)
    dedupe_info: Mapped[dict] = mapped_column(JSON, default=dict)
    llm_summary: Mapped[str | None] = mapped_column(Text)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
```

Why? Computing a claim bundle takes time. By storing it, we can return it instantly next time!

---

## 📝 Key Takeaways

1. **PostgreSQL** is our reliable database
2. **SQLAlchemy ORM** lets us use Python instead of raw SQL
3. **Models** define our table structure as Python classes
4. **Relationships** connect tables (Customer → Policy → Claim)
5. **Indexes** make searches faster
6. **Migrations** (Alembic) track database changes
7. **Caching** pre-computed bundles speeds up responses

---

## ❓ Practice Questions

1. What is an ORM and why do we use it?
2. What does `ForeignKey` do?
3. Why do we use enums for status values?
4. What is the purpose of database indexes?
5. When would a CanonicalClaimBundle be marked as "stale"?

---

## 💻 Code Exercise

Add a new field to the Claim model:

```python
# Add to the Claim class
adjuster_id: Mapped[str | None] = mapped_column(String(100))
```

Then create and run a migration:
```bash
alembic revision --autogenerate -m "Add adjuster_id to claims"
alembic upgrade head
```

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `app/db/models.py` | All database table definitions |
| `app/db/session.py` | Database connection handling |
| `alembic.ini` | Alembic configuration |
| `app/db/migrations/` | Migration scripts |

---

[← Previous: Services](../section-06-services/README.md) | [Next: Vector Store →](../section-08-vector-store/README.md)
