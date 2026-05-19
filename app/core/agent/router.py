"""Intent router — classifies user intent within the builder flow.

Two-tier classification:
  1. Deterministic keyword matching for short, unambiguous messages
  2. LLM fallback for longer or ambiguous messages
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import logger
from app.schemas.builder import BuilderPhase, BuilderState
from app.services.llm.service import LLMService

# ------------------------------------------------------------------
# Deterministic fast-path keywords
# ------------------------------------------------------------------

_PARTICLES = frozenset("吧了啊呀嘛啦哦呢的")

_ADVANCE_PHRASES = frozenset({
    "确认", "可以", "好的", "好", "行", "ok",
    "下一步", "继续", "就这样", "没问题", "就这些",
    "确定", "同意", "嗯", "对",
    "好的继续", "没问题继续", "没有问题",
    "确认选择", "就这样分", "就按这个来",
    "就这么定", "就这么办", "没意见",
})

_BACK_KEYWORDS = ("返回", "回退", "上一步", "重新选", "重来", "从头")

_SELECTION_PREFIXES = ("我选", "就选", "选这", "就去这", "就要这")

# "确认这个分组方案" / "同意这个安排" — button-generated confirmation text
_CONFIRM_PREFIXES = ("确认这", "同意这", "就按这", "就用这")


def _strip_particles(text: str) -> str:
    """Strip trailing Chinese particles (吧/了/啊/…)."""
    while text and text[-1] in _PARTICLES:
        text = text[:-1]
    return text


def _is_advance(text: str) -> bool:
    """Check if text expresses advance intent (after punctuation strip)."""
    core = _strip_particles(text).lower()
    if core in _ADVANCE_PHRASES:
        return True
    parts = [_strip_particles(p.strip()) for p in re.split(r"[，,、]", text) if p.strip()]
    return bool(parts) and all(p.lower() in _ADVANCE_PHRASES for p in parts)

# ------------------------------------------------------------------
# LLM router prompt
# ------------------------------------------------------------------

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
- **select_pois 层特有**：用户列出了他们想选的景点名称（如"我选这几个：西湖、灵隐寺…"），这表示用户已做出选择，应该推进到下一层
- **group_days 层特有**：用户表示对分组满意、同意分组方案

## 用户想要修改当前层 (action: "modify")
- 当前是 select_pois 层：**增减个别**景点（"加上雷峰塔"/"去掉XX"）、问某个景点的详细信息
- 当前是 group_days 层：移动某个景点到另一天、调整天的主题
- 当前是 arrange 层：调整某个时间、换顺序
- 例："加上雷峰塔" / "把xx移到第二天" / "下午的安排太紧了"
- ⚠️ 注意区分：用户列出完整选择列表 = advance，用户增减个别项 = modify

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
    """Classifies user intent within the active builder flow.

    Uses a two-tier approach: deterministic keyword matching first,
    LLM fallback for ambiguous messages.
    """

    def __init__(self, llm: LLMService) -> None:
        """Initialize with LLM service."""
        self._llm = llm

    async def classify(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
    ) -> RouterResult:
        """Classify user intent as advance, modify, or back."""
        deterministic = self._try_deterministic(messages, state.phase)
        if deterministic:
            logger.info(
                "router_deterministic",
                action=deterministic.action,
                phase=state.phase,
            )
            return deterministic

        return await self._llm_classify(messages, state)

    @staticmethod
    def _try_deterministic(
        messages: list[dict[str, Any]],
        current_phase: str,
    ) -> RouterResult | None:
        """Keyword-based classification for short, unambiguous messages."""
        user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_msg = msg.get("content", "").strip()
                break
        if not user_msg:
            return None

        normalized = user_msg.rstrip("。！!~？?…，,～")

        # "我选这几个：X、Y、Z" in select_pois → advance (any length)
        if current_phase == "select_pois":
            if any(normalized.startswith(p) for p in _SELECTION_PREFIXES):
                return RouterResult(action="advance")

        if len(normalized) > 20:
            return None

        # Back keywords (check first — more specific)
        if any(kw in normalized for kw in _BACK_KEYWORDS):
            return RouterResult(action="back")

        # "确认这个分组方案" — button-generated confirmation text
        if any(normalized.startswith(p) for p in _CONFIRM_PREFIXES):
            return RouterResult(action="advance")

        # Advance: exact match, particle stripping, comma-split
        if _is_advance(normalized):
            return RouterResult(action="advance")

        return None

    async def _llm_classify(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
    ) -> RouterResult:
        """LLM-based classification for ambiguous messages."""
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
                "router_llm_classified",
                action=result.action,
                target_phase=result.target_phase,
                modification=result.modification[:100],
            )
            return result

        except Exception as e:
            logger.error("router_classify_failed", error=str(e))
            return RouterResult(action="modify", target_phase=state.phase)
