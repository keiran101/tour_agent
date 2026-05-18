"""Intent router — classifies user intent within the builder flow."""

import json
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import logger
from app.schemas.builder import BuilderPhase, BuilderState
from app.services.llm.service import LLMService

_ROUTER_PROMPT = """# 角色
你是一个对话意图路由器。用户正在使用交互式行程构建器，你需要判断用户当前消息的意图。

# 当前构建器状态
- 当前层级: {current_phase}
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
  "target_phase": "select_pois" | "group_days" | "arrange" | "confirm" | null,
  "modification": "用户的具体修改意图（如有）",
  "preferences_update": ["新发现的偏好1", "新发现的偏好2"]
}}
```

- action=advance 时，target_phase 为下一层
- action=modify 时，target_phase 为当前层
- action=back 时，target_phase 为要回退到的层
- 如果用户没有透露新偏好，preferences_update 为空列表
"""

_VALID_PHASES = {"select_pois", "group_days", "arrange", "confirm"}


@dataclass
class RouterResult:
    """Result of intent classification."""

    action: str = "modify"
    target_phase: str | None = None
    modification: str = ""
    preferences_update: list[str] = field(default_factory=list)

    @property
    def resolved_phase(self) -> BuilderPhase:
        """Return target phase, defaulting to select_pois."""
        if self.target_phase and self.target_phase in _VALID_PHASES:
            return self.target_phase  # type: ignore[return-value]
        return "select_pois"


class IntentRouter:
    """Classifies user intent within the active builder flow."""

    def __init__(self, llm: LLMService) -> None:
        """Initialize with LLM service."""
        self._llm = llm

    async def classify(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
    ) -> RouterResult:
        """Classify user intent as advance, modify, or back."""
        prompt = _ROUTER_PROMPT.format(
            current_phase=state.phase,
            selected_count=len(state.selected_ids),
            grouped_days=len(state.day_groups),
        )

        llm_messages = [
            {"role": "system", "content": prompt},
            *messages[-4:],
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
            data = json.loads(raw)

            result = RouterResult(
                action=data.get("action", "modify"),
                target_phase=data.get("target_phase"),
                modification=data.get("modification", ""),
                preferences_update=data.get("preferences_update", []),
            )

            logger.info(
                "router_classified",
                action=result.action,
                target_phase=result.target_phase,
                modification=result.modification[:100],
            )
            return result

        except Exception as e:
            logger.error("router_classify_failed", error=str(e))
            return RouterResult(action="modify", target_phase=state.phase)
