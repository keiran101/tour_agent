"""Trip orchestrator — owns the state machine and dispatches to executors."""

from __future__ import annotations

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
from app.core.agent.router import IntentRouter, RouterResult
from app.core.logging import logger
from app.schemas.builder import BuilderPhase, BuilderState, POIOption
from app.schemas.chat import BuilderAction
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
        builder_action: BuilderAction | None = None,
    ) -> ExecutorResult:
        """Route intent, transition state, and dispatch to the correct executor."""
        logger.info("orchestrator_handle", phase=state.phase, has_action=builder_action is not None)

        # --- Gathering phase: no routing needed ---
        if state.phase == "gathering":
            result = await self._executors["gathering"].run(messages, state)
            if result.auto_advance:
                state.phase = "select_pois"
                return await self._executors["select_pois"].run(messages, state)
            return result

        # --- Fix corrupted state: fall back if prerequisite data is missing ---
        _ensure_phase_prerequisites(state)

        # --- Builder active: deterministic action or LLM classification ---
        if builder_action:
            intent = _action_to_intent(builder_action)
            logger.info("deterministic_intent", action=intent.action, phase=state.phase)
        else:
            intent = await self._router.classify(messages, state)

        for pref in intent.preferences_update:
            if pref not in state.preferences.inferred:
                state.preferences.inferred.append(pref)

        if intent.action == "advance":
            # Structured UI action: use IDs/groups directly
            if builder_action and builder_action.selected_ids:
                state.selected_ids = builder_action.selected_ids
            elif state.phase == "select_pois" and not builder_action:
                # Text-based selection: resolve POI names → IDs from user message
                user_msg = _last_user_content(messages)
                resolved = _resolve_poi_names(user_msg, state.all_pois)
                if resolved:
                    state.selected_ids = resolved
                    logger.info("poi_names_resolved", count=len(resolved))

            if builder_action and builder_action.day_groups:
                state.day_groups = builder_action.day_groups

            # Guard: block advance if current phase data is missing
            if not _can_advance(state):
                logger.info("advance_blocked_missing_data", phase=state.phase)
                return await self._executors[state.phase].run(messages, state)

            if state.phase == "confirm":
                state.confirmed = True
            else:
                new_phase = TRANSITIONS.get(state.phase, {}).get("advance")
                if new_phase:
                    state.phase = new_phase
        elif intent.action == "back":
            state.confirmed = False
            if intent.target_phase in self._executors:
                state.phase = intent.target_phase  # type: ignore[assignment]
            else:
                fallback = TRANSITIONS.get(state.phase, {}).get("back")
                if fallback:
                    state.phase = fallback

        return await self._executors[state.phase].run(messages, state)


def _can_advance(state: BuilderState) -> bool:
    """Check if the current phase has enough data to advance."""
    if state.phase == "select_pois" and not state.selected_ids:
        return False
    if state.phase == "group_days" and not state.day_groups:
        return False
    if state.phase == "arrange" and not state.schedule:
        return False
    return True


def _ensure_phase_prerequisites(state: BuilderState) -> None:
    """Fall back to an earlier phase if prerequisite data is missing.

    Handles corrupted state where the phase got ahead of the data
    (e.g. advanced to group_days but select_pois failed and left no POIs).
    """
    if state.phase in ("group_days", "arrange", "confirm") and not state.selected_ids:
        logger.info("prerequisite_fallback", from_phase=state.phase, to_phase="select_pois", reason="no selected POIs")
        state.phase = "select_pois"
        return
    if state.phase in ("arrange", "confirm") and not state.day_groups:
        logger.info("prerequisite_fallback", from_phase=state.phase, to_phase="group_days", reason="no day groups")
        state.phase = "group_days"
        return
    if state.phase == "confirm" and not state.schedule:
        logger.info("prerequisite_fallback", from_phase=state.phase, to_phase="arrange", reason="no schedule")
        state.phase = "arrange"


def _action_to_intent(action: BuilderAction) -> RouterResult:
    """Convert a structured BuilderAction to a RouterResult (no LLM needed)."""
    return RouterResult(
        action=action.action,
        target_phase=action.target_phase,
    )


def _last_user_content(messages: list[dict[str, Any]]) -> str:
    """Extract the last user message content."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


def _resolve_poi_names(user_msg: str, all_pois: list[POIOption]) -> list[str]:
    """Match POI names mentioned in user text to their IDs."""
    if not all_pois or not user_msg:
        return []
    return [poi.id for poi in all_pois if poi.name in user_msg]
