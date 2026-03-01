from pathlib import Path

from api.services.rag.ingest import ingest_documents


class FakeEmbeddingClient:
    def __init__(self, dimensions: int = 8) -> None:
        self._dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(index + 1) for index in range(self._dimensions)] for _ in texts]


def test_ingest_documents_creates_local_index(tmp_path: Path) -> None:
    source_dir = tmp_path / "sample_docs"
    source_dir.mkdir(parents=True)
    (source_dir / "a.txt").write_text("alpha beta gamma " * 40, encoding="utf-8")
    (source_dir / "b.md").write_text("# heading\n" + ("delta " * 60), encoding="utf-8")

    db_path = tmp_path / "rag_index" / "rag.db"

    summary = ingest_documents(
        source_dir=source_dir,
        db_path=db_path,
        chunk_size=120,
        chunk_overlap=20,
        embedding_client=FakeEmbeddingClient(dimensions=16),
    )

    assert summary.document_count == 2
    assert summary.chunk_count > 0
    assert db_path.exists()


def test_ingest_documents_writes_sqlite_index(tmp_path: Path) -> None:
    source_dir = tmp_path / "sample_docs"
    source_dir.mkdir(parents=True)
    (source_dir / "doc.txt").write_text("hello world " * 30, encoding="utf-8")

    db_path = tmp_path / "rag_index" / "rag.db"

    ingest_documents(
        source_dir=source_dir,
        db_path=db_path,
        chunk_size=80,
        chunk_overlap=10,
        embedding_client=FakeEmbeddingClient(dimensions=8),
    )

    assert db_path.exists()
