"""Tool base class and registry.

Defines the interface all agent tools must implement,
compatible with OpenAI function-calling schema.

Two base classes:
  - Tool: internal tools (search, weather, etc.) — execute(**kwargs) -> str
  - InteractiveTool: yield-to-user tools — execute(args, state) -> ToolResult
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from app.core.logging import logger

if TYPE_CHECKING:
    from app.core.agent.state import TripPlanningState


@dataclass
class ToolResult:
    """Result returned by any tool execution.

    For internal tools, only `content` is populated.
    For interactive tools, `yield_to_user=True` breaks the ReAct loop
    and returns `ui_payload` / `layer` to the frontend.
    """

    content: str
    yield_to_user: bool = False
    ui_payload: BaseModel | None = None
    layer: str | None = None


class Tool(ABC):
    """Base class for internal agent tools (no state access, returns str)."""

    name: str
    description: str
    parameters: dict[str, Any]

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool and return a string result for the LLM."""

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class InteractiveTool(Tool):
    """Base class for interactive (yield-to-user) tools.

    These tools receive the persistent TripPlanningState, can mutate it,
    and return a ToolResult that may break the ReAct loop.
    """

    @abstractmethod
    async def run(self, args: dict[str, Any], state: TripPlanningState) -> ToolResult:
        """Execute with access to persistent state. Override this instead of execute()."""

    async def execute(self, **kwargs: Any) -> str:
        raise RuntimeError("InteractiveTool.execute() should not be called directly; use ToolRegistry")


class ToolRegistry:
    """Registry of available tools for the agent."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        logger.debug("tool_registered", tool_name=tool.name)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        return list(self._tools.values())

    def get_openai_schemas(self) -> list[dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    async def execute(
        self,
        name: str,
        arguments: str,
        state: TripPlanningState | None = None,
    ) -> ToolResult:
        """Execute a tool by name with a JSON arguments string."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(content=f"Error: unknown tool '{name}'")

        try:
            kwargs = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError as e:
            return ToolResult(content=f"Error: invalid arguments JSON — {e}")

        try:
            if isinstance(tool, InteractiveTool):
                if state is None:
                    return ToolResult(content=f"Error: tool '{name}' requires state but none provided")
                result = await tool.run(kwargs, state)
            else:
                raw = await tool.execute(**kwargs)
                result = ToolResult(content=raw)

            logger.info("tool_executed", tool_name=name, yield_to_user=result.yield_to_user)
            return result
        except Exception as e:
            logger.error("tool_execution_failed", tool_name=name, error=str(e))
            return ToolResult(content=f"Error executing {name}: {e}")
