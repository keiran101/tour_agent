"""Base executor and shared helpers for the multi-layer trip builder."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import json_repair

from app.core.logging import logger
from app.schemas.builder import (
    BuilderResponse,
    BuilderState,
    StoredRequirements,
)
from app.schemas.gatherer import Question
from app.services.llm.service import LLMService
from app.services.memory import MemoryService


def _try_parse_json(text: str) -> dict[str, Any] | None:
    """Try to parse JSON, using json_repair for common LLM mistakes."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.debug("json_parse_attempt_raw", error=str(e), pos=e.pos, text_around=text[max(0, (e.pos or 0) - 30):(e.pos or 0) + 30])
    try:
        result = json_repair.loads(text)
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    return None


@dataclass
class ExecutorResult:
    """Unified return type for all executors."""

    message: str
    builder_response: BuilderResponse | None = None
    questions: list[Question] = field(default_factory=list)
    auto_advance: bool = False


class BaseExecutor(ABC):
    """Abstract base for all phase executors."""

    def __init__(
        self,
        llm: LLMService,
        memory: MemoryService,
        user_id: int | None = None,
        session_id: str | None = None,
    ) -> None:
        """Initialize with shared services and session context."""
        self._llm = llm
        self._memory = memory
        self._user_id = user_id
        self._session_id = session_id

    @abstractmethod
    async def run(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
    ) -> ExecutorResult:
        """Execute this phase and return a result."""

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(
        self,
        base_prompt: str,
        state: BuilderState,
        extra_context: str = "",
    ) -> str:
        parts = [base_prompt]

        prefs_section = state.preferences_prompt_section()
        if prefs_section:
            parts.append(prefs_section)

        req_section = self._format_requirements(state.requirements)
        if req_section:
            parts.append(req_section)

        if extra_context:
            parts.append(extra_context)

        return "\n".join(parts)

    @staticmethod
    def _format_requirements(req: StoredRequirements) -> str:
        if not req.destination:
            return ""
        lines = ["\n## 用户旅行需求"]
        lines.append(f"- 目的地: {req.destination}")
        lines.append(f"- 天数: {req.duration_days}天")
        if req.budget_level:
            lines.append(f"- 预算: {req.budget_level}")
        if req.travel_style:
            lines.append(f"- 偏好: {'、'.join(req.travel_style)}")
        if req.group_type:
            lines.append(f"- 同行: {req.group_type}")
        if req.pace:
            lines.append(f"- 节奏: {req.pace}")
        if req.travel_dates:
            lines.append(f"- 日期: {req.travel_dates}")
        if req.special_requests:
            lines.append(f"- 特殊需求: {req.special_requests}")
        return "\n".join(lines)

    @staticmethod
    def _parse_json_from_answer(text: str) -> dict[str, Any] | None:
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Extract from ```json ... ``` fenced block
        for marker in ("```json", "```"):
            idx = text.find(marker)
            if idx == -1:
                continue
            start = idx + len(marker)
            end = text.find("```", start)
            fragment = text[start:end].strip() if end != -1 else text[start:].strip()
            result = _try_parse_json(fragment)
            if result is not None:
                return result

        # Fallback: outermost { … }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            result = _try_parse_json(text[first_brace:last_brace + 1])
            if result is not None:
                return result

        logger.warning("executor_json_parse_failed", text_preview=text[:200])
        return None
