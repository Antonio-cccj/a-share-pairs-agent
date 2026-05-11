"""Retrieval-Augmented Generation primitives.

- :mod:`core.rag.embed`        - embedding back-ends (BGE / hash fallback).
- :mod:`core.rag.chroma_store` - persistent vector store backed by ChromaDB.
"""

from core.rag.chroma_store import ChromaStore  # noqa: F401
from core.rag.embed import Embedder, get_default_embedder  # noqa: F401
