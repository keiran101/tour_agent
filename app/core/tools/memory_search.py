"""search_memory tool — retrieves relevant past conversation summaries."""

from typing import Any

from app.core.logging import logger
from app.core.tools.base import Tool
from app.services.memory import MemoryService


class SearchMemoryTool(Tool):
    """Search past conversation summaries for cross-session context."""

    name = "search_memory"
    description = (
        "搜索该用户的历史对话记录。当用户提到之前的行程、过去的对话、"
        "或想参考以前的方案时调用此工具。不要在每次对话中都调用，"
        "只在用户明确引用历史内容时使用。"
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，描述用户想找的历史内容，如'杭州三日游'",
            },
        },
        "required": ["query"],
    }

    def __init__(self, memory: MemoryService, user_id: int | None = None) -> None:
        self._memory = memory
        self._user_id = user_id

    async def execute(self, **kwargs: Any) -> str:
        query = kwargs.get("query", "")
        if not query:
            return "Error: query is required"

        user_id = str(self._user_id) if self._user_id else None
        if not user_id:
            return "没有找到相关的历史对话记录。"

        result = await self._memory.search(user_id, query)
        if not result:
            return "没有找到相关的历史对话记录。"

        logger.info("search_memory_hit", user_id=user_id, query=query[:50])
        return f"找到以下相关历史对话：\n{result}"
