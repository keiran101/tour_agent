"""Pydantic schemas for the interactive trip builder flow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Layer 1: POI selection
# ------------------------------------------------------------------

class POIMeta(BaseModel):
    """Numeric/factual metadata for a POI card."""

    rating: float | None = None
    price: str = ""
    duration: str = ""
    distance: str = ""


class POIOption(BaseModel):
    """A single POI card shown in the selection layer."""

    id: str = Field(..., description="Unique identifier (used to reference in later layers)")
    name: str
    category: Literal["attraction", "restaurant", "hotel", "shopping", "activity"]
    brief: str = Field(..., description="One-line description")
    reason: str = Field(default="", description="Why recommended / why not")
    meta: POIMeta = Field(default_factory=POIMeta)


class SelectPOIsPayload(BaseModel):
    """Structured data for Layer 1: POI selection."""

    recommended: list[POIOption] = Field(default_factory=list)
    alternatives: list[POIOption] = Field(default_factory=list)


# ------------------------------------------------------------------
# Layer 2: Day grouping
# ------------------------------------------------------------------

class DayGroup(BaseModel):
    """One day's worth of grouped POIs."""

    day: int
    theme: str
    reason: str = Field(default="", description="Why grouped this way")
    items: list[str] = Field(default_factory=list, description="POI ids assigned to this day")


class GroupDaysPayload(BaseModel):
    """Structured data for Layer 2: day grouping."""

    days: list[DayGroup] = Field(default_factory=list)
    suggestion: str = Field(default="", description="Agent's additional tip")


# ------------------------------------------------------------------
# Layer 3: Time arrangement
# ------------------------------------------------------------------

class ScheduledActivity(BaseModel):
    """A time-bound activity within a day."""

    time: str = Field(..., description="e.g. '09:00-12:00'")
    poi_id: str
    name: str = ""
    transport_to_next: str = ""


class DaySchedule(BaseModel):
    """Full schedule for one day."""

    day: int
    theme: str = ""
    activities: list[ScheduledActivity] = Field(default_factory=list)


class ArrangePayload(BaseModel):
    """Structured data for Layer 3: time arrangement."""

    days: list[DaySchedule] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)
    budget_estimate: str = ""


# ------------------------------------------------------------------
# Builder response (returned to frontend)
# ------------------------------------------------------------------

BuilderLayer = Literal["select_pois", "group_days", "arrange", "confirm"]


class BuilderResponse(BaseModel):
    """Structured builder payload included in ChatResponse.

    The frontend uses `layer` to decide which UI to render (cards, drag-drop, timeline).
    `data` contains the layer-specific payload.
    """

    layer: BuilderLayer
    data: SelectPOIsPayload | GroupDaysPayload | ArrangePayload | None = None


# ------------------------------------------------------------------
# Builder state (persisted in session for backtracking)
# ------------------------------------------------------------------

class SessionPreferences(BaseModel):
    """Accumulated user preferences for the session."""

    explicit: list[str] = Field(default_factory=list, description="User explicitly stated")
    inferred: list[str] = Field(default_factory=list, description="Inferred from behavior")


class StoredRequirements(BaseModel):
    """Subset of travel requirements stored in builder state for cross-turn access."""

    destination: str = ""
    duration_days: int = 3
    budget_level: str = ""
    travel_style: list[str] = Field(default_factory=list)
    group_type: str = ""
    pace: str = ""
    travel_dates: str = ""
    special_requests: str = ""


class BuilderState(BaseModel):
    """Full builder state persisted in the session."""

    layer: BuilderLayer = "select_pois"
    requirements: StoredRequirements = Field(default_factory=StoredRequirements)
    preferences: SessionPreferences = Field(default_factory=SessionPreferences)
    all_pois: list[POIOption] = Field(default_factory=list, description="All POIs found")
    selected_ids: list[str] = Field(default_factory=list, description="User's selected POI ids")
    day_groups: list[DayGroup] = Field(default_factory=list)
    schedule: ArrangePayload | None = None

    def get_selected_pois(self) -> list[POIOption]:
        """Return POIOption objects for selected ids."""
        id_set = set(self.selected_ids)
        return [p for p in self.all_pois if p.id in id_set]

    def preferences_prompt_section(self) -> str:
        """Format preferences as a system prompt section."""
        lines: list[str] = []
        if not self.preferences.explicit and not self.preferences.inferred:
            return ""
        lines.append("\n## 本次用户偏好")
        for p in self.preferences.explicit:
            lines.append(f"- {p}")
        for p in self.preferences.inferred:
            lines.append(f"- [推断] {p}")
        return "\n".join(lines)
