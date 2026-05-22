"""confirm_trip tool — saves the finalized trip to database.

Wraps ConfirmExecutor logic: builds structured itinerary from state,
calls SaveTripTool/TripService to persist, marks state as saved.
"""

from __future__ import annotations

from typing import Any

from app.core.agent.state import TripPlanningState
from app.core.logging import logger
from app.core.tools.base import InteractiveTool, ToolResult
from app.schemas.trip import TripCreate
from app.services.trip import TripService


class ConfirmTripTool(InteractiveTool):
    """Yield-to-user tool that saves the trip and returns confirmation."""

    name = "confirm_trip"
    description = (
        "Save the finalized trip itinerary to the database. "
        "Call this after the user has confirmed the full schedule from arrange_schedule."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(
        self,
        trip_service: TripService,
        user_id: int,
        session_id: str | None = None,
    ) -> None:
        self._trip_service = trip_service
        self._user_id = user_id
        self._session_id = session_id

    async def run(self, args: dict[str, Any], state: TripPlanningState) -> ToolResult:
        if not state.schedule:
            return ToolResult(content="还没有完成时间安排，请先调用 arrange_schedule。")

        destination = state.requirements.destination
        total_days = state.requirements.duration_days or len(state.schedule.days)
        title = f"{destination}{total_days}日游"

        save_args = _build_save_trip_args(state, destination, total_days, title)

        try:
            data = TripCreate(**save_args)
            trip = await self._trip_service.create(
                user_id=self._user_id,
                data=data,
                session_id=self._session_id,
            )
            state.trip_saved = True
            logger.info("confirm_trip_saved", trip_id=trip.id, destination=destination)

            message = f"行程已保存！{title} — 你可以随时在「我的行程」中查看和修改。"
            return ToolResult(content=message, yield_to_user=True)

        except Exception as e:
            logger.error("confirm_trip_failed", error=str(e))
            return ToolResult(content=f"保存行程失败：{e}")


def _build_save_trip_args(
    state: TripPlanningState,
    destination: str,
    total_days: int,
    title: str,
) -> dict[str, Any]:
    poi_map = {p.id: p for p in state.search_results}
    days = []
    for day_sched in (state.schedule.days if state.schedule else []):
        activities = []
        for act in day_sched.activities:
            poi = poi_map.get(act.poi_id)
            cat = poi.category if poi else "activity"
            activities.append({
                "time_slot": _time_to_slot(act.time),
                "name": act.name or (poi.name if poi else act.poi_id),
                "category": cat,
                "description": poi.brief if poi else "",
                "duration_minutes": _estimate_duration(act.time),
                "tips": act.transport_to_next,
            })
        days.append({
            "day": day_sched.day,
            "theme": day_sched.theme,
            "activities": activities,
        })

    return {
        "title": title,
        "destination": destination,
        "total_days": total_days,
        "days": days,
        "tips": state.schedule.tips if state.schedule else [],
        "budget_estimate": state.schedule.budget_estimate if state.schedule else "",
    }


def _time_to_slot(time_str: str) -> str:
    try:
        hour = int(time_str.split(":")[0])
    except (ValueError, IndexError):
        return "morning"
    if hour < 11:
        return "morning"
    elif hour < 14:
        return "lunch"
    elif hour < 17:
        return "afternoon"
    elif hour < 19:
        return "dinner"
    else:
        return "evening"


def _estimate_duration(time_str: str) -> int:
    try:
        parts = time_str.split("-")
        start_h, start_m = map(int, parts[0].split(":"))
        end_h, end_m = map(int, parts[1].split(":"))
        return (end_h * 60 + end_m) - (start_h * 60 + start_m)
    except (ValueError, IndexError):
        return 60
