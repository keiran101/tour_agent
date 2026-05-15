"""Chat API endpoints — wired to the self-built ReAct Agent loop.

Multi-turn conversation: server is the source of truth for history.
Client sends only the new user message; server loads prior turns from DB,
runs the agent with full context, and persists the new turn afterward.
"""

import json
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse

from app.api.v1.auth import get_current_session
from app.core.agent.loop import AgentLoop
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.tools import create_tool_registry
from app.models.session import Session
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    Message,
)
from app.services.database import database_service
from app.services.llm.service import llm_service
from app.services.memory import memory_service

router = APIRouter()

_PLANNER_PROMPT = (Path(__file__).resolve().parents[2] / "core" / "prompts" / "planner.md").read_text(encoding="utf-8")


def _build_agent() -> AgentLoop:
    return AgentLoop(
        llm=llm_service,
        tools=create_tool_registry(),
        memory=memory_service,
        system_prompt=_PLANNER_PROMPT,
    )


async def _load_history(session_id: str) -> list[dict]:
    """Load conversation history (user + assistant turns) from DB."""
    try:
        return await database_service.get_messages(session_id)
    except Exception as e:
        logger.warning("history_load_failed", session_id=session_id, error=str(e))
        return []


async def _save_turn(session_id: str, user_content: str, assistant_content: str) -> None:
    """Persist one conversation turn (user question + assistant answer)."""
    try:
        await database_service.save_messages(session_id, [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ])
    except Exception as e:
        logger.warning("history_save_failed", session_id=session_id, error=str(e))


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Process a chat request via the Agent loop (synchronous, full response)."""
    new_user_content = chat_request.messages[-1].content

    logger.info(
        "chat_request_received",
        session_id=session.id,
        content_length=len(new_user_content),
    )

    try:
        history = await _load_history(session.id)
        user_messages = history + [{"role": "user", "content": new_user_content}]

        agent = _build_agent()
        state = await agent.run(
            user_messages=user_messages,
            user_id=str(session.user_id),
            session_id=session.id,
        )

        answer = state.final_answer or ""
        await _save_turn(session.id, new_user_content, answer)

        return ChatResponse(
            messages=[Message(role="assistant", content=answer)],
        )

    except Exception as e:
        logger.exception("chat_request_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat_stream"][0])
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Stream a chat response via the Agent loop (SSE)."""
    new_user_content = chat_request.messages[-1].content

    logger.info(
        "stream_chat_request_received",
        session_id=session.id,
        content_length=len(new_user_content),
    )

    history = await _load_history(session.id)
    user_messages = history + [{"role": "user", "content": new_user_content}]

    agent = _build_agent()
    session_id = session.id
    user_id = str(session.user_id)

    async def event_generator():
        final_answer = ""
        try:
            async for event in agent.run_stream(
                user_messages=user_messages,
                user_id=user_id,
                session_id=session_id,
            ):
                if event.get("type") == "answer":
                    final_answer = event.get("content", "")
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("stream_chat_failed", session_id=session_id, error=str(e))
            error_event = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"
        finally:
            if final_answer:
                await _save_turn(session_id, new_user_content, final_answer)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
