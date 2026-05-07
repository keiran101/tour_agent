"""Agent state management.

Tracks conversation messages, tool call history, and step count
across the agent loop execution.
"""

from dataclasses import dataclass, field
from typing import Any


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
