"""Chat API endpoints — multi-layer interactive trip builder.

Flow:
  1. Gatherer collects requirements (gathering/ready)
  2. Builder Layer 1: POI recommendation + selection
  3. Builder Layer 2: Day grouping
  4. Builder Layer 3: Time arrangement
  5. Builder Layer 4: Confirm & save

User can advance, modify, or backtrack at any layer.
Client sends only the new user message; server manages full state.
"""

import json

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse

from app.api.v1.auth import get_current_session
from app.core.agent.builder import BuilderOrchestrator
from app.core.agent.gatherer import GathererAgent
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.session import Session
from app.schemas.builder import BuilderState, StoredRequirements
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    Message,
)
from app.schemas.gatherer import TravelRequirements
from app.services.database import database_service
from app.services.llm.service import llm_service
from app.services.memory import memory_service

router = APIRouter()

# Layer progression order
_LAYER_ORDER = ["select_pois", "group_days", "arrange", "confirm"]


def _next_layer(current: str) -> str:
    """Get the next layer after the current one."""
    try:
        idx = _LAYER_ORDER.index(current)
        if idx + 1 < len(_LAYER_ORDER):
            return _LAYER_ORDER[idx + 1]
    except ValueError:
        pass
    return current


async def _load_history(session_id: str) -> list[dict]:
    """Load conversation history from DB."""
    try:
        return await database_service.get_messages(session_id)
    except Exception as e:
        logger.warning("history_load_failed", session_id=session_id, error=str(e))
        return []


async def _save_turn(session_id: str, user_content: str, assistant_content: str) -> None:
    """Persist one conversation turn."""
    try:
        await database_service.save_messages(session_id, [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ])
    except Exception as e:
        logger.warning("history_save_failed", session_id=session_id, error=str(e))


async def _load_builder_state(session_id: str) -> BuilderState | None:
    """Load builder state from session."""
    try:
        raw = await database_service.get_builder_state(session_id)
        if raw:
            return BuilderState.model_validate_json(raw)
    except Exception as e:
        logger.warning("builder_state_load_failed", session_id=session_id, error=str(e))
    return None


async def _save_builder_state(session_id: str, state: BuilderState) -> None:
    """Persist builder state to session."""
    try:
        await database_service.save_builder_state(
            session_id, state.model_dump_json(),
        )
    except Exception as e:
        logger.warning("builder_state_save_failed", session_id=session_id, error=str(e))




