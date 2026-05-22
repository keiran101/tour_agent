"""Chat API endpoints — thin HTTP layer over TripAgent.

All business logic (ReAct loop, tool dispatch) lives in the agent;
this module only handles HTTP concerns:
  - Load/save conversation history and builder state
  - Construct ChatResponse / SSE stream from AgentResponse
"""

import json

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.api.v1.auth import get_current_session, get_current_user
from app.core.agent.agent import AgentResponse, TripAgent
from app.core.agent.state import TripPlanningState
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.tools import create_tool_registry
from app.models.session import Session
from app.models.user import User
from app.schemas.builder import BuilderResponse, BuilderState
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


async def _save_turn(session_id: str, user_content: str, result: AgentResponse) -> None:
    try:
        assistant_msg: dict = {"role": "assistant", "content": result.content}
        if result.questions:
            assistant_msg["questions"] = [q.model_dump() for q in result.questions]
        if result.ui_payload and result.layer:
            builder = BuilderResponse(
                layer=result.layer,  # type: ignore[arg-type]
                data=result.ui_payload,  # type: ignore[arg-type]
            )
            assistant_msg["builder"] = builder.model_dump()
        await database_service.save_messages(session_id, [
            {"role": "user", "content": user_content},
            assistant_msg,
        ])
    except Exception as e:
        logger.warning("history_save_failed", session_id=session_id, error=str(e))


async def _load_state(session_id: str) -> TripPlanningState:
    try:
        raw = await database_service.get_builder_state(session_id)
        if raw:
            try:
                return TripPlanningState.model_validate_json(raw)
            except ValidationError:
                old = BuilderState.model_validate_json(raw)
                return TripPlanningState.from_builder_state(old)
    except Exception as e:
        logger.warning("state_load_failed", session_id=session_id, error=str(e))
    return TripPlanningState()


async def _save_state(session_id: str, state: TripPlanningState) -> None:
    try:
        await database_service.save_builder_state(session_id, state.model_dump_json())
    except Exception as e:
        logger.warning("state_save_failed", session_id=session_id, error=str(e))


def _derive_phase(state: TripPlanningState) -> str:
    """Derive a frontend-compatible phase string from state data."""
    if state.trip_saved:
        return "confirm"
    if state.schedule:
        return "arrange"
    if state.day_groups:
        return "group_days"
    if state.selected_pois:
        return "select_pois"
    return "gathering"


def _create_agent(session: Session) -> TripAgent:
    tools = create_tool_registry(
        llm=llm_service,
        memory=memory_service,
        user_id=session.user_id,
        session_id=session.id,
    )
    return TripAgent(
        llm=llm_service,
        memory=memory_service,
        tools=tools,
        user_id=session.user_id,
        session_id=session.id,
    )


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
    """ReAct agent chat — LLM decides which tool to call next."""
    new_user_content = chat_request.messages[-1].content
    logger.info("chat_request", session_id=session.id, length=len(new_user_content))

    try:
        history = await _load_history(session.id)
        messages = history + [{"role": "user", "content": new_user_content}]
        state = await _load_state(session.id)

        agent = _create_agent(session)
        result = await agent.handle(messages, state, chat_request.builder_action)

        await _save_state(session.id, state)
        await _save_turn(session.id, new_user_content, result)

        builder_resp = None
        if result.ui_payload and result.layer:
            builder_resp = BuilderResponse(
                layer=result.layer,  # type: ignore[arg-type]
                data=result.ui_payload,  # type: ignore[arg-type]
            )

        return ChatResponse(
            messages=[Message(role="assistant", content=result.content)],
            questions=result.questions,
            builder=builder_resp,
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
    """SSE streaming variant — same agent, event-based output."""
    new_user_content = chat_request.messages[-1].content
    logger.info("stream_chat_request", session_id=session.id, length=len(new_user_content))

    history = await _load_history(session.id)
    messages = history + [{"role": "user", "content": new_user_content}]
    state = await _load_state(session.id)
    session_id = session.id

    agent = _create_agent(session)

    async def generator():
        try:
            result = await agent.handle(messages, state, chat_request.builder_action)

            if result.type == "gathering":
                event = {
                    "type": "gathering",
                    "content": result.content,
                    "questions": [q.model_dump() for q in result.questions],
                }
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            elif result.type == "builder" and result.ui_payload:
                builder_event = {
                    "type": "builder",
                    "content": result.content,
                    "layer": result.layer,
                    "data": result.ui_payload.model_dump() if hasattr(result.ui_payload, "model_dump") else None,
                }
                yield f"data: {json.dumps(builder_event, ensure_ascii=False)}\n\n"

            else:
                yield f"data: {json.dumps({'type': 'answer', 'content': result.content}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

            await _save_state(session_id, state)
            await _save_turn(session_id, new_user_content, result)

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

    try:
        history = await database_service.get_display_messages(session_id)
    except Exception as e:
        logger.warning("display_history_load_failed", session_id=session_id, error=str(e))
        history = []
    state = await _load_state(session_id)

    messages = [
        HistoryMessage(
            role=m["role"],
            content=m.get("content", ""),
            questions=m.get("questions"),
            builder=m.get("builder"),
        )
        for m in history
        if m.get("role") in ("user", "assistant")
    ]

    return SessionDetailResponse(
        session_id=session_id,
        name=session.name,
        phase=_derive_phase(state),
        messages=messages,
    )
