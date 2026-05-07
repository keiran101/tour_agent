"""LLM service with retries and circular fallback.

Uses AsyncOpenAI client directly (no LangChain dependency).
All models accessed via OpenAI-compatible protocol.
"""

import asyncio
import logging
from typing import Any

from openai import (
    APIError,
    APITimeoutError,
    OpenAIError,
    RateLimitError,
)
from openai.types.chat import ChatCompletion
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import logger
from app.services.llm.registry import LLMRegistry


class LLMService:
    """Service for managing LLM calls with retries and circular fallback."""

    def __init__(self):
        """Initialize with default model from registry."""
        self._current_model_index: int = 0
        self._tools_schema: list[dict[str, Any]] = []

        all_names = LLMRegistry.get_all_names()
        try:
            config = LLMRegistry.get_config()
            self._current_model_index = all_names.index(config.name)
            logger.info(
                "llm_service_initialized",
                default_model=config.name,
                total_models=len(all_names),
            )
        except Exception as e:
            logger.warning("llm_service_init_fallback", error=str(e))

    def set_tools(self, tools_schema: list[dict[str, Any]]) -> None:
        """Set the tools schema for function calling."""
        self._tools_schema = tools_schema
        logger.debug("tools_schema_set", tool_count=len(tools_schema))

    async def call(
        self,
        messages: list[dict[str, Any]],
        model_name: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatCompletion:
        """Call the LLM with retries and circular fallback.

        Args:
            messages: OpenAI-format messages list.
            model_name: Override model. None uses default.
            tools: Override tools schema. None uses bound tools.
            temperature: Override temperature.
            max_tokens: Override max tokens.

        Returns:
            ChatCompletion from the OpenAI-compatible API.
        """
        try:
            return await asyncio.wait_for(
                self._call_with_fallback(messages, model_name, tools, temperature, max_tokens),
                timeout=settings.LLM_TOTAL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.exception("llm_total_timeout_exceeded", timeout_seconds=settings.LLM_TOTAL_TIMEOUT)
            raise RuntimeError(f"llm call timed out after {settings.LLM_TOTAL_TIMEOUT}s")

    @retry(
        stop=stop_after_attempt(settings.MAX_LLM_CALL_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _invoke(
        self,
        model_name: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
    ) -> ChatCompletion:
        """Single LLM invocation with retry."""
        config = LLMRegistry.get_config(model_name)
        client = LLMRegistry.get_client(model_name)

        kwargs: dict[str, Any] = {
            "model": config.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await client.chat.completions.create(**kwargs)
            logger.debug("llm_call_successful", model=config.name)
            return response
        except (RateLimitError, APITimeoutError, APIError):
            raise
        except OpenAIError as e:
            logger.error("llm_call_failed", error_type=type(e).__name__, error=str(e))
            raise

    async def _call_with_fallback(
        self,
        messages: list[dict[str, Any]],
        model_name: str | None,
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> ChatCompletion:
        """Try each registered model in turn until one succeeds."""
        all_names = LLMRegistry.get_all_names()
        total = len(all_names)

        start = self._current_model_index
        if model_name:
            if model_name in all_names:
                start = all_names.index(model_name)
            else:
                raise ValueError(f"model '{model_name}' not found. available: {', '.join(all_names)}")

        effective_tools = tools if tools is not None else self._tools_schema or None
        effective_temp = temperature if temperature is not None else settings.DEFAULT_LLM_TEMPERATURE
        effective_max = max_tokens if max_tokens is not None else settings.MAX_TOKENS

        last_error: Exception | None = None

        for i in range(total):
            idx = (start + i) % total
            current_name = all_names[idx]
            try:
                result = await self._invoke(current_name, messages, effective_tools, effective_temp, effective_max)
                if i > 0:
                    self._current_model_index = idx
                return result
            except OpenAIError as e:
                last_error = e
                logger.error(
                    "llm_call_failed_after_retries",
                    model=current_name,
                    models_tried=i + 1,
                    total_models=total,
                    error=str(e),
                )

        raise RuntimeError(f"all {total} models failed. last error: {last_error}")


llm_service = LLMService()
