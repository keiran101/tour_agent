"""TripAgent — ReAct agent main loop with yield-to-user support.

Replaces TripOrchestrator. The LLM autonomously decides which tool to call;
interactive tools break the loop and return UI data to the frontend.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.core.agent.state import AgentState, TripPlanningState
from app.core.config import settings
from app.core.logging import logger
from app.core.observability import get_langfuse
from app.core.tools.base import ToolRegistry, ToolResult
from app.schemas.builder import DayGroup
from app.schemas.chat import BuilderAction
from app.schemas.gatherer import Question
from app.services.llm.service import LLMService
from app.services.memory import MemoryService
from app.utils.graph import extract_text_content

_AGENT_PROMPT = (
    Path(__file__).resolve().parents[1] / "prompts" / "agent_system.md"
).read_text(encoding="utf-8")


@dataclass
class AgentResponse:
    """Unified return type from TripAgent to the API layer."""

    type: str  # "answer" | "builder" | "gathering"
    content: str = ""
    layer: str | None = None
    ui_payload: BaseModel | None = None
    questions: list[Question] = field(default_factory=list)


class TripAgent:
    """Self-built ReAct agent for interactive trip planning.

    Usage:
        agent = TripAgent(llm, memory, tools, user_id, session_id)
        response = await agent.handle(messages, state, builder_action)
    """

    def __init__(
        self,
        llm: LLMService,
        memory: MemoryService,
        tools: ToolRegistry,
        user_id: int | None = None,
        session_id: str | None = None,
    ) -> None:
        self._llm = llm
        self._memory = memory
        self._tools = tools
        self._user_id = user_id
        self._session_id = session_id
        self._max_steps = settings.AGENT_MAX_STEPS

    async def handle(
        self,
        messages: list[dict[str, Any]],
        state: TripPlanningState,
        builder_action: BuilderAction | None = None,
    ) -> AgentResponse:
        """Run one turn of the ReAct agent loop."""
        start = time.monotonic()

        root_span = get_langfuse().start_span(name="trip_agent")
        root_span.update_trace(
            name="trip_agent",
            session_id=self._session_id,
            user_id=str(self._user_id) if self._user_id else None,
            input=messages[-1].get("content", "") if messages else "",
            metadata={"state_summary": state.summary()},
        )

        if builder_action:
            self._apply_builder_action(state, builder_action)
            synthetic = self._describe_action(builder_action, state)
            messages = [*messages, {"role": "user", "content": synthetic}]

        system_prompt = await self._build_system_prompt(state, messages)

        loop_state = AgentState()
        loop_state.add_message("system", system_prompt)
        for msg in messages:
            loop_state.add_message(msg["role"], msg.get("content", ""))

        tools_schema = self._tools.get_openai_schemas() or None

        logger.info(
            "trip_agent_started",
            session_id=self._session_id,
            state_summary=state.summary(),
            tool_count=len(tools_schema) if tools_schema else 0,
        )

        response = await self._react_loop(loop_state, state, tools_schema, root_span)

        elapsed = round(time.monotonic() - start, 2)
        logger.info(
            "trip_agent_finished",
            steps=loop_state.step,
            tool_calls=len(loop_state.tool_calls),
            elapsed=elapsed,
            response_type=response.type,
        )

        root_span.update_trace(
            output=response.content[:200],
            metadata={
                "steps": loop_state.step,
                "tool_calls": len(loop_state.tool_calls),
                "elapsed_seconds": elapsed,
                "response_type": response.type,
            },
        )
        root_span.end()

        return response

    # ------------------------------------------------------------------
    # ReAct loop
    # ------------------------------------------------------------------

    async def _react_loop(
        self,
        loop_state: AgentState,
        state: TripPlanningState,
        tools_schema: list[dict[str, Any]] | None,
        root_span: Any,
    ) -> AgentResponse:
        while loop_state.step < self._max_steps and not loop_state.is_done:
            loop_state.step += 1
            step_span = root_span.start_span(name=f"step_{loop_state.step}")

            generation = step_span.start_generation(
                name="llm_call",
                model=settings.DEFAULT_LLM_MODEL,
                input=loop_state.messages,
            )

            try:
                llm_response = await self._llm.call(
                    messages=loop_state.messages,
                    tools=tools_schema,
                )
            except Exception as e:
                generation.update(output=str(e), level="ERROR").end()
                step_span.end()
                return AgentResponse(type="answer", content=f"抱歉，服务出现问题：{e}")

            choice = llm_response.choices[0]
            message = choice.message

            generation.update(
                output=message.content or "[tool_calls]",
                usage_details=_extract_usage(llm_response),
            ).end()

            self._append_assistant_message(loop_state, message)

            if not message.tool_calls:
                content = extract_text_content(message.content or "")
                loop_state.final_answer = content
                step_span.end()
                return AgentResponse(type="answer", content=content)

            for tc in message.tool_calls:
                tool_name = tc.function.name
                arguments = tc.function.arguments

                logger.info("agent_tool_call", step=loop_state.step, tool=tool_name)

                tool_span = step_span.start_span(
                    name=f"tool:{tool_name}",
                    input=arguments,
                )

                result: ToolResult = await self._tools.execute(
                    tool_name, arguments, state=state,
                )

                tool_span.update(output=result.content[:500]).end()

                loop_state.record_tool_call(tool_name, arguments, result.content)
                loop_state.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result.content,
                })

                if result.yield_to_user:
                    step_span.end()
                    return self._build_yield_response(result, message)

            step_span.end()

        if not loop_state.is_done:
            logger.warning("trip_agent_max_steps", max_steps=self._max_steps)
            answer = await self._force_final_answer(loop_state, root_span)
            return AgentResponse(type="answer", content=answer)

        return AgentResponse(type="answer", content=loop_state.final_answer or "")

    # ------------------------------------------------------------------
    # Builder action processing
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_builder_action(state: TripPlanningState, action: BuilderAction) -> None:
        """Apply frontend card interaction to persistent state."""
        if action.action == "advance":
            if action.selected_ids:
                id_set = set(action.selected_ids)
                state.selected_pois = [p for p in state.search_results if p.id in id_set]
                state.day_groups = []
                state.schedule = None
            if action.day_groups:
                state.day_groups = [DayGroup(**g) if isinstance(g, dict) else g for g in action.day_groups]
                state.schedule = None
        elif action.action == "back":
            target = action.target_phase
            if target == "select_pois":
                state.selected_pois = []
                state.day_groups = []
                state.schedule = None
            elif target == "group_days":
                state.day_groups = []
                state.schedule = None
            elif target == "arrange":
                state.schedule = None

    @staticmethod
    def _describe_action(action: BuilderAction, state: TripPlanningState) -> str:
        """Generate a synthetic user message describing the card interaction."""
        if action.action == "advance":
            if action.selected_ids is not None:
                names = [p.name for p in state.selected_pois[:5]]
                return f"我选好了景点：{'、'.join(names)}等{len(state.selected_pois)}个。请继续下一步。"
            if action.day_groups is not None:
                return f"我确认了{len(state.day_groups)}天的分组方案。请安排详细时间线。"
            if state.schedule:
                return "我确认了时间安排。请保存行程。"
            return "确认，继续下一步。"
        elif action.action == "back":
            target_map = {
                "select_pois": "景点选择",
                "group_days": "分天方案",
                "arrange": "时间安排",
            }
            target_name = target_map.get(action.target_phase or "", "上一步")
            return f"我想返回修改{target_name}。"
        else:
            return "我想修改当前方案。"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_yield_response(
        self, result: ToolResult, message: Any,
    ) -> AgentResponse:
        """Convert a yield ToolResult into an AgentResponse."""
        content = message.content or result.content

        if result.layer == "gathering":
            questions: list[Question] = []
            if result.ui_payload and hasattr(result.ui_payload, "questions"):
                questions = result.ui_payload.questions  # type: ignore[attr-defined]
            return AgentResponse(
                type="gathering",
                content=content,
                questions=questions,
            )

        if result.layer:
            return AgentResponse(
                type="builder",
                content=content,
                layer=result.layer,
                ui_payload=result.ui_payload,
            )

        return AgentResponse(type="answer", content=content)

    async def _build_system_prompt(
        self,
        state: TripPlanningState,
        messages: list[dict[str, Any]],
    ) -> str:
        query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                query = msg.get("content", "")
                break

        memory_context = await self._memory.search(
            str(self._user_id) if self._user_id else None, query,
        )

        prompt = _AGENT_PROMPT.replace("{state_summary}", state.summary())
        prompt = prompt.replace("{memory_context}", memory_context or "暂无")

        return prompt

    async def _force_final_answer(
        self, loop_state: AgentState, parent_span: Any,
    ) -> str:
        loop_state.add_message(
            "system",
            "你已达到最大步数。请根据目前的信息给出最好的回复。",
        )

        generation = parent_span.start_generation(
            name="force_final_answer",
            model=settings.DEFAULT_LLM_MODEL,
            input=loop_state.messages,
        )

        response = await self._llm.call(
            messages=loop_state.messages,
            tools=None,
        )
        answer = extract_text_content(response.choices[0].message.content or "")

        generation.update(
            output=answer,
            usage_details=_extract_usage(response),
        ).end()

        return answer

    @staticmethod
    def _append_assistant_message(loop_state: AgentState, message: Any) -> None:
        assistant_msg: dict[str, Any] = {"role": "assistant"}
        if message.content:
            assistant_msg["content"] = message.content
        reasoning = getattr(message, "reasoning_content", None)
        if reasoning:
            assistant_msg["reasoning_content"] = reasoning
        if message.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        loop_state.messages.append(assistant_msg)


def _extract_usage(response: Any) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if not usage:
        return None
    result: dict[str, int] = {}
    for key, attr in [("input", "prompt_tokens"), ("output", "completion_tokens"), ("total", "total_tokens")]:
        val = getattr(usage, attr, None)
        if val is not None:
            result[key] = val
    return result or None
