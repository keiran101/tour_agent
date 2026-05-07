"""Long-term memory service using pgvector (self-implemented, no mem0).

Stores and retrieves user preference memories via embedding similarity search.
Uses PostgreSQL + pgvector for vector storage and OpenAI-compatible
embedding API for vectorization.
"""

from app.core.logging import logger


class MemoryService:
    """Self-implemented memory service using pgvector."""

    def __init__(self):
        """Initialize the memory service."""
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize pgvector table and embedding client."""
        # TODO: create pgvector extension and memory table if not exists
        self._initialized = True
        logger.info("memory_service_initialized")

    async def search(self, user_id: str | None, query: str) -> str:
        """Search relevant memories by embedding similarity."""
        if user_id is None:
            return ""
        # TODO: embed query, search pgvector, return formatted results
        return ""

    async def add(self, user_id: str | None, messages: list[dict], metadata: dict | None = None) -> None:
        """Extract and store memory from conversation messages."""
        if user_id is None:
            return
        # TODO: extract key info from messages, embed, store in pgvector
        logger.debug("memory_add_stub", user_id=user_id)


memory_service = MemoryService()
