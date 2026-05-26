"""CLI: run the event classifier on the announcements table."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.announcement_loader import load_announcements_to_chroma  # noqa: E402
from agents.event_rag_agent import EventRAGAgent  # noqa: E402
from core.data import IngestService  # noqa: E402
from core.logger import get_logger  # noqa: E402
from core.rag import ChromaStore  # noqa: E402

log = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reindex", action="store_true", help="Re-embed announcements into Chroma first."
    )
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    args = parser.parse_args(argv)

    svc = IngestService()
    if args.reindex:
        load_announcements_to_chroma(svc, ChromaStore())
    agent = EventRAGAgent(ingest=svc)
    n = agent.run_batch(start=args.start, endd=args.end)
    log.info("classified events={}", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
