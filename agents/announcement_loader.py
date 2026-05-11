"""Bulk-load announcements into the vector store.

Two responsibilities:

1. Read the ``announcements`` table from SQLite/PG.
2. Index each row in the project's ``ChromaStore`` collection so the agent
   can perform similarity search at query time.
"""

from __future__ import annotations

from core.data import IngestService
from core.logger import get_logger
from core.rag import ChromaStore

log = get_logger(__name__)


def load_announcements_to_chroma(
    ingest: IngestService,
    store: ChromaStore | None = None,
    codes: list[str] | None = None,
    start: str | None = None,
    endd: str | None = None,
) -> int:
    """Read announcements -> upsert into Chroma.  Returns the row count."""
    store = store or ChromaStore()
    df = ingest.load_announcements(codes=codes, start=start, endd=endd)
    if df.empty:
        log.warning("no announcements in database; consider ingesting first")
        return 0
    # Concatenate title + content as the embedded document.
    docs = (df["title"].fillna("") + "\n" + df["content"].fillna("")).tolist()
    ids = df["ann_id"].astype(str).tolist()
    metas = [
        {
            "ts_code": str(row["ts_code"]),
            "ann_date": str(row["ann_date"]),
            "source": str(row.get("source", "")),
        }
        for _, row in df.iterrows()
    ]
    n = store.upsert(ids=ids, texts=docs, metadatas=metas)
    log.info("upserted {} announcements into chroma", n)
    return n
