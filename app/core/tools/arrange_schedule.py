"""arrange_schedule tool — creates detailed day-by-day time schedules.

Wraps ArrangeExecutor logic: runs an internal AgentLoop with route_calculator,
then yields the schedule to the user for confirmation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import json_repair
import json
from pydantic import ValidationError

from app.core.agent.loop import AgentLoop
from app.core.agent.state import TripPlanningState
from app.core.logging import logger
from app.core.tools.base import InteractiveTool, ToolResult, ToolRegistry
from app.schemas.builder import ArrangePayload
from app.services.llm.service import LLMService
from app.services.memory import MemoryService

_ARRANGE_PROMPT = (
    Path(__file__).resolve().parents[1] / "prompts" / "arrange.md"
).read_text(encoding="utf-8")


class ArrangeScheduleTool(InteractiveTool):
    """Yield-to-user tool that arranges detailed timing and routes."""

    name = "arrange_schedule"
    description = (
        "Create a detailed day-by-day schedule with timing and transport info. "
        "Call this after the user has confirmed day groupings from present_groups."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "hint": {
                "type": "string",
                "description": "Optional scheduling hint, e.g. '第二天下午有雨，安排室内'",
            },
        },
        "required": [],
    }

    def __init__(
        self,
        llm: LLMService,
        memory: MemoryService,
        internal_tools: ToolRegistry,
        user_id: int | None = None,
        session_id: str | None = None,
    ) -> None:
        self._llm = llm
        self._memory = memory
        self._internal_tools = internal_tools
        self._user_id = user_id
        self._session_id = session_id

    async def run(self, args: dict[str, Any], state: TripPlanningState) -> ToolResult:
        if not state.day_groups:
            return ToolResult(content="错误：还没有分天方案，请先调用 present_groups。")
        if state.schedule and not args.get("hint"):
            return ToolResult(
                content="时间线已安排且用户已确认，无需重复。请调用 confirm_trip 保存行程。"
            )

        groups_context = _format_groups(state)
        extra = f"\n## 每天的分组安排\n{groups_context}"
        hint = args.get("hint", "")
        if hint:
            extra += f"\n\n## Agent 提示\n{hint}"

        system_prompt = self._build_prompt(state, extra)

        agent = AgentLoop(
            llm=self._llm,
            tools=self._internal_tools,
            memory=self._memory,
            system_prompt=system_prompt,
            max_steps=8,
        )

        agent_state = await agent.run(
            user_messages=[{"role": "user", "content": "请安排详细的每日时间线。"}],
            user_id=str(self._user_id) if self._user_id else None,
            session_id=self._session_id,
        )

        raw_answer = agent_state.final_answer or ""
        parsed = _parse_json(raw_answer)

        if parsed is None:
            if state.schedule:
                logger.warning("arrange_parse_failed_reusing", raw_preview=raw_answer[:200])
                return ToolResult(
                    content="时间安排解析出现问题，使用已有方案。",
                    yield_to_user=True,
                    ui_payload=state.schedule,
                    layer="arrange",
                )
            logger.warning("arrange_parse_failed", raw_preview=raw_answer[:200])
            return ToolResult(content="时间安排生成出现问题，请重试。")

        message = parsed.get("message", "")

        try:
            arrange_data = ArrangePayload(
                days=parsed.get("days", []),
                tips=parsed.get("tips", []),
                budget_estimate=parsed.get("budget_estimate", ""),
            )
        except (ValidationError, TypeError):
            return ToolResult(content=raw_answer)

        state.schedule = arrange_data

        logger.info("arrange_schedule_done", day_count=len(arrange_data.days))

        return ToolResult(
            content=message,
            yield_to_user=True,
            ui_payload=arrange_data,
            layer="arrange",
        )

    def _build_prompt(self, state: TripPlanningState, extra: str) -> str:
        parts = [_ARRANGE_PROMPT]
        prefs = state.preferences_prompt_section()
        if prefs:
            parts.append(prefs)
        req = _format_requirements(state.requirements)
        if req:
            parts.append(req)
        parts.append(extra)
        return "\n".join(parts)


def _format_requirements(req: Any) -> str:
    if not req.destination:
        return ""
    lines = ["\n## 用户旅行需求"]
    lines.append(f"- 目的地: {req.destination}")
    lines.append(f"- 天数: {req.duration_days}天")
    if req.budget_level:
        lines.append(f"- 预算: {req.budget_level}")
    if req.travel_style:
        lines.append(f"- 偏好: {'、'.join(req.travel_style)}")
    return "\n".join(lines)


def _format_groups(state: TripPlanningState) -> str:
    poi_map = {p.id: p for p in state.search_results}
    lines = []
    for group in state.day_groups:
        lines.append(f"\n### 第{group.day}天：{group.theme}")
        for pid in group.items:
            poi = poi_map.get(pid)
            if poi:
                lines.append(f"  - {poi.name} ({poi.category}, {poi.meta.duration})")
            else:
                lines.append(f"  - {pid} (未知)")
    return "\n".join(lines)


def _parse_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        try:
            result = json_repair.loads(text[first:last + 1])
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    return None
