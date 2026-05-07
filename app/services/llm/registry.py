"""LLM model registry using OpenAI-compatible protocol.

Supports MiMo, DeepSeek, Qwen and any other model served via
OpenAI-compatible API (SiliconFlow, vLLM, Ollama, etc.).
"""

from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging import logger


@dataclass
class ModelConfig:
    """Configuration for a single LLM model."""

    name: str
    model_id: str
    base_url: str = ""
    api_key: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096
    extra_kwargs: dict[str, Any] = field(default_factory=dict)


class LLMRegistry:
    """Registry of available LLM models.

    All models use AsyncOpenAI client with OpenAI-compatible protocol,
    so switching between MiMo / DeepSeek / Qwen is just config.
    """

    _configs: list[ModelConfig] = []
    _clients: dict[str, AsyncOpenAI] = {}

    @classmethod
    def _ensure_initialized(cls) -> None:
        if cls._configs:
            return

        cls._configs = [
            ModelConfig(
                name="mimo",
                model_id="MiMo-V2.5",
                temperature=0.2,
                max_tokens=settings.MAX_TOKENS,
            ),
            ModelConfig(
                name="deepseek",
                model_id="deepseek-chat",
                temperature=0.2,
                max_tokens=settings.MAX_TOKENS,
            ),
            ModelConfig(
                name="qwen",
                model_id="Qwen/Qwen3-8B",
                temperature=0.2,
                max_tokens=settings.MAX_TOKENS,
            ),
        ]

        logger.info(
            "llm_registry_initialized",
            models=[c.name for c in cls._configs],
            default_model=settings.DEFAULT_LLM_MODEL,
        )

    @classmethod
    def get_client(cls, model_name: str | None = None) -> AsyncOpenAI:
        """Get or create an AsyncOpenAI client for the given model."""
        cls._ensure_initialized()
        name = model_name or settings.DEFAULT_LLM_MODEL
        config = cls._get_config(name)

        if config.name not in cls._clients:
            cls._clients[config.name] = AsyncOpenAI(
                api_key=config.api_key or settings.LLM_API_KEY,
                base_url=config.base_url or settings.LLM_BASE_URL,
            )
        return cls._clients[config.name]

    @classmethod
    def get_config(cls, model_name: str | None = None) -> ModelConfig:
        """Get model config by name."""
        cls._ensure_initialized()
        return cls._get_config(model_name or settings.DEFAULT_LLM_MODEL)

    @classmethod
    def _get_config(cls, name: str) -> ModelConfig:
        for config in cls._configs:
            if config.name == name or config.model_id == name:
                return config
        logger.warning("model_not_found_using_first", requested=name)
        return cls._configs[0]

    @classmethod
    def get_all_names(cls) -> list[str]:
        """Return all registered model names."""
        cls._ensure_initialized()
        return [c.name for c in cls._configs]

    @classmethod
    def get_config_at_index(cls, index: int) -> ModelConfig:
        """Return model config at index, wrapping if out of range."""
        cls._ensure_initialized()
        return cls._configs[index % len(cls._configs)]
