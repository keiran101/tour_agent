"""Builder orchestrator — manages the multi-layer interactive trip planning flow.

Layers:
  1. select_pois  — Agent searches, presents recommended + alternatives
  2. group_days   — Agent groups selected POIs into days
  3. arrange      — Agent adds timing + routes
  4. confirm      — User confirms, save_trip called

The orchestrator picks the right prompt, runs the agent (with or without tools),
parses structured output, and updates BuilderState for persistence.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.agent.loop import AgentLoop
from app.core.config import settings
from app.core.logging import logger
from app.core.tools import create_tool_registry
from app.schemas.builder import (
    ArrangePayload,
    BuilderResponse,
    BuilderState,
    DayGroup,
    GroupDaysPayload,
    POIOption,
    SelectPOIsPayload,
)
from app.schemas.gatherer import TravelRequirements
from app.services.llm.service import LLMService
from app.services.memory import MemoryService

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_RECOMMEND_PROMPT = (_PROMPTS_DIR / "recommend.md").read_text(encoding="utf-8")
_GROUP_PROMPT = (_PROMPTS_DIR / "group.md").read_text(encoding="utf-8")
_ARRANGE_PROMPT = (_PROMPTS_DIR / "arrange.md").read_text(encoding="utf-8")


class BuilderOrchestrator:
    """Orchestrates the multi-layer trip building process.

    Each call to `run()` advances the builder by one layer (or handles
    user modifications within the current layer).
    """

    def __init__(
        self,
        llm: LLMService,
        memory: MemoryService,
        user_id: int | None = None,
        session_id: str | None = None,
    ) -> None:
        """Initialize with LLM, memory service, and session context."""
        self._llm = llm
        self._memory = memory
        self._user_id = user_id
        self._session_id = session_id

    async def run(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
        requirements: TravelRequirements | None = None,
    ) -> tuple[str, BuilderResponse | None, BuilderState]:
        """Execute the current builder layer.

        Args:
            messages: Full conversation history (user + assistant turns).
            state: Current builder state (loaded from DB).
            requirements: Travel requirements from Gatherer.

        Returns:
            Tuple of (assistant_message, builder_response, updated_state).
        """
        layer = state.layer

        logger.info(
            "builder_run",
            layer=layer,
            session_id=self._session_id,
            selected_count=len(state.selected_ids),
        )

        if layer == "select_pois":
            return await self._run_select_pois(messages, state, requirements)
        elif layer == "group_days":
            return await self._run_group_days(messages, state, requirements)
        elif layer == "arrange":
            return await self._run_arrange(messages, state, requirements)
        elif layer == "confirm":
            return await self._run_confirm(messages, state, requirements)
        else:
            return "系统错误：未知的规划阶段", None, state

    # ------------------------------------------------------------------
    # Layer 1: POI Selection
    # ------------------------------------------------------------------

    async def _run_select_pois(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
        requirements: TravelRequirements | None,
    ) -> tuple[str, BuilderResponse | None, BuilderState]:
        """Search for POIs and present recommendations."""
        system_prompt = self._build_system_prompt(_RECOMMEND_PROMPT, state, requirements)

        tools = create_tool_registry(user_id=self._user_id, session_id=self._session_id)

        agent = AgentLoop(
            llm=self._llm,
            tools=tools,
            memory=self._memory,
            system_prompt=system_prompt,
            max_steps=settings.AGENT_MAX_STEPS,
        )

        agent_state = await agent.run(
            user_messages=messages,
            user_id=str(self._user_id) if self._user_id else None,
            session_id=self._session_id,
        )

        raw_answer = agent_state.final_answer or ""
        parsed = self._parse_json_from_answer(raw_answer)

        if parsed is None:
            return raw_answer, None, state

        # Extract structured data
        message = parsed.get("message", "")
        recommended_raw = parsed.get("recommended", [])
        alternatives_raw = parsed.get("alternatives", [])

        recommended = [POIOption(**p) for p in recommended_raw if self._valid_poi(p)]
        alternatives = [POIOption(**p) for p in alternatives_raw if self._valid_poi(p)]

        # Update preferences if provided
        pref_update = parsed.get("preferences_update", {})
        if pref_update.get("inferred"):
            for item in pref_update["inferred"]:
                if item not in state.preferences.inferred:
                    state.preferences.inferred.append(item)

        # Update state
        state.all_pois = recommended + alternatives
        state.selected_ids = [p.id for p in recommended]

        payload = SelectPOIsPayload(recommended=recommended, alternatives=alternatives)
        builder_resp = BuilderResponse(layer="select_pois", data=payload)

        logger.info(
            "builder_select_pois_done",
            recommended_count=len(recommended),
            alternatives_count=len(alternatives),
        )

        return message, builder_resp, state

    # ------------------------------------------------------------------
    # Layer 2: Day Grouping
    # ------------------------------------------------------------------

    async def _run_group_days(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
        requirements: TravelRequirements | None,
    ) -> tuple[str, BuilderResponse | None, BuilderState]:
        """Group selected POIs into days."""
        selected_pois = state.get_selected_pois()
        if not selected_pois:
            return "还没有选定的地点，请先完成景点选择。", None, state

        # Build context with selected POIs
        poi_context = self._format_pois_for_prompt(selected_pois)
        duration = requirements.duration_days if requirements else 3

        extra_context = f"""
