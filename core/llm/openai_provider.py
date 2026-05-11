"""OpenAI-compatible provider.

Covers OpenAI itself plus any service that exposes the same REST surface
(DeepSeek, Moonshot, DashScope/Qwen, Together AI, vLLM, etc.).  The provider
is parameterised by ``base_url`` so users can point it anywhere.
"""

from __future__ import annotations

from typing import Any

from core.llm.base import LLMMessage, LLMProvider
from core.logger import get_logger

log = get_logger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    """Thin wrapper over the official ``openai`` SDK >=1.0."""

    name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        if not api_key:
            raise ValueError("API key empty for OpenAI-compatible provider")
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> str:
        payload = [{"role": m.role, "content": m.content} for m in messages]
        log.debug("openai-compat chat model={} turns={}", self.model, len(payload))
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=payload,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        return resp.choices[0].message.content or ""
