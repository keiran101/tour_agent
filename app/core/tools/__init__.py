"""Tour-specific tool registry."""

from app.core.tools.base import Tool, ToolRegistry
from app.core.tools.map import RouteCalculatorTool
from app.core.tools.poi import POISearchTool
from app.core.tools.search import WebSearchTool
from app.core.tools.trip import SaveTripTool
from app.core.tools.weather import WeatherTool

__all__ = [
    "Tool",
    "ToolRegistry",
    "POISearchTool",
    "WeatherTool",
    "WebSearchTool",
    "RouteCalculatorTool",
    "SaveTripTool",
    "create_tool_registry",
]


def create_tool_registry(
    user_id: int | None = None,
    session_id: str | None = None,
) -> ToolRegistry:
    """Create a ToolRegistry with all tour-specific tools registered.

    When user_id is provided, the save_trip tool is included so the agent
    can persist structured itineraries to the database.
    """
    registry = ToolRegistry()
    registry.register(POISearchTool())
    registry.register(WeatherTool())
    registry.register(WebSearchTool())
    registry.register(RouteCalculatorTool())

    if user_id is not None:
        from app.services.database import database_service
        from app.services.trip import TripService

        trip_service = TripService(database_service.engine)
        registry.register(SaveTripTool(trip_service, user_id, session_id))

    return registry
