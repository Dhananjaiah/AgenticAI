"""
Structured logging configuration with correlation IDs.

Provides:
- JSON or text formatted logging
- Correlation ID tracking across requests
- Request-scoped context
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

from app.config import get_settings

settings = get_settings()

# Context variable for correlation ID
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Get the current correlation ID."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str | None = None) -> str:
    """
    Set the correlation ID for the current context.

    Args:
        correlation_id: Optional correlation ID. If not provided, generates a new one.

    Returns:
        str: The correlation ID that was set
    """
    cid = correlation_id or str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid


def add_correlation_id(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add correlation ID to log event."""
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def add_claim_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add claim context if available."""
    # This could be extended to add claim_id, policy_id etc. from context
    return event_dict


def configure_logging() -> None:
    """Configure structured logging for the application."""
    log_level = getattr(logging, settings.logging.log_level.upper(), logging.INFO)

    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        add_correlation_id,
        add_claim_context,
    ]

    if settings.logging.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Set log levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        BoundLogger: Structured logger instance
    """
    return structlog.get_logger(name)


class LoggingMiddleware:
    """
    Middleware for request logging with correlation IDs.

    Adds correlation ID to each request and logs request/response details.
    """

    def __init__(self, app: Any) -> None:
        """Initialize middleware."""
        self.app = app
        self.logger = get_logger(__name__)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        """Process request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Get or generate correlation ID
        headers = dict(scope.get("headers", []))
        correlation_id = headers.get(b"x-correlation-id", b"").decode() or str(uuid.uuid4())
        set_correlation_id(correlation_id)

        # Log request
        self.logger.info(
            "Request started",
            method=scope.get("method"),
            path=scope.get("path"),
        )

        # Track response status
        response_status = [0]

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                response_status[0] = message.get("status", 0)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            self.logger.info(
                "Request completed",
                method=scope.get("method"),
                path=scope.get("path"),
                status=response_status[0],
            )
