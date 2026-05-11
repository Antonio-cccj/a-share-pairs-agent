"""Centralised configuration loaded from environment variables / .env file.

Uses :mod:`pydantic-settings` so that:

- Each setting has an explicit type and default.
- All env vars are documented in `.env.example`.
- Settings can be overridden at runtime via constructor kwargs (handy in tests).

The :class:`Settings` object is process-wide and exposed via :func:`get_settings`
(LRU-cached singleton).  Importing :data:`settings` directly is also fine.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProviderName = Literal["anthropic", "openai", "deepseek", "zhipu", "ollama", "mock"]


class Settings(BaseSettings):
    """Aggregated application settings (env-driven).

    Notes
    -----
    The grouping is purely for readability; pydantic still treats every field as
    a flat env variable.  Do **not** rename a field without updating
    ``.env.example`` accordingly.
    """

    # pydantic-settings v2 config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unknown env vars rather than crash
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ Data
    tushare_token: str = Field(default="", description="Tushare Pro token; leave empty to use akshare fallback.")
    data_cache_dir: Path = Field(default=Path("./data/cache"))
    database_url: str = Field(default="sqlite:///./data/edpt.sqlite")

    # ------------------------------------------------------------------ LLM
    llm_provider: LLMProviderName = Field(default="mock")
    llm_model: str = Field(default="")
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=2048, gt=0)

    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-sonnet-4-5")

    openai_api_key: str = Field(default="")
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    openai_model: str = Field(default="gpt-4o-mini")

    deepseek_api_key: str = Field(default="")
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1")
    deepseek_model: str = Field(default="deepseek-chat")

    zhipu_api_key: str = Field(default="")
    zhipu_model: str = Field(default="glm-4-flash")

    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    ollama_model: str = Field(default="qwen2.5:7b")

    # ------------------------------------------------------------------ RAG
    embedding_model: str = Field(default="BAAI/bge-large-zh-v1.5")
    chroma_persist_dir: Path = Field(default=Path("./chroma_db"))
    chroma_collection: str = Field(default="announcements")

    # -------------------------------------------------------------- Backtest
    backtest_commission_bps: float = Field(default=3.0)
    backtest_stamp_duty_bps: float = Field(default=10.0)
    backtest_slippage_bps: float = Field(default=5.0)
    backtest_start: str = Field(default="2021-01-01")
    backtest_end: str = Field(default="2024-12-31")

    # --------------------------------------------------------------- Logging
    log_level: str = Field(default="INFO")
    log_dir: Path = Field(default=Path("./logs"))

    # ------------------------------------------------------ Convenience API
    def is_mock_llm(self) -> bool:
        """Return True when LLM calls should be replaced by rule-based fallback.

        Used by :mod:`core.llm.factory` and by tests / CI to avoid network calls.
        """
        return self.llm_provider == "mock"

    def ensure_dirs(self) -> None:
        """Create any data/log directories the app might write into.

        Idempotent; safe to call multiple times (e.g. from CLI entry points).
        """
        for p in (self.data_cache_dir, self.log_dir, self.chroma_persist_dir):
            Path(p).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton :class:`Settings` instance.

    Use :func:`reload_settings` in tests if you mutate env vars at runtime.
    """
    return Settings()


def reload_settings() -> Settings:
    """Force a re-read of env vars (e.g. after monkeypatching in tests)."""
    get_settings.cache_clear()
    return get_settings()


settings = get_settings()
