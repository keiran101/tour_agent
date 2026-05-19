"""Arrange executor — adds timing and routes to day groups."""

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.agent.executors.base import BaseExecutor, ExecutorResult
from app.core.agent.loop import AgentLoop
from app.core.logging import logger
from app.core.tools import create_tool_registry
from app.schemas.builder import (
    ArrangePayload,
    BuilderResponse,
    BuilderState,
)

_ARRANGE_PROMPT = (
    Path(__file__).resolve().parents[2] / "prompts" / "arrange.md"
).read_text(encoding="utf-8")


class ArrangeExecutor(BaseExecutor):
    """Arranges detailed timing with route calculation."""

    async def run(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
    ) -> ExecutorResult:
        """Arrange timing and routes for each day's POIs."""
        if not state.day_groups:
            return ExecutorResult(message="还没有分组信息，请先确认每天的安排。")

        groups_context = _format_groups(state)
        extra_context = f"\n## 每天的分组安排\n{groups_context}"
        system_prompt = self._build_system_prompt(_ARRANGE_PROMPT, state, extra_context)

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
            if state.schedule:
                builder_resp = BuilderResponse(layer="arrange", data=state.schedule)
                logger.warning("arrange_parse_failed_reusing_state", raw_preview=raw_answer[:200])
                return ExecutorResult(
                    message="时间安排解析出现问题，以下是当前的安排方案：",
                    builder_response=builder_resp,
                )
            logger.warning("arrange_parse_failed_no_state", raw_preview=raw_answer[:200])
            return ExecutorResult(message="抱歉，时间安排生成出现问题，请稍后重试。")

        message = parsed.get("message", "")

        try:
            arrange_data = ArrangePayload(
                days=parsed.get("days", []),
                tips=parsed.get("tips", []),
                budget_estimate=parsed.get("budget_estimate", ""),
            )
        except (ValidationError, TypeError):
            return ExecutorResult(message=raw_answer)

        state.schedule = arrange_data

        builder_resp = BuilderResponse(layer="arrange", data=arrange_data)
        logger.info("arrange_done", day_count=len(arrange_data.days))

        return ExecutorResult(message=message, builder_response=builder_resp)


def _format_groups(state: BuilderState) -> str:
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
