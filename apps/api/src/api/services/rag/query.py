from __future__ import annotations

import json
from pathlib import Path

from api.services.rag.embedder import embed_text
from api.services.rag.types import QueryHit


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _load_index_records(index_dir: Path) -> list[dict[str, object]]:
    index_file = index_dir / "index.json"
    if not index_file.exists():
        raise FileNotFoundError(
            f"RAG index file not found: {index_file}. Run `uv run --project apps/api rag-ingest` first."
        )

    payload = json.loads(index_file.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError(f"Invalid index payload in {index_file}: 'records' must be a list")

    return records


def search_index(*, index_dir: Path, query_text: str, top_k: int = 3) -> list[QueryHit]:
    normalized_query = query_text.strip()
    if not normalized_query:
        raise ValueError("query_text must not be empty")

    records = _load_index_records(index_dir)
    if not records:
        return []

    first_embedding = records[0].get("embedding")
    if not isinstance(first_embedding, list) or not first_embedding:
        raise ValueError("Invalid index payload: missing embedding vectors")

    dimensions = len(first_embedding)
    query_embedding = embed_text(normalized_query, dimensions=dimensions)

    hits: list[QueryHit] = []
    for record in records:
        embedding = record.get("embedding")
        chunk_id = record.get("chunk_id")
        source_path = record.get("source_path")
        text = record.get("text")

        if (
            not isinstance(embedding, list)
            or not isinstance(chunk_id, str)
            or not isinstance(source_path, str)
            or not isinstance(text, str)
        ):
            continue

        score = _dot(query_embedding, [float(value) for value in embedding])
        hits.append(
            QueryHit(
                chunk_id=chunk_id,
                source_path=source_path,
                text=text,
                score=score,
            )
        )

    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits[: max(1, top_k)]
