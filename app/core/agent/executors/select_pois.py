"""Select POIs executor — searches and presents recommended + alternative POIs."""

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.agent.executors.base import BaseExecutor, ExecutorResult
from app.core.agent.loop import AgentLoop
from app.core.config import settings
from app.core.logging import logger
from app.core.tools import create_tool_registry
from app.schemas.builder import (
    BuilderResponse,
    BuilderState,
    POIOption,
    SelectPOIsPayload,
)

_RECOMMEND_PROMPT = (
    Path(__file__).resolve().parents[2] / "prompts" / "recommend.md"
).read_text(encoding="utf-8")


class SelectPOIsExecutor(BaseExecutor):
    """Searches for POIs and presents recommendations."""

    async def run(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
    ) -> ExecutorResult:
        """Search POIs and return recommended + alternatives."""
        system_prompt = self._build_system_prompt(_RECOMMEND_PROMPT, state)
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
            if state.all_pois:
                selected_set = set(state.selected_ids)
                payload = SelectPOIsPayload(
                    recommended=[p for p in state.all_pois if p.id in selected_set],
                    alternatives=[p for p in state.all_pois if p.id not in selected_set],
                )
                builder_resp = BuilderResponse(layer="select_pois", data=payload)
                logger.warning("select_pois_parse_failed_reusing_state", raw_preview=raw_answer[:200])
                return ExecutorResult(
                    message="推荐信息解析出现问题，以下是当前的推荐列表：",
                    builder_response=builder_resp,
                )
            logger.warning("select_pois_parse_failed_no_state", raw_preview=raw_answer[:200])
            return ExecutorResult(message="抱歉，景点推荐出现问题，请重新描述你的需求。")

        message = parsed.get("message", "")
        recommended = _build_poi_list(parsed.get("recommended", []))
        alternatives = _build_poi_list(parsed.get("alternatives", []))

        pref_update = parsed.get("preferences_update", {})
        if pref_update.get("inferred"):
            for item in pref_update["inferred"]:
                if item not in state.preferences.inferred:
                    state.preferences.inferred.append(item)

        state.all_pois = recommended + alternatives
        state.selected_ids = [p.id for p in recommended]

        payload = SelectPOIsPayload(recommended=recommended, alternatives=alternatives)
        builder_resp = BuilderResponse(layer="select_pois", data=payload)

        logger.info(
            "select_pois_done",
            recommended_count=len(recommended),
            alternatives_count=len(alternatives),
        )

        return ExecutorResult(message=message, builder_response=builder_resp)


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
