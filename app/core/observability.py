"""Observability module for the application.

Uses Langfuse Python SDK directly (no LangChain dependency).
Provides a singleton Langfuse client for manual tracing of
agent steps, tool calls, and LLM invocations.
"""

from langfuse import Langfuse

from app.core.config import settings
from app.core.logging import logger

_langfuse: Langfuse | None = None


def get_langfuse() -> Langfuse:
    """Get or create the singleton Langfuse client."""
    global _langfuse
    if _langfuse is None:
        _langfuse = Langfuse(
            tracing_enabled=settings.LANGFUSE_TRACING_ENABLED,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
            environment=settings.ENVIRONMENT.value,
            debug=settings.DEBUG,
        )
    return _langfuse


def langfuse_init() -> None:
    """Initialize Langfuse and verify authentication."""
    client = get_langfuse()
    if client.auth_check():
        logger.debug("langfuse_auth_success")
    else:
        logger.debug("langfuse_auth_failure")
