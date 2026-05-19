"""Chat API endpoints — thin HTTP layer over TripOrchestrator.

All business logic (state machine, routing, executor dispatch) lives in
the orchestrator; this module only handles HTTP concerns:
  - Load/save conversation history and builder state
  - Construct ChatResponse / SSE stream from ExecutorResult
"""

import json

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse

from app.api.v1.auth import get_current_session, get_current_user
from app.core.agent.orchestrator import TripOrchestrator
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.session import Session
from app.models.user import User
from app.schemas.builder import (
    BuilderResponse,
    BuilderState,
    GroupDaysPayload,
    SelectPOIsPayload,
)
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    HistoryMessage,
    Message,
    SessionDetailResponse,
)
from app.services.database import database_service
from app.services.llm.service import llm_service
from app.services.memory import memory_service

router = APIRouter()


# ------------------------------------------------------------------
# Persistence helpers
# ------------------------------------------------------------------

async def _load_history(session_id: str) -> list[dict]:
    try:
        return await database_service.get_messages(session_id)
    except Exception as e:
        logger.warning("history_load_failed", session_id=session_id, error=str(e))
        return []


async def _save_turn(session_id: str, user_content: str, assistant_content: str) -> None:
    try:
        await database_service.save_messages(session_id, [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ])
    except Exception as e:
        logger.warning("history_save_failed", session_id=session_id, error=str(e))


async def _load_state(session_id: str) -> BuilderState:
    try:
        raw = await database_service.get_builder_state(session_id)
        if raw:
            return BuilderState.model_validate_json(raw)
    except Exception as e:
        logger.warning("state_load_failed", session_id=session_id, error=str(e))
    return BuilderState()


async def _save_state(session_id: str, state: BuilderState) -> None:
    try:
        await database_service.save_builder_state(session_id, state.model_dump_json())
    except Exception as e:
        logger.warning("state_save_failed", session_id=session_id, error=str(e))


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Multi-phase chat: gathering -> select_pois -> group_days -> arrange -> confirm."""
    new_user_content = chat_request.messages[-1].content
    logger.info("chat_request", session_id=session.id, length=len(new_user_content))

    try:
        history = await _load_history(session.id)
        messages = history + [{"role": "user", "content": new_user_content}]
        state = await _load_state(session.id)

        orchestrator = TripOrchestrator(
            llm=llm_service,
            memory=memory_service,
            user_id=session.user_id,
            session_id=session.id,
        )

        result = await orchestrator.handle(messages, state, chat_request.builder_action)

        await _save_state(session.id, state)
        await _save_turn(session.id, new_user_content, result.message)

        return ChatResponse(
            messages=[Message(role="assistant", content=result.message)],
            questions=result.questions,
            builder=result.builder_response,
        )

    except Exception as e:
        logger.exception("chat_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat_stream"][0])
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """SSE streaming variant — same orchestrator, streamed output."""
    new_user_content = chat_request.messages[-1].content
    logger.info("stream_chat_request", session_id=session.id, length=len(new_user_content))

    history = await _load_history(session.id)
    messages = history + [{"role": "user", "content": new_user_content}]
    state = await _load_state(session.id)
    session_id = session.id

    orchestrator = TripOrchestrator(
        llm=llm_service,
        memory=memory_service,
        user_id=session.user_id,
        session_id=session.id,
    )

    async def generator():
        try:
            result = await orchestrator.handle(messages, state, chat_request.builder_action)

            if result.questions:
                event = {
                    "type": "gathering",
                    "content": result.message,
                    "questions": [q.model_dump() for q in result.questions],
                }
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            elif result.builder_response:
                builder_event = {
                    "type": "builder",
                    "content": result.message,
                    "layer": result.builder_response.layer,
                    "data": result.builder_response.data.model_dump() if result.builder_response.data else None,
                }
                yield f"data: {json.dumps(builder_event, ensure_ascii=False)}\n\n"

            else:
                yield f"data: {json.dumps({'type': 'answer', 'content': result.message}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

            await _save_state(session_id, state)
            await _save_turn(session_id, new_user_content, result.message)

        except Exception as e:
            logger.exception("stream_failed", session_id=session_id, error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ------------------------------------------------------------------
# Session detail (conversation history)
# ------------------------------------------------------------------

@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_messages(
    session_id: str,
    user: User = Depends(get_current_user),
):
    """Load conversation history and current builder state for a session."""
    session = await database_service.get_session(session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    history = await _load_history(session_id)
    state = await _load_state(session_id)

    messages = [
        HistoryMessage(role=m["role"], content=m.get("content", ""))
        for m in history
        if m.get("role") in ("user", "assistant")
    ]

    return SessionDetailResponse(
        session_id=session_id,
        name=session.name,
        phase=state.phase,
        messages=messages,
        builder=_state_to_builder_response(state),
    )


def _state_to_builder_response(state: BuilderState) -> BuilderResponse | None:
    """Reconstruct the current phase's BuilderResponse from persisted state."""
    if state.phase == "gathering":
        return None
    if state.phase == "select_pois":
        selected_set = set(state.selected_ids)
        return BuilderResponse(
            layer="select_pois",
            data=SelectPOIsPayload(
                recommended=[p for p in state.all_pois if p.id in selected_set],
                alternatives=[p for p in state.all_pois if p.id not in selected_set],
            ),
        )
    if state.phase == "group_days":
        return BuilderResponse(
            layer="group_days",
            data=GroupDaysPayload(days=state.day_groups),
        )
    if state.phase in ("arrange", "confirm"):
        return BuilderResponse(layer=state.phase, data=state.schedule)
    return None
