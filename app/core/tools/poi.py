"""POI (Point of Interest) search tool.

Routes to Amap (高德) for domestic destinations and Google Places for overseas,
based on destination region detection.
"""

import json
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.core.tools.base import Tool
from app.utils.geo import is_domestic

_AMAP_TEXT_SEARCH = "https://restapi.amap.com/v3/place/text"
_GOOGLE_PLACES_SEARCH = "https://places.googleapis.com/v1/places:searchText"

_TIMEOUT = httpx.Timeout(10.0)


class POISearchTool(Tool):
    """Search for points of interest near a destination."""

    name = "poi_search"
    description = (
        "Search for tourist attractions, restaurants, hotels, or other POIs "
        "at a given destination. Automatically uses Amap for Chinese cities "
        "and Google Places for overseas destinations."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query, e.g. '西湖附近的景点' or 'museums in Paris'",
            },
            "destination": {
                "type": "string",
                "description": "City or region name for routing domestic/overseas, e.g. '杭州' or 'Paris'",
            },
            "category": {
                "type": "string",
                "description": "POI category filter: attraction, restaurant, hotel, shopping",
                "enum": ["attraction", "restaurant", "hotel", "shopping"],
            },
        },
        "required": ["query", "destination"],
    }

    async def execute(self, query: str, destination: str, category: str = "attraction") -> str:
        if is_domestic(destination):
            return await self._search_amap(query, destination, category)
        return await self._search_google(query, destination, category)

    async def _search_amap(self, query: str, destination: str, category: str) -> str:
        if not settings.AMAP_API_KEY:
            return "Error: AMAP_API_KEY not configured"

        type_code = _amap_type_code(category)
        params: dict[str, str] = {
            "key": settings.AMAP_API_KEY,
            "keywords": query,
            "city": destination,
            "citylimit": "true",
            "offset": "10",
            "extensions": "all",
        }
        if type_code:
            params["types"] = type_code

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_AMAP_TEXT_SEARCH, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "1":
            logger.warning("amap_api_error", info=data.get("info"))
            return f"Amap API error: {data.get('info', 'unknown')}"

        pois = data.get("pois", [])
        if not pois:
            return f"No POIs found for '{query}' in {destination}"

        results = []
        for p in pois[:8]:
            item = {
                "name": p.get("name", ""),
                "address": p.get("address", ""),
                "type": p.get("type", ""),
                "location": p.get("location", ""),
                "tel": p.get("tel", ""),
                "rating": p.get("biz_ext", {}).get("rating", ""),
            }
            results.append(item)

        return json.dumps(results, ensure_ascii=False)

    async def _search_google(self, query: str, destination: str, category: str) -> str:
        if not settings.GOOGLE_PLACES_API_KEY:
            return "Error: GOOGLE_PLACES_API_KEY not configured"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
            "X-Goog-FieldMask": (
                "places.displayName,places.formattedAddress,"
                "places.location,places.rating,places.types,"
                "places.regularOpeningHours"
            ),
        }
        body = {
            "textQuery": f"{query} in {destination}",
            "maxResultCount": 8,
            "languageCode": "zh-CN",
        }

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(_GOOGLE_PLACES_SEARCH, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        places = data.get("places", [])
        if not places:
            return f"No POIs found for '{query}' in {destination}"

        results = []
        for p in places:
            loc = p.get("location", {})
            item = {
                "name": p.get("displayName", {}).get("text", ""),
                "address": p.get("formattedAddress", ""),
                "types": ", ".join(p.get("types", [])[:3]),
                "location": f"{loc.get('longitude', '')},{loc.get('latitude', '')}",
                "rating": p.get("rating", ""),
            }
            results.append(item)

        return json.dumps(results, ensure_ascii=False)


def _amap_type_code(category: str) -> str:
    """Map category to Amap POI type code."""
    mapping = {
        "attraction": "110000",
        "restaurant": "050000",
        "hotel": "100000",
        "shopping": "060000",
    }
    return mapping.get(category, "")
