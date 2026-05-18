"""Gatherer agent — conversation router for the multi-layer builder flow.

Responsibilities:
1. Collect travel requirements (gathering phase)
2. Route user intent to the correct builder layer
3. Detect backtracking ("我想换几个景点" → back to select_pois)
4. Extract preference updates from user messages
"""

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.logging import logger
from app.core.observability import get_langfuse
from app.schemas.builder import BuilderLayer, BuilderState
from app.schemas.gatherer import GathererOutput
from app.services.llm.service import LLMService

_GATHERER_PROMPT = (
    Path(__file__).resolve().parents[1] / "prompts" / "gatherer.md"
).read_text(encoding="utf-8")

_ROUTER_PROMPT = """# 角色
你是一个对话意图路由器。用户正在使用交互式行程构建器，你需要判断用户当前消息的意图。

# 当前构建器状态
- 当前层级: {current_layer}
- 已选景点数: {selected_count}
- 已分组天数: {grouped_days}

# 判断规则

## 用户想要前进到下一层 (action: "advance")
- "可以" / "确认" / "就这样" / "OK" / "下一步"
- 明确表示对当前结果满意

## 用户想要修改当前层 (action: "modify")
- 当前是 select_pois 层：加选/取消某个景点、问某个景点的详细信息
- 当前是 group_days 层：移动某个景点到另一天、调整天的主题
- 当前是 arrange 层：调整某个时间、换顺序
- 例："加上雷峰塔" / "把xx移到第二天" / "下午的安排太紧了"

## 用户想要回退 (action: "back")
- "我想重新选景点" / "回到上一步" / "换几个地方"
- 当前在 group_days 但想改 POI 选择
- 当前在 arrange 但想改分组

## 用户提供了偏好信息 (preferences)
- 在任何操作中，如果用户透露了新的偏好信息，提取出来
- 例如："我妈腿不好走不了太多路" → "同行人体力有限，减少步行"

# 输出格式
只输出 JSON：
```json
{{
  "action": "advance" | "modify" | "back",
  "target_layer": "select_pois" | "group_days" | "arrange" | "confirm" | null,
  "modification": "用户的具体修改意图（如有）",
  "preferences_update": ["新发现的偏好1", "新发现的偏好2"]
}}
```

- action=advance 时，target_layer 为下一层
- action=modify 时，target_layer 为当前层
- action=back 时，target_layer 为要回退到的层
- 如果用户没有透露新偏好，preferences_update 为空列表
"""


class GathererAgent:
    """Determines conversation phase and routes user intent.

    Two modes:
    1. Gathering mode: Collects travel requirements (before builder starts)
    2. Router mode: Routes intent within the builder flow (after requirements collected)
    """

    def __init__(self, llm: LLMService) -> None:
        """Initialize with an LLM service instance."""
        self._llm = llm

    async def run(
        self,
        messages: list[dict[str, Any]],
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> GathererOutput:
        """Analyze conversation and return gathering result or ready signal.

        Used in the initial requirement-collecting phase (before builder starts).
        """
        span = get_langfuse().start_span(name="gatherer_run")
        span.update_trace(
            name="gatherer_run",
            session_id=session_id,
            user_id=user_id,
            input=messages[-1].get("content", "") if messages else "",
        )

        llm_messages = [
            {"role": "system", "content": _GATHERER_PROMPT},
            *messages,
        ]

        try:
            response = await self._llm.call(
                messages=llm_messages,
                tools=None,
                temperature=0.3,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content or "{}"
            logger.debug("gatherer_raw_output", raw=raw[:500])

            output = GathererOutput.model_validate_json(raw)

            span.update_trace(
                output=output.model_dump_json(),
                metadata={"status": output.status, "question_count": len(output.questions)},
            )
            span.end()

            logger.info(
                "gatherer_completed",
                status=output.status,
                question_count=len(output.questions),
                has_requirements=output.requirements is not None,
            )
            return output

        except (ValidationError, Exception) as e:
            span.update_trace(output=f"error: {e}", level="ERROR")
            span.end()
            logger.error("gatherer_failed", error_type=type(e).__name__, error=str(e))
            return self._fallback_output()

    async def route(
        self,
        messages: list[dict[str, Any]],
        builder_state: BuilderState,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> "RouterResult":
        """Route user intent within the builder flow.

        Returns action (advance/modify/back), target layer, and any
        preference updates extracted from the user message.
        """
        current_layer = builder_state.layer
        prompt = _ROUTER_PROMPT.format(
            current_layer=current_layer,
            selected_count=len(builder_state.selected_ids),
            grouped_days=len(builder_state.day_groups),
        )

        llm_messages = [
            {"role": "system", "content": prompt},
            *messages[-4:],  # Only need recent context for routing
        ]

        try:
            response = await self._llm.call(
                messages=llm_messages,
                tools=None,
                temperature=0.1,
                max_tokens=256,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content or "{}"
            import json
            data = json.loads(raw)

            action = data.get("action", "modify")
            target_layer = data.get("target_layer")
            modification = data.get("modification", "")
            preferences_update = data.get("preferences_update", [])

            logger.info(
                "gatherer_route_result",
                action=action,
                target_layer=target_layer,
                modification=modification[:100],
            )

            return RouterResult(
                action=action,
                target_layer=target_layer,
                modification=modification,
                preferences_update=preferences_update,
            )

        except Exception as e:
            logger.error("gatherer_route_failed", error=str(e))
            return RouterResult(action="modify", target_layer=current_layer)

    @staticmethod
    def _fallback_output() -> GathererOutput:
        """Fallback: pass through to Planner (degrades to current behavior)."""
        return GathererOutput(status="ready", content="")


class RouterResult:
    """Result of the intent routing within the builder flow."""

    def __init__(
        self,
        action: str = "modify",
        target_layer: str | None = None,
        modification: str = "",
        preferences_update: list[str] | None = None,
    ):
        """Initialize router result with action and target layer."""
        self.action = action
        self.target_layer = target_layer
        self.modification = modification
        self.preferences_update = preferences_update or []

    @property
    def next_layer(self) -> BuilderLayer:
        """Determine the next layer to execute."""
        if self.target_layer and self.target_layer in (
            "select_pois", "group_days", "arrange", "confirm",
        ):
            return self.target_layer  # type: ignore[return-value]
        return "select_pois"
