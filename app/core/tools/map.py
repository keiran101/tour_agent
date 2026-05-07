"""Route and distance calculation tool.

Computes travel time/distance between POIs for itinerary optimization.
Uses Amap direction API for domestic routes.
"""

import json
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.core.tools.base import Tool

_AMAP_DIRECTION_TRANSIT = "https://restapi.amap.com/v3/direction/transit/integrated"
_AMAP_DIRECTION_DRIVING = "https://restapi.amap.com/v3/direction/driving"
_AMAP_DIRECTION_WALKING = "https://restapi.amap.com/v3/direction/walking"

_TIMEOUT = httpx.Timeout(10.0)


class RouteCalculatorTool(Tool):
    """Calculate travel time and distance between two locations."""

    name = "route_calculator"
    description = (
        "Calculate travel time and distance between two locations. "
        "Supports driving, transit (public transport), and walking modes. "
        "Input coordinates as 'longitude,latitude' strings."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin coordinates 'lng,lat', e.g. '120.15,30.28'",
            },
            "destination": {
                "type": "string",
                "description": "Destination coordinates 'lng,lat', e.g. '120.21,30.25'",
            },
            "mode": {
                "type": "string",
                "description": "Travel mode",
                "enum": ["driving", "transit", "walking"],
            },
            "city": {
                "type": "string",
                "description": "City name, required for transit mode, e.g. '杭州'",
            },
        },
        "required": ["origin", "destination"],
    }

    async def execute(
        self,
        origin: str,
        destination: str,
        mode: str = "transit",
        city: str = "",
    ) -> str:
        if not settings.AMAP_API_KEY:
            return "Error: AMAP_API_KEY not configured"

        if mode == "driving":
            return await self._driving(origin, destination)
        elif mode == "walking":
            return await self._walking(origin, destination)
        else:
            return await self._transit(origin, destination, city)

    async def _transit(self, origin: str, destination: str, city: str) -> str:
        params = {
            "key": settings.AMAP_API_KEY,
            "origin": origin,
            "destination": destination,
            "city": city or "全国",
            "strategy": "0",
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_AMAP_DIRECTION_TRANSIT, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "1":
            logger.warning("amap_transit_error", info=data.get("info"))
            return f"Amap transit API error: {data.get('info', 'unknown')}"

        route = data.get("route", {})
        transits = route.get("transits", [])
        if not transits:
            return "No transit route found"

        best = transits[0]
        result = {
            "mode": "transit",
            "origin": origin,
            "destination": destination,
            "duration": _format_duration(best.get("duration", "0")),
            "walking_distance": f"{best.get('walking_distance', '0')}m",
            "cost": best.get("cost", ""),
        }
        return json.dumps(result, ensure_ascii=False)

    async def _driving(self, origin: str, destination: str) -> str:
        params = {
            "key": settings.AMAP_API_KEY,
            "origin": origin,
            "destination": destination,
            "strategy": "10",
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_AMAP_DIRECTION_DRIVING, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "1":
            logger.warning("amap_driving_error", info=data.get("info"))
            return f"Amap driving API error: {data.get('info', 'unknown')}"

        paths = data.get("route", {}).get("paths", [])
        if not paths:
            return "No driving route found"

        best = paths[0]
        result = {
            "mode": "driving",
            "origin": origin,
            "destination": destination,
            "distance": f"{int(best.get('distance', 0)) / 1000:.1f}km",
            "duration": _format_duration(best.get("duration", "0")),
            "tolls": f"{best.get('tolls', '0')}元",
        }
        return json.dumps(result, ensure_ascii=False)

    async def _walking(self, origin: str, destination: str) -> str:
        params = {
            "key": settings.AMAP_API_KEY,
            "origin": origin,
            "destination": destination,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_AMAP_DIRECTION_WALKING, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "1":
            logger.warning("amap_walking_error", info=data.get("info"))
            return f"Amap walking API error: {data.get('info', 'unknown')}"

        paths = data.get("route", {}).get("paths", [])
        if not paths:
            return "No walking route found"

        best = paths[0]
        result = {
            "mode": "walking",
            "origin": origin,
            "destination": destination,
            "distance": f"{int(best.get('distance', 0))}m",
            "duration": _format_duration(best.get("duration", "0")),
        }
        return json.dumps(result, ensure_ascii=False)


def _format_duration(seconds_str: str) -> str:
    """Convert seconds string to human-readable duration."""
    try:
        total = int(seconds_str)
    except (ValueError, TypeError):
        return seconds_str
    if total < 60:
        return f"{total}秒"
    minutes = total // 60
    if minutes < 60:
        return f"{minutes}分钟"
    hours = minutes // 60
    remaining = minutes % 60
    if remaining:
        return f"{hours}小时{remaining}分钟"
    return f"{hours}小时"
