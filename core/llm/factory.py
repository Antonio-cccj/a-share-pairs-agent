"""LLM provider factory.

Returns the right provider given the global settings or an explicit override.
Falls back to :class:`MockLLM` whenever:

- the requested provider's optional SDK is not installed, or
- the API key is empty, or
- the user explicitly sets ``LLM_PROVIDER=mock``.

This keeps the code paths that need an LLM running on machines without any
credentials (CI, evaluators, no-API mode).
"""

from __future__ import annotations

from typing import Any

from core.config import LLMProviderName, settings
from core.llm.base import LLMProvider
from core.llm.mock_provider import MockLLM
from core.logger import get_logger

log = get_logger(__name__)


def build_llm(
    provider: LLMProviderName | None = None,
    model: str | None = None,
    **overrides: Any,
) -> LLMProvider:
    """Construct a provider matching the requested name.

    Parameters
    ----------
    provider
        Name override; falls back to ``settings.llm_provider``.
    model
        Optional override of the per-provider default model.
    **overrides
        Forwarded to the concrete provider constructor (temperature, etc.).
    """
    name = (provider or settings.llm_provider).lower()
    temperature = overrides.pop("temperature", settings.llm_temperature)
    max_tokens = overrides.pop("max_tokens", settings.llm_max_tokens)

    try:
        if name == "anthropic":
            from core.llm.anthropic_provider import AnthropicProvider

            return AnthropicProvider(
                api_key=settings.anthropic_api_key,
                model=model or settings.anthropic_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if name == "openai":
            from core.llm.openai_provider import OpenAICompatibleProvider

            return OpenAICompatibleProvider(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=model or settings.openai_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if name == "deepseek":
            from core.llm.openai_provider import OpenAICompatibleProvider

            return OpenAICompatibleProvider(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=model or settings.deepseek_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if name == "zhipu":
            from core.llm.zhipu_provider import ZhipuProvider

            return ZhipuProvider(
                api_key=settings.zhipu_api_key,
                model=model or settings.zhipu_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if name == "ollama":
            from core.llm.ollama_provider import OllamaProvider

            return OllamaProvider(
                base_url=settings.ollama_base_url,
                model=model or settings.ollama_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if name == "mock":
            return MockLLM(temperature=temperature, max_tokens=max_tokens)
        log.warning("unknown LLM provider '{}', falling back to mock", name)
    except ImportError as e:
        log.warning("optional SDK missing for provider '{}' ({}); falling back to mock", name, e)
    except Exception as e:
        log.warning("failed to instantiate provider '{}' ({}); falling back to mock", name, e)
    return MockLLM(temperature=temperature, max_tokens=max_tokens)
