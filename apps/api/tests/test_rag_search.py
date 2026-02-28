from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.config import get_settings
from api.db import Base, get_engine
from api.main import app
from api.models import JobRecord
from api.services.rag.ingest import ingest_documents
from api.services.rag.query import search_index


@pytest.fixture
def rag_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[tuple[TestClient, Path]]:
    sqlite_db_path = tmp_path / "api-tests.db"
    index_dir = tmp_path / "rag_index"

    monkeypatch.setenv("API_DATABASE_URL", f"sqlite+pysqlite:///{sqlite_db_path}")
    monkeypatch.setenv("API_DB_ECHO", "false")
    monkeypatch.setenv("RAG_INDEX_DIR", str(index_dir))

    get_settings.cache_clear()
    get_engine.cache_clear()

    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    # keep existing API DB path healthy while testing rag route
    with Session(engine) as session:
        session.add(JobRecord(id="seed-job", status="queued"))
        session.commit()

    with TestClient(app) as client:
        yield client, index_dir

    engine.dispose()


def test_search_index_returns_ranked_hits(tmp_path: Path) -> None:
    source_dir = tmp_path / "sample_docs"
    source_dir.mkdir(parents=True)
    (source_dir / "robotics.txt").write_text(
        "robotics automation assembly line maintenance", encoding="utf-8"
    )
    (source_dir / "finance.txt").write_text(
        "financial forecast revenue accounting", encoding="utf-8"
    )

    index_dir = tmp_path / "rag_index"
    ingest_documents(
        source_dir=source_dir,
        output_dir=index_dir,
        chunk_size=120,
        chunk_overlap=20,
        embedding_dim=16,
    )

    hits = search_index(index_dir=index_dir, query_text="automation robotics", top_k=1)

    assert len(hits) == 1
    assert hits[0].source_path in {"robotics.txt", "finance.txt"}


def test_rag_search_endpoint_returns_hits(rag_client: tuple[TestClient, Path], tmp_path: Path) -> None:
    client, index_dir = rag_client

    source_dir = tmp_path / "sample_docs"
    source_dir.mkdir(parents=True)
    (source_dir / "ops.md").write_text(
        "predictive maintenance and automation for factories", encoding="utf-8"
    )

    ingest_documents(
        source_dir=source_dir,
        output_dir=index_dir,
        chunk_size=120,
        chunk_overlap=20,
        embedding_dim=16,
    )

    get_settings.cache_clear()

    response = client.get("/rag/search", params={"q": "maintenance automation", "k": 2})

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 1
    assert {"chunk_id", "source_path", "score", "text"}.issubset(payload[0].keys())


def test_rag_search_endpoint_without_index_returns_503(
    rag_client: tuple[TestClient, Path],
) -> None:
    client, _ = rag_client

    response = client.get("/rag/search", params={"q": "hello", "k": 2})

    assert response.status_code == 503
    assert "rag-ingest" in response.json()["detail"]
