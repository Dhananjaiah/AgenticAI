"""
API routers module for Agentic-AI Insurance Claims Architecture.
"""

from app.api.admin import router as admin_router
from app.api.claims import router as claims_router
from app.api.health import router as health_router
from app.api.policies import router as policies_router

__all__ = [
    "claims_router",
    "policies_router",
    "admin_router",
    "health_router",
]
