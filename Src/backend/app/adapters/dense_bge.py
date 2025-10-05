"""Adapter around sentence-transformers for dense embeddings."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from sentence_transformers import SentenceTransformer

from app.config import settings


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    """Lazily load and cache the embedding model."""
    return SentenceTransformer(settings.bge_model)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts as dense vectors."""
    model = _model()
    return model.encode(texts, normalize_embeddings=True).tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Alias used by ingestion_service."""
    return embed_texts(texts)


def embed_one(text: str) -> List[float]:
    """Embed a single string as a dense vector."""
    return embed_texts([text])[0]
