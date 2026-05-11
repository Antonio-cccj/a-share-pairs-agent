"""LLM provider adapter layer.

Public surface
--------------
- :class:`core.llm.base.LLMProvider`      - abstract interface.
- :class:`core.llm.base.LLMMessage`       - chat message dataclass.
- :func:`core.llm.factory.build_llm`      - factory returning a provider by name.
- :class:`core.llm.mock_provider.MockLLM` - rule-based fallback used in CI & no-API mode.
"""

from core.llm.base import LLMMessage, LLMProvider  # noqa: F401
from core.llm.factory import build_llm  # noqa: F401
