"""Chat API endpoints.

Placeholder — will be wired to the self-built Agent loop
once app/core/agent/loop.py is implemented.
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
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.session import Session
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    StreamResponse,
)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Process a chat request via the Agent loop."""
    try:
        logger.info(
            "chat_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        # TODO: wire to app.core.agent.loop
        raise NotImplementedError("agent loop not yet implemented")

    except NotImplementedError:
        raise HTTPException(status_code=501, detail="agent loop not yet implemented")
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
    """Stream a chat response via the Agent loop."""
    try:
        logger.info(
            "stream_chat_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        # TODO: wire to app.core.agent.loop streaming
        raise NotImplementedError("agent streaming not yet implemented")

    except NotImplementedError:
        raise HTTPException(status_code=501, detail="agent streaming not yet implemented")
    except Exception as e:
        logger.exception("stream_chat_request_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
