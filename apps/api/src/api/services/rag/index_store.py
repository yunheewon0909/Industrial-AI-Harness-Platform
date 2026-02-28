from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from api.services.rag.types import ChunkRecord


def persist_index(
    output_dir: Path,
    *,
    chunks: list[ChunkRecord],
    embeddings: list[list[float]],
) -> Path:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    for chunk, embedding in zip(chunks, embeddings):
        records.append(
            {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "source_path": chunk.source_path,
                "text": chunk.text,
                "embedding": embedding,
            }
        )

    payload = {
        "version": "r1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chunk_count": len(records),
        "records": records,
    }

    index_file = output_dir / "index.json"
    index_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return index_file
