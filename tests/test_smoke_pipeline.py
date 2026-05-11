"""End-to-end smoke test: init DB with samples and run a backtest."""

from __future__ import annotations

import os

import pytest


@pytest.mark.slow
def test_full_sample_pipeline(monkeypatch, tmp_path):
    """Run the full sample-data pipeline; should produce non-empty metrics."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'edpt.sqlite'}")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    # Reload settings after env mutation.
    from core import config
    config.reload_settings()

    from scripts.init_db import main as init_main
    from scripts.run_backtest import main as bt_main

    assert init_main(["--use-samples"]) == 0
    rc = bt_main(["--use-samples", "--no-plot", "--out-dir", str(tmp_path / "out"), "--max-pairs", "10"])
    assert rc == 0
    # Metrics file exists and parses to non-empty dict.
    import json

    metrics = json.loads((tmp_path / "out" / "metrics.json").read_text(encoding="utf-8"))
    assert "sharpe" in metrics
