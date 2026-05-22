"""Long-term memory service using pgvector (self-implemented, no mem0).

Stores and retrieves conversation summaries via embedding similarity search.
Used for cross-session context retrieval (e.g. "我们之前聊过的杭州行程").

Architecture:
  1. Embedding: AsyncOpenAI → BAAI/bge-m3 (1024-dim)
  2. Storage:   PostgreSQL + pgvector extension
  3. Retrieval: Cosine similarity (<=>) top-k search

Uses sync psycopg + asyncio.to_thread() for cross-platform compatibility
(Windows ProactorEventLoop doesn't support psycopg async mode).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import psycopg
from openai import AsyncOpenAI
from pgvector.psycopg import register_vector
from psycopg import sql

from app.core.config import settings
from app.core.logging import logger

if TYPE_CHECKING:
    from app.services.llm.service import LLMService

_SIMILARITY_THRESHOLD = 0.5
_DEFAULT_TOP_K = 3


class MemoryService:
    """Conversation summary memory service using pgvector."""

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
                    session_id VARCHAR(255),
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
        """Search relevant conversation summaries by embedding cosine similarity."""
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
        llm: LLMService | None = None,
        session_id: str | None = None,
    ) -> None:
        """Summarize conversation via LLM and store as memory."""
        if not user_id or not self._initialized:
            return

        if llm:
            memory_text = await self._summarize_conversation(messages, llm)
        else:
            memory_text = ""

        if not memory_text:
            return

        try:
            embedding = await self._embed(memory_text)
            await asyncio.to_thread(self._add_db, user_id, session_id, memory_text, embedding)
            logger.debug("memory_added", user_id=user_id, session_id=session_id, content_length=len(memory_text))
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

    def _add_db(self, user_id: str, session_id: str | None, content: str, embedding: list[float]) -> None:
        import json
        metadata = json.dumps({"session_id": session_id} if session_id else {}, ensure_ascii=False)
        with psycopg.connect(self._conninfo) as conn:
            register_vector(conn)
            conn.execute(
                sql.SQL("""
                    INSERT INTO {tbl} (user_id, session_id, content, embedding, metadata)
                    VALUES (%s, %s, %s, %s::vector, %s::jsonb)
                """).format(tbl=self._table),
                (user_id, session_id, content, str(embedding), metadata),
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
    # Conversation summarization
    # ------------------------------------------------------------------

    _SUMMARIZE_PROMPT = (
        "用一两句话概括以下对话的核心内容，重点描述：用户想规划什么行程、最终结果如何。\n"
        "只输出摘要，不要加前缀或解释。如果对话没有实质内容，只输出：NONE"
    )

    async def _summarize_conversation(
        self, messages: list[dict[str, Any]], llm: LLMService,
    ) -> str:
        """Use LLM to generate a short conversation summary."""
        conversation = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content:
                continue
            if role == "user":
                conversation.append(f"用户: {content}")
            elif role == "assistant" and "tool_calls" not in msg:
                conversation.append(f"助手: {content[:300]}")

        if not conversation:
            return ""

        extract_messages = [
            {"role": "system", "content": self._SUMMARIZE_PROMPT},
            {"role": "user", "content": "\n".join(conversation[-10:])},
        ]

        try:
            response = await llm.call(
                messages=extract_messages,
                tools=None,
                temperature=0.0,
                max_tokens=128,
            )
            result = (response.choices[0].message.content or "").strip()
            if not result or result.upper() == "NONE":
                return ""
            return result
        except Exception as e:
            logger.warning("memory_summarize_failed", error=str(e))
            return ""


memory_service = MemoryService()
