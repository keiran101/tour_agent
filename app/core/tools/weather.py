"""Weather forecast tool using QWeather (和风天气) API.

Provides current weather and multi-day forecasts for travel planning.
Uses QWeather v7 API: city lookup + weather forecast.
"""

import json
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.core.tools.base import Tool

_QWEATHER_CITY_LOOKUP = "https://geoapi.qweather.com/v2/city/lookup"
_QWEATHER_FORECAST_3D = "https://devapi.qweather.com/v7/weather/3d"
_QWEATHER_FORECAST_7D = "https://devapi.qweather.com/v7/weather/7d"
_QWEATHER_NOW = "https://devapi.qweather.com/v7/weather/now"

_TIMEOUT = httpx.Timeout(10.0)


class WeatherTool(Tool):
    """Query weather forecast for a destination city."""

    name = "weather_query"
    description = (
        "Get current weather or multi-day forecast for a city. "
        "Useful for recommending what to pack and scheduling outdoor activities."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name, e.g. '杭州' or 'Tokyo'",
            },
            "forecast_days": {
                "type": "integer",
                "description": "Number of forecast days: 0 for current weather, 3 or 7 for forecast",
                "enum": [0, 3, 7],
            },
        },
        "required": ["city"],
    }

    async def execute(self, city: str, forecast_days: int = 3) -> str:
        if not settings.QWEATHER_API_KEY:
            return "Error: QWEATHER_API_KEY not configured"

        location_id = await self._lookup_city(city)
        if location_id is None:
            return f"City '{city}' not found in QWeather"

        if forecast_days == 0:
            return await self._get_now(location_id, city)
        return await self._get_forecast(location_id, city, forecast_days)

    async def _lookup_city(self, city: str) -> str | None:
        params = {
            "location": city,
            "key": settings.QWEATHER_API_KEY,
            "number": "1",
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_QWEATHER_CITY_LOOKUP, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != "200":
            logger.warning("qweather_city_lookup_failed", city=city, code=data.get("code"))
            return None

        locations = data.get("location", [])
        if not locations:
            return None
        return locations[0].get("id")

    async def _get_now(self, location_id: str, city: str) -> str:
        params = {"location": location_id, "key": settings.QWEATHER_API_KEY}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_QWEATHER_NOW, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != "200":
            return f"QWeather API error: {data.get('code')}"

        now = data.get("now", {})
        result = {
            "city": city,
            "type": "current",
            "text": now.get("text", ""),
            "temp": f"{now.get('temp', '')}°C",
            "feelsLike": f"{now.get('feelsLike', '')}°C",
            "humidity": f"{now.get('humidity', '')}%",
            "windDir": now.get("windDir", ""),
            "windScale": now.get("windScale", ""),
        }
        return json.dumps(result, ensure_ascii=False)

    async def _get_forecast(self, location_id: str, city: str, days: int) -> str:
        url = _QWEATHER_FORECAST_7D if days == 7 else _QWEATHER_FORECAST_3D
        params = {"location": location_id, "key": settings.QWEATHER_API_KEY}

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != "200":
            return f"QWeather API error: {data.get('code')}"

        daily_list = data.get("daily", [])
        results = []
        for d in daily_list:
            results.append({
                "date": d.get("fxDate", ""),
                "textDay": d.get("textDay", ""),
                "textNight": d.get("textNight", ""),
                "tempMin": f"{d.get('tempMin', '')}°C",
                "tempMax": f"{d.get('tempMax', '')}°C",
                "humidity": f"{d.get('humidity', '')}%",
                "windDirDay": d.get("windDirDay", ""),
                "uvIndex": d.get("uvIndex", ""),
            })

        output = {"city": city, "type": f"{days}d_forecast", "daily": results}
        return json.dumps(output, ensure_ascii=False)
