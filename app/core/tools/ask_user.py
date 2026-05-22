"""ask_user tool — collects travel requirements via structured questions.

Wraps the GatheringExecutor logic: calls LLM with gatherer prompt,
returns questions (yield) or signals requirements ready (no yield).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.agent.state import TripPlanningState
from app.core.logging import logger
from app.core.tools.base import InteractiveTool, ToolResult
from app.schemas.builder import StoredRequirements
from app.schemas.gatherer import GathererOutput
from app.services.llm.service import LLMService

_GATHERER_PROMPT = (
    Path(__file__).resolve().parents[1] / "prompts" / "gatherer.md"
).read_text(encoding="utf-8")


class AskUserTool(InteractiveTool):
    """Yield-to-user tool that asks the user structured questions."""

    name = "ask_user"
    description = (
        "Ask the user questions to collect travel requirements "
        "(destination, duration, budget, style, etc.). "
        "Call this when you need more information from the user."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "context": {
                "type": "string",
                "description": "Brief description of what information is still needed",
            },
        },
        "required": [],
    }

    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    async def run(self, args: dict[str, Any], state: TripPlanningState) -> ToolResult:
        messages = self._build_messages(args, state)

        try:
            response = await self._llm.call(
                messages=messages,
                tools=None,
                temperature=0.3,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or "{}"
            logger.debug("ask_user_raw_output", raw=raw[:500])
            output = GathererOutput.model_validate_json(raw)
        except (ValidationError, Exception) as e:
            logger.error("ask_user_failed", error=str(e))
            return ToolResult(content="需求收集出现问题，请用户重新描述旅行需求。")

        if output.status == "gathering":
            logger.info("ask_user_gathering", question_count=len(output.questions))
            return ToolResult(
                content=output.content,
                yield_to_user=True,
                ui_payload=_QuestionsPayload(questions=output.questions),
                layer="gathering",
            )

        # Ready — store requirements into state
        logger.info("ask_user_ready", has_requirements=output.requirements is not None)
        if output.requirements:
            state.requirements = StoredRequirements(
                destination=output.requirements.destination,
                duration_days=output.requirements.duration_days,
                budget_level=output.requirements.budget_level,
                travel_style=output.requirements.travel_style,
                group_type=output.requirements.group_type,
                pace=output.requirements.pace,
                travel_dates=output.requirements.travel_dates,
                special_requests=output.requirements.special_requests,
            )
            if output.requirements.group_type:
                state.preferences.explicit.append(f"同行: {output.requirements.group_type}")
            if output.requirements.pace:
                state.preferences.explicit.append(f"节奏: {output.requirements.pace}")
            if output.requirements.special_requests:
                state.preferences.explicit.append(output.requirements.special_requests)

        return ToolResult(
            content=f"需求收集完成：{state.summary()}。可以继续下一步。",
        )

    def _build_messages(
        self, args: dict[str, Any], state: TripPlanningState,
    ) -> list[dict[str, Any]]:
        parts = [_GATHERER_PROMPT]
        req_section = _format_requirements(state.requirements)
        if req_section:
            parts.append(req_section)
        prefs = state.preferences_prompt_section()
        if prefs:
            parts.append(prefs)

        context_hint = args.get("context", "")
        if context_hint:
            parts.append(f"\n## Agent 补充\n{context_hint}")

        return [{"role": "system", "content": "\n".join(parts)}]


def _format_requirements(req: StoredRequirements) -> str:
    if not req.destination:
        return ""
    lines = ["\n## 已收集的需求"]
    lines.append(f"- 目的地: {req.destination}")
    lines.append(f"- 天数: {req.duration_days}天")
    if req.budget_level:
        lines.append(f"- 预算: {req.budget_level}")
    if req.travel_style:
        lines.append(f"- 偏好: {'、'.join(req.travel_style)}")
    if req.group_type:
        lines.append(f"- 同行: {req.group_type}")
    return "\n".join(lines)


class _QuestionsPayload:
    """Adapter to carry questions as ui_payload (has model_dump for SSE)."""

    def __init__(self, questions: list) -> None:
        self.questions = questions

    def model_dump(self) -> dict[str, Any]:
        return {"questions": [q.model_dump() for q in self.questions]}
