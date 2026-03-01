from pathlib import Path
import sqlite3

import pytest

from api.services.rag.chunker import chunk_documents
from api.services.rag.loader import load_documents
from api.services.rag.sqlite_store import load_sqlite_chunks, persist_sqlite_index


def _embedding_for_chunk(text: str) -> list[float]:
    normalized = text.lower()
    return [
        float(normalized.count("automation")),
        float(normalized.count("maintenance")),
        float(len(normalized) % 7),
    ]


def test_sqlite_store_roundtrip_and_schema(tmp_path: Path) -> None:
    source_dir = tmp_path / "sample_docs"
    source_dir.mkdir(parents=True)
    (source_dir / "a.txt").write_text(
        "automation automation maintenance line", encoding="utf-8"
    )
    (source_dir / "b.md").write_text(
        "maintenance checklist and safety automation", encoding="utf-8"
    )

    documents = load_documents(source_dir)
    chunks = chunk_documents(documents, chunk_size=80, chunk_overlap=10)
    embeddings = [_embedding_for_chunk(chunk.text) for chunk in chunks]

    db_path = tmp_path / "rag_index" / "rag.db"
    persist_sqlite_index(
        db_path,
        documents=documents,
        chunks=chunks,
        embeddings=embeddings,
    )

    assert db_path.exists()

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {"documents", "chunks"}.issubset(tables)

        document_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(documents)").fetchall()
        }
        assert {"id", "source_path", "content_hash", "created_at"}.issubset(document_columns)

        chunk_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(chunks)").fetchall()
        }
        assert {
            "id",
            "doc_id",
            "chunk_index",
            "text",
            "token_count",
            "embedding",
            "embedding_dim",
            "created_at",
        }.issubset(chunk_columns)

        document_count = connection.execute("SELECT count(*) FROM documents").fetchone()[0]
        chunk_count = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]

    assert document_count == len(documents)
    assert chunk_count == len(chunks)

    loaded_chunks = load_sqlite_chunks(db_path)
    assert len(loaded_chunks) == len(chunks)

    embeddings_by_chunk_id = {
        chunk.chunk_id: embedding for chunk, embedding in zip(chunks, embeddings)
    }
    for loaded_chunk in loaded_chunks:
        assert loaded_chunk.embedding == pytest.approx(
            embeddings_by_chunk_id[loaded_chunk.chunk_id], rel=1e-6, abs=1e-6
        )