## 用户选定的 POI 列表
{poi_context}

## 旅行天数
{duration} 天
"""
        system_prompt = self._build_system_prompt(
            _GROUP_PROMPT, state, requirements, extra_context,
        )

        # No tools needed for grouping — pure reasoning
        response = await self._llm.call(
            messages=[
                {"role": "system", "content": system_prompt},
                *messages,
            ],
            tools=None,
            temperature=0.3,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        parsed = self._parse_json_from_answer(raw)

        if parsed is None:
            return raw, None, state

        message = parsed.get("message", "")
        days_raw = parsed.get("days", [])
        suggestion = parsed.get("suggestion", "")

        days = []
        for d in days_raw:
            try:
                days.append(DayGroup(**d))
            except (ValidationError, TypeError):
                continue

        # Update state
        state.day_groups = days
        state.layer = "group_days"

        payload = GroupDaysPayload(days=days, suggestion=suggestion)
        builder_resp = BuilderResponse(layer="group_days", data=payload)

        logger.info("builder_group_days_done", day_count=len(days))

        return message, builder_resp, state

    # ------------------------------------------------------------------
    # Layer 3: Time Arrangement
    # ------------------------------------------------------------------

    async def _run_arrange(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
        requirements: TravelRequirements | None,
    ) -> tuple[str, BuilderResponse | None, BuilderState]:
        """Arrange detailed timing with route calculation."""
        if not state.day_groups:
            return "还没有分组信息，请先确认每天的安排。", None, state

        # Build context with day groups and POI details
        groups_context = self._format_groups_for_prompt(state)
        extra_context = f"\n## 每天的分组安排\n{groups_context}"

        system_prompt = self._build_system_prompt(
            _ARRANGE_PROMPT, state, requirements, extra_context,
        )

        # Use route_calculator tool
        tools = create_tool_registry(user_id=self._user_id, session_id=self._session_id)

        agent = AgentLoop(
            llm=self._llm,
            tools=tools,
            memory=self._memory,
            system_prompt=system_prompt,
            max_steps=8,
        )

        agent_state = await agent.run(
            user_messages=messages,
            user_id=str(self._user_id) if self._user_id else None,
            session_id=self._session_id,
        )

        raw_answer = agent_state.final_answer or ""
        parsed = self._parse_json_from_answer(raw_answer)

        if parsed is None:
            return raw_answer, None, state

        message = parsed.get("message", "")

        try:
            arrange_data = ArrangePayload(
                days=parsed.get("days", []),
                tips=parsed.get("tips", []),
                budget_estimate=parsed.get("budget_estimate", ""),
            )
        except (ValidationError, TypeError):
            return raw_answer, None, state

        state.schedule = arrange_data

        builder_resp = BuilderResponse(layer="arrange", data=arrange_data)
        logger.info("builder_arrange_done", day_count=len(arrange_data.days))

        return message, builder_resp, state

    # ------------------------------------------------------------------
    # Layer 4: Confirm & Save
    # ------------------------------------------------------------------

    async def _run_confirm(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
        requirements: TravelRequirements | None,
    ) -> tuple[str, BuilderResponse | None, BuilderState]:
        """Save the finalized trip."""
        if not state.schedule:
            return "还没有完成时间安排，无法保存。", None, state

        tools = create_tool_registry(user_id=self._user_id, session_id=self._session_id)

        # Build save_trip arguments from state
        destination = requirements.destination if requirements else ""
        total_days = requirements.duration_days if requirements else len(state.schedule.days)
        title = f"{destination}{total_days}日游"

        save_args = self._build_save_trip_args(state, destination, total_days, title)

        result = await tools.execute("save_trip", json.dumps(save_args, ensure_ascii=False))

        logger.info("builder_confirm_saved", result=result[:200])

        message = f"行程已保存！{title} — 你可以随时在「我的行程」中查看和修改。"
        return message, BuilderResponse(layer="confirm", data=None), state

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(
        self,
        base_prompt: str,
        state: BuilderState,
        requirements: TravelRequirements | None,
        extra_context: str = "",
    ) -> str:
        """Assemble system prompt with preferences and requirements."""
        parts = [base_prompt]

        # Inject user preferences
        prefs_section = state.preferences_prompt_section()
        if prefs_section:
            parts.append(prefs_section)

        # Inject requirements
        if requirements:
            parts.append(self._format_requirements(requirements))

        if extra_context:
            parts.append(extra_context)

        return "\n".join(parts)

    @staticmethod
    def _format_requirements(req: TravelRequirements) -> str:
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
        if req.travel_dates:
            lines.append(f"- 日期: {req.travel_dates}")
        if req.special_requests:
            lines.append(f"- 特殊需求: {req.special_requests}")
        return "\n".join(lines)

    @staticmethod
    def _format_pois_for_prompt(pois: list[POIOption]) -> str:
        lines = []
        for p in pois:
            meta_parts = []
            if p.meta.rating:
                meta_parts.append(f"⭐{p.meta.rating}")
            if p.meta.price:
                meta_parts.append(p.meta.price)
            if p.meta.duration:
                meta_parts.append(p.meta.duration)
            meta_str = " | ".join(meta_parts)
            lines.append(f"- [{p.id}] {p.name} ({p.category}) — {p.brief} [{meta_str}]")
        return "\n".join(lines)

    def _format_groups_for_prompt(self, state: BuilderState) -> str:
        poi_map = {p.id: p for p in state.all_pois}
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

    @staticmethod
    def _build_save_trip_args(
        state: BuilderState,
        destination: str,
        total_days: int,
        title: str,
    ) -> dict[str, Any]:
        """Convert BuilderState.schedule into save_trip tool arguments."""
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

    @staticmethod
    def _parse_json_from_answer(text: str) -> dict[str, Any] | None:
        """Try to extract JSON from agent answer (may be wrapped in markdown)."""
        text = text.strip()
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try extracting from ```json ... ```
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass
        # Try extracting from ``` ... ```
        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass
        # Try finding first { ... last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(text[first_brace:last_brace + 1])
            except json.JSONDecodeError:
                pass
        logger.warning("builder_json_parse_failed", text_preview=text[:200])
        return None

    @staticmethod
    def _valid_poi(data: dict) -> bool:
        """Check if a dict has minimum fields for a POIOption."""
        return bool(data.get("id") and data.get("name") and data.get("category"))


# ------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------

def _time_to_slot(time_str: str) -> str:
    """Convert 'HH:MM-HH:MM' to a time_slot enum value."""
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
    """Estimate duration in minutes from 'HH:MM-HH:MM' format."""
    try:
        parts = time_str.split("-")
        start_h, start_m = map(int, parts[0].split(":"))
        end_h, end_m = map(int, parts[1].split(":"))
        return (end_h * 60 + end_m) - (start_h * 60 + start_m)
    except (ValueError, IndexError):
        return 60
