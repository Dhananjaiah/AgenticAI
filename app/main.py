"""
Main FastAPI application for Agentic-AI Insurance Claims Architecture.

This is the entry point for the HTTP API that provides:
- Claim data retrieval and processing
- Policy management
- Admin operations
- Health and metrics endpoints
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import claims_router, policies_router, admin_router, health_router
from app.config import get_settings
from app.db.session import init_db, close_db
from app.observability.logging_config import (
    configure_logging,
    get_logger,
    set_correlation_id,
    LoggingMiddleware,
)
from app.services.cache import CacheService

settings = get_settings()

# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Agentic-AI Claims application", version=settings.app_version)

    # Initialize database tables (for development)
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning("Database initialization skipped", error=str(e))

    # Initialize cache
    cache = CacheService()
    try:
        if await cache.ping():
            logger.info("Cache (Redis) connected")
        else:
            logger.warning("Cache (Redis) not available")
    except Exception as e:
        logger.warning("Cache initialization failed", error=str(e))

    yield

    # Shutdown
    logger.info("Shutting down Agentic-AI Claims application")
    await close_db()
    await cache.close()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="""
    Agentic-AI Insurance Claims Architecture API.
    
    This API provides endpoints for:
    - Retrieving claim data with full canonical bundles
    - Policy and claims management
    - Index management and refresh operations
    - Health checks and metrics
    
    The system uses Microsoft Autogen for agentic orchestration,
    with retriever agents for SQL, SharePoint, and Blob storage.
    """,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Add correlation ID to each request."""
    correlation_id = request.headers.get("X-Correlation-ID")
    set_correlation_id(correlation_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id or ""
    return response


# Include routers
app.include_router(health_router)
app.include_router(claims_router, prefix="/api/v1")
app.include_router(policies_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
