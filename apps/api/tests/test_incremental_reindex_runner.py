from pathlib import Path
import sqlite3

from api.services.rag.chunker import chunk_documents
from api.services.rag.incremental_reindex_job_runner import run_incremental_reindex_job
from api.services.rag.loader import load_documents
from api.services.rag.sqlite_store import persist_sqlite_index


class TrackingEmbeddingClient:
    def __init__(self, dimensions: int) -> None:
        self._dimensions = dimensions
        self.calls: list[str] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.extend(texts)
        return [[1.0] * self._dimensions for _ in texts]


class ConstantEmbeddingClient:
    def __init__(self, dimensions: int) -> None:
        self._dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] * self._dimensions for _ in texts]


def test_incremental_reindex_updates_only_changed_docs_and_deletes_removed(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)

    (source_dir / "keep.md").write_text("keep content stable", encoding="utf-8")
    (source_dir / "update.md").write_text("update before change", encoding="utf-8")
    (source_dir / "removed.md").write_text("this file will be removed", encoding="utf-8")

    initial_documents = load_documents(source_dir)
    removed_doc_id = {doc.source_path: doc.doc_id for doc in initial_documents}["removed.md"]
    initial_chunks = chunk_documents(initial_documents, chunk_size=500, chunk_overlap=50)
    initial_embeddings = ConstantEmbeddingClient(dimensions=3).embed_texts(
        [chunk.text for chunk in initial_chunks]
    )

    db_path = tmp_path / "rag" / "rag.db"
    persist_sqlite_index(
        db_path,
        documents=initial_documents,
        chunks=initial_chunks,
        embeddings=initial_embeddings,
    )

    (source_dir / "update.md").write_text("update after change", encoding="utf-8")
    (source_dir / "new.md").write_text("brand new file content", encoding="utf-8")
    (source_dir / "removed.md").unlink()

    embedding_client = TrackingEmbeddingClient(dimensions=4)
    metrics = run_incremental_reindex_job(
        source_dir=source_dir,
        db_path=db_path,
        chunk_size=500,
        chunk_overlap=50,
        embedding_client=embedding_client,
        embed_model="fake-embed",
    )

    assert metrics["mode"] == "incremental"
    assert metrics["scanned_files"] == 3
    assert metrics["unchanged"] == 1
    assert metrics["new"] == 1
    assert metrics["updated"] == 1
    assert metrics["removed"] == 1
    assert metrics["documents_total_after"] == 3
    assert metrics["chunks_total_after"] == 3
    assert metrics["max_embedding_dim"] == 4
    assert metrics["embed_model"] == "fake-embed"
    assert len(embedding_client.calls) == 2

    with sqlite3.connect(db_path) as connection:
        source_paths = [
            row[0]
            for row in connection.execute(
                "SELECT source_path FROM documents ORDER BY source_path"
            ).fetchall()
        ]
        assert source_paths == ["keep.md", "new.md", "update.md"]

        removed_doc_rows = connection.execute(
            "SELECT COUNT(*) FROM documents WHERE id = ?",
            (removed_doc_id,),
        ).fetchone()[0]
        removed_chunk_rows = connection.execute(
            "SELECT COUNT(*) FROM chunks WHERE doc_id = ?",
            (removed_doc_id,),
        ).fetchone()[0]

    assert removed_doc_rows == 0
    assert removed_chunk_rows == 0
