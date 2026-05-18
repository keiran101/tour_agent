"""Pydantic models for Gatherer agent structured output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Question(BaseModel):
    """A single multiple-choice question for the user."""

    id: str = Field(..., description="Semantic identifier, e.g. 'destination', 'budget'")
    text: str = Field(..., description="Question text shown to the user")
    options: list[str] = Field(default_factory=list, description="Choices; empty = free-text input")
    allow_multiple: bool = Field(default=False, description="Whether multiple options can be selected")


class TravelRequirements(BaseModel):
    """Structured travel requirements extracted from the conversation."""

    destination: str = Field(..., description="目的地")
    duration_days: int = Field(..., description="旅行天数")
    budget_level: str = Field(default="", description="预算档次: 经济型/舒适型/豪华型")
    travel_style: list[str] = Field(default_factory=list, description="偏好风格列表")
    group_type: str = Field(default="", description="同行: 独自/情侣/家庭/朋友")
    special_requests: str = Field(default="", description="特殊需求")
    pace: str = Field(default="", description="节奏偏好: 紧凑/适中/休闲")
    travel_dates: str = Field(default="", description="具体出行日期")


class GathererOutput(BaseModel):
    """Structured output from the Gatherer agent."""

    status: Literal["gathering", "ready"] = Field(
        ..., description="'gathering' = still asking; 'ready' = proceed to planning",
    )
    content: str = Field(
        ..., description="User-facing Chinese text (saved to DB as assistant message)",
    )
    questions: list[Question] = Field(default_factory=list)
    requirements: TravelRequirements | None = Field(default=None)
