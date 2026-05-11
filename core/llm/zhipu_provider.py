"""Zhipu AI (GLM-4) provider.

Uses the official ``zhipuai`` SDK.  Zhipu's GLM-4 series has a free tier
(``glm-4-flash``) that is convenient for Chinese-text tasks like research-report
parsing.
"""

from __future__ import annotations

from typing import Any

from core.llm.base import LLMMessage, LLMProvider
from core.logger import get_logger

log = get_logger(__name__)


class ZhipuProvider(LLMProvider):
    name = "zhipu"

    def __init__(self, api_key: str, model: str, temperature: float = 0.1, max_tokens: int = 2048) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        if not api_key:
            raise ValueError("ZHIPU_API_KEY is empty")
        from zhipuai import ZhipuAI

        self._client = ZhipuAI(api_key=api_key)

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> str:
        payload = [{"role": m.role, "content": m.content} for m in messages]
        log.debug("zhipu chat model={} turns={}", self.model, len(payload))
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=payload,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        return resp.choices[0].message.content or ""
