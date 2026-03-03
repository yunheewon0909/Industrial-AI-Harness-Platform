from __future__ import annotations

from array import array
from dataclasses import dataclass
import hashlib
from pathlib import Path
import sqlite3

from api.services.rag.types import ChunkRecord, SourceDocument


@dataclass(frozen=True)
class StoredChunk:
    chunk_id: str
    source_path: str
    text: str
    embedding: list[float]


@dataclass(frozen=True)
class StoredDocument:
    doc_id: str
    source_path: str
    content_hash: str


def _encode_embedding(values: list[float]) -> bytes:
    vector = array("f", values)
    return vector.tobytes()


def _decode_embedding(blob: bytes) -> list[float]:
    vector = array("f")
    vector.frombytes(blob)
    return vector.tolist()


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_index(chunk: ChunkRecord) -> int:
    _, separator, suffix = chunk.chunk_id.rpartition("-")
    if separator and suffix.isdigit():
        return int(suffix)
    raise ValueError(f"Invalid chunk id format: {chunk.chunk_id}")


def ensure_sqlite_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            source_path TEXT NOT NULL UNIQUE,
            content_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            token_count INTEGER,
            embedding BLOB NOT NULL,
            embedding_dim INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE,
            UNIQUE (doc_id, chunk_index)
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
        CREATE INDEX IF NOT EXISTS idx_documents_source_path ON documents(source_path);
        CREATE INDEX IF NOT EXISTS idx_chunks_created_at ON chunks(created_at);
        """
    )


def persist_sqlite_index(
    db_path: Path,
    *,
    documents: list[SourceDocument],
    chunks: list[ChunkRecord],
    embeddings: list[list[float]],
) -> Path:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        ensure_sqlite_schema(connection)
        connection.execute("DELETE FROM chunks")
        connection.execute("DELETE FROM documents")

        connection.executemany(
            "INSERT INTO documents (id, source_path, content_hash) VALUES (?, ?, ?)",
            [
                (document.doc_id, document.source_path, compute_content_hash(document.text))
                for document in sorted(documents, key=lambda item: item.doc_id)
            ],
        )

        connection.executemany(
            """
            INSERT INTO chunks (id, doc_id, chunk_index, text, token_count, embedding, embedding_dim)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk.chunk_id,
                    chunk.doc_id,
                    _chunk_index(chunk),
                    chunk.text,
                    len(chunk.text.split()),
                    sqlite3.Binary(_encode_embedding(embedding)),
                    len(embedding),
                )
                for chunk, embedding in zip(chunks, embeddings)
            ],
        )

    return db_path


def get_documents_map_by_source_path(connection: sqlite3.Connection) -> dict[str, StoredDocument]:
    rows = connection.execute(
        """
        SELECT id, source_path, content_hash
        FROM documents
        ORDER BY source_path
        """
    ).fetchall()
    documents: dict[str, StoredDocument] = {}
    for row in rows:
        if len(row) != 3:
            continue
        doc_id, source_path, content_hash = row
        if (
            not isinstance(doc_id, str)
            or not isinstance(source_path, str)
            or not isinstance(content_hash, str)
        ):
            continue
        documents[source_path] = StoredDocument(
            doc_id=doc_id,
            source_path=source_path,
            content_hash=content_hash,
        )
    return documents


def upsert_document(
    connection: sqlite3.Connection,
    *,
    doc_id: str,
    source_path: str,
    content_hash: str,
) -> None:
    connection.execute(
        """
        INSERT INTO documents (id, source_path, content_hash)
        VALUES (?, ?, ?)
        ON CONFLICT(source_path) DO UPDATE SET
            id = excluded.id,
            content_hash = excluded.content_hash
        """,
        (doc_id, source_path, content_hash),
    )


def delete_document_and_chunks(connection: sqlite3.Connection, doc_id: str) -> None:
    connection.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
    connection.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


def replace_chunks_for_doc(
    connection: sqlite3.Connection,
    *,
    doc_id: str,
    chunks: list[ChunkRecord],
    embeddings: list[list[float]],
) -> None:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")

    connection.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
    if not chunks:
        return

    connection.executemany(
        """
        INSERT INTO chunks (id, doc_id, chunk_index, text, token_count, embedding, embedding_dim)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                chunk.chunk_id,
                chunk.doc_id,
                _chunk_index(chunk),
                chunk.text,
                len(chunk.text.split()),
                sqlite3.Binary(_encode_embedding(embedding)),
                len(embedding),
            )
            for chunk, embedding in zip(chunks, embeddings)
        ],
    )


def sqlite_index_stats(connection: sqlite3.Connection) -> tuple[int, int, int]:
    documents_total = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
    chunks_total = int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
    max_embedding_dim = int(
        connection.execute("SELECT COALESCE(MAX(embedding_dim), 0) FROM chunks").fetchone()[0]
    )
    return documents_total, chunks_total, max_embedding_dim


def load_sqlite_chunks(db_path: Path) -> list[StoredChunk]:
    if not db_path.exists():
        raise FileNotFoundError(f"RAG sqlite index file not found: {db_path}")

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT c.id, d.source_path, c.text, c.embedding, c.embedding_dim
            FROM chunks c
            JOIN documents d ON d.id = c.doc_id
            ORDER BY c.id
            """
        ).fetchall()

    chunks: list[StoredChunk] = []
    for chunk_id, source_path, text, embedding_blob, embedding_dim in rows:
        if (
            not isinstance(chunk_id, str)
            or not isinstance(source_path, str)
            or not isinstance(text, str)
            or not isinstance(embedding_blob, bytes)
            or not isinstance(embedding_dim, int)
        ):
            continue

        embedding = _decode_embedding(embedding_blob)
        if len(embedding) != embedding_dim:
            continue

        chunks.append(
            StoredChunk(
                chunk_id=chunk_id,
                source_path=source_path,
                text=text,
                embedding=embedding,
            )
        )
    return chunks
