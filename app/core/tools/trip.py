"""save_trip tool — lets the agent persist a structured itinerary to the database."""

import json
from typing import Any

from app.core.logging import logger
from app.core.tools.base import Tool
from app.schemas.trip import TripCreate
from app.services.trip import TripService


class SaveTripTool(Tool):
    """Save a structured trip itinerary to the database.

    The agent calls this tool after it has gathered enough information and
    produced a complete itinerary.  User/session context is injected at
    construction time so the LLM only needs to supply the itinerary data.
    """

    name = "save_trip"
    description = (
        "Save a completed trip itinerary to the database. "
        "Call this AFTER you have planned the full itinerary. "
        "Pass the structured itinerary with title, destination, days, "
        "activities, tips, and optional budget estimate."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Trip title, e.g. '北京3日文化之旅'",
            },
            "destination": {
                "type": "string",
                "description": "Destination city/region, e.g. '北京'",
            },
            "total_days": {
                "type": "integer",
                "description": "Total number of days",
            },
            "days": {
                "type": "array",
                "description": "Day-by-day itinerary",
                "items": {
                    "type": "object",
                    "properties": {
                        "day": {"type": "integer", "description": "Day number (1-based)"},
                        "theme": {"type": "string", "description": "Theme for the day, e.g. '故宫与王府井'"},
                        "activities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "time_slot": {
                                        "type": "string",
                                        "enum": ["morning", "lunch", "afternoon", "dinner", "evening"],
                                    },
                                    "name": {"type": "string", "description": "Activity/place name"},
                                    "category": {
                                        "type": "string",
                                        "enum": ["attraction", "restaurant", "hotel", "shopping", "transport", "activity"],
                                    },
                                    "description": {"type": "string", "description": "Brief description"},
                                    "duration_minutes": {"type": "integer", "description": "Estimated duration in minutes"},
                                    "location": {"type": "string", "description": "Address or coordinates"},
                                    "tips": {"type": "string", "description": "Practical tips for this activity"},
                                },
                                "required": ["time_slot", "name", "category"],
                            },
                        },
                        "transport_tips": {"type": "string", "description": "Transport advice for the day"},
                    },
                    "required": ["day", "theme", "activities"],
                },
            },
            "tips": {
                "type": "array",
                "items": {"type": "string"},
                "description": "General travel tips",
            },
            "budget_estimate": {
                "type": "string",
                "description": "Budget estimate summary, e.g. '人均约3000元（含住宿、餐饮、门票）'",
            },
        },
        "required": ["title", "destination", "total_days", "days"],
    }

    def __init__(self, trip_service: TripService, user_id: int, session_id: str | None = None) -> None:
        self._trip_service = trip_service
        self._user_id = user_id
        self._session_id = session_id

    async def execute(self, **kwargs: Any) -> str:
        try:
            data = TripCreate(**kwargs)
        except Exception as e:
            logger.warning("save_trip_validation_failed", error=str(e))
            return f"Error: invalid itinerary data — {e}"

        try:
            trip = await self._trip_service.create(
                user_id=self._user_id,
                data=data,
                session_id=self._session_id,
            )
            logger.info("save_trip_success", trip_id=trip.id, destination=data.destination)
            return json.dumps(
                {"status": "saved", "trip_id": trip.id, "title": trip.title},
                ensure_ascii=False,
            )
        except Exception as e:
            logger.error("save_trip_db_failed", error=str(e))
            return f"Error: failed to save trip — {e}"
