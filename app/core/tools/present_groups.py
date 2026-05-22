"""present_groups tool — groups selected POIs into days.

Wraps GroupDaysExecutor logic: pure LLM reasoning to assign POIs to days,
then yields the grouping plan to the user for confirmation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import json_repair
from pydantic import ValidationError

from app.core.agent.state import TripPlanningState
from app.core.logging import logger
from app.core.tools.base import InteractiveTool, ToolResult
from app.schemas.builder import (
    DayGroup,
    GroupDaysPayload,
    POIOption,
)
from app.services.llm.service import LLMService

_GROUP_PROMPT = (
    Path(__file__).resolve().parents[1] / "prompts" / "group.md"
).read_text(encoding="utf-8")


class PresentGroupsTool(InteractiveTool):
    """Yield-to-user tool that presents day grouping to the user."""

    name = "present_groups"
    description = (
        "Group the user's selected POIs into days and present the grouping plan. "
        "Call this after the user has selected POIs from recommend_pois."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "hint": {
                "type": "string",
                "description": "Optional grouping hint from the user, e.g. '第一天想轻松一点'",
            },
        },
        "required": [],
    }

    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    async def run(self, args: dict[str, Any], state: TripPlanningState) -> ToolResult:
        if not state.selected_pois:
            return ToolResult(content="用户还没有选择景点，请先调用 recommend_pois。")

        poi_context = _format_pois(state.selected_pois)
        duration = state.requirements.duration_days or 3

        extra = f"\n## 用户选定的 POI 列表\n{poi_context}\n\n## 旅行天数\n{duration} 天"
        hint = args.get("hint", "")
        if hint:
            extra += f"\n\n## 用户提示\n{hint}"

        system_prompt = self._build_prompt(state, extra)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请将这些景点分配到{duration}天的行程中。"},
        ]

        response = await self._llm.call(
            messages=messages,
            tools=None,
            temperature=0.3,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        parsed = _parse_json(raw)

        if parsed is None:
            if state.day_groups:
                payload = GroupDaysPayload(days=state.day_groups, suggestion="")
                logger.warning("present_groups_parse_failed_reusing", raw_preview=raw[:200])
                return ToolResult(
                    content="分组信息解析出现问题，使用已有方案。",
                    yield_to_user=True,
                    ui_payload=payload,
                    layer="group_days",
                )
            logger.warning("present_groups_parse_failed", raw_preview=raw[:200])
            return ToolResult(content="分组方案生成出现问题，请重试。")

        message = parsed.get("message", "")
        suggestion = parsed.get("suggestion", "")

        days: list[DayGroup] = []
        for d in parsed.get("days", []):
            try:
                days.append(DayGroup(**d))
            except (ValidationError, TypeError):
                continue

        # Write state + cascading invalidation
        state.day_groups = days
        state.schedule = None

        payload = GroupDaysPayload(days=days, suggestion=suggestion)
        logger.info("present_groups_done", day_count=len(days))

        return ToolResult(
            content=message,
            yield_to_user=True,
            ui_payload=payload,
            layer="group_days",
        )

    def _build_prompt(self, state: TripPlanningState, extra: str) -> str:
        parts = [_GROUP_PROMPT]
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


def _format_pois(pois: list[POIOption]) -> str:
    lines = []
    for p in pois:
        meta_parts = []
        if p.meta.rating:
            meta_parts.append(f"rating:{p.meta.rating}")
        if p.meta.price:
            meta_parts.append(p.meta.price)
        if p.meta.duration:
            meta_parts.append(p.meta.duration)
        meta_str = " | ".join(meta_parts)
        lines.append(f"- [{p.id}] {p.name} ({p.category}) — {p.brief} [{meta_str}]")
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