@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Multi-layer chat: Gatherer → Builder (select → group → arrange → confirm)."""
    new_user_content = chat_request.messages[-1].content

    logger.info(
        "chat_request_received",
        session_id=session.id,
        content_length=len(new_user_content),
    )

    try:
        history = await _load_history(session.id)
        user_messages = history + [{"role": "user", "content": new_user_content}]

        # Check if builder is already active
        builder_state = await _load_builder_state(session.id)

        if builder_state is not None:
            # Builder is active — route user intent
            return await _handle_builder_phase(
                session, user_messages, new_user_content, builder_state,
            )

        # Builder not started yet — run Gatherer
        gatherer = GathererAgent(llm=llm_service)
        gatherer_output = await gatherer.run(
            messages=user_messages,
            user_id=str(session.user_id),
            session_id=session.id,
        )

        if gatherer_output.status == "gathering":
            # Still collecting requirements
            answer = gatherer_output.content
            await _save_turn(session.id, new_user_content, answer)
            return ChatResponse(
                messages=[Message(role="assistant", content=answer)],
                questions=gatherer_output.questions,
            )

        # Gatherer returned "ready" — initialize builder and run Layer 1
        requirements = gatherer_output.requirements
        builder_state = BuilderState(layer="select_pois")

        # Store requirements in builder state for cross-turn access
        if requirements:
            builder_state.requirements = StoredRequirements(
                destination=requirements.destination,
                duration_days=requirements.duration_days,
                budget_level=requirements.budget_level,
                travel_style=requirements.travel_style,
                group_type=requirements.group_type,
                pace=requirements.pace,
                travel_dates=requirements.travel_dates,
                special_requests=requirements.special_requests,
            )
            if requirements.group_type:
                builder_state.preferences.explicit.append(f"同行: {requirements.group_type}")
            if requirements.pace:
                builder_state.preferences.explicit.append(f"节奏: {requirements.pace}")
            if requirements.special_requests:
                builder_state.preferences.explicit.append(requirements.special_requests)

        return await _run_builder_layer(
            session, user_messages, new_user_content,
            builder_state, requirements,
        )

    except Exception as e:
        logger.exception("chat_request_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_builder_phase(
    session: Session,
    user_messages: list[dict],
    new_user_content: str,
    builder_state: BuilderState,
) -> ChatResponse:
    """Handle user messages when the builder is already active."""
    gatherer = GathererAgent(llm=llm_service)
    route_result = await gatherer.route(
        messages=user_messages,
        builder_state=builder_state,
        user_id=str(session.user_id),
        session_id=session.id,
    )

    # Update preferences from routing
    for pref in route_result.preferences_update:
        if pref not in builder_state.preferences.inferred:
            builder_state.preferences.inferred.append(pref)

    # Determine target layer
    if route_result.action == "advance":
        builder_state.layer = _next_layer(builder_state.layer)
    elif route_result.action == "back":
        builder_state.layer = route_result.next_layer
    # "modify" keeps the current layer

    # Use requirements stored in builder state
    requirements = _requirements_from_builder_state(builder_state)

    return await _run_builder_layer(
        session, user_messages, new_user_content,
        builder_state, requirements,
    )


async def _run_builder_layer(
    session: Session,
    user_messages: list[dict],
    new_user_content: str,
    builder_state: BuilderState,
    requirements: TravelRequirements | None,
) -> ChatResponse:
    """Execute the current builder layer and return response."""
    orchestrator = BuilderOrchestrator(
        llm=llm_service,
        memory=memory_service,
        user_id=session.user_id,
        session_id=session.id,
    )

    answer, builder_resp, updated_state = await orchestrator.run(
        messages=user_messages,
        state=builder_state,
        requirements=requirements,
    )

    # Persist state and turn
    await _save_builder_state(session.id, updated_state)
    await _save_turn(session.id, new_user_content, answer)

    return ChatResponse(
        messages=[Message(role="assistant", content=answer)],
        builder=builder_resp,
    )


def _requirements_from_builder_state(state: BuilderState) -> TravelRequirements | None:
    """Convert stored requirements back to TravelRequirements."""
    stored = state.requirements
    if not stored.destination:
        return None
    return TravelRequirements(
        destination=stored.destination,
        duration_days=stored.duration_days,
        budget_level=stored.budget_level,
        travel_style=stored.travel_style,
        group_type=stored.group_type,
        pace=stored.pace,
        travel_dates=stored.travel_dates,
        special_requests=stored.special_requests,
    )


# ------------------------------------------------------------------
# Streaming endpoint
# ------------------------------------------------------------------


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat_stream"][0])
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Stream chat response. Builder layers that use tools stream progress events."""
    new_user_content = chat_request.messages[-1].content

    logger.info(
        "stream_chat_request_received",
        session_id=session.id,
        content_length=len(new_user_content),
    )

    history = await _load_history(session.id)
    user_messages = history + [{"role": "user", "content": new_user_content}]

    builder_state = await _load_builder_state(session.id)
    session_id = session.id

    if builder_state is None:
        # Gatherer phase (non-streaming)
        gatherer = GathererAgent(llm=llm_service)
        gatherer_output = await gatherer.run(
            messages=user_messages,
            user_id=str(session.user_id),
            session_id=session.id,
        )

        if gatherer_output.status == "gathering":
            async def gathering_generator():
                event = {
                    "type": "gathering",
                    "content": gatherer_output.content,
                    "questions": [q.model_dump() for q in gatherer_output.questions],
                }
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'answer', 'content': gatherer_output.content}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                await _save_turn(session_id, new_user_content, gatherer_output.content)

            return StreamingResponse(
                gathering_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        # Initialize builder
        requirements = gatherer_output.requirements
        builder_state = BuilderState(layer="select_pois")
        if requirements:
            builder_state.requirements = StoredRequirements(
                destination=requirements.destination,
                duration_days=requirements.duration_days,
                budget_level=requirements.budget_level,
                travel_style=requirements.travel_style,
                group_type=requirements.group_type,
                pace=requirements.pace,
                travel_dates=requirements.travel_dates,
                special_requests=requirements.special_requests,
            )
            if requirements.group_type:
                builder_state.preferences.explicit.append(f"同行: {requirements.group_type}")
            if requirements.pace:
                builder_state.preferences.explicit.append(f"节奏: {requirements.pace}")
            if requirements.special_requests:
                builder_state.preferences.explicit.append(requirements.special_requests)
    else:
        # Builder active — route intent
        gatherer = GathererAgent(llm=llm_service)
        route_result = await gatherer.route(
            messages=user_messages,
            builder_state=builder_state,
            user_id=str(session.user_id),
            session_id=session.id,
        )
        for pref in route_result.preferences_update:
            if pref not in builder_state.preferences.inferred:
                builder_state.preferences.inferred.append(pref)
        if route_result.action == "advance":
            builder_state.layer = _next_layer(builder_state.layer)
        elif route_result.action == "back":
            builder_state.layer = route_result.next_layer
        requirements = _requirements_from_builder_state(builder_state)

    # Run builder layer (non-streaming for now, stream the final result)
    orchestrator = BuilderOrchestrator(
        llm=llm_service,
        memory=memory_service,
        user_id=session.user_id,
        session_id=session.id,
    )

    async def builder_generator():
        try:
            answer, builder_resp, updated_state = await orchestrator.run(
                messages=user_messages,
                state=builder_state,
                requirements=requirements,
            )

            # Emit builder event
            if builder_resp:
                builder_event = {
                    "type": "builder",
                    "layer": builder_resp.layer,
                    "data": builder_resp.data.model_dump() if builder_resp.data else None,
                }
                yield f"data: {json.dumps(builder_event, ensure_ascii=False)}\n\n"

            # Emit answer
            yield f"data: {json.dumps({'type': 'answer', 'content': answer}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

            await _save_builder_state(session_id, updated_state)
            await _save_turn(session_id, new_user_content, answer)

        except Exception as e:
            logger.exception("stream_builder_failed", session_id=session_id, error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        builder_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
