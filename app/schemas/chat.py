"""This file contains the chat schema for the application."""

import re
from typing import (
    List,
    Literal,
)

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from app.schemas.base import BaseResponse
from app.schemas.builder import BuilderResponse, DayGroup
from app.schemas.gatherer import Question


class BuilderAction(BaseModel):
    """Structured action from frontend UI interactions.

    Bypasses LLM intent classification for deterministic handling.
    """

    action: Literal["advance", "modify", "back"] = Field(..., description="Intent type")
    selected_ids: list[str] = Field(default_factory=list, description="POI ids selected by user (select_pois phase)")
    day_groups: list[DayGroup] = Field(default_factory=list, description="Reordered day groups (group_days phase)")
    target_phase: str | None = Field(default=None, description="Phase to go back to (back action)")


class Message(BaseModel):
    """Message model for chat endpoint.

    Attributes:
        role: The role of the message sender (user or assistant).
        content: The content of the message.
    """

    model_config = {"extra": "ignore"}

    role: Literal["user", "assistant", "system"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The content of the message", min_length=1, max_length=3000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate the message content.

        Args:
            v: The content to validate

        Returns:
            str: The validated content

        Raises:
            ValueError: If the content contains disallowed patterns
        """
        # Check for potentially harmful content
        if re.search(r"<script.*?>.*?</script>", v, re.IGNORECASE | re.DOTALL):
            raise ValueError("Content contains potentially harmful script tags")

        # Check for null bytes
        if "\0" in v:
            raise ValueError("Content contains null bytes")

        return v


class ChatRequest(BaseModel):
    """Request model for chat endpoint.

    Attributes:
        messages: List of messages in the conversation.
        builder_action: Optional structured action from frontend UI (bypasses LLM router).
    """

    messages: List[Message] = Field(
        ...,
        description="List of messages in the conversation",
        min_length=1,
    )
    builder_action: BuilderAction | None = Field(
        default=None,
        description="Structured builder action from frontend UI interactions",
    )


class ChatResponse(BaseResponse):
    """Response model for chat endpoint.

    Attributes:
        messages: List of messages in the conversation.
        questions: Structured questions from the Gatherer agent (empty when planning).
        builder: Structured builder payload for interactive trip building UI.
    """

    messages: List[Message] = Field(..., description="List of messages in the conversation")
    questions: List[Question] = Field(default_factory=list, description="Multiple-choice questions for user selection")
    builder: BuilderResponse | None = Field(default=None, description="Interactive builder data for frontend rendering")


class StreamResponse(BaseResponse):
    """Response model for streaming chat endpoint.

    Attributes:
        content: The content of the current chunk.
        done: Whether the stream is complete.
    """

    content: str = Field(default="", description="The content of the current chunk")
    done: bool = Field(default=False, description="Whether the stream is complete")


class HistoryMessage(BaseModel):
    """Message for conversation history display, including structured data."""

    role: str
    content: str = ""
    questions: list[Question] | None = None
    builder: BuilderResponse | None = None


class SessionDetailResponse(BaseResponse):
    """Response for loading a session's conversation history."""

    session_id: str
    name: str = ""
    phase: str = "gathering"
    messages: list[HistoryMessage] = Field(default_factory=list)


class SessionTitle(BaseModel):
    """Structured output schema for session title generation."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=60,
    )

    @field_validator("title")
    @classmethod
    def _normalize(cls, v: str) -> str:
        v = " ".join(v.split()).strip(" \"'`.,:;!?-")
        if not v:
            raise ValueError("empty title after normalization")
        return v
