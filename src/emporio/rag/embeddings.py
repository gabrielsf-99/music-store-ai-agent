"""Local multilingual embeddings (fastembed / ONNX, no API key)."""

import os
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path

# Windows without developer mode cannot create symlinks; the HF cache still works without them.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384  # must match vector(...) in db/schema.sql
CACHE_DIR = Path(__file__).resolve().parents[3] / ".cache" / "fastembed"

Embedder = Callable[[Sequence[str]], list[list[float]]]


@lru_cache
def _model():
    from fastembed import TextEmbedding  # heavy import, only when embeddings are needed

    return TextEmbedding(EMBEDDING_MODEL, cache_dir=str(CACHE_DIR))


def warm_up() -> None:
    """Load the model up front, so the first customer question does not pay for it."""
    _model()


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    return [vector.tolist() for vector in _model().embed(list(texts))]


def to_pgvector(vector: Sequence[float]) -> str:
    """pgvector text format: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{value:.7f}" for value in vector) + "]"
