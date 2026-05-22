"""Agent state management.

Two state objects:
  - AgentState: ephemeral per-run state (messages, step counter, tool calls).
  - TripPlanningState: persistent cross-turn state (requirements, POIs, schedule).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.builder import (
    ArrangePayload,
    BuilderState,
    DayGroup,
    POIOption,
    SessionPreferences,
    StoredRequirements,
)


# ------------------------------------------------------------------
# Ephemeral per-run state (used by AgentLoop / TripAgent)
# ------------------------------------------------------------------

@dataclass
class ToolCallRecord:
    """Record of a single tool invocation."""

    step: int
    tool_name: str
    arguments: str
    result: str


@dataclass
class AgentState:
    """Mutable state for a single agent run."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    step: int = 0
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    final_answer: str | None = None

    @property
    def is_done(self) -> bool:
        return self.final_answer is not None

    def add_message(self, role: str, content: str | None = None, **kwargs: Any) -> None:
        msg: dict[str, Any] = {"role": role}
        if content is not None:
            msg["content"] = content
        msg.update(kwargs)
        self.messages.append(msg)

    def record_tool_call(self, tool_name: str, arguments: str, result: str) -> None:
        self.tool_calls.append(
            ToolCallRecord(
                step=self.step,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
            )
        )


# ------------------------------------------------------------------
# Persistent cross-turn state (serialized to DB between turns)
# ------------------------------------------------------------------

class TripPlanningState(BaseModel):
    """Agent's working memory, persisted across conversation turns.

    Tools read/write this state directly. The Agent only sees summary().
    """

    requirements: StoredRequirements = Field(default_factory=StoredRequirements)
    preferences: SessionPreferences = Field(default_factory=SessionPreferences)

    search_results: list[POIOption] = Field(default_factory=list)
    selected_pois: list[POIOption] = Field(default_factory=list)

    day_groups: list[DayGroup] = Field(default_factory=list)
    schedule: ArrangePayload | None = None

    trip_saved: bool = False

    def summary(self) -> str:
        """~50 token status + next-step hint for the Agent's system prompt."""
        parts: list[str] = []
        if self.requirements.destination:
            r = self.requirements
            parts.append(f"{r.destination}{r.duration_days}天 预算{r.budget_level}")
        if self.selected_pois:
            names = ", ".join(p.name for p in self.selected_pois[:4])
            tail = f"等{len(self.selected_pois)}个" if len(self.selected_pois) > 4 else ""
            parts.append(f"已选景点: {names}{tail}")
        if self.day_groups:
            parts.append(f"已分{len(self.day_groups)}天")
        if self.schedule:
            parts.append("时间线已排")
        if self.trip_saved:
            parts.append("行程已保存")

        status = " | ".join(parts) or "空白（尚未开始规划）"
        return f"{status}\n下一步行动：{self.next_step_hint()}"

    def next_step_hint(self) -> str:
        """Tell the Agent what it should do next."""
        if not self.requirements.destination:
            return "用 ask_user 收集用户的旅行需求（目的地、天数、偏好等）"
        if not self.selected_pois:
            return "用 recommend_pois 搜索并推荐景点，让用户选择"
        if not self.day_groups:
            return "用 present_groups 将已选景点分配到各天，让用户确认"
        if self.schedule is None:
            return "用 arrange_schedule 安排每天的详细时间线"
        if not self.trip_saved:
            return "用 confirm_trip 保存行程"
        return "行程已完成，自由对话即可"

    def preferences_prompt_section(self) -> str:
        """Format preferences as a system prompt section."""
        lines: list[str] = []
        if not self.preferences.explicit and not self.preferences.inferred:
            return ""
        lines.append("\n## 本次用户偏好")
        for p in self.preferences.explicit:
            lines.append(f"- {p}")
        for p in self.preferences.inferred:
            lines.append(f"- [推断] {p}")
        return "\n".join(lines)

    @staticmethod
    def from_builder_state(bs: BuilderState) -> TripPlanningState:
        """Migrate legacy BuilderState to TripPlanningState."""
        id_set = set(bs.selected_ids)
        return TripPlanningState(
            requirements=bs.requirements,
            preferences=bs.preferences,
            search_results=list(bs.all_pois),
            selected_pois=[p for p in bs.all_pois if p.id in id_set],
            day_groups=list(bs.day_groups),
            schedule=bs.schedule,
            trip_saved=bs.confirmed,
        )
