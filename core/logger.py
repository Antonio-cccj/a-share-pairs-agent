"""Loguru-based structured logger.

Why loguru?
-----------
The user rules require Winston-style structured logging.  Loguru is the
closest Python equivalent: zero-config sinks, JSON serialization, rotation,
contextual binding, and TRACE/DEBUG/INFO/SUCCESS/WARNING/ERROR/CRITICAL levels.

Usage
-----
>>> from core.logger import get_logger
>>> log = get_logger(__name__)
>>> log.info("ingested {n} rows", n=1234)

Side effects
------------
The first call to :func:`configure_logging` installs:

- A coloured stderr sink (level driven by ``LOG_LEVEL`` env).
- A rotating file sink at ``{LOG_DIR}/app.log`` (10 MB rotation, 14-day retention).
- A JSON file sink at ``{LOG_DIR}/app.jsonl`` for machine ingestion.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from loguru import logger as _logger

from core.config import settings

_CONFIGURED = False


def configure_logging(level: str | None = None, log_dir: Path | None = None) -> None:
    """Initialise the global loguru logger.  Idempotent across calls.

    Parameters
    ----------
    level
        Optional override for the console level (defaults to ``LOG_LEVEL`` env).
    log_dir
        Optional override for the log directory.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    eff_level = (level or settings.log_level).upper()
    eff_dir = Path(log_dir or settings.log_dir)
    eff_dir.mkdir(parents=True, exist_ok=True)

    # Reset any default sinks Loguru pre-installs.
    _logger.remove()

    # Coloured console sink.
    _logger.add(
        sys.stderr,
        level=eff_level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    # Human-readable rotating file sink.
    _logger.add(
        eff_dir / "app.log",
        level="DEBUG",
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
        enqueue=True,  # async-safe across processes
        backtrace=True,
        diagnose=False,  # avoid leaking variables in shared logs
    )

    # Structured JSON sink (one record per line).
    _logger.add(
        eff_dir / "app.jsonl",
        level="DEBUG",
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
        serialize=True,
        enqueue=True,
    )

    _CONFIGURED = True
    _logger.debug("logging configured | level={} | dir={}", eff_level, eff_dir)


def get_logger(name: str | None = None, **bindings: Any):
    """Return a child logger with optional context bindings.

    Examples
    --------
    >>> log = get_logger(__name__, ticker="600519.SH")
    >>> log.info("priced")
    """
    configure_logging()
    bound = (
        _logger.bind(name=name or "root", **bindings)
        if bindings
        else _logger.bind(name=name or "root")
    )
    return bound
