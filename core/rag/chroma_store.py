"""ChromaDB persistent vector store with an in-memory fallback.

Public API
----------
- :meth:`ChromaStore.upsert` - add or update documents.
- :meth:`ChromaStore.query`  - top-K cosine-similarity search.
- :meth:`ChromaStore.count`  - count documents in the collection.

When ``chromadb`` is not installed (e.g. CI minimal image), we silently switch
to a numpy-backed in-process store with the same interface so downstream code
stays unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from core.config import settings
from core.logger import get_logger
from core.rag.embed import Embedder, get_default_embedder

log = get_logger(__name__)


class ChromaStore:
    """Adapter around ChromaDB's ``PersistentClient`` with a numpy fallback."""

    def __init__(
        self,
        persist_dir: Path | None = None,
        collection: str | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self.persist_dir = Path(persist_dir or settings.chroma_persist_dir)
        self.collection_name = collection or settings.chroma_collection
        self.embedder = embedder or get_default_embedder()
        self._chroma_client: Any = None
        self._collection: Any = None
        self._mem: dict[str, dict[str, Any]] | None = None

        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings  # noqa: F401

            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=str(self.persist_dir))
            self._collection = self._chroma_client.get_or_create_collection(
                self.collection_name, metadata={"hnsw:space": "cosine"}
            )
            log.info(
                "chromadb collection '{}' opened at {}", self.collection_name, self.persist_dir
            )
        except Exception as e:
            log.warning("chromadb unavailable ({}); using in-memory fallback", e)
            self._mem = {}

    # --------------------------------------------------------------- upsert
    def upsert(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> int:
        """Insert/replace *texts* keyed by *ids*; returns the number written."""
        if not ids:
            return 0
        if len(texts) != len(ids):
            raise ValueError("ids and texts must have the same length")
        metadatas = metadatas or [{} for _ in ids]
        embeddings = self.embedder.encode(texts).tolist()

        if self._collection is not None:
            self._collection.upsert(
                ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings
            )
            return len(ids)

        assert self._mem is not None
        for i, t, m, e in zip(ids, texts, metadatas, embeddings):
            self._mem[i] = {"text": t, "meta": m, "emb": np.array(e, dtype=np.float32)}
        return len(ids)

    # ---------------------------------------------------------------- query
    def query(self, query_text: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Return top-K hits ranked by cosine similarity."""
        q_emb = self.embedder.encode([query_text])[0]

        if self._collection is not None:
            res = self._collection.query(query_embeddings=[q_emb.tolist()], n_results=top_k)
            ids = res.get("ids", [[]])[0]
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[]])[0]
            return [
                {"id": i, "text": d, "meta": m, "score": 1.0 - float(s)}
                for i, d, m, s in zip(ids, docs, metas, dists)
            ]

        assert self._mem is not None
        if not self._mem:
            return []
        ids = list(self._mem.keys())
        mat = np.vstack([self._mem[i]["emb"] for i in ids])
        # Cosine similarity (embeddings come pre-normalised from BGE; for the
        # fallback they're also L2-normalised in _hash_embed).
        sims = mat @ q_emb
        idx = np.argsort(-sims)[:top_k]
        return [
            {
                "id": ids[i],
                "text": self._mem[ids[i]]["text"],
                "meta": self._mem[ids[i]]["meta"],
                "score": float(sims[i]),
            }
            for i in idx
        ]

    def count(self) -> int:
        if self._collection is not None:
            return int(self._collection.count())
        return len(self._mem or {})
