"""Trip orchestrator — owns the state machine and dispatches to executors."""

from typing import Any

from app.core.agent.executors import (
    ArrangeExecutor,
    BaseExecutor,
    ConfirmExecutor,
    ExecutorResult,
    GatheringExecutor,
    GroupDaysExecutor,
    SelectPOIsExecutor,
)
from app.core.agent.router import IntentRouter
from app.core.logging import logger
from app.schemas.builder import BuilderPhase, BuilderState
from app.services.llm.service import LLMService
from app.services.memory import MemoryService

TRANSITIONS: dict[str, dict[str, BuilderPhase]] = {
    "gathering":   {"advance": "select_pois"},
    "select_pois": {"advance": "group_days",  "back": "gathering"},
    "group_days":  {"advance": "arrange",     "back": "select_pois"},
    "arrange":     {"advance": "confirm",     "back": "group_days"},
}


class TripOrchestrator:
    """Central state machine for the multi-phase trip building flow.

    Handles:
    - Phase transitions (advance / back / modify)
    - Dispatching to the correct executor
    - Auto-advancing from gathering → select_pois when requirements are ready
    """

    def __init__(
        self,
        llm: LLMService,
        memory: MemoryService,
        user_id: int | None = None,
        session_id: str | None = None,
    ) -> None:
        """Initialize router and all phase executors."""
        self._router = IntentRouter(llm)
        self._executors: dict[str, BaseExecutor] = {
            "gathering":   GatheringExecutor(llm, memory, user_id, session_id),
            "select_pois": SelectPOIsExecutor(llm, memory, user_id, session_id),
            "group_days":  GroupDaysExecutor(llm, memory, user_id, session_id),
            "arrange":     ArrangeExecutor(llm, memory, user_id, session_id),
            "confirm":     ConfirmExecutor(llm, memory, user_id, session_id),
        }

    async def handle(
        self,
        messages: list[dict[str, Any]],
        state: BuilderState,
    ) -> ExecutorResult:
        """Route intent, transition state, and dispatch to the correct executor."""
        logger.info("orchestrator_handle", phase=state.phase, session_id=None)

        # --- Gathering phase: no routing needed ---
        if state.phase == "gathering":
            result = await self._executors["gathering"].run(messages, state)
            if result.auto_advance:
                state.phase = "select_pois"
                return await self._executors["select_pois"].run(messages, state)
            return result

        # --- Builder active: classify intent and transition ---
        intent = await self._router.classify(messages, state)

        for pref in intent.preferences_update:
            if pref not in state.preferences.inferred:
                state.preferences.inferred.append(pref)

        if intent.action == "advance":
            new_phase = TRANSITIONS.get(state.phase, {}).get("advance")
            if new_phase:
                state.phase = new_phase
        elif intent.action == "back":
            if intent.target_phase in self._executors:
                state.phase = intent.target_phase  # type: ignore[assignment]
            else:
                fallback = TRANSITIONS.get(state.phase, {}).get("back")
                if fallback:
                    state.phase = fallback

        return await self._executors[state.phase].run(messages, state)
