"""Pytest fixtures."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _mock_llm_env(monkeypatch):
    """Force mock LLM in every test so we never hit a network."""
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("TUSHARE_TOKEN", "")
    # reload settings so the new env values stick
    from core import config

    config.reload_settings()


@pytest.fixture
def tmp_db_url(tmp_path: Path) -> str:
    """Spin up a throw-away SQLite file per test."""
    return f"sqlite:///{tmp_path / 'test.sqlite'}"
