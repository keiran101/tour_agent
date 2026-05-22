"""recommend_pois tool — searches and presents POI recommendations.

Wraps SelectPOIsExecutor logic: runs an internal AgentLoop with POI/search
tools, then presents recommended + alternative POIs to the user.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.agent.loop import AgentLoop
from app.core.agent.state import TripPlanningState
from app.core.config import settings
from app.core.logging import logger
from app.core.tools.base import InteractiveTool, ToolResult, ToolRegistry
from app.schemas.builder import (
    POIOption,
    SelectPOIsPayload,
)
from app.services.llm.service import LLMService
from app.services.memory import MemoryService

_RECOMMEND_PROMPT = (
    Path(__file__).resolve().parents[1] / "prompts" / "recommend.md"
).read_text(encoding="utf-8")


class RecommendPoisTool(InteractiveTool):
    """Yield-to-user tool that searches POIs and presents selection cards."""

    name = "recommend_pois"
    description = (
        "Search for points of interest and present recommendations to the user. "
        "Call this after requirements are collected. "
        "Returns a POI selection card for user to choose from."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "focus": {
                "type": "string",
                "description": "Optional focus area, e.g. '美食' or '自然风光'",
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
        if not state.requirements.destination:
            return ToolResult(content="错误：还没有目的地信息，请先调用 ask_user 收集需求。")
        if state.selected_pois and not args.get("focus"):
            return ToolResult(
                content="景点已推荐且用户已选择，无需重复。请调用 present_groups 进行分天。"
            )

        system_prompt = self._build_prompt(state, args.get("focus", ""))

        agent = AgentLoop(
            llm=self._llm,
            tools=self._internal_tools,
            memory=self._memory,
            system_prompt=system_prompt,
            max_steps=settings.AGENT_MAX_STEPS,
        )

        agent_state = await agent.run(
            user_messages=[{"role": "user", "content": self._build_user_msg(state)}],
            user_id=str(self._user_id) if self._user_id else None,
            session_id=self._session_id,
        )

        raw_answer = agent_state.final_answer or ""
        parsed = _parse_json(raw_answer)

        if parsed is None:
            if state.search_results:
                payload = SelectPOIsPayload(
                    recommended=state.selected_pois or state.search_results[:8],
                    alternatives=state.search_results[8:] if not state.selected_pois else [],
                )
                logger.warning("recommend_pois_parse_failed_reusing", raw_preview=raw_answer[:200])
                return ToolResult(
                    content="推荐信息解析出现问题，使用已有数据。",
                    yield_to_user=True,
                    ui_payload=payload,
                    layer="select_pois",
                )
            logger.warning("recommend_pois_parse_failed", raw_preview=raw_answer[:200])
            return ToolResult(content="景点推荐出现问题，请重试。")

        message = parsed.get("message", "")
        recommended = _build_poi_list(parsed.get("recommended", []))
        alternatives = _build_poi_list(parsed.get("alternatives", []))

        pref_update = parsed.get("preferences_update", {})
        if pref_update.get("inferred"):
            for item in pref_update["inferred"]:
                if item not in state.preferences.inferred:
                    state.preferences.inferred.append(item)

        state.search_results = recommended + alternatives
        state.selected_pois = list(recommended)
        # Cascading invalidation
        state.day_groups = []
        state.schedule = None

        payload = SelectPOIsPayload(recommended=recommended, alternatives=alternatives)
        logger.info(
            "recommend_pois_done",
            recommended_count=len(recommended),
            alternatives_count=len(alternatives),
        )

        return ToolResult(
            content=message,
            yield_to_user=True,
            ui_payload=payload,
            layer="select_pois",
        )

    def _build_prompt(self, state: TripPlanningState, focus: str) -> str:
        parts = [_RECOMMEND_PROMPT]
        prefs = state.preferences_prompt_section()
        if prefs:
            parts.append(prefs)
        parts.append(_format_requirements(state.requirements))
        if focus:
            parts.append(f"\n## 重点关注\n{focus}")
        return "\n".join(parts)

    @staticmethod
    def _build_user_msg(state: TripPlanningState) -> str:
        r = state.requirements
        parts = [f"请为{r.destination}{r.duration_days}天旅行推荐景点。"]
        if r.travel_style:
            parts.append(f"偏好：{'、'.join(r.travel_style)}。")
        if r.budget_level:
            parts.append(f"预算：{r.budget_level}。")
        return "".join(parts)


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
    if req.group_type:
        lines.append(f"- 同行: {req.group_type}")
    if req.pace:
        lines.append(f"- 节奏: {req.pace}")
    return "\n".join(lines)


def _parse_json(text: str) -> dict[str, Any] | None:
    import json
    import json_repair

    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for marker in ("```json", "```"):
        idx = text.find(marker)
        if idx == -1:
            continue
        start = idx + len(marker)
        end = text.find("```", start)
        fragment = text[start:end].strip() if end != -1 else text[start:].strip()
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            pass
        try:
            result = json_repair.loads(fragment)
            if isinstance(result, dict):
                return result
        except Exception:
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


def _build_poi_list(items: list[dict]) -> list[POIOption]:
    result: list[POIOption] = []
    for p in items:
        if not (p.get("id") and p.get("name") and p.get("category")):
            continue
        try:
            result.append(POIOption(**p))
        except (ValidationError, TypeError):
            continue
    return result
