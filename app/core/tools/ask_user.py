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
            "user_input": {
                "type": "string",
                "description": "用户最新的消息原文（必须完整转述，不要概括）",
            },
            "context": {
                "type": "string",
                "description": "补充说明，如还缺哪些信息",
            },
        },
        "required": ["user_input"],
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
            if output.requirements:
                self._save_partial_requirements(state, output.requirements)
            logger.info(
                "ask_user_gathering",
                question_count=len(output.questions),
                destination=state.requirements.destination or "(empty)",
            )
            return ToolResult(
                content=output.content,
                yield_to_user=True,
                ui_payload=_QuestionsPayload(questions=output.questions),
                layer="gathering",
            )

        # Ready — store requirements into state
        if output.requirements:
            self._save_partial_requirements(state, output.requirements)
        logger.info(
            "ask_user_ready",
            destination=state.requirements.destination or "(empty)",
            summary=state.summary(),
        )

        return ToolResult(
            content=f"需求收集完成：{state.summary()}。可以继续下一步。",
        )

    @staticmethod
    def _save_partial_requirements(
        state: TripPlanningState, req: Any,
    ) -> None:
        """Merge gathered fields into state, preserving previously collected values."""
        current = state.requirements
        state.requirements = StoredRequirements(
            destination=req.destination or current.destination,
            duration_days=req.duration_days if req.duration_days else current.duration_days,
            budget_level=req.budget_level or current.budget_level,
            travel_style=req.travel_style or current.travel_style,
            group_type=req.group_type or current.group_type,
            pace=req.pace or current.pace,
            travel_dates=req.travel_dates or current.travel_dates,
            special_requests=req.special_requests or current.special_requests,
        )
        if req.group_type and f"同行: {req.group_type}" not in state.preferences.explicit:
            state.preferences.explicit.append(f"同行: {req.group_type}")
        if req.pace and f"节奏: {req.pace}" not in state.preferences.explicit:
            state.preferences.explicit.append(f"节奏: {req.pace}")
        if req.special_requests and req.special_requests not in state.preferences.explicit:
            state.preferences.explicit.append(req.special_requests)

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

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "\n".join(parts)},
        ]

        user_input = args.get("user_input", "")
        if user_input:
            messages.append({"role": "user", "content": user_input})
        else:
            messages.append({"role": "user", "content": "请开始收集旅行需求。"})

        return messages


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
