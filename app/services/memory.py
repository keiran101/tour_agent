"""Long-term memory service using pgvector (self-implemented, no mem0).

Stores and retrieves user preference memories via embedding similarity search.
Uses PostgreSQL + pgvector for vector storage and OpenAI-compatible
embedding API for vectorization.

Architecture:
  1. Embedding: AsyncOpenAI → BAAI/bge-m3 (1024-dim)
  2. Storage:   PostgreSQL + pgvector extension
  3. Retrieval: Cosine similarity (<=>) top-k search

Uses sync psycopg + asyncio.to_thread() for cross-platform compatibility
(Windows ProactorEventLoop doesn't support psycopg async mode).
"""

import asyncio
from typing import Any

import psycopg
from openai import AsyncOpenAI
from pgvector.psycopg import register_vector
from psycopg import sql

from app.core.config import settings
from app.core.logging import logger

_SIMILARITY_THRESHOLD = 0.35
_DEFAULT_TOP_K = 5


class MemoryService:
    """Self-implemented memory service using pgvector."""

    def __init__(self) -> None:
        self._initialized = False
        self._embed_client: AsyncOpenAI | None = None
        self._table = sql.Identifier(settings.MEMORY_COLLECTION_NAME)
        self._dim = settings.EMBEDDING_DIM
        self._conninfo = (
            f"host={settings.POSTGRES_HOST} port={settings.POSTGRES_PORT} "
            f"dbname={settings.POSTGRES_DB} user={settings.POSTGRES_USER} "
            f"password={settings.POSTGRES_PASSWORD}"
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Create pgvector extension and memory table if not exists."""
        try:
            self._embed_client = AsyncOpenAI(
                api_key=settings.EMBEDDING_API_KEY or settings.LLM_API_KEY,
                base_url=settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL,
            )

            await asyncio.to_thread(self._init_db)

            self._initialized = True
            logger.info("memory_service_initialized", table=settings.MEMORY_COLLECTION_NAME, dim=self._dim)
        except Exception as e:
            logger.warning("memory_service_init_failed", error=str(e))

    def _init_db(self) -> None:
        """Create pgvector extension and memory table (sync, runs in thread)."""
        with psycopg.connect(self._conninfo) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS {tbl} (
                    id         BIGSERIAL PRIMARY KEY,
                    user_id    VARCHAR(255) NOT NULL,
                    content    TEXT NOT NULL,
                    embedding  vector({dim}),
                    metadata   JSONB DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """).format(tbl=self._table, dim=sql.Literal(self._dim)))

            conn.execute(sql.SQL(
                "CREATE INDEX IF NOT EXISTS {idx} ON {tbl} (user_id)"
            ).format(
                idx=sql.Identifier(f"idx_{settings.MEMORY_COLLECTION_NAME}_user_id"),
                tbl=self._table,
            ))
            conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(self, user_id: str | None, query: str, top_k: int = _DEFAULT_TOP_K) -> str:
        """Search relevant memories by embedding cosine similarity.

        Returns formatted string for injection into system prompt.
        """
        if not user_id or not self._initialized:
            return ""

        try:
            query_vec = await self._embed(query)
            rows = await asyncio.to_thread(self._search_db, user_id, query_vec, top_k)

            if not rows:
                return ""

            parts: list[str] = []
            for content, similarity in rows:
                if similarity >= _SIMILARITY_THRESHOLD:
                    parts.append(f"- {content}")

            return "\n".join(parts)

        except Exception as e:
            logger.warning("memory_search_failed", user_id=user_id, error=str(e))
            return ""

    async def add(
        self,
        user_id: str | None,
        messages: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Extract and store memory from conversation messages."""
        if not user_id or not self._initialized:
            return

        memory_text = self._extract_memory(messages)
        if not memory_text:
            return

        try:
            embedding = await self._embed(memory_text)
            await asyncio.to_thread(self._add_db, user_id, memory_text, embedding)
            logger.debug("memory_added", user_id=user_id, content_length=len(memory_text))
        except Exception as e:
            logger.warning("memory_add_failed", user_id=user_id, error=str(e))

    # ------------------------------------------------------------------
    # Database operations (sync, called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _search_db(self, user_id: str, query_vec: list[float], top_k: int) -> list[tuple[str, float]]:
        with psycopg.connect(self._conninfo) as conn:
            register_vector(conn)
            cur = conn.execute(
                sql.SQL("""
                    SELECT content, 1 - (embedding <=> %s::vector) AS similarity
                    FROM {tbl}
                    WHERE user_id = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """).format(tbl=self._table),
                (str(query_vec), user_id, str(query_vec), top_k),
            )
            return cur.fetchall()

    def _add_db(self, user_id: str, content: str, embedding: list[float]) -> None:
        with psycopg.connect(self._conninfo) as conn:
            register_vector(conn)
            conn.execute(
                sql.SQL("""
                    INSERT INTO {tbl} (user_id, content, embedding, metadata)
                    VALUES (%s, %s, %s::vector, %s::jsonb)
                """).format(tbl=self._table),
                (user_id, content, str(embedding), "{}"),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    async def _embed(self, text: str) -> list[float]:
        """Generate embedding vector for text via OpenAI-compatible API."""
        assert self._embed_client is not None
        response = await self._embed_client.embeddings.create(
            input=text,
            model=settings.EMBEDDING_MODEL,
        )
        return response.data[0].embedding

    # ------------------------------------------------------------------
    # Memory extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_memory(messages: list[dict[str, Any]]) -> str:
        """Extract memorable content from conversation messages.

        Keeps user queries and assistant final answers (not tool-calling steps).
        """
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content:
                continue
            if role == "user":
                parts.append(f"用户: {content}")
            elif role == "assistant" and "tool_calls" not in msg:
                parts.append(f"助手: {content[:500]}")

        if not parts:
            return ""
        return "\n".join(parts[-6:])


memory_service = MemoryService()
