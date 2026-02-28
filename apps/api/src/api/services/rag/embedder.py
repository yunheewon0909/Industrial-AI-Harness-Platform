from __future__ import annotations

import hashlib
import math

from api.services.rag.types import ChunkRecord


def _deterministic_embedding(text: str, *, dimensions: int) -> list[float]:
    if dimensions <= 0:
        raise ValueError("dimensions must be > 0")

    seed = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[int] = []
    digest = seed

    while len(values) < dimensions:
        digest = hashlib.sha256(digest + seed).digest()
        values.extend(digest)

    vector = [((value / 127.5) - 1.0) for value in values[:dimensions]]
    norm = math.sqrt(sum(value * value for value in vector))
    if norm > 0:
        return [value / norm for value in vector]

    return vector


def embed_chunks(chunks: list[ChunkRecord], *, dimensions: int) -> list[list[float]]:
    return [_deterministic_embedding(chunk.text, dimensions=dimensions) for chunk in chunks]
