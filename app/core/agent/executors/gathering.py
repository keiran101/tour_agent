"""Gathering executor — collects travel requirements via conversation."""

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.agent.executors.base import BaseExecutor, ExecutorResult
from app.core.logging import logger
from app.core.observability import get_langfuse
from app.schemas.builder import BuilderState, StoredRequirements
from app.schemas.gatherer import GathererOutput

_GATHERER_PROMPT = (
    Path(__file__).resolve().parents[2] / "prompts" / "gatherer.md"
).read_text(encoding="utf-8")


class GatheringExecutor(BaseExecutor):
    """Collects travel requirements through multi-turn conversation."""

    async def run(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
    ) -> ExecutorResult:
        """Collect requirements; auto_advance=True when ready."""
        span = get_langfuse().start_span(name="gathering")
        span.update_trace(
            name="gathering",
            session_id=self._session_id,
            user_id=str(self._user_id) if self._user_id else None,
            input=messages[-1].get("content", "") if messages else "",
        )

        llm_messages = [
            {"role": "system", "content": _GATHERER_PROMPT},
            *messages,
        ]

        try:
            response = await self._llm.call(
                messages=llm_messages,
                tools=None,
                temperature=0.3,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content or "{}"
            logger.debug("gathering_raw_output", raw=raw[:500])
            output = GathererOutput.model_validate_json(raw)

            span.update_trace(
                output=output.model_dump_json(),
                metadata={"status": output.status},
            )
            span.end()

        except (ValidationError, Exception) as e:
            span.update_trace(output=f"error: {e}")
            span.end()
            logger.error("gathering_failed", error_type=type(e).__name__, error=str(e))
            output = GathererOutput(status="ready", content="")

        if output.status == "gathering":
            logger.info("gathering_continue", question_count=len(output.questions))
            return ExecutorResult(
                message=output.content,
                questions=output.questions,
            )

        # Ready — store requirements into state and signal auto-advance
        logger.info("gathering_ready", has_requirements=output.requirements is not None)
        if output.requirements:
            state.requirements = StoredRequirements(
                destination=output.requirements.destination,
                duration_days=output.requirements.duration_days,
                budget_level=output.requirements.budget_level,
                travel_style=output.requirements.travel_style,
                group_type=output.requirements.group_type,
                pace=output.requirements.pace,
                travel_dates=output.requirements.travel_dates,
                special_requests=output.requirements.special_requests,
            )
            if output.requirements.group_type:
                state.preferences.explicit.append(f"同行: {output.requirements.group_type}")
            if output.requirements.pace:
                state.preferences.explicit.append(f"节奏: {output.requirements.pace}")
            if output.requirements.special_requests:
                state.preferences.explicit.append(output.requirements.special_requests)

        return ExecutorResult(message=output.content, auto_advance=True)