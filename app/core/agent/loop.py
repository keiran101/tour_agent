"""ReAct agent main loop.

Implements a think-act-observe cycle:
1. LLM decides next action (tool call or final answer)
2. Execute selected tool
3. Feed observation back to LLM
4. Repeat until final answer or max steps reached

Langfuse tracing structure:
  Trace(agent_run)
    ├── Span(step_1)
    │   ├── Generation(llm_call)
    │   └── Span(tool:xxx)
    ├── Span(step_2) ...
    └── Generation(force_final_answer)  [if max_steps reached]
"""

import time
from typing import Any, AsyncGenerator

from app.core.agent.state import AgentState
from app.core.config import settings
from app.core.logging import logger
from app.core.observability import get_langfuse
from app.core.tools.base import ToolRegistry
from app.services.llm.service import LLMService
from app.services.memory import MemoryService
from app.utils.graph import extract_text_content


class AgentLoop:
    """Self-built ReAct agent loop.

    Usage:
        loop = AgentLoop(llm=llm_service, tools=registry, memory=memory_service,
                         system_prompt=prompt_text)
        state = await loop.run(user_messages, user_id="u1")
        print(state.final_answer)
    """

    def __init__(
        self,
        llm: LLMService,
        tools: ToolRegistry,
        memory: MemoryService,
        system_prompt: str = "",
        max_steps: int | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._memory = memory
        self._system_prompt = system_prompt
        self._max_steps = max_steps or settings.AGENT_MAX_STEPS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        user_messages: list[dict[str, Any]],
        user_id: str | None = None,
        session_id: str | None = None,
        model_name: str | None = None,
    ) -> AgentState:
        """Run the agent loop to completion and return final state."""
        state = AgentState()
        start_time = time.monotonic()

        root_span = get_langfuse().start_span(name="agent_run")
        root_span.update_trace(
            name="agent_run",
            session_id=session_id,
            user_id=user_id,
            input=user_messages[-1].get("content", "") if user_messages else "",
            metadata={"max_steps": self._max_steps},
        )

        system_content = await self._build_system_prompt(user_id, user_messages)
        state.add_message("system", system_content)

        for msg in user_messages:
            state.add_message(msg["role"], msg.get("content", ""))

        tools_schema = self._tools.get_openai_schemas() or None

        logger.info(
            "agent_loop_started",
            user_id=user_id,
            session_id=session_id,
            tool_count=len(tools_schema) if tools_schema else 0,
            max_steps=self._max_steps,
        )

        while state.step < self._max_steps and not state.is_done:
            state.step += 1
            step_span = root_span.start_span(name=f"step_{state.step}")
            await self._step(state, model_name, tools_schema, step_span)
            step_span.end()

        if not state.is_done:
            logger.warning("agent_max_steps_reached", max_steps=self._max_steps)
            state.final_answer = await self._force_final_answer(state, model_name, root_span)

        elapsed = round(time.monotonic() - start_time, 2)
        logger.info(
            "agent_loop_finished",
            steps=state.step,
            tool_calls=len(state.tool_calls),
            elapsed=elapsed,
        )

        root_span.update_trace(
            output=state.final_answer,
            metadata={
                "steps": state.step,
                "tool_calls": len(state.tool_calls),
                "elapsed_seconds": elapsed,
            },
        )
        root_span.end()

        await self._memory.add(user_id, state.messages, llm=self._llm, session_id=session_id)

        return state

    async def run_stream(
        self,
        user_messages: list[dict[str, Any]],
        user_id: str | None = None,
        session_id: str | None = None,
        model_name: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Run the agent loop, yielding events for SSE streaming.

        Event types:
          {"type": "llm_call", "step": int, "response": {...}}
          {"type": "thinking", "step": int, "tool": str, "arguments": str}
          {"type": "tool_result", "step": int, "tool": str, "result": str}
          {"type": "answer", "content": str}
          {"type": "error", "message": str}
        """
        state = AgentState()

        root_span = get_langfuse().start_span(name="agent_run_stream")
        root_span.update_trace(
            name="agent_run_stream",
            session_id=session_id,
            user_id=user_id,
            input=user_messages[-1].get("content", "") if user_messages else "",
        )

        system_content = await self._build_system_prompt(user_id, user_messages)
        state.add_message("system", system_content)

        for msg in user_messages:
            state.add_message(msg["role"], msg.get("content", ""))

        tools_schema = self._tools.get_openai_schemas() or None

        while state.step < self._max_steps and not state.is_done:
            state.step += 1
            step_span = root_span.start_span(name=f"step_{state.step}")

            try:
                generation = step_span.start_generation(
                    name="llm_call",
                    model=model_name or settings.DEFAULT_LLM_MODEL,
                    input=state.messages,
                )
                response = await self._llm.call(
                    messages=state.messages,
                    model_name=model_name,
                    tools=tools_schema,
                )
                choice = response.choices[0]
                message = choice.message
                generation.update(
                    output=message.content or "[tool_calls]",
                    usage_details=_extract_usage(response),
                ).end()
            except Exception as e:
                generation.update(
                    output=str(e), level="ERROR", status_message=str(e),
                ).end()
                step_span.end()
                root_span.update_trace(output=f"error: {e}")
                root_span.end()
                yield {"type": "error", "message": str(e)}
                return

            yield {
                "type": "llm_call",
                "step": state.step,
                "response": _serialize_message(message),
            }

            self._append_assistant_message(state, message)

            if message.tool_calls:
                for tc in message.tool_calls:
                    yield {
                        "type": "thinking",
                        "step": state.step,
                        "tool": tc.function.name,
                        "arguments": tc.function.arguments,
                    }

                    tool_span = step_span.start_span(
                        name=f"tool:{tc.function.name}",
                        input=tc.function.arguments,
                    )
                    tool_result = await self._tools.execute(tc.function.name, tc.function.arguments)
                    result_text = tool_result.content
                    tool_span.update(output=result_text[:500]).end()

                    state.record_tool_call(tc.function.name, tc.function.arguments, result_text)
                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_text,
                    })

                    yield {
                        "type": "tool_result",
                        "step": state.step,
                        "tool": tc.function.name,
                        "result": result_text,
                    }
            else:
                state.final_answer = extract_text_content(message.content or "")
                yield {"type": "answer", "content": state.final_answer}

            step_span.end()

        if not state.is_done:
            answer = await self._force_final_answer(state, model_name, root_span)
            state.final_answer = answer
            yield {"type": "answer", "content": answer}

        root_span.update_trace(output=state.final_answer)
        root_span.end()
        await self._memory.add(user_id, state.messages, llm=self._llm, session_id=session_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _step(
        self,
        state: AgentState,
        model_name: str | None,
        tools_schema: list[dict[str, Any]] | None,
        span: Any = None,
    ) -> None:
        """Execute a single think-act-observe step."""
        logger.debug("agent_step", step=state.step)

        generation = None
        if span:
            generation = span.start_generation(
                name="llm_call",
                model=model_name or settings.DEFAULT_LLM_MODEL,
                input=state.messages,
            )

        response = await self._llm.call(
            messages=state.messages,
            model_name=model_name,
            tools=tools_schema,
        )

        choice = response.choices[0]
        message = choice.message

        if generation:
            generation.update(
                output=message.content or "[tool_calls]",
                usage_details=_extract_usage(response),
            ).end()

        self._append_assistant_message(state, message)

        if message.tool_calls:
            for tc in message.tool_calls:
                tool_name = tc.function.name
                arguments = tc.function.arguments

                logger.info("tool_call", step=state.step, tool=tool_name)

                tool_span = span.start_span(
                    name=f"tool:{tool_name}",
                    input=arguments,
                ) if span else None

                tool_result = await self._tools.execute(tool_name, arguments)
                result_text = tool_result.content
                state.record_tool_call(tool_name, arguments, result_text)

                if tool_span:
                    tool_span.update(output=result_text[:500]).end()

                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_text,
                })
        else:
            state.final_answer = extract_text_content(message.content or "")
            logger.info("agent_final_answer", step=state.step)

    @staticmethod
    def _append_assistant_message(state: AgentState, message: Any) -> None:
        """Append the raw assistant message (with optional tool_calls) to state."""
        assistant_msg: dict[str, Any] = {"role": "assistant"}
        if message.content:
            assistant_msg["content"] = message.content
        # Reasoning models (MiMo/DeepSeek-R1) require reasoning_content to be passed back
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
        state.messages.append(assistant_msg)

    async def _build_system_prompt(
        self, user_id: str | None, user_messages: list[dict[str, Any]]
    ) -> str:
        """Build system prompt."""
        return self._system_prompt

    async def _force_final_answer(
        self, state: AgentState, model_name: str | None, parent_span: Any = None,
    ) -> str:
        """Force LLM to produce a final answer without tools."""
        state.add_message(
            "system",
            "You have reached the maximum number of steps. "
            "Summarize what you've learned and provide the best answer you can now.",
        )

        generation = None
        if parent_span:
            generation = parent_span.start_generation(
                name="force_final_answer",
                model=model_name or settings.DEFAULT_LLM_MODEL,
                input=state.messages,
            )

        response = await self._llm.call(
            messages=state.messages,
            model_name=model_name,
            tools=None,
        )
        answer = extract_text_content(response.choices[0].message.content or "")

        if generation:
            generation.update(output=answer, usage_details=_extract_usage(response)).end()

        return answer


def _serialize_message(message: Any) -> dict[str, Any]:
    """Serialize an OpenAI ChatCompletionMessage to a plain dict for logging."""
    out: dict[str, Any] = {"role": "assistant"}
    if message.content:
        out["content"] = message.content
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning:
        out["reasoning_content"] = reasoning
    if message.tool_calls:
        out["tool_calls"] = [
            {"id": tc.id, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in message.tool_calls
        ]
    return out


def _extract_usage(response: Any) -> dict[str, int] | None:
    """Pull token usage from an OpenAI-compatible response."""
    usage = getattr(response, "usage", None)
    if not usage:
        return None
    result: dict[str, int] = {}
    for key, attr in [("input", "prompt_tokens"), ("output", "completion_tokens"), ("total", "total_tokens")]:
        val = getattr(usage, attr, None)
        if val is not None:
            result[key] = val
    return result or None
