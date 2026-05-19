"""Group days executor — groups selected POIs into days."""

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.agent.executors.base import BaseExecutor, ExecutorResult
from app.core.logging import logger
from app.schemas.builder import (
    BuilderResponse,
    BuilderState,
    DayGroup,
    GroupDaysPayload,
    POIOption,
)

_GROUP_PROMPT = (
    Path(__file__).resolve().parents[2] / "prompts" / "group.md"
).read_text(encoding="utf-8")


class GroupDaysExecutor(BaseExecutor):
    """Groups selected POIs into days — pure LLM reasoning, no tools."""

    async def run(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
    ) -> ExecutorResult:
        """Group selected POIs into days via pure LLM reasoning."""
        selected_pois = state.get_selected_pois()
        if not selected_pois:
            return ExecutorResult(message="还没有选定的地点，请先完成景点选择。")

        poi_context = _format_pois(selected_pois)
        duration = state.requirements.duration_days or 3

        extra_context = f"\n## 用户选定的 POI 列表\n{poi_context}\n\n## 旅行天数\n{duration} 天"
        system_prompt = self._build_system_prompt(_GROUP_PROMPT, state, extra_context)

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
            if state.day_groups:
                payload = GroupDaysPayload(days=state.day_groups, suggestion="")
                builder_resp = BuilderResponse(layer="group_days", data=payload)
                logger.warning("group_days_parse_failed_reusing_state", raw_preview=raw[:200])
                return ExecutorResult(
                    message="分组信息解析出现问题，以下是当前的分组方案：",
                    builder_response=builder_resp,
                )
            logger.warning("group_days_parse_failed_no_state", raw_preview=raw[:200])
            return ExecutorResult(message="抱歉，分组方案生成出现问题，请稍后重试。")

        message = parsed.get("message", "")
        suggestion = parsed.get("suggestion", "")

        days = []
        for d in parsed.get("days", []):
            try:
                days.append(DayGroup(**d))
            except (ValidationError, TypeError):
                continue

        state.day_groups = days

        payload = GroupDaysPayload(days=days, suggestion=suggestion)
        builder_resp = BuilderResponse(layer="group_days", data=payload)

        logger.info("group_days_done", day_count=len(days))

        return ExecutorResult(message=message, builder_response=builder_resp)


def _format_pois(pois: list[POIOption]) -> str:
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
