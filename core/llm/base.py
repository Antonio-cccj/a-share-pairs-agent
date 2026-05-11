"""Abstract LLM provider interface.

We deliberately keep the surface minimal (`chat` + `extract_json`) because the
two project use-cases - event classification and sentiment extraction - both
boil down to "send a prompt, get text/JSON back".

Why not LangChain / LiteLLM?
----------------------------
We want zero heavy dependencies in the default install, and we want the user
to swap providers via a single env var.  Each concrete provider is ~50 LOC.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMMessage:
    """A single chat-completion message."""

    role: str  # "system" | "user" | "assistant"
    content: str


class LLMProvider(ABC):
    """Common ancestor for all providers.

    Subclasses must implement :meth:`chat`.  :meth:`extract_json` is a generic
    helper that parses the first JSON object in the model's reply.
    """

    name: str = "base"

    def __init__(self, model: str, temperature: float, max_tokens: int) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    # ------------------------------------------------------------ abstract
    @abstractmethod
    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> str:
        """Return the assistant's reply text."""

    # ------------------------------------------------------------ helpers
    def extract_json(self, messages: list[LLMMessage], **kwargs: Any) -> dict[str, Any]:
        """Send *messages* and parse the first JSON object from the reply.

        Tries strict ``json.loads`` first, falls back to greedy regex extraction
        for chatty providers that wrap JSON in prose / code fences.

        Raises
        ------
        ValueError
            If no JSON object can be located.
        """
        text = self.chat(messages, **kwargs)
        # 1. Strict parse.
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 2. Strip Markdown code fences (```json ... ```).
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence:
            try:
                return json.loads(fence.group(1))
            except json.JSONDecodeError:
                pass
        # 3. Greedy: first {...} substring.
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError as e:
                raise ValueError(f"LLM returned non-JSON: {text[:200]}") from e
        raise ValueError(f"LLM reply contains no JSON object: {text[:200]}")
