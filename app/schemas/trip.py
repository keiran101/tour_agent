"""Trip planning request/response schemas.

Defines the structured itinerary format that the agent outputs via the save_trip tool,
and the API response schemas for trip CRUD endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.base import BaseResponse


class TimeSlot(str, Enum):
    morning = "morning"
    lunch = "lunch"
    afternoon = "afternoon"
    dinner = "dinner"
    evening = "evening"


class ActivityCategory(str, Enum):
    attraction = "attraction"
    restaurant = "restaurant"
    hotel = "hotel"
    shopping = "shopping"
    transport = "transport"
    activity = "activity"


class TripStatus(str, Enum):
    draft = "draft"
    confirmed = "confirmed"
    completed = "completed"


class Activity(BaseModel):
    """A single activity within a day plan."""

    time_slot: TimeSlot
    name: str = Field(..., max_length=200)
    category: ActivityCategory = ActivityCategory.attraction
    description: str = Field(default="", max_length=1000)
    duration_minutes: int = Field(default=60, ge=10, le=720)
    location: str | None = Field(default=None, max_length=500)
    tips: str | None = Field(default=None, max_length=500)


class DayPlan(BaseModel):
    """Plan for a single day of the trip."""

    day: int = Field(..., ge=1, le=30)
    theme: str = Field(..., max_length=100)
    activities: list[Activity] = Field(..., min_length=1)
    transport_tips: str | None = Field(default=None, max_length=500)


class Itinerary(BaseModel):
    """Complete structured itinerary — the core data the agent produces."""

    destination: str = Field(..., max_length=100)
    total_days: int = Field(..., ge=1, le=30)
    days: list[DayPlan] = Field(..., min_length=1)
    tips: list[str] = Field(default_factory=list)
    budget_estimate: str | None = Field(default=None, max_length=500)


class TripCreate(BaseModel):
    """Arguments for creating a trip (used by save_trip tool)."""

    title: str = Field(..., min_length=1, max_length=200)
    destination: str = Field(..., max_length=100)
    total_days: int = Field(..., ge=1, le=30)
    days: list[DayPlan]
    tips: list[str] = Field(default_factory=list)
    budget_estimate: str | None = None


class TripUpdate(BaseModel):
    """Partial update for a trip."""

    title: str | None = Field(default=None, max_length=200)
    status: TripStatus | None = None
    days: list[DayPlan] | None = None
    tips: list[str] | None = None
    budget_estimate: str | None = None


class TripResponse(BaseResponse):
    """Full trip data returned by the API."""

    id: str
    user_id: int
    session_id: str | None = None
    title: str
    destination: str
    total_days: int
    status: TripStatus
    itinerary: Itinerary
    created_at: datetime
    updated_at: datetime


class TripListResponse(BaseResponse):
    """List of trips for a user."""

    trips: list[TripResponse]
    total: int
