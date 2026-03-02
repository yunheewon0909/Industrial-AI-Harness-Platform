from pathlib import Path

import pytest

from api.services.rag.reindex_job_runner import run_reindex_job


class FakeEmbeddingClient:
    def __init__(self, dimensions: int) -> None:
        self._dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] * self._dimensions for _ in texts]


def test_run_reindex_job_writes_atomically_and_returns_metrics(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)
    (source_dir / "doc.txt").write_text("alpha beta gamma " * 80, encoding="utf-8")

    db_path = tmp_path / "rag" / "rag.db"
    metrics = run_reindex_job(
        source_dir=source_dir,
        db_path=db_path,
        chunk_size=120,
        chunk_overlap=20,
        embedding_client=FakeEmbeddingClient(dimensions=8),
    )

    assert db_path.exists()
    assert not db_path.with_suffix(".db.tmp").exists()
    assert metrics["documents"] == 1
    assert metrics["chunks"] > 0
    assert metrics["max_embedding_dim"] == 8


def test_run_reindex_job_self_check_failure_cleans_tmp_file(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)
    (source_dir / "doc.txt").write_text("hello world " * 40, encoding="utf-8")

    db_path = tmp_path / "rag" / "rag.db"

    with pytest.raises(ValueError, match="embedding dim is zero"):
        run_reindex_job(
            source_dir=source_dir,
            db_path=db_path,
            chunk_size=100,
            chunk_overlap=10,
            embedding_client=FakeEmbeddingClient(dimensions=0),
        )

    assert not db_path.exists()
    assert not db_path.with_suffix(".db.tmp").exists()

