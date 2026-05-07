"""ReAct agent main loop.

Implements a think-act-observe cycle:
1. LLM decides next action (tool call or final answer)
2. Execute selected tool
3. Feed observation back to LLM
4. Repeat until final answer or max steps reached
"""

import time
from typing import Any, AsyncGenerator

from app.core.agent.state import AgentState
from app.core.config import settings
from app.core.logging import logger
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
            await self._step(state, model_name, tools_schema)

        if not state.is_done:
            logger.warning("agent_max_steps_reached", max_steps=self._max_steps)
            state.final_answer = await self._force_final_answer(state, model_name)

        elapsed = round(time.monotonic() - start_time, 2)
        logger.info(
            "agent_loop_finished",
            steps=state.step,
            tool_calls=len(state.tool_calls),
            elapsed=elapsed,
        )

        await self._memory.add(user_id, state.messages)

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
          {"type": "thinking", "step": int, "tool": str}
          {"type": "tool_result", "step": int, "tool": str, "result": str}
          {"type": "answer", "content": str}
          {"type": "error", "message": str}
        """
        state = AgentState()

        system_content = await self._build_system_prompt(user_id, user_messages)
        state.add_message("system", system_content)

        for msg in user_messages:
            state.add_message(msg["role"], msg.get("content", ""))

        tools_schema = self._tools.get_openai_schemas() or None

        while state.step < self._max_steps and not state.is_done:
            state.step += 1

            try:
                response = await self._llm.call(
                    messages=state.messages,
                    model_name=model_name,
                    tools=tools_schema,
                )
            except Exception as e:
                yield {"type": "error", "message": str(e)}
                return

            choice = response.choices[0]
            message = choice.message

            self._append_assistant_message(state, message)

            if message.tool_calls:
                for tc in message.tool_calls:
                    yield {"type": "thinking", "step": state.step, "tool": tc.function.name}

                    result = await self._tools.execute(tc.function.name, tc.function.arguments)
                    state.record_tool_call(tc.function.name, tc.function.arguments, result)

                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                    yield {
                        "type": "tool_result",
                        "step": state.step,
                        "tool": tc.function.name,
                        "result": result,
                    }
            else:
                state.final_answer = extract_text_content(message.content or "")
                yield {"type": "answer", "content": state.final_answer}

        if not state.is_done:
            answer = await self._force_final_answer(state, model_name)
            state.final_answer = answer
            yield {"type": "answer", "content": answer}

        await self._memory.add(user_id, state.messages)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _step(
        self,
        state: AgentState,
        model_name: str | None,
        tools_schema: list[dict[str, Any]] | None,
    ) -> None:
        """Execute a single think-act-observe step."""
        logger.debug("agent_step", step=state.step)

        response = await self._llm.call(
            messages=state.messages,
            model_name=model_name,
            tools=tools_schema,
        )

        choice = response.choices[0]
        message = choice.message

        self._append_assistant_message(state, message)

        if message.tool_calls:
            for tc in message.tool_calls:
                tool_name = tc.function.name
                arguments = tc.function.arguments

                logger.info("tool_call", step=state.step, tool=tool_name)

                result = await self._tools.execute(tool_name, arguments)
                state.record_tool_call(tool_name, arguments, result)

                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
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
        """Build system prompt with long-term memory context injected."""
        query = ""
        for msg in reversed(user_messages):
            if msg.get("role") == "user":
                query = msg.get("content", "")
                break

        memory_context = await self._memory.search(user_id, query)

        parts = [self._system_prompt]
        if memory_context:
            parts.append(f"\n## What you know about this user\n{memory_context}")

        return "\n".join(parts)

    async def _force_final_answer(
        self, state: AgentState, model_name: str | None
    ) -> str:
        """Force LLM to produce a final answer without tools."""
        state.add_message(
            "system",
            "You have reached the maximum number of steps. "
            "Summarize what you've learned and provide the best answer you can now.",
        )
        response = await self._llm.call(
            messages=state.messages,
            model_name=model_name,
            tools=None,
        )
        return extract_text_content(response.choices[0].message.content or "")
