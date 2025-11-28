-- Initialize databases and schemas for Agentic-AI Claims

-- Create metadata database
CREATE DATABASE claims_metadata_db;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE claims_db TO claims_user;
GRANT ALL PRIVILEGES ON DATABASE claims_metadata_db TO claims_user;

-- Connect to claims_db and create extensions
\c claims_db

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes for common queries (will be created by Alembic migrations)
-- These are placeholder comments for documentation

-- Index for claim lookups
-- CREATE INDEX IF NOT EXISTS ix_claims_number ON claims(claim_number);
-- CREATE INDEX IF NOT EXISTS ix_claims_status_date ON claims(status, filed_date);

-- Index for document searches
-- CREATE INDEX IF NOT EXISTS ix_documents_claim ON documents(claim_id);
-- CREATE INDEX IF NOT EXISTS ix_documents_indexed ON documents(is_indexed, created_at);
