"""Sentence embeddings with a hash-based fallback.

Why a fallback?
---------------
``sentence-transformers`` + ``torch`` is a 1+ GB install and the BGE model is
~1.3 GB to download.  CI workflows and no-API users need *something* to put in
the vector store immediately, so we ship a deterministic feature-hashing
embedder.  The default ``Embedder`` auto-detects which one to use.

The fallback is obviously inferior to BGE; downstream consumers can detect
which one is active via :attr:`Embedder.kind`.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from functools import lru_cache

import numpy as np

from core.config import settings
from core.logger import get_logger

log = get_logger(__name__)


_FALLBACK_DIM = 256
_BGE_DIM = 1024  # bge-large-zh-v1.5 -> 1024


class Embedder:
    """Embed text into fixed-size float32 vectors.

    Parameters
    ----------
    model_name
        Hugging Face model id; ignored when ``use_fallback=True``.
    use_fallback
        Force the hash-based embedder.  ``None`` lets the class auto-detect.
    """

    def __init__(self, model_name: str | None = None, use_fallback: bool | None = None) -> None:
        self.model_name = model_name or settings.embedding_model
        self._st_model = None
        self._kind = "fallback"

        if use_fallback is True:
            self._kind = "fallback"
            return
        try:
            # Lazy import: only pay the cost when the user actually wants BGE.
            from sentence_transformers import SentenceTransformer

            self._st_model = SentenceTransformer(self.model_name)
            self._kind = "sentence-transformers"
            log.info("loaded embedding model '{}'", self.model_name)
        except Exception as e:
            if use_fallback is False:
                # User explicitly demanded BGE; re-raise to make it visible.
                raise
            log.warning("sentence-transformers unavailable ({}); using hash fallback", e)
            self._kind = "fallback"

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def dim(self) -> int:
        return _BGE_DIM if self._kind == "sentence-transformers" else _FALLBACK_DIM

    def encode(self, texts: Iterable[str]) -> np.ndarray:
        """Return a ``(N, dim)`` float32 array."""
        texts = list(texts)
        if self._st_model is not None:
            return self._st_model.encode(texts, normalize_embeddings=True).astype(np.float32)
        return np.vstack([_hash_embed(t) for t in texts]).astype(np.float32)


@lru_cache(maxsize=1)
def get_default_embedder() -> Embedder:
    """Process-wide singleton."""
    return Embedder()


# ----------------------------------------------------------- fallback impl
_WORD_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9]+")


def _hash_embed(text: str) -> np.ndarray:
    """Deterministic feature-hashed embedding.

    Splits text into Chinese characters + ASCII tokens, hashes each into a
    fixed-size vector, and L2-normalises the result.  Not as good as BGE,
    but produces reasonable cosine similarities between related Chinese
    sentences (we tested informally on event-classification prompts).
    """
    vec = np.zeros(_FALLBACK_DIM, dtype=np.float32)
    if not text:
        return vec
    tokens = _WORD_RE.findall(text)
    for tok in tokens:
        h = int.from_bytes(hashlib.md5(tok.encode("utf-8")).digest()[:4], "little")
        idx = h % _FALLBACK_DIM
        sign = 1.0 if (h >> 31) & 1 else -1.0
        vec[idx] += sign
    n = float(np.linalg.norm(vec))
    if n > 0:
        vec /= n
    return vec
