"""Pluggable text-embedding providers.

* ``hash``                – dependency-free feature hashing. Deterministic and fast, but only
                            captures word overlap (lexical), not meaning. Good for local dev/tests.
* ``sentence-transformers`` – real semantic embeddings. Install ``sentence-transformers`` and set
                            EMBEDDING_PROVIDER=sentence-transformers. Make sure EMBEDDING_DIM
                            matches the model (all-MiniLM-L6-v2 -> 384).

If you change provider/model/dimension on an existing database, re-run
``python -m scripts.reindex_embeddings`` (and recreate the column if the dimension changed).
"""
import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from app.config import settings

_TOKEN = re.compile(r"\w+", re.UNICODE)


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    return vec if norm == 0 else [v / norm for v in vec]


class HashEmbedding:
    def __init__(self, dim: int):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = _TOKEN.findall(text.lower())
        grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        for gram in grams:
            digest = hashlib.md5(gram.encode()).digest()
            value = int.from_bytes(digest[:8], "big")
            sign = 1.0 if digest[8] & 1 else -1.0
            vec[value % self.dim] += sign
        return _normalize(vec)


class SentenceTransformerEmbedding:
    def __init__(self, model_name: str, dim: int):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install sentence-transformers to use EMBEDDING_PROVIDER=sentence-transformers"
            ) from exc
        self.model = SentenceTransformer(model_name)
        actual = self.model.get_sentence_embedding_dimension()
        if actual != dim:
            raise RuntimeError(f"EMBEDDING_DIM={dim} but model outputs {actual} dimensions")

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self.model.encode(texts, normalize_embeddings=True)]


@lru_cache
def get_provider() -> EmbeddingProvider:
    if settings.embedding_provider == "sentence-transformers":
        return SentenceTransformerEmbedding(settings.embedding_model, settings.embedding_dim)
    if settings.embedding_provider == "hash":
        return HashEmbedding(settings.embedding_dim)
    raise RuntimeError(f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider}")


def embed_text(text: str) -> list[float]:
    return get_provider().embed([text])[0]


def book_text(title: str, authors: list[str], description: str | None) -> str:
    parts = [title]
    if authors:
        parts.append("by " + ", ".join(authors))
    if description:
        parts.append(description)
    return ". ".join(parts)
