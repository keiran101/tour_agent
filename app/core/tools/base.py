"""Tool base class and registry.

Defines the interface all agent tools must implement,
compatible with OpenAI function-calling schema.
"""

import json
from abc import ABC, abstractmethod
from typing import Any

from app.core.logging import logger


class Tool(ABC):
    """Base class for all agent tools."""

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

    async def execute(self, name: str, arguments: str) -> str:
        """Execute a tool by name with a JSON arguments string."""
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"

        try:
            kwargs = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError as e:
            return f"Error: invalid arguments JSON — {e}"

        try:
            result = await tool.execute(**kwargs)
            logger.info("tool_executed", tool_name=name)
            return result
        except Exception as e:
            logger.error("tool_execution_failed", tool_name=name, error=str(e))
            return f"Error executing {name}: {e}"
