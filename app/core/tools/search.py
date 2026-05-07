"""Web search tool using Tavily API.

Used for fetching UGC content (travel tips, reviews) from sources
like Xiaohongshu, Mafengwo etc. without direct scraping.
"""

import json
from typing import Any

from tavily import AsyncTavilyClient

from app.core.config import settings
from app.core.tools.base import Tool


class WebSearchTool(Tool):
    """Search the web for travel tips, reviews, and practical info."""

    name = "web_search"
    description = (
        "Search the web for travel-related information: user reviews, "
        "travel tips, local food recommendations, ticket prices, "
        "transportation guides, etc. Good for getting real traveler experiences."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query, e.g. '杭州三日游攻略' or 'best street food in Bangkok'",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (1-10)",
            },
        },
        "required": ["query"],
    }

    async def execute(self, query: str, max_results: int = 5) -> str:
        if not settings.TAVILY_API_KEY:
            return "Error: TAVILY_API_KEY not configured"

        max_results = max(1, min(10, max_results))

        client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
        response = await client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_answer=True,
        )

        answer = response.get("answer", "")
        raw_results = response.get("results", [])

        results = []
        for r in raw_results:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:500],
            })

        output: dict[str, Any] = {"query": query, "results": results}
        if answer:
            output["summary"] = answer

        return json.dumps(output, ensure_ascii=False)
