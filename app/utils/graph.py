"""Message utilities for the agent loop."""

from app.core.logging import logger


def extract_text_content(content: str | list) -> str:
    """Extract plain text from LLM content (handles structured blocks)."""
    if isinstance(content, str):
        return content

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "reasoning":
                logger.debug("reasoning_block_received", reasoning_id=block.get("id"))
    return "".join(parts)
