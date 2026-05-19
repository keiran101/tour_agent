"""Confirm executor — saves the finalized trip to database."""

import json
from typing import Any

from app.core.agent.executors.base import BaseExecutor, ExecutorResult
from app.core.logging import logger
from app.core.tools import create_tool_registry
from app.schemas.builder import BuilderResponse, BuilderState


class ConfirmExecutor(BaseExecutor):
    """Saves the finalized trip via the save_trip tool."""

    async def run(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
    ) -> ExecutorResult:
        """Show confirmation card, or save trip if user already confirmed."""
        if not state.schedule:
            return ExecutorResult(message="还没有完成时间安排，无法保存。")

        destination = state.requirements.destination
        total_days = state.requirements.duration_days or len(state.schedule.days)
        title = f"{destination}{total_days}日游"

        if not state.confirmed:
            builder_resp = BuilderResponse(layer="confirm", data=state.schedule)
            return ExecutorResult(
                message=f"行程安排已完成！请确认 {title} 的整体方案，确认无误后我帮你保存到行程列表。",
                builder_response=builder_resp,
            )

        tools = create_tool_registry(user_id=self._user_id, session_id=self._session_id)
        save_args = _build_save_trip_args(state, destination, total_days, title)
        result = await tools.execute("save_trip", json.dumps(save_args, ensure_ascii=False))

        logger.info("confirm_saved", result=result[:200])

        message = f"行程已保存！{title} — 你可以随时在「我的行程」中查看和修改。"
        return ExecutorResult(message=message)


def _build_save_trip_args(
    state: BuilderState,
    destination: str,
    total_days: int,
    title: str,
) -> dict[str, Any]:
    poi_map = {p.id: p for p in state.all_pois}
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
