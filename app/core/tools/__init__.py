"""Tour-specific tool registry."""

from app.core.tools.base import Tool, ToolRegistry
from app.core.tools.map import RouteCalculatorTool
from app.core.tools.poi import POISearchTool
from app.core.tools.search import WebSearchTool
from app.core.tools.weather import WeatherTool

__all__ = [
    "Tool",
    "ToolRegistry",
    "POISearchTool",
    "WeatherTool",
    "WebSearchTool",
    "RouteCalculatorTool",
    "create_tool_registry",
]


def create_tool_registry() -> ToolRegistry:
    """Create a ToolRegistry with all tour-specific tools registered."""
    registry = ToolRegistry()
    registry.register(POISearchTool())
    registry.register(WeatherTool())
    registry.register(WebSearchTool())
    registry.register(RouteCalculatorTool())
    return registry
