"""Tour-specific tool registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.tools.base import InteractiveTool, Tool, ToolRegistry, ToolResult
from app.core.tools.map import RouteCalculatorTool
from app.core.tools.poi import POISearchTool
from app.core.tools.search import WebSearchTool
from app.core.tools.trip import SaveTripTool
from app.core.tools.weather import WeatherTool

if TYPE_CHECKING:
    from app.services.llm.service import LLMService
    from app.services.memory import MemoryService

__all__ = [
    "InteractiveTool",
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "POISearchTool",
    "WeatherTool",
    "WebSearchTool",
    "RouteCalculatorTool",
    "SaveTripTool",
    "create_tool_registry",
    "create_internal_tool_registry",
]


def create_internal_tool_registry() -> ToolRegistry:
    """Create a registry with only internal (non-interactive) tools.

    Used by interactive tools that run internal sub-loops (e.g. recommend_pois,
    arrange_schedule) — they need POI search, route calculation, etc. but not
    the interactive tools themselves.
    """
    registry = ToolRegistry()
    registry.register(POISearchTool())
    registry.register(WeatherTool())
    registry.register(WebSearchTool())
    registry.register(RouteCalculatorTool())
    return registry


def create_tool_registry(
    llm: LLMService | None = None,
    memory: MemoryService | None = None,
    user_id: int | None = None,
    session_id: str | None = None,
) -> ToolRegistry:
    """Create a ToolRegistry with all tools (internal + interactive).

    When llm/memory are provided, interactive tools (ask_user, recommend_pois,
    etc.) are included. When user_id is provided, confirm_trip is included.
    """
    from app.core.tools.ask_user import AskUserTool
    from app.core.tools.arrange_schedule import ArrangeScheduleTool
    from app.core.tools.present_groups import PresentGroupsTool
    from app.core.tools.recommend_pois import RecommendPoisTool
    from app.core.tools.save_trip_interactive import ConfirmTripTool

    registry = ToolRegistry()

    # Internal tools
    registry.register(POISearchTool())
    registry.register(WeatherTool())
    registry.register(WebSearchTool())
    registry.register(RouteCalculatorTool())

    # Interactive tools (need LLM service)
    if llm is not None:
        internal_tools = create_internal_tool_registry()

        registry.register(AskUserTool(llm))
        registry.register(RecommendPoisTool(
            llm, memory or _stub_memory(), internal_tools, user_id, session_id,
        ))
        registry.register(PresentGroupsTool(llm))
        registry.register(ArrangeScheduleTool(
            llm, memory or _stub_memory(), internal_tools, user_id, session_id,
        ))

    if user_id is not None:
        from app.services.database import database_service
        from app.services.trip import TripService

        trip_service = TripService(database_service.engine)
        registry.register(ConfirmTripTool(trip_service, user_id, session_id))

    return registry


def _stub_memory() -> MemoryService:
    """Fallback when memory service is not provided."""
    from app.services.memory import memory_service
    return memory_service
