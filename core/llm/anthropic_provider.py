"""Anthropic Claude provider."""

from __future__ import annotations

from typing import Any

from core.llm.base import LLMMessage, LLMProvider
from core.logger import get_logger

log = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    """Wraps the official ``anthropic`` SDK.

    Lazy-imports the SDK so the optional dependency stays optional.
    """

    name = "anthropic"

    def __init__(
        self, api_key: str, model: str, temperature: float = 0.0, max_tokens: int = 2048
    ) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is empty")
        # Lazy import keeps install lighter for users on other backends.
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> str:
        # Anthropic separates the system prompt from the user/assistant turns.
        system = "\n".join(m.content for m in messages if m.role == "system") or None
        turns = [
            {"role": ("user" if m.role == "user" else "assistant"), "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        log.debug("anthropic chat model={} turns={}", self.model, len(turns))
        resp = self._client.messages.create(
            model=self.model,
            system=system,
            messages=turns,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        # ``content`` is a list of ContentBlock; we keep only text blocks.
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "".join(parts)
