from __future__ import annotations

import argparse
import json
from pathlib import Path
import os
import sqlite3
import sys
from time import perf_counter
from typing import TypedDict

from api.config import get_settings
from api.services.rag.embedding_client import EmbeddingClient
from api.services.rag.ingest import ingest_documents


class ReindexResult(TypedDict):
    documents: int
    chunks: int
    db_path: str
    duration_ms: int
    max_embedding_dim: int
    embed_model: str


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rag-reindex-runner",
        description="Run RAG sqlite reindex with atomic replace",
    )
    parser.add_argument(
        "--payload-json",
        default=None,
        help="Optional JSON object payload with runtime overrides (source_dir/chunk_size/chunk_overlap/db_path)",
    )
    return parser


def _self_check_sqlite(db_path: Path) -> tuple[int, int]:
    with sqlite3.connect(db_path) as connection:
        chunk_count = int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        max_embedding_dim = int(
            connection.execute("SELECT COALESCE(MAX(embedding_dim), 0) FROM chunks").fetchone()[0]
        )

    if chunk_count <= 0:
        raise ValueError("reindex self-check failed: chunk count is zero")
    if max_embedding_dim <= 0:
        raise ValueError("reindex self-check failed: embedding dim is zero")

    return chunk_count, max_embedding_dim


def run_reindex_job(
    *,
    source_dir: Path,
    db_path: Path,
    chunk_size: int,
    chunk_overlap: int,
    embedding_client: EmbeddingClient | None = None,
) -> ReindexResult:
    tmp_db_path = db_path.with_suffix(f"{db_path.suffix}.tmp")
    start = perf_counter()

    if tmp_db_path.exists():
        tmp_db_path.unlink()

    try:
        summary = ingest_documents(
            source_dir=source_dir,
            db_path=tmp_db_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_client=embedding_client,
        )
        chunk_count, max_embedding_dim = _self_check_sqlite(tmp_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp_db_path, db_path)
    finally:
        if tmp_db_path.exists():
            tmp_db_path.unlink()

    duration_ms = int((perf_counter() - start) * 1000)
    return {
        "documents": summary.document_count,
        "chunks": chunk_count,
        "db_path": str(db_path),
        "duration_ms": duration_ms,
        "max_embedding_dim": max_embedding_dim,
        "embed_model": get_settings().ollama_embed_model,
    }


def _resolve_payload(payload_json_raw: str | None) -> dict[str, object]:
    if payload_json_raw is None:
        return {}
    parsed = json.loads(payload_json_raw)
    if not isinstance(parsed, dict):
        raise ValueError("payload_json must be a JSON object")
    return parsed


def _payload_int(payload: dict[str, object], key: str, default: int) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise ValueError(f"{key} must be an integer")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    settings = get_settings()

    try:
        payload = _resolve_payload(args.payload_json)
        source_dir = Path(str(payload.get("source_dir", settings.rag_source_dir)))
        db_path = Path(str(payload.get("db_path", settings.rag_db_path)))
        chunk_size = _payload_int(payload, "chunk_size", settings.rag_chunk_size)
        chunk_overlap = _payload_int(payload, "chunk_overlap", settings.rag_chunk_overlap)

        metrics = run_reindex_job(
            source_dir=source_dir,
            db_path=db_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    except Exception as exc:
        print(f"[rag-reindex-runner] failed: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc

    metrics["embed_model"] = settings.ollama_embed_model
    print(json.dumps(metrics), flush=True)


if __name__ == "__main__":
    main()
