"""Core shared modules for the A-share pairs agent.

Submodules
----------
- :mod:`core.config`  : pydantic-settings based env loader.
- :mod:`core.logger`  : loguru-based structured logger.
- :mod:`core.data`    : Tushare / akshare clients and SQLite/PG ingest layer.
- :mod:`core.llm`     : Provider-agnostic LLM adapter (Anthropic/OpenAI/DeepSeek/Zhipu/Ollama/Mock).
- :mod:`core.rag`     : ChromaDB persistent store and BGE-large-zh embeddings.
"""

__all__ = ["config", "logger", "data", "llm", "rag"]
