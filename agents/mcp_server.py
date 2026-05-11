"""MCP server exposing event-classification tools.

Run it with::

    python -m agents.mcp_server

Then add it to Claude Desktop / Cursor's MCP config (see docs/mcp_usage.md).

When the optional ``mcp`` SDK is missing we print a friendly diagnostic
instead of crashing the import.  This keeps the package importable in CI
where the SDK might not be installed.
"""

from __future__ import annotations

from typing import Any

from agents.event_rag_agent import EventRAGAgent
from core.config import settings
from core.logger import get_logger

log = get_logger(__name__)


def _build_server():
    """Lazy build the FastMCP server so import never blows up."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:  # pragma: no cover - optional dep
        raise SystemExit(
            "The `mcp` package is not installed.  `pip install mcp` to enable the MCP server."
        ) from e

    agent = EventRAGAgent()
    mcp = FastMCP("event-driven-pairs-trading-cn")

    @mcp.tool()
    def classify_announcement(title: str, content: str, ts_code: str = "") -> dict[str, Any]:
        """Classify a single A-share announcement into one of 9 risk-event types.

        Args:
            title:   announcement title (Chinese).
            content: announcement body (Chinese).
            ts_code: optional Tushare-style ticker, e.g. 600519.SH.

        Returns:
            A dict with event_type / severity / rationale / confidence.
        """
        rec = agent.classify(title=title, content=content, ts_code=ts_code)
        return rec.as_dict()

    @mcp.tool()
    def list_event_types() -> dict[str, Any]:
        """Return the 9-event taxonomy (label, severity, keywords)."""
        return agent.taxonomy

    @mcp.tool()
    def run_event_batch(start: str, end: str) -> dict[str, Any]:
        """Run the classifier on every announcement in [start, end] (YYYY-MM-DD)."""
        n = agent.run_batch(start=start, endd=end)
        return {"classified": n, "start": start, "end": end}

    log.info("MCP server registered tools: classify_announcement, list_event_types, run_event_batch")
    return mcp


def main() -> None:
    """Entry point used by ``python -m agents.mcp_server``."""
    mcp = _build_server()
    log.info("starting MCP server (provider={})", settings.llm_provider)
    mcp.run()


if __name__ == "__main__":
    main()
