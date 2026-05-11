"""Ollama (local) provider.

Allows fully-offline LLM inference via the user's local Ollama daemon.
Recommended model for Chinese tasks: ``qwen2.5:7b-instruct``.
"""

from __future__ import annotations

from typing import Any

import httpx

from core.llm.base import LLMMessage, LLMProvider
from core.logger import get_logger

log = get_logger(__name__)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, temperature: float = 0.1, max_tokens: int = 2048) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self.base_url = base_url.rstrip("/")

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
                "num_predict": kwargs.get("max_tokens", self.max_tokens),
            },
        }
        log.debug("ollama chat model={} url={}", self.model, self.base_url)
        with httpx.Client(timeout=300.0) as client:
            r = client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
        return data.get("message", {}).get("content", "")
