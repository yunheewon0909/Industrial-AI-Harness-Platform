from pathlib import Path

from api.services.rag.ingest import ingest_documents


def test_ingest_documents_creates_local_index(tmp_path: Path) -> None:
    source_dir = tmp_path / "sample_docs"
    source_dir.mkdir(parents=True)
    (source_dir / "a.txt").write_text("alpha beta gamma " * 40, encoding="utf-8")
    (source_dir / "b.md").write_text("# heading\n" + ("delta " * 60), encoding="utf-8")

    output_dir = tmp_path / "rag_index"

    summary = ingest_documents(
        source_dir=source_dir,
        output_dir=output_dir,
        chunk_size=120,
        chunk_overlap=20,
        embedding_dim=16,
    )

    assert summary.document_count == 2
    assert summary.chunk_count > 0
    assert (output_dir / "index.json").exists()


def test_ingest_documents_overwrites_existing_index(tmp_path: Path) -> None:
    source_dir = tmp_path / "sample_docs"
    source_dir.mkdir(parents=True)
    (source_dir / "doc.txt").write_text("hello world " * 30, encoding="utf-8")

    output_dir = tmp_path / "rag_index"
    output_dir.mkdir(parents=True)
    (output_dir / "stale.txt").write_text("stale", encoding="utf-8")

    ingest_documents(
        source_dir=source_dir,
        output_dir=output_dir,
        chunk_size=80,
        chunk_overlap=10,
        embedding_dim=8,
    )

    assert not (output_dir / "stale.txt").exists()
    assert (output_dir / "index.json").exists()
