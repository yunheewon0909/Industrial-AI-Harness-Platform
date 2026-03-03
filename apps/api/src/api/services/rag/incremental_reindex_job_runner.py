from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from time import perf_counter
from typing import TypedDict

from api.config import get_settings
from api.services.rag.chunker import chunk_documents
from api.services.rag.embedding_client import EmbeddingClient, OllamaEmbeddingClient
from api.services.rag.loader import load_documents
from api.services.rag.sqlite_store import (
    StoredDocument,
    compute_content_hash,
    delete_document_and_chunks,
    ensure_sqlite_schema,
    get_documents_map_by_source_path,
    replace_chunks_for_doc,
    sqlite_index_stats,
    upsert_document,
)
from api.services.rag.types import SourceDocument


class IncrementalReindexResult(TypedDict):
    mode: str
    scanned_files: int
    unchanged: int
    new: int
    updated: int
    removed: int
    documents_total_after: int
    chunks_total_after: int
    duration_ms: int
    embed_model: str
    max_embedding_dim: int
    db_path: str


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rag-incremental-reindex-runner",
        description="Run RAG sqlite incremental reindex (changed docs only)",
    )
    parser.add_argument(
        "--payload-json",
        default=None,
        help="Optional JSON object payload with runtime overrides (source_dir/chunk_size/chunk_overlap/db_path)",
    )
    return parser


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


def _load_documents_allow_empty(source_dir: Path) -> list[SourceDocument]:
    try:
        return load_documents(source_dir)
    except ValueError as exc:
        if "No non-empty supported documents found" in str(exc):
            return []
        raise


def _classify_documents(
    scanned_docs: list[SourceDocument],
    stored_docs_by_path: dict[str, StoredDocument],
) -> tuple[list[SourceDocument], list[SourceDocument], list[tuple[StoredDocument, SourceDocument]], list[StoredDocument]]:
    scanned_by_path = {document.source_path: document for document in scanned_docs}

    unchanged_docs: list[SourceDocument] = []
    new_docs: list[SourceDocument] = []
    updated_docs: list[tuple[StoredDocument, SourceDocument]] = []

    for source_path, scanned_doc in scanned_by_path.items():
        existing = stored_docs_by_path.get(source_path)
        scanned_hash = compute_content_hash(scanned_doc.text)
        if existing is None:
            new_docs.append(scanned_doc)
            continue
        if existing.content_hash == scanned_hash:
            unchanged_docs.append(scanned_doc)
            continue
        updated_docs.append((existing, scanned_doc))

    removed_docs = [
        stored_doc
        for source_path, stored_doc in stored_docs_by_path.items()
        if source_path not in scanned_by_path
    ]

    return unchanged_docs, new_docs, updated_docs, removed_docs


def _upsert_and_replace_doc(
    connection: sqlite3.Connection,
    *,
    doc_id: str,
    source_document: SourceDocument,
    chunk_size: int,
    chunk_overlap: int,
    embedding_client: EmbeddingClient,
) -> None:
    normalized_document = SourceDocument(
        doc_id=doc_id,
        source_path=source_document.source_path,
        text=source_document.text,
    )
    chunks = chunk_documents([normalized_document], chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    embeddings = embedding_client.embed_texts([chunk.text for chunk in chunks]) if chunks else []

    upsert_document(
        connection,
        doc_id=doc_id,
        source_path=normalized_document.source_path,
        content_hash=compute_content_hash(normalized_document.text),
    )
    replace_chunks_for_doc(
        connection,
        doc_id=doc_id,
        chunks=chunks,
        embeddings=embeddings,
    )


def run_incremental_reindex_job(
    *,
    source_dir: Path,
    db_path: Path,
    chunk_size: int,
    chunk_overlap: int,
    embedding_client: EmbeddingClient,
    embed_model: str,
) -> IncrementalReindexResult:
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    start = perf_counter()
    scanned_docs = _load_documents_allow_empty(source_dir)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        ensure_sqlite_schema(connection)
        connection.execute("PRAGMA foreign_keys = ON")

        stored_docs_by_path = get_documents_map_by_source_path(connection)
        unchanged_docs, new_docs, updated_docs, removed_docs = _classify_documents(
            scanned_docs,
            stored_docs_by_path,
        )

        try:
            connection.execute("BEGIN")
            for removed_doc in removed_docs:
                delete_document_and_chunks(connection, removed_doc.doc_id)

            for new_doc in new_docs:
                _upsert_and_replace_doc(
                    connection,
                    doc_id=new_doc.doc_id,
                    source_document=new_doc,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    embedding_client=embedding_client,
                )

            for existing_doc, updated_doc in updated_docs:
                _upsert_and_replace_doc(
                    connection,
                    doc_id=existing_doc.doc_id,
                    source_document=updated_doc,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    embedding_client=embedding_client,
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

        documents_total_after, chunks_total_after, max_embedding_dim = sqlite_index_stats(connection)

    duration_ms = int((perf_counter() - start) * 1000)
    return {
        "mode": "incremental",
        "scanned_files": len(scanned_docs),
        "unchanged": len(unchanged_docs),
        "new": len(new_docs),
        "updated": len(updated_docs),
        "removed": len(removed_docs),
        "documents_total_after": documents_total_after,
        "chunks_total_after": chunks_total_after,
        "duration_ms": duration_ms,
        "embed_model": embed_model,
        "max_embedding_dim": max_embedding_dim,
        "db_path": str(db_path),
    }


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

        embedding_client = OllamaEmbeddingClient(
            base_url=settings.ollama_embed_base_url,
            model=settings.ollama_embed_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )

        metrics = run_incremental_reindex_job(
            source_dir=source_dir,
            db_path=db_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_client=embedding_client,
            embed_model=settings.ollama_embed_model,
        )
    except Exception as exc:
        print(f"[rag-incremental-reindex-runner] failed: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc

    print(json.dumps(metrics), flush=True)


if __name__ == "__main__":
    main()
